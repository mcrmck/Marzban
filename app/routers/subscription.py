import re
from distutils.version import LooseVersion # type: ignore

from fastapi import APIRouter, Depends, Header, Path, Request, Response
from fastapi.responses import HTMLResponse

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


@router.get("/{token}/")
@router.get("/{token}", include_in_schema=False)
def user_subscription(
    request: Request,
    db: Session = Depends(get_db), # db session for crud.update_user_sub
    db_user_response: UserResponse = Depends(get_validated_sub), # Renamed for clarity, this is Pydantic UserResponse
    user_agent: str = Header(default="")
):
    # db_user_response already includes active_node_id due to get_validated_sub -> crud.get_user -> get_user_queryset

    accept_header = request.headers.get("Accept", "")
    if "text/html" in accept_header and not user_agent: # Prioritize user_agent for config generation
        return HTMLResponse(
            render_template(
                "subscription/modern.html", # Assuming this template can handle user model
                {"user": db_user_response} # Pass Pydantic model
            )
        )

    # Ensure the ORM user object is fetched for crud.update_user_sub if it expects ORM
    # However, crud.update_user_sub currently takes dbuser: User (ORM), so we need to fetch it.
    # This is a bit awkward if get_validated_sub returns Pydantic.
    # For now, let's assume get_validated_sub can provide ORM or we fetch again.
    # To simplify, let's assume crud.update_user_sub is adapted or we pass the Pydantic model if sufficient.
    # Let's modify crud.update_user_sub to accept account_number or UserResponse if possible,
    # or fetch the ORM user here.

    orm_user_for_sub_update = crud.get_user_by_sub_token(db, db_user_response.account_number) # Fetch ORM user
    if orm_user_for_sub_update:
      crud.update_user_sub(db, orm_user_for_sub_update, user_agent)
    else: # Should not happen if get_validated_sub succeeded
      pass


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

    target_format = "v2ray" # Default
    media_type = "text/plain"
    as_base64 = True
    reverse_links = False # Most formats don't reverse by default from user_agent sniffing

    # User-Agent sniffing logic (remains largely the same)
    if re.match(r'^([Cc]lash-verge|[Cc]lash[-\.]?[Mm]eta|[Ff][Ll][Cc]lash|[Mm]ihomo)', user_agent):
        target_format, media_type, as_base64 = "clash-meta", "text/yaml", False
    elif re.match(r'^([Cc]lash|[Ss]tash)', user_agent):
        target_format, media_type, as_base64 = "clash", "text/yaml", False
    elif re.match(r'^(SFA|SFI|SFM|SFT|[Kk]aring|[Hh]iddify[Nn]ext)', user_agent):
        target_format, media_type, as_base64 = "sing-box", "application/json", False
    elif re.match(r'^(SS|SSR|SSD|SSS|Outline|Shadowsocks|SSconf)', user_agent):
        target_format, media_type, as_base64 = "outline", "application/json", False
    elif (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_V2RAYN) and (match := re.match(r'^v2rayN/(\d+\.\d+)', user_agent)):
        if LooseVersion(match.group(1)) >= LooseVersion("6.40"):
            target_format, media_type, as_base64 = "v2ray-json", "application/json", False
    elif (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_V2RAYNG) and (match := re.match(r'^v2rayNG/(\d+\.\d+\.\d+)', user_agent)):
        if LooseVersion(match.group(1)) >= LooseVersion("1.8.29"):
            target_format, media_type, as_base64 = "v2ray-json", "application/json", False
        elif LooseVersion(match.group(1)) >= LooseVersion("1.8.18"):
            target_format, media_type, as_base64, reverse_links = "v2ray-json", "application/json", False, True
    elif re.match(r'^[Ss]treisand', user_agent) and (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_STREISAND):
        target_format, media_type, as_base64 = "v2ray-json", "application/json", False
    elif (USE_CUSTOM_JSON_DEFAULT or USE_CUSTOM_JSON_FOR_HAPP) and (match := re.match(r'^Happ/(\d+\.\d+\.\d+)', user_agent)):
        if LooseVersion(match.group(1)) >= LooseVersion("1.63.1"):
            target_format, media_type, as_base64 = "v2ray-json", "application/json", False

    # Generate subscription based on detected format and active_node_id
    conf_content = generate_subscription(
        user=db_user_response, # Pass the Pydantic UserResponse
        config_format=target_format, # type: ignore
        as_base64=as_base64,
        reverse=reverse_links,
        active_node_id_override=db_user_response.active_node_id # Key change
    )
    return Response(content=conf_content, media_type=media_type, headers=response_headers)


@router.get("/{token}/info", response_model=SubscriptionUserResponse)
def user_subscription_info(
    db_user_response: UserResponse = Depends(get_validated_sub), # db_user_response is Pydantic UserResponse
):
    # Convert to SubscriptionUserResponse if needed, or ensure UserResponse matches its fields
    # For now, assume UserResponse is sufficient or SubscriptionUserResponse is a superset/compatible
    # If SubscriptionUserResponse has specific fields not in UserResponse, model_validate from db_user_response
    return SubscriptionUserResponse.model_validate(db_user_response.model_dump())


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