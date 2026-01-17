import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import feedback, health, ingest, query
from app.core.config import settings
from app.core.exceptions import AdvisoryAssistantError
from app.core.logging import LogContext, get_logger, setup_logging
from app.retrieval.vector_store import get_vector_store

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logger.info(
        "Starting application",
        app_name=settings.app_name,
        environment=settings.app_env,
    )
    
    # Initialize vector store
    try:
        vector_store = get_vector_store()
        vector_store.initialize()  # Synchronous
        logger.info("Vector store initialized")
    except Exception as e:
        logger.error("Failed to initialize vector store", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


app = FastAPI(
    title="Internal AI Advisory Assistant",
    description="Internal AI Advisory Assistant",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")
    
    start_time = time.time()
    
    async with LogContext(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    ):
        try:
            response = await call_next(request)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            
            return response
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Request failed",
                error=str(e),
                duration_ms=duration_ms,
            )
            raise


@app.exception_handler(AdvisoryAssistantError)
async def advisory_exception_handler(
    request: Request,
    exc: AdvisoryAssistantError,
) -> JSONResponse:
    logger.warning(
        "Application error",
        error_code=exc.error_code,
        message=exc.message,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning(
        "Validation error",
        errors=exc.errors(),
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unexpected error",
        error=str(exc),
        exc_info=True,
    )
    
    if settings.is_production:
        message = "An internal error occurred"
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": message,
        },
    )


app.include_router(query.router, prefix=settings.api_prefix)
app.include_router(ingest.router, prefix=settings.api_prefix)
app.include_router(feedback.router, prefix=settings.api_prefix)
app.include_router(health.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
