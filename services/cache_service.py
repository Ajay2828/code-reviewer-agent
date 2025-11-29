import json
import hashlib
from typing import Optional, Any, Dict
import redis.asyncio as aioredis
import structlog

from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class CacheService:
    """
    Redis-based caching service for review results
    
    Cache strategy:
    - Key: hash of (file_path + content_hash + agent_name)
    - Value: AgentResult serialized as JSON
    - TTL: Configurable (default 1 hour)
    
    This prevents re-analyzing identical code
    """
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.enabled = settings.REDIS_HOST is not None
        
    async def connect(self):
        """Initialize Redis connection"""
        if not self.enabled:
            logger.warning("cache_disabled", reason="No Redis configuration")
            return
        
        try:
            self.redis = await aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                password=settings.REDIS_PASSWORD,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis.ping()
            logger.info("cache_connected", host=settings.REDIS_HOST)
            
        except Exception as e:
            logger.error("cache_connection_failed", error=str(e))
            self.enabled = False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("cache_disconnected")
    
    def _generate_cache_key(
        self,
        file_path: str,
        content_hash: str,
        agent_name: str
    ) -> str:
        """
        Generate cache key for a review
        
        Format: review:agent_name:hash
        """
        key_material = f"{file_path}:{content_hash}:{agent_name}"
        key_hash = hashlib.sha256(key_material.encode()).hexdigest()[:16]
        return f"review:{agent_name}:{key_hash}"
    
    async def get_cached_result(
        self,
        file_path: str,
        content_hash: str,
        agent_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached review result
        
        Returns None if not found or cache disabled
        """
        if not self.enabled or not self.redis:
            return None
        
        try:
            cache_key = self._generate_cache_key(file_path, content_hash, agent_name)
            cached_data = await self.redis.get(cache_key)
            
            if cached_data:
                logger.info(
                    "cache_hit",
                    agent=agent_name,
                    file=file_path
                )
                return json.loads(cached_data)
            
            logger.debug(
                "cache_miss",
                agent=agent_name,
                file=file_path
            )
            return None
            
        except Exception as e:
            logger.error("cache_get_failed", error=str(e))
            return None
    
    async def set_cached_result(
        self,
        file_path: str,
        content_hash: str,
        agent_name: str,
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache a review result
        
        Args:
            file_path: Path to the file
            content_hash: Hash of file content
            agent_name: Name of agent
            result: Result to cache (must be JSON serializable)
            ttl: Time to live in seconds (default: from settings)
        
        Returns:
            True if cached successfully
        """
        if not self.enabled or not self.redis:
            return False
        
        try:
            cache_key = self._generate_cache_key(file_path, content_hash, agent_name)
            ttl = ttl or settings.CACHE_TTL
            
            await self.redis.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )
            
            logger.info(
                "cache_set",
                agent=agent_name,
                file=file_path,
                ttl=ttl
            )
            return True
            
        except Exception as e:
            logger.error("cache_set_failed", error=str(e))
            return False
    
    async def invalidate_file(
        self,
        file_path: str,
        content_hash: str
    ) -> int:
        """
        Invalidate all cached results for a file
        
        Returns number of keys deleted
        """
        if not self.enabled or not self.redis:
            return 0
        
        try:
            # Find all keys for this file
            pattern = f"review:*:{hashlib.sha256(f'{file_path}:{content_hash}:*'.encode()).hexdigest()[:8]}*"
            keys = []
            
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(
                    "cache_invalidated",
                    file=file_path,
                    keys_deleted=deleted
                )
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error("cache_invalidate_failed", error=str(e))
            return 0
    
    async def clear_all(self) -> bool:
        """Clear all review caches (use with caution!)"""
        if not self.enabled or not self.redis:
            return False
        
        try:
            keys = []
            async for key in self.redis.scan_iter(match="review:*"):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
                logger.warning("cache_cleared", keys_deleted=len(keys))
            
            return True
            
        except Exception as e:
            logger.error("cache_clear_failed", error=str(e))
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled or not self.redis:
            return {"enabled": False}
        
        try:
            info = await self.redis.info("stats")
            keyspace = await self.redis.info("keyspace")
            
            # Count review keys
            review_keys = 0
            async for _ in self.redis.scan_iter(match="review:*"):
                review_keys += 1
            
            return {
                "enabled": True,
                "review_keys": review_keys,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) / 
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                )
            }
            
        except Exception as e:
            logger.error("cache_stats_failed", error=str(e))
            return {"enabled": True, "error": str(e)}


# Singleton instance
_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get or create cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    return _cache_service