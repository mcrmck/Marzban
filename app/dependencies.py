from typing import Optional, Union
from app.models.admin import AdminInDB, AdminValidationResult, Admin
from app.models.user import UserResponse, UserStatus # UserStatus might not be needed here directly
from app.db import Session, crud, get_db
from config import SUDOERS, SECRET_KEY, ALGORITHM # Ensure SECRET_KEY, ALGORITHM are in config
from fastapi import Depends, HTTPException, status # Added status
from datetime import datetime, timezone, timedelta
from fastapi.security import OAuth2PasswordBearer
from app.utils.jwt import get_subscription_payload # SECRET_KEY, ALGORITHM removed from here if now direct
from jose import jwt, JWTError # Added jose imports

import logging

logger = logging.getLogger("marzban")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def validate_admin(db: Session, username: str, password: str) -> Optional[AdminValidationResult]:
    """Validate admin credentials with environment variables or database."""
    if SUDOERS.get(username) == password:
        return AdminValidationResult(username=username, is_sudo=True)

    dbadmin = crud.get_admin(db, username)
    if dbadmin and AdminInDB.model_validate(dbadmin).verify_password(password):
        return AdminValidationResult(username=dbadmin.username, is_sudo=dbadmin.is_sudo)

    return None


def get_admin_by_username(username: str, db: Session = Depends(get_db)):
    """Fetch an admin by username from the database."""
    dbadmin = crud.get_admin(db, username)
    if not dbadmin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return dbadmin


def get_dbnode(node_id: int, db: Session = Depends(get_db)):
    """Fetch a node by its ID from the database, raising a 404 error if not found."""
    dbnode = crud.get_node_by_id(db, node_id)
    if not dbnode:
        raise HTTPException(status_code=404, detail="Node not found")
    return dbnode


def validate_dates(start: Optional[Union[str, datetime]], end: Optional[Union[str, datetime]]) -> tuple[datetime, datetime]:
    """Validate if start and end dates are correct and if end is after start."""
    try:
        if start:
            start_date = start if isinstance(start, datetime) else datetime.fromisoformat(
                start).astimezone(timezone.utc)
        else:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if end:
            end_date = end if isinstance(end, datetime) else datetime.fromisoformat(end).astimezone(timezone.utc)
            if start_date and end_date < start_date: # start_date will always exist here
                raise HTTPException(status_code=400, detail="Start date must be before end date")
        else:
            end_date = datetime.now(timezone.utc)

        return start_date, end_date
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date range or format")


def get_user_template(template_id: int, db: Session = Depends(get_db)):
    """Fetch a User Template by its ID, raise 404 if not found."""
    dbuser_template = crud.get_user_template(db, template_id)
    if not dbuser_template:
        raise HTTPException(status_code=404, detail="User Template not found")
    return dbuser_template


def get_validated_sub(
        token: str,
        db: Session = Depends(get_db)
) -> "UserResponse": # Return Pydantic model
    logger.info(f"get_validated_sub: Attempting to validate token: {token[:20]}...")

    payload = get_subscription_payload(token)
    if not payload:
        logger.error("get_validated_sub: get_subscription_payload returned None.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token payload (payload is None)")

    logger.info(f"get_validated_sub: Token payload received: {payload}")

    account_number_from_sub = payload.get('sub') # Default 'sub' claim for subject
    if not account_number_from_sub:
        account_number_from_sub = payload.get('account_number')
        if not account_number_from_sub:
            logger.error(f"get_validated_sub: 'sub' or 'account_number' missing in token payload. Keys: {list(payload.keys())}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account number missing in token")

    logger.info(f"get_validated_sub: Account number from token: {account_number_from_sub}")

    db_orm_user = crud.get_user(db, account_number_from_sub)
    if not db_orm_user:
        logger.error(f"get_validated_sub: User not found in DB for account_number: {account_number_from_sub}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found from token")

    logger.info(f"get_validated_sub: User {db_orm_user.account_number} found in DB. Created at: {db_orm_user.created_at}, Sub revoked at: {db_orm_user.sub_revoked_at}")

    token_created_at_val = payload.get('created_at')
    if token_created_at_val is None:
        token_created_at_val = payload.get('iat')
        if token_created_at_val is None:
            logger.error(f"get_validated_sub: Token creation timestamp ('created_at' or 'iat') missing in payload. Keys: {list(payload.keys())}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token creation time missing")
        else:
            logger.info(f"get_validated_sub: Using 'iat' as token creation timestamp value: {token_created_at_val}")
            # 'iat' is typically already a numeric timestamp
            token_created_at_ts = float(token_created_at_val)
    else:
        logger.info(f"get_validated_sub: Token 'created_at' timestamp value: {token_created_at_val}")
        # If 'created_at' is a datetime object (from get_subscription_payload), convert to timestamp
        if isinstance(token_created_at_val, datetime):
            token_created_at_ts = token_created_at_val.timestamp()
        else: # Assume it's already a numeric timestamp
            token_created_at_ts = float(token_created_at_val)

    logger.info(f"get_validated_sub: Processed token_created_at_ts: {token_created_at_ts}")

    db_user_created_at_ts = db_orm_user.created_at.timestamp() if isinstance(db_orm_user.created_at, datetime) else float(db_orm_user.created_at or 0)
    logger.info(f"get_validated_sub: DB user created_at_ts: {db_user_created_at_ts}, Token created_at_ts: {token_created_at_ts}")

    if db_user_created_at_ts > token_created_at_ts: # direct comparison of timestamps
        logger.error(f"get_validated_sub: User record created ({db_user_created_at_ts}) after token issuance ({token_created_at_ts}).")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User record created after token issuance")

    if db_orm_user.sub_revoked_at:
        db_user_sub_revoked_at_ts = db_orm_user.sub_revoked_at.timestamp() if isinstance(db_orm_user.sub_revoked_at, datetime) else float(db_orm_user.sub_revoked_at)
        logger.info(f"get_validated_sub: DB user sub_revoked_at_ts: {db_user_sub_revoked_at_ts}, Token created_at_ts: {token_created_at_ts}")
        if db_user_sub_revoked_at_ts > token_created_at_ts: # direct comparison of timestamps
            logger.error(f"get_validated_sub: Subscription revoked ({db_user_sub_revoked_at_ts}) after token issuance ({token_created_at_ts}).")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription revoked after token issuance")

    logger.info(f"get_validated_sub: Token validated successfully for user {db_orm_user.account_number}")

    # Convert SQLAlchemy User to UserResponse
    return UserResponse.model_validate(db_orm_user, context={'db': db})


def get_validated_user(
        account_number: str,
        admin: Admin = Depends(Admin.get_current),
        db: Session = Depends(get_db)
):
    db_orm_user = crud.get_user(db, account_number)
    if not db_orm_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return the ORM model for use in routers that call CRUD functions
    return db_orm_user


def get_expired_users_list(db: Session, admin: Admin, expired_after: Optional[datetime] = None, # Admin model from app.models.admin
                           expired_before: Optional[datetime] = None):
    expired_before = expired_before or datetime.now(timezone.utc)
    expired_after = expired_after or datetime.min.replace(tzinfo=timezone.utc)

    # crud.get_admin expects a username string
    dbadmin_orm = crud.get_admin(db, admin.username) # Fetch the ORM Admin model
    if not admin.is_sudo and not dbadmin_orm: # Should not happen if admin is validated by Admin.get_current
         raise HTTPException(status_code=403, detail="Admin performing action not found")

    dbusers_orm_list = crud.get_users(
        db=db,
        status=[UserStatus.expired, UserStatus.limited],
        admin=dbadmin_orm if not admin.is_sudo else None # Pass the ORM admin model
    )

    return [
        u for u in dbusers_orm_list
        if u.expire and expired_after.timestamp() <= u.expire <= expired_before.timestamp()
    ]


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)): # Return ORM User
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: Optional[str] = payload.get("sub")
        if account_number is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_orm = crud.get_user(db, account_number=account_number) # crud.get_user returns ORM User
    if user_orm is None:
        raise credentials_exception
    return user_orm # Return ORM User model