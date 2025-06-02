import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

def setup_client_portal_static_files(app: FastAPI):
    """Setup static file serving for the client portal React app."""
    # Path to the directory where the React app's static files are built
    base_dir = Path(__file__).parent.parent
    build_dir = base_dir / "dashboard" / "build"

    # Mount the main application with html=True to handle SPA routing
    if build_dir.is_dir() and (build_dir / "index.html").exists():
        # Mount the portal app
        app.mount("/portal", StaticFiles(directory=str(build_dir), html=True), name="portal-static")
        print(f"Successfully mounted /portal to {build_dir}")
    else:
        print(f"Warning: Build directory or index.html not found at {build_dir}")