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
from config import DEBUG, XRAY_EXCLUDE_INBOUND_TAGS, XRAY_FALLBACKS_INBOUND_TAG


def merge_dicts(a, b):  # B will override A dictionary key and values
    for key, value in b.items():
        if isinstance(value, dict) and key in a and isinstance(a[key], dict):
            merge_dicts(a[key], value)  # Recursively merge nested dictionaries
        else:
            a[key] = value
    return a


class XRayConfig(dict):
    def __init__(self,
                 config: Union[dict, str, PosixPath] = {},
                 api_host: str = "127.0.0.1",
                 api_port: int = 8080):
        if isinstance(config, str):
            try:
                # considering string as json
                config = commentjson.loads(config)
            except (json.JSONDecodeError, ValueError):
                # considering string as file path
                with open(config, 'r') as file:
                    config = commentjson.loads(file.read())

        if isinstance(config, PosixPath):
            with open(config, 'r') as file:
                config = commentjson.loads(file.read())

        if isinstance(config, dict):
            config = deepcopy(config)

        self.api_host = api_host
        self.api_port = api_port

        super().__init__(config)
        self._validate()

        self.inbounds = []
        self.inbounds_by_protocol = {}
        self.inbounds_by_tag = {}
        self._fallbacks_inbound = self.get_inbound(XRAY_FALLBACKS_INBOUND_TAG)
        self._resolve_inbounds()

        self._apply_api()

    def _apply_api(self):
        api_inbound = self.get_inbound("API_INBOUND")
        if api_inbound:
            # Ensure 'listen' is a dictionary if it exists, or create it
            if "listen" not in api_inbound or not isinstance(api_inbound["listen"], dict):
                 api_inbound["listen"] = {} # Initialize if not a dict or not present
            api_inbound["listen"]["address"] = self.api_host # Set address within the listen dict
            api_inbound["port"] = self.api_port
            return

        self["api"] = {
            "services": [
                "HandlerService",
                "StatsService",
                "LoggerService"
            ],
            "tag": "API"
        }
        self["stats"] = {}
        forced_policies = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundDownlink": False,
                "statsInboundUplink": False,
                "statsOutboundDownlink": True,
                "statsOutboundUplink": True
            }
        }
        if self.get("policy"):
            self["policy"] = merge_dicts(self.get("policy"), forced_policies)
        else:
            self["policy"] = forced_policies
        inbound = {
            "listen": self.api_host, # listen can be just the address string
            "port": self.api_port,
            "protocol": "dokodemo-door",
            "settings": {
                "address": self.api_host # Or specific address for dokodemo if different
            },
            "tag": "API_INBOUND"
        }
        try:
            self["inbounds"].insert(0, inbound)
        except KeyError:
            self["inbounds"] = []
            self["inbounds"].insert(0, inbound)

        rule = {
            "inboundTag": [
                "API_INBOUND"
            ],
            "outboundTag": "API",
            "type": "field"
        }
        try:
            self["routing"]["rules"].insert(0, rule)
        except KeyError:
            self["routing"] = {"rules": []}
            self["routing"]["rules"].insert(0, rule)

    def _validate(self):
        if not self.get("inbounds"):
            raise ValueError("config doesn't have inbounds")

        if not self.get("outbounds"):
            raise ValueError("config doesn't have outbounds")

        for inbound in self['inbounds']:
            if not inbound.get("tag"):
                raise ValueError("all inbounds must have a unique tag")
            if ',' in inbound.get("tag"):
                raise ValueError("character «,» is not allowed in inbound tag")
        for outbound in self['outbounds']:
            if not outbound.get("tag"):
                raise ValueError("all outbounds must have a unique tag")

    def _resolve_inbounds(self):
        for inbound in self['inbounds']:
            # Ensure ProxyTypes has _value2member_map_ or adapt the check
            if not hasattr(ProxyTypes, '_value2member_map_') or inbound['protocol'] not in ProxyTypes._value2member_map_:
                continue

            if inbound['tag'] in XRAY_EXCLUDE_INBOUND_TAGS:
                continue

            if not inbound.get('settings'):
                inbound['settings'] = {}
            if not inbound['settings'].get('clients'):
                inbound['settings']['clients'] = []

            settings = {
                "tag": inbound["tag"],
                "protocol": inbound["protocol"],
                "port": None,
                "network": "tcp",
                "tls": 'none',
                "sni": [],
                "host": [], # Ensure host is initialized as a list if it's expected to be
                "path": "",
                "header_type": "",
                "is_fallback": False
            }

            # port settings
            try:
                settings['port'] = inbound['port']
            except KeyError:
                if self._fallbacks_inbound:
                    try:
                        settings['port'] = self._fallbacks_inbound['port']
                        settings['is_fallback'] = True
                    except KeyError:
                        raise ValueError("fallbacks inbound doesn't have port")

            # stream settings
            if stream := inbound.get('streamSettings'):
                net = stream.get('network', 'tcp')
                net_settings = stream.get(f"{net}Settings", {})
                security = stream.get("security")
                # Make sure tls_settings is initialized before potential use
                tls_settings = stream.get(f"{security}Settings", {}) if security else {}


                if settings['is_fallback'] is True and self._fallbacks_inbound: # Check _fallbacks_inbound exists
                    # probably this is a fallback
                    fallback_stream_settings = self._fallbacks_inbound.get('streamSettings', {})
                    security = fallback_stream_settings.get('security')
                    tls_settings = fallback_stream_settings.get(f"{security}Settings", {}) if security else {}


                settings['network'] = net

                if security == 'tls':
                    settings['tls'] = 'tls'
                    for certificate in tls_settings.get('certificates', []):
                        if certificate.get("certificateFile"): # Simplified check
                            try:
                                with open(certificate['certificateFile'], 'rb') as file:
                                    cert_bytes = file.read() # Renamed to avoid conflict
                                    settings['sni'].extend(get_cert_SANs(cert_bytes))
                            except FileNotFoundError:
                                # Log error or handle missing cert file
                                print(f"Warning: Certificate file not found: {certificate['certificateFile']}")
                            except Exception as e:
                                print(f"Warning: Error reading certificate file {certificate['certificateFile']}: {e}")


                        if certificate.get("certificate"): # Simplified check
                            cert_data = certificate['certificate'] # Renamed
                            if isinstance(cert_data, list):
                                cert_data = '\n'.join(cert_data)
                            if isinstance(cert_data, str):
                                cert_data = cert_data.encode()
                            try:
                                settings['sni'].extend(get_cert_SANs(cert_data))
                            except Exception as e:
                                print(f"Warning: Error processing inline certificate for SNI: {e}")


                elif security == 'reality':
                    settings['fp'] = tls_settings.get('fingerprint', 'chrome') # Use get with default
                    settings['tls'] = 'reality'
                    settings['sni'] = tls_settings.get('serverNames', [])

                    settings['pbk'] = tls_settings.get('publicKey') # Directly get publicKey
                    if not settings['pbk']: # If publicKey is not directly provided
                        pvk = tls_settings.get('privateKey')
                        if not pvk:
                            raise ValueError(
                                f"You need to provide privateKey or publicKey in realitySettings of {inbound['tag']}")
                        try:
                            from app.xray import core # Local import if not already at top
                            x25519 = core.get_x25519(pvk)
                            settings['pbk'] = x25519['public_key']
                        except ImportError:
                             print("Warning: app.xray.core not available for deriving public key from private key.")
                        except Exception as e:
                            raise ValueError(f"Error deriving public key for {inbound['tag']}: {e}")


                        if not settings.get('pbk'): # Check again after derivation attempt
                            raise ValueError(
                                f"You need to provide publicKey in realitySettings of {inbound['tag']}")

                    settings['sids'] = tls_settings.get('shortIds', []) # Default to empty list
                    if not settings['sids']: # Check if list is empty
                        raise ValueError(
                            f"You need to define at least one shortID in realitySettings of {inbound['tag']}")

                    settings['spx'] = tls_settings.get('spiderX', "") # Corrected key name based on common usage, ensure it matches your Xray version

                if net in ('tcp', 'raw'): # 'raw' is often an alias or similar to 'tcp' in some contexts
                    header = net_settings.get('header', {})
                    request = header.get('request', {})
                    path_setting = request.get('path') # Renamed to avoid conflict
                    host_setting = request.get('headers', {}).get('Host') # Renamed

                    settings['header_type'] = header.get('type', '')

                    if isinstance(path_setting, str) or isinstance(host_setting, str):
                        raise ValueError(f"Settings of {inbound['tag']} for path and host must be list, not str for TCP HTTP header\n"
                                         "https://xtls.github.io/config/transports/tcp.html#httpheaderobject")

                    if path_setting and isinstance(path_setting, list):
                        settings['path'] = path_setting[0] if path_setting else ""

                    if host_setting and isinstance(host_setting, list):
                        settings['host'] = host_setting # host is expected to be a list of strings by some parts of your logic

                elif net == 'ws':
                    path_setting = net_settings.get('path', '')
                    host_value = net_settings.get('Host', net_settings.get('headers', {}).get('Host')) # More robust Host header check

                    settings['header_type'] = '' # Typically no header type for WS itself, it's a protocol

                    if isinstance(path_setting, list) or isinstance(host_value, list):
                        raise ValueError(f"Settings of {inbound['tag']} for path and host must be str, not list for WebSocket\n"
                                         "https://xtls.github.io/config/transports/websocket.html#websocketobject")

                    if isinstance(path_setting, str):
                        settings['path'] = path_setting

                    if isinstance(host_value, str) and host_value: # Ensure host_value is not empty
                        settings['host'] = [host_value]
                    else:
                        settings['host'] = []


                    settings["heartbeatPeriod"] = net_settings.get('heartbeatPeriod', 0) # Added for WS

                elif net == 'grpc' or net == 'gun': # gun is often used for gRPC
                    settings['header_type'] = ''
                    settings['path'] = net_settings.get('serviceName', '')
                    host_value = net_settings.get('authority', '') # authority is used in gRPC
                    settings['host'] = [host_value] if host_value else []
                    settings['multiMode'] = net_settings.get('multiMode', False)


                elif net == 'quic':
                    settings['header_type'] = net_settings.get('header', {}).get('type', '')
                    settings['path'] = net_settings.get('key', '') # QUIC key/PSK
                    settings['host'] = [net_settings.get('security', '')] # QUIC security (e.g., 'none', 'aes-128-gcm')

                elif net == 'httpupgrade':
                    settings['path'] = net_settings.get('path', '')
                    host_value = net_settings.get('host', '')
                    settings['host'] = [host_value] if host_value else []

                # splithttp and xhttp are less common, ensure these settings match your Xray version's capabilities
                elif net in ('splithttp', 'xhttp'): # These are XTLS specific, might not be in standard Xray
                    settings['path'] = net_settings.get('path', '')
                    host_value = net_settings.get('host', '')
                    settings['host'] = [host_value] if host_value else []
                    settings['scMaxEachPostBytes'] = net_settings.get('scMaxEachPostBytes', 1000000)
                    settings['scMaxConcurrentPosts'] = net_settings.get('scMaxConcurrentPosts', 100)
                    settings['scMinPostsIntervalMs'] = net_settings.get('scMinPostsIntervalMs', 30)
                    settings['xPaddingBytes'] = net_settings.get('xPaddingBytes', "100-1000")
                    settings['xmux'] = net_settings.get('xmux', {})
                    settings["mode"] = net_settings.get("mode", "auto")
                    settings["noGRPCHeader"] = net_settings.get("noGRPCHeader", False)
                    settings["keepAlivePeriod"] = net_settings.get("keepAlivePeriod", 0)


                elif net == 'kcp':
                    header = net_settings.get('header', {})
                    settings['header_type'] = header.get('type', '')
                    # KCP 'host' and 'path' are often not standard terms, 'seed' for path-like behavior is common
                    settings['host'] = [] # KCP doesn't typically use a 'Host' header in the same way HTTP does
                    settings['path'] = net_settings.get('seed', '')


                elif net in ("http", "h2"): # h3 uses QUIC, handled above
                    # For HTTP/H2, streamSettings might be under httpSettings
                    actual_net_settings = stream.get("httpSettings", net_settings) # Prefer httpSettings if present

                    settings['host'] = actual_net_settings.get('host', []) # host can be a list of domains
                    if isinstance(settings['host'], str): # Ensure it's a list
                        settings['host'] = [settings['host']] if settings['host'] else []

                    settings['path'] = actual_net_settings.get('path', '')

                # Fallback for other network types if any, though most common are covered
                # else:
                #     settings['path'] = net_settings.get('path', '')
                #     host_value = net_settings.get('host', net_settings.get('Host')) # Check both cases
                #     if isinstance(host_value, str) and host_value:
                #         settings['host'] = [host_value]
                #     elif isinstance(host_value, list):
                #         settings['host'] = host_value
                #     else:
                #         settings['host'] = []


            self.inbounds.append(settings)
            self.inbounds_by_tag[inbound['tag']] = settings

            try:
                self.inbounds_by_protocol[inbound['protocol']].append(settings)
            except KeyError:
                self.inbounds_by_protocol[inbound['protocol']] = [settings]

    def get_inbound(self, tag) -> dict | None: # Added return type hint
        for inbound in self.get('inbounds', []): # Use .get for safety
            if inbound.get('tag') == tag: # Use .get for safety
                return inbound
        return None # Explicitly return None if not found

    def get_outbound(self, tag) -> dict | None: # Added return type hint
        for outbound in self.get('outbounds', []): # Use .get for safety
            if outbound.get('tag') == tag: # Use .get for safety
                return outbound
        return None # Explicitly return None if not found

    def to_json(self, **json_kwargs):
        return json.dumps(self, **json_kwargs)

    def copy(self):
        return deepcopy(self)

    def include_db_users(self) -> XRayConfig:
        config = self.copy()

        with GetDB() as db:
            # Updated query: Removed excluded_inbounds_association
            query = db.query(
                db_models.User.id,
                db_models.User.account_number,
                func.lower(db_models.Proxy.type).label('type'), # Ensure Proxy.type is string here
                db_models.Proxy.settings
            ).join(
                db_models.Proxy, db_models.User.id == db_models.Proxy.user_id
            ).filter(
                db_models.User.status.in_([UserStatus.active, UserStatus.on_hold])
            )
            # Removed group_by as it's not needed without group_concat for excluded inbounds
            # This will fetch one row per user-proxy combination.
            result = query.all()

            # Group users by their proxy type (e.g., "vmess", "vless")
            # Each proxy type will have a list of users (and their specific proxy settings)
            grouped_user_proxies = defaultdict(list)
            for row in result:
                # row.type will be the string value from func.lower(db_models.Proxy.type)
                grouped_user_proxies[row.type].append({
                    "user_id": row.id,
                    "account_number": row.account_number,
                    "settings": row.settings # These are the specific settings for this user's proxy
                })

            # Iterate through the system's configured inbounds (already processed by _resolve_inbounds)
            for inbound_protocol_str, resolved_inbounds_list in self.inbounds_by_protocol.items():
                # inbound_protocol_str is like "vmess", "vless"
                # resolved_inbounds_list is a list of processed inbound settings dicts for that protocol

                # Get the users who have this specific proxy_protocol_str active
                users_for_this_protocol = grouped_user_proxies.get(inbound_protocol_str, [])
                if not users_for_this_protocol:
                    continue # No users have this proxy type configured, skip to next protocol

                # For each system inbound of this protocol type
                for resolved_inbound_settings in resolved_inbounds_list:
                    inbound_tag = resolved_inbound_settings.get("tag")
                    if not inbound_tag:
                        continue # Should not happen if _resolve_inbounds worked correctly

                    # Get the 'clients' list for this specific inbound_tag from the copied config
                    # This ensures we are modifying the correct inbound in the new config object
                    target_inbound_in_config = config.get_inbound(inbound_tag)
                    if not target_inbound_in_config or 'settings' not in target_inbound_in_config:
                        continue

                    # Ensure 'clients' list exists in the target inbound's settings
                    if 'clients' not in target_inbound_in_config['settings']:
                        target_inbound_in_config['settings']['clients'] = []

                    clients_list_for_inbound = target_inbound_in_config['settings']['clients']

                    # Add each user (who has this proxy_protocol active) to this inbound's client list
                    for user_proxy_data in users_for_this_protocol:
                        user_id = user_proxy_data["user_id"]
                        account_number = user_proxy_data["account_number"]
                        user_specific_proxy_settings = user_proxy_data["settings"] # e.g., {"id": "uuid", "level": 0}

                        # Construct the client entry for Xray config
                        client_entry = {
                            "email": f"{user_id}.{account_number}", # Standard Marzban user identifier for Xray
                            **user_specific_proxy_settings # Spread the user's specific proxy settings
                        }

                        # Apply XTLS flow logic (if applicable, based on original code)
                        # This logic might need to be adapted based on the `resolved_inbound_settings` (network, tls type etc.)
                        if client_entry.get('flow') and (
                                resolved_inbound_settings.get('network', 'tcp') not in ('tcp', 'raw', 'kcp') or
                                (resolved_inbound_settings.get('network', 'tcp') in ('tcp', 'raw', 'kcp') and
                                 resolved_inbound_settings.get('tls') not in ('tls', 'reality')) or
                                resolved_inbound_settings.get('header_type') == 'http' # Check based on resolved inbound
                        ):
                            del client_entry['flow']

                        clients_list_for_inbound.append(client_entry)

        if DEBUG:
            try:
                with open('generated_config-debug.json', 'w') as f:
                    f.write(config.to_json(indent=4))
            except Exception as e:
                print(f"Error writing debug config: {e}")


        return config
