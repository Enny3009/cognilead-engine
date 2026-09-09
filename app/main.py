from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import structlog

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import setup_logging
from app.core.redis import ping_redis

setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("system.startup", project_name=settings.PROJECT_NAME, env=settings.ENVIRONMENT)
    yield
    logger.info("system.shutdown", project_name=settings.PROJECT_NAME)
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all V1 API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health/live", tags=["Health"], status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"], status_code=status.HTTP_200_OK)
async def readiness_probe() -> JSONResponse:
    redis_healthy = await ping_redis()
    db_healthy = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_healthy = True
    except Exception as e:
        logger.error("healthcheck.database_failed", error=str(e))

    if redis_healthy and db_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "up", "redis": "up"},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "unhealthy",
            "database": "up" if db_healthy else "down",
            "redis": "up" if redis_healthy else "down",
        },
    )