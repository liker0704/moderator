"""
Test suite for ARQ worker system.

Tests worker configuration, lifecycle hooks, and task handler registration.
Mock-based tests for worker configuration and lifecycle. Integration test
requirements are documented for full ARQ testing.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from job_queue.worker import (
    WorkerConfig,
    startup,
    shutdown,
    job_started,
    job_finished,
    job_failed,
    create_worker_settings,
    create_worker,
)


class TestWorkerConfig:
    """Tests for WorkerConfig dataclass."""

    def test_worker_config_defaults(self):
        """Test WorkerConfig dataclass with default values."""
        config = WorkerConfig(
            redis_host="localhost",
            redis_port=6379
        )

        assert config.redis_host == "localhost"
        assert config.redis_port == 6379
        assert config.redis_password is None
        assert config.redis_db == 0
        assert config.max_jobs == 10
        assert config.job_timeout == 300
        assert config.keep_result == 3600
        assert config.max_tries == 3
        assert config.health_check_interval == 60

    def test_worker_config_custom_values(self):
        """Test WorkerConfig with custom values."""
        config = WorkerConfig(
            redis_host="redis.example.com",
            redis_port=6380,
            redis_password="secret123",
            redis_db=1,
            max_jobs=20,
            job_timeout=600,
            keep_result=7200,
            max_tries=5,
            health_check_interval=120
        )

        assert config.redis_host == "redis.example.com"
        assert config.redis_port == 6380
        assert config.redis_password == "secret123"
        assert config.redis_db == 1
        assert config.max_jobs == 20
        assert config.job_timeout == 600
        assert config.keep_result == 7200
        assert config.max_tries == 5
        assert config.health_check_interval == 120

    def test_worker_config_partial_override(self):
        """Test WorkerConfig with partial custom values."""
        config = WorkerConfig(
            redis_host="localhost",
            redis_port=6379,
            max_jobs=15
        )

        assert config.max_jobs == 15
        assert config.job_timeout == 300  # Default
        assert config.max_tries == 3  # Default


class TestLifecycleHooks:
    """Tests for worker lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_worker_startup_success(self):
        """Test worker startup initializes resources successfully."""
        ctx = {}

        with patch('job_queue.worker.get_config') as mock_config, \
             patch('job_queue.worker.init_asyncpg_pool') as mock_init_db, \
             patch('job_queue.worker.logger') as mock_logger:

            # Mock config
            mock_cfg = MagicMock()
            mock_cfg.database.connection_string = "postgresql://test:test@localhost:5432/test"
            mock_config.return_value = mock_cfg

            # Mock database init
            mock_pool = AsyncMock()
            mock_init_db.return_value = mock_pool

            # Call startup hook
            await startup(ctx)

            # Verify database pool initialized with correct parameters
            mock_init_db.assert_called_once_with(
                database_url="postgresql://test:test@localhost:5432/test",
                min_size=5,
                max_size=15
            )

            # Verify context populated with config
            assert 'config' in ctx
            assert ctx['config'] == mock_cfg

            # Verify logging
            assert mock_logger.info.call_count >= 2  # Startup and complete messages

    @pytest.mark.asyncio
    async def test_worker_startup_database_failure(self):
        """Test worker startup handles database connection failure."""
        ctx = {}

        with patch('job_queue.worker.get_config') as mock_config, \
             patch('job_queue.worker.init_asyncpg_pool') as mock_init_db, \
             patch('job_queue.worker.logger') as mock_logger:

            mock_cfg = MagicMock()
            mock_cfg.database.connection_string = "postgresql://invalid"
            mock_config.return_value = mock_cfg

            # Simulate database connection failure
            mock_init_db.side_effect = Exception("Database connection failed")

            # Startup should raise the exception
            with pytest.raises(Exception) as exc_info:
                await startup(ctx)

            assert "Database connection failed" in str(exc_info.value)

            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_startup_config_failure(self):
        """Test worker startup handles missing configuration."""
        ctx = {}

        with patch('job_queue.worker.get_config') as mock_config, \
             patch('job_queue.worker.logger') as mock_logger:

            mock_config.side_effect = Exception("Config not found")

            # Should handle gracefully and raise
            with pytest.raises(Exception) as exc_info:
                await startup(ctx)

            assert "Config not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_worker_shutdown_success(self):
        """Test worker shutdown cleans up resources successfully."""
        ctx = {'config': MagicMock()}

        with patch('job_queue.worker.close_asyncpg_pool') as mock_close_db, \
             patch('job_queue.worker.logger') as mock_logger:

            mock_close_db.return_value = None

            await shutdown(ctx)

            # Verify cleanup called
            mock_close_db.assert_called_once()

            # Verify logging
            assert mock_logger.info.call_count >= 2  # Shutdown and complete messages

    @pytest.mark.asyncio
    async def test_worker_shutdown_handles_errors(self):
        """Test worker shutdown handles cleanup errors gracefully."""
        ctx = {}

        with patch('job_queue.worker.close_asyncpg_pool') as mock_close_db, \
             patch('job_queue.worker.logger') as mock_logger:

            mock_close_db.side_effect = Exception("Cleanup failed")

            # Should not raise, just log error
            await shutdown(ctx)

            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_shutdown_no_pool(self):
        """Test worker shutdown handles missing database pool."""
        ctx = {}  # No resources to clean up

        with patch('job_queue.worker.close_asyncpg_pool') as mock_close_db:
            # Should not raise
            await shutdown(ctx)

            # Cleanup should still be attempted
            mock_close_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_started_hook(self):
        """Test job_started hook logs job start correctly."""
        ctx = {
            'job_id': 'test-job-123',
            'job_name': 'process_discord_message',
            'job_try': 1
        }

        with patch('job_queue.worker.logger') as mock_logger:
            await job_started(ctx)

            # Verify logging with correct extra data
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert 'process_discord_message' in call_args[0][0]
            assert call_args[1]['extra']['job_id'] == 'test-job-123'
            assert call_args[1]['extra']['job_name'] == 'process_discord_message'

    @pytest.mark.asyncio
    async def test_job_started_missing_context(self):
        """Test job_started handles missing context gracefully."""
        ctx = {}  # No job_id or job_name

        with patch('job_queue.worker.logger') as mock_logger:
            # Should not raise
            await job_started(ctx)

            # Should log with 'unknown'
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]['extra']['job_id'] == 'unknown'
            assert call_args[1]['extra']['job_name'] == 'unknown'

    @pytest.mark.asyncio
    async def test_job_finished_hook(self):
        """Test job_finished hook logs job completion correctly."""
        ctx = {
            'job_id': 'test-job-456',
            'job_name': 'post_to_telegram',
            'job_result': {'status': 'success'}
        }

        with patch('job_queue.worker.logger') as mock_logger:
            await job_finished(ctx)

            # Verify logging
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert 'post_to_telegram' in call_args[0][0]
            assert call_args[1]['extra']['job_id'] == 'test-job-456'

    @pytest.mark.asyncio
    async def test_job_failed_hook(self):
        """Test job_failed hook logs error details correctly."""
        ctx = {
            'job_id': 'test-job-789',
            'job_name': 'process_telegram_message',
            'job_error': Exception('Task processing failed'),
            'job_try': 2
        }

        with patch('job_queue.worker.logger') as mock_logger:
            await job_failed(ctx)

            # Verify error logging
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert 'process_telegram_message' in call_args[0][0]
            assert 'Task processing failed' in call_args[0][0]
            assert call_args[1]['extra']['job_id'] == 'test-job-789'

    @pytest.mark.asyncio
    async def test_job_failed_missing_error(self):
        """Test job_failed handles missing error info gracefully."""
        ctx = {
            'job_id': 'test-job-999',
            'job_name': 'send_reminder'
        }

        with patch('job_queue.worker.logger') as mock_logger:
            await job_failed(ctx)

            # Should log with 'unknown error'
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert 'unknown error' in call_args[0][0]


class TestWorkerSettings:
    """Tests for worker settings creation."""

    def test_create_worker_settings_basic(self):
        """Test worker settings creation with basic configuration."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify settings class created
            assert hasattr(WorkerSettings, 'redis_settings')
            assert hasattr(WorkerSettings, 'functions')
            assert hasattr(WorkerSettings, 'max_jobs')
            assert hasattr(WorkerSettings, 'job_timeout')
            assert hasattr(WorkerSettings, 'on_startup')
            assert hasattr(WorkerSettings, 'on_shutdown')

    def test_worker_settings_redis_config(self):
        """Test worker settings uses correct Redis configuration."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "redis.example.com"
            mock_cfg.redis.port = 6380
            mock_cfg.redis.password = "secret123"
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify Redis settings
            assert WorkerSettings.redis_settings.host == "redis.example.com"
            assert WorkerSettings.redis_settings.port == 6380
            assert WorkerSettings.redis_settings.password == "secret123"
            assert WorkerSettings.redis_settings.database == 0  # Default

    def test_worker_settings_job_config(self):
        """Test worker settings includes correct job configuration."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify job settings
            assert WorkerSettings.max_jobs == 10
            assert WorkerSettings.job_timeout == 300
            assert WorkerSettings.keep_result == 3600
            assert WorkerSettings.max_tries == 3
            assert WorkerSettings.health_check_interval == 60

    def test_worker_settings_queue_config(self):
        """Test worker settings includes queue configuration."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify queue settings
            assert WorkerSettings.queue_name == "moderator:queue"
            assert WorkerSettings.allow_abort_jobs is True
            assert WorkerSettings.log_results is True

    def test_worker_settings_lifecycle_hooks(self):
        """Test worker settings includes lifecycle hooks."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify lifecycle hooks
            assert WorkerSettings.on_startup == startup
            assert WorkerSettings.on_shutdown == shutdown

    def test_worker_settings_missing_redis_config(self):
        """Test worker settings raises error when Redis config missing."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis = None
            mock_config.return_value = mock_cfg

            # Should raise RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                create_worker_settings()

            assert "Redis configuration not available" in str(exc_info.value)


class TestTaskHandlerRegistration:
    """Tests for task handler registration."""

    def test_worker_registers_all_handlers(self):
        """Test worker registers all required task handlers."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify 6 handlers registered
            assert len(WorkerSettings.functions) == 6

    def test_process_discord_message_handler_registered(self):
        """Test process_discord_message handler is registered."""
        from job_queue.handlers import process_discord_message

        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            # Verify handler in functions list
            assert process_discord_message in WorkerSettings.functions

            # Verify it's a coroutine
            assert asyncio.iscoroutinefunction(process_discord_message)

    def test_process_telegram_message_handler_registered(self):
        """Test process_telegram_message handler is registered."""
        from job_queue.handlers import process_telegram_message

        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            assert process_telegram_message in WorkerSettings.functions
            assert asyncio.iscoroutinefunction(process_telegram_message)

    def test_post_to_discord_handler_registered(self):
        """Test post_to_discord handler is registered."""
        from job_queue.handlers import post_to_discord

        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            assert post_to_discord in WorkerSettings.functions
            assert asyncio.iscoroutinefunction(post_to_discord)

    def test_post_to_telegram_handler_registered(self):
        """Test post_to_telegram handler is registered."""
        from job_queue.handlers import post_to_telegram

        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            assert post_to_telegram in WorkerSettings.functions
            assert asyncio.iscoroutinefunction(post_to_telegram)

    def test_generate_llm_response_handler_registered(self):
        """Test generate_llm_response handler is registered."""
        from job_queue.handlers import generate_llm_response

        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            assert generate_llm_response in WorkerSettings.functions
            assert asyncio.iscoroutinefunction(generate_llm_response)

    def test_send_reminder_handler_registered(self):
        """Test send_reminder handler is registered."""
        from job_queue.handlers import send_reminder

        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            WorkerSettings = create_worker_settings()

            assert send_reminder in WorkerSettings.functions
            assert asyncio.iscoroutinefunction(send_reminder)


class TestWorkerCreation:
    """Tests for worker instance creation."""

    @pytest.mark.asyncio
    async def test_create_worker_instance(self):
        """Test create_worker creates a valid Worker instance."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            worker = await create_worker()

            # Verify worker instance created
            assert worker is not None
            # Worker attributes depend on ARQ's Worker class structure

    @pytest.mark.asyncio
    async def test_create_worker_uses_settings(self):
        """Test create_worker uses correct settings."""
        with patch('job_queue.worker.get_config') as mock_config, \
             patch('job_queue.worker.Worker') as mock_worker_class:

            mock_cfg = MagicMock()
            mock_cfg.redis.host = "localhost"
            mock_cfg.redis.port = 6379
            mock_cfg.redis.password = None
            mock_config.return_value = mock_cfg

            mock_worker_instance = AsyncMock()
            mock_worker_class.return_value = mock_worker_instance

            worker = await create_worker()

            # Verify Worker class was called
            mock_worker_class.assert_called_once()

            # Verify settings passed to Worker
            call_kwargs = mock_worker_class.call_args[1]
            assert 'functions' in call_kwargs
            assert 'redis_settings' in call_kwargs
            assert 'max_jobs' in call_kwargs
            assert 'on_startup' in call_kwargs
            assert 'on_shutdown' in call_kwargs


class TestWorkerErrorHandling:
    """Tests for worker error handling."""

    @pytest.mark.asyncio
    async def test_startup_handles_missing_config(self):
        """Test startup handles missing configuration gracefully."""
        ctx = {}

        with patch('job_queue.worker.get_config') as mock_config:
            mock_config.side_effect = Exception("Config not found")

            with pytest.raises(Exception) as exc_info:
                await startup(ctx)

            assert "Config not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_shutdown_handles_no_pool(self):
        """Test shutdown handles missing database pool gracefully."""
        ctx = {}

        with patch('job_queue.worker.close_asyncpg_pool') as mock_close:
            # Should not raise even if pool doesn't exist
            await shutdown(ctx)

            # Should still attempt cleanup
            mock_close.assert_called_once()

    def test_create_worker_settings_handles_no_redis(self):
        """Test create_worker_settings handles missing Redis config."""
        with patch('job_queue.worker.get_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.redis = None
            mock_config.return_value = mock_cfg

            with pytest.raises(RuntimeError) as exc_info:
                create_worker_settings()

            assert "Redis configuration not available" in str(exc_info.value)
            assert "REDIS_HOST" in str(exc_info.value)


# Integration test documentation
class TestWorkerIntegrationRequirements:
    """
    INTEGRATION TESTS - Require Redis + ARQ

    These tests require a running Redis instance and are marked for
    integration testing in CI/CD pipelines.

    Setup for CI/CD:
    1. Start Redis container:
       docker run -d --name redis-test -p 6380:6379 redis:7-alpine

    2. Set environment variables:
       export REDIS_HOST=localhost
       export REDIS_PORT=6380

    3. Run worker in burst mode (process all jobs then exit):
       python -m arq job_queue.worker.WorkerSettings --burst

    4. Run integration tests:
       pytest tests/test_worker.py -v -m integration

    To run these tests locally:
       pytest tests/test_worker.py::TestWorkerIntegrationRequirements -v --run-integration
    """

    @pytest.mark.skip(reason="Requires Redis + ARQ - integration test")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_worker_processes_enqueued_tasks(self):
        """
        Integration test: Verify worker processes enqueued tasks.

        This test requires:
        - Redis running
        - ARQ worker running
        - Ability to enqueue and monitor jobs

        Test steps:
        1. Enqueue a test task
        2. Start worker in burst mode
        3. Verify task was processed
        4. Check result in Redis
        """
        # Implementation requires full ARQ + Redis setup
        pass

    @pytest.mark.skip(reason="Requires Redis + ARQ - integration test")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_worker_retries_on_failure(self):
        """
        Integration test: Verify worker retries failed tasks.

        This test requires:
        - Redis running
        - ARQ worker running
        - Mock handler that fails initially

        Test steps:
        1. Enqueue task that will fail
        2. Verify task is retried (max_tries=3)
        3. Check retry count in job info
        4. Verify final failure is logged
        """
        # Implementation requires full ARQ + Redis setup
        pass

    @pytest.mark.skip(reason="Requires Redis + ARQ - integration test")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_worker_lifecycle_hooks_execute(self):
        """
        Integration test: Verify lifecycle hooks execute correctly.

        This test requires:
        - Redis running
        - Database connection available
        - Full worker startup/shutdown cycle

        Test steps:
        1. Start worker
        2. Verify on_startup hook executed
        3. Verify database pool initialized
        4. Stop worker
        5. Verify on_shutdown hook executed
        6. Verify resources cleaned up
        """
        # Implementation requires full ARQ + Redis setup
        pass

    @pytest.mark.skip(reason="Requires Redis + ARQ - integration test")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_worker_handles_concurrent_jobs(self):
        """
        Integration test: Verify worker handles concurrent jobs.

        This test requires:
        - Redis running
        - ARQ worker with max_jobs > 1

        Test steps:
        1. Enqueue multiple tasks simultaneously
        2. Verify worker processes them concurrently
        3. Check max_jobs limit is respected
        4. Verify all jobs complete successfully
        """
        # Implementation requires full ARQ + Redis setup
        pass

    @pytest.mark.skip(reason="Requires Redis + ARQ - integration test")
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_worker_job_timeout(self):
        """
        Integration test: Verify worker respects job timeout.

        This test requires:
        - Redis running
        - ARQ worker with job_timeout configured
        - Handler that runs longer than timeout

        Test steps:
        1. Enqueue long-running task
        2. Verify worker times out after job_timeout seconds
        3. Check task status shows timeout
        4. Verify retry is attempted
        """
        # Implementation requires full ARQ + Redis setup
        pass
