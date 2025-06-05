import time
import jwt
import logging
from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from math import ceil
from typing import Union


from config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger("marzban")


@lru_cache(maxsize=None)
def get_secret_key():
    from app.db import GetDB, get_jwt_secret_key
    with GetDB() as db:
        key = get_jwt_secret_key(db)
        logger.debug(f"Retrieved JWT secret key: {key[:10]}...")
        return key


def create_admin_token(username: str, is_sudo=False) -> str:
    now = datetime.utcnow()
    data = {
        "sub": username, 
        "access": "sudo" if is_sudo else "admin", 
        "iat": now,
        "created_at": now.timestamp()  # Add created_at timestamp for admin model validation
    }
    if JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 0:
        expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        data["exp"] = expire
    logger.debug(f"Creating admin token with data: {data}")
    encoded_jwt = jwt.encode(data, get_secret_key(), algorithm="HS256")
    logger.debug(f"Created admin token: {encoded_jwt[:20]}...")
    return encoded_jwt


def get_admin_payload(token: str) -> Union[dict, None]:
    try:
        # Check if token is empty or None
        if not token or not token.strip():
            logger.warning("get_admin_payload: Empty or None token provided")
            return None
            
        # Add debug logging for token format
        logger.debug(f"get_admin_payload: Processing token of length {len(token)}, starts with: {token[:20]}...")
        
        payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])

        username: str = payload.get("sub")
        access: str = payload.get("access")
        if not username or access not in ('admin', 'sudo'):
            logger.warning(f"Invalid payload - username: {username}, access: {access}")
            return

        # Get created_at timestamp - prefer explicit created_at over iat
        created_at = None
        try:
            if 'created_at' in payload:
                created_at = payload['created_at']
                # If it's already a timestamp, use it directly
                if not isinstance(created_at, (int, float)):
                    created_at = datetime.utcfromtimestamp(payload['iat']).timestamp()
            elif 'iat' in payload:
                created_at = datetime.utcfromtimestamp(payload['iat']).timestamp()
            else:
                logger.warning("Token missing both 'created_at' and 'iat' claims")
        except Exception as e:
            logger.error(f"Error processing timestamp claims: {str(e)}")
            created_at = None

        result = {"username": username, "is_sudo": access == "sudo", "created_at": created_at}
        logger.debug(f"get_admin_payload: Successfully decoded token for user {username}")
        return result
    except jwt.exceptions.PyJWTError as e:
        logger.error(f"JWT decode error for token '{token[:20]}...': {str(e)}")
        return
    except Exception as e:
        logger.error(f"Unexpected error in get_admin_payload for token '{token[:20]}...': {str(e)}")
        return


def create_subscription_token(account_number: str) -> str:
    data = account_number + ',' + str(ceil(time.time()))
    data_b64_str = b64encode(data.encode('utf-8'), altchars=b'-_').decode('utf-8').rstrip('=')
    data_b64_sign = b64encode(
        sha256(
            (data_b64_str+get_secret_key()).encode('utf-8')
        ).digest(),
        altchars=b'-_'
    ).decode('utf-8')[:10]
    data_final = data_b64_str + data_b64_sign
    return data_final


def get_subscription_payload(token: str) -> Union[dict, None]:
    try:
        if len(token) < 15:
            return

        if token.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."):
            payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
            if payload.get("access") == "subscription":
                 return {"account_number": payload['sub'], "created_at": datetime.utcfromtimestamp(payload['iat'])}
            else:
                return
        else:
            u_token = token[:-10]
            u_signature = token[-10:]
            try:
                u_token_dec = b64decode(
                    (u_token.encode('utf-8') + b'=' * (-len(u_token.encode('utf-8')) % 4)),
                    altchars=b'-_', validate=True)
                u_token_dec_str = u_token_dec.decode('utf-8')
            except:
                logger.error(f"Error decoding token: {token}")
                return
            u_token_resign = b64encode(sha256((u_token+get_secret_key()).encode('utf-8')
                                              ).digest(), altchars=b'-_').decode('utf-8')[:10]
            if u_signature == u_token_resign:
                u_account_number = u_token_dec_str.split(',')[0] # Changed from u_username
                u_created_at = int(u_token_dec_str.split(',')[1])
                return {"account_number": u_account_number, "created_at": datetime.utcfromtimestamp(u_created_at)}
            else:
                return
    except jwt.exceptions.PyJWTError:
        return
