from typing import Optional
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, field_validator

from app.db import Session, crud, get_db
from app.utils.jwt import get_admin_payload
from config import SUDOERS

logger = logging.getLogger("marzban")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/token")  # Admin view url


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Admin(BaseModel):
    username: str
    is_sudo: bool
    telegram_id: Optional[int] = None
    discord_webhook: Optional[str] = None
    users_usage: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("users_usage",  mode='before')
    def cast_to_int(cls, v):
        if v is None:  # Allow None values
            return v
        if isinstance(v, float):  # Allow float to int conversion
            return int(v)
        if isinstance(v, int):  # Allow integers directly
            return v
        raise ValueError("must be an integer or a float, not a string")  # Reject strings

    @classmethod
    def get_admin(cls, token: str, db: Session) -> Optional["Admin"]: # Return type is Pydantic Admin
        logger.debug(f"Validating admin token: {token[:20]}...")
        payload = get_admin_payload(token)
        if not payload:
            logger.warning("get_admin_payload returned None")
            return None

        username_from_token = payload.get('username')
        if not username_from_token:
            logger.warning("Token payload missing username")
            return None

        logger.debug(f"Looking up admin in database: {username_from_token}")
        db_admin_orm = crud.get_admin(db, username_from_token)

        if not db_admin_orm:
            logger.warning(f"Admin not found in database: {username_from_token}")
            return None

        # Check if password was reset after token issuance
        if db_admin_orm.password_reset_at:
            token_created_at_payload = payload.get("created_at")
            if token_created_at_payload is not None:
                logger.debug(f"Checking password reset time: {db_admin_orm.password_reset_at} vs token created at: {token_created_at_payload}")
                if db_admin_orm.password_reset_at.timestamp() > token_created_at_payload:
                    logger.warning(f"Token invalidated by password reset for admin: {username_from_token}")
                    return None
            else:
                logger.warning(f"Token missing created_at claim for admin: {username_from_token}")
                return None

        # Create Pydantic model from the ORM model fetched from the database
        pydantic_admin_instance = cls.model_validate(db_admin_orm)

        # Now, if the username is in SUDOERS, ensure their is_sudo status is True
        if username_from_token in SUDOERS:
            logger.debug(f"Admin {username_from_token} is in SUDOERS, ensuring is_sudo=True")
            pydantic_admin_instance.is_sudo = True

        logger.debug(f"Successfully validated admin token for: {username_from_token}")
        return pydantic_admin_instance

    @classmethod
    def get_current(cls,
                    db: Session = Depends(get_db),
                    token: str = Depends(oauth2_scheme)):
        logger.debug("Validating current admin token")
        admin = cls.get_admin(token, db)
        if not admin:
            logger.warning("Failed to validate current admin token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.debug(f"Successfully validated current admin: {admin.username}")
        return admin

    @classmethod
    def check_sudo_admin(cls,
                         db: Session = Depends(get_db),
                         token: str = Depends(oauth2_scheme)):
        logger.debug("Validating sudo admin token")
        admin = cls.get_admin(token, db)
        if not admin:
            logger.warning("Failed to validate sudo admin token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not admin.is_sudo:
            logger.warning(f"Non-sudo admin {admin.username} attempted sudo operation")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You're not allowed"
            )
        logger.debug(f"Successfully validated sudo admin: {admin.username}")
        return admin


class AdminCreate(Admin):
    password: str
    telegram_id: Optional[int] = None
    discord_webhook: Optional[str] = None

    @property
    def hashed_password(self):
        return pwd_context.hash(self.password)

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, value):
        if value and not value.startswith("https://discord.com"):
            raise ValueError("Discord webhook must start with 'https://discord.com'")
        return value


class AdminModify(BaseModel):
    password: Optional[str] = None
    is_sudo: bool
    telegram_id: Optional[int] = None
    discord_webhook: Optional[str] = None

    @property
    def hashed_password(self):
        if self.password:
            return pwd_context.hash(self.password)

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook(cls, value):
        if value and not value.startswith("https://discord.com"):
            raise ValueError("Discord webhook must start with 'https://discord.com'")
        return value


class AdminPartialModify(BaseModel): # Inherit from BaseModel directly for clarity in partial updates
    password: Optional[str] = None
    is_sudo: Optional[bool] = None
    telegram_id: Optional[int] = None
    discord_webhook: Optional[str] = None
    # Ensure all fields that can be partially updated are listed here with Optional and default to None

    @property
    def hashed_password(self):
        if self.password:
            return pwd_context.hash(self.password)
        return None

    @field_validator("discord_webhook")
    @classmethod
    def validate_discord_webhook_partial_modify(cls, value): # Renamed
        if value and not value.startswith("https://discord.com"): # Allow None/empty
            raise ValueError("Discord webhook must start with 'https://discord.com'")
        return value


class AdminInDB(Admin):
    username: str
    hashed_password: str

    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)


class AdminValidationResult(BaseModel):
    username: str
    is_sudo: bool
