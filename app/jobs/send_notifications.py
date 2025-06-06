from datetime import datetime as dt
from datetime import timedelta as td
from typing import Any, Dict, List

from fastapi.encoders import jsonable_encoder
from requests import Session

import logging
from app.db import GetDB
from app.db.models import NotificationReminder
from app.utils.notification import queue
from config import (JOB_SEND_NOTIFICATIONS_INTERVAL,
                    NUMBER_OF_RECURRENT_NOTIFICATIONS,
                    RECURRENT_NOTIFICATIONS_TIMEOUT, WEBHOOK_ADDRESS,
                    WEBHOOK_SECRET)

session = Session()

headers = {"x-webhook-secret": WEBHOOK_SECRET} if WEBHOOK_SECRET else None


def send(data: List[Dict[Any, Any]]) -> bool:
    """Send the notification to the webhook address provided by WEBHOOK_ADDRESS

    Args:
        data (List[Dict[Any, Any]]): list of json encoded notifications

    Returns:
        bool: returns True if an ok response received
    """

    result_list = []
    for webhook in WEBHOOK_ADDRESS:
        result = send_req(w_address=webhook, data=data)
        result_list.append(result)
    if True in result_list:
        return True
    else:
        return False


def send_req(w_address: str, data):
    try:
        logging.getLogger("marzban").info(f"Sending {len(data)} webhook updates to {w_address}")
        r = session.post(w_address, json=data, headers=headers)
        if r.ok:
            return True
        logging.getLogger("marzban").error(r)
    except Exception as err:
        logging.getLogger("marzban").error(err)
    return False


def send_notifications():
    if not queue:
        return

    notifications_to_send = list()
    try:
        while (notification := queue.popleft()):
            if (notification.tries > NUMBER_OF_RECURRENT_NOTIFICATIONS):
                continue
            if notification.send_at > dt.utcnow().timestamp():
                queue.append(notification)  # add it to the queue again for the next check
                continue
            notifications_to_send.append(notification)
    except IndexError:  # if the queue is empty
        pass

    if not notifications_to_send:
        return
    if not send([jsonable_encoder(notif) for notif in notifications_to_send]):
        for notification in notifications_to_send:
            if (notification.tries + 1) > NUMBER_OF_RECURRENT_NOTIFICATIONS:
                continue
            notification.tries += 1
            notification.send_at = (  # schedule notification for n seconds later
                dt.utcnow() + td(seconds=RECURRENT_NOTIFICATIONS_TIMEOUT)).timestamp()
            queue.append(notification)


def delete_expired_reminders() -> None:
    with GetDB() as db:
        db.query(NotificationReminder).filter(NotificationReminder.expires_at < dt.utcnow()).delete()
        db.commit()


# Function to register webhook jobs and shutdown handler
def register_webhook_jobs():
    if WEBHOOK_ADDRESS:
        from app import app, scheduler

        @app.on_event("shutdown")
        def app_shutdown():
            logging.getLogger("marzban").info("Sending pending notifications before shutdown...")
            send_notifications()

        logging.getLogger("marzban").info("Send webhook job started")
        scheduler.add_job(send_notifications, "interval",
                          seconds=JOB_SEND_NOTIFICATIONS_INTERVAL,
                          replace_existing=True)
        scheduler.add_job(delete_expired_reminders, "interval", hours=2, start_date=dt.utcnow() + td(minutes=1))
