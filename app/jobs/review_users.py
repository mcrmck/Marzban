from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

import logging
from app.db import GetDB
from app.db.crud import get_users, update_user_status, start_user_expire, get_notification_reminder, reset_user_by_next
from app.db.models import UserStatus
from app.models.user import UserResponse, ReminderType
from app.xray import xray
from app.utils import report
from app.utils.helpers import calculate_expiration_days, calculate_usage_percent
from config import WEBHOOK_ADDRESS, JOB_REVIEW_USERS_INTERVAL, NOTIFY_DAYS_LEFT, NOTIFY_REACHED_USAGE_PERCENT

if TYPE_CHECKING:
    from app.db.models import User


def add_notification_reminders(db: Session, user: "User", now: datetime = datetime.utcnow()) -> None:
    if user.data_limit:
        usage_percent = calculate_usage_percent(user.used_traffic, user.data_limit)

        for percent in sorted(NOTIFY_REACHED_USAGE_PERCENT, reverse=True):
            if usage_percent >= percent:
                if not get_notification_reminder(db, user.id, ReminderType.data_usage, threshold=percent):
                    report.data_usage_percent_reached(
                        db, usage_percent, UserResponse.model_validate(user, context={'db': db}),
                        user.id, user.expire, threshold=percent
                    )
                break

    if user.expire:
        expire_days = calculate_expiration_days(user.expire)

        for days_left in sorted(NOTIFY_DAYS_LEFT):
            if expire_days <= days_left:
                if not get_notification_reminder(db, user.id, ReminderType.expiration_date, threshold=days_left):
                    report.expire_days_reached(
                        db, expire_days, UserResponse.model_validate(user, context={'db': db}),
                        user.id, user.expire, threshold=days_left
                    )
                break


def reset_user_by_next_report(db: Session, user: "User"):
    user = reset_user_by_next(db, user)
    xray.operations.update_user(user.id, db)
    report.user_data_reset_by_next(user=UserResponse.model_validate(user, context={'db': db}), user_admin=user.admin)


def check_user_data_usage(db: Session, user: "User"):
    if user.data_limit and user.used_traffic >= user.data_limit:
        user.status = UserStatus.limited
        db.commit()
        usage_percent = (user.used_traffic / user.data_limit) * 100 if user.data_limit else 0
        report.user_limited(
            db, usage_percent, UserResponse.model_validate(user, context={'db': db}),
        )


def check_user_expiration(db: Session, user: "User"):
    if user.expire and user.expire <= int(datetime.utcnow().timestamp()):
        user.status = UserStatus.expired
        db.commit()
        expire_days = (user.expire - int(datetime.utcnow().timestamp())) // (24 * 3600)
        report.user_expired(
            db, expire_days, UserResponse.model_validate(user, context={'db': db}),
        )


def review():
    now = datetime.utcnow()
    now_ts = now.timestamp()
    with GetDB() as db:
        for user in get_users(db, status=UserStatus.active):

            limited = user.data_limit and user.used_traffic >= user.data_limit
            expired = user.expire and user.expire <= now_ts

            if (limited or expired) and user.next_plan is not None:
                if user.next_plan is not None:

                    if user.next_plan.fire_on_either:
                        reset_user_by_next_report(db, user)
                        continue

                    elif limited and expired:
                        reset_user_by_next_report(db, user)
                        continue

            if limited:
                status = UserStatus.limited
            elif expired:
                status = UserStatus.expired
            else:
                if WEBHOOK_ADDRESS:
                    add_notification_reminders(db, user, now)
                continue

            xray.operations.remove_user(user)
            update_user_status(db, user, status)

            report.status_change(username=user.username, status=status,
                                 user=UserResponse.model_validate(user, context={'db': db}), user_admin=user.admin)

            logging.getLogger("marzban").debug(f"User \"{user.username}\" status changed to {status}")

        for user in get_users(db, status=UserStatus.on_hold):

            if user.edit_at:
                base_time = datetime.timestamp(user.edit_at)
            else:
                base_time = datetime.timestamp(user.created_at)

            # Check if the user is online After or at 'base_time'
            if user.online_at and base_time <= datetime.timestamp(user.online_at):
                status = UserStatus.active

            elif user.on_hold_timeout and (datetime.timestamp(user.on_hold_timeout) <= (now_ts)):
                # If the user didn't connect within the timeout period, change status to "Active"
                status = UserStatus.active

            else:
                continue

            update_user_status(db, user, status)
            start_user_expire(db, user)

            report.status_change(username=user.username, status=status,
                                 user=UserResponse.model_validate(user, context={'db': db}), user_admin=user.admin)

            logging.getLogger("marzban").debug(f"User \"{user.username}\" status changed to {status}")


# Job registration moved to app/jobs/__init__.py to avoid circular imports
