import os # Add os import for path checking
import logging # Add logging import
from random import randint
from typing import TYPE_CHECKING, Dict, Sequence # Keep existing Sequence if used by ProxyHost type hint

from app.utils.store import DictStorage
from app.utils.system import check_port
from app.xray import operations # Ensure this is how operations is meant to be imported
from app.xray.config import XRayConfig
from app.xray.node import XRayNode
from xray_api import XRay as XRayAPI # Retaining, though direct use in this file is minimal
from xray_api import exceptions, types
from xray_api import exceptions as exc
from config import XRAY_CONFIG_PATH
from app.db.models import NodeServiceConfiguration # Add this import

# Setup a logger for this module
logger = logging.getLogger(__name__)
# Basic logging config if no handlers are already set up by the app's main logger
if not logging.getLogger('app').hasHandlers(): # Check against a root app logger or a known one
    logging.basicConfig(level=logging.DEBUG)


# Search for a free API port for the default config template
api_port_found = False
api_port_to_use = 20000 # Default fallback for api_port
try:
    for port_candidate in range(randint(10000, 60000), 65536):
        if not check_port(port_candidate):
            api_port_to_use = port_candidate
            api_port_found = True
            break
    # No need for an else here, api_port_to_use has a default
finally:
    # --- MODIFICATION START ---
    # The path where your xray_config.json is confirmed to be inside the container
    actual_xray_config_path = XRAY_CONFIG_PATH

    logger.info(f"Attempting to initialize XRayConfig. Determined API port: {api_port_to_use}")
    logger.info(f"Target XRay config file path: {actual_xray_config_path}")

    if os.path.exists(actual_xray_config_path):
        logger.info(f"XRayConfig file FOUND at {actual_xray_config_path}. Initializing XRayConfig with this path.")
        # Pass the file path string to base_template_path, and also the determined api_port
        config = XRayConfig(base_template_path=actual_xray_config_path, node_api_port=api_port_to_use)
    else:
        logger.error(f"CRITICAL: XRayConfig file NOT FOUND at {actual_xray_config_path}. Falling back to default config structure.")
        config = XRayConfig(base_template_path=None, node_api_port=api_port_to_use)
    # --- MODIFICATION END ---

    # Clean up variables from port search, ensure they exist before deleting
    if 'port_candidate' in locals():
        del port_candidate
    # No need to delete api_port_found or api_port_to_use as they are not large or sensitive here
    # and api_port_to_use is passed to XRayConfig.


# No global 'api' client for a local core
# No global 'core' instance

nodes: Dict[int, XRayNode] = {}


if TYPE_CHECKING:
    # Assuming db_models.ProxyHost is the correct ORM model type
    from app.db import models as db_models_for_typehint # Use an alias to avoid conflict

@DictStorage
def hosts(storage: dict):
    from app.db import GetDB, crud, models as db_models # Import models for type hint

    storage.clear()
    with GetDB() as db_session: # Use a new session for this function
        if hasattr(config, 'inbounds_by_tag') and config.inbounds_by_tag:
            for inbound_tag_key in config.inbounds_by_tag: # Use a different variable name
                # Get service configurations for this inbound tag
                service_configs: Sequence[db_models.NodeServiceConfiguration] = crud.get_service_configurations(db_session, inbound_tag_key)

                storage[inbound_tag_key] = [
                    {
                        "remark": service.service_name,
                        "address": [service.listen_address] if service.listen_address else [],
                        "port": service.listen_port,
                        "path": service.ws_path or service.grpc_service_name or service.http_upgrade_path,
                        "sni": [service.sni] if service.sni else [],
                        "host": [service.sni] if service.sni else [], # Use SNI as host if available
                        "alpn": None, # ALPN is handled in advanced_tls_settings
                        "fingerprint": service.fingerprint,
                        "tls": service.security_type.value if service.security_type else None,
                        "allowinsecure": False, # This should be controlled by security_type
                        "mux_enable": False, # This is now handled in advanced_stream_settings
                        "fragment_setting": None, # This is now handled in advanced_stream_settings
                        "noise_setting": None, # This is now handled in advanced_stream_settings
                        "random_user_agent": False, # This is now handled in advanced_stream_settings
                        "use_sni_as_host": True, # Default to using SNI as host
                        "node_id": service.node_id,
                        # Include advanced settings
                        "advanced_protocol_settings": service.advanced_protocol_settings,
                        "advanced_stream_settings": service.advanced_stream_settings,
                        "advanced_tls_settings": service.advanced_tls_settings,
                        "advanced_reality_settings": service.advanced_reality_settings,
                        "sniffing_settings": service.sniffing_settings
                    } for service in service_configs if service.enabled
                ]
        else:
            logger.warning("hosts function: xray.config.inbounds_by_tag is not available or empty. No hosts loaded.")


__all__ = [
    "config",
    "hosts",
    "nodes",
    "operations",
    "exceptions",
    "exc",
    "types",
    "XRayConfig",
    "XRayNode",
]