"""
Prometheus Metrics Definitions and Collection.

This module defines and manages all Prometheus metrics for the moderator application.
Metrics include:
- Counters: messages_total, tasks_total, replies_total, llm_requests_total, errors_total
- Histograms: response_time_seconds
- Gauges: open_tasks_count, allowlist_size

All metrics are collected and exposed via the /metrics endpoint.
"""

import time
import asyncio
from functools import wraps
from typing import Optional, Callable, Any
from contextlib import asynccontextmanager

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from aiohttp import web
from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Counter Metrics
# =============================================================================

# Messages processed by platform
messages_total = Counter(
    'messages_total',
    'Total messages processed',
    ['platform']  # Labels: discord, telegram
)

# Tasks created by status
tasks_total = Counter(
    'tasks_total',
    'Total tasks created',
    ['status']  # Labels: pending, approved, rejected, muted, error
)

# Replies sent by platform
replies_total = Counter(
    'replies_total',
    'Total replies sent',
    ['platform']  # Labels: discord, telegram
)

# LLM requests by provider
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'status']  # Labels: provider (openai, anthropic), status (success, error)
)

# Errors by type
errors_total = Counter(
    'errors_total',
    'Total errors encountered',
    ['error_type']  # Labels: database, discord, telegram, llm, validation, unknown
)


# =============================================================================
# Histogram Metrics
# =============================================================================

# Response time distribution (in seconds)
response_time_seconds = Histogram(
    'response_time_seconds',
    'Response time distribution in seconds',
    ['operation'],  # Labels: message_processing, llm_request, database_query
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0)
)


# =============================================================================
# Gauge Metrics
# =============================================================================

# Current open tasks count
open_tasks_count = Gauge(
    'open_tasks_count',
    'Current number of open tasks (pending status)'
)

# Current allowlist size
allowlist_size = Gauge(
    'allowlist_size',
    'Current number of channels in allowlist',
    ['platform']  # Labels: discord, telegram
)

# Application info
app_info = Gauge(
    'app_info',
    'Application information',
    ['version', 'environment']
)


# =============================================================================
# Metric Collection Functions
# =============================================================================

def increment_messages(platform: str):
    """
    Increment message counter for a platform.

    Args:
        platform: Platform name (discord, telegram)
    """
    try:
        messages_total.labels(platform=platform).inc()
        logger.debug(f"Incremented messages_total for platform: {platform}")
    except Exception as e:
        logger.error(f"Error incrementing messages_total: {e}", exc_info=True)


def increment_tasks(status: str):
    """
    Increment task counter for a status.

    Args:
        status: Task status (pending, approved, rejected, muted, error)
    """
    try:
        tasks_total.labels(status=status).inc()
        logger.debug(f"Incremented tasks_total for status: {status}")
    except Exception as e:
        logger.error(f"Error incrementing tasks_total: {e}", exc_info=True)


def increment_replies(platform: str):
    """
    Increment reply counter for a platform.

    Args:
        platform: Platform name (discord, telegram)
    """
    try:
        replies_total.labels(platform=platform).inc()
        logger.debug(f"Incremented replies_total for platform: {platform}")
    except Exception as e:
        logger.error(f"Error incrementing replies_total: {e}", exc_info=True)


def increment_llm_requests(provider: str, status: str = "success"):
    """
    Increment LLM request counter.

    Args:
        provider: LLM provider (openai, anthropic)
        status: Request status (success, error)
    """
    try:
        llm_requests_total.labels(provider=provider, status=status).inc()
        logger.debug(f"Incremented llm_requests_total for provider: {provider}, status: {status}")
    except Exception as e:
        logger.error(f"Error incrementing llm_requests_total: {e}", exc_info=True)


def increment_errors(error_type: str):
    """
    Increment error counter for an error type.

    Args:
        error_type: Error type (database, discord, telegram, llm, validation, unknown)
    """
    try:
        errors_total.labels(error_type=error_type).inc()
        logger.debug(f"Incremented errors_total for type: {error_type}")
    except Exception as e:
        logger.error(f"Error incrementing errors_total: {e}", exc_info=True)


def observe_response_time(operation: str, duration_seconds: float):
    """
    Observe response time for an operation.

    Args:
        operation: Operation name (message_processing, llm_request, database_query)
        duration_seconds: Duration in seconds
    """
    try:
        response_time_seconds.labels(operation=operation).observe(duration_seconds)
        logger.debug(f"Observed response_time for {operation}: {duration_seconds:.3f}s")
    except Exception as e:
        logger.error(f"Error observing response_time: {e}", exc_info=True)


def set_open_tasks(count: int):
    """
    Set current open tasks count.

    Args:
        count: Number of open tasks
    """
    try:
        open_tasks_count.set(count)
        logger.debug(f"Set open_tasks_count to: {count}")
    except Exception as e:
        logger.error(f"Error setting open_tasks_count: {e}", exc_info=True)


def set_allowlist_size(platform: str, count: int):
    """
    Set allowlist size for a platform.

    Args:
        platform: Platform name (discord, telegram)
        count: Number of channels in allowlist
    """
    try:
        allowlist_size.labels(platform=platform).set(count)
        logger.debug(f"Set allowlist_size for {platform} to: {count}")
    except Exception as e:
        logger.error(f"Error setting allowlist_size: {e}", exc_info=True)


def set_app_info(version: str, environment: str):
    """
    Set application info gauge.

    Args:
        version: Application version
        environment: Environment name (production, development)
    """
    try:
        app_info.labels(version=version, environment=environment).set(1)
        logger.debug(f"Set app_info: version={version}, environment={environment}")
    except Exception as e:
        logger.error(f"Error setting app_info: {e}", exc_info=True)


# =============================================================================
# Decorators for Automatic Metric Collection
# =============================================================================

def track_response_time(operation: str):
    """
    Decorator to automatically track response time for async functions.

    Args:
        operation: Operation name for the metric label

    Example:
        @track_response_time('message_processing')
        async def process_message(msg):
            # ... processing logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.perf_counter() - start_time
                observe_response_time(operation, duration)
        return wrapper
    return decorator


@asynccontextmanager
async def track_operation(operation: str):
    """
    Context manager to track operation response time.

    Args:
        operation: Operation name for the metric label

    Example:
        async with track_operation('database_query'):
            result = await execute_query()
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        observe_response_time(operation, duration)


# =============================================================================
# Gauge Update Functions (Background Tasks)
# =============================================================================

async def update_gauge_metrics():
    """
    Update gauge metrics from database.

    This function queries the database to update gauge metrics like:
    - open_tasks_count: Number of tasks with 'pending' status
    - allowlist_size: Number of channels in allowlist by platform

    Should be called periodically from a background task.
    """
    try:
        from database.connection import get_asyncpg_pool
        from database.dao import AsyncTaskDAO

        pool = get_asyncpg_pool()
        if not pool:
            logger.warning("Database pool not available for gauge metrics update")
            return

        async with pool.acquire() as conn:
            # Update open tasks count
            try:
                result = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM tasks WHERE status = 'pending'"
                )
                if result:
                    set_open_tasks(result['count'])
            except Exception as e:
                logger.error(f"Error updating open_tasks_count: {e}", exc_info=True)
                increment_errors('database')

            # Update allowlist size for Discord
            try:
                result = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM channels_allowlist WHERE platform = 'discord'"
                )
                if result:
                    set_allowlist_size('discord', result['count'])
            except Exception as e:
                logger.error(f"Error updating allowlist_size for discord: {e}", exc_info=True)
                increment_errors('database')

            # Update allowlist size for Telegram
            try:
                result = await conn.fetchrow(
                    "SELECT COUNT(*) as count FROM channels_allowlist WHERE platform = 'telegram'"
                )
                if result:
                    set_allowlist_size('telegram', result['count'])
            except Exception as e:
                logger.error(f"Error updating allowlist_size for telegram: {e}", exc_info=True)
                increment_errors('database')

    except Exception as e:
        logger.error(f"Error updating gauge metrics: {e}", exc_info=True)
        increment_errors('unknown')


async def gauge_metrics_updater(interval: int = 60):
    """
    Background task that periodically updates gauge metrics.

    Args:
        interval: Update interval in seconds (default: 60)
    """
    logger.info(f"Starting gauge metrics updater with {interval}s interval")

    while True:
        try:
            await update_gauge_metrics()
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Gauge metrics updater cancelled")
            break
        except Exception as e:
            logger.error(f"Error in gauge metrics updater: {e}", exc_info=True)
            await asyncio.sleep(interval)


# =============================================================================
# HTTP Endpoint Handler
# =============================================================================

async def metrics_handler(request: web.Request) -> web.Response:
    """
    Handle GET /metrics requests.

    Returns Prometheus-formatted metrics in text format.

    Returns:
        web.Response: Response with Prometheus metrics in text/plain format
    """
    try:
        # Generate latest metrics in Prometheus text format
        metrics_output = generate_latest()

        return web.Response(
            body=metrics_output,
            content_type=CONTENT_TYPE_LATEST,
            status=200
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        increment_errors('unknown')
        return web.Response(
            text=f"Error generating metrics: {str(e)}",
            status=500
        )


# =============================================================================
# Initialization
# =============================================================================

def init_metrics(version: str = "1.0.0", environment: str = "production"):
    """
    Initialize metrics with application metadata.

    Args:
        version: Application version
        environment: Environment name (production, development)
    """
    logger.info(f"Initializing Prometheus metrics (version={version}, env={environment})")
    set_app_info(version, environment)
    logger.info("Prometheus metrics initialized")
