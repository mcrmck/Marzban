# Marzban/app/dashboard/__init__.py
import atexit
import os
import subprocess # Still imported, though run_dev might not be called by startup
import logging
from pathlib import Path

# Ensure 'app' is the shared FastAPI instance and DEBUG, DASHBOARD_PATH are from config
try:
    from app import app
    from config import DEBUG, VITE_BASE_API, DASHBOARD_PATH # DEBUG is not used by this startup logic anymore
    # VITE_BASE_API is also not used if run_dev isn't called
except ImportError as e:
    # Fallback for parsing if imports fail, actual functionality would be broken
    class DummyApp: pass
    app = DummyApp()
    DEBUG = False # Default
    VITE_BASE_API = None
    DASHBOARD_PATH = "/dashboard" # Default fallback

from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("marzban.dashboard")
logger.setLevel(logging.DEBUG) # Ensure visibility

base_dir = Path(__file__).parent
build_dir = base_dir / 'build' # This is where `npm run build` places assets
statics_dir = build_dir / 'statics'

# The run_dev function can remain if you want to call it manually for other purposes,
# but it won't be called by the dashboard's startup sequence anymore.
def run_dev():
    print("DASHBOARD_RUN_DEV: CALLED (but not from startup in 'always-build' mode)", flush=True)
    logger.error("DASHBOARD_RUN_DEV: CALLED (but not from startup in 'always-build' mode) (logger.error)")
    try:
        logger.info(f"Dashboard: Attempting to start in development mode (DASHBOARD_PATH: {DASHBOARD_PATH})...")
        if not DASHBOARD_PATH or not isinstance(DASHBOARD_PATH, str):
            logger.error("run_dev: DASHBOARD_PATH is not configured correctly.")
            return False

        command = ['npm', 'run', 'dev', '--', '--host', '0.0.0.0', '--clearScreen', 'false', '--base', os.path.join(DASHBOARD_PATH, '')]
        logger.debug(f"run_dev: Executing command: {' '.join(command)} in {base_dir}")

        env = {**os.environ}
        if VITE_BASE_API:
            env['VITE_BASE_API'] = VITE_BASE_API

        proc = subprocess.Popen(command, env=env, cwd=str(base_dir))
        atexit.register(proc.terminate)
        logger.info("run_dev: Development server process initiated.")
        return True
    except FileNotFoundError:
        logger.error("run_dev: 'npm' command not found.")
        return False
    except Exception as e:
        logger.error(f"run_dev: Error starting dashboard: {e}", exc_info=True)
        return False

def mount_static_files():
    print("DASHBOARD_MOUNT_STATIC_FILES: CALLED", flush=True)
    logger.error("DASHBOARD_MOUNT_STATIC_FILES: CALLED (logger.error)")
    try:
        logger.info(f"Dashboard: Mounting static files (DASHBOARD_PATH: {DASHBOARD_PATH}) from {build_dir}...")
        if not DASHBOARD_PATH or not isinstance(DASHBOARD_PATH, str):
            logger.error("mount_static_files: DASHBOARD_PATH is not configured correctly.")
            return False
        if not build_dir.is_dir():
            logger.error(f"mount_static_files: Build directory not found at {build_dir}. Ensure 'npm run build' has run and assets are copied correctly in Dockerfile.")
            return False
        index_html_path = build_dir / 'index.html'
        if not index_html_path.exists():
            logger.error(f"mount_static_files: index.html not found in {build_dir}.")
            return False

        # Mount the main dashboard application - this will serve both index.html and statics
        app.mount(
            DASHBOARD_PATH,
            StaticFiles(directory=str(build_dir), html=True), # html=True serves index.html for subpaths
            name="dashboard"
        )
        logger.info(f"mount_static_files: Mounted dashboard at {DASHBOARD_PATH} from {build_dir}")

        return True
    except Exception as e:
        logger.error(f"mount_static_files: Error: {e}", exc_info=True)
        return False

@app.on_event("startup")
def dashboard_startup_event():
    print("DASHBOARD_STARTUP_EVENT: CALLED (Always Build Version)", flush=True)
    logger.error("DASHBOARD_STARTUP_EVENT: CALLED (Always Build Version) (logger.error)")
    try:
        logger.info("DASHBOARD_STARTUP_EVENT: Always calling mount_static_files().")
        if not mount_static_files():
            logger.error("DASHBOARD_STARTUP_EVENT: mount_static_files() reported failure.")
        else:
            logger.info("DASHBOARD_STARTUP_EVENT: mount_static_files() presumably succeeded.")
        logger.info("DASHBOARD_STARTUP_EVENT: Logic finished.")
    except Exception as e_dashboard_startup:
        print(f"DASHBOARD_STARTUP_EVENT: EXCEPTION: {e_dashboard_startup}", flush=True)
        logger.error(f"DASHBOARD_STARTUP_EVENT: EXCEPTION: {e_dashboard_startup}", exc_info=True)

logger.info("DASHBOARD_INIT: End of file reached (Always Build Version setup).")