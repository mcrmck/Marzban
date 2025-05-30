import re
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

# USERNAME_REGEXP is not needed anymore
# USERNAME_REGEXP = re.compile(r"^(?=\w{3,32}\b)[a-zA-Z0-9-_@.]+(?:_[a-zA-Z0-9-_@.]+)*$")


class ReminderType(str, Enum):
    expiration_date = "expiration_date"
    data_usage = "data_usage"


class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"
    limited = "limited"
    expired = "expired"
    on_hold = "on_hold"


class UserStatusModify(str, Enum):
    active = "active"
    disabled = "disabled"
    on_hold = "on_hold"


class UserStatusCreate(str, Enum):
    active = "active"
    on_hold = "on_hold" # No 'disabled' on create


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


class User(BaseModel):
    account_number: str = Field(..., description="Account number for the user (UUID)") # Added (UUID)
    proxies: Dict[ProxyTypes, ProxySettings] = {}
    expire: Optional[int] = Field(None, nullable=True)
    data_limit: Optional[int] = Field(
        ge=0, default=None, description="data_limit can be 0 or greater"
    )
    data_limit_reset_strategy: UserDataLimitResetStrategy = (
        UserDataLimitResetStrategy.no_reset
    )
    inbounds: Dict[ProxyTypes, List[str]] = {}
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
        if v is None:
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, int):
            return v
        # Removed check for string, as it should not be a string.
        # If it could be a string representing a number, add int(v) attempt.
        raise ValueError("data_limit must be an integer or a float")


    @field_validator("proxies", mode="before")
    def validate_proxies(cls, v, values, **kwargs): # values is not used, can be removed if not needed by other logic
        if v is None:
            return {}
        return {
            proxy_type: ProxySettings.from_dict(
                proxy_type, v.get(proxy_type, {}))
            for proxy_type in v
        }

    # Username validation removed
    # @field_validator("username", check_fields=False)
    # @classmethod
    # def validate_username(cls, v):
    #     if not USERNAME_REGEXP.match(v):
    #         raise ValueError(
    #             "Username only can be 3 to 32 characters and contain a-z, 0-9, and underscores in between."
    #         )
    #     return v

    @field_validator("note", check_fields=False) # check_fields=False is deprecated, use model_validator or root_validator
    @classmethod
    def validate_note(cls, v):
        if v and len(v) > 500:
            raise ValueError("User's note can be a maximum of 500 character")
        return v

    @field_validator("on_hold_expire_duration", "on_hold_timeout", mode="before")
    def validate_timeout(cls, v, values): # 'values' is not used, can be removed
        if (v in (0, None)): # 'v is None or v == 0' is clearer
            return None
        return v

class UserCreate(User):
    # username: str # Removed
    # password: str # Removed, as per migration script logic
    account_number: Optional[str] = Field(None, description="Account number (UUID), auto-generated if not provided") # Made optional for auto-generation
    status: UserStatusCreate = UserStatusCreate.active # Default to active
    inbounds: Optional[Dict[str, List[str]]] = Field(default_factory=dict) # Default to empty dict

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "account_number": "35e4e39c-7d5c-4f4b-8b71-558e4f37ff53", # Example UUID
            # "email": "user@example.com", # Removed as per migration
            # "password": "password123", # Removed as per migration
            "proxies": {
                "vmess": {"id": "some-uuid-for-vmess"}, # Example with a placeholder
                "vless": {},
            },
            "inbounds": {
                "vmess": ["VMess TCP", "VMess Websocket"],
                "vless": ["VLESS TCP REALITY", "VLESS GRPC REALITY"],
            },
            "next_plan": {
                "data_limit": 0,
                "expire": 0,
                "add_remaining_traffic": False,
                "fire_on_either": True
            },
            "expire": 0,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": "Sample user note",
            "on_hold_timeout": "2023-11-03T20:30:00",
            "on_hold_expire_duration": 0, # This would be problematic if status is on_hold
        }
    })

    @property
    def excluded_inbounds(self):
        excluded = {}
        if not self.inbounds:
            return excluded

        for proxy_type in self.proxies:
            excluded[proxy_type] = []
            # Ensure xray.config.inbounds_by_protocol exists and is a dict/map
            for inbound in xray.config.inbounds_by_protocol.get(proxy_type, []):
                # Ensure self.inbounds.get(proxy_type, []) is valid
                if inbound.get("tag") not in self.inbounds.get(proxy_type, []): # Defensive get for inbound's tag
                    excluded[proxy_type].append(inbound.get("tag"))
        return excluded

    @field_validator("inbounds", mode="before")
    def validate_inbounds(cls, inbounds, values, **kwargs): # values and kwargs not used
        if inbounds is None:
            return {}

        proxies = values.data.get("proxies", {}) # Default to empty dict

        # delete inbounds that are for protocols not activated
        for proxy_type in list(inbounds.keys()): # Iterate over keys copy
            if proxy_type not in proxies:
                del inbounds[proxy_type]

        # check by proxies to ensure that every protocol has inbounds set
        for proxy_type in proxies:
            tags = inbounds.get(proxy_type)

            if tags:
                for tag in tags:
                    if tag not in xray.config.inbounds_by_tag: # Ensure inbounds_by_tag exists
                        raise ValueError(f"Inbound {tag} doesn't exist")
            else: # If tags is None or empty list
                inbounds[proxy_type] = [
                    i.get("tag") # Defensive get
                    for i in xray.config.inbounds_by_protocol.get(proxy_type, []) if i.get("tag") # Ensure tag exists
                ]
        return inbounds

    @field_validator("status", mode="before")
    def validate_status(cls, status, values):
        on_hold_expire_duration = values.data.get("on_hold_expire_duration")
        expire = values.data.get("expire")
        if status == UserStatusCreate.on_hold:
            if not on_hold_expire_duration or on_hold_expire_duration == 0:
                raise ValueError("User cannot be on hold without a valid on_hold_expire_duration.")
            if expire is not None and expire != 0: # if expire is set to a specific date
                raise ValueError("User cannot be on hold with a specific expiration date set. Use on_hold_expire_duration.")
        return status


class UserModify(User):
    account_number: Optional[str] = Field(None, description="Account number (UUID), should not be changed here, used for path param.")
    status: Optional[UserStatusModify] = None # Optional on modify
    data_limit_reset_strategy: Optional[UserDataLimitResetStrategy] = None # Optional on modify
    proxies: Optional[Dict[ProxyTypes, ProxySettings]] = Field(default_factory=dict)
    inbounds: Optional[Dict[ProxyTypes, List[str]]] = Field(default_factory=dict)


    model_config = ConfigDict(json_schema_extra={
        "example": {
            # account_number is not in body for modify, it's in path
            "proxies": {
                "vmess": {"id": "some-uuid-for-vmess"},
                "vless": {},
            },
            "inbounds": {
                "vmess": ["VMess TCP", "VMess Websocket"],
                "vless": ["VLESS TCP REALITY", "VLESS GRPC REALITY"],
            },
            "next_plan": {
                "data_limit": 0,
                "expire": 0,
                "add_remaining_traffic": False,
                "fire_on_either": True
            },
            "expire": 0,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": "Updated note",
            "on_hold_timeout": "2023-11-03T20:30:00",
            "on_hold_expire_duration": 0,
        }
    })

    @property
    def excluded_inbounds(self):
        excluded = {}
        if not self.inbounds: return excluded
        for proxy_type in self.inbounds:
            excluded[proxy_type] = []
            for inbound in xray.config.inbounds_by_protocol.get(proxy_type, []):
                if inbound.get("tag") not in self.inbounds.get(proxy_type, []):
                    excluded[proxy_type].append(inbound.get("tag"))
        return excluded

    @field_validator("inbounds", mode="before")
    def validate_inbounds(cls, inbounds, values, **kwargs):
        if not inbounds: return {} # Allow empty inbounds on modify

        proxies_in_payload = values.data.get("proxies") # Check if proxies are being modified too

        for proxy_type, tags in list(inbounds.items()): # Iterate over copy
            # If proxies are part of the payload and this proxy_type is not in it,
            # it might mean we are trying to set inbounds for a proxy not being (re)defined.
            # This logic might need refinement based on desired behavior (e.g. only validate if proxies also present).
            if proxies_in_payload is not None and proxy_type not in proxies_in_payload:
                # Or, if modifying inbounds independently is allowed, this check might be too strict.
                # For now, assume inbounds are validated against existing or concurrently provided proxies.
                pass


            if tags is None: # Allow explicitly setting inbounds to None for a proxy type (to clear them?)
                inbounds[proxy_type] = [] # Or handle as per desired logic
                continue

            for tag in tags:
                if tag not in xray.config.inbounds_by_tag:
                    raise ValueError(f"Inbound {tag} doesn't exist")
        return inbounds


    @field_validator("proxies", mode="before")
    def validate_proxies_modify(cls, v, values, **kwargs): # Renamed to avoid conflict if User.validate_proxies is different
        if v is None: # Allow None to signify no change to proxies
            return None # Or return {} if empty dict means no change and None isn't allowed by API
        return {
            proxy_type: ProxySettings.from_dict(
                proxy_type, v.get(proxy_type, {}))
            for proxy_type in v
        }

    @field_validator("status", mode="before")
    def validate_status_modify(cls, status, values): # Renamed
        if status is None: return None # No change
        on_hold_expire_duration = values.data.get("on_hold_expire_duration")
        # If on_hold_expire_duration is not in payload, we might need to fetch current user's value
        # For simplicity, assume if status is set to on_hold, on_hold_expire_duration must be provided or already valid.
        expire = values.data.get("expire")

        if status == UserStatusModify.on_hold:
            # This logic might be complex if dependent fields are not always in the payload.
            # We are modifying, so we might need the existing state of the user.
            # For now, assume if 'on_hold_expire_duration' is in payload and is 0/None, it's an error for 'on_hold'.
            if on_hold_expire_duration is not None and on_hold_expire_duration == 0 : # Explicitly setting duration to 0
                raise ValueError("User cannot be on hold without a valid on_hold_expire_duration.")
            # If 'expire' is in payload and non-zero:
            if expire is not None and expire != 0:
                raise ValueError("User cannot be on hold with a specific expiration date set.")
        return status


class UserResponse(User):
    # account_number is inherited from User
    status: UserStatus
    used_traffic: int
    lifetime_used_traffic: int = 0
    created_at: datetime
    links: List[str] = Field(default_factory=list)
    subscription_url: str = ""
    # proxies type inherited, ensure it's compatible
    excluded_inbounds: Dict[ProxyTypes, List[str]] = Field(default_factory=dict)

    admin: Optional[Admin] = None # Or a more specific AdminResponse model
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_links_response(self): # Renamed
        if not self.links: # Only generate if empty
            self.links = generate_v2ray_links(
                self.proxies, self.inbounds, extra_data=self.model_dump(), reverse=False,
            )
        return self

    @model_validator(mode="after")
    def validate_subscription_url_response(self): # Renamed
        if not self.subscription_url: # Only generate if empty
            salt = secrets.token_hex(8)
            url_prefix = (XRAY_SUBSCRIPTION_URL_PREFIX).replace('*', salt)
            # create_subscription_token should use account_number
            token = create_subscription_token(self.account_number)
            self.subscription_url = f"{url_prefix}/{XRAY_SUBSCRIPTION_PATH}/{token}"
        return self

    @field_validator("proxies", mode="before")
    def validate_proxies_response(cls, v, values, **kwargs): # Renamed
        if isinstance(v, list): # Assuming v could be a list of DB proxy objects
            # This transformation depends on the structure of these DB objects
            # Example: if each object `p` has `p.type` and `p.settings`
            v_dict = {}
            for p_obj in v: # Pseudo-code, adapt to actual object structure
                if hasattr(p_obj, 'type') and hasattr(p_obj, 'settings'):
                    v_dict[p_obj.type] = p_obj.settings
                # Else, handle error or skip
            v = v_dict
        # Call User.validate_proxies or its equivalent logic if needed for structure
        # For now, assuming `super().validate_proxies` or direct validation
        validated_proxies = {}
        for proxy_type_key, settings_val in v.items():
            try:
                # Assuming ProxyTypes enum can be created from string key
                proxy_type_enum = ProxyTypes(str(proxy_type_key))
                validated_proxies[proxy_type_enum] = ProxySettings.from_dict(proxy_type_enum, settings_val if settings_val else {})
            except ValueError:
                # Handle invalid proxy_type_key if necessary
                pass # Or log a warning
        return validated_proxies


    @field_validator("used_traffic", "lifetime_used_traffic", mode='before')
    def cast_traffic_to_int(cls, v): # Renamed
        if v is None: # Should traffic be nullable? If not, remove this check.
            return 0 # Default to 0 if None, or raise error
        if isinstance(v, float):
            return int(v)
        if isinstance(v, int):
            return v
        raise ValueError("Traffic value must be an integer or a float")


class SubscriptionUserResponse(UserResponse):
    # Exclude fields not relevant for subscription view
    admin: Optional[Admin] = Field(default=None, exclude=True)
    excluded_inbounds: Optional[Dict[ProxyTypes, List[str]]] = Field(None, exclude=True)
    note: Optional[str] = Field(None, exclude=True)
    inbounds: Optional[Dict[ProxyTypes, List[str]]] = Field(None, exclude=True)
    auto_delete_in_days: Optional[int] = Field(None, exclude=True)
    # Add other fields to exclude if necessary
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