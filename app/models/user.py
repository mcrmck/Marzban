import secrets
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    # EmailStr, # Not used here anymore
)

from app import xray
from app.models.admin import Admin # Assuming Admin model doesn't need username changes reflected here for User model
from app.models.proxy import ProxySettings, ProxyTypes
from app.subscription.share import generate_v2ray_links # Check if this uses username
from app.utils.jwt import create_subscription_token # Check if this uses username
from config import XRAY_SUBSCRIPTION_PATH, XRAY_SUBSCRIPTION_URL_PREFIX


class ReminderType(str, Enum):
    expiration_date = "expiration_date"
    data_usage = "data_usage"


class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"  # Represents pending payment or manually disabled
    limited = "limited"
    expired = "expired"
    on_hold = "on_hold"


class UserStatusModify(str, Enum):
    active = "active"
    disabled = "disabled"
    on_hold = "on_hold"


class UserStatusCreate(str, Enum):
    active = "active"
    on_hold = "on_hold"
    disabled = "disabled" # Added: for initial registration, pending payment


class UserDataLimitResetStrategy(str, Enum):
    no_reset = "no_reset"
    day = "day"
    week = "week"
    month = "month"
    year = "year"


class NextPlanModel(BaseModel):
    data_limit: Optional[int] = None
    expire: Optional[int] = None
    add_remaining_traffic: bool = False
    fire_on_either: bool = True
    model_config = ConfigDict(from_attributes=True)


class User(BaseModel): # This is the base Pydantic model for User data
    account_number: str = Field(..., description="Account number for the user (UUID)")
    proxies: Dict[ProxyTypes, ProxySettings] = Field(default_factory=dict)
    expire: Optional[int] = Field(None, nullable=True)
    data_limit: Optional[int] = Field(
        default=None, ge=0, description="data_limit can be 0 or greater" # ge=0 was from original
    )
    data_limit_reset_strategy: UserDataLimitResetStrategy = (
        UserDataLimitResetStrategy.no_reset
    )
    # REMOVED: 'inbounds' field. Admins don't set this as a restriction.
    # User.inbounds property on SQLAlchemy model provides all available ones.
    # This will be populated in UserResponse from the ORM model.
    note: Optional[str] = Field(None, nullable=True)
    sub_updated_at: Optional[datetime] = Field(None, nullable=True)
    sub_last_user_agent: Optional[str] = Field(None, nullable=True)
    online_at: Optional[datetime] = Field(None, nullable=True)
    on_hold_expire_duration: Optional[int] = Field(None, nullable=True)
    on_hold_timeout: Optional[Union[datetime, None]] = Field(None, nullable=True)
    auto_delete_in_days: Optional[int] = Field(None, nullable=True)
    next_plan: Optional[NextPlanModel] = Field(None, nullable=True)

    @field_validator('data_limit', mode='before')
    def cast_to_int(cls, v):
        # ... (existing logic)
        if v is None: return v
        if isinstance(v, (float, int)): return int(v)
        raise ValueError("data_limit must be an integer or a float")

    @field_validator("proxies", mode="before")
    def validate_proxies(cls, v, values, **kwargs):
        # ... (existing logic)
        if v is None: return {}
        return {
            ProxyTypes(proxy_type_key): ProxySettings.from_dict(
                ProxyTypes(proxy_type_key), v.get(proxy_type_key, {})
            )
            for proxy_type_key in v
        }

    @field_validator("note") # Removed check_fields=False, it's default in Pydantic v2 for single field
    @classmethod
    def validate_note(cls, v):
        # ... (existing logic)
        if v and len(v) > 500:
            raise ValueError("User's note can be a maximum of 500 character")
        return v

    @field_validator("on_hold_expire_duration", "on_hold_timeout", mode="before")
    def validate_timeout(cls, v, info): # Pydantic v2 uses info (ValidationInfo)
        # ... (existing logic)
        if v in (0, None): return None
        return v


class UserCreate(User):
    account_number: Optional[str] = Field(None, description="Account number (UUID), auto-generated if not provided")
    status: UserStatusCreate = UserStatusCreate.disabled
    # REMOVED: inbounds: Optional[Dict[str, List[str]]] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, json_schema_extra={ # Added from_attributes=True
        "example": {
            "account_number": "35e4e39c-7d5c-4f4b-8b71-558e4f37ff53",
            "proxies": {
                "vmess": {"id": "some-uuid-for-vmess"},
                "vless": {},
            },
            # "inbounds" example removed
            "next_plan": {  },
            "expire": 0, "data_limit": 0, "status": "disabled",
            # ... other fields
        }
    })

    # REMOVED: excluded_inbounds property
    # REMOVED: validate_inbounds validator (as 'inbounds' field is removed)

    @field_validator("status", mode="before")
    def validate_status(cls, status, info): # Pydantic v2 uses info
        # ... (existing logic, ensure `info.data.get` is used instead of `values.data.get`)
        on_hold_expire_duration = info.data.get("on_hold_expire_duration")
        expire = info.data.get("expire")
        if status == UserStatusCreate.on_hold:
            if not on_hold_expire_duration or on_hold_expire_duration == 0:
                raise ValueError("User cannot be on hold without a valid on_hold_expire_duration.")
            if expire is not None and expire != 0:
                raise ValueError("User cannot be on hold with a specific expiration date set. Use on_hold_expire_duration.")
        return status


class UserModify(User):
    account_number: Optional[str] = Field(None, description="Account number (UUID), should not be changed here, used for path param.")
    status: Optional[UserStatusModify] = None
    data_limit_reset_strategy: Optional[UserDataLimitResetStrategy] = None
    proxies: Optional[Dict[ProxyTypes, ProxySettings]] = Field(default_factory=dict)
    # REMOVED: inbounds: Optional[Dict[ProxyTypes, List[str]]] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, json_schema_extra={ # Added from_attributes=True
        "example": {
            # "inbounds" example removed
            # ... other fields
        }
    })

    # REMOVED: excluded_inbounds property
    # REMOVED: validate_inbounds_modify validator

    @field_validator("proxies", mode="before")
    def validate_proxies_modify(cls, v, info): # Pydantic v2 uses info
        # ... (existing logic, use info.data if needed)
        if v is None: return None
        return {
            ProxyTypes(proxy_type_key): ProxySettings.from_dict(
                ProxyTypes(proxy_type_key), v.get(proxy_type_key, {})
            )
            for proxy_type_key in v
        }

    @field_validator("status", mode="before")
    def validate_status_modify(cls, status, info): # Pydantic v2 uses info
        # ... (existing logic, use info.data.get)
        if status is None: return None
        on_hold_expire_duration = info.data.get("on_hold_expire_duration")
        expire = info.data.get("expire")
        if status == UserStatusModify.on_hold:
            if on_hold_expire_duration is not None and on_hold_expire_duration == 0 :
                raise ValueError("User cannot be on hold without a valid on_hold_expire_duration.")
            if expire is not None and expire != 0:
                raise ValueError("User cannot be on hold with a specific expiration date set.")
        return status

class UserResponse(User):
    id: int # Assuming User ORM model has an id, add if not already in base Pydantic User
    status: UserStatus
    used_traffic: int
    lifetime_used_traffic: int = 0
    created_at: datetime
    links: List[str] = Field(default_factory=list)
    subscription_url: str = ""

    # ADDED: inbounds field, will be populated from ORM User.inbounds property
    inbounds: Dict[ProxyTypes, List[str]] = Field(default_factory=dict)

    # REMOVED: excluded_inbounds: Dict[ProxyTypes, List[str]] = Field(default_factory=dict)

    admin: Optional[Admin] = None # Or AdminResponse model
    model_config = ConfigDict(from_attributes=True) # Enables ORM mode

    @model_validator(mode="after")
    def build_dynamic_fields(self) -> 'UserResponse':
        # The 'inbounds' field should be automatically populated from the
        # User ORM model's 'inbounds' property due to from_attributes=True.
        # If it's not, and you have access to the ORM object (e.g. self.__pydantic_private__.get('_orm_model')),
        # you could populate it here, but Pydantic v2 aims to make this more direct.

        if not self.links and self.proxies and self.inbounds:
             # generate_v2ray_links now uses self.inbounds which reflects all available inbounds
            self.links = generate_v2ray_links(
                proxies=self.proxies,
                inbounds_config=self.inbounds, # Pass the populated inbounds
                extra_data=self.model_dump(), # Pass current model state
                reverse=False,
            )
        if not self.subscription_url:
            salt = secrets.token_hex(8)
            url_prefix = (XRAY_SUBSCRIPTION_URL_PREFIX).replace('*', salt)
            token = create_subscription_token(self.account_number)
            self.subscription_url = f"{url_prefix}/{XRAY_SUBSCRIPTION_PATH}/{token}"
        return self

    @field_validator("proxies", mode="before")
    def validate_proxies_response(cls, v, info):
        # ... (existing logic from your file for UserResponse)
        if isinstance(v, list): # Assuming v could be a list of DB proxy objects
            v_dict = {}
            for p_obj in v:
                if hasattr(p_obj, 'type') and hasattr(p_obj, 'settings'):
                    try:
                        # Ensure p_obj.type is converted to ProxyTypes enum if it's not already
                        proxy_type_enum = ProxyTypes(p_obj.type) if not isinstance(p_obj.type, ProxyTypes) else p_obj.type
                        v_dict[proxy_type_enum] = p_obj.settings
                    except ValueError: # Handle cases where p_obj.type isn't a valid ProxyTypes member
                        pass
            v = v_dict

        validated_proxies = {}
        if v:
            for proxy_type_key, settings_val in v.items():
                try:
                    proxy_type_enum = ProxyTypes(str(proxy_type_key)) if not isinstance(proxy_type_key, ProxyTypes) else proxy_type_key
                    validated_proxies[proxy_type_enum] = ProxySettings.from_dict(proxy_type_enum, settings_val if settings_val else {})
                except ValueError:
                    pass
        return validated_proxies

    @field_validator("used_traffic", "lifetime_used_traffic", mode='before')
    def cast_traffic_to_int(cls, v):
        # ... (existing logic)
        if v is None: return 0
        if isinstance(v, (float, int)): return int(v)
        raise ValueError("Traffic value must be an integer or a float")


class SubscriptionUserResponse(UserResponse):
    admin: Optional[Admin] = Field(default=None, exclude=True)
    # excluded_inbounds was removed from UserResponse
    note: Optional[str] = Field(None, exclude=True)
    # 'inbounds' is kept in UserResponse. If you want to exclude it from subscription info:
    # inbounds: Optional[Dict[ProxyTypes, List[str]]] = Field(None, exclude=True)
    auto_delete_in_days: Optional[int] = Field(None, exclude=True)
    model_config = ConfigDict(from_attributes=True)



class UsersResponse(BaseModel):
    users: List[UserResponse]
    total: int


class UserUsageResponse(BaseModel):
    node_id: Union[int, None] = None
    node_name: str
    used_traffic: int

    @field_validator("used_traffic",  mode='before')
    def cast_usage_traffic_to_int(cls, v): # Renamed
        if v is None:
            return 0 # Default to 0, or handle as error
        if isinstance(v, float):
            return int(v)
        if isinstance(v, int):
            return v
        raise ValueError("Traffic usage must be an integer or a float")


class UserUsagesResponse(BaseModel):
    account_number: str # Changed from username
    usages: List[UserUsageResponse]


class UsersUsagesResponse(BaseModel):
    usages: List[UserUsageResponse] # This seems to be a list of individual node usages, not grouped by user.
                                   # If it's for ALL users' usages combined, the name might be misleading.
                                   # If it's supposed to be List[UserUsagesResponse], then it needs adjustment.
                                   # Assuming it's a flat list of usages across users/nodes.