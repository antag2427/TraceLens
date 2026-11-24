"""FastAPI application and local deployment settings."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers

from .api import router
from .db import Base, connect

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


class LimitUpload:
    """Bound the multipart request before the uploaded file reaches its route."""

    def __init__(self, app, *, limit):
        self.app = app
        self.limit = limit + 1024 * 1024

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/v1/logs/upload":
            await self.app(scope, receive, send)
            return
        message = "Upload body exceeds the configured request limit"
        length = Headers(scope=scope).get("content-length", "")
        if length.isdecimal() and int(length) > self.limit:
            await JSONResponse({"detail": message}, status_code=413)(scope, receive, send)
            return
        received = 0

        async def capped_receive():
            nonlocal received
            chunk = await receive()
            received += len(chunk.get("body", b""))
            if received > self.limit:
                raise HTTPException(413, message)
            return chunk

        await self.app(scope, capped_receive, send)


def create_app(database_path=None):
    path = Path(database_path or os.environ.get("TRACELENS_DB_PATH", str(ROOT / "data/local/tracelens.sqlite3")))
    engine, sessions = connect(path)

    @asynccontextmanager
    async def lifespan(_app):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(title="TraceLens", version="1.0.0", lifespan=lifespan,
                  description="Local log ingestion and evidence-based incident investigation")
    app.state.sessions = sessions
    app.state.analysis_lock = Lock()
    app.state.max_upload = int(os.getenv("TRACELENS_MAX_UPLOAD_BYTES", "26214400"))
    app.state.demo_file = ROOT / "data/generated/demo.jsonl"
    app.add_middleware(LimitUpload, limit=app.state.max_upload)
    origins = os.getenv("TRACELENS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins.split(",") if o.strip() and o.strip() != "*"],
                       allow_methods=["GET", "POST", "PATCH", "PUT"], allow_headers=["Content-Type"])
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled %s on %s", type(exc).__name__, request.url.path)
        return JSONResponse({"detail": "An internal error occurred. Check the server logs."}, status_code=500)

    return app


app = create_app()
