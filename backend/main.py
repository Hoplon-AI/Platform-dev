"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from backend.api.ingestion.upload_router import router as upload_router
from backend.api.v1.lineage_router import router as lineage_router
from backend.api.v1.portfolios_router import router as portfolios_router
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
app.add_middleware(
    CORSMiddleware,
    # Local dev: support both localhost and 127.0.0.1 for Vite/React dev servers.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload_router)
app.include_router(lineage_router)
app.include_router(portfolios_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Platform-dev API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# TODO review 
@app.get("/health")
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
