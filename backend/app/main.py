"""FastAPI application for Turing Machine simulation.

This module provides the HTTP API, CORS middleware, strict request size protection,
and endpoints for health checks and machine simulation.
"""

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.schemas import PredictionRequest, SimulationRequest, SimulationResponse
from backend.app.simulator import simulate

MAX_REQUEST_BODY_SIZE = 262144  # 256 KiB (262,144 bytes)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


class RequestBodyTooLargeException(Exception):
    """Exception raised when an incoming request body exceeds the size limit."""
    pass


class ContentSizeLimitMiddleware:
    """Pure ASGI middleware enforcing maximum request body limits.

    Rejects requests whose declared Content-Length or actual streamed body
    exceeds 256 KiB (262,144 bytes) with HTTP 413 Request Entity Too Large.
    """

    def __init__(self, app, max_content_size: int = MAX_REQUEST_BODY_SIZE):
        self.app = app
        self.max_content_size = max_content_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Fast check: declared Content-Length header
        headers = dict(scope.get("headers", []))
        content_length_header = headers.get(b"content-length")
        if content_length_header is not None:
            try:
                content_length = int(content_length_header.decode("latin1"))
                if content_length > self.max_content_size:
                    response = JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "detail": (
                                f"Request body exceeds maximum permitted size of "
                                f"{self.max_content_size} bytes (256 KiB)."
                            )
                        },
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        # 2. Streamed check: track actual received bytes
        received_bytes = 0

        async def receive_wrapper():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received_bytes += len(chunk)
                if received_bytes > self.max_content_size:
                    raise RequestBodyTooLargeException()
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        except RequestBodyTooLargeException:
            response = JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={
                    "detail": (
                        f"Request body exceeds maximum permitted size of "
                        f"{self.max_content_size} bytes (256 KiB)."
                    )
                },
            )
            await response(scope, receive, send)


app = FastAPI(
    title="Turing Machine Simulator API",
    description="Deterministic Turing Machine Simulation Engine API",
    version="1.0.0",
)

# Exception handler for body size limit
@app.exception_handler(RequestBodyTooLargeException)
async def request_body_too_large_handler(request: Request, exc: RequestBodyTooLargeException):
    return JSONResponse(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        content={
            "detail": (
                f"Request body exceeds maximum permitted size of "
                f"{MAX_REQUEST_BODY_SIZE} bytes (256 KiB)."
            )
        },
    )


# Register CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# Register request size limit middleware
app.add_middleware(ContentSizeLimitMiddleware, max_content_size=MAX_REQUEST_BODY_SIZE)


@app.get(
    "/api/health",
    summary="Health Check",
    tags=["Health"],
    response_model=dict[str, str],
)
async def health_check() -> dict[str, str]:
    """Report service health and readiness."""
    return {"status": "ok"}


@app.post(
    "/api/simulate",
    summary="Execute Turing Machine Simulation",
    tags=["Simulation"],
    response_model=SimulationResponse,
    status_code=status.HTTP_200_OK,
)
async def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """Execute a deterministic simulation of a Turing Machine on an input string.

    The simulation executes up to `step_limit` transitions and returns the exact
    terminal condition, step count, initial tape snapshot, and full execution trace.
    """
    try:
        response = simulate(
            machine=request.machine,
            input_text=request.input,
            step_limit=request.step_limit,
            trace_limit=None,
        )
        return response
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from err


@lru_cache(maxsize=1)
def prediction_models():
    from backend.app.predictor import load_model_bundle

    return load_model_bundle(PROJECT_ROOT / "models" / "final")


@app.post("/api/predict", tags=["Prediction"])
def run_prediction(request: PredictionRequest) -> dict:
    try:
        from backend.app.predictor import predict_all_budgets, predict_bounded

        models = prediction_models()
    except (ImportError, OSError, ValueError, KeyError, AttributeError) as err:
        logger.exception("Prediction models could not be loaded")
        raise HTTPException(503, "Prediction models are unavailable. See the README for setup.") from err

    if request.step_limit is not None:
        return predict_bounded(request.machine, request.input, request.step_limit, models)
    return predict_all_budgets(
        request.machine, request.input, models, enforce_monotonic=False
    )


# Mount frontend static distribution after API routes.
import os
from fastapi.staticfiles import StaticFiles

frontend_dist_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
    "dist",
)
if os.path.isdir(frontend_dist_dir):
    app.mount("/", StaticFiles(directory=frontend_dist_dir, html=True), name="frontend")
