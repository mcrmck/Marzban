from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from pathlib import PosixPath
from typing import Union

import commentjson
from sqlalchemy import func

from app.db import GetDB # Assuming GetDB provides a session
from app.db import models as db_models
from app.models.proxy import ProxyTypes
from app.models.user import UserStatus # Assuming UserStatus is correctly defined
from app.utils.crypto import get_cert_SANs
# Removed XRAY_FALLBACKS_INBOUND_TAG from this import
from config import DEBUG, XRAY_EXCLUDE_INBOUND_TAGS
import logging

logger = logging.getLogger(__name__)
# Set logger level to DEBUG if DEBUG is True
if DEBUG:
    logger.setLevel(logging.DEBUG)
    # Add a handler if none exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)

def merge_dicts(a, b):  # B will override A dictionary key and values
    for key, value in b.items():
        if isinstance(value, dict) and key in a and isinstance(a[key], dict):
            merge_dicts(a[key], value)  # Recursively merge nested dictionaries
        else:
            a[key] = value
    return a


class XRayConfig(dict):
    def __init__(self,
                 config_dict: Union[dict, str, PosixPath, None] = None,
                 api_host: str = "127.0.0.1",
                 api_port: int = 8080):

        logger.debug(f"XRayConfig.__init__: Starting initialization with config_dict type: {type(config_dict)}")
        if config_dict is not None:
            logger.debug(f"XRayConfig.__init__: config_dict value: {config_dict}")

        self.api_host = api_host
        self.api_port = api_port
        logger.debug(f"XRayConfig.__init__: Using API host: {api_host}, port: {api_port}")

        processed_config = {} # This will hold the configuration to actually use

        if isinstance(config_dict, str):
            logger.debug(f"XRayConfig.__init__: Attempting to parse string config_dict: {config_dict[:100]}...")
            try:
                # considering string as json
                logger.debug("XRayConfig.__init__: Attempting to parse as JSON")
                processed_config = commentjson.loads(config_dict)
                logger.debug("XRayConfig.__init__: Successfully parsed JSON")
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug(f"XRayConfig.__init__: JSON parsing failed ({str(e)}), trying as file path")
                try:
                    logger.debug(f"XRayConfig.__init__: Attempting to load from file: {config_dict}")
                    with open(config_dict, 'r') as file:
                        processed_config = commentjson.loads(file.read())
                    logger.debug(f"XRayConfig.__init__: Successfully loaded from file: {config_dict}")
                except FileNotFoundError:
                    logger.error(f"XRayConfig.__init__: Config file not found: {config_dict}")
                    config_dict = None
                except Exception as e:
                    logger.error(f"XRayConfig.__init__: Error reading config file {config_dict}: {str(e)}")
                    config_dict = None
        elif isinstance(config_dict, PosixPath):
            try:
                logger.debug(f"XRayConfig.__init__: Attempting to load from PosixPath: {config_dict}")
                with open(config_dict, 'r') as file:
                    processed_config = commentjson.loads(file.read())
                logger.debug(f"XRayConfig.__init__: Successfully loaded from PosixPath: {config_dict}")
            except FileNotFoundError:
                logger.error(f"XRayConfig.__init__: Config file not found at PosixPath: {config_dict}")
                config_dict = None
            except Exception as e:
                logger.error(f"XRayConfig.__init__: Error reading from PosixPath {config_dict}: {str(e)}")
                config_dict = None
        elif isinstance(config_dict, dict):
            logger.debug("XRayConfig.__init__: Using provided dictionary as config")
            processed_config = deepcopy(config_dict)
        else:
            logger.debug(f"XRayConfig.__init__: config_dict is of unsupported type: {type(config_dict)}")

        if config_dict is None:
            logger.warning("XRayConfig.__init__: Initializing with default structure because config_dict is None or could not be loaded.")
            processed_config = {
                "log": {
                    "loglevel": "warning"
                },
                "inbounds": [],
                "outbounds": [
                    {
                        "protocol": "freedom",
                        "settings": {},
                        "tag": "direct"
                    },
                    {
                        "protocol": "blackhole",
                        "settings": {},
                        "tag": "block"
                    }
                ],
                "routing": {
                    "rules": []
                }
            }
            logger.debug("XRayConfig.__init__: Default config structure initialized")

        if not isinstance(processed_config, dict):
            logger.error(f"XRayConfig.__init__: Internal error - processed_config is not a dict. Type: {type(processed_config)}")
            raise TypeError("Internal error: processed_config is not a dict after input handling.")

        logger.debug(f"XRayConfig.__init__: Final processed_config keys: {list(processed_config.keys())}")
        super().__init__(processed_config)

        # Initial validation for basic structure if not empty
        if processed_config:
            logger.debug("XRayConfig.__init__: Validating initial config structure")
            self._validate()
            logger.debug("XRayConfig.__init__: Initial validation complete")

        self.inbounds = []
        self.inbounds_by_protocol = defaultdict(list)
        self.inbounds_by_tag = {}
        self._fallbacks_inbound = {}

        logger.debug("XRayConfig.__init__: Applying API configuration")
        self._apply_api()
        logger.debug("XRayConfig.__init__: Resolving inbounds")
        self._resolve_inbounds()
        logger.debug("XRayConfig.__init__: Initialization complete")

    def _apply_api(self):
        api_inbound_entry = self.get_inbound("API_INBOUND") # Check if an inbound with this tag already exists
        if api_inbound_entry: # If it exists, just ensure its port and listen address are correct
            api_inbound_entry["port"] = self.api_port
            api_inbound_entry["listen"] = self.api_host # Overwrite or set listen address
            # Ensure settings.address is also updated if that's how dokodemo-door expects it
            if api_inbound_entry.get("protocol") == "dokodemo-door":
                if "settings" not in api_inbound_entry:
                    api_inbound_entry["settings"] = {}
                api_inbound_entry["settings"]["address"] = self.api_host
            return

        # If no API_INBOUND exists, create it along with api and stats sections
        self["api"] = self.get("api", {
            "services": [
                "HandlerService",
                "StatsService",
                "LoggerService"
            ],
            "tag": "API"
        })
        self["stats"] = self.get("stats", {}) # Initialize stats if not present

        forced_policies = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundDownlink": False, # Typically false for panel-managed stats
                "statsInboundUplink": False,   # Typically false for panel-managed stats
                "statsOutboundDownlink": True,
                "statsOutboundUplink": True
            }
        }
        current_policy = self.get("policy", {})
        self["policy"] = merge_dicts(current_policy, forced_policies)

        new_api_inbound = {
            "listen": self.api_host,
            "port": self.api_port,
            "protocol": "dokodemo-door",
            "settings": {
                "address": self.api_host # Dokodemo typically uses settings.address for the target
            },
            "tag": "API_INBOUND"
        }

        # Ensure 'inbounds' list exists
        if "inbounds" not in self:
            self["inbounds"] = []
        self["inbounds"].insert(0, new_api_inbound)

        # Ensure 'routing' and 'routing.rules' list exist
        if "routing" not in self:
            self["routing"] = {"rules": []}
        elif "rules" not in self["routing"]:
            self["routing"]["rules"] = []

        api_rule = {
            "inboundTag": [
                "API_INBOUND"
            ],
            "outboundTag": "API", # This requires an outbound with tag "API"
            "type": "field"
        }
        # Check if an outbound with tag "API" exists, if not, consider adding a default one
        if not self.get_outbound("API"):
            if "outbounds" not in self:
                self["outbounds"] = []
            # Add a default freedom outbound for API if it doesn't exist, or ensure it's configured
            # For simplicity here, we assume routing to "direct" or similar for API is okay
            # A specific "API" outbound might be "proxy/freedom" tagged "API"
            # For now, let's assume the user ensures an appropriate outbound for "API" tag exists
            # or we simply point to "direct". Using "direct" if "API" outbound is missing:
            api_rule["outboundTag"] = "direct" # Fallback if "API" outbound doesn't exist

        self["routing"]["rules"].insert(0, api_rule)

    def _validate(self):
        # Allow empty inbounds initially, as _apply_api will add the API inbound
        if not self.get("outbounds"): # outbounds must exist
            raise ValueError("XRayConfig: 'outbounds' key is missing or empty.")

        # Validate after all modifications, especially inbounds and outbounds
        # This basic validation is fine for the initial structure.
        # More specific validations occur in _resolve_inbounds.
        for inbound in self.get('inbounds', []): # use .get for safety
            if not inbound.get("tag"):
                raise ValueError("XRayConfig: All inbounds must have a unique tag.")
            if ',' in inbound.get("tag"):
                raise ValueError("XRayConfig: Character «,» is not allowed in inbound tag.")
        for outbound in self.get('outbounds', []):
            if not outbound.get("tag"):
                raise ValueError("XRayConfig: All outbounds must have a unique tag.")

    def _resolve_inbounds(self):
        # Reset internal lists before resolving from the current state of self (the dict)
        self.inbounds = []
        self.inbounds_by_protocol = defaultdict(list)
        self.inbounds_by_tag = {}

        # Find a potential fallback inbound from the configuration itself if defined
        # This is a placeholder for a more robust fallback mechanism.
        # For now, we're not auto-assigning fallbacks like the original code did with XRAY_FALLBACKS_INBOUND_TAG.
        # If a user defines an inbound with a specific setting indicating it's a fallback source,
        # that could be used. Here, _fallbacks_inbound remains mostly unused.
        # self._fallbacks_inbound = {} # Example: find and set self._fallbacks_inbound if logic exists

        for inbound_config_dict in self.get('inbounds', []): # Iterate over current inbounds in self
            # Ensure ProxyTypes has _value2member_map_ or adapt the check
            if not hasattr(ProxyTypes, '_value2member_map_') or inbound_config_dict.get('protocol') not in ProxyTypes._value2member_map_:
                continue

            if inbound_config_dict.get('tag') in XRAY_EXCLUDE_INBOUND_TAGS:
                continue

            # Ensure settings and clients sub-dictionaries exist
            if not inbound_config_dict.get('settings'):
                inbound_config_dict['settings'] = {}
            if not inbound_config_dict['settings'].get('clients'):
                inbound_config_dict['settings']['clients'] = [] # Important for include_db_users

            settings = {
                "tag": inbound_config_dict["tag"],
                "protocol": inbound_config_dict["protocol"],
                "port": inbound_config_dict.get("port"), # Get port directly
                "network": "tcp", # Default
                "tls": 'none',  # Default
                "sni": [],
                "host": [],
                "path": "",
                "header_type": "",
                "is_fallback": False # Not actively used yet without a fallback mechanism
            }

            # stream settings
            if stream_settings_dict := inbound_config_dict.get('streamSettings'):
                net = stream_settings_dict.get('network', 'tcp')
                current_net_settings = stream_settings_dict.get(f"{net}Settings", {})
                security = stream_settings_dict.get("security")
                # Initialize tls_settings to an empty dict to prevent errors if security is None
                current_tls_settings = stream_settings_dict.get(f"{security}Settings", {}) if security else {}

                settings['network'] = net

                if security == 'tls':
                    settings['tls'] = 'tls'
                    for certificate in current_tls_settings.get('certificates', []):
                        if cert_file_path := certificate.get("certificateFile"):
                            try:
                                with open(cert_file_path, 'rb') as file:
                                    cert_bytes = file.read()
                                    settings['sni'].extend(get_cert_SANs(cert_bytes))
                            except FileNotFoundError:
                                print(f"Warning: Certificate file not found: {cert_file_path} for inbound {settings['tag']}")
                            except Exception as e:
                                print(f"Warning: Error reading certificate file {cert_file_path}: {e}")

                        if cert_data_inline := certificate.get("certificate"):
                            if isinstance(cert_data_inline, list):
                                cert_data_inline = '\n'.join(cert_data_inline)
                            if isinstance(cert_data_inline, str):
                                cert_data_inline = cert_data_inline.encode()
                            try:
                                settings['sni'].extend(get_cert_SANs(cert_data_inline))
                            except Exception as e:
                                print(f"Warning: Error processing inline certificate for SNI in inbound {settings['tag']}: {e}")

                elif security == 'reality':
                    settings['fp'] = current_tls_settings.get('fingerprint', 'chrome')
                    settings['tls'] = 'reality'
                    settings['sni'] = current_tls_settings.get('serverNames', []) # Should be 'serverNames' for Xray spec
                    settings['pbk'] = current_tls_settings.get('publicKey')

                    if not settings['pbk']:
                         raise ValueError(
                            f"Panel requires 'publicKey' to be explicitly provided in realitySettings for inbound '{settings['tag']}'. Private key derivation is no longer supported by the panel."
                        )

                    settings['sids'] = current_tls_settings.get('shortIds', [])
                    if not settings['sids']:
                         raise ValueError(
                            f"You need to define at least one shortID in realitySettings of inbound '{settings['tag']}'"
                        )
                    settings['spx'] = current_tls_settings.get('spiderX', "")


                if net in ('tcp', 'raw'):
                    header = current_net_settings.get('header', {})
                    request = header.get('request', {})
                    path_list = request.get('path', [])
                    host_list_from_headers = request.get('headers', {}).get('Host', [])

                    settings['header_type'] = header.get('type', '')

                    if isinstance(path_list, str) or isinstance(host_list_from_headers, str):
                        raise ValueError(f"Settings of {settings['tag']} for path and host must be list, not str for TCP HTTP header")

                    settings['path'] = path_list[0] if path_list else ""
                    settings['host'] = host_list_from_headers if host_list_from_headers else []


                elif net == 'ws':
                    settings['path'] = current_net_settings.get('path', '')
                    host_val_ws = current_net_settings.get('Host', current_net_settings.get('headers', {}).get('Host'))

                    if isinstance(settings['path'], list) or isinstance(host_val_ws, list):
                        raise ValueError(f"Settings of {settings['tag']} for path and host must be str, not list for WebSocket")

                    settings['host'] = [host_val_ws] if host_val_ws else []
                    settings["heartbeatPeriod"] = current_net_settings.get('heartbeatPeriod', 0)


                elif net == 'grpc' or net == 'gun':
                    settings['path'] = current_net_settings.get('serviceName', '')
                    authority_grpc = current_net_settings.get('authority', '')
                    settings['host'] = [authority_grpc] if authority_grpc else []
                    settings['multiMode'] = current_net_settings.get('multiMode', False)

                # Add other network types (quic, httpupgrade, etc.) from your original _resolve_inbounds if needed,
                # ensuring they read from 'current_net_settings' and 'current_tls_settings'.

            self.inbounds.append(settings) # Processed settings for internal use
            self.inbounds_by_tag[settings['tag']] = settings
            self.inbounds_by_protocol[settings['protocol']].append(settings)


    def get_inbound(self, tag) -> dict | None:
        for inbound in self.get('inbounds', []):
            if inbound.get('tag') == tag:
                return inbound
        return None

    def get_outbound(self, tag) -> dict | None:
        for outbound in self.get('outbounds', []):
            if outbound.get('tag') == tag:
                return outbound
        return None

    def to_json(self, **json_kwargs):
        # Return a JSON representation of self (the main dict)
        return json.dumps(dict(self), **json_kwargs)


    def copy(self) -> XRayConfig: # Ensure it returns an instance of XRayConfig
        # Create a new XRayConfig instance from a deepcopy of the current instance's dictionary data.
        # This ensures that the new instance also goes through __init__ processing if necessary,
        # but for a simple copy of the dict content that's already processed, a direct deepcopy is fine.
        # However, to maintain integrity of api_host/port and re-run resolutions:
        new_config_dict = deepcopy(dict(self))
        return XRayConfig(config_dict=new_config_dict, api_host=self.api_host, api_port=self.api_port)


    def include_db_users(self) -> XRayConfig:
        logger.debug("XRayConfig.include_db_users: Starting to include DB users in config")
        config_with_users = self.copy()
        logger.debug("XRayConfig.include_db_users: Created copy of base config")

        with GetDB() as db:
            logger.debug("XRayConfig.include_db_users: Querying active users from database")
            query = db.query(
                db_models.User.id,
                db_models.User.account_number,
                func.lower(db_models.Proxy.type).label('proxy_type_value'),
                db_models.Proxy.settings
            ).join(
                db_models.Proxy, db_models.User.id == db_models.Proxy.user_id
            ).filter(
                db_models.User.status.in_([UserStatus.active, UserStatus.on_hold])
            )
            db_user_proxies = query.all()
            logger.debug(f"XRayConfig.include_db_users: Found {len(db_user_proxies)} active users with proxies")

            grouped_user_proxies_by_protocol = defaultdict(list)
            for row in db_user_proxies:
                grouped_user_proxies_by_protocol[row.proxy_type_value].append({
                    "user_id": row.id,
                    "account_number": row.account_number,
                    "settings": row.settings
                })
            logger.debug(f"XRayConfig.include_db_users: Grouped users by protocol: {list(grouped_user_proxies_by_protocol.keys())}")

            for original_inbound_tag, resolved_inbound_details in config_with_users.inbounds_by_tag.items():
                inbound_protocol = resolved_inbound_details.get("protocol")
                if not inbound_protocol:
                    logger.debug(f"XRayConfig.include_db_users: Skipping inbound {original_inbound_tag} - no protocol defined")
                    continue

                users_for_this_protocol = grouped_user_proxies_by_protocol.get(inbound_protocol, [])
                if not users_for_this_protocol:
                    logger.debug(f"XRayConfig.include_db_users: No users found for protocol {inbound_protocol} in inbound {original_inbound_tag}")
                    continue

                logger.debug(f"XRayConfig.include_db_users: Processing {len(users_for_this_protocol)} users for protocol {inbound_protocol} in inbound {original_inbound_tag}")
                target_inbound_dict = config_with_users.get_inbound(original_inbound_tag)
                if not target_inbound_dict or "settings" not in target_inbound_dict:
                    logger.error(f"XRayConfig.include_db_users: Invalid inbound configuration for {original_inbound_tag}")
                    continue

                if "clients" not in target_inbound_dict["settings"]:
                    target_inbound_dict["settings"]["clients"] = []

                target_inbound_dict["settings"]["clients"] = []

                for user_proxy_data in users_for_this_protocol:
                    client_entry = {
                        "email": f"{user_proxy_data['user_id']}.{user_proxy_data['account_number']}",
                        **user_proxy_data["settings"]
                    }

                    if client_entry.get('flow') and (
                            resolved_inbound_details.get('network', 'tcp') not in ('tcp', 'raw', 'kcp') or
                            (resolved_inbound_details.get('network', 'tcp') in ('tcp', 'raw', 'kcp') and
                             resolved_inbound_details.get('tls') not in ('tls', 'reality')) or
                            resolved_inbound_details.get('header_type') == 'http'
                    ):
                        logger.debug(f"XRayConfig.include_db_users: Removing flow from client {client_entry['email']} due to incompatible settings")
                        client_entry_copy = client_entry.copy()
                        del client_entry_copy['flow']
                        target_inbound_dict["settings"]["clients"].append(client_entry_copy)
                    else:
                        target_inbound_dict["settings"]["clients"].append(client_entry)

                logger.debug(f"XRayConfig.include_db_users: Added {len(target_inbound_dict['settings']['clients'])} clients to inbound {original_inbound_tag}")

        if DEBUG:
            try:
                debug_file = 'generated_config_with_users-debug.json'
                logger.debug(f"XRayConfig.include_db_users: Writing debug config to {debug_file}")
                with open(debug_file, 'w') as f:
                    f.write(config_with_users.to_json(indent=4))
                logger.debug("XRayConfig.include_db_users: Successfully wrote debug config file")
            except Exception as e:
                logger.error(f"XRayConfig.include_db_users: Error writing debug config: {str(e)}")

        logger.debug("XRayConfig.include_db_users: Finished including DB users in config")
        return config_with_users