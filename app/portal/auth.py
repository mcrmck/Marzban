from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer # Will be replaced for cookie auth
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db import get_db, crud
from app.models.user import UserResponse # Ensure this is the Pydantic model
from config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, PORTAL_JWT_SECRET_KEY # Using PORTAL_JWT_SECRET_KEY from config

# Ensure PORTAL_JWT_SECRET_KEY is defined in your config.py or environment
# Example: PORTAL_JWT_SECRET_KEY = "your-very-secure-secret-key-for-portal"
# SECRET_KEY = os.getenv("PORTAL_JWT_SECRET_KEY", "a-default-fallback-secret-if-not-set") # Get from env
SECRET_KEY = PORTAL_JWT_SECRET_KEY # Directly use from config import
ALGORITHM = "HS256"

# oauth2_scheme is not directly used by get_current_user for cookie auth anymore,
# but can be kept if other parts of your API (not client-portal) use it for header-based auth.
# For client portal cookie auth, we'll read directly from the request.
# If tokenUrl is for a different auth system, it can remain.
# If it was intended for client-portal login, it's superseded by the form post to /client-portal/token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/client-portal/token") # Or adjust if tokenUrl is different

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user( # Renamed parameter for clarity
    request: Request, # Changed dependency to Request to access cookies
    db: Session = Depends(get_db)
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials - user not logged in", # More specific detail
        headers={"WWW-Authenticate": "Bearer"}, # Keep for consistency if other parts use Bearer
    )


    token = request.cookies.get("access_token")

    if not token:
        raise credentials_exception

    if token.startswith("Bearer "):
        token = token.split("Bearer ")[1]
    else:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: Optional[str] = payload.get("sub")
        if account_number is None:
            raise credentials_exception
    except JWTError as e:
        raise credentials_exception
    except Exception as e:
        raise credentials_exception

    # --- FETCH REAL USER FROM DB ---
    db_user_orm = crud.get_user(db, account_number=account_number)

    if not db_user_orm:
        raise credentials_exception

    # --- VALIDATE WITH PYDANTIC ---
    try:
        user = UserResponse.model_validate(db_user_orm)
        return user
    except ValidationError as e:
        raise credentials_exception
    except Exception as e:
        raise credentials_exception


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[UserResponse]:
    """
    Attempts to get the current user from the access_token cookie
    by fetching from the database. Returns None if not authenticated.
    """
    token = request.cookies.get("access_token")

    if not token:
        return None

    # Ensure the "Bearer " prefix is handled consistently
    if token.startswith("Bearer "):
        token = token.split("Bearer ")[1]
    else:
        # If the token doesn't have the prefix, it's likely invalid or not set by our system
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: Optional[str] = payload.get("sub")
        if account_number is None:
            return None

        db_user_orm = crud.get_user(db, account_number=account_number)
        if not db_user_orm:
            return None

        user = UserResponse.model_validate(db_user_orm)
        return user
    except (JWTError, ValidationError): # Catch both JWT and Pydantic validation errors
        return None
    except Exception: # Catch any other unexpected errors
        # import traceback
        # traceback.print_exc() # Good for server-side debugging
        return None
