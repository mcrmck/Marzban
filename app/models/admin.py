from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, field_validator

from app.db import Session, crud, get_db
from app.utils.jwt import get_admin_payload
from config import SUDOERS

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
        payload = get_admin_payload(token)
        if not payload:
            return None

        username_from_token = payload.get('username')
        if not username_from_token:
            return None

        db_admin_orm = crud.get_admin(db, username_from_token)

        if not db_admin_orm:
            # logger.warning(f"Pydantic Admin.get_admin: Admin ORM object not found in DB for username '{username_from_token}'. Authentication will fail.")
            return None # Admin MUST exist in the database to be considered valid by this method.

        # Check if password was reset after token issuance
        if db_admin_orm.password_reset_at:
            token_created_at_payload = payload.get("created_at") # Assuming "created_at" is a Unix timestamp in the JWT payload
            if token_created_at_payload is not None: # Ensure the claim exists
                # Convert db_admin_orm.password_reset_at (datetime) to timestamp for comparison
                if db_admin_orm.password_reset_at.timestamp() > token_created_at_payload:
                    # logger.warning(f"Pydantic Admin.get_admin: Token for '{username_from_token}' is invalid due to password reset after token creation.")
                    return None
            else:
                # logger.warning(f"Pydantic Admin.get_admin: Token for '{username_from_token}' is missing 'created_at' claim, cannot validate against password_reset_at.")
                # Depending on security policy, you might deny access if created_at is missing and password_reset_at is set
                return None

        # Create Pydantic model from the ORM model fetched from the database
        pydantic_admin_instance = cls.model_validate(db_admin_orm)

        # Now, if the username is in SUDOERS, ensure their is_sudo status is True
        # This means SUDOERS acts as an override or guarantee for sudo status for DB users.
        if username_from_token in SUDOERS:
            pydantic_admin_instance.is_sudo = True
            # Optional: You might want to log if db_admin_orm.is_sudo was False but SUDOERS made it True,
            # or even update the DB record to reflect this, though this function's primary role is auth.
            # if not db_admin_orm.is_sudo:
            #     logger.info(f"Admin '{username_from_token}' is in SUDOERS, ensuring is_sudo=True (DB was {db_admin_orm.is_sudo}).")

        return pydantic_admin_instance

    @classmethod
    def get_current(cls,
                    db: Session = Depends(get_db),
                    token: str = Depends(oauth2_scheme)):
        admin = cls.get_admin(token, db)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return admin

    @classmethod
    def check_sudo_admin(cls,
                         db: Session = Depends(get_db),
                         token: str = Depends(oauth2_scheme)):
        admin = cls.get_admin(token, db)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not admin.is_sudo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You're not allowed"
            )
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


class AdminPartialModify(AdminModify):
    __annotations__ = {k: Optional[v] for k, v in AdminModify.__annotations__.items()}


class AdminInDB(Admin):
    username: str
    hashed_password: str

    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)


class AdminValidationResult(BaseModel):
    username: str
    is_sudo: bool
