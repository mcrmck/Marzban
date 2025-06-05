import socket
import re
import ssl
import tempfile
import threading
import time
import json as py_json
from collections import deque
from contextlib import contextmanager
from typing import List, Optional

import requests
import rpyc
from websocket import create_connection, WebSocketConnectionClosedException, WebSocketTimeoutException

from app.xray.config import XRayConfig # Assuming this path is correct in your project
from xray_api import XRay as XRayAPI # Assuming this path is correct
import logging
import os # For potential temp file cleanup if delete=False is used extensively

logger = logging.getLogger(__name__)

# This should be the CA certificate the PANEL uses to verify the NODE'S SERVER CERTIFICATE
PANEL_TRUSTED_CA_PATH = "/etc/marzban/MyMarzbanCA.pem" # Make sure this file exists in the panel container


def string_to_temp_file(content: str) -> tempfile._TemporaryFileWrapper:
    """Creates a temporary file with the given string content.
    The file will be deleted when closed if delete=True (default).
    Using delete=False here to ensure file persists as long as the object needs it.
    Cleanup should be handled by __del__ or explicitly.
    """
    # Using delete=False. Caller is responsible for cleanup or __del__ method should handle.
    file = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
    file.write(content)
    file.flush() # Ensure content is written to disk
    return file




class NodeAPIError(Exception):
    """Custom exception for errors during Node API communication."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Node API Error - Status {status_code}: {detail}")


class ReSTXRayNode:
    """
    Represents a Marzban Node that communicates via a ReST API (HTTPS with mTLS).
    Manages connection, configuration, and interaction with the XRay core on the node.
    """
    def __init__(self,
                 node_id: int,
                 name: str,
                 address: str,
                 port: int,          # Node's REST API port (e.g., 6001)
                 api_port: int,      # XRay's gRPC API port (e.g., 62051)
                 ssl_key_content: str,  # Panel's client private key (string content)
                 ssl_cert_content: str, # Panel's client certificate (string content)
                 usage_coefficient: float = 1.0):

        self.id = node_id
        self.name = name
        self.address = address.strip('/')
        self.port = port
        self.api_port = api_port
        self.usage_coefficient = usage_coefficient

        logger.info(f"Node {self.name} ({self.id}): Initializing ReSTXRayNode for {self.address}:{self.port}. API Port: {self.api_port}")

        # Create temporary files for the panel's client SSL key and certificate
        # These are used by the 'requests' library for mTLS.
        self._keyfile = string_to_temp_file(ssl_key_content)
        self._certfile = string_to_temp_file(ssl_cert_content)
        logger.debug(f"Node {self.name} ({self.id}): Client key temp file: {self._keyfile.name}")
        logger.debug(f"Node {self.name} ({self.id}): Client cert temp file: {self._certfile.name}")

        self.session = requests.Session()
        # To disable hostname verification (e.g., if node cert has CN but no matching SAN):
        # self.session.mount('https://', SANIgnoringAdaptor())
        # logger.warning(f"Node {self.name} ({self.id}): SSL hostname verification is DISABLED via SANIgnoringAdaptor.")

        # Configure mTLS for the session: client cert/key and CA for server verification
        self.session.cert = (self._certfile.name, self._keyfile.name)
        self.session.verify = PANEL_TRUSTED_CA_PATH # CA that signed the node's server certificate

        logger.debug(f"Node {self.name} ({self.id}): Requests session configured with "
                     f"client_cert='{self._certfile.name}', client_key='{self._keyfile.name}', "
                     f"server_ca_verify='{self.session.verify}'")

        self._session_id: Optional[str] = None # Stores the active REST API session ID with the node
        self._rest_api_url = f"https://{self.address}:{self.port}"

        # SSL context for WebSocket connection (if used for logs)
        # This context needs to be configured for mTLS as well if the WebSocket server requires it.
        self._ssl_context_for_ws = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self._ssl_context_for_ws.check_hostname = False # Consistent with SANIgnoringAdaptor if used
        self._ssl_context_for_ws.verify_mode = ssl.CERT_REQUIRED # Panel (client) must verify node's WS cert
        self._ssl_context_for_ws.load_verify_locations(cafile=PANEL_TRUSTED_CA_PATH)
        self._ssl_context_for_ws.load_cert_chain(certfile=self._certfile.name, keyfile=self._keyfile.name) # Panel presents its client cert

        self._logs_ws_url = f"wss://{self.address}:{self.port}/logs"
        self._logs_queues: List[deque] = []
        self._logs_bg_thread = threading.Thread(target=self._bg_fetch_logs, daemon=True)

        self._api: Optional[XRayAPI] = None # For gRPC XRayAPI client
        self._started: bool = False # Tracks if XRay core is considered started on the node
        self._node_server_cert_content: Optional[str] = None # To store fetched node server cert for gRPC

    def __del__(self):
        """Attempt to clean up temporary files when the object is garbage collected."""
        logger.debug(f"Node {self.name} ({self.id}): __del__ called. Cleaning up temporary files.")
        if hasattr(self, '_certfile') and self._certfile:
            try:
                logger.debug(f"Node {self.name} ({self.id}): Closing and deleting temp cert file: {self._certfile.name}")
                self._certfile.close()
                if os.path.exists(self._certfile.name): # If delete=False was used
                    os.remove(self._certfile.name)
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing/deleting temp cert file {getattr(self._certfile, 'name', 'N/A')}: {e}")

        if hasattr(self, '_keyfile') and self._keyfile:
            try:
                logger.debug(f"Node {self.name} ({self.id}): Closing and deleting temp key file: {self._keyfile.name}")
                self._keyfile.close()
                if os.path.exists(self._keyfile.name): # If delete=False was used
                     os.remove(self._keyfile.name)
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing/deleting temp key file {getattr(self._keyfile, 'name', 'N/A')}: {e}")

        # This attribute might not always exist if __init__ failed early or it's an RPyC node.
        if hasattr(self, '_node_certfile') and self._node_certfile:
            try:
                logger.debug(f"Node {self.name} ({self.id}): Closing and deleting temp node server cert file: {self._node_certfile.name}")
                self._node_certfile.close()
                if os.path.exists(self._node_certfile.name): # If delete=False was used
                    os.remove(self._node_certfile.name)
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing/deleting temp node server cert file {getattr(self._node_certfile, 'name', 'N/A')}: {e}")

    def _prepare_config(self, config: XRayConfig) -> XRayConfig:
        """
        Prepares the XRay configuration by inlining certificate file contents.
        Modifies the config object in-place and returns it.
        """
        logger.debug(f"Node {self.name} ({self.id}): Preparing XRay config, inlining certificate files.")
        # This logic assumes 'certificateFile' and 'keyFile' paths are accessible
        # to the panel, and their content needs to be embedded into the config.
        for inbound in config.get("inbounds", []):
            stream_settings = inbound.get("streamSettings") or {}
            # Consider all settings that might contain certificate paths
            security_settings_options = ["tlsSettings", "realitySettings", "xtlsSettings"]
            for settings_key in security_settings_options:
                security_settings = stream_settings.get(settings_key)
                if security_settings and "certificates" in security_settings:
                    for certificate_obj in security_settings["certificates"]:
                        if certificate_obj.get("certificateFile"):
                            cert_file_path = certificate_obj['certificateFile']
                            try:
                                with open(cert_file_path, 'r') as f:
                                    certificate_obj['certificate'] = [line.strip() for line in f.readlines()]
                                del certificate_obj['certificateFile']
                                logger.debug(f"Node {self.name} ({self.id}): Inlined certificateFile: {cert_file_path}")
                            except Exception as e:
                                logger.error(f"Node {self.name} ({self.id}): Error reading certificateFile {cert_file_path}: {e}")

                        if certificate_obj.get("keyFile"):
                            key_file_path = certificate_obj['keyFile']
                            try:
                                with open(key_file_path, 'r') as f:
                                    certificate_obj['key'] = [line.strip() for line in f.readlines()]
                                del certificate_obj['keyFile']
                                logger.debug(f"Node {self.name} ({self.id}): Inlined keyFile: {key_file_path}")
                            except Exception as e:
                                logger.error(f"Node {self.name} ({self.id}): Error reading keyFile {key_file_path}: {e}")
        return config

    def make_request(self, path: str, method: str = "POST", timeout: int = 10, **params_for_body) -> Optional[dict]:
        """
        Makes an HTTP request to the node's ReST API.
        Handles mTLS, JSON body construction, and error parsing.
        The `session_id` for authentication is automatically added to the body for relevant methods.
        """
        request_url = self._rest_api_url + path
        request_kwargs = {"timeout": timeout}

        effective_body_for_log = {} # For logging, don't mutate params_for_body

        if method.upper() in ["POST", "PUT", "PATCH"]:
            # `session_id` is the primary auth; other params are specific to the endpoint.
            # The node API should expect `session_id` alongside other data if needed.
            body_payload = params_for_body.copy() # Start with specific params
            body_payload["session_id"] = self._session_id # Add/overwrite session_id for auth
            request_kwargs["json"] = body_payload
            effective_body_for_log = body_payload
            logger.debug(f"Node {self.name} ({self.id}): Attempting {method} to {request_url} "
                         f"with JSON body: {py_json.dumps(effective_body_for_log, indent=2)}")
        else: # GET, DELETE etc.
            # For GET/DELETE, send session_id and other params as URL query parameters
            query_params = params_for_body.copy()
            if self._session_id is not None: # Only add session_id if it exists
                query_params["session_id"] = self._session_id
            if query_params: # Only add 'params' to kwargs if there are any
                request_kwargs["params"] = query_params
            effective_body_for_log = query_params # For logging query params
            logger.debug(f"Node {self.name} ({self.id}): Attempting {method} to {request_url} "
                         f"with query params: {effective_body_for_log}")

        try:
            response = self.session.request(method, request_url, **request_kwargs)

            # Log raw response for debugging before any processing
            logger.debug(f"Node {self.name} ({self.id}): Response from {method} {request_url}: "
                         f"Status={response.status_code}, Headers={response.headers}, "
                         f"Text (first 200 chars)='{response.text[:200]}'")

            if not response.content and (200 <= response.status_code < 300):
                logger.debug(f"Node {self.name} ({self.id}): Request to {request_url} successful with empty content (Status: {response.status_code}).")
                return None if response.status_code == 204 else {} # Handle 204 No Content vs empty 200 JSON

            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

        except requests.exceptions.SSLError as e:
            logger.error(f"Node {self.name} ({self.id}): SSLError during {method} to {request_url}: {e}", exc_info=True)
            raise NodeAPIError(status_code=0, detail=str(e))
        except requests.exceptions.HTTPError as e: # Raised by response.raise_for_status()
            logger.error(f"Node {self.name} ({self.id}): HTTPError for {method} to {request_url}. Status: {e.response.status_code}. Response: {e.response.text[:200]}", exc_info=True)
            # Try to parse error detail from JSON response if possible
            detail = str(e)
            try:
                err_data = e.response.json()
                detail = err_data.get("detail", str(e))
            except py_json.JSONDecodeError:
                pass # Use original error string
            raise NodeAPIError(status_code=e.response.status_code, detail=detail)
        except requests.exceptions.RequestException as e:
            logger.error(f"Node {self.name} ({self.id}): RequestException (e.g., Timeout, ConnectionError) "
                         f"during {method} to {request_url}: {e}", exc_info=True)
            raise NodeAPIError(status_code=0, detail=str(e))
        except py_json.JSONDecodeError as e:
            logger.error(f"Node {self.name} ({self.id}): JSONDecodeError for {method} to {request_url}. "
                         f"Status: {response.status_code if 'response' in locals() else 'N/A'}. "
                         f"Response text: {response.text[:200] if 'response' in locals() else 'N/A'}", exc_info=True)
            status = response.status_code if 'response' in locals() else 0
            raise NodeAPIError(status_code=status, detail=f"Failed to decode JSON response: {e.msg}")

        # This part is effectively covered by raise_for_status() and subsequent .json() parsing.
        # If we reach here, it means status was 2xx and JSON parsing succeeded.
        return data


    @property
    def connected(self) -> bool:
        """Checks if the node is connected by sending a ping and having a session ID."""
        if not self._session_id:
            logger.debug(f"Node {self.name} ({self.id}): Considered not connected (no session ID).")
            return False
        try:
            # Assuming "/ping" is a POST endpoint that expects session_id in the body.
            # make_request will automatically add self._session_id to the body.
            self.make_request(path="/ping", method="POST", timeout=3)
            logger.debug(f"Node {self.name} ({self.id}): Ping successful.")
            return True
        except NodeAPIError as e:
            logger.warning(f"Node {self.name} ({self.id}): Ping failed, considered not connected. Error: {e.detail}")
            self._session_id = None # Clear session_id on ping failure
            return False
        except Exception as e:
            logger.error(f"Node {self.name} ({self.id}): Unexpected error during ping: {e}", exc_info=True)
            self._session_id = None # Clear session_id
            return False

    @property
    def started(self) -> bool:
        """Checks if XRay core is started on the node by querying its status."""
        if not self._session_id: # Cannot check status if not even connected via REST
            logger.debug(f"Node {self.name} ({self.id}): Cannot check 'started' status, no REST session ID.")
            return False
        try:
            # Assuming root GET path "/" returns status including 'started'.
            # make_request will automatically add self._session_id as a query param for GET.
            res = self.make_request(path="/", method="GET", timeout=3)
            self._started = res.get('started', False) if res else False # Handle None response from make_request
            logger.debug(f"Node {self.name} ({self.id}): XRay core 'started' status: {self._started}")
            return self._started
        except NodeAPIError as e:
            logger.warning(f"Node {self.name} ({self.id}): Could not get XRay 'started' status. Error: {e.detail}")
            return False # Default to False if status check fails
        except Exception as e:
            logger.error(f"Node {self.name} ({self.id}): Unexpected error getting XRay 'started' status: {e}", exc_info=True)
            return False

    @property
    def api(self) -> XRayAPI:
        """Provides a gRPC client (XRayAPI) to interact with the XRay core's API."""
        if not self.connected: # Check REST connection first
            logger.error(f"Node {self.name} ({self.id}): Cannot get gRPC API, REST API not connected.")
            raise ConnectionError(f"Node {self.name} is not connected via REST API.")
        if not self.started:
            logger.error(f"Node {self.name} ({self.id}): Cannot get gRPC API, XRay core not started on node.")
            raise ConnectionError(f"XRay core on node {self.name} is not started.")

        if not self._node_server_cert_content:
            logger.error(f"Node {self.name} ({self.id}): Node's server certificate for gRPC not available.")
            # Attempt to fetch it now if we are connected via REST
            try:
                logger.info(f"Node {self.name} ({self.id}): Fetching server certificate from {self.address}:{self.port} for gRPC API.")
                self._node_server_cert_content = ssl.get_server_certificate((self.address, self.port))
                logger.info(f"Node {self.name} ({self.id}): Successfully fetched server certificate for gRPC.")
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Failed to fetch server certificate for gRPC: {e}", exc_info=True)
                raise ConnectionError(f"Node {self.name}'s server certificate for gRPC mTLS could not be obtained: {e}")

        if not self._api:
            logger.info(f"Node {self.name} ({self.id}): Initializing gRPC XRayAPI to {self.address}:{self.api_port}")
            try:
                # For gRPC TLS:
                # `ssl_cert` in XRayAPI is the CA cert used by the client (panel) to verify the XRay gRPC server.
                # OR it's the XRay gRPC server's own certificate if server auth is one-way TLS.
                # If XRay gRPC API also requires client certificates (mTLS for gRPC),
                # then XRayAPI would need parameters like `client_key` and `client_cert`.
                # The current usage implies one-way TLS from panel to XRay gRPC, where panel verifies XRay's cert.
                self._api = XRayAPI(
                    address=self.address,
                    port=self.api_port,
                    ssl_cert=self._node_server_cert_content.encode(), # Panel uses this to verify XRay gRPC server
                    ssl_target_name=self.address # Or specific CN/SAN in XRay gRPC server's cert
                )
                # Consider adding a gRPC ping or simple command here to confirm connectivity
                # grpc.channel_ready_future(self._api._channel).result(timeout=5)
                logger.info(f"Node {self.name} ({self.id}): gRPC XRayAPI initialized.")
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Failed to initialize gRPC XRayAPI: {e}", exc_info=True)
                self._api = None
                raise ConnectionError(f"Failed to initialize gRPC API for node {self.name}: {e}")
        return self._api

    def connect(self) -> bool:
        """Establishes a ReST API session with the node."""
        logger.info(f"Node {self.name} ({self.id}): ReSTXRayNode.connect() called. Current session ID: {self._session_id}. "
                    f"Main session obj: {id(self.session)}, URL: {self._rest_api_url}")

        # If already connected (has a valid session_id and ping works), no need to reconnect.
        # However, the `connected` property itself pings, so be careful of recursive calls if connect() calls connected().
        # Let's assume connect() is called when a fresh connection or re-connection is desired.
        # We'll clear the old session ID to force a new one if this method is explicitly called.
        # self._session_id = None # Uncomment if explicit call to connect should always get new session

        connect_body_params = {"session_id": self._session_id} # Python None becomes JSON null if _session_id is None

        # --- TEMPORARY SESSION TEST ---
        # Set to True to use a fresh session for this connect call, bypassing self.session.
        # Useful for diagnosing if self.session (pooled connection) is the issue.
        use_temp_session_for_connect_test = True
        # -----------------------------

        if use_temp_session_for_connect_test:
            logger.info(f"Node {self.name} ({self.id}): === Performing /connect with a TEMPORARY session ===")
            temp_session = requests.Session()
            temp_session.cert = (self._certfile.name, self._keyfile.name)
            temp_session.verify = PANEL_TRUSTED_CA_PATH

            logger.debug(f"Node {self.name} ({self.id}): Temp session configured with client cert, key, and CA verify.")

            response_data_temp = None
            try:
                logger.debug(f"Node {self.name} ({self.id}): Making /connect request with TEMP session. Body params: {connect_body_params}")
                # make_request for temp session (simplified version of main make_request for this test)
                response = temp_session.post(self._rest_api_url + "/connect", json=connect_body_params, timeout=10)
                response.raise_for_status()
                response_data_temp = response.json()
                logger.info(f"Node {self.name} ({self.id}): /connect with TEMP session successful. Response: {response_data_temp}")

                self._session_id = response_data_temp.get("session_id")
                self.core_version = response_data_temp.get("core_version") # Assuming /connect returns this
                self.xray_status = "connected"
                logger.info(f"Node {self.name} ({self.id}): Successfully established connection using TEMP session. New Session ID: {self._session_id}")

                # Fetch node's server certificate for gRPC, now that REST connection is up
                if not self._node_server_cert_content:
                    try:
                        logger.debug(f"Node {self.name} ({self.id}): Fetching server certificate from {self.address}:{self.port} for gRPC API.")
                        self._node_server_cert_content = ssl.get_server_certificate((self.address, self.port))
                        logger.info(f"Node {self.name} ({self.id}): Successfully fetched node's server certificate for gRPC.")
                    except Exception as e:
                        logger.error(f"Node {self.name} ({self.id}): Failed to fetch node's server certificate for gRPC: {e}", exc_info=True)
                        # This doesn't mean REST connect failed, but gRPC will fail later.
                return True

            except requests.exceptions.RequestException as e: # Catches SSLError, HTTPError, Timeout, ConnectionError etc.
                logger.error(f"Node {self.name} ({self.id}): === TEMPORARY session /connect FAILED. Error: {e} ===", exc_info=True)
                self.xray_status = "error"
                raise NodeAPIError(status_code=0, detail=f"Temp session connect failed: {str(e)}")
            finally:
                temp_session.close()

        # ---- If not using temp_session_for_connect_test, or if you want to proceed with self.session ----
        logger.info(f"Node {self.name} ({self.id}): === Performing /connect with MAIN session (self.session) ===")

        # Ensure main session is correctly configured (should be done in __init__)
        if not self.session.verify: self.session.verify = PANEL_TRUSTED_CA_PATH
        if not self.session.cert: self.session.cert = (self._certfile.name, self._keyfile.name)

        logger.debug(f"Node {self.name} ({self.id}): Main session verify: {self.session.verify}, cert: {self.session.cert}")

        try:
            if not self._node_server_cert_content: # Fetch if not already fetched
                logger.debug(f"Node {self.name} ({self.id}): Fetching server certificate from {self.address}:{self.port} for gRPC API.")
                self._node_server_cert_content = ssl.get_server_certificate((self.address, self.port))
                logger.info(f"Node {self.name} ({self.id}): Successfully fetched node's server certificate for gRPC.")

            # make_request already adds self._session_id.
            # If /connect expects {"session_id": null/value}, then we pass that as a parameter.
            # The `connect_body_params` already holds this.
            response_data_main = self.make_request(path="/connect", method="POST", timeout=10, **connect_body_params)

            if response_data_main: # Check if response is not None (e.g. from 204)
                self._session_id = response_data_main.get('session_id')
                self.core_version = response_data_main.get('core_version')
                self.xray_status = "connected"
                logger.info(f"Node {self.name} ({self.id}): Successfully connected using MAIN session. New Session ID: {self._session_id}")
                return True
            else: # Should not happen if make_request raises error on failure or returns dict on success
                logger.error(f"Node {self.name} ({self.id}): Connection with MAIN session to /connect seemed to succeed but returned no data.")
                self.xray_status = "error"
                raise NodeAPIError(status_code=0, detail="Connected but received no data from /connect")

        except NodeAPIError as e: # Re-catches from make_request
            logger.error(f"Node {self.name} ({self.id}): Failed to connect using MAIN session. Error: {e.detail}", exc_info=True)
            self.xray_status = "error"
            raise # Re-raise the caught NodeAPIError
        except Exception as e:
            logger.error(f"Node {self.name} ({self.id}): Unexpected error during MAIN session connect: {e}", exc_info=True)
            self.xray_status = "error"
            raise NodeAPIError(status_code=0, detail=f"Unexpected error during main session connect: {str(e)}")


    def disconnect(self):
        """Disconnects from the node's ReST API by invalidating the session."""
        if not self._session_id:
            logger.info(f"Node {self.name} ({self.id}): Already disconnected or never connected (no session ID).")
            return

        logger.info(f"Node {self.name} ({self.id}): Attempting to disconnect ReST session ID: {self._session_id}")
        try:
            # The /disconnect endpoint needs the current session_id to invalidate.
            # make_request automatically includes self._session_id in the body.
            # If /disconnect doesn't need any *other* params, just call it.
            self.make_request(path="/disconnect", method="POST", timeout=5)
            logger.info(f"Node {self.name} ({self.id}): Disconnected ReST session successfully.")
        except NodeAPIError as e:
            logger.error(f"Node {self.name} ({self.id}): Failed to disconnect ReST session. Error: {e.detail}", exc_info=True)
            # Still proceed to clear local state
        finally:
            self._session_id = None
            self.xray_status = "disconnected"
            self._api = None # Clear gRPC API client as REST session is gone
            self._started = False # Assume XRay is no longer controlled/known state

    def get_version(self) -> Optional[str]:
        """Gets the XRay core version from the node."""
        logger.debug(f"Node {self.name} ({self.id}): Getting XRay core version.")
        if not self.connected:
             logger.warning(f"Node {self.name} ({self.id}): Cannot get version, not connected.")
             return None # Or raise error
        try:
            # Assuming root path "/" or a specific "/status" or "/version" endpoint
            res = self.make_request(path="/", method="GET", timeout=3) # make_request adds session_id as query param
            if res and 'core_version' in res:
                self.core_version = res['core_version']
                logger.debug(f"Node {self.name} ({self.id}): Fetched XRay core version: {self.core_version}")
                return self.core_version
            else:
                logger.warning(f"Node {self.name} ({self.id}): 'core_version' not found in response from GET /. Response: {res}")
                return None
        except NodeAPIError as e:
            logger.error(f"Node {self.name} ({self.id}): Error getting version: {e.detail}", exc_info=True)
            return None


    def start(self, config: XRayConfig) -> Optional[dict]:
        """Starts the XRay core on the node with the given configuration."""
        logger.info(f"Node {self.name} ({self.id}): Attempting to start XRay core.")
        if not self.connected:
            logger.info(f"Node {self.name} ({self.id}): Not connected, attempting to connect first.")
            if not self.connect(): # connect() now returns bool
                 logger.error(f"Node {self.name} ({self.id}): Connection attempt failed. Cannot start XRay.")
                 raise NodeAPIError(status_code=0, detail="Pre-start connection failed.")

        prepared_config = self._prepare_config(config)
        prepared_config_dict = prepared_config.as_dict()
        prepared_config_json = py_json.dumps(prepared_config_dict)

        try:
            logger.debug(f"Node {self.name} ({self.id}): Sending /start request with config.")
            res = self.make_request(path="/start", method="POST", timeout=10, config=prepared_config_json)
        except NodeAPIError as exc:
            if 'Xray is started already' in str(exc.detail): # Check string representation
                logger.warning(f"Node {self.name} ({self.id}): XRay already started, attempting restart.")
                return self.restart(config)
            else:
                logger.error(f"Node {self.name} ({self.id}): Error starting XRay: {exc.detail}", exc_info=True)
                raise

        self._started = True
        logger.info(f"Node {self.name} ({self.id}): XRay core reported as started successfully by /start call.")

        # Initialize and test gRPC API
        try:
            if self.api: # Accessing property initializes and tests it
                logger.info(f"Node {self.name} ({self.id}): gRPC API connection to XRay core OK after start.")
        except ConnectionError as e: # Catch errors from self.api property
            logger.error(f"Node {self.name} ({self.id}): Failed to establish gRPC API connection after starting XRay: {e}", exc_info=True)

        return res

    def stop(self):
        """Stops the XRay core on the node."""
        logger.info(f"Node {self.name} ({self.id}): Attempting to stop XRay core.")
        if not self.connected:
            logger.info(f"Node {self.name} ({self.id}): Not connected, attempting to connect first before stopping.")
            if not self.connect():
                 logger.error(f"Node {self.name} ({self.id}): Connection attempt failed. Cannot stop XRay.")
                 raise NodeAPIError(status_code=0, detail="Pre-stop connection failed.")
        try:
            self.make_request(path='/stop', method="POST", timeout=5)
            logger.info(f"Node {self.name} ({self.id}): XRay core stopped successfully via API.")
        except NodeAPIError as e:
            logger.error(f"Node {self.name} ({self.id}): Error stopping XRay: {e.detail}", exc_info=True)
            # Even if API call fails (e.g. already stopped), update local state
        finally:
            self._api = None # Clear gRPC client
            self._started = False # Mark as stopped locally
            logger.debug(f"Node {self.name} ({self.id}): Local state set to stopped.")


    def restart(self, config: XRayConfig) -> Optional[dict]:
        """Restarts the XRay core on the node with the given configuration."""
        logger.info(f"Node {self.name} ({self.id}): Attempting to restart XRay core.")
        if not self.connected:
            logger.info(f"Node {self.name} ({self.id}): Not connected, attempting to connect first before restarting.")
            if not self.connect():
                 logger.error(f"Node {self.name} ({self.id}): Connection attempt failed. Cannot restart XRay.")
                 raise NodeAPIError(status_code=0, detail="Pre-restart connection failed.")

        prepared_config = self._prepare_config(config)
        prepared_config_dict = prepared_config.as_dict()
        prepared_config_json = py_json.dumps(prepared_config_dict)

        try:
            logger.debug(f"Node {self.name} ({self.id}): Sending /restart request with config.")
            res = self.make_request(path="/restart", method="POST", timeout=10, config=prepared_config_json)
        except NodeAPIError as e:
            logger.error(f"Node {self.name} ({self.id}): Error restarting XRay: {e.detail}", exc_info=True)
            raise

        self._started = True # Assume restart implies it's (now) started
        logger.info(f"Node {self.name} ({self.id}): XRay core reported as restarted successfully.")

        self._api = None # Clear old gRPC client to force reinitialization
        try:
            if self.api: # Accessing property re-initializes and tests
                logger.info(f"Node {self.name} ({self.id}): gRPC API connection after restart OK.")
        except ConnectionError as e:
            logger.error(f"Node {self.name} ({self.id}): Failed to establish gRPC API connection after restarting XRay: {e}", exc_info=True)

        return res

    def _bg_fetch_logs(self):
        """Background thread function to fetch logs via WebSocket."""
        while True:
            if not self._logs_queues: # No active listeners
                logger.debug(f"Node {self.name} ({self.id}): No log queues, WebSocket log fetching thread exiting.")
                break

            if not self._session_id:
                logger.warning(f"Node {self.name} ({self.id}): No REST session ID, cannot fetch logs via WebSocket. Waiting...")
                time.sleep(5)
                continue # Go to start of while True to re-check queues and session_id

            try:
                websocket_url = f"{self._logs_ws_url}?session_id={self._session_id}&interval=0.7"
                logger.info(f"Node {self.name} ({self.id}): Connecting to WebSocket for logs: {websocket_url}")

                # Using the _ssl_context_for_ws which is configured for mTLS
                ws = create_connection(websocket_url, sslopt={"context": self._ssl_context_for_ws}, timeout=5)
                logger.info(f"Node {self.name} ({self.id}): WebSocket connected for logs.")

                while self._logs_queues: # Check queues again before entering receive loop
                    try:
                        log_message = ws.recv()
                        if not log_message:
                            # logger.debug(f"Node {self.name} ({self.id}): WebSocket received empty message (keep-alive?).")
                            continue
                        for buf in list(self._logs_queues): # Iterate copy
                            if buf is not None: # Should not be None if list management is correct
                                buf.append(log_message)
                    except WebSocketConnectionClosedException:
                        logger.warning(f"Node {self.name} ({self.id}): WebSocket connection closed by server.")
                        break # Break inner loop to attempt reconnection
                    except WebSocketTimeoutException:
                        # This is expected if no logs are sent within the timeout
                        # logger.debug(f"Node {self.name} ({self.id}): WebSocket recv timeout.")
                        pass
                    except Exception as e:
                        logger.error(f"Node {self.name} ({self.id}): Error receiving from WebSocket: {e}", exc_info=True)
                        break # Break inner loop on other errors
                ws.close() # Ensure closed if inner loop breaks
            except ssl.SSLError as e:
                logger.error(f"Node {self.name} ({self.id}): SSL error connecting WebSocket: {e}", exc_info=True)
            except ConnectionRefusedError as e:
                logger.error(f"Node {self.name} ({self.id}): Connection refused for WebSocket: {e}")
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Generic error in WebSocket connection/outer loop: {e}", exc_info=True)

            if not self._logs_queues: # Final check before sleep
                logger.debug(f"Node {self.name} ({self.id}): No log queues after WebSocket attempt, exiting thread.")
                break
            logger.debug(f"Node {self.name} ({self.id}): WebSocket attempt finished, sleeping before retry if needed.")
            time.sleep(3) # Wait a bit before retrying the WebSocket connection

    @contextmanager
    def get_logs(self) -> deque:
        """Context manager to get a new log buffer and manage thread lifecycle."""
        buffer = deque(maxlen=100)
        self._logs_queues.append(buffer)
        logger.debug(f"Node {self.name} ({self.id}): Added log queue. Total queues: {len(self._logs_queues)}. New queue ID: {id(buffer)}")

        if self._logs_queues and (not self._logs_bg_thread.is_alive()):
            try:
                logger.info(f"Node {self.name} ({self.id}): Starting background log fetching thread.")
                self._logs_bg_thread.start()
            except RuntimeError:
                logger.info(f"Node {self.name} ({self.id}): Background log fetching thread was dead, creating new and starting.")
                self._logs_bg_thread = threading.Thread(target=self._bg_fetch_logs, daemon=True)
                self._logs_bg_thread.start()

        try:
            yield buffer
        finally:
            try:
                self._logs_queues.remove(buffer)
                logger.debug(f"Node {self.name} ({self.id}): Removed log queue ID: {id(buffer)}. Total queues: {len(self._logs_queues)}")
            except ValueError:
                logger.warning(f"Node {self.name} ({self.id}): Log queue ID {id(buffer)} not found for removal, already removed?")
            # del buffer # Not strictly necessary

class RPyCXRayNode:
    """
    Represents a Marzban Node that communicates via RPyC (over SSL for mTLS).
    This class definition is kept from your original code for completeness.
    Ensure its __init__ also gets node_id and name if it's used.
    Its SSL connection logic (ca_certs) also needs to use PANEL_TRUSTED_CA_PATH.
    """
    def __init__(self,
                 # Consider adding node_id and name here too for consistency
                 node_id: int, name: str, # ADDED for consistency
                 address: str,
                 port: int,
                 api_port: int, # XRay gRPC API port, might be less relevant for RPyC direct control
                 ssl_key_content: str, # Panel's client key content
                 ssl_cert_content: str, # Panel's client cert content
                 usage_coefficient: float = 1.0):

        self.id = node_id # ADDED
        self.name = name   # ADDED
        logger.info(f"Node {self.name} ({self.id}): Initializing RPyCXRayNode for {address}:{port}.")

        class Service(rpyc.Service):
            # ... (RPyC Service class as you provided) ...
            def __init__(self, parent_node_name: str, on_start_funcs: List[callable] = None, on_stop_funcs: List[callable] = None):
                self.parent_node_name = parent_node_name
                self.on_start_funcs = on_start_funcs or []
                self.on_stop_funcs = on_stop_funcs or []
                logger.debug(f"RPyC Service for Node {self.parent_node_name} initialized.")
            # ... rest of Service class methods ...

        self.address = address.strip('/')
        self.port = port
        self.api_port = api_port # May or may not be used if RPyC controls XRay directly
        # self.ssl_key_content = ssl_key_content
        # self.ssl_cert_content = ssl_cert_content
        self.usage_coefficient = usage_coefficient

        self.started = False # Tracks if XRay core is started on the node via RPyC

        self._keyfile = string_to_temp_file(ssl_key_content)
        self._certfile = string_to_temp_file(ssl_cert_content)
        logger.debug(f"Node {self.name} ({self.id}): RPyC client key temp file: {self._keyfile.name}")
        logger.debug(f"Node {self.name} ({self.id}): RPyC client cert temp file: {self._certfile.name}")

        self._service = Service(parent_node_name=self.name)
        self._api: Optional[XRayAPI] = None # For gRPC, if still used alongside RPyC
        self._node_server_cert_content: Optional[str] = None # For gRPC or if RPyC client needs it explicitly
        self.connection = None # RPyC connection object

    def __del__(self):
        logger.debug(f"Node {self.name} ({self.id}): RPyCXRayNode __del__ called. Cleaning up.")
        self.disconnect() # Close RPyC connection
        if hasattr(self, '_certfile') and self._certfile:
            try:
                logger.debug(f"Node {self.name} ({self.id}): Closing RPyC temp cert file: {self._certfile.name}")
                self._certfile.close()
                if os.path.exists(self._certfile.name): os.remove(self._certfile.name)
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing RPyC temp cert file: {e}")
        if hasattr(self, '_keyfile') and self._keyfile:
            try:
                logger.debug(f"Node {self.name} ({self.id}): Closing RPyC temp key file: {self._keyfile.name}")
                self._keyfile.close()
                if os.path.exists(self._keyfile.name): os.remove(self._keyfile.name)
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing RPyC temp key file: {e}")
        if hasattr(self, '_node_certfile') and self._node_certfile: # If this temp file was used for RPyC CA
            try:
                self._node_certfile.close()
                if os.path.exists(self._node_certfile.name): os.remove(self._node_certfile.name)
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing RPyC temp _node_certfile: {e}")


    def disconnect(self):
        logger.debug(f"Node {self.name} ({self.id}): RPyC disconnect called.")
        if hasattr(self, 'connection') and self.connection and not self.connection.closed:
            try:
                self.connection.close()
                logger.info(f"Node {self.name} ({self.id}): RPyC connection closed.")
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): Error closing RPyC connection: {e}")
        self.connection = None


    def connect(self):
        logger.info(f"Node {self.name} ({self.id}): Attempting RPyC SSL connect to {self.address}:{self.port}")
        self.disconnect() # Ensure any old connection is closed

        # For RPyC's ssl_connect, ca_certs is used by the client (panel) to verify the server (node).
        # It should be PANEL_TRUSTED_CA_PATH.
        # The server (RPyC node) would need its own CA to verify the client if doing mTLS.
        # RPyC's ssl_connect uses Python's ssl module.

        # The original code used `self._node_certfile.name` for ca_certs, which is incorrect.
        # It should be the CA that signed the RPyC server's certificate.

        # Fetching server cert here is only for `ssl_target_name` in gRPC or if RPyC server cert CN is needed for `server_hostname`.
        # For `ca_certs` in `rpyc.ssl_connect`, we need the CA that signed the RPyC server's certificate.

        # If RPyC server on the node is using the same server.crt as the ReST API,
        # then PANEL_TRUSTED_CA_PATH is the correct CA to verify it.

        ssl_kwargs = {
            "keyfile": self._keyfile.name,
            "certfile": self._certfile.name,
            "ca_certs": PANEL_TRUSTED_CA_PATH, # CRITICAL FIX: Use the actual CA
            "cert_reqs": ssl.CERT_REQUIRED,
            "server_side": False, # We are the client
            # "server_hostname": self.address # Important if node's cert CN/SAN needs to match address
        }
        logger.debug(f"Node {self.name} ({self.id}): RPyC ssl_connect kwargs: keyfile={ssl_kwargs['keyfile']}, "
                     f"certfile={ssl_kwargs['certfile']}, ca_certs={ssl_kwargs['ca_certs']}")

        tries = 0
        max_tries = 3
        while tries < max_tries:
            tries += 1
            try:
                logger.debug(f"Node {self.name} ({self.id}): RPyC connect attempt {tries}/{max_tries}")
                # rpyc.ssl_connect itself creates the SSL context.
                # We pass cert_reqs for client to require server cert validation.
                conn = rpyc.ssl_connect(self.address,
                                        self.port,
                                        service=self._service, # For remote callbacks, if any
                                        config={"ssl_keyfile": self._keyfile.name,
                                                "ssl_certfile": self._certfile.name,
                                                "ssl_ca_certs": PANEL_TRUSTED_CA_PATH,
                                                "ssl_cert_reqs": ssl.CERT_REQUIRED,
                                                "sync_request_timeout": 10, # Timeout for RPyC requests
                                                },
                                        keepalive=True)
                conn.ping(timeout=5) # Test with a timeout
                self.connection = conn
                logger.info(f"Node {self.name} ({self.id}): RPyC SSL connection successful.")
                # Fetch node's server cert for gRPC API if it's going to be used
                if not self._node_server_cert_content:
                    try:
                        self._node_server_cert_content = ssl.get_server_certificate((self.address, self.port)) # Assuming gRPC uses same cert as RPyC
                    except Exception as e_cert:
                        logger.warning(f"Node {self.name} ({self.id}): Could not fetch server cert for gRPC after RPyC connect: {e_cert}")
                break # Successful connection
            except (rpyc.core.protocol.PingError, EOFError, TimeoutError, socket.timeout, ssl.SSLError) as exc:
                logger.warning(f"Node {self.name} ({self.id}): RPyC connect attempt {tries}/{max_tries} failed: {exc}")
                if tries >= max_tries:
                    logger.error(f"Node {self.name} ({self.id}): RPyC connect failed after {max_tries} attempts.")
                    raise ConnectionError(f"RPyC connect to {self.name} failed: {exc}") from exc
                time.sleep(1) # Wait a bit before retrying
            except Exception as exc: # Catch any other unexpected error
                 logger.error(f"Node {self.name} ({self.id}): Unexpected RPyC connect error: {exc}", exc_info=True)
                 raise ConnectionError(f"Unexpected RPyC connect error for {self.name}: {exc}") from exc


    @property
    def connected(self) -> bool:
        try:
            return self.connection is not None and not self.connection.closed and self.connection.ping(timeout=2)
        except (AttributeError, EOFError, TimeoutError, rpyc.core.protocol.PingError, ConnectionRefusedError, BrokenPipeError):
            logger.debug(f"Node {self.name} ({self.id}): RPyC ping failed or not connected.")
            self.disconnect() # Ensure connection object is cleaned up
            return False
        except Exception as e:
            logger.error(f"Node {self.name} ({self.id}): RPyC unexpected error in connected check: {e}", exc_info=True)
            return False


    @property
    def remote(self): # Access to RPyC server's exposed methods
        if not self.connected:
            logger.info(f"Node {self.name} ({self.id}): RPyC not connected, attempting to connect for remote access.")
            self.connect() # This will raise an error if it fails
        return self.connection.root

    @property
    def api(self) -> Optional[XRayAPI]: # gRPC API
        # Decide if RPyC node type should even have a gRPC API.
        # If RPyC provides full control, this might not be needed or used.
        # For now, keeping the logic similar to ReSTXRayNode.
        if not self.connected: # RPyC connection
            logger.error(f"Node {self.name} ({self.id}): RPyCXRayNode cannot get gRPC API, RPyC not connected.")
            raise ConnectionError(f"RPyC to node {self.name} is not connected.")
        if not self.started: # XRay started via RPyC
            logger.error(f"Node {self.name} ({self.id}): RPyCXRayNode cannot get gRPC API, XRay not started.")
            raise ConnectionError(f"XRay on node {self.name} (via RPyC) is not started.")

        if not self._node_server_cert_content:
            logger.warning(f"Node {self.name} ({self.id}): RPyC node's server certificate for gRPC not available (was not fetched during RPyC connect).")
            # This indicates an issue, as it should have been fetched if RPyC connect was successful.
            # Or RPyC and gRPC use different certs/ports, which needs specific handling.
            raise ConnectionError(f"Node {self.name}'s server certificate for gRPC mTLS was not obtained.")

        if not self._api:
            logger.info(f"Node {self.name} ({self.id}): RPyC node initializing gRPC XRayAPI to {self.address}:{self.api_port}")
            try:
                self._api = XRayAPI(
                    address=self.address,
                    port=self.api_port,
                    ssl_cert=self._node_server_cert_content.encode(),
                    ssl_target_name=self.address # Or "Gozargah"
                )
                logger.info(f"Node {self.name} ({self.id}): RPyC node's gRPC XRayAPI initialized.")
            except Exception as e:
                logger.error(f"Node {self.name} ({self.id}): RPyC node failed to initialize gRPC XRayAPI: {e}", exc_info=True)
                self._api = None
                raise ConnectionError(f"Failed to initialize gRPC API for RPyC node {self.name}: {e}")
        return self._api


    def get_version(self) -> Optional[str]:
        logger.debug(f"Node {self.name} ({self.id}): RPyC getting XRay version.")
        try:
            return self.remote.fetch_xray_version() # Assuming RPyC service has this method
        except (AttributeError, EOFError, TimeoutError) as e: # Common RPyC errors
            logger.error(f"Node {self.name} ({self.id}): RPyC error getting version: {e}", exc_info=True)
            self.disconnect() # Disconnect on RPyC error
            return None


    def _prepare_config(self, config: XRayConfig) -> XRayConfig:
        # Same as ReSTXRayNode, assuming config prep is identical if panel sends full config
        logger.debug(f"Node {self.name} ({self.id}): RPyC preparing XRay config.")
        # In RPyC, it might be more common to send structured data rather than JSON strings,
        # or the RPyC service on the node handles JSON string directly.
        # This method inlines certs from local files for the panel.
        for inbound in config.get("inbounds", []):
            stream_settings = inbound.get("streamSettings") or {}
            security_settings_options = ["tlsSettings", "realitySettings", "xtlsSettings"]
            for settings_key in security_settings_options:
                security_settings = stream_settings.get(settings_key)
                if security_settings and "certificates" in security_settings:
                    for certificate_obj in security_settings["certificates"]:
                        if certificate_obj.get("certificateFile"):
                            cert_file_path = certificate_obj['certificateFile']
                            try:
                                with open(cert_file_path, 'r') as f:
                                    certificate_obj['certificate'] = [line.strip() for line in f.readlines()]
                                del certificate_obj['certificateFile']
                            except Exception as e:
                                logger.error(f"Node {self.name} ({self.id}): RPyC error reading certificateFile {cert_file_path}: {e}")
                        if certificate_obj.get("keyFile"):
                            key_file_path = certificate_obj['keyFile']
                            try:
                                with open(key_file_path, 'r') as f:
                                    certificate_obj['key'] = [line.strip() for line in f.readlines()]
                                del certificate_obj['keyFile']
                            except Exception as e:
                                logger.error(f"Node {self.name} ({self.id}): RPyC error reading keyFile {key_file_path}: {e}")
        return config


    def start(self, config: XRayConfig):
        logger.info(f"Node {self.name} ({self.id}): RPyC attempting to start XRay core.")
        if not self.connected:
            self.connect()

        prepared_config = self._prepare_config(config)
        prepared_config_dict = prepared_config.as_dict()
        json_config_str = py_json.dumps(prepared_config_dict)

        try:
            self.remote.start(json_config_str) # Call RPyC service's start method
            self.started = True
            logger.info(f"Node {self.name} ({self.id}): RPyC XRay core started successfully.")

            # Initialize gRPC API if used
            try:
                if self.api_port: _ = self.api # Access to initialize if needed
            except ConnectionError as e_grpc:
                logger.warning(f"Node {self.name} ({self.id}): RPyC XRay started, but gRPC API init failed: {e_grpc}")

        except Exception as e: # Catch RPyC call errors
            logger.error(f"Node {self.name} ({self.id}): RPyC error starting XRay: {e}", exc_info=True)
            self.started = False
            raise NodeAPIError(0, f"RPyC start failed: {e}")


    def stop(self):
        logger.info(f"Node {self.name} ({self.id}): RPyC attempting to stop XRay core.")
        if not self.connected:
            self.connect()
        try:
            self.remote.stop() # Call RPyC service's stop method
            logger.info(f"Node {self.name} ({self.id}): RPyC XRay core stopped successfully.")
        except Exception as e:
            logger.error(f"Node {self.name} ({self.id}): RPyC error stopping XRay: {e}", exc_info=True)
            # Still update local state
        finally:
            self.started = False
            self._api = None


    def restart(self, config: XRayConfig):
        logger.info(f"Node {self.name} ({self.id}): RPyC attempting to restart XRay core.")
        if not self.connected:
            self.connect()

        prepared_config = self._prepare_config(config)
        prepared_config_dict = prepared_config.as_dict()
        json_config_str = py_json.dumps(prepared_config_dict)

        try:
            self.remote.restart(json_config_str) # Call RPyC service's restart method
            self.started = True
            logger.info(f"Node {self.name} ({self.id}): RPyC XRay core restarted successfully.")

            self._api = None # Force re-init of gRPC if used
            try:
                if self.api_port: _ = self.api
            except ConnectionError as e_grpc:
                logger.warning(f"Node {self.name} ({self.id}): RPyC XRay restarted, but gRPC API init failed: {e_grpc}")

        except Exception as e:
            logger.error(f"Node {self.name} ({self.id}): RPyC error restarting XRay: {e}", exc_info=True)
            self.started = False # Unsure of state after failed restart
            raise NodeAPIError(0, f"RPyC restart failed: {e}")


    @contextmanager
    def get_logs(self) -> deque:
        # RPyC log fetching logic from your original code
        logger.debug(f"Node {self.name} ({self.id}): RPyC get_logs called.")
        if not self.connected:
            raise ConnectionError(f"RPyC node {self.name} is not connected")

        # Initialize __curr_logs if it doesn't exist
        if not hasattr(self, '_RPyCXRayNode__curr_logs'): # Name mangling for private-like attribute
            self._RPyCXRayNode__curr_logs = 0
        if not hasattr(self, '_RPyCXRayNode__bgsrv'):
            self._RPyCXRayNode__bgsrv = None # Initialize to None

        buffer = deque(maxlen=100)
        active_log_subscription = None # To hold the RPyC netref for logs

        try:
            if self._RPyCXRayNode__curr_logs <= 0:
                self._RPyCXRayNode__curr_logs = 1
                if not self._RPyCXRayNode__bgsrv or not self._RPyCXRayNode__bgsrv._active:
                    logger.debug(f"Node {self.name} ({self.id}): RPyC starting BgServingThread.")
                    self._RPyCXRayNode__bgsrv = rpyc.BgServingThread(self.connection)
            else:
                if not self._RPyCXRayNode__bgsrv or not self._RPyCXRayNode__bgsrv._active: # Check if thread died
                    logger.debug(f"Node {self.name} ({self.id}): RPyC re-starting BgServingThread.")
                    self._RPyCXRayNode__bgsrv = rpyc.BgServingThread(self.connection)
                self._RPyCXRayNode__curr_logs += 1

            logger.debug(f"Node {self.name} ({self.id}): RPyC fetching logs. Current log users: {self._RPyCXRayNode__curr_logs}")
            active_log_subscription = self.remote.fetch_logs(buffer.append) # Assuming fetch_logs returns a subscription object
            yield buffer

        finally:
            logger.debug(f"Node {self.name} ({self.id}): RPyC get_logs finally block. Current log users before dec: {self._RPyCXRayNode__curr_logs}")
            if self._RPyCXRayNode__curr_logs > 0 : # Should always be true if we entered try
                 self._RPyCXRayNode__curr_logs -= 1

            if active_log_subscription and hasattr(active_log_subscription, 'stop'):
                try:
                    logger.debug(f"Node {self.name} ({self.id}): RPyC stopping log subscription.")
                    active_log_subscription.stop()
                except Exception as e_log_stop:
                    logger.error(f"Node {self.name} ({self.id}): RPyC error stopping log subscription: {e_log_stop}")

            if self._RPyCXRayNode__curr_logs <= 0:
                if self._RPyCXRayNode__bgsrv and self._RPyCXRayNode__bgsrv._active:
                    logger.debug(f"Node {self.name} ({self.id}): RPyC stopping BgServingThread as no more log users.")
                    self._RPyCXRayNode__bgsrv.stop()
                self._RPyCXRayNode__bgsrv = None # Clear it


    def on_start(self, func: callable) -> callable:
        self._service.add_startup_func(func)
        return func

    def on_stop(self, func: callable) -> callable:
        self._service.add_shutdown_func(func)
        return func


class XRayNode:
    """
    Factory class to create either a ReSTXRayNode or RPyCXRayNode.
    The detection logic here is crucial.
    """
    def __new__(cls, # cls is conventional for __new__
                # --- These parameters need to be passed from the calling code ---
                node_id: int,       # Unique ID for the node
                name: str,          # User-friendly name for the node
                # ----------------------------------------------------------------
                address: str,       # IP or hostname of the node
                port: int,          # Primary connection port (ReST or RPyC)
                api_port: int,      # XRay's gRPC API port (for direct XRay interaction)
                ssl_key_content: str,  # Panel's client private key (string content)
                ssl_cert_content: str, # Panel's client certificate (string content)
                usage_coefficient: float = 1.0,
                node_type_preference: Optional[str] = None # e.g., "rest" or "rpyc" to override detection
                ) -> object: # Returns an instance of ReSTXRayNode or RPyCXRayNode

        logger.info(f"XRayNode Factory: Creating node object for '{name}' ({node_id}) at {address}:{port}. Type preference: {node_type_preference}")

        # If a preference is given, use it.
        if node_type_preference == "rest":
            logger.info(f"XRayNode Factory: Forcing ReSTXRayNode for '{name}' due to preference.")
            return ReSTXRayNode(
                node_id=node_id, name=name, address=address, port=port, api_port=api_port,
                ssl_key_content=ssl_key_content, ssl_cert_content=ssl_cert_content,
                usage_coefficient=usage_coefficient
            )
        elif node_type_preference == "rpyc":
            logger.info(f"XRayNode Factory: Forcing RPyCXRayNode for '{name}' due to preference.")
            return RPyCXRayNode(
                node_id=node_id, name=name, address=address, port=port, api_port=api_port,
                ssl_key_content=ssl_key_content, ssl_cert_content=ssl_cert_content,
                usage_coefficient=usage_coefficient
            )

        # Attempt to detect ReST (HTTPS) node. This detection is basic.
        # A ReST node is expected to be an HTTPS server on `port`.
        # An RPyC SSL node will also have an SSL server on `port`.
        # The key difference is how they respond to an initial SSL handshake and subsequent data.
        # A simple socket connection and sending HTTP HEAD won't work for an HTTPS endpoint
        # without an SSL handshake first.

        # For now, to ensure your ReST logic is tested (as previous logs indicated it was the target):
        logger.warning(f"XRayNode Factory: Detection logic is basic. Forcing ReSTXRayNode for '{name}' "
                       f"({address}:{port}) for current testing phase. "
                       f"Set 'node_type_preference' for explicit control.")
        return ReSTXRayNode(
            node_id=node_id, name=name, address=address, port=port, api_port=api_port,
            ssl_key_content=ssl_key_content, ssl_cert_content=ssl_cert_content,
            usage_coefficient=usage_coefficient
        )

        # --- More robust (but still imperfect) detection placeholder ---
        # try:
        #     logger.debug(f"XRayNode Factory: Attempting ReST (HTTPS) detection for '{name}' ({address}:{port})")
        #     # Try a minimal SSL connection and see if it looks like HTTP after
        #     context = ssl.create_default_context(cafile=PANEL_TRUSTED_CA_PATH) # To verify node server cert
        #     context.load_cert_chain(certfile=string_to_temp_file(ssl_cert_content).name, # Panel's client cert for mTLS
        #                             keyfile=string_to_temp_file(ssl_key_content).name)
        #     context.check_hostname = True # Should verify hostname if cert has SAN
        #     # context.minimum_version = ssl.TLSVersion.TLSv1_2 # Example: Enforce min TLS version

        #     with socket.create_connection((address, port), timeout=2) as sock:
        #         with context.wrap_socket(sock, server_hostname=address) as ssock:
        #             logger.debug(f"XRayNode Factory: SSL handshake successful with {address}:{port}. Peer cert: {ssock.getpeercert()}")
        #             # For a ReST API, we might expect an HTTP response if we send something.
        #             # For RPyC, it might behave differently after handshake.
        #             # This is still tricky. Sending HTTP data might be necessary.
        #             ssock.sendall(b"GET /ping HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % address.encode())
        #             response_peek = ssock.recv(1024)
        #             logger.debug(f"XRayNode Factory: Response peek from {address}:{port} - {response_peek[:60]}")
        #             if response_peek.startswith(b"HTTP/"):
        #                 logger.info(f"XRayNode Factory: Detected ReST (HTTPS) for '{name}' ({address}:{port}).")
        #                 # Cleanup temp files for certs used in detection if they were created just for this
        #                 return ReSTXRayNode(
        #                     node_id=node_id, name=name, address=address, port=port, api_port=api_port,
        #                     ssl_key_content=ssl_key_content, ssl_cert_content=ssl_cert_content,
        #                     usage_coefficient=usage_coefficient
        #                 )
        #             else:
        #                 logger.info(f"XRayNode Factory: Non-HTTP response from {address}:{port}, assuming RPyC for '{name}'.")
        #                 raise ValueError("Potentially RPyC or other protocol") # Fall through to RPyC
        # except Exception as e_rest_detect:
        #     logger.warning(f"XRayNode Factory: ReST (HTTPS) detection for '{name}' ({address}:{port}) failed or indicated not ReST: {e_rest_detect}. Trying RPyC.")
        #     return RPyCXRayNode(
        #         node_id=node_id, name=name, address=address, port=port, api_port=api_port,
        #         ssl_key_content=ssl_key_content, ssl_cert_content=ssl_cert_content,
        #         usage_coefficient=usage_coefficient
        #     )