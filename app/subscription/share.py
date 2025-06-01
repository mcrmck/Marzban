import base64
import logging
import random
import secrets
from collections import defaultdict
from datetime import datetime as dt
from datetime import timedelta
from typing import TYPE_CHECKING, List, Literal, Union, Optional, Dict, Any # Added Any

from jdatetime import date as jd # type: ignore

from app import xray, logger # Added logger
from app.utils.system import get_public_ip, get_public_ipv6, readable_size
from app.models.proxy import ProxyTypes, ShadowsocksSettings # Added ShadowsocksSettings

# Import subscription configuration classes correctly
from .v2ray import V2rayShareLink, V2rayJsonConfig
from .singbox import SingBoxConfiguration
from .outline import OutlineConfiguration
from .clash import ClashConfiguration, ClashMetaConfiguration


if TYPE_CHECKING:
    from app.models.user import UserResponse # This is a Pydantic model
    from app.db.models import ProxyHost as DBProxyHost # For type hint if directly used

from config import (
    ACTIVE_STATUS_TEXT,
    DISABLED_STATUS_TEXT,
    EXPIRED_STATUS_TEXT,
    LIMITED_STATUS_TEXT,
    ONHOLD_STATUS_TEXT,
)

SERVER_IP = get_public_ip()
SERVER_IPV6 = get_public_ipv6()

STATUS_EMOJIS = {
    "active": "✅",
    "expired": "⌛️",
    "limited": "🪫",
    "disabled": "❌",
    "on_hold": "🔌",
}

STATUS_TEXTS = {
    "active": ACTIVE_STATUS_TEXT,
    "expired": EXPIRED_STATUS_TEXT,
    "limited": LIMITED_STATUS_TEXT,
    "disabled": DISABLED_STATUS_TEXT,
    "on_hold": ONHOLD_STATUS_TEXT,
}


# Helper functions for specific formats now accept active_node_id
def generate_v2ray_links(proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]) -> list:
    format_variables = setup_format_variables(extra_data)
    conf = V2rayShareLink()
    # Assuming V2rayShareLink.add can handle settings being Pydantic models (it uses .model_dump())
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id)


def generate_clash_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int], is_meta: bool = False
) -> str:
    if is_meta:
        conf = ClashMetaConfiguration()
    else:
        conf = ClashConfiguration()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id)


def generate_singbox_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]
) -> str:
    conf = SingBoxConfiguration()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id)


def generate_outline_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]
) -> str:
    conf = OutlineConfiguration()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id)


def generate_v2ray_json_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]
) -> str:
    conf = V2rayJsonConfig()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id)


def generate_subscription(
        user: "UserResponse", # This is Pydantic UserResponse
        config_format: Literal["v2ray", "clash-meta", "clash", "sing-box", "outline", "v2ray-json"],
        as_base64: bool,
        reverse: bool,
        active_node_id_override: Optional[int] = None # New parameter
) -> str:
    # user.selected_nodes logic removed.
    # user.proxies are the Pydantic models of proxy settings (e.g. VLESSSettings)
    # user.inbounds is Dict[ProxyTypes, List[str (tag)]]

    kwargs = {
        "proxies": user.proxies, # Pass the full user.proxies dict
        "inbounds": user.inbounds,
        "extra_data": user.model_dump(), # Use model_dump() for Pydantic models
        "reverse": reverse,
        "active_node_id": active_node_id_override # Pass the active node ID
    }

    config_str = "" # Initialize to empty string

    if config_format == "v2ray":
        links = generate_v2ray_links(**kwargs) # type: ignore
        config_str = "\n".join(links)
    elif config_format == "clash-meta":
        config_str = generate_clash_subscription(**kwargs, is_meta=True) # type: ignore
    elif config_format == "clash":
        config_str = generate_clash_subscription(**kwargs) # type: ignore
    elif config_format == "sing-box":
        config_str = generate_singbox_subscription(**kwargs) # type: ignore
    elif config_format == "outline":
        config_str = generate_outline_subscription(**kwargs) # type: ignore
    elif config_format == "v2ray-json":
        config_str = generate_v2ray_json_subscription(**kwargs) # type: ignore
    else:
        raise ValueError(f'Unsupported format "{config_format}"')

    if as_base64:
        config_str = base64.b64encode(config_str.encode()).decode()

    return config_str


def format_time_left(seconds_left: int) -> str:
    if not seconds_left or seconds_left <= 0: # Also check for None or 0
        return "∞"
    # ... (rest of the function remains the same)
    minutes, seconds = divmod(seconds_left, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    months, days = divmod(days, 30) # Approximation

    result = []
    if months: result.append(f"{months}m")
    if days: result.append(f"{days}d")
    if hours and (days < 7): result.append(f"{hours}h") # Show hours if less than a week of days
    if minutes and not (months or days): result.append(f"{minutes}m") # Show minutes if no months/days
    if not result and seconds_left > 0 : result.append(f"{int(seconds_left)}s") # Show seconds if nothing else and >0

    return " ".join(result) if result else "0s" # Handle case where result is empty (e.g. very short duration)


def setup_format_variables(extra_data: dict) -> dict: # extra_data is from user.model_dump()
    from app.models.user import UserStatus # Local import to avoid circular dependency issues at module level

    user_status_val = extra_data.get("status") # This will be the enum member's value, e.g., "active"
    # Convert string status to UserStatus enum member if necessary for comparison, though direct string compare is fine too.
    # user_status_enum = UserStatus(user_status_val) if user_status_val else None

    expire_timestamp = extra_data.get("expire")
    on_hold_expire_duration = extra_data.get("on_hold_expire_duration")
    # ... (rest of setup_format_variables remains the same) ...
    now = dt.utcnow()
    now_ts = now.timestamp()

    days_left_str = "∞"
    time_left_str = "∞"
    expire_date_str = "∞"
    jalali_expire_date_str = "∞"

    if user_status_val != UserStatus.on_hold.value: # Compare with enum's value
        if expire_timestamp is not None and expire_timestamp >= 0:
            seconds_left = expire_timestamp - int(now_ts)
            expire_datetime = dt.fromtimestamp(expire_timestamp)
            expire_date_str = expire_datetime.strftime("%Y-%m-%d")
            try:
                jalali_expire_date_str = jd.fromgregorian(
                    date=expire_datetime.date() # Pass date object
                ).strftime("%Y-%m-%d")
            except Exception: # Catch potential errors from jdatetime
                jalali_expire_date_str = expire_date_str # Fallback

            if seconds_left > 0 :
                days_left_val = (expire_datetime - now).days
                days_left_str = str(days_left_val +1) if days_left_val >=0 else "0" # ensure non-negative days count
                time_left_str = format_time_left(seconds_left)
            else:
                days_left_str = "0"
                time_left_str = "0s"
    else: # UserStatus.on_hold
        if on_hold_expire_duration is not None and on_hold_expire_duration > 0:
            days_left_str = str(timedelta(seconds=on_hold_expire_duration).days)
            time_left_str = format_time_left(on_hold_expire_duration)
            expire_date_str = "-" # No specific expiry date when on hold
            jalali_expire_date_str = "-"

    data_limit_str = "∞"
    data_left_str = "∞"
    data_limit_val = extra_data.get("data_limit")
    if data_limit_val is not None and data_limit_val > 0:  # Check if data_limit is set and positive
        data_limit_str = readable_size(data_limit_val)
        data_left_val = data_limit_val - extra_data.get("used_traffic", 0)
        data_left_str = readable_size(max(0, data_left_val))  # Ensure non-negative
    elif data_limit_val == 0:  # Explicitly 0 means limited after any usage
        data_limit_str = readable_size(0)
        data_left_str = readable_size(0)

    status_emoji = STATUS_EMOJIS.get(user_status_val, "")
    status_text = STATUS_TEXTS.get(user_status_val, "")
    account_number = extra_data.get("account_number", "{ACCOUNT_NUMBER}")  # Use account_number from user data

    format_variables = defaultdict(
        lambda: "", # Default to empty string instead of "<missing>"
        {
            "SERVER_IP": SERVER_IP or "",
            "SERVER_IPV6": SERVER_IPV6 or "",
            "USERNAME": account_number, # Use account_number as USERNAME placeholder
            "ACCOUNT_NUMBER": account_number,
            "DATA_USAGE": readable_size(extra_data.get("used_traffic", 0)),
            "DATA_LIMIT": data_limit_str,
            "DATA_LEFT": data_left_str,
            "DAYS_LEFT": days_left_str,
            "EXPIRE_DATE": expire_date_str,
            "JALALI_EXPIRE_DATE": jalali_expire_date_str,
            "TIME_LEFT": time_left_str,
            "STATUS_EMOJI": status_emoji,
            "STATUS_TEXT": status_text,
        },
    )
    return format_variables


def process_inbounds_and_tags(
        user_inbounds: Dict[ProxyTypes, List[str]], # from user.inbounds
        user_proxies: Dict[ProxyTypes, Any],       # from user.proxies (Pydantic models)
        format_variables: dict,
        conf: Union[
            V2rayShareLink, V2rayJsonConfig, SingBoxConfiguration,
            ClashConfiguration, OutlineConfiguration
        ],
        reverse: bool,
        active_node_id: Optional[int] # New parameter
) -> Union[List, str]:


    processed_conf_tags = [] # To keep track of added proxy remarks for some client types

    all_user_tags_with_protocol = []
    for protocol_enum, tags in user_inbounds.items():
        for tag_name in tags:
            all_user_tags_with_protocol.append({'protocol': protocol_enum, 'tag': tag_name})


    global_inbound_order_map = {tag: index for index, tag in enumerate(xray.config.inbounds_by_tag.keys())}

    sorted_user_tags_with_protocol = sorted(
        all_user_tags_with_protocol,
        key=lambda x: global_inbound_order_map.get(x['tag'], float('inf'))
    )

    # MODIFICATION START: Logic to handle active_node_id and nodeless hosts
    for item in sorted_user_tags_with_protocol:
        protocol_enum: ProxyTypes = item['protocol']
        tag_name: str = item['tag']


        proxy_specific_settings = user_proxies.get(protocol_enum)
        if not proxy_specific_settings:
            continue

        global_inbound_config = xray.config.inbounds_by_tag.get(tag_name)
        if not global_inbound_config:
            continue


        current_format_variables = format_variables.copy()
        current_format_variables.update({
            "PROTOCOL": global_inbound_config.get("protocol","").upper(),
            "TRANSPORT": global_inbound_config.get("network","")
        })

        all_host_dicts_for_tag = xray.hosts.get(tag_name, [])

        selected_host_dicts = [] # Initialize list for hosts that will be added to subscription

        if active_node_id is not None:
            logger.debug(f"User {current_format_variables.get('ACCOUNT_NUMBER')} has active_node_id {active_node_id}. "
                         f"Filtering for ProxyHosts matching node_id {active_node_id} for tag '{tag_name}'.")
            for host_dict_candidate in all_host_dicts_for_tag:
                if host_dict_candidate.get('node_id') == active_node_id and \
                   not host_dict_candidate.get('is_disabled', False):
                    selected_host_dicts.append(host_dict_candidate)

            if not selected_host_dicts:
                logger.warning(f"User {current_format_variables.get('ACCOUNT_NUMBER')} has active_node_id {active_node_id}, "
                               f"but no enabled ProxyHosts found for tag '{tag_name}' on this node. Skipping this tag for this node.")
                continue # Skip to the next tag in sorted_user_tags_with_protocol

        else: # active_node_id is None
            logger.info(f"User {current_format_variables.get('ACCOUNT_NUMBER')} has no active_node_id. "
                        f"Looking for enabled ProxyHosts with node_id=None (master instance) for tag '{tag_name}'.")
            for host_dict_candidate in all_host_dicts_for_tag:
                if host_dict_candidate.get('node_id') is None and \
                   not host_dict_candidate.get('is_disabled', False):
                    selected_host_dicts.append(host_dict_candidate)

            if not selected_host_dicts:
                logger.info(f"User {current_format_variables.get('ACCOUNT_NUMBER')} has no active_node_id, "
                            f"and no enabled ProxyHosts with node_id=None found for tag '{tag_name}'. Skipping this tag.")
                continue # Skip to the next tag in sorted_user_tags_with_protocol



        for host_config_dict in selected_host_dicts: # Iterate only selected hosts
            combined_inbound_details = global_inbound_config.copy()

            host_addresses = host_config_dict.get("address", [])
            if not host_addresses or not isinstance(host_addresses, list) or not host_addresses[0]:
                logger.warning(f"Skipping host {host_config_dict.get('remark', 'Unknown')} for tag {tag_name} due to missing or invalid address.")
                continue
            processed_address = random.choice(host_addresses)
            if '*' in processed_address:
                 processed_address = processed_address.replace("*", secrets.token_hex(8))

            sni_list_from_host = host_config_dict.get("sni")
            final_sni_list = sni_list_from_host if sni_list_from_host is not None else global_inbound_config.get("sni")
            processed_sni = ""
            if final_sni_list and isinstance(final_sni_list, list):
                salt = secrets.token_hex(8)
                processed_sni = random.choice(final_sni_list).replace("*", salt)

            req_host_list_from_host = host_config_dict.get("host")
            final_req_host_list = req_host_list_from_host if req_host_list_from_host is not None else global_inbound_config.get("host")
            processed_req_host = ""
            if final_req_host_list and isinstance(final_req_host_list, list):
                salt = secrets.token_hex(8)
                processed_req_host = random.choice(final_req_host_list).replace("*", salt)

            path_from_host = host_config_dict.get("path")
            processed_path_template = path_from_host if path_from_host is not None else global_inbound_config.get("path", "")
            processed_path = processed_path_template.format_map(current_format_variables)

            if host_config_dict.get("use_sni_as_host", False) and processed_sni:
                processed_req_host = processed_sni

            combined_inbound_details.update({
                "port": host_config_dict.get("port") or global_inbound_config.get("port"),
                "sni": processed_sni,
                "host": processed_req_host,
                "path": processed_path,
                "tls": host_config_dict.get("security", global_inbound_config.get("tls")),
                "alpn": host_config_dict.get("alpn") if host_config_dict.get("alpn") is not None else global_inbound_config.get("alpn"),
                "fp": host_config_dict.get("fingerprint") or global_inbound_config.get("fp", ""),
                "pbk": host_config_dict.get("pbk") or global_inbound_config.get("pbk", ""),
                "sid": host_config_dict.get("sid") or global_inbound_config.get("sid", ""),
                "spx": host_config_dict.get("spx") or global_inbound_config.get("spx", ""),
                "allowinsecure": host_config_dict.get("allowinsecure", False) or global_inbound_config.get("allowinsecure", False),
                "mux_enable": host_config_dict.get("mux_enable", False),
                "fragment_setting": host_config_dict.get("fragment_setting"),
                "noise_setting": host_config_dict.get("noise_setting"),
                "random_user_agent": host_config_dict.get("random_user_agent", False),
                "header_type": host_config_dict.get("header_type") or global_inbound_config.get("header_type", "none"),
                "scMaxEachPostBytes": host_config_dict.get('scMaxEachPostBytes', global_inbound_config.get('scMaxEachPostBytes')),
                "scMaxConcurrentPosts": host_config_dict.get('scMaxConcurrentPosts', global_inbound_config.get('scMaxConcurrentPosts')),
                "scMinPostsIntervalMs": host_config_dict.get('scMinPostsIntervalMs', global_inbound_config.get('scMinPostsIntervalMs')),
                "xPaddingBytes": host_config_dict.get('xPaddingBytes', global_inbound_config.get('xPaddingBytes')),
                "noGRPCHeader": host_config_dict.get('noGRPCHeader', global_inbound_config.get('noGRPCHeader', False)),
                "heartbeatPeriod": host_config_dict.get('heartbeatPeriod', global_inbound_config.get('heartbeatPeriod', 0)),
                "keepAlivePeriod": host_config_dict.get('keepAlivePeriod', global_inbound_config.get('keepAlivePeriod', 0)),
                "xmux": host_config_dict.get('xmux', global_inbound_config.get('xmux', {})),
                "mode": host_config_dict.get('mode', global_inbound_config.get('mode', "auto")),
                "multiMode": host_config_dict.get('multiMode', global_inbound_config.get('multiMode', False)),
            })

            user_protocol_settings_pydantic = proxy_specific_settings

            try:
                # Ensure settings are properly converted to dict with string values
                settings_dict = user_protocol_settings_pydantic.model_dump(exclude_none=True)
                if isinstance(user_protocol_settings_pydantic, ShadowsocksSettings):
                    # Handle method value - it could be an enum or already a string
                    if 'method' in settings_dict:
                        method_value = settings_dict['method']
                        if hasattr(method_value, 'value'):  # If it's an enum
                            settings_dict['method'] = method_value.value
                        # If it's already a string, leave it as is

                conf.add( # type: ignore
                    remark=host_config_dict.get("remark", "N/A").format_map(current_format_variables),
                    address=processed_address.format_map(current_format_variables),
                    inbound=combined_inbound_details,
                    settings=settings_dict
                )
            except Exception as e:
                logger.error(f"Error adding config for remark {host_config_dict.get('remark', 'N/A')}: {e}", exc_info=True)

    return conf.render(reverse=reverse) # type: ignore


def encode_title(text: str) -> str:
    return f"base64:{base64.b64encode(text.encode()).decode()}"