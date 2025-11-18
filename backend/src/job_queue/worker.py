"""
ARQ worker configuration and initialization.

This module handles:
- ARQ worker settings and configuration
- Task function registration
- Retry policies and error handling
- Lifecycle hooks (startup, shutdown, before/after job)
- Connection management for worker processes
- Logging and monitoring integration

The worker processes tasks from Redis queue asynchronously,
providing reliable background job execution with automatic retries.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from arq import create_pool, cron
from arq.connections import RedisSettings, ArqRedis
from arq.worker import Worker

from config import get_config
from utils.logger import get_logger
from database.connection import init_asyncpg_pool, close_asyncpg_pool

# Import task handlers
from queue.handlers import (
    process_discord_message,
    process_telegram_message,
    post_to_discord,
    post_to_telegram,
    generate_llm_response,
    send_reminder,
)

logger = get_logger(__name__)


@dataclass
class WorkerConfig:
    """
    Worker configuration dataclass.

    Attributes:
        redis_host: Redis server hostname
        redis_port: Redis server port
        redis_password: Optional Redis password
        redis_db: Redis database number
        max_jobs: Maximum number of concurrent jobs
        job_timeout: Job execution timeout in seconds
        keep_result: How long to keep job results in seconds
        max_tries: Maximum number of retry attempts
        health_check_interval: Health check interval in seconds
    """

    redis_host: str
    redis_port: int
    redis_password: Optional[str] = None
    redis_db: int = 0
    max_jobs: int = 10
    job_timeout: int = 300  # 5 minutes
    keep_result: int = 3600  # 1 hour
    max_tries: int = 3
    health_check_interval: int = 60


async def startup(ctx: dict):
    """
    Worker startup hook.

    Initializes connections and resources needed by worker tasks.

    Args:
        ctx: Worker context dictionary for sharing resources
    """
    logger.info("Worker starting up...")

    try:
        # Initialize database connection pool
        config = get_config()
        await init_asyncpg_pool(
            database_url=config.database.connection_string,
            min_size=5,
            max_size=15
        )
        logger.info("Database connection pool initialized")

        # Store config in context for task access
        ctx["config"] = config

        logger.info("Worker startup complete")

    except Exception as e:
        logger.error(f"Worker startup failed: {e}", exc_info=True)
        raise


async def shutdown(ctx: dict):
    """
    Worker shutdown hook.

    Cleans up connections and resources when worker stops.

    Args:
        ctx: Worker context dictionary
    """
    logger.info("Worker shutting down...")

    try:
        # Close database connection pool
        await close_asyncpg_pool()
        logger.info("Database connection pool closed")

        logger.info("Worker shutdown complete")

    except Exception as e:
        logger.error(f"Worker shutdown error: {e}", exc_info=True)


async def job_started(ctx: dict):
    """
    Hook called before each job starts.

    Args:
        ctx: Worker context dictionary
    """
    job_id = ctx.get("job_id", "unknown")
    job_name = ctx.get("job_name", "unknown")
    logger.info(
        f"Job started: {job_name}",
        extra={"job_id": job_id, "job_name": job_name}
    )


async def job_finished(ctx: dict):
    """
    Hook called after each job completes.

    Args:
        ctx: Worker context dictionary
    """
    job_id = ctx.get("job_id", "unknown")
    job_name = ctx.get("job_name", "unknown")
    logger.info(
        f"Job finished: {job_name}",
        extra={"job_id": job_id, "job_name": job_name}
    )


async def job_failed(ctx: dict):
    """
    Hook called when a job fails.

    Args:
        ctx: Worker context dictionary
    """
    job_id = ctx.get("job_id", "unknown")
    job_name = ctx.get("job_name", "unknown")
    error = ctx.get("job_error", "unknown error")
    logger.error(
        f"Job failed: {job_name} - {error}",
        extra={"job_id": job_id, "job_name": job_name, "error": str(error)}
    )


def create_worker_settings() -> type:
    """
    Create ARQ worker settings class.

    Returns:
        WorkerSettings class with all configuration
    """
    config = get_config()

    # Get Redis configuration
    if config.redis:
        redis_host = config.redis.host
        redis_port = config.redis.port
        redis_password = config.redis.password
    else:
        raise RuntimeError(
            "Redis configuration not available. "
            "Set REDIS_HOST environment variable."
        )

    # Create worker configuration
    worker_config = WorkerConfig(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_password=redis_password,
    )

    class WorkerSettings:
        """
        ARQ Worker Settings.

        This class defines the configuration and task functions
        for the ARQ worker process.
        """

        # Redis connection settings
        redis_settings = RedisSettings(
            host=worker_config.redis_host,
            port=worker_config.redis_port,
            password=worker_config.redis_password if worker_config.redis_password else None,
            database=worker_config.redis_db,
        )

        # Task functions to be executed by worker
        functions = [
            process_discord_message,
            process_telegram_message,
            post_to_discord,
            post_to_telegram,
            generate_llm_response,
            send_reminder,
        ]

        # Worker behavior settings
        max_jobs = worker_config.max_jobs
        job_timeout = worker_config.job_timeout
        keep_result = worker_config.keep_result
        max_tries = worker_config.max_tries
        health_check_interval = worker_config.health_check_interval

        # Lifecycle hooks
        on_startup = startup
        on_shutdown = shutdown

        # Queue name (default is 'arq:queue')
        queue_name = "moderator:queue"

        # Allow abort jobs
        allow_abort_jobs = True

        # Log all jobs
        log_results = True

    return WorkerSettings


async def create_worker() -> Worker:
    """
    Create and configure ARQ worker instance.

    Returns:
        Configured Worker instance

    Example:
        >>> worker = await create_worker()
        >>> await worker.run()
    """
    WorkerSettings = create_worker_settings()

    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
        keep_result=WorkerSettings.keep_result,
        max_tries=WorkerSettings.max_tries,
        health_check_interval=WorkerSettings.health_check_interval,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        queue_name=WorkerSettings.queue_name,
        allow_abort_jobs=WorkerSettings.allow_abort_jobs,
        log_results=WorkerSettings.log_results,
    )

    return worker


# For ARQ CLI: python -m arq src.queue.worker.WorkerSettings
WorkerSettings = create_worker_settings()


if __name__ == "__main__":
    """
    Run worker directly using asyncio.

    Alternative to: python -m arq src.queue.worker.WorkerSettings
    """
    async def main():
        worker = await create_worker()
        await worker.run()

    asyncio.run(main())
