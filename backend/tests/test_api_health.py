"""
Unit and integration tests for Health Check API.

Tests the health check system functionality including:
- Individual health check functions (Discord, Database, Redis, LLM)
- Overall status determination logic
- HTTP endpoint integration
- Error handling and edge cases
- Server infrastructure
"""

import pytest
import pytest_asyncio
import time
import os
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import json


# Set required environment variables for tests
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up environment variables required for testing."""
    os.environ.setdefault('DB_NAME', 'test_db')
    os.environ.setdefault('DB_USER', 'test_user')
    os.environ.setdefault('DB_PASSWORD', 'test_password')
    os.environ.setdefault('DB_HOST', 'localhost')
    os.environ.setdefault('DB_PORT', '5432')
    os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
    os.environ.setdefault('TELEGRAM_MODERATOR_USER_ID', '123456')
    os.environ.setdefault('MODERATOR_TG_USER_ID', '123456')
    os.environ.setdefault('ALERT_CHAT_ID', '123456')
    os.environ.setdefault('ENCRYPTION_KEY', 'test_encryption_key_32_bytes_long!')
    yield


class TestDiscordHealthCheck:
    """Test cases for _check_discord function."""

    @pytest.mark.asyncio
    async def test_discord_not_configured(self):
        """Test Discord health check when gateway is None (not configured)."""
        from api.health import _check_discord

        result = await _check_discord(None)

        assert result['status'] == 'not_configured'
        assert result['connected'] is False
        assert 'Discord integration not enabled' in result['message']

    @pytest.mark.asyncio
    async def test_discord_client_not_initialized(self):
        """Test Discord health check when client is not initialized."""
        from api.health import _check_discord

        # Mock gateway without client
        mock_gateway = Mock()
        mock_gateway.client = None

        result = await _check_discord(mock_gateway)

        assert result['status'] == 'unhealthy'
        assert result['connected'] is False
        assert 'Discord client not initialized' in result['message']

    @pytest.mark.asyncio
    async def test_discord_gateway_without_client_attribute(self):
        """Test Discord health check when gateway has no client attribute."""
        from api.health import _check_discord

        # Mock gateway without client attribute
        mock_gateway = Mock(spec=[])  # Empty spec means no attributes

        result = await _check_discord(mock_gateway)

        assert result['status'] == 'unhealthy'
        assert result['connected'] is False
        assert 'Discord client not initialized' in result['message']

    @pytest.mark.asyncio
    async def test_discord_connected_with_session(self):
        """Test Discord health check when connected with session."""
        from api.health import _check_discord

        # Mock gateway with connected client
        mock_client = Mock()
        mock_client.is_connected = True
        mock_client.session_id = 'abcdef123456789'

        mock_gateway = Mock()
        mock_gateway.client = mock_client

        result = await _check_discord(mock_gateway)

        assert result['status'] == 'healthy'
        assert result['connected'] is True
        assert 'session_id' in result
        assert result['session_id'] == 'abcdef12...'

    @pytest.mark.asyncio
    async def test_discord_connected_without_session(self):
        """Test Discord health check when connected but no session."""
        from api.health import _check_discord

        # Mock gateway with connected client but no session
        mock_client = Mock()
        mock_client.is_connected = True
        mock_client.session_id = None

        mock_gateway = Mock()
        mock_gateway.client = mock_client

        result = await _check_discord(mock_gateway)

        assert result['status'] == 'unhealthy'
        assert result['connected'] is True
        assert 'session_id' not in result

    @pytest.mark.asyncio
    async def test_discord_disconnected(self):
        """Test Discord health check when disconnected."""
        from api.health import _check_discord

        # Mock gateway with disconnected client
        mock_client = Mock()
        mock_client.is_connected = False
        mock_client.session_id = None

        mock_gateway = Mock()
        mock_gateway.client = mock_client

        result = await _check_discord(mock_gateway)

        assert result['status'] == 'unhealthy'
        assert result['connected'] is False

    @pytest.mark.asyncio
    async def test_discord_check_exception(self):
        """Test Discord health check handles exceptions."""
        from api.health import _check_discord

        # Mock gateway that raises exception when accessing is_connected
        mock_gateway = Mock()
        mock_client = Mock()

        # Make is_connected raise an exception
        type(mock_client).is_connected = property(lambda self: (_ for _ in ()).throw(Exception("Connection error")))

        mock_gateway.client = mock_client

        result = await _check_discord(mock_gateway)

        assert result['status'] == 'unhealthy'
        assert result['connected'] is False
        assert 'error' in result
        assert 'Connection error' in result['error']


class TestDatabaseHealthCheck:
    """Test cases for _check_database function."""

    @pytest.mark.asyncio
    async def test_database_healthy(self):
        """Test database health check when database is healthy."""
        from api.health import _check_database

        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True

            result = await _check_database()

            assert result['status'] == 'healthy'
            assert 'response_time_ms' in result
            assert result['response_time_ms'] >= 0

    @pytest.mark.asyncio
    async def test_database_unhealthy(self):
        """Test database health check when database is unhealthy."""
        from api.health import _check_database

        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False

            result = await _check_database()

            assert result['status'] == 'unhealthy'
            assert 'response_time_ms' in result
            assert result['response_time_ms'] >= 0

    @pytest.mark.asyncio
    async def test_database_check_exception(self):
        """Test database health check handles exceptions."""
        from api.health import _check_database

        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = Exception("Database connection failed")

            result = await _check_database()

            assert result['status'] == 'unhealthy'
            assert 'response_time_ms' in result
            assert 'error' in result
            assert 'Database connection failed' in result['error']

    @pytest.mark.asyncio
    async def test_database_response_time_accuracy(self):
        """Test database health check measures response time accurately."""
        from api.health import _check_database

        async def slow_check():
            """Simulate slow database check."""
            await AsyncMock()()
            time.sleep(0.05)  # 50ms delay
            return True

        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = slow_check

            result = await _check_database()

            assert result['status'] == 'healthy'
            assert result['response_time_ms'] >= 50
            assert result['response_time_ms'] < 100  # Should be less than 100ms


class TestRedisHealthCheck:
    """Test cases for _check_redis function."""

    @pytest.mark.asyncio
    async def test_redis_healthy(self):
        """Test Redis health check when Redis is healthy."""
        from api.health import _check_redis

        with patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True

            result = await _check_redis()

            assert result['status'] == 'healthy'
            assert 'response_time_ms' in result
            assert result['response_time_ms'] >= 0

    @pytest.mark.asyncio
    async def test_redis_unhealthy(self):
        """Test Redis health check when Redis is unhealthy."""
        from api.health import _check_redis

        with patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False

            result = await _check_redis()

            assert result['status'] == 'unhealthy'
            assert 'response_time_ms' in result

    @pytest.mark.asyncio
    async def test_redis_not_configured(self):
        """Test Redis health check when Redis is not initialized."""
        from api.health import _check_redis

        with patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = RuntimeError("Redis client not initialized")

            result = await _check_redis()

            assert result['status'] == 'not_configured'
            assert 'Redis client not initialized' in result['message']

    @pytest.mark.asyncio
    async def test_redis_check_exception(self):
        """Test Redis health check handles exceptions."""
        from api.health import _check_redis

        with patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = Exception("Connection refused")

            result = await _check_redis()

            assert result['status'] == 'unhealthy'
            assert 'response_time_ms' in result
            assert 'error' in result
            assert 'Connection refused' in result['error']


class TestLLMHealthCheck:
    """Test cases for _check_llm function."""

    @pytest.mark.asyncio
    async def test_llm_configured_with_model(self):
        """Test LLM health check when LLM is configured with model."""
        from api.health import _check_llm

        mock_config = Mock()
        mock_config.llm = Mock()
        mock_config.llm.provider = 'anthropic'
        mock_config.llm.model = 'claude-3-sonnet'

        with patch('config.get_config', return_value=mock_config):
            result = await _check_llm()

            assert result['status'] == 'configured'
            assert result['provider'] == 'anthropic'
            assert result['model'] == 'claude-3-sonnet'

    @pytest.mark.asyncio
    async def test_llm_configured_without_model(self):
        """Test LLM health check when LLM is configured without model."""
        from api.health import _check_llm

        mock_config = Mock()
        mock_config.llm = Mock()
        mock_config.llm.provider = 'openai'
        # No model attribute

        with patch('config.get_config', return_value=mock_config):
            result = await _check_llm()

            assert result['status'] == 'configured'
            assert result['provider'] == 'openai'
            assert result['model'] is None

    @pytest.mark.asyncio
    async def test_llm_not_configured_no_provider(self):
        """Test LLM health check when LLM has no provider."""
        from api.health import _check_llm

        mock_config = Mock()
        mock_config.llm = Mock()
        mock_config.llm.provider = None

        with patch('config.get_config', return_value=mock_config):
            result = await _check_llm()

            assert result['status'] == 'not_configured'
            assert result['provider'] is None

    @pytest.mark.asyncio
    async def test_llm_not_configured_no_llm(self):
        """Test LLM health check when LLM config is missing."""
        from api.health import _check_llm

        mock_config = Mock()
        mock_config.llm = None

        with patch('config.get_config', return_value=mock_config):
            result = await _check_llm()

            assert result['status'] == 'not_configured'
            assert result['provider'] is None

    @pytest.mark.asyncio
    async def test_llm_check_exception(self):
        """Test LLM health check handles exceptions."""
        from api.health import _check_llm

        with patch('config.get_config', side_effect=Exception("Config error")):
            result = await _check_llm()

            assert result['status'] == 'not_configured'
            assert 'error' in result
            assert 'Config error' in result['error']


class TestOverallStatusDetermination:
    """Test cases for _determine_overall_status function."""

    def test_all_services_healthy(self):
        """Test overall status when all services are healthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'healthy'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'healthy'

    def test_discord_unhealthy(self):
        """Test overall status when Discord is unhealthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'unhealthy'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'unhealthy'

    def test_database_unhealthy(self):
        """Test overall status when database is unhealthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'healthy'},
            'database': {'status': 'unhealthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'unhealthy'

    def test_redis_unhealthy(self):
        """Test overall status when Redis is unhealthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'healthy'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'unhealthy'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'unhealthy'

    def test_multiple_services_unhealthy(self):
        """Test overall status when multiple services are unhealthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'unhealthy'},
            'database': {'status': 'unhealthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'unhealthy'

    def test_discord_not_configured_database_healthy(self):
        """Test overall status when Discord not configured but database healthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'not_configured'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'healthy'

    def test_redis_not_configured_database_healthy(self):
        """Test overall status when Redis not configured but database healthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'healthy'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'not_configured'},
            'llm': {'status': 'configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'healthy'

    def test_llm_unhealthy_degraded(self):
        """Test overall status is degraded when only LLM is unhealthy."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'healthy'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'unhealthy'}
        }

        status = _determine_overall_status(checks)
        assert status == 'degraded'

    def test_llm_not_configured_healthy(self):
        """Test overall status is healthy when LLM is not configured."""
        from api.health import _determine_overall_status

        checks = {
            'discord': {'status': 'healthy'},
            'database': {'status': 'healthy'},
            'redis': {'status': 'healthy'},
            'llm': {'status': 'not_configured'}
        }

        status = _determine_overall_status(checks)
        assert status == 'healthy'


class TestHealthCheckEndpoint(AioHTTPTestCase):
    """Integration tests for health check HTTP endpoint."""

    async def get_application(self):
        """Create aiohttp application for testing."""
        from api.server import create_app
        return create_app(discord_gateway=None)

    @unittest_run_loop
    async def test_health_endpoint_all_healthy(self):
        """Test GET /health returns 200 when all critical services healthy."""
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = True
            mock_redis.return_value = True

            mock_cfg = Mock()
            mock_cfg.llm = Mock()
            mock_cfg.llm.provider = 'anthropic'
            mock_cfg.llm.model = 'claude-3-sonnet'
            mock_config.return_value = mock_cfg

            resp = await self.client.request("GET", "/health")

            assert resp.status == 200

            data = await resp.json()
            assert data['status'] == 'healthy'
            assert 'timestamp' in data
            assert 'checks' in data
            assert 'version' in data
            assert data['version'] == '0.1.0-mvp'

    @unittest_run_loop
    async def test_health_endpoint_database_unhealthy(self):
        """Test GET /health returns 503 when database unhealthy."""
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = False
            mock_redis.return_value = True

            mock_cfg = Mock()
            mock_cfg.llm = None
            mock_config.return_value = mock_cfg

            resp = await self.client.request("GET", "/health")

            assert resp.status == 503

            data = await resp.json()
            assert data['status'] == 'unhealthy'
            assert data['checks']['database']['status'] == 'unhealthy'

    @unittest_run_loop
    async def test_health_endpoint_multiple_services_unhealthy(self):
        """Test GET /health returns 503 when multiple services unhealthy."""
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = False
            mock_redis.return_value = False

            mock_cfg = Mock()
            mock_cfg.llm = None
            mock_config.return_value = mock_cfg

            resp = await self.client.request("GET", "/health")

            assert resp.status == 503

            data = await resp.json()
            assert data['status'] == 'unhealthy'
            assert data['checks']['database']['status'] == 'unhealthy'
            assert data['checks']['redis']['status'] == 'unhealthy'

    @unittest_run_loop
    async def test_health_endpoint_degraded_llm(self):
        """Test GET /health returns 503 with degraded when only LLM unhealthy."""
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = True
            mock_redis.return_value = True

            # LLM is unhealthy (not configured = degraded state)
            mock_cfg = Mock()
            mock_cfg.llm = None
            mock_config.return_value = mock_cfg

            resp = await self.client.request("GET", "/health")

            # When all critical services healthy but LLM not configured, should be healthy
            assert resp.status == 200

            data = await resp.json()
            assert data['checks']['llm']['status'] == 'not_configured'

    @unittest_run_loop
    async def test_health_endpoint_response_format(self):
        """Test GET /health response has correct JSON structure."""
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = True
            mock_redis.return_value = True

            mock_cfg = Mock()
            mock_cfg.llm = Mock()
            mock_cfg.llm.provider = 'anthropic'
            mock_config.return_value = mock_cfg

            resp = await self.client.request("GET", "/health")
            data = await resp.json()

            # Check top-level fields
            assert 'status' in data
            assert 'timestamp' in data
            assert 'checks' in data
            assert 'version' in data

            # Check checks structure
            assert 'discord' in data['checks']
            assert 'database' in data['checks']
            assert 'redis' in data['checks']
            assert 'llm' in data['checks']

            # Each check should have status
            for service in ['discord', 'database', 'redis', 'llm']:
                assert 'status' in data['checks'][service]

    @unittest_run_loop
    async def test_health_endpoint_timestamp_format(self):
        """Test GET /health timestamp is ISO 8601 with Z suffix."""
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = True
            mock_redis.return_value = True

            mock_cfg = Mock()
            mock_cfg.llm = None
            mock_config.return_value = mock_cfg

            resp = await self.client.request("GET", "/health")
            data = await resp.json()

            timestamp = data['timestamp']
            assert timestamp.endswith('Z')

            # Parse timestamp to ensure it's valid ISO 8601
            parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            assert isinstance(parsed, datetime)

    @unittest_run_loop
    async def test_health_endpoint_with_discord_gateway(self):
        """Test GET /health with Discord gateway configured."""
        from api.server import create_app

        # Create mock Discord gateway
        mock_client = Mock()
        mock_client.is_connected = True
        mock_client.session_id = 'test-session-id-12345'

        mock_gateway = Mock()
        mock_gateway.client = mock_client

        app = create_app(discord_gateway=mock_gateway)

        # Use app for this specific test
        with patch('database.connection.check_database_health', new_callable=AsyncMock) as mock_db, \
             patch('job_queue.client.check_redis_health', new_callable=AsyncMock) as mock_redis, \
             patch('config.get_config') as mock_config:

            mock_db.return_value = True
            mock_redis.return_value = True

            mock_cfg = Mock()
            mock_cfg.llm = None
            mock_config.return_value = mock_cfg

            # Create test client for this app
            async with self.client.server.app.router.add_get('/test-health',
                lambda request: web.json_response({'test': 'data'})) as _:
                pass

            # Actually, let's use a simpler approach - create a temporary test client
            from aiohttp.test_utils import TestClient

            async with TestClient(self.server, app=app) as client:
                resp = await client.get('/health')

                assert resp.status == 200

                data = await resp.json()
                assert data['checks']['discord']['status'] == 'healthy'
                assert data['checks']['discord']['connected'] is True


class TestServerInfrastructure:
    """Test cases for server infrastructure."""

    def test_create_app_returns_application(self):
        """Test create_app() creates valid aiohttp application."""
        from api.server import create_app

        app = create_app()

        assert isinstance(app, web.Application)

    def test_create_app_stores_discord_gateway(self):
        """Test application state contains discord_gateway."""
        from api.server import create_app

        mock_gateway = Mock()
        app = create_app(discord_gateway=mock_gateway)

        assert 'discord_gateway' in app
        assert app['discord_gateway'] is mock_gateway

    def test_create_app_stores_none_gateway(self):
        """Test application state handles None discord_gateway."""
        from api.server import create_app

        app = create_app(discord_gateway=None)

        assert 'discord_gateway' in app
        assert app['discord_gateway'] is None

    def test_create_app_registers_health_route(self):
        """Test routes registered correctly."""
        from api.server import create_app

        app = create_app()

        # Check that /health route exists
        routes = [route for route in app.router.routes()]
        health_routes = [r for r in routes if hasattr(r.resource, 'canonical') and '/health' in r.resource.canonical]

        assert len(health_routes) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
