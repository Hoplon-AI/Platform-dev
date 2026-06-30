
"""
Main FastAPI application entry point.
"""
from dotenv import load_dotenv
load_dotenv(override=True)
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from backend.api.ingestion.upload_router import router as upload_router
from backend.api.v1.lineage_router import router as lineage_router
from backend.api.v1.portfolios_router import router as portfolios_router
from backend.api.enrichment.enrichment_router import router as enrichment_router
from backend.geo import router as geo_router
from backend.api.v1.ha_profile_router import router as ha_profile_router
from backend.api.v1.export_router import router as export_router
from backend.api.v1.underwriter_router import router as underwriter_router
from backend.api.v1.pdf_test_router import router as pdf_test_router
from backend.api.v1.auth_router import router as auth_router
from backend.core.database.db_pool import DatabasePool
from infrastructure.storage.s3_config import get_s3_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Ensures global resources (database pool) are initialized for the app lifetime.
    """
    await DatabasePool.initialize()
    try:
        yield
    finally:
        await DatabasePool.close()


app = FastAPI(
    title="Platform-dev API",
    description="Bronze-layer ingestion, audit, and lineage APIs",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
import os as _os
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Production origins from env var (comma-separated, e.g. https://app.equirisk.ai,https://d1234.cloudfront.net)
_extra_origins = _os.getenv("CORS_ORIGINS", "")
if _extra_origins:
    _cors_origins += [o.strip() for o in _extra_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload_router)
app.include_router(lineage_router)
app.include_router(portfolios_router)
app.include_router(geo_router)
app.include_router(ha_profile_router)
app.include_router(export_router)
app.include_router(underwriter_router)
app.include_router(enrichment_router)
app.include_router(pdf_test_router)
app.include_router(auth_router)



@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Platform-dev API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Lightweight health check for ALB (always returns 200 if app is running)
@app.get("/health")
async def alb_health_check() -> Dict[str, str]:
    """Simple health check for ALB - returns 200 if app is running."""
    return {"status": "ok"}


@app.get("/health/detailed")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint.
    
    Verifies:
    - Database connectivity
    - S3 storage connectivity
    
    Returns:
        Health status with component checks
    """
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "checks": {}
    }
    overall_healthy = True
    
    # Check database connectivity
    try:
        pool = DatabasePool.get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "message": "Database connection successful"
                }
            else:
                health_status["checks"]["database"] = {
                    "status": "unhealthy",
                    "message": "Database query returned unexpected result"
                }
                overall_healthy = False
    except RuntimeError as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database pool not initialized: {str(e)}"
        }
        overall_healthy = False
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}"
        }
        overall_healthy = False
    
    # Check S3 storage connectivity
    try:
        s3_config = get_s3_config()
        s3_client = s3_config.get_client()
        bucket_name = s3_config.get_bucket_name()
        
        # Try to head the bucket (check if it exists and is accessible)
        s3_client.head_bucket(Bucket=bucket_name)
        
        health_status["checks"]["s3_storage"] = {
            "status": "healthy",
            "message": f"S3 bucket '{bucket_name}' is accessible"
        }
    except Exception as e:
        health_status["checks"]["s3_storage"] = {
            "status": "unhealthy",
            "message": f"S3 storage check failed: {str(e)}"
        }
        overall_healthy = False
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    # Return appropriate HTTP status code
    if not overall_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return health_status