import secrets
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, TYPE_CHECKING
from sqlalchemy.orm import Session
import logging

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    ValidationInfo,
    # EmailStr, # Not used here anymore
)

from app import xray
from app.models.admin import Admin # Assuming Admin model doesn't need username changes reflected here for User model
from app.models.proxy import ProxySettings, ProxyTypes
from app.utils.jwt import create_subscription_token # Check if this uses username
from config import XRAY_SUBSCRIPTION_PATH, XRAY_SUBSCRIPTION_URL_PREFIX
from app.db import crud

if TYPE_CHECKING:
    from app.subscription.share import generate_v2ray_links


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


class User(BaseModel):
    account_number: str = Field(..., description="Account number for the user (UUID)")
    proxies: Dict[ProxyTypes, ProxySettings] = Field(default_factory=dict)
    expire: Optional[int] = Field(None, nullable=True)
    # MODIFICATION START: Remove ge=0 and rely on the validator below
    data_limit: Optional[int] = Field(None, description="Data limit in bytes, None for unlimited")
    # MODIFICATION END
    data_limit_reset_strategy: UserDataLimitResetStrategy = (
        UserDataLimitResetStrategy.no_reset
    )
    note: Optional[str] = Field(None, nullable=True)
    sub_updated_at: Optional[datetime] = Field(None, nullable=True)
    sub_last_user_agent: Optional[str] = Field(None, nullable=True)
    online_at: Optional[datetime] = Field(None, nullable=True)
    on_hold_expire_duration: Optional[int] = Field(None, nullable=True)
    on_hold_timeout: Optional[Union[datetime, None]] = Field(None, nullable=True)
    auto_delete_in_days: Optional[int] = Field(None, nullable=True)
    next_plan: Optional[NextPlanModel] = Field(None, nullable=True)

    # REMOVE the old @field_validator('data_limit', mode='before') def cast_to_int
    # REPLACE with the new comprehensive validator:
    @field_validator('data_limit', mode='before')
    def validate_data_limit(cls, v):
        if v is None:
            return None  # Allow None
        try:
            # Attempt to cast to int, this will handle floats like 10.0 correctly
            val = int(v)
        except (ValueError, TypeError):
            # If casting fails (e.g., it's a string like "abc" or an incompatible type)
            raise ValueError("data_limit must be a number (e.g., 100, 100.0, or null)")

        if val < 0:
            raise ValueError("data_limit must be non-negative")
        return val

    # Keep other existing validators as they are, for example:
    @field_validator("proxies", mode="before")
    def validate_proxies(cls, v, values, **kwargs): # Ensure this signature matches your Pydantic version if it's older
        # ... (existing logic from your file)
        if v is None: return {}
        return {
            ProxyTypes(proxy_type_key): ProxySettings.from_dict(
                ProxyTypes(proxy_type_key), v.get(proxy_type_key, {})
            )
            for proxy_type_key in v
        }

    @field_validator("note")
    @classmethod
    def validate_note(cls, v):
        # ... (existing logic from your file)
        if v and len(v) > 500:
            raise ValueError("User's note can be a maximum of 500 character")
        return v

    @field_validator("on_hold_expire_duration", "on_hold_timeout", mode="before")
    def validate_timeout(cls, v, info): # Pydantic v2 uses info (ValidationInfo)
        # ... (existing logic from your file)
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
    proxies: Optional[Dict[ProxyTypes, ProxySettings]] = None

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
    active_node_id: Optional[int] = None

    admin: Optional[Admin] = None # Or AdminResponse model
    model_config = ConfigDict(from_attributes=True) # Enables ORM mode

    @model_validator(mode="after")
    def build_dynamic_fields(self, info: ValidationInfo) -> 'UserResponse':
        # Detect FastAPI's subsequent context-less validation call
        is_problematic_fastapi_call = (info.context is None and info.config == {})

        if is_problematic_fastapi_call:
            # If dynamic fields were already populated by a previous, context-aware call,
            # trust that and don't overwrite.
            if hasattr(self, 'links') and self.links and \
               hasattr(self, 'subscription_url') and self.subscription_url:
                return self
            else:
                logging.error(
                    "UserResponse.build_dynamic_fields: Problematic call AND dynamic fields "
                    "NOT populated. This is unexpected. Proceeding with default/error values."
                )

        # Attempt to get db and request from context
        db = info.context.get('db') if info.context else None

        # Initialize fields if they don't exist (e.g., first pass or problematic call recovery)
        if not hasattr(self, 'links') or not self.links:
            self.links = []
        if not hasattr(self, 'subscription_url') or not self.subscription_url:
            self.subscription_url = ""

        # If db is not available (either original problematic call or a genuine miss),
        # set error/default messages and return.
        if not db:
            self.links = self.links or ["Configuration links require server context."]
            self.subscription_url = self.subscription_url or "Subscription URL requires server context."
            return self

        # --- Normal Link and Subscription URL Generation Logic ---
        user_account_number = self.account_number # Assuming self has account_number

        # Generate subscription URL
        if not self.subscription_url: # Only if not already set (e.g., by problematic call check)
            try:
                salt = secrets.token_hex(8)
                url_prefix = (XRAY_SUBSCRIPTION_URL_PREFIX).replace('*', salt)
                token = create_subscription_token(user_account_number)
                self.subscription_url = f"{url_prefix}/{XRAY_SUBSCRIPTION_PATH}/{token}"
            except Exception as e:
                logging.error(f"Error generating subscription URL for user {user_account_number}: {e}", exc_info=True)
                self.subscription_url = "ErrorGeneratingSubURL"

        # Generate V2Ray links if node is active and proxies exist
        if self.active_node_id and self.proxies:
            try:
                from app.subscription.share import generate_v2ray_links  # Local import
                node_services = crud.get_services_for_node(db, self.active_node_id)
                active_node_specific_inbounds = {}

                for proxy_type_enum, user_proxy_settings in self.proxies.items():
                    active_node_specific_inbounds[proxy_type_enum] = []
                    for service_config in node_services:
                        if (service_config.enabled and
                            hasattr(service_config, 'protocol_type') and # Check attribute existence
                            service_config.protocol_type.value.lower() == proxy_type_enum.value.lower() and
                            hasattr(service_config, 'xray_inbound_tag') and # Check attribute existence
                            service_config.xray_inbound_tag):
                            active_node_specific_inbounds[proxy_type_enum].append(service_config.xray_inbound_tag)

                if not active_node_specific_inbounds or not any(active_node_specific_inbounds.values()):
                    self.links = [f"No server configurations for node {self.active_node_id}: No enabled services with required inbound tags match your protocols."]
                else:
                    self.links = generate_v2ray_links(
                        proxies=self.proxies,
                        inbounds=active_node_specific_inbounds,
                        extra_data=self.model_dump(exclude_none=True), # Use exclude_none
                        reverse=False,
                        active_node_id=self.active_node_id
                    )
                    if not self.links:
                         self.links = [f"No configurations generated for node {self.active_node_id}. Check services/protocols."]
            except Exception as e:
                logging.error(f"Error generating links for user {user_account_number} on node {self.active_node_id}: {e}", exc_info=True)
                self.links = [f"Error generating configurations for node {self.active_node_id}."]
        else: # No active node or no proxies
            if not self.active_node_id:
                self.links = ["Please activate a server node first to see configuration links."]
            elif not self.proxies:
                self.links = [f"No proxy protocols configured for your account to use with node {self.active_node_id or ''}."]
            # If self.links was already set (e.g. by problematic call check), don't overwrite unless it's still empty
            elif not self.links:
                self.links = ["Configuration links are unavailable."]

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
        if v is None:
            return 0
        try:
            if isinstance(v, (float, int)):
                result = int(v)
                return result
            if isinstance(v, str):
                result = int(float(v))
                return result
            return 0
        except (ValueError, TypeError) as e:
            return 0


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