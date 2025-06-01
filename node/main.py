import os
import ssl
import logging
import sys
import traceback

import uvicorn
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer

import rest_service
import rpyc_service
from certificate import generate_certificate, generate_ca_certificate
from config import (SERVICE_HOST, SERVICE_PORT, SERVICE_PROTOCOL,
                    SSL_CERT_FILE, SSL_KEY_FILE, SSL_CLIENT_CERT_FILE)
from logger import logger

# Configure detailed SSL logging
logging.getLogger('uvicorn').setLevel(logging.DEBUG)
logging.getLogger('uvicorn.access').setLevel(logging.DEBUG)
logging.getLogger('uvicorn.error').setLevel(logging.DEBUG)
logging.getLogger('uvicorn.ssl').setLevel(logging.DEBUG)

def verify_ssl_files():
    """Verify SSL files and log their details"""
    logger.debug(f"Checking SSL files:")
    logger.debug(f"SSL_CERT_FILE: {SSL_CERT_FILE} (exists: {os.path.isfile(SSL_CERT_FILE)})")
    logger.debug(f"SSL_KEY_FILE: {SSL_KEY_FILE} (exists: {os.path.isfile(SSL_KEY_FILE)})")
    logger.debug(f"SSL_CLIENT_CERT_FILE: {SSL_CLIENT_CERT_FILE} (exists: {os.path.isfile(SSL_CLIENT_CERT_FILE) if SSL_CLIENT_CERT_FILE else False})")

    if os.path.isfile(SSL_CERT_FILE):
        try:
            with open(SSL_CERT_FILE, 'r') as f:
                cert_content = f.read()
                logger.debug(f"Certificate content (first 100 chars): {cert_content[:100]}")
                # Add certificate chain verification
                try:
                    context = ssl.create_default_context()
                    context.load_verify_locations(cafile=SSL_CLIENT_CERT_FILE)
                    context.load_cert_chain(SSL_CERT_FILE, SSL_KEY_FILE)
                    logger.info("SSL certificate chain verification successful")
                except Exception as e:
                    logger.error(f"SSL certificate chain verification failed: {e}")
        except Exception as e:
            logger.error(f"Error reading certificate file: {e}")

def generate_ssl_files():
    logger.info("Generating SSL files...")

    # First generate CA certificate
    ca_pems = generate_ca_certificate()
    ca_cert_file = os.path.join(os.path.dirname(SSL_CERT_FILE), 'ca.crt')
    ca_key_file = os.path.join(os.path.dirname(SSL_CERT_FILE), 'ca.key')

    try:
        # Write CA certificate and key
        with open(ca_cert_file, 'w') as f:
            f.write(ca_pems['cert'])
        logger.info(f"CA certificate written to {ca_cert_file}")

        with open(ca_key_file, 'w') as f:
            f.write(ca_pems['key'])
        logger.info(f"CA key written to {ca_key_file}")

        # Generate node certificate signed by CA
        node_pems = generate_certificate(ca_pems['cert'], ca_pems['key'])

        with open(SSL_KEY_FILE, 'w') as f:
            f.write(node_pems['key'])
        logger.info(f"SSL key written to {SSL_KEY_FILE}")

        with open(SSL_CERT_FILE, 'w') as f:
            f.write(node_pems['cert'])
        logger.info(f"SSL certificate written to {SSL_CERT_FILE}")

    except Exception as e:
        logger.error(f"Error writing SSL files: {e}")
        raise

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to catch unhandled exceptions"""
    logger.error("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
    logger.error("Stack trace:", exc_info=True)
    logger.error(f"Exception type: {exc_type.__name__}")
    logger.error(f"Exception value: {exc_value}")
    logger.error("Traceback:")
    for line in traceback.format_tb(exc_traceback):
        logger.error(line.strip())

if __name__ == "__main__":
    # Set up global exception handler
    sys.excepthook = handle_exception

    logger.info("Starting node service...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Environment variables: {dict(os.environ)}")

    verify_ssl_files()

    if not all((os.path.isfile(SSL_CERT_FILE),
                os.path.isfile(SSL_KEY_FILE))):
        logger.info("SSL files not found, generating new ones...")
        generate_ssl_files()

    if not SSL_CLIENT_CERT_FILE:
        logger.warning(
            "You are running node without SSL_CLIENT_CERT_FILE, be aware that everyone can connect to this node and this isn't secure!")

    if SSL_CLIENT_CERT_FILE and not os.path.isfile(SSL_CLIENT_CERT_FILE):
        logger.error("Client's certificate file specified on SSL_CLIENT_CERT_FILE is missing")
        exit(0)

    if SERVICE_PROTOCOL == 'rpyc':
        logger.info("Starting RPyC service...")
        try:
            authenticator = SSLAuthenticator(keyfile=SSL_KEY_FILE,
                                             certfile=SSL_CERT_FILE,
                                             ca_certs=SSL_CLIENT_CERT_FILE or None)
            thread = ThreadedServer(rpyc_service.XrayService(),
                                    port=SERVICE_PORT,
                                    authenticator=authenticator)
            logger.info(f"Node service running on :{SERVICE_PORT}")
            thread.start()
        except Exception as e:
            logger.error(f"Failed to start RPyC service: {e}")
            logger.error("Stack trace:", exc_info=True)
            raise

    elif SERVICE_PROTOCOL == 'rest':
        if not SSL_CLIENT_CERT_FILE:
            logger.error("SSL_CLIENT_CERT_FILE is required for rest service.")
            exit(0)

        logger.info(f"Starting REST service on :{SERVICE_PORT}")
        try:
            uvicorn.run(
                rest_service.app,
                host=SERVICE_HOST,
                port=SERVICE_PORT,
                ssl_keyfile=SSL_KEY_FILE,
                ssl_certfile=SSL_CERT_FILE,
                ssl_ca_certs=SSL_CLIENT_CERT_FILE,
                ssl_cert_reqs=2,
                log_level="debug"
            )
        except Exception as e:
            logger.error(f"Error starting REST service: {e}")
            logger.error("Stack trace:", exc_info=True)
            raise

    else:
        logger.error("SERVICE_PROTOCOL is not any of (rpyc, rest).")
        exit(0)