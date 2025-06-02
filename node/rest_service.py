import asyncio
import json
import time
import traceback
from uuid import UUID, uuid4

from fastapi import (APIRouter, Body, FastAPI, HTTPException, Request,
                     WebSocket, status)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from config import (XRAY_ASSETS_PATH, XRAY_EXECUTABLE_PATH,
                   SSL_CERT_FILE, SSL_KEY_FILE, SSL_CLIENT_CERT_FILE)
from logger import logger
from xray import XRayConfig, XRayCore

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    logger.info("REST service starting up...")
    logger.info(f"XRay executable path: {XRAY_EXECUTABLE_PATH}")
    logger.info(f"XRay assets path: {XRAY_ASSETS_PATH}")
    # Add SSL context verification
    try:
        import ssl
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(SSL_CERT_FILE, SSL_KEY_FILE)
        context.load_verify_locations(cafile=SSL_CLIENT_CERT_FILE)
        context.verify_mode = ssl.CERT_REQUIRED
        logger.info("SSL context verification successful")
        logger.info(f"SSL context verify mode: {context.verify_mode}")
        logger.info(f"SSL context check hostname: {context.check_hostname}")
        logger.info(f"SSL context options: {context.options}")
    except Exception as e:
        logger.error(f"SSL context verification failed: {e}")
        logger.error("Stack trace:", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("REST service shutting down...")
    logger.info("Stack trace:", exc_info=True)

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    logger.error("Stack trace:", exc_info=True)
    details = {}
    for error in exc.errors():
        details[error["loc"][-1]] = error.get("msg")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": details}),
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    logger.error("Stack trace:", exc_info=True)
    # Add more detailed error information
    error_details = {
        "error": str(exc),
        "type": type(exc).__name__,
        "traceback": traceback.format_exc()
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_details,
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"HTTP {request.method} {request.url.path} from {request.client.host}")
    try:
        response = await call_next(request)
        logger.info(f"HTTP {request.method} {request.url.path} -> {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"HTTP {request.method} {request.url.path} failed: {e}")
        logger.error("Stack trace:", exc_info=True)
        raise

class Service(object):
    def __init__(self):
        logger.info("Initializing Service...")
        self.router = APIRouter()

        self.connected = False
        self.client_ip = None
        self.session_id = None
        logger.info(f"Initializing XRayCore with executable_path={XRAY_EXECUTABLE_PATH}, assets_path={XRAY_ASSETS_PATH}")
        self.core = XRayCore(
            executable_path=XRAY_EXECUTABLE_PATH,
            assets_path=XRAY_ASSETS_PATH
        )
        self.core_version = self.core.get_version()
        logger.info(f"XRayCore version: {self.core_version}")
        self.config = None

        self.router.add_api_route("/", self.base, methods=["POST", "GET"])
        self.router.add_api_route("/ping", self.ping, methods=["POST"])
        self.router.add_api_route("/connect", self.connect, methods=["POST"])
        self.router.add_api_route("/disconnect", self.disconnect, methods=["POST"])
        self.router.add_api_route("/start", self.start, methods=["POST"])
        self.router.add_api_route("/stop", self.stop, methods=["POST"])
        self.router.add_api_route("/restart", self.restart, methods=["POST"])

        self.router.add_websocket_route("/logs", self.logs)
        logger.info("Service initialization complete")

    def match_session_id(self, session_id: UUID):
        logger.debug(f"Checking session ID: {session_id} against current: {self.session_id}")
        if session_id != self.session_id:
            logger.warning(f"Session ID mismatch: {session_id} != {self.session_id}")
            raise HTTPException(
                status_code=403,
                detail="Session ID mismatch."
            )
        return True

    def response(self, **kwargs):
        return {
            "connected": self.connected,
            "started": self.core.started,
            "core_version": self.core_version,
            **kwargs
        }

    def base(self):
        logger.debug("Base endpoint called")
        return self.response()

    def connect(self, request: Request):
        logger.info(f"Connect request from {request.client.host}")
        self.session_id = uuid4()
        self.client_ip = request.client.host

        if self.connected:
            logger.warning(
                f'New connection from {self.client_ip}, Core control access was taken away from previous client.')
            if self.core.started:
                try:
                    logger.info("Stopping core due to new connection")
                    self.core.stop()
                except RuntimeError as e:
                    logger.error(f"Error stopping core: {e}")
                    logger.error("Stack trace:", exc_info=True)

        self.connected = True
        logger.info(f'{self.client_ip} connected, Session ID = "{self.session_id}".')

        return self.response(
            session_id=self.session_id
        )

    def disconnect(self):
        logger.info(f"Disconnect request received from {self.client_ip}")
        if self.connected:
            logger.info(f'{self.client_ip} disconnected, Session ID = "{self.session_id}".')

        self.session_id = None
        self.client_ip = None
        self.connected = False

        if self.core.started:
            try:
                logger.info("Stopping core due to disconnect")
                self.core.stop()
            except RuntimeError as e:
                logger.error(f"Error stopping core: {e}")
                logger.error("Stack trace:", exc_info=True)

        return self.response()

    def ping(self, session_id: UUID = Body(embed=True)):
        logger.debug(f"Ping request with session ID: {session_id}")
        self.match_session_id(session_id)
        return {}

    def start(self, session_id: UUID = Body(embed=True), config: str = Body(embed=True)):
        logger.info(f"Start request with session ID: {session_id}")
        self.match_session_id(session_id)

        try:
            logger.debug("Parsing XRay config")
            config = XRayConfig(config, self.client_ip)
        except json.decoder.JSONDecodeError as exc:
            logger.error(f"Failed to decode config: {exc}")
            logger.error("Stack trace:", exc_info=True)
            raise HTTPException(
                status_code=422,
                detail={
                    "config": f'Failed to decode config: {exc}'
                }
            )

        with self.core.get_logs() as logs:
            try:
                logger.info("Starting XRay core")
                self.core.start(config)

                start_time = time.time()
                end_time = start_time + 3
                last_log = ''
                while time.time() < end_time:
                    while logs:
                        log = logs.popleft()
                        if log:
                            last_log = log
                            logger.debug(f"XRay log: {log}")
                        if f'Xray {self.core_version} started' in log:
                            logger.info("XRay core started successfully")
                            break
                    time.sleep(0.1)

            except Exception as exc:
                logger.error(f"Failed to start core: {exc}")
                logger.error("Stack trace:", exc_info=True)
                raise HTTPException(
                    status_code=503,
                    detail=str(exc)
                )

        if not self.core.started:
            logger.error(f"Core failed to start. Last log: {last_log}")
            raise HTTPException(
                status_code=503,
                detail=last_log
            )

        return self.response()

    def stop(self, session_id: UUID = Body(embed=True)):
        logger.info(f"Stop request with session ID: {session_id}")
        self.match_session_id(session_id)

        try:
            logger.info("Stopping XRay core")
            self.core.stop()
            logger.info("XRay core stopped successfully")
        except RuntimeError as e:
            logger.error(f"Error stopping core: {e}")
            logger.error("Stack trace:", exc_info=True)

        return self.response()

    def restart(self, session_id: UUID = Body(embed=True), config: str = Body(embed=True)):
        logger.info(f"Restart request with session ID: {session_id}")
        self.match_session_id(session_id)

        try:
            logger.debug("Parsing XRay config for restart")
            config = XRayConfig(config, self.client_ip)
        except json.decoder.JSONDecodeError as exc:
            logger.error(f"Failed to decode config: {exc}")
            logger.error("Stack trace:", exc_info=True)
            raise HTTPException(
                status_code=422,
                detail={
                    "config": f'Failed to decode config: {exc}'
                }
            )

        try:
            logger.info("Restarting XRay core")
            with self.core.get_logs() as logs:
                self.core.restart(config)

                start_time = time.time()
                end_time = start_time + 3
                last_log = ''
                while time.time() < end_time:
                    while logs:
                        log = logs.popleft()
                        if log:
                            last_log = log
                            logger.debug(f"XRay log: {log}")
                        if f'Xray {self.core_version} started' in log:
                            logger.info("XRay core restarted successfully")
                            break
                    time.sleep(0.1)

        except Exception as exc:
            logger.error(f"Failed to restart core: {exc}")
            logger.error("Stack trace:", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=str(exc)
            )

        if not self.core.started:
            logger.error(f"Core failed to restart. Last log: {last_log}")
            raise HTTPException(
                status_code=503,
                detail=last_log
            )

        return self.response()

    async def logs(self, websocket: WebSocket):
        logger.info("WebSocket logs connection request")
        session_id = websocket.query_params.get('session_id')
        interval = websocket.query_params.get('interval')

        try:
            session_id = UUID(session_id)
            if session_id != self.session_id:
                logger.warning(f"Session ID mismatch in logs WebSocket: {session_id} != {self.session_id}")
                return await websocket.close(reason="Session ID mismatch.", code=4403)

        except ValueError:
            logger.error(f"Invalid session_id format: {session_id}")
            return await websocket.close(reason="session_id should be a valid UUID.", code=4400)

        if interval:
            try:
                interval = float(interval)
            except ValueError:
                logger.error(f"Invalid interval value: {interval}")
                return await websocket.close(reason="Invalid interval value.", code=4400)

            if interval > 10:
                logger.error(f"Interval too large: {interval}")
                return await websocket.close(reason="Interval must be more than 0 and at most 10 seconds.", code=4400)

        logger.info(f"Accepting WebSocket connection for logs with session_id={session_id}, interval={interval}")
        await websocket.accept()

        cache = ''
        last_sent_ts = 0
        try:
            with self.core.get_logs() as logs:
                while session_id == self.session_id:
                    if interval and time.time() - last_sent_ts >= interval and cache:
                        try:
                            await websocket.send_text(cache)
                        except (WebSocketDisconnect, RuntimeError) as e:
                            logger.error(f"WebSocket error: {e}")
                            logger.error("Stack trace:", exc_info=True)
                            break
                        cache = ''
                        last_sent_ts = time.time()

                    if not logs:
                        try:
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logger.error(f"Error in logs WebSocket loop: {e}")
                            logger.error("Stack trace:", exc_info=True)
                            break
                        continue

                    while logs:
                        log = logs.popleft()
                        if log:
                            cache += log + '\n'
        except Exception as e:
            logger.error(f"Error in logs WebSocket handler: {e}")
            logger.error("Stack trace:", exc_info=True)
        finally:
            logger.info("WebSocket logs connection closed")

service = Service()
app.include_router(service.router)