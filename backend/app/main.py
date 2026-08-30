import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.core.logging import RequestLoggingMiddleware, logger
from backend.app.api.v1.router import api_router


from backend.app.rag.retriever import Retriever
from backend.app.core.database import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing application...")
    init_db()
    try:
        db = get_db()
        retriever = Retriever(db)
        chunks, mat, _ = retriever._get_published_chunks_and_matrix()
        logger.info(f"Vector index pre-warmed in RAM ({len(chunks)} published chunks indexed).")
    except Exception as e:
        logger.warning(f"Vector index pre-warming skipped: {e}")
    logger.info("Application startup complete.")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

from fastapi.middleware.gzip import GZipMiddleware

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router, prefix=settings.API_V1_STR)

# Static Frontend Mount with Optimized Caching
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/static"))
if os.path.exists(static_dir):
    class CachedStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            ext = os.path.splitext(path)[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico", ".woff2", ".woff", ".ttf"]:
                response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            elif ext in [".css", ".js"]:
                response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
            else:
                response.headers["Cache-Control"] = "no-cache, must-revalidate"
            return response

    app.mount("/static", CachedStaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(
            os.path.join(static_dir, "index.html"),
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("openapi.json"):
            return None
        file_path = os.path.join(static_dir, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            headers = {"Cache-Control": "public, max-age=604800, immutable"} if ext in [".jpg", ".jpeg", ".png", ".webp", ".svg", ".ico"] else {"Cache-Control": "no-cache"}
            return FileResponse(file_path, headers=headers)
        return FileResponse(
            os.path.join(static_dir, "index.html"),
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
