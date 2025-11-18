"""Health check endpoint handler and logic."""

import time
from datetime import datetime
from typing import Dict, Any, Optional

from aiohttp import web
from utils.logger import get_logger

logger = get_logger(__name__)


async def health_check_handler(request: web.Request) -> web.Response:
    """
    Handle GET /health requests.

    Returns JSON with overall health status and individual service checks.

    HTTP Status Codes:
        200 OK: Overall status is "healthy"
        503 Service Unavailable: Overall status is "unhealthy" or "degraded"
    """
    # Get discord_gateway from app state
    discord_gateway = request.app.get('discord_gateway')

    # Perform all health checks
    checks = await perform_health_checks(discord_gateway)

    # Determine overall status
    overall_status = _determine_overall_status(checks)

    # Build response
    response_data = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks,
        "version": "0.1.0-mvp"
    }

    # Return 200 for healthy, 503 for unhealthy/degraded
    status_code = 200 if overall_status == "healthy" else 503

    return web.json_response(response_data, status=status_code)


async def perform_health_checks(discord_gateway=None) -> Dict[str, Any]:
    """
    Perform all health checks.

    Args:
        discord_gateway: DiscordGatewayManager instance (optional)

    Returns:
        dict with health check results for each service
    """
    checks = {}

    # Discord check
    checks['discord'] = await _check_discord(discord_gateway)

    # Database check
    checks['database'] = await _check_database()

    # Redis check
    checks['redis'] = await _check_redis()

    # LLM check (optional)
    checks['llm'] = await _check_llm()

    return checks


async def _check_discord(discord_gateway) -> Dict[str, Any]:
    """
    Check Discord Gateway connection status.

    Returns:
        {
            "status": "healthy" | "unhealthy" | "not_configured",
            "connected": bool,
            "session_id": str (truncated) or None
        }
    """
    try:
        if discord_gateway is None:
            return {
                "status": "not_configured",
                "connected": False,
                "message": "Discord integration not enabled"
            }

        # Access discord_gateway.client safely
        if not hasattr(discord_gateway, 'client') or discord_gateway.client is None:
            return {
                "status": "unhealthy",
                "connected": False,
                "message": "Discord client not initialized"
            }

        is_connected = discord_gateway.client.is_connected
        has_session = discord_gateway.client.session_id is not None

        status = "healthy" if (is_connected and has_session) else "unhealthy"

        result = {
            "status": status,
            "connected": is_connected
        }

        if is_connected and has_session:
            # Truncate session_id for security
            result["session_id"] = discord_gateway.client.session_id[:8] + "..."

        return result

    except Exception as e:
        logger.error(f"Discord health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e)
        }


async def _check_database() -> Dict[str, Any]:
    """
    Check PostgreSQL database connection.

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "response_time_ms": float
        }
    """
    start_time = time.perf_counter()

    try:
        from database.connection import check_database_health

        is_healthy = await check_database_health()

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "response_time_ms": round(elapsed_ms, 2)
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "response_time_ms": round(elapsed_ms, 2),
            "error": str(e)
        }


async def _check_redis() -> Dict[str, Any]:
    """
    Check Redis connection.

    Returns:
        {
            "status": "healthy" | "unhealthy" | "not_configured",
            "response_time_ms": float (if applicable)
        }
    """
    start_time = time.perf_counter()

    try:
        from job_queue.client import check_redis_health

        is_healthy = await check_redis_health()

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "response_time_ms": round(elapsed_ms, 2)
        }

    except RuntimeError as e:
        # Redis not initialized (not_configured)
        if "not initialized" in str(e).lower():
            return {
                "status": "not_configured",
                "message": "Redis client not initialized"
            }
        raise

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Redis health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "response_time_ms": round(elapsed_ms, 2),
            "error": str(e)
        }


async def _check_llm() -> Dict[str, Any]:
    """
    Check LLM configuration status.

    NOTE: Does not test API connectivity to avoid costs.

    Returns:
        {
            "status": "configured" | "not_configured",
            "provider": str | None,
            "model": str | None
        }
    """
    try:
        from config import get_config
        config = get_config()

        if not config.llm or not config.llm.provider:
            return {
                "status": "not_configured",
                "provider": None
            }

        return {
            "status": "configured",
            "provider": config.llm.provider,
            "model": config.llm.model if hasattr(config.llm, 'model') else None
        }

    except Exception as e:
        logger.error(f"LLM health check failed: {e}", exc_info=True)
        return {
            "status": "not_configured",
            "error": str(e)
        }


def _determine_overall_status(checks: Dict[str, Dict[str, Any]]) -> str:
    """
    Determine overall health status based on individual checks.

    Logic:
    - "healthy": All critical services are healthy
    - "degraded": Optional services unhealthy, critical services healthy
    - "unhealthy": Any critical service is unhealthy

    Critical services: discord (if configured), database, redis (if configured)
    Optional services: llm
    """
    discord_status = checks.get("discord", {}).get("status")
    database_status = checks.get("database", {}).get("status")
    redis_status = checks.get("redis", {}).get("status")
    llm_status = checks.get("llm", {}).get("status")

    # Check critical services
    critical_unhealthy = []

    # Discord is critical if configured
    if discord_status not in ["not_configured", None]:
        if discord_status != "healthy":
            critical_unhealthy.append("discord")

    # Database is always critical
    if database_status != "healthy":
        critical_unhealthy.append("database")

    # Redis is critical if configured
    if redis_status not in ["not_configured", None]:
        if redis_status != "healthy":
            critical_unhealthy.append("redis")

    # Determine overall status
    if critical_unhealthy:
        logger.warning(f"Critical services unhealthy: {critical_unhealthy}")
        return "unhealthy"

    # Check if any optional service is degraded
    if llm_status == "unhealthy":
        logger.info("Optional service (LLM) degraded")
        return "degraded"

    return "healthy"
