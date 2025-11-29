# api/routes/health.py
"""
Health check endpoints
"""
from fastapi import APIRouter
import structlog

from config.settings import get_settings
from services.cache_service import get_cache_service

logger = structlog.get_logger()
settings = get_settings()
router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health check with service status"""
    try:
        # Check cache
        cache_service = await get_cache_service()
        cache_status = "connected" if cache_service.enabled else "disabled"
        
        # Check LLM
        from core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager()
        llm_status = "ready" if llm_manager.primary_llm else "not_configured"
        
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "services": {
                "cache": cache_status,
                "llm": llm_status,
                "knowledge_base": "ready"
            }
        }
        
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe"""
    try:
        # Check if services are ready
        cache_service = await get_cache_service()
        return {"ready": True}
    except:
        return {"ready": False}


@router.get("/live")
async def liveness():
    """Kubernetes liveness probe"""
    return {"alive": True}