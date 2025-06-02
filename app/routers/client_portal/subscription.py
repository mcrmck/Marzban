import re
from distutils.version import LooseVersion # type: ignore
import logging

from fastapi import APIRouter, Depends, Header, Path, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db import Session, crud, get_db # crud.get_user_by_sub_token will be used by get_validated_sub
from app.dependencies import get_validated_sub, validate_dates
from app.models.user import SubscriptionUserResponse, UserResponse # UserResponse now includes active_node_id
from app.subscription.share import encode_title, generate_subscription
from app.templates import render_template
from config import (
    SUB_PROFILE_TITLE,
    SUB_SUPPORT_URL,
    SUB_UPDATE_INTERVAL,
    USE_CUSTOM_JSON_DEFAULT,
    USE_CUSTOM_JSON_FOR_HAPP,
    USE_CUSTOM_JSON_FOR_STREISAND,
    USE_CUSTOM_JSON_FOR_V2RAYN,
    USE_CUSTOM_JSON_FOR_V2RAYNG,
    XRAY_SUBSCRIPTION_PATH,
)

logger = logging.getLogger(__name__)

client_config = {
    "clash-meta": {"config_format": "clash-meta", "media_type": "text/yaml", "as_base64": False, "reverse": False},
    "sing-box": {"config_format": "sing-box", "media_type": "application/json", "as_base64": False, "reverse": False},
    "clash": {"config_format": "clash", "media_type": "text/yaml", "as_base64": False, "reverse": False},
    "v2ray": {"config_format": "v2ray", "media_type": "text/plain", "as_base64": True, "reverse": False},
    "outline": {"config_format": "outline", "media_type": "application/json", "as_base64": False, "reverse": False},
    "v2ray-json": {"config_format": "v2ray-json", "media_type": "application/json", "as_base64": False, "reverse": False}
}

router = APIRouter(tags=['Subscription'], prefix=f'/{XRAY_SUBSCRIPTION_PATH}')


def get_subscription_user_info(user: UserResponse) -> dict:
    return {
        "upload": 0, # Assuming upload is not tracked or is 0 for this info header
        "download": user.used_traffic,
        "total": user.data_limit if user.data_limit is not None else 0, # 0 for unlimited
        "expire": user.expire if user.expire is not None else 0, # 0 for no expiry
    }


@router.get("/sub/{token}", response_class=Response, name="user_subscription")
async def user_subscription(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    db_user_response: UserResponse = Depends(get_validated_sub),
):
    """
    Generate subscription configuration based on user agent
    """
    try:
        # Get the ORM user for subscription updates
        db_user = crud.get_user_by_id(db, db_user_response.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update subscription access time
        crud.update_user_subscription_access_time(db, db_user)

        # Detect client type from user agent
        user_agent = request.headers.get("user-agent", "").lower()
        client_type = None

        for client, patterns in client_config.items():
            if any(pattern in user_agent for pattern in patterns["patterns"]):
                client_type = client
                break

        if not client_type:
            # Default to v2ray if no specific client is detected
            client_type = "v2ray"

        # Generate subscription content
        subscription_content = generate_subscription(
            db_user_response,
            client_type,
            request.base_url,
            db
        )

        # Set response headers
        headers = {
            "content-type": client_config[client_type]["media_type"],
            "content-disposition": f'attachment; filename="{client_type}-config.{client_config[client_type]["extension"]}"'
        }

        return Response(
            content=subscription_content,
            headers=headers
        )

    except Exception as e:
        logger.error(f"Error generating subscription: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate subscription configuration"
        )

@router.get("/sub/{token}/info", response_class=JSONResponse, name="user_subscription_info")
async def user_subscription_info(
    token: str,
    db: Session = Depends(get_db),
    db_user_response: UserResponse = Depends(get_validated_sub),
):
    """
    Get user subscription information
    """
    try:
        return {
            "status": "success",
            "data": {
                "user": db_user_response.model_dump(exclude_none=True),
                "subscription_url": f"/sub/{token}"
            }
        }
    except Exception as e:
        logger.error(f"Error getting subscription info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get subscription information"
        )

@router.get("/sub/{token}/usage", response_class=JSONResponse, name="user_get_usage")
async def user_get_usage(
    token: str,
    db: Session = Depends(get_db),
    db_user_response: UserResponse = Depends(get_validated_sub),
):
    """
    Get user usage information
    """
    try:
        # Get the ORM user for usage data
        db_user = crud.get_user_by_id(db, db_user_response.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get usage data
        usage_data = {
            "upload": db_user.used_traffic.get("upload", 0),
            "download": db_user.used_traffic.get("download", 0),
            "total": db_user.used_traffic.get("total", 0)
        }

        return {
            "status": "success",
            "data": usage_data
        }
    except Exception as e:
        logger.error(f"Error getting usage data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get usage data"
        )

@router.get("/{token}/usage") # This endpoint might not be directly used by clients but is available
def user_get_usage(
    db_user_response: UserResponse = Depends(get_validated_sub), # Pydantic UserResponse
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db) # For fetching ORM user for crud.get_user_usages
):
    start_dt, end_dt = validate_dates(start, end)

    # crud.get_user_usages expects an ORM User. Fetch it.
    orm_user = crud.get_user_by_sub_token(db, db_user_response.account_number)
    if not orm_user: # Should not happen if get_validated_sub passed
        raise HTTPException(status_code=404, detail="User not found for usage query.")

    usages_data = crud.get_user_usages(db, orm_user, start_dt, end_dt)
    # Assuming db_user_response.username exists. If account_number is preferred:
    return {"usages": usages_data, "account_number": db_user_response.account_number}


@router.get("/{token}/{client_type}")
def user_subscription_with_client_type(
    request: Request,
    db_user_response: UserResponse = Depends(get_validated_sub), # Pydantic UserResponse
    client_type: str = Path(..., regex="^(" + "|".join(client_config.keys()) + ")$"), # More robust regex
    db: Session = Depends(get_db), # For update_user_sub
    # user_agent: str = Header(default="") # Not strictly needed here as client_type is explicit
):
    # db_user_response has active_node_id
    orm_user_for_sub_update = crud.get_user_by_sub_token(db, db_user_response.account_number)
    if orm_user_for_sub_update: # Update sub access time/agent
        user_agent_from_header = request.headers.get("user-agent", "") # Get user-agent if needed
        crud.update_user_sub(db, orm_user_for_sub_update, user_agent_from_header)

    response_headers = {
        "content-disposition": f'attachment; filename="{db_user_response.account_number}"',
        "profile-web-page-url": str(request.url), # Or a link to client portal account page
        "support-url": SUB_SUPPORT_URL,
        "profile-title": encode_title(SUB_PROFILE_TITLE),
        "profile-update-interval": SUB_UPDATE_INTERVAL,
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(db_user_response).items()
        )
    }

    config_params = client_config.get(client_type)
    if not config_params: # Should be caught by Path regex, but as a safeguard
        raise HTTPException(status_code=400, detail=f"Unsupported client type: {client_type}")

    conf_content = generate_subscription(
        user=db_user_response, # Pass Pydantic UserResponse
        config_format=config_params["config_format"], # type: ignore
        as_base64=config_params["as_base64"],
        reverse=config_params["reverse"],
        active_node_id_override=db_user_response.active_node_id # Key change
    )

    return Response(content=conf_content, media_type=config_params["media_type"], headers=response_headers)