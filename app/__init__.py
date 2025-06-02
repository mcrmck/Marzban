# Marzban/app/__init__.py
import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from .version import __version__
from config import ALLOWED_ORIGINS, DOCS, XRAY_SUBSCRIPTION_PATH, DEBUG, HOME_PAGE_TEMPLATE

# Configure logging
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,  # Set default level to INFO
        format='%(levelname)s:%(name)s:%(message)s'
    )

# Reduce verbosity of specific loggers
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

# Set app logger level
logger = logging.getLogger("marzban.app_init")
logger.setLevel(logging.INFO if not DEBUG else logging.DEBUG)

app = FastAPI(
    title="MarzbanAPI",
    description="Unified GUI Censorship Resistant Solution Powered by Xray",
    version=__version__,
    docs_url="/docs" if DOCS else None,
    redoc_url="/redoc" if DOCS else None,
    debug=DEBUG
)

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

# --- Include API Routers ---
try:
    from .routers import api_router as main_api_aggregator_router
    # All routes from main_api_aggregator_router will now be prefixed with /api
    app.include_router(main_api_aggregator_router, prefix="/api")
    logger.info("APP_INIT: Successfully included main_api_aggregator_router under /api prefix.")
except ImportError as e:
    logger.error(f"APP_INIT: FAILED to import or include main_api_aggregator_router: {e}", exc_info=True)

# --- Include Root/Homepage Router ---
try:
    from .routers.core.home import router as home_page_router
    app.include_router(home_page_router, tags=["Homepage"])
    logger.info("APP_INIT: Successfully included home_page_router.")
except ImportError as e:
    logger.error(f"APP_INIT: FAILED to import or include home_page_router: {e}", exc_info=True)

# --- Serve Admin Panel SPA ---
admin_spa_build_dir = os.path.join(os.path.dirname(__file__), "dashboard", "dist_admin")
if os.path.exists(admin_spa_build_dir) and os.path.isfile(os.path.join(admin_spa_build_dir, "index.html")):
    app.mount("/admin", StaticFiles(directory=admin_spa_build_dir, html=True), name="admin-spa")
    logger.info(f"Admin Panel SPA mounted at /admin from {admin_spa_build_dir}")
else:
    logger.warning(
        f"Admin Panel SPA build directory ({admin_spa_build_dir}) or its index.html not found. "
        f"Admin panel will not be served. Searched for index.html at: {os.path.join(admin_spa_build_dir, 'index.html')}"
    )

# --- Serve Client Portal SPA ---
portal_spa_build_dir = os.path.join(os.path.dirname(__file__), "dashboard", "dist_portal")
if os.path.exists(portal_spa_build_dir) and os.path.isfile(os.path.join(portal_spa_build_dir, "index.html")):
    app.mount("/portal", StaticFiles(directory=portal_spa_build_dir, html=True), name="portal-spa")
    logger.info(f"Client Portal SPA mounted at /portal from {portal_spa_build_dir}")
else:
    logger.warning(
        f"Client Portal SPA build directory ({portal_spa_build_dir}) or its index.html not found. "
        f"Client portal will not be served. Searched for index.html at: {os.path.join(portal_spa_build_dir, 'index.html')}"
    )

def use_route_names_as_operation_ids(current_app: FastAPI):
    for route in current_app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name
use_route_names_as_operation_ids(app)

@app.on_event("startup")
def on_app_init_startup():
    # VERY FIRST LINES for unconditional logging:
    logger.error("APP_INIT_STARTUP_EVENT: CALLED (logger.error)")
    try:
        if XRAY_SUBSCRIPTION_PATH:
            paths = [f"{r.path}/" for r in app.routes if hasattr(r, 'path')]
            paths.append("/api/") # Ensure this is relevant to your routing
            if f"/{XRAY_SUBSCRIPTION_PATH}/" in paths:
                logger.warning(f"APP_INIT_STARTUP_EVENT: Route conflict detected for /{XRAY_SUBSCRIPTION_PATH}/")
                # Consider if raising an error here is intended or if logging is sufficient

        if not scheduler.running:
            scheduler.start()
        else:
            logger.info("APP_INIT_STARTUP_EVENT: Scheduler was already running.")
    except Exception as e_init_startup:
        logger.error(f"APP_INIT_STARTUP_EVENT: EXCEPTION: {e_init_startup}", exc_info=True)

@app.on_event("shutdown")
def on_app_init_shutdown():
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