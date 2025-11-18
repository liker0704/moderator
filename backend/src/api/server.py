"""
Health Check API Server

Provides HTTP server infrastructure for health check endpoint.
Uses aiohttp for async HTTP server with graceful shutdown support.
"""

import asyncio
import os
from typing import Optional
from aiohttp import web
from utils.logger import get_logger
from .health import health_check_handler

logger = get_logger(__name__)


def create_app(discord_gateway=None) -> web.Application:
    """
    Create and configure aiohttp Application instance.

    Sets up routes, middleware, and application state for the health check API.

    Args:
        discord_gateway: Optional DiscordGatewayManager instance for health checks

    Returns:
        Configured aiohttp Application instance
    """
    # Create application instance
    app = web.Application()

    # Store discord_gateway in application state for access by handlers
    app['discord_gateway'] = discord_gateway

    # Register health check route
    app.router.add_get('/health', health_check_handler)

    logger.debug("Health Check API application created")

    return app


async def run_health_check_server(
    discord_gateway=None,
    host: str = '0.0.0.0',
    port: int = 8000
) -> None:
    """
    Run Health Check API server.

    Starts an aiohttp HTTP server that provides health check endpoints.
    Supports graceful shutdown and proper cleanup on termination.

    Args:
        discord_gateway: Optional DiscordGatewayManager instance for health checks
        host: Host address to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 8000, overridden by HEALTH_CHECK_PORT env var)

    Raises:
        asyncio.CancelledError: When server shutdown is requested
        OSError: When port is already in use or binding fails
    """
    # Get port from environment variable if set
    port = int(os.getenv('HEALTH_CHECK_PORT', port))

    logger.info(f"Initializing Health Check API server on {host}:{port}")

    # Create application
    app = create_app(discord_gateway)

    # Create and setup runner
    runner = web.AppRunner(app)
    await runner.setup()

    try:
        # Create and start site
        site = web.TCPSite(runner, host, port)

        try:
            await site.start()
        except OSError as e:
            logger.error(f"Failed to start Health Check API server on {host}:{port}: {e}")
            raise

        logger.info(f"Health Check API server running on http://{host}:{port}/health")

        # Wait indefinitely (until cancelled)
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        logger.info("Health Check API server shutdown requested")
        raise

    except Exception as e:
        logger.error(f"Unexpected error in Health Check API server: {e}", exc_info=True)
        raise

    finally:
        # Cleanup
        logger.info("Cleaning up Health Check API server...")
        await runner.cleanup()
        logger.info("Health Check API server stopped")


async def main():
    """
    Main entry point for standalone server testing.

    This allows running the server independently for development and testing.
    Usage: python -m api.server
    """
    logger.info("Starting standalone Health Check API server")

    try:
        await run_health_check_server()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run standalone server for testing
    asyncio.run(main())
