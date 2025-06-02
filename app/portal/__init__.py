from fastapi import FastAPI
from .static import setup_client_portal_static_files

def mount_portal_routers(app: FastAPI):
    """Mount the client portal routers in the FastAPI application."""
    setup_client_portal_static_files(app)