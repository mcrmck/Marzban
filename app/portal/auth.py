from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db import get_db, crud
from app.models.user import UserResponse
from config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

# This should be a secure secret key in production
SECRET_KEY = "your-secret-key-here"  # TODO: Move to environment variables
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: str = payload.get("sub")
        if account_number is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # TODO: Implement actual user lookup from database
    # For now, return a mock user for testing
    return UserResponse(
        id="1",
        account_number=account_number,
        is_active=True
    )


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db) # <--- Inject the DB session
) -> Optional[UserResponse]:
    """
    Attempts to get the current user from the access_token cookie
    by fetching from the database.
    """
    token = request.cookies.get("access_token")

    if not token:
        return None

    if token.startswith("Bearer "):
        token = token.split("Bearer ")[1]
    else:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_number: str = payload.get("sub")
        if account_number is None:
            return None


        # --- FETCH REAL USER FROM DB ---
        db_user = crud.get_user(db, account_number=account_number) # Use CRUD function

        if not db_user:
            return None


        # --- VALIDATE WITH PYDANTIC ---
        try:
            # Use model_validate for Pydantic v2.
            # This requires UserResponse to be configured with from_attributes=True
            user = UserResponse.model_validate(db_user)
            return user
        except ValidationError as e:
            return None
        # --- END VALIDATE ---

    except JWTError as e:
        return None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None