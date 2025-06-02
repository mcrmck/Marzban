import base64
import json # For logging dicts
import logging
import random
import secrets
from collections import defaultdict
from datetime import datetime as dt
from datetime import timedelta
from typing import TYPE_CHECKING, List, Literal, Union, Optional, Dict, Any

from jdatetime import date as jd # type: ignore

# Ensure xray, logger are available. If xray.config or xray.hosts are not yet populated
# when this module loads, their usage in functions must be robust.
from app import xray, logger # Main app logger
from app.utils.system import get_public_ip, get_public_ipv6, readable_size
from app.models.proxy import ProxyTypes, ShadowsocksSettings
from app.db import crud as db_crud # For fetching node details
from app.db import SessionLocal # To get a DB session if needed

# Import subscription configuration classes correctly
from .v2ray import V2rayShareLink, V2rayJsonConfig
from .singbox import SingBoxConfiguration
from .outline import OutlineConfiguration
from .clash import ClashConfiguration, ClashMetaConfiguration

if TYPE_CHECKING:
    from app.models.user import UserResponse
    # from app.db.models import ProxyHost as DBProxyHost # No longer used

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
    "active": "✅", "expired": "⌛️", "limited": "🪫",
    "disabled": "❌", "on_hold": "🔌",
}
STATUS_TEXTS = {
    "active": ACTIVE_STATUS_TEXT, "expired": EXPIRED_STATUS_TEXT,
    "limited": LIMITED_STATUS_TEXT, "disabled": DISABLED_STATUS_TEXT,
    "on_hold": ONHOLD_STATUS_TEXT,
}

# --- Helper functions (generate_v2ray_links, etc.) remain the same ---
# They all call process_inbounds_and_tags, which is what we're modifying.

def generate_v2ray_links(proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]) -> list:
    format_variables = setup_format_variables(extra_data)
    conf = V2rayShareLink()
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id) # type: ignore

# ... (generate_clash_subscription, generate_singbox_subscription, etc. are similar)
def generate_clash_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int], is_meta: bool = False
) -> str:
    if is_meta:
        conf = ClashMetaConfiguration()
    else:
        conf = ClashConfiguration()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id) # type: ignore


def generate_singbox_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]
) -> str:
    conf = SingBoxConfiguration()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id) # type: ignore


def generate_outline_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]
) -> str:
    conf = OutlineConfiguration()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id) # type: ignore


def generate_v2ray_json_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, active_node_id: Optional[int]
) -> str:
    conf = V2rayJsonConfig()
    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(inbounds, proxies, format_variables, conf, reverse, active_node_id) # type: ignore


# --- generate_subscription remains the same ---
def generate_subscription(
        user: "UserResponse",
        config_format: Literal["v2ray", "clash-meta", "clash", "sing-box", "outline", "v2ray-json"],
        as_base64: bool,
        reverse: bool,
        active_node_id_override: Optional[int] = None
) -> str:
    # Use the node ID from the override if provided, otherwise from the user object
    # This assumes user.active_node_id is correctly populated by UserResponse.build_dynamic_fields
    current_active_node_id = active_node_id_override if active_node_id_override is not None else user.active_node_id

    kwargs = {
        "proxies": user.proxies,
        "inbounds": user.inbounds, # This is Dict[ProxyTypes, List[str_tags]]
        "extra_data": user.model_dump(exclude_none=True), # Get full user data as dict
        "reverse": reverse,
        "active_node_id": current_active_node_id
    }
    # ... (rest of the function is the same) ...
    config_str = ""
    if config_format == "v2ray":
        links = generate_v2ray_links(**kwargs)
        config_str = "\n".join(links)
    elif config_format == "clash-meta":
        config_str = generate_clash_subscription(**kwargs, is_meta=True)
    elif config_format == "clash":
        config_str = generate_clash_subscription(**kwargs)
    elif config_format == "sing-box":
        config_str = generate_singbox_subscription(**kwargs)
    elif config_format == "outline":
        config_str = generate_outline_subscription(**kwargs)
    elif config_format == "v2ray-json":
        config_str = generate_v2ray_json_subscription(**kwargs)
    else:
        raise ValueError(f'Unsupported format "{config_format}"')

    if as_base64:
        config_str = base64.b64encode(config_str.encode()).decode()
    return config_str

# --- format_time_left and setup_format_variables remain the same ---
def format_time_left(seconds_left: int) -> str:
    if not seconds_left or seconds_left <= 0:
        return "∞"
    minutes, seconds = divmod(seconds_left, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    months, days = divmod(days, 30)
    result = []
    if months: result.append(f"{months}m")
    if days: result.append(f"{days}d")
    if hours and (days < 7): result.append(f"{hours}h")
    if minutes and not (months or days): result.append(f"{minutes}m")
    if not result and seconds_left > 0 : result.append(f"{int(seconds_left)}s")
    return " ".join(result) if result else "0s"

def setup_format_variables(extra_data: dict) -> dict:
    from app.models.user import UserStatus
    user_status_val = extra_data.get("status")
    expire_timestamp = extra_data.get("expire")
    on_hold_expire_duration = extra_data.get("on_hold_expire_duration")
    now = dt.utcnow()
    now_ts = now.timestamp()
    days_left_str = "∞"; time_left_str = "∞"; expire_date_str = "∞"; jalali_expire_date_str = "∞"

    if user_status_val != UserStatus.on_hold.value:
        if expire_timestamp is not None and expire_timestamp >= 0:
            seconds_left = expire_timestamp - int(now_ts)
            expire_datetime = dt.fromtimestamp(expire_timestamp)
            expire_date_str = expire_datetime.strftime("%Y-%m-%d")
            try:
                jalali_expire_date_str = jd.fromgregorian(date=expire_datetime.date()).strftime("%Y-%m-%d")
            except Exception: jalali_expire_date_str = expire_date_str
            if seconds_left > 0 :
                days_left_val = (expire_datetime - now).days
                days_left_str = str(days_left_val + 1) if days_left_val >=0 else "0"
                time_left_str = format_time_left(seconds_left)
            else: days_left_str = "0"; time_left_str = "0s"
    else:
        if on_hold_expire_duration is not None and on_hold_expire_duration > 0:
            days_left_str = str(timedelta(seconds=on_hold_expire_duration).days)
            time_left_str = format_time_left(on_hold_expire_duration)
            expire_date_str = "-"; jalali_expire_date_str = "-"
    data_limit_str = "∞"; data_left_str = "∞"
    data_limit_val = extra_data.get("data_limit")
    if data_limit_val is not None and data_limit_val > 0:
        data_limit_str = readable_size(data_limit_val)
        data_left_val = data_limit_val - extra_data.get("used_traffic", 0)
        data_left_str = readable_size(max(0, data_left_val))
    elif data_limit_val == 0:
        data_limit_str = readable_size(0); data_left_str = readable_size(0)
    status_emoji = STATUS_EMOJIS.get(user_status_val, ""); status_text = STATUS_TEXTS.get(user_status_val, "")
    account_number = extra_data.get("account_number", "{ACCOUNT_NUMBER}")
    return defaultdict(lambda: "", {
        "SERVER_IP": SERVER_IP or "", "SERVER_IPV6": SERVER_IPV6 or "",
        "USERNAME": account_number, "ACCOUNT_NUMBER": account_number,
        "DATA_USAGE": readable_size(extra_data.get("used_traffic", 0)),
        "DATA_LIMIT": data_limit_str, "DATA_LEFT": data_left_str,
        "DAYS_LEFT": days_left_str, "EXPIRE_DATE": expire_date_str,
        "JALALI_EXPIRE_DATE": jalali_expire_date_str, "TIME_LEFT": time_left_str,
        "STATUS_EMOJI": status_emoji, "STATUS_TEXT": status_text,
    })


def process_inbounds_and_tags(
        user_inbounds: Dict[ProxyTypes, List[str]], # e.g., {ProxyTypes.VLESS: ['marzban_service_1']}
        user_proxies: Dict[ProxyTypes, Any],       # e.g., {ProxyTypes.VLESS: VLESSSettingsModelInstance}
        format_variables: dict,
        conf: Union[
            V2rayShareLink, V2rayJsonConfig, SingBoxConfiguration,
            ClashConfiguration, OutlineConfiguration
        ],
        reverse: bool,
        active_node_id: Optional[int]
) -> Union[List, str]:

    # Use the main app logger or a specific one for this module
    _logger = logging.getLogger(f"{__name__}.process_inbounds_and_tags") # More specific
    _logger.info(f"Processing inbounds for user {format_variables.get('ACCOUNT_NUMBER', 'N/A')}, active_node_id: {active_node_id}")
    _logger.debug(f"Received user_inbounds: {user_inbounds}")
    _logger.debug(f"Received user_proxies keys: {[k.value for k in user_proxies.keys()] if user_proxies else 'None'}")

    if not xray.config or not xray.config.inbounds_by_tag:
        _logger.error("Global xray.config or xray.config.inbounds_by_tag is not loaded/available. Cannot generate links.")
        return conf.render(reverse=reverse) # type: ignore

    _logger.debug(f"Available global XRay inbound tags (xray.config.inbounds_by_tag.keys()): {list(xray.config.inbounds_by_tag.keys())}")

    all_user_tags_with_protocol = []
    if not user_inbounds:
        _logger.warning("User has no specific inbounds (user_inbounds map is empty). No links will be generated.")
        return conf.render(reverse=reverse) # type: ignore

    for protocol_enum, tags_for_protocol in user_inbounds.items():
        for tag_name in tags_for_protocol:
            all_user_tags_with_protocol.append({'protocol': protocol_enum, 'tag': tag_name})

    if not all_user_tags_with_protocol:
        _logger.warning("No tags to process after parsing user_inbounds. No links generated.")
        return conf.render(reverse=reverse) # type: ignore

    _logger.debug(f"Total tags to process for user: {all_user_tags_with_protocol}")

    # Sorting based on global XRay config order (if still desired)
    global_inbound_order_map = {tag: index for index, tag in enumerate(xray.config.inbounds_by_tag.keys())}
    sorted_user_tags_with_protocol = sorted(
        all_user_tags_with_protocol,
        key=lambda x: global_inbound_order_map.get(x['tag'], float('inf')) # Tags not in global config go last
    )
    _logger.debug(f"Sorted tags for processing: {sorted_user_tags_with_protocol}")


    node_public_address = None
    node_name_for_remark = "Server" # Default remark node name

    if active_node_id is not None:
        # Fetch active node's details (especially its public FQDN or IP)
        # This requires a DB session.
        db_for_node_fetch = SessionLocal()
        try:
            active_node_orm = db_crud.get_node_by_id(db_for_node_fetch, active_node_id)
            if active_node_orm:
                # Assuming Node model has an 'address' field for its public FQDN/IP
                # And a 'name' field for remarks.
                node_public_address = active_node_orm.address
                node_name_for_remark = active_node_orm.name
                _logger.info(f"  Fetched active node {active_node_id}: Name='{node_name_for_remark}', PublicAddress='{node_public_address}'")
                if not node_public_address:
                    _logger.warning(f"  Active node {active_node_id} ('{node_name_for_remark}') has no public address configured. Link generation may fail or use fallbacks.")
            else:
                _logger.error(f"  Active node with ID {active_node_id} not found in database. Cannot determine public address for links.")
                return conf.render(reverse=reverse) # type: ignore
        finally:
            db_for_node_fetch.close()
    else:
        _logger.info("  No active_node_id provided; link generation will rely on global SERVER_IP or addresses within XRay config if public.")
        # If no active_node_id, we might use a globally defined SERVER_IP or assume service listen address is public.
        # This path is less common if users always activate specific nodes.
        node_public_address = SERVER_IP # Fallback, or handle as error if specific node address is always expected


    for item_idx, item_data in enumerate(sorted_user_tags_with_protocol):
        protocol_enum: ProxyTypes = item_data['protocol']
        service_tag_name: str = item_data['tag'] # e.g., 'marzban_service_1'

        _logger.info(f"  Processing user's service tag {item_idx + 1}/{len(sorted_user_tags_with_protocol)}: Protocol='{protocol_enum.value}', Tag='{service_tag_name}' for NodeID={active_node_id}")

        user_protocol_settings = user_proxies.get(protocol_enum)
        if not user_protocol_settings:
            _logger.warning(f"    User {format_variables.get('ACCOUNT_NUMBER')} missing proxy settings for protocol {protocol_enum.value}. Skipping tag '{service_tag_name}'.")
            continue

        # Get the full XRay inbound configuration for this specific tag from the panel's loaded XRay config
        # This 'actual_xray_inbound_config' is the source of truth for ports, paths, SNI from XRay's perspective.
        actual_xray_inbound_config = xray.config.inbounds_by_tag.get(service_tag_name)
        if not actual_xray_inbound_config:
            _logger.warning(f"    Service tag '{service_tag_name}' (for user protocol {protocol_enum.value}) not found in the panel's loaded XRay configuration (xray.config.inbounds_by_tag). Skipping.")
            continue
        _logger.debug(f"    Found XRay inbound config for tag '{service_tag_name}': Port={actual_xray_inbound_config.get('port')}, Listen='{actual_xray_inbound_config.get('listen')}'")


        # Determine the final public address for the link
        final_link_address = node_public_address # Default to the active node's address
        if not final_link_address:
            # If node address wasn't found, try fallback to XRay listen address ONLY if it's not a bind-all/localhost
            xray_listen_addr = actual_xray_inbound_config.get("listen", "0.0.0.0")
            if xray_listen_addr and xray_listen_addr not in ["0.0.0.0", "127.0.0.1", "::"]:
                final_link_address = xray_listen_addr
                _logger.info(f"    Using XRay listen address '{xray_listen_addr}' as public address for tag '{service_tag_name}' (node public address was not available).")
            else:
                _logger.error(f"    Cannot determine a public address for tag '{service_tag_name}' (NodeID: {active_node_id}, NodeAddr: {node_public_address}, XRayListen: {xray_listen_addr}). Skipping link generation for this tag.")
                continue

        final_link_port = actual_xray_inbound_config.get("port") # Port should come from XRay config

        # Prepare `link_specific_details` from `actual_xray_inbound_config`
        link_specific_details = actual_xray_inbound_config.copy() # Includes port, protocol, settings, streamSettings
        stream_settings = link_specific_details.get("streamSettings", {})

        _logger.debug(f"    Actual XRay inbound config for tag '{service_tag_name}':")
        _logger.debug(f"      Full config: {json.dumps(actual_xray_inbound_config, default=str, indent=2)}")
        _logger.debug(f"      Stream settings: {json.dumps(stream_settings, default=str, indent=2)}")

        # Extract and format SNI, Path, Host header for the link generation classes
        link_specific_details['sni'] = stream_settings.get("tlsSettings", {}).get("serverName") or \
                                       stream_settings.get("realitySettings", {}).get("serverName", "")
        if '*' in link_specific_details['sni']:
            link_specific_details['sni'] = link_specific_details['sni'].replace("*", secrets.token_hex(8))

        link_specific_details['host'] = stream_settings.get("wsSettings", {}).get("headers", {}).get("Host") or \
                                        stream_settings.get("httpSettings", {}).get("headers", {}).get("Host", "") # For HTTP/2 upg.

        # Extract network type from stream settings
        network_type = stream_settings.get("network", "tcp")
        link_specific_details['network'] = network_type
        _logger.debug(f"      Network type: {network_type}")

        # Set header_type based on network type and stream settings
        if network_type == "ws":
            link_specific_details['header_type'] = "none"
        elif network_type == "tcp":
            link_specific_details['header_type'] = stream_settings.get("tcpSettings", {}).get("header", {}).get("type", "none")
        elif network_type == "grpc":
            link_specific_details['header_type'] = "grpc"
        else:
            link_specific_details['header_type'] = "none"
        _logger.debug(f"      Header type: {link_specific_details['header_type']}")

        # Add TLS settings
        link_specific_details['tls'] = stream_settings.get("security", "") # 'tls', 'reality', or empty
        link_specific_details['fp'] = stream_settings.get("tlsSettings", {}).get("fingerprint") or \
                                      stream_settings.get("realitySettings", {}).get("fingerprint", "")
        link_specific_details['alpn'] = stream_settings.get("tlsSettings", {}).get("alpn", []) # Default to empty list if not present

        path_val = ""
        if network_type == "ws" and stream_settings.get("wsSettings"):
            path_val = stream_settings["wsSettings"].get("path", "")
        elif network_type == "grpc" and stream_settings.get("grpcSettings"):
            path_val = stream_settings["grpcSettings"].get("serviceName", "")
        # Apply formatting to path if it uses variables (less common for direct XRay config values)
        link_specific_details['path'] = path_val.format_map(format_variables) if path_val else ""
        _logger.debug(f"      Path: {link_specific_details['path']}")

        _logger.debug(f"      Final link_specific_details: {json.dumps(link_specific_details, default=str, indent=2)}")

        remark_str = f"{node_name_for_remark} - {protocol_enum.value.upper()}"
        if format_variables.get("ACCOUNT_NUMBER"): # Add user identifier to remark
            remark_str = f"{format_variables['ACCOUNT_NUMBER']}@{node_name_for_remark} - {protocol_enum.value.upper()}"
        remark_str = remark_str.format_map(format_variables) # Apply any other remark formatting


        user_protocol_settings_dict = user_protocol_settings.model_dump(exclude_none=True)
        if isinstance(user_protocol_settings, ShadowsocksSettings): # Ensure enum values are strings
            if 'method' in user_protocol_settings_dict and hasattr(user_protocol_settings_dict['method'], 'value'):
                user_protocol_settings_dict['method'] = user_protocol_settings_dict['method'].value

        _logger.debug(f"    Final components for conf.add for tag '{service_tag_name}':")
        _logger.debug(f"      Remark: '{remark_str}'")
        _logger.debug(f"      Address: '{final_link_address}'")
        _logger.debug(f"      Port: {final_link_port}") # Port is part of link_specific_details from XRay config
        _logger.debug(f"      User Protocol Settings (passed as 'settings'): {user_protocol_settings_dict}")
        _logger.debug(f"      Link Specific Details (passed as 'inbound'): {json.dumps(link_specific_details, default=str, indent=2)}")


        try:
            conf.add( # type: ignore
                remark=remark_str,
                address=final_link_address, # Public FQDN or IP of the node
                # The `inbound` dict here should contain all XRay inbound params like port, protocol, streamSettings, sni, path, host etc.
                # The `settings` dict should contain user-specific params like VLESS id, SS password.
                inbound=link_specific_details,   # This now carries port, sni, path, host, tls, fp etc from actual_xray_inbound_config
                settings=user_protocol_settings_dict # User's VLESS id, SS pass/method etc.
            )
            _logger.info(f"    Successfully added configuration for tag '{service_tag_name}' to subscription builder.")
        except Exception as e_add:
            _logger.error(f"    Error adding config for tag '{service_tag_name}', remark '{remark_str}': {e_add}", exc_info=True)

    rendered_config = conf.render(reverse=reverse) # type: ignore
    if isinstance(rendered_config, list) and not rendered_config:
        _logger.warning(f"User {format_variables.get('ACCOUNT_NUMBER', 'N/A')}: conf.render() produced an empty list. No links were successfully added.")
    elif isinstance(rendered_config, str) and not rendered_config.strip():
         _logger.warning(f"User {format_variables.get('ACCOUNT_NUMBER', 'N/A')}: conf.render() produced an empty string. No config generated.")
    else:
        _logger.info(f"User {format_variables.get('ACCOUNT_NUMBER', 'N/A')}: Successfully rendered subscription content.")

    return rendered_config


def encode_title(text: str) -> str:
    return f"base64:{base64.b64encode(text.encode()).decode()}"