from decouple import config
from dotenv import load_dotenv
import os

load_dotenv()

SERVICE_HOST = config("SERVICE_HOST", default="0.0.0.0")
SERVICE_PORT = config('SERVICE_PORT', cast=int, default=6001)

XRAY_API_HOST = config("XRAY_API_HOST", default="0.0.0.0")
XRAY_API_PORT = config('XRAY_API_PORT', cast=int, default=62051)
XRAY_EXECUTABLE_PATH = config("XRAY_EXECUTABLE_PATH", default="/usr/local/bin/xray")
XRAY_ASSETS_PATH = config("XRAY_ASSETS_PATH", default="/usr/local/share/xray")

SSL_CERT_FILE = config("SSL_CERT_FILE", default="/etc/marzban-node/certs/server.crt")
SSL_KEY_FILE = config("SSL_KEY_FILE", default="/etc/marzban-node/certs/server.key")
SSL_CLIENT_CERT_FILE = config("SSL_CLIENT_CERT_FILE", default="/etc/marzban-node/certs/ca.crt")

DEBUG = config("DEBUG", cast=bool, default=False)

SERVICE_PROTOCOL = config('SERVICE_PROTOCOL', cast=str, default='rest')

INBOUNDS = config("INBOUNDS", cast=lambda v: [x.strip() for x in v.split(',')] if v else [], default="")

SSL_VERIFY = config("SSL_VERIFY", cast=bool, default=True)
SSL_CERT_REQS = config("SSL_CERT_REQS", default="CERT_REQUIRED")

LOG_LEVEL = config("LOG_LEVEL", default="INFO")