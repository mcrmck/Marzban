from random import randint
from typing import TYPE_CHECKING, Dict, Sequence

from app.models.proxy import ProxyHostSecurity
from app.utils.store import DictStorage
from app.utils.system import check_port
from app.xray import operations
from app.xray.config import XRayConfig  # Keeping this import
from app.xray.node import XRayNode      # Keeping this import
from xray_api import XRay as XRayAPI    # This import can stay for now, 'types' might use it
from xray_api import exceptions, types
from xray_api import exceptions as exc


# Search for a free API port for the default config template
# This API port is for the conceptual API inbound within the template.
api_port_found = False
try:
    for port_candidate in range(randint(10000, 60000), 65536):
        if not check_port(port_candidate):
            api_port = port_candidate
            api_port_found = True
            break
    if not api_port_found:
        # Fallback or raise error if no port is found after extensive search
        # For now, let's assume one is found for simplicity in this step.
        # A real scenario might involve a fixed default or a more robust search.
        api_port = 20000 # Default fallback, though the loop should ideally find one.
finally:
    # Initialize 'config' as a base/template XRayConfig instance.
    # It will not load from XRAY_JSON (from main config) anymore.
    # XRayConfig.__init__ will need to handle config_dict=None gracefully.
    config = XRayConfig(config_dict=None, api_port=api_port)
    if api_port_found: # Only delete if it was set in the loop
        del api_port
    del port_candidate # Clean up loop variable
    del api_port_found


# No global 'api' client for a local core
# No global 'core' instance

nodes: Dict[int, XRayNode] = {}


if TYPE_CHECKING:
    from app.db.models import ProxyHost


@DictStorage
def hosts(storage: dict):
    from app.db import GetDB, crud

    storage.clear()
    # 'config' here refers to the xray.config object instantiated above.
    # It needs to have inbounds_by_tag correctly populated, even if from a default template.
    if hasattr(config, 'inbounds_by_tag') and config.inbounds_by_tag:
        for inbound_tag in config.inbounds_by_tag:
            inbound_hosts: Sequence[ProxyHost] = crud.get_hosts(db, inbound_tag)

            storage[inbound_tag] = [
                {
                    "remark": host.remark,
                    "address": [i.strip() for i in host.address.split(',')] if host.address else [],
                    "port": host.port,
                    "path": host.path if host.path else None,
                    "sni": [i.strip() for i in host.sni.split(',')] if host.sni else [],
                    "host": [i.strip() for i in host.host.split(',')] if host.host else [],
                    "alpn": host.alpn.value,
                    "fingerprint": host.fingerprint.value,
                    "tls": None
                    if host.security == ProxyHostSecurity.inbound_default
                    else host.security.value,
                    "allowinsecure": host.allowinsecure,
                    "mux_enable": host.mux_enable,
                    "fragment_setting": host.fragment_setting,
                    "noise_setting": host.noise_setting,
                    "random_user_agent": host.random_user_agent,
                    "use_sni_as_host": host.use_sni_as_host,
                } for host in inbound_hosts if not host.is_disabled
            ]
    else: # Handle case where config might not have inbounds_by_tag (e.g. minimal default)
        pass


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