from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.v1.router import api_v1_router
from app.api.v1.websockets.task_stream import router as websocket_router
from app.core.errors import register_problem_handlers

logger = logging.getLogger("rolesync.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("Database schemas initialized.")
    except Exception as e:
        logger.warning(f"Database auto-init skipped or deferred: {e}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise-grade AI Job Application Copilot & ATS Tailoring Engine",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    lifespan=lifespan,
)

# Register RFC 7807 problem+json error handlers
register_problem_handlers(app)

# Rate Limiter
from app.core.limiter import limiter
app.state.limiter = limiter

# Enterprise CORS Middleware allowing approved web origins and browser extensions
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^chrome-extension://[a-zA-Z0-9]+$|^moz-extension://[a-zA-Z0-9-]+$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_STR)
app.include_router(websocket_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "RoleSync Platform API",
        "version": settings.VERSION
    }
