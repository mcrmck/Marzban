import re
from datetime import datetime as dt
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User, UserResponse, UserStatus
from app.utils.system import readable_size
from app.crud import crud

statuses = {
    UserStatus.active: "✅",
    UserStatus.expired: "🕰",
    UserStatus.limited: "🪫",
    UserStatus.disabled: "❌",
    UserStatus.on_hold: "🔌",
}


def time_to_string(time: dt):
    now = dt.now()
    if time < now:
        delta = now - time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"about <code>{days}</code> days ago"
        elif hours > 0:
            return f"about <code>{hours}</code> hours ago"
        elif minutes > 0:
            return f"about <code>{minutes}</code> minutes ago"
        else:
            return "just now"
    else:
        delta = time - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"in about <code>{days}</code> days"
        elif hours > 0:
            return f"in about <code>{hours}</code> hours"
        elif minutes > 0:
            return f"in about <code>{minutes}</code> minutes"
        else:
            return "very soon"


def get_user_info_text(db_user: User, db: Session) -> str:
    user: UserResponse = UserResponse.model_validate(db_user, context={'db': db})
    data_limit = readable_size(user.data_limit) if user.data_limit else "Unlimited"
    used_traffic = readable_size(user.used_traffic) if user.used_traffic else "-"
    data_left = readable_size(user.data_limit - user.used_traffic) if user.data_limit else "-"
    on_hold_timeout = user.on_hold_timeout.strftime("%Y-%m-%d") if user.on_hold_timeout else "-"
    on_hold_duration = user.on_hold_expire_duration // (24*60*60) if user.on_hold_expire_duration else None
    expiry_date = dt.fromtimestamp(user.expire).date() if user.expire else "Never"
    time_left = time_to_string(dt.fromtimestamp(user.expire)) if user.expire else "-"
    online_at = time_to_string(user.online_at) if user.online_at else "-"
    sub_updated_at = time_to_string(user.sub_updated_at) if user.sub_updated_at else "-"
    if user.status == UserStatus.on_hold:
        expiry_text = f"⏰ <b>On Hold Duration:</b> <code>{on_hold_duration} days</code> (auto start at <code>{ on_hold_timeout}</code>)"
    else:
        expiry_text = f"📅 <b>Expiry Date:</b> <code>{expiry_date}</code> ({time_left})"
    return f"""\
{statuses[user.status]} <b>Status:</b> <code>{user.status.title()}</code>

🔤 <b>Username:</b> <code>{user.username}</code>

🔋 <b>Data limit:</b> <code>{data_limit}</code>
📶 <b>Data Used:</b> <code>{used_traffic}</code> (<code>{data_left}</code> left)
{expiry_text}

🔌 <b>Online at:</b> {online_at}
🔄 <b>Subscription updated at:</b> {sub_updated_at}
📱 <b>Subscription last agent:</b> <blockquote>{user.sub_last_user_agent or "-"}</blockquote>

📝 <b>Note:</b> <blockquote expandable>{user.note or "empty"}</blockquote>
👨‍💻 <b>Admin:</b> <code>{db_user.admin.username if db_user.admin else "-"}</code>
🚀 <b><a href="{user.subscription_url}">Subscription</a>:</b> <code>{user.subscription_url}</code>"""


def get_number_at_end(username: str):
    n = re.search(r'(\d+)$', username)
    if n:
        return n.group(1)


def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[UserResponse]:
    db_user = crud.get_user_by_telegram_id(db, telegram_id)
    if not db_user:
        return None
    return UserResponse.model_validate(db_user, context={'db': db})
