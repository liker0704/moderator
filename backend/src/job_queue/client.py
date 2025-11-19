"""
Redis client management for queue system.

This module handles:
- Redis connection initialization and configuration
- Connection pooling for optimal performance
- Health checks and connection monitoring
- Graceful shutdown and resource cleanup
- Singleton pattern for global client access

The Redis client is used by both the task enqueueing functions
and the ARQ worker for reliable message queue operations.
"""

import redis.asyncio as aioredis
from typing import Optional
from config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)


class RedisClient:
    """
    Redis client manager with singleton pattern.

    Provides a centralized Redis connection with:
    - Connection pooling
    - Automatic reconnection
    - Health monitoring
    - Graceful shutdown
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: Optional[str] = None,
        db: int = 0,
        max_connections: int = 50,
        decode_responses: bool = False,
    ):
        """
        Initialize Redis client manager.

        Args:
            host: Redis server hostname
            port: Redis server port
            password: Optional Redis password for authentication
            db: Redis database number (default: 0)
            max_connections: Maximum number of connections in pool
            decode_responses: Whether to decode responses to strings
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.max_connections = max_connections
        self.decode_responses = decode_responses

        self._client: Optional[aioredis.Redis] = None
        self._pool: Optional[aioredis.ConnectionPool] = None

    async def connect(self) -> bool:
        """
        Establish Redis connection with connection pooling.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create connection pool
            self._pool = aioredis.ConnectionPool(
                host=self.host,
                port=self.port,
                password=self.password if self.password else None,
                db=self.db,
                max_connections=self.max_connections,
                decode_responses=self.decode_responses,
            )

            # Create Redis client with connection pool
            self._client = aioredis.Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()

            logger.info(
                f"Redis client connected to {self.host}:{self.port}",
                extra={"host": self.host, "port": self.port}
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to connect to Redis: {e}",
                exc_info=True,
                extra={"host": self.host, "port": self.port}
            )
            return False

    async def disconnect(self):
        """
        Close Redis connection and cleanup resources.
        """
        try:
            if self._client:
                await self._client.close()
                self._client = None

            if self._pool:
                await self._pool.disconnect()
                self._pool = None

            logger.info("Redis client disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting Redis client: {e}", exc_info=True)

    async def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if Redis is accessible, False otherwise
        """
        try:
            if not self._client:
                return False

            await self._client.ping()
            return True

        except Exception as e:
            logger.error(f"Redis health check failed: {e}", exc_info=True)
            return False

    @property
    def client(self) -> aioredis.Redis:
        """
        Get Redis client instance.

        Returns:
            Redis client

        Raises:
            RuntimeError: If Redis is not connected
        """
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")

        return self._client


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


async def init_redis_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    db: int = 0,
    max_connections: int = 50,
) -> RedisClient:
    """
    Initialize global Redis client.

    Args:
        host: Redis hostname (defaults from config)
        port: Redis port (defaults from config)
        password: Redis password (defaults from config)
        db: Redis database number
        max_connections: Maximum connections in pool

    Returns:
        RedisClient instance

    Raises:
        RuntimeError: If Redis configuration is not available
    """
    global _redis_client

    config = get_config()

    # Use config values if not provided
    if config.redis:
        host = host or config.redis.host
        port = port or config.redis.port
        password = password or config.redis.password
    else:
        if not host or not port:
            raise RuntimeError(
                "Redis configuration not available. "
                "Set REDIS_HOST and REDIS_PORT environment variables."
            )

    _redis_client = RedisClient(
        host=host,
        port=port,
        password=password,
        db=db,
        max_connections=max_connections,
    )

    await _redis_client.connect()

    return _redis_client


def get_redis_client() -> RedisClient:
    """
    Get global Redis client instance.

    Returns:
        RedisClient instance

    Raises:
        RuntimeError: If Redis has not been initialized
    """
    if not _redis_client:
        raise RuntimeError("Redis not initialized. Call init_redis_client() first.")

    return _redis_client


async def close_redis_client():
    """
    Close global Redis client and cleanup resources.
    """
    global _redis_client

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None


async def check_redis_health() -> bool:
    """
    Check if Redis connection is healthy.

    Returns:
        True if Redis is accessible, False otherwise
    """
    try:
        client = get_redis_client()
        return await client.health_check()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}", exc_info=True)
        return False
