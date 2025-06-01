# Marzban/app/__init__.py
import logging
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from .version import __version__
from config import ALLOWED_ORIGINS, DOCS, XRAY_SUBSCRIPTION_PATH, DEBUG

app = FastAPI(
    title="MarzbanAPI",
    description="Unified GUI Censorship Resistant Solution Powered by Xray",
    version=__version__,
    docs_url="/docs" if DOCS else None,
    redoc_url="/redoc" if DOCS else None,
    debug=DEBUG
)

if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("marzban.app_init")
logger.setLevel(logging.DEBUG)

logger.info(f"APP_INIT: Top of file executing. Version: {__version__}, DEBUG: {DEBUG}")

scheduler = BackgroundScheduler(
    {"apscheduler.job_defaults.max_instances": 20}, timezone="UTC"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    static_portal_path = "app/portal/static"
    app.mount("/client-portal/static", StaticFiles(directory=str(static_portal_path)), name="portal_static")
    logger.info(f"APP_INIT: Mounted portal static files from {static_portal_path}")
except Exception as e:
    logger.error(f"APP_INIT: Could not mount portal static files from '{static_portal_path}': {e}", exc_info=True)

logger.info("APP_INIT: About to import .dashboard")
try:
    from . import dashboard
    logger.info("APP_INIT: Successfully imported .dashboard")
except ImportError as e:
    logger.error(f"APP_INIT: FAILED to import .dashboard: {e}", exc_info=True)

try:
    from .routers import api_router
    app.include_router(api_router)
    logger.info("APP_INIT: Successfully imported and included api_router.")
except ImportError as e:
    logger.error(f"APP_INIT: FAILED to import or include api_router: {e}", exc_info=True)

def use_route_names_as_operation_ids(current_app: FastAPI):
    for route in current_app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name
use_route_names_as_operation_ids(app)

@app.on_event("startup")
def on_app_init_startup():
    # VERY FIRST LINES for unconditional logging:
    print("APP_INIT_STARTUP_EVENT: CALLED", flush=True)
    logger.error("APP_INIT_STARTUP_EVENT: CALLED (logger.error)")
    try:
        logger.debug("APP_INIT_STARTUP_EVENT: Inside try block.")
        if XRAY_SUBSCRIPTION_PATH:
            paths = [f"{r.path}/" for r in app.routes if hasattr(r, 'path')]
            paths.append("/api/") # Ensure this is relevant to your routing
            if f"/{XRAY_SUBSCRIPTION_PATH}/" in paths:
                logger.warning(f"APP_INIT_STARTUP_EVENT: Route conflict detected for /{XRAY_SUBSCRIPTION_PATH}/")
                # Consider if raising an error here is intended or if logging is sufficient

        if not scheduler.running:
            scheduler.start()
            logger.info("APP_INIT_STARTUP_EVENT: Scheduler started.")
        else:
            logger.info("APP_INIT_STARTUP_EVENT: Scheduler was already running.")
        logger.info("APP_INIT_STARTUP_EVENT: Logic finished successfully.")
    except Exception as e_init_startup:
        print(f"APP_INIT_STARTUP_EVENT: EXCEPTION: {e_init_startup}", flush=True)
        logger.error(f"APP_INIT_STARTUP_EVENT: EXCEPTION: {e_init_startup}", exc_info=True)

@app.on_event("shutdown")
def on_app_init_shutdown():
    print("APP_INIT_SHUTDOWN_EVENT: CALLED", flush=True)
    logger.error("APP_INIT_SHUTDOWN_EVENT: CALLED (logger.error)")
    if scheduler.running:
      scheduler.shutdown()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = {}
    for error in exc.errors():
        loc_key = error["loc"][-1] if error["loc"] and isinstance(error["loc"], (list, tuple)) else "unknown_field"
        details[loc_key] = error.get("msg")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": details}),
    )
logger.debug("APP_INIT: End of file reached")