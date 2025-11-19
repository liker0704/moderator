"""
Health Check API Server

Provides HTTP server infrastructure for health check endpoint.
Uses aiohttp for async HTTP server with graceful shutdown support.

Security features (v1.0+):
- Security headers middleware (CSP, X-Frame-Options, etc.)
- HTTPS enforcement (HSTS)
- XSS protection headers
- Content type sniffing prevention
"""

import asyncio
import os
from typing import Optional
from aiohttp import web
from utils.logger import get_logger
from .health import health_check_handler

logger = get_logger(__name__)

# Import metrics handler if metrics are enabled
try:
    from .metrics import metrics_handler
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Metrics module not available")


# =============================================================================
# Security Headers Middleware (v1.0+)
# =============================================================================

@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    """
    Add security headers to all HTTP responses.

    This middleware implements defense-in-depth security by adding headers that:
    - Prevent clickjacking (X-Frame-Options)
    - Prevent MIME type sniffing (X-Content-Type-Options)
    - Enable XSS protection (X-XSS-Protection)
    - Enforce HTTPS (Strict-Transport-Security, if HTTPS detected)
    - Restrict content sources (Content-Security-Policy)

    Headers added:
    - Content-Security-Policy: Restricts resource loading to same origin
    - X-Frame-Options: Prevents embedding in frames (clickjacking protection)
    - X-Content-Type-Options: Prevents MIME sniffing attacks
    - X-XSS-Protection: Enables browser XSS filtering (legacy browsers)
    - Strict-Transport-Security: Enforces HTTPS (only if HTTPS is used)
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features

    Args:
        request: aiohttp Request object
        handler: Next handler in the chain

    Returns:
        Response with security headers added
    """
    # Process the request
    response = await handler(request)

    # Content Security Policy
    # Restricts resources to same origin, blocks inline scripts/styles by default
    # For metrics endpoint, we allow 'unsafe-inline' for Prometheus text format
    if request.path == '/metrics':
        # Metrics endpoint needs relaxed CSP for text/plain content
        csp = "default-src 'self'; script-src 'none'; style-src 'none';"
    else:
        # Strict CSP for other endpoints
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
    response.headers['Content-Security-Policy'] = csp

    # Prevent clickjacking - deny all framing
    response.headers['X-Frame-Options'] = 'DENY'

    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # XSS Protection (legacy, but still useful for older browsers)
    # mode=block tells browser to block the page if XSS is detected
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Referrer Policy - don't leak referrer to external sites
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions Policy - restrict browser features
    # Disable potentially dangerous features
    response.headers['Permissions-Policy'] = (
        'geolocation=(), '
        'microphone=(), '
        'camera=(), '
        'payment=(), '
        'usb=(), '
        'magnetometer=(), '
        'gyroscope=(), '
        'accelerometer=()'
    )

    # Strict Transport Security (HSTS)
    # Only add if request is HTTPS (check X-Forwarded-Proto header from reverse proxy)
    is_https = (
        request.scheme == 'https' or
        request.headers.get('X-Forwarded-Proto') == 'https' or
        request.headers.get('X-Forwarded-Ssl') == 'on'
    )

    if is_https:
        # Enable HSTS for 1 year, include subdomains
        # preload: allow inclusion in browser HSTS preload lists (optional)
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains'
        )
        logger.debug("Added HSTS header (HTTPS detected)")

    # Cache-Control for security-sensitive endpoints
    # Prevent caching of health check responses (may contain sensitive info)
    if request.path in ['/health', '/metrics']:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

    return response


def create_app(discord_gateway=None, metrics_enabled: bool = False) -> web.Application:
    """
    Create and configure aiohttp Application instance.

    Sets up routes, middleware, and application state for the health check API.

    Args:
        discord_gateway: Optional DiscordGatewayManager instance for health checks
        metrics_enabled: Whether to enable Prometheus metrics endpoint (default: False)

    Returns:
        Configured aiohttp Application instance
    """
    # Create application instance with security headers middleware (v1.0+)
    app = web.Application(middlewares=[security_headers_middleware])

    # Store discord_gateway in application state for access by handlers
    app['discord_gateway'] = discord_gateway

    # Register health check route
    app.router.add_get('/health', health_check_handler)

    # Register metrics route if enabled
    if metrics_enabled and METRICS_AVAILABLE:
        app.router.add_get('/metrics', metrics_handler)
        logger.info("Prometheus metrics endpoint enabled at /metrics")
    elif metrics_enabled and not METRICS_AVAILABLE:
        logger.warning("Metrics requested but metrics module not available")

    logger.debug("Health Check API application created with security headers middleware")

    return app


async def run_health_check_server(
    discord_gateway=None,
    host: str = '0.0.0.0',
    port: int = 8000,
    metrics_enabled: bool = False
) -> None:
    """
    Run Health Check API server.

    Starts an aiohttp HTTP server that provides health check endpoints.
    Supports graceful shutdown and proper cleanup on termination.

    Args:
        discord_gateway: Optional DiscordGatewayManager instance for health checks
        host: Host address to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 8000, overridden by HEALTH_CHECK_PORT env var)
        metrics_enabled: Whether to enable Prometheus metrics endpoint (default: False)

    Raises:
        asyncio.CancelledError: When server shutdown is requested
        OSError: When port is already in use or binding fails
    """
    # Get port from environment variable if set
    port = int(os.getenv('HEALTH_CHECK_PORT', port))

    logger.info(f"Initializing Health Check API server on {host}:{port}")
    if metrics_enabled:
        logger.info("Prometheus metrics endpoint will be available at /metrics")

    # Create application
    app = create_app(discord_gateway, metrics_enabled=metrics_enabled)

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
        if metrics_enabled and METRICS_AVAILABLE:
            logger.info(f"Prometheus metrics available at http://{host}:{port}/metrics")

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
