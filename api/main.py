from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import structlog
from typing import Dict, Any

from config.settings import get_settings
from services.cache_service import get_cache_service
from rag.knowledge_base import get_knowledge_base
from api.routes import review, webhooks, health

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("application_starting", version=settings.APP_VERSION)
    
    # Initialize services
    cache_service = await get_cache_service()
    logger.info("cache_service_initialized")
    
    knowledge_base = get_knowledge_base()
    logger.info("knowledge_base_initialized")
    
    # Load knowledge base if directory exists
    import os
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'rag', 'data')
    if os.path.exists(data_dir):
        await knowledge_base.initialize_from_files(data_dir)
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    await cache_service.disconnect()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready AI code review agent with multi-agent architecture",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(review.router, prefix="/api/v1", tags=["review"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/api/v1/stats")
async def get_stats():
    """Get system statistics"""
    try:
        cache_service = await get_cache_service()
        cache_stats = await cache_service.get_stats()
        
        knowledge_base = get_knowledge_base()
        kb_stats = knowledge_base.get_stats()
        
        from core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager()
        llm_stats = llm_manager.get_stats()
        
        return {
            "cache": cache_stats,
            "knowledge_base": kb_stats,
            "llm": llm_stats,
            "environment": settings.ENVIRONMENT
        }
        
    except Exception as e:
        logger.error("get_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=settings.DEBUG
    )