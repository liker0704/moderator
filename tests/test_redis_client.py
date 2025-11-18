"""
Test suite for Redis client wrapper.

This module tests the Redis client functionality with mocks for unit testing.
Integration tests with real Redis are marked with @pytest.mark.integration
and @pytest.mark.skip for future CI/CD setup.
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from importlib import import_module

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

import redis.asyncio as aioredis

# Import client module directly to avoid __init__.py issues
# We need to mock dependencies before importing
sys.modules['queue.handlers'] = MagicMock()
sys.modules['queue'] = MagicMock()

# Now import after mocking problematic modules
from job_queue import client as redis_client_module


class TestRedisClientInitialization:
    """Tests for RedisClient initialization."""

    def test_redis_client_init_basic(self):
        """Test RedisClient initialization with basic parameters."""
        client = redis_client_module.RedisClient(
            host="localhost",
            port=6379,
            password=None,
            db=0
        )

        assert client.host == "localhost"
        assert client.port == 6379
        assert client.password is None
        assert client.db == 0
        assert client.max_connections == 50  # default
        assert client.decode_responses is False  # default
        assert client._client is None
        assert client._pool is None

    def test_redis_client_init_with_password(self):
        """Test RedisClient initialization with password."""
        client = redis_client_module.RedisClient(
            host="redis.example.com",
            port=6380,
            password="secret123",
            db=1
        )

        assert client.host == "redis.example.com"
        assert client.port == 6380
        assert client.password == "secret123"
        assert client.db == 1

    def test_redis_client_init_custom_pool_size(self):
        """Test RedisClient initialization with custom max_connections."""
        client = redis_client_module.RedisClient(
            host="localhost",
            port=6379,
            max_connections=100
        )

        assert client.max_connections == 100

    def test_redis_client_init_decode_responses(self):
        """Test RedisClient initialization with decode_responses."""
        client = redis_client_module.RedisClient(
            host="localhost",
            port=6379,
            decode_responses=True
        )

        assert client.decode_responses is True


class TestRedisClientConnection:
    """Tests for RedisClient connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful Redis connection."""
        with patch('redis.asyncio.ConnectionPool') as mock_pool_class, \
             patch('redis.asyncio.Redis') as mock_redis_class:

            # Setup mocks
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis_class.return_value = mock_redis

            # Test connection
            client = redis_client_module.RedisClient(host="localhost", port=6379)
            result = await client.connect()

            assert result is True
            assert client._pool is mock_pool
            assert client._client is mock_redis

            # Verify pool creation
            mock_pool_class.assert_called_once_with(
                host="localhost",
                port=6379,
                password=None,
                db=0,
                max_connections=50,
                decode_responses=False,
            )

            # Verify Redis client creation
            mock_redis_class.assert_called_once_with(connection_pool=mock_pool)

            # Verify ping was called
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_with_password(self):
        """Test Redis connection with password authentication."""
        with patch('redis.asyncio.ConnectionPool') as mock_pool_class, \
             patch('redis.asyncio.Redis') as mock_redis_class:

            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis_class.return_value = mock_redis

            client = redis_client_module.RedisClient(
                host="localhost",
                port=6379,
                password="secret123"
            )
            result = await client.connect()

            assert result is True

            # Verify password was passed to pool
            mock_pool_class.assert_called_once_with(
                host="localhost",
                port=6379,
                password="secret123",
                db=0,
                max_connections=50,
                decode_responses=False,
            )

    @pytest.mark.asyncio
    async def test_connect_failure_connection_refused(self):
        """Test connection failure when Redis is not available."""
        with patch('redis.asyncio.ConnectionPool') as mock_pool_class, \
             patch('redis.asyncio.Redis') as mock_redis_class:

            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(
                side_effect=aioredis.ConnectionError("Connection refused")
            )
            mock_redis_class.return_value = mock_redis

            client = redis_client_module.RedisClient(host="invalid-host", port=9999)
            result = await client.connect()

            assert result is False
            # Client and pool should still be set but ping failed
            assert client._pool is mock_pool
            assert client._client is mock_redis

    @pytest.mark.asyncio
    async def test_connect_failure_generic_error(self):
        """Test connection failure with generic exception."""
        with patch('redis.asyncio.ConnectionPool') as mock_pool_class:

            mock_pool_class.side_effect = Exception("Network error")

            client = redis_client_module.RedisClient(host="localhost", port=6379)
            result = await client.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful Redis disconnection."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        # Set up mock client and pool
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        client._client = mock_redis

        mock_pool = AsyncMock()
        mock_pool.disconnect = AsyncMock()
        client._pool = mock_pool

        await client.disconnect()

        # Verify cleanup
        mock_redis.close.assert_called_once()
        mock_pool.disconnect.assert_called_once()
        assert client._client is None
        assert client._pool is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Test disconnect when client was never connected."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        # Should not raise error
        await client.disconnect()

        assert client._client is None
        assert client._pool is None

    @pytest.mark.asyncio
    async def test_disconnect_with_error(self):
        """Test disconnect handles errors gracefully."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock(side_effect=Exception("Close error"))
        client._client = mock_redis

        # Should not raise - errors are logged
        await client.disconnect()


class TestRedisClientHealthCheck:
    """Tests for Redis health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check with healthy Redis connection."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        client._client = mock_redis

        result = await client.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when client is not connected."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)
        # _client is None

        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Test health check when ping fails."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(
            side_effect=aioredis.ConnectionError("Connection lost")
        )
        client._client = mock_redis

        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check with timeout error."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(
            side_effect=aioredis.TimeoutError("Ping timeout")
        )
        client._client = mock_redis

        result = await client.health_check()

        assert result is False


class TestRedisClientProperty:
    """Tests for Redis client property accessor."""

    def test_client_property_when_connected(self):
        """Test accessing client property when connected."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)

        mock_redis = AsyncMock()
        client._client = mock_redis

        result = client.client

        assert result is mock_redis

    def test_client_property_when_not_connected(self):
        """Test accessing client property raises error when not connected."""
        client = redis_client_module.RedisClient(host="localhost", port=6379)
        # _client is None

        with pytest.raises(RuntimeError, match="Redis not connected"):
            _ = client.client


class TestGlobalRedisClient:
    """Tests for global Redis client management functions."""

    @pytest.mark.asyncio
    async def test_init_redis_client_with_config(self):
        """Test initializing global Redis client from config."""
        with patch.object(redis_client_module, 'get_config') as mock_get_config, \
             patch('redis.asyncio.ConnectionPool') as mock_pool_class, \
             patch('redis.asyncio.Redis') as mock_redis_class:

            # Setup config mock
            mock_config = Mock()
            mock_config.redis = Mock()
            mock_config.redis.host = "config-host"
            mock_config.redis.port = 6380
            mock_config.redis.password = "config-password"
            mock_get_config.return_value = mock_config

            # Setup Redis mocks
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis_class.return_value = mock_redis

            client = await redis_client_module.init_redis_client()

            assert client is not None
            assert client.host == "config-host"
            assert client.port == 6380
            assert client.password == "config-password"

    @pytest.mark.asyncio
    async def test_init_redis_client_override_config(self):
        """Test initializing global Redis client with explicit parameters."""
        with patch.object(redis_client_module, 'get_config') as mock_get_config, \
             patch('redis.asyncio.ConnectionPool') as mock_pool_class, \
             patch('redis.asyncio.Redis') as mock_redis_class:

            # Setup config mock
            mock_config = Mock()
            mock_config.redis = Mock()
            mock_config.redis.host = "config-host"
            mock_config.redis.port = 6379
            mock_config.redis.password = None
            mock_get_config.return_value = mock_config

            # Setup Redis mocks
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool

            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis_class.return_value = mock_redis

            # Override with explicit params
            client = await redis_client_module.init_redis_client(
                host="override-host",
                port=7000,
                password="override-pass"
            )

            assert client.host == "override-host"
            assert client.port == 7000
            assert client.password == "override-pass"

    @pytest.mark.asyncio
    async def test_init_redis_client_no_config(self):
        """Test initialization fails when config is not available."""
        with patch.object(redis_client_module, 'get_config') as mock_get_config:

            # Config has no redis section
            mock_config = Mock()
            mock_config.redis = None
            mock_get_config.return_value = mock_config

            with pytest.raises(RuntimeError, match="Redis configuration not available"):
                await redis_client_module.init_redis_client()

    def test_get_redis_client_success(self):
        """Test getting initialized global Redis client."""
        # Setup global client
        mock_client = redis_client_module.RedisClient(host="localhost", port=6379)
        original_client = redis_client_module._redis_client
        redis_client_module._redis_client = mock_client

        try:
            result = redis_client_module.get_redis_client()
            assert result is mock_client
        finally:
            redis_client_module._redis_client = original_client

    def test_get_redis_client_not_initialized(self):
        """Test getting client before initialization raises error."""
        original_client = redis_client_module._redis_client
        redis_client_module._redis_client = None

        try:
            with pytest.raises(RuntimeError, match="Redis not initialized"):
                redis_client_module.get_redis_client()
        finally:
            redis_client_module._redis_client = original_client

    @pytest.mark.asyncio
    async def test_close_redis_client_success(self):
        """Test closing global Redis client."""
        # Setup global client with mocks
        mock_client = redis_client_module.RedisClient(host="localhost", port=6379)
        mock_redis = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_client._client = mock_redis

        mock_pool = AsyncMock()
        mock_pool.disconnect = AsyncMock()
        mock_client._pool = mock_pool

        original_client = redis_client_module._redis_client
        redis_client_module._redis_client = mock_client

        try:
            await redis_client_module.close_redis_client()

            # Verify disconnect was called
            mock_redis.close.assert_called_once()
            mock_pool.disconnect.assert_called_once()

            # Global client should be None
            assert redis_client_module._redis_client is None
        finally:
            redis_client_module._redis_client = original_client

    @pytest.mark.asyncio
    async def test_close_redis_client_when_none(self):
        """Test closing when no global client exists."""
        original_client = redis_client_module._redis_client
        redis_client_module._redis_client = None

        try:
            # Should not raise
            await redis_client_module.close_redis_client()
            assert redis_client_module._redis_client is None
        finally:
            redis_client_module._redis_client = original_client

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self):
        """Test global health check function."""
        # Setup global client
        mock_client = redis_client_module.RedisClient(host="localhost", port=6379)
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_client._client = mock_redis

        original_client = redis_client_module._redis_client
        redis_client_module._redis_client = mock_client

        try:
            result = await redis_client_module.check_redis_health()

            assert result is True
            mock_redis.ping.assert_called_once()
        finally:
            redis_client_module._redis_client = original_client

    @pytest.mark.asyncio
    async def test_check_redis_health_not_initialized(self):
        """Test health check when client not initialized."""
        original_client = redis_client_module._redis_client
        redis_client_module._redis_client = None

        try:
            result = await redis_client_module.check_redis_health()
            assert result is False
        finally:
            redis_client_module._redis_client = original_client


# Integration Tests Documentation
class TestRedisIntegrationRequirements:
    """
    INTEGRATION TESTS - Require real Redis instance

    These tests are marked with @pytest.mark.integration and @pytest.mark.skip.
    To enable them in CI/CD:

    1. Docker Compose Setup (docker-compose.test.yml):
       ```yaml
       version: '3.8'
       services:
         redis-test:
           image: redis:7-alpine
           ports:
             - "6380:6379"
           healthcheck:
             test: ["CMD", "redis-cli", "ping"]
             interval: 5s
             timeout: 3s
             retries: 5
       ```

    2. GitHub Actions / CI Configuration:
       ```yaml
       - name: Start Redis
         run: docker-compose -f docker-compose.test.yml up -d redis-test

       - name: Wait for Redis
         run: docker-compose -f docker-compose.test.yml exec redis-test redis-cli ping

       - name: Run Integration Tests
         run: pytest tests/test_redis_client.py -v -m integration
         env:
           REDIS_HOST: localhost
           REDIS_PORT: 6380

       - name: Stop Redis
         run: docker-compose -f docker-compose.test.yml down
       ```

    3. Local Testing:
       ```bash
       # Start Redis container
       docker run -d --name redis-test -p 6380:6379 redis:7-alpine

       # Run integration tests
       REDIS_HOST=localhost REDIS_PORT=6380 pytest tests/test_redis_client.py -v -m integration

       # Stop container
       docker stop redis-test && docker rm redis-test
       ```
    """

    @pytest.mark.skip(reason="Requires real Redis instance - enable in CI/CD")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_redis_connection(self):
        """Integration test: Connect to real Redis instance."""
        import os

        client = redis_client_module.RedisClient(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6380")),
        )

        # Connect
        result = await client.connect()
        assert result is True

        # Health check
        health = await client.health_check()
        assert health is True

        # Disconnect
        await client.disconnect()

    @pytest.mark.skip(reason="Requires real Redis instance - enable in CI/CD")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_redis_get_set(self):
        """Integration test: Perform GET/SET operations on real Redis."""
        import os

        client = redis_client_module.RedisClient(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6380")),
        )

        await client.connect()

        # Test SET
        await client.client.set("test_key", "test_value")

        # Test GET
        value = await client.client.get("test_key")
        assert value == b"test_value"

        # Cleanup
        await client.client.delete("test_key")
        await client.disconnect()

    @pytest.mark.skip(reason="Requires real Redis instance - enable in CI/CD")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_redis_connection_pool(self):
        """Integration test: Verify connection pooling works."""
        import os

        client = redis_client_module.RedisClient(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6380")),
            max_connections=10
        )

        await client.connect()

        # Perform multiple operations to test pooling
        for i in range(20):
            await client.client.ping()

        await client.disconnect()
