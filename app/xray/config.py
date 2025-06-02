from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from pathlib import PosixPath
from typing import Union, List, Dict, Optional

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
                 base_template_path: Union[str, PosixPath, None] = None,
                 node_api_host: str = "127.0.0.1",
                 node_api_port: int = 62051):

        logger.debug(f"XRayConfig.__init__: Starting initialization with base_template_path: {base_template_path}")

        self.node_api_host = node_api_host
        self.node_api_port = node_api_port
        logger.debug(f"XRayConfig.__init__: Using node API host: {node_api_host}, port: {node_api_port}")

        # Initialize with default structure
        default_config = {
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

        # If base template provided, try to load and merge it
        if base_template_path:
            try:
                if isinstance(base_template_path, str):
                    with open(base_template_path, 'r') as f:
                        template_config = commentjson.loads(f.read())
                else:  # PosixPath
                    with open(base_template_path, 'r') as f:
                        template_config = commentjson.loads(f.read())

                logger.debug(f"XRayConfig.__init__: Successfully loaded base template from {base_template_path}")
                # Merge template into default config (template takes precedence)
                merge_dicts(default_config, template_config)
            except Exception as e:
                logger.error(f"XRayConfig.__init__: Error loading base template: {e}")
                logger.info("XRayConfig.__init__: Using default configuration structure")

        super().__init__(default_config)
        logger.debug(f"XRayConfig.__init__: Final config keys: {list(self.keys())}")
        self._precompute_inbound_maps()
        logger.debug(f"XRayConfig.__init__: Finished precomputing inbound maps. Final config keys: {list(self.keys())}")

    def _precompute_inbound_maps(self):
        logger.debug("XRayConfig._precompute_inbound_maps: Precomputing inbound protocol and tag maps.")
        from collections import defaultdict
        self.inbounds_by_protocol = defaultdict(list)
        self.inbounds_by_tag = {}  # Simplified to a flat dict with tag as key

        loaded_inbounds = self.get('inbounds', [])
        if not isinstance(loaded_inbounds, list):
            logger.error(f"XRayConfig._precompute_inbound_maps: 'inbounds' is not a list, it's {type(loaded_inbounds)}. Cannot precompute maps.")
            return

        for inbound_config in loaded_inbounds:
            if not isinstance(inbound_config, dict):
                logger.warning(f"XRayConfig._precompute_inbound_maps: Found non-dict item in inbounds list: {inbound_config}")
                continue

            protocol = inbound_config.get('protocol')
            tag = inbound_config.get('tag')

            if protocol:
                self.inbounds_by_protocol[protocol].append(inbound_config)
                if tag:
                    self.inbounds_by_tag[tag] = inbound_config
                else:
                    logger.warning(f"XRayConfig._precompute_inbound_maps: Inbound with protocol '{protocol}' is missing a 'tag'.")
            else:
                logger.warning(f"XRayConfig._precompute_inbound_maps: Inbound is missing a 'protocol': {inbound_config}")

        logger.debug(f"XRayConfig._precompute_inbound_maps: Populated {len(self.inbounds_by_tag)} inbound tags and {len(self.inbounds_by_protocol)} protocols")

    def _apply_node_api_and_policy(self):
        """Configure API, stats, and policy sections for node management."""
        logger.debug("XRayConfig._apply_node_api_and_policy: Applying node API and policy configuration")

        # API section
        self["api"] = {
            "services": ["HandlerService", "StatsService", "LoggerService"],
            "tag": "API_GRPC_CTRL"
        }

        # Stats section
        self["stats"] = {}

        # Policy section
        forced_policies = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundDownlink": True,
                "statsInboundUplink": True
            }
        }
        current_policy = self.get("policy", {})
        self["policy"] = merge_dicts(current_policy, forced_policies)

        # Add XRay gRPC API inbound
        api_inbound = {
            "tag": "API_GRPC_INBOUND",
            "listen": self.node_api_host,
            "port": self.node_api_port,
            "protocol": "dokodemo-door",
            "settings": {
                "address": self.node_api_host,
                "followRedirect": False
            }
        }

        # Ensure inbounds list exists and add API inbound at the start
        if "inbounds" not in self:
            self["inbounds"] = []
        self["inbounds"].insert(0, api_inbound)

        # Add routing rule for API inbound
        api_rule = {
            "type": "field",
            "inboundTag": ["API_GRPC_INBOUND"],
            "outboundTag": "API_GRPC_CTRL"
        }

        # Ensure routing rules list exists and add API rule at the start
        if "routing" not in self:
            self["routing"] = {"rules": []}
        elif "rules" not in self["routing"]:
            self["routing"]["rules"] = []
        self["routing"]["rules"].insert(0, api_rule)

        logger.debug("XRayConfig._apply_node_api_and_policy: Node API and policy configuration applied")
        self._precompute_inbound_maps()

    def _generate_inbound_dict(self, service_db_model: "db_models.NodeServiceConfiguration",
                             users_for_service: List["db_models.User"]) -> dict:
        """Generate an XRay inbound configuration for a specific service."""
        logger.debug(f"XRayConfig._generate_inbound_dict: Generating inbound for service {service_db_model.id}")

        # Process clients
        clients = []
        for db_user in users_for_service:
            # Find user's proxy settings for this service's protocol
            user_proxy = next((p for p in db_user.proxies if p.type == service_db_model.protocol_type), None)
            if not user_proxy:
                continue

            client_entry = {
                "email": f"{db_user.id}.{db_user.account_number}",
                **deepcopy(user_proxy.settings)
            }

            # Handle flow control
            if 'flow' in client_entry:
                network_type = service_db_model.network_type or "tcp"
                security_type = service_db_model.security_type or db_models.SecurityType.NONE
                advanced_settings = service_db_model.advanced_stream_settings or {}
                tcp_settings = advanced_settings.get("tcpSettings", {})
                header_type = tcp_settings.get("header", {}).get("type", "")

                if (network_type not in ('tcp', 'kcp', 'raw') or
                    (network_type in ('tcp', 'kcp', 'raw') and
                     security_type not in (db_models.SecurityType.TLS, db_models.SecurityType.REALITY)) or
                    header_type == 'http'):
                    logger.debug(f"Removing flow from client {client_entry['email']} due to incompatible settings")
                    del client_entry['flow']

            clients.append(client_entry)

        # Protocol settings
        inbound_proto_settings = {}
        if clients:
            inbound_proto_settings["clients"] = clients

        # Add protocol-specific settings
        if service_db_model.protocol_type == ProxyTypes.VLESS:
            inbound_proto_settings["decryption"] = "none"
            if service_db_model.advanced_protocol_settings:
                merge_dicts(inbound_proto_settings, service_db_model.advanced_protocol_settings)
        elif service_db_model.protocol_type == ProxyTypes.VMess:
            if service_db_model.advanced_protocol_settings:
                merge_dicts(inbound_proto_settings, service_db_model.advanced_protocol_settings)
        elif service_db_model.protocol_type == ProxyTypes.Trojan:
            if service_db_model.advanced_protocol_settings:
                merge_dicts(inbound_proto_settings, service_db_model.advanced_protocol_settings)
        elif service_db_model.protocol_type == ProxyTypes.Shadowsocks:
            inbound_proto_settings = deepcopy(service_db_model.advanced_protocol_settings or {})
            if not inbound_proto_settings:
                inbound_proto_settings = {
                    "method": "aes-256-gcm",
                    "password": "marzban_default_ss_password"
                }
                logger.warning(f"Using default Shadowsocks settings for service {service_db_model.id}")

        # Stream settings
        stream_settings = {}
        network_type = service_db_model.network_type or "tcp"
        stream_settings["network"] = network_type

        if service_db_model.security_type != db_models.SecurityType.NONE:
            stream_settings["security"] = service_db_model.security_type.value

        # Network-specific settings
        network_specific_config = {}
        if network_type == "ws":
            network_specific_config["path"] = service_db_model.ws_path or "/"
        elif network_type == "grpc":
            network_specific_config["serviceName"] = service_db_model.grpc_service_name or "default_grpc"
        elif network_type == "http":
            network_specific_config["path"] = service_db_model.http_upgrade_path or "/"

        # Merge advanced stream settings
        if service_db_model.advanced_stream_settings:
            advanced_network_settings = service_db_model.advanced_stream_settings.get(f"{network_type}Settings", {})
            merge_dicts(network_specific_config, advanced_network_settings)

            # Merge other top-level settings
            for key, value in service_db_model.advanced_stream_settings.items():
                if not key.endswith("Settings"):
                    stream_settings[key] = value

        if network_specific_config:
            stream_settings[f"{network_type}Settings"] = network_specific_config

        # Security settings
        if service_db_model.security_type == db_models.SecurityType.TLS:
            tls_settings = {"serverName": service_db_model.sni}
            if service_db_model.fingerprint:
                tls_settings["fingerprint"] = service_db_model.fingerprint
            if service_db_model.advanced_tls_settings:
                merge_dicts(tls_settings, service_db_model.advanced_tls_settings)
            stream_settings["tlsSettings"] = tls_settings

        elif service_db_model.security_type == db_models.SecurityType.REALITY:
            reality_settings = {
                "serverName": service_db_model.sni,
                "publicKey": service_db_model.reality_public_key,
                "shortIds": [service_db_model.reality_short_id]
            }
            if service_db_model.fingerprint:
                reality_settings["fingerprint"] = service_db_model.fingerprint
            if service_db_model.advanced_reality_settings:
                merge_dicts(reality_settings, service_db_model.advanced_reality_settings)
            stream_settings["realitySettings"] = reality_settings

        # Sniffing settings
        sniffing = service_db_model.sniffing_settings or {
            "enabled": True,
            "destOverride": ["http", "tls", "quic", "fakedns"]
        }

        # Assemble final inbound configuration
        inbound_dict = {
            "tag": service_db_model.xray_inbound_tag or f"marzban_service_{service_db_model.id}",
            "protocol": service_db_model.protocol_type.value,
            "listen": service_db_model.listen_address or "0.0.0.0",
            "port": service_db_model.listen_port,
            "settings": inbound_proto_settings,
            "streamSettings": stream_settings,
            "sniffing": sniffing
        }

        logger.debug(f"XRayConfig._generate_inbound_dict: Generated inbound for service {service_db_model.id}")
        return inbound_dict

    def build_node_config(self, node_orm: "db_models.Node",
                         users_on_node: List["db_models.User"]) -> "XRayConfig":
        """Build a complete XRay configuration for a specific node."""
        logger.info(f"XRayConfig.build_node_config: Building config for node {node_orm.name}")

        # Update API port from node
        self.node_api_port = node_orm.api_port
        logger.debug(f"XRayConfig.build_node_config: Using node API port: {self.node_api_port}")

        # Apply node API and policy configuration
        self._apply_node_api_and_policy()

        # Clear existing inbounds except API inbound
        api_inbound = next((inb for inb in self["inbounds"] if inb["tag"] == "API_GRPC_INBOUND"), None)
        self["inbounds"] = [api_inbound] if api_inbound else []

        # Clear the inbound maps since we're rebuilding
        self.inbounds_by_protocol.clear()
        self.inbounds_by_tag.clear()

        # Add API inbound to maps if it exists
        if api_inbound:
            self._update_inbound_maps(api_inbound, 'add')

        # Process each service configuration
        for service in node_orm.service_configurations:
            if not service.enabled:
                logger.debug(f"Skipping disabled service {service.id} on node {node_orm.name}")
                continue

            # Filter users for this service
            relevant_users = [
                user for user in users_on_node
                if any(p.type == service.protocol_type for p in user.proxies)
            ]

            if not relevant_users and service.protocol_type not in (ProxyTypes.HTTP, ProxyTypes.SOCKS):
                logger.warning(f"No relevant users found for service {service.id} on node {node_orm.name}")
                continue

            # Generate inbound configuration
            inbound_dict = self._generate_inbound_dict(service, relevant_users)
            self["inbounds"].append(inbound_dict)
            self._update_inbound_maps(inbound_dict, 'add')

        logger.info(f"XRayConfig.build_node_config: Built config for node {node_orm.name} with {len(self['inbounds'])} inbounds")

        if DEBUG:
            try:
                debug_file = f'generated_config_node_{node_orm.id}-debug.json'
                logger.debug(f"Writing debug config to {debug_file}")
                with open(debug_file, 'w') as f:
                    f.write(self.to_json(indent=4))
            except Exception as e:
                logger.error(f"Error writing debug config: {e}")

        return self

    def copy(self) -> "XRayConfig":
        """Create a deep copy of this configuration."""
        new_dict = deepcopy(dict(self))
        new_instance = XRayConfig(base_template_path=None,
                                node_api_host=self.node_api_host,
                                node_api_port=self.node_api_port)
        new_instance.clear()
        new_instance.update(new_dict)
        return new_instance

    def as_dict(self) -> dict:
        """Return the configuration as a plain dictionary."""
        return dict(self)

    def to_json(self, **json_kwargs):
        """Convert the configuration to a JSON string."""
        return json.dumps(dict(self), **json_kwargs)

    def _update_inbound_maps(self, inbound_config: dict, action: str = 'add'):
        """Update the inbound maps when an inbound is added, modified, or removed.

        Args:
            inbound_config: The inbound configuration dictionary
            action: One of 'add', 'modify', or 'remove'
        """
        if not isinstance(inbound_config, dict):
            logger.warning(f"XRayConfig._update_inbound_maps: Invalid inbound config type: {type(inbound_config)}")
            return

        protocol = inbound_config.get('protocol')
        tag = inbound_config.get('tag')

        if not protocol:
            logger.warning(f"XRayConfig._update_inbound_maps: Inbound missing protocol: {inbound_config}")
            return

        if action in ('add', 'modify'):
            # Update protocol map
            if action == 'add':
                self.inbounds_by_protocol[protocol].append(inbound_config)
            else:  # modify
                # Remove old entry if it exists
                self.inbounds_by_protocol[protocol] = [inb for inb in self.inbounds_by_protocol[protocol]
                                                     if inb.get('tag') != tag]
                self.inbounds_by_protocol[protocol].append(inbound_config)

            # Update tag map
            if tag:
                self.inbounds_by_tag[tag] = inbound_config
            else:
                logger.warning(f"XRayConfig._update_inbound_maps: Inbound missing tag: {inbound_config}")

        elif action == 'remove':
            # Remove from protocol map
            if protocol in self.inbounds_by_protocol:
                self.inbounds_by_protocol[protocol] = [inb for inb in self.inbounds_by_protocol[protocol]
                                                     if inb.get('tag') != tag]
                if not self.inbounds_by_protocol[protocol]:
                    del self.inbounds_by_protocol[protocol]

            # Remove from tag map
            if tag and tag in self.inbounds_by_tag:
                del self.inbounds_by_tag[tag]

        logger.debug(f"XRayConfig._update_inbound_maps: Updated maps after {action} action. "
                    f"Now have {len(self.inbounds_by_tag)} tags and {len(self.inbounds_by_protocol)} protocols")