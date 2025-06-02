from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db import get_db, crud
from app.models.user import UserResponse
from config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, PORTAL_JWT_SECRET_KEY

SECRET_KEY = PORTAL_JWT_SECRET_KEY
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/client-portal/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def extract_token(request: Request) -> Optional[str]:
    """Extract token from either cookies or Authorization header."""
    # Try to get token from cookies first
    token = request.cookies.get("access_token")

    # If not in cookies, try Authorization header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1]

    return token

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials - user not logged in",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = extract_token(request)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: Optional[str] = payload.get("sub")
        if account_number is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    except Exception:
        raise credentials_exception

    db_user_orm = crud.get_user(db, account_number=account_number)

    if not db_user_orm:
        raise credentials_exception

    try:
        user = UserResponse.model_validate(db_user_orm, context={'db': db})
        return user
    except ValidationError:
        raise credentials_exception
    except Exception:
        raise credentials_exception

async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[UserResponse]:
    """
    Attempts to get the current user from the access_token cookie
    by fetching from the database. Returns None if not authenticated.
    """
    token = extract_token(request)
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: Optional[str] = payload.get("sub")
        if account_number is None:
            return None

        db_user_orm = crud.get_user(db, account_number=account_number)
        if not db_user_orm:
            return None

        user = UserResponse.model_validate(db_user_orm, context={'db': db})
        return user
    except (JWTError, ValidationError):
        return None
    except Exception:
        return None