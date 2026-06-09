from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.api.v1.router import api_router
from app.core.exceptions import CustomException

app = FastAPI(
    title=settings.APP_NAME,
    description="通用 AI 伴学与智能体协同平台 API 服务",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    debug=settings.APP_DEBUG
)

# Set up CORS middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Exception handler for custom business/auth exceptions
@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": int(exc.code) if exc.code.isdigit() else 40000,
            "message": exc.message,
            "data": exc.data
        }
    )

# Exception handler for Pydantic validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error.get("loc", []))
        errors.append(f"[{loc}]: {error.get('msg')}")
    
    return JSONResponse(
        status_code=422,
        content={
            "code": 40001,
            "message": "数据格式校验失败: " + ", ".join(errors),
            "data": exc.errors()
        }
    )

# Exception handler for global unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.error(f"Global unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 50000,
            "message": "系统内部繁忙，请稍后再试",
            "data": str(exc) if settings.APP_DEBUG else None
        }
    )

# Basic health check
@app.get("/api/health", tags=["系统状态"], summary="健康检查")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV
    }

@app.on_event("startup")
async def startup_event():
    if settings.ENABLE_INLINE_SCHEDULER:
        from app.core.scheduler import start_scheduler
        start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    if settings.ENABLE_INLINE_SCHEDULER:
        from app.core.scheduler import stop_scheduler
        stop_scheduler()

# Include the API router
app.include_router(api_router, prefix="/api/v1")
