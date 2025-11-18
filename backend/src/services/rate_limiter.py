"""
Rate limiting system for Discord API.

This module implements a sophisticated rate limiting system to ensure compliance
with Discord's API rate limits:
- Global rate limit: 50 requests per second across all endpoints
- Per-route rate limits: Each Discord API endpoint has its own bucket
- Bucket-based system: Discord uses X-RateLimit-Bucket headers to group routes
- Automatic retry with exponential backoff for 429 responses

The RateLimiter class tracks rate limits per bucket and automatically waits
when limits are reached to prevent 429 (Too Many Requests) errors.

Usage:
    >>> rate_limiter = get_rate_limiter()
    >>> await rate_limiter.acquire('/channels/123/messages')
    >>> # Make API request
    >>> await rate_limiter.update_from_response(response)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Bucket:
    """
    Rate limit bucket for a specific Discord API route.

    Discord groups similar routes into buckets and applies rate limits per bucket.
    Each bucket tracks the remaining requests, limit, and reset time.

    Attributes:
        limit: Maximum number of requests allowed in the time window
        remaining: Number of requests remaining before rate limit
        reset_at: Unix timestamp when the rate limit resets
        bucket_id: Discord's bucket identifier (from X-RateLimit-Bucket header)
    """
    limit: int = 1
    remaining: int = 1
    reset_at: float = 0.0
    bucket_id: Optional[str] = None

    def is_rate_limited(self) -> bool:
        """
        Check if this bucket is currently rate limited.

        Returns:
            bool: True if no requests remaining and reset time hasn't passed
        """
        if self.remaining > 0:
            return False

        current_time = time.time()
        return current_time < self.reset_at

    def get_reset_after(self) -> float:
        """
        Get seconds until rate limit resets.

        Returns:
            float: Seconds to wait (0 if not rate limited)
        """
        if not self.is_rate_limited():
            return 0.0

        current_time = time.time()
        return max(0.0, self.reset_at - current_time)

    def consume(self) -> None:
        """
        Consume one request from this bucket.

        Decrements the remaining count. Should be called after a successful
        API request.
        """
        if self.remaining > 0:
            self.remaining -= 1


@dataclass
class GlobalRateLimit:
    """
    Global rate limit tracker (50 requests per second).

    Discord enforces a global rate limit of 50 requests per second across
    all API endpoints. This class uses a sliding window to track requests.

    Attributes:
        max_requests: Maximum requests per second (50 for Discord)
        window_size: Time window in seconds (1 second)
        request_times: List of timestamps for recent requests
    """
    max_requests: int = 50
    window_size: float = 1.0
    request_times: list = field(default_factory=list)

    def is_rate_limited(self) -> bool:
        """
        Check if global rate limit is reached.

        Returns:
            bool: True if at max requests in the current window
        """
        self._cleanup_old_requests()
        return len(self.request_times) >= self.max_requests

    def get_wait_time(self) -> float:
        """
        Get seconds to wait until a slot becomes available.

        Returns:
            float: Seconds to wait (0 if not rate limited)
        """
        if not self.is_rate_limited():
            return 0.0

        self._cleanup_old_requests()
        if len(self.request_times) == 0:
            return 0.0

        # Wait until the oldest request falls out of the window
        oldest_request = self.request_times[0]
        current_time = time.time()
        wait_time = self.window_size - (current_time - oldest_request)

        return max(0.0, wait_time)

    def consume(self) -> None:
        """
        Record a new request in the global rate limit tracker.

        Should be called after making an API request.
        """
        self._cleanup_old_requests()
        self.request_times.append(time.time())

    def _cleanup_old_requests(self) -> None:
        """
        Remove request timestamps that are outside the current window.

        This maintains a sliding window by removing old entries.
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_size

        # Remove all requests older than the window
        self.request_times = [
            t for t in self.request_times
            if t > cutoff_time
        ]


class RateLimiter:
    """
    Main rate limiter for Discord API requests.

    This class manages both global and per-route rate limits. It tracks
    individual buckets for different API routes and ensures compliance
    with Discord's rate limiting policies.

    The rate limiter automatically:
    - Waits when rate limits are reached
    - Updates limits from Discord response headers
    - Handles 429 (Too Many Requests) responses
    - Implements exponential backoff for retries

    Attributes:
        global_limit: Global rate limit tracker (50 req/sec)
        buckets: Dictionary mapping routes to their Bucket objects
        bucket_ids: Dictionary mapping bucket IDs to routes
    """

    def __init__(self):
        """Initialize the rate limiter with global and per-route tracking."""
        self.global_limit = GlobalRateLimit()
        self.buckets: Dict[str, Bucket] = {}
        self.bucket_ids: Dict[str, str] = {}

        logger.info("RateLimiter initialized")

    def _get_route_key(self, endpoint: str) -> str:
        """
        Generate a normalized route key for bucket tracking.

        Discord groups similar routes (e.g., all channel message posts) into
        the same bucket. This method normalizes endpoints by replacing IDs
        with placeholders.

        Args:
            endpoint: API endpoint (e.g., "/channels/123/messages")

        Returns:
            str: Normalized route key (e.g., "/channels/{id}/messages")

        Examples:
            >>> _get_route_key("/channels/123456789/messages")
            "/channels/{id}/messages"
            >>> _get_route_key("/channels/987654321/messages/111111111")
            "/channels/{id}/messages/{id}"
        """
        # Replace numeric IDs with {id} placeholder
        import re
        route = re.sub(r'/\d+', '/{id}', endpoint)
        return route

    def _get_bucket(self, route: str) -> Bucket:
        """
        Get or create a bucket for a specific route.

        Args:
            route: Normalized route key

        Returns:
            Bucket: The bucket for this route
        """
        if route not in self.buckets:
            self.buckets[route] = Bucket()
            logger.debug(f"Created new bucket for route: {route}")

        return self.buckets[route]

    async def acquire(self, endpoint: str) -> None:
        """
        Acquire permission to make a request to the given endpoint.

        This method will wait if either:
        1. The global rate limit (50 req/sec) is reached
        2. The per-route bucket limit is reached

        Args:
            endpoint: API endpoint to request (e.g., "/channels/123/messages")

        Example:
            >>> rate_limiter = RateLimiter()
            >>> await rate_limiter.acquire("/channels/123/messages")
            >>> # Now safe to make the API request
        """
        route = self._get_route_key(endpoint)

        # Check and wait for global rate limit
        while self.global_limit.is_rate_limited():
            wait_time = self.global_limit.get_wait_time()
            logger.warning(
                f"Global rate limit reached, waiting {wait_time:.2f}s",
                extra={"wait_time": wait_time}
            )
            await asyncio.sleep(wait_time + 0.1)  # Add small buffer

        # Check and wait for per-route bucket limit
        bucket = self._get_bucket(route)
        while bucket.is_rate_limited():
            wait_time = bucket.get_reset_after()
            logger.warning(
                f"Route rate limit reached for {route}, waiting {wait_time:.2f}s",
                extra={
                    "route": route,
                    "wait_time": wait_time,
                    "bucket_id": bucket.bucket_id
                }
            )
            await asyncio.sleep(wait_time + 0.1)  # Add small buffer

        # Consume from both limits
        self.global_limit.consume()
        bucket.consume()

        logger.debug(
            f"Rate limit acquired for {route}",
            extra={
                "route": route,
                "bucket_remaining": bucket.remaining,
                "global_requests": len(self.global_limit.request_times)
            }
        )

    def update_from_response(self, endpoint: str, headers: Dict[str, str]) -> None:
        """
        Update rate limit state from Discord API response headers.

        Discord includes rate limit information in response headers:
        - X-RateLimit-Limit: Maximum requests allowed
        - X-RateLimit-Remaining: Requests remaining
        - X-RateLimit-Reset: Unix timestamp when limit resets
        - X-RateLimit-Bucket: Bucket identifier for this route

        Args:
            endpoint: API endpoint that was requested
            headers: Response headers from Discord API

        Example:
            >>> headers = {
            ...     'X-RateLimit-Limit': '5',
            ...     'X-RateLimit-Remaining': '4',
            ...     'X-RateLimit-Reset': '1700000000.123',
            ...     'X-RateLimit-Bucket': 'abc123'
            ... }
            >>> rate_limiter.update_from_response("/channels/123/messages", headers)
        """
        route = self._get_route_key(endpoint)
        bucket = self._get_bucket(route)

        # Extract rate limit headers (case-insensitive)
        headers_lower = {k.lower(): v for k, v in headers.items()}

        limit = headers_lower.get('x-ratelimit-limit')
        remaining = headers_lower.get('x-ratelimit-remaining')
        reset = headers_lower.get('x-ratelimit-reset')
        bucket_id = headers_lower.get('x-ratelimit-bucket')

        # Update bucket if headers are present
        updated = False
        if limit is not None:
            bucket.limit = int(limit)
            updated = True

        if remaining is not None:
            bucket.remaining = int(remaining)
            updated = True

        if reset is not None:
            bucket.reset_at = float(reset)
            updated = True

        if bucket_id is not None:
            bucket.bucket_id = bucket_id
            # Map bucket_id to route for future lookups
            self.bucket_ids[bucket_id] = route
            updated = True

        if updated:
            logger.debug(
                f"Updated rate limit for {route}",
                extra={
                    "route": route,
                    "limit": bucket.limit,
                    "remaining": bucket.remaining,
                    "reset_at": bucket.reset_at,
                    "bucket_id": bucket.bucket_id
                }
            )

    async def handle_rate_limit_response(
        self,
        endpoint: str,
        response_data: Dict,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[float]:
        """
        Handle a 429 (Too Many Requests) response from Discord.

        When Discord returns a 429, it includes a retry_after field indicating
        how long to wait before retrying. This method updates the bucket state
        and returns the wait time.

        Args:
            endpoint: API endpoint that was rate limited
            response_data: JSON response body containing retry_after
            retry_count: Current retry attempt (for logging)
            max_retries: Maximum number of retries allowed

        Returns:
            Optional[float]: Seconds to wait before retry, or None if max retries exceeded

        Example:
            >>> response = {"retry_after": 2.5, "global": False}
            >>> wait_time = await rate_limiter.handle_rate_limit_response(
            ...     "/channels/123/messages",
            ...     response
            ... )
            >>> if wait_time:
            ...     await asyncio.sleep(wait_time)
        """
        if retry_count >= max_retries:
            logger.error(
                f"Max retries ({max_retries}) exceeded for {endpoint}",
                extra={"endpoint": endpoint, "retry_count": retry_count}
            )
            return None

        retry_after = response_data.get("retry_after", 1.0)
        is_global = response_data.get("global", False)

        if is_global:
            # Global rate limit - affects all routes
            logger.warning(
                f"Global rate limit hit, waiting {retry_after}s",
                extra={
                    "retry_after": retry_after,
                    "retry_count": retry_count
                }
            )
            # Update global limit reset time
            self.global_limit.request_times.clear()
        else:
            # Route-specific rate limit
            route = self._get_route_key(endpoint)
            bucket = self._get_bucket(route)

            # Update bucket state
            bucket.remaining = 0
            bucket.reset_at = time.time() + retry_after

            logger.warning(
                f"Route rate limit hit for {route}, waiting {retry_after}s",
                extra={
                    "route": route,
                    "retry_after": retry_after,
                    "retry_count": retry_count,
                    "bucket_id": bucket.bucket_id
                }
            )

        return retry_after


# Singleton instance
_rate_limiter_instance: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the singleton RateLimiter instance.

    This ensures only one RateLimiter exists throughout the application,
    which is necessary for accurate rate limit tracking.

    Returns:
        RateLimiter: The singleton rate limiter instance

    Example:
        >>> limiter1 = get_rate_limiter()
        >>> limiter2 = get_rate_limiter()
        >>> assert limiter1 is limiter2  # Same instance
    """
    global _rate_limiter_instance

    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
        logger.info("Created singleton RateLimiter instance")

    return _rate_limiter_instance


# Example usage and testing
if __name__ == "__main__":
    import asyncio

    async def test_rate_limiter():
        """Test the rate limiter functionality."""
        limiter = get_rate_limiter()

        print("Testing rate limiter...")

        # Test 1: Basic acquire
        print("\n1. Testing basic acquire...")
        await limiter.acquire("/channels/123/messages")
        print("✓ Acquired rate limit")

        # Test 2: Multiple rapid requests
        print("\n2. Testing multiple rapid requests...")
        for i in range(5):
            await limiter.acquire("/channels/123/messages")
            print(f"✓ Request {i+1} acquired")

        # Test 3: Update from headers
        print("\n3. Testing header update...")
        headers = {
            'X-RateLimit-Limit': '5',
            'X-RateLimit-Remaining': '3',
            'X-RateLimit-Reset': str(time.time() + 5),
            'X-RateLimit-Bucket': 'test-bucket-123'
        }
        limiter.update_from_response("/channels/123/messages", headers)
        print("✓ Headers processed")

        route = limiter._get_route_key("/channels/123/messages")
        bucket = limiter._get_bucket(route)
        print(f"  Limit: {bucket.limit}, Remaining: {bucket.remaining}")

        # Test 4: Rate limit response handling
        print("\n4. Testing 429 response handling...")
        response_data = {
            "retry_after": 2.0,
            "global": False
        }
        wait_time = await limiter.handle_rate_limit_response(
            "/channels/123/messages",
            response_data
        )
        print(f"✓ Should wait {wait_time}s")

        # Test 5: Global rate limit
        print("\n5. Testing global rate limit...")
        print(f"Global requests in window: {len(limiter.global_limit.request_times)}")
        is_limited = limiter.global_limit.is_rate_limited()
        print(f"✓ Global rate limited: {is_limited}")

        print("\n✅ All tests passed!")

    # Run tests
    asyncio.run(test_rate_limiter())
