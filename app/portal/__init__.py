from fastapi import FastAPI
from .routers import main, auth

def mount_portal_routers(app: FastAPI):
    """Mount the client portal routers in the FastAPI application."""
    app.include_router(main.router)
    app.include_router(auth.router)