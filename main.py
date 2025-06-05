# Marzban/main.py

import logging
import os
from contextlib import asynccontextmanager # Keep this for the main_lifespan definition
import uvicorn
from fastapi import FastAPI # For type hinting


try:
    from app import app # This is the central FastAPI instance
except ImportError as e:
    raise

from config import (DEBUG, UVICORN_HOST, UVICORN_PORT, UVICORN_SSL_CERTFILE,
                    UVICORN_SSL_KEYFILE, UVICORN_SSL_CA_TYPE, UVICORN_UDS)


logger = logging.getLogger("marzban.main")
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, force=True, format='%(levelname)s:%(name)s:%(message)s')
logger.setLevel(logging.DEBUG)


# Lifespan function definition (remains defined but won't be attached for this test)
@asynccontextmanager
async def main_lifespan(fastapi_app: FastAPI):
    yield
    logger.info("Main lifespan: Custom shutdown tasks would run here.")


# Cert Validation and DB Table Creation can remain as placeholders
def validate_cert_and_key(cert_file_path, key_file_path, ca_type):
    pass
try:
    logger.info("MAIN.PY: DB creation logic present but might be effectively skipped if Base/engine not fully available due to other commented out lifespan tasks.")
except Exception as e:
    logger.error(f"Error during DB table creation (main.py): {e}", exc_info=True)


if __name__ == "__main__":
    bind_args = {}
    # --- Ensure your Uvicorn bind_args setup is complete here ---
    current_ca_type = UVICORN_SSL_CA_TYPE.lower() if UVICORN_SSL_CA_TYPE else "public"
    if current_ca_type not in ["public", "private"]:
        current_ca_type = "public"

    if UVICORN_SSL_CERTFILE and UVICORN_SSL_KEYFILE:
        try:
            bind_args['ssl_certfile'] = UVICORN_SSL_CERTFILE
            bind_args['ssl_keyfile'] = UVICORN_SSL_KEYFILE
        except ValueError as e:
            logger.error(f"SSL Configuration Error: {e}. Marzban will attempt to start without HTTPS.")
            if 'ssl_certfile' in bind_args: del bind_args['ssl_certfile']
            if 'ssl_keyfile' in bind_args: del bind_args['ssl_keyfile']

    if UVICORN_UDS:
        bind_args['uds'] = UVICORN_UDS
    else:
        bind_args['host'] = UVICORN_HOST if UVICORN_HOST else '0.0.0.0'
        bind_args['port'] = UVICORN_PORT if UVICORN_PORT else 8000

    log_level_uvicorn = "info"

    try:
        uvicorn.run(
            "app:app", # Points to Marzban/app/__init__.py's 'app' instance
            reload=DEBUG,
            log_level=log_level_uvicorn,
            workers=1,
            **bind_args # Pass all other computed bind_args (host, port, ssl, uds)
        )
    except Exception as e:
        logger.critical(f"Failed to start Uvicorn: {e}", exc_info=True)