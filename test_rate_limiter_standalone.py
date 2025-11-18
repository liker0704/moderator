#!/usr/bin/env python3
"""
Standalone test for rate_limiter module.

This test verifies the rate limiting implementation without requiring
full project dependencies.
"""

import asyncio
import time
import sys
import os

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))

# Mock logger to avoid redis dependency
class MockLogger:
    def info(self, msg, **kwargs):
        print(f"INFO: {msg}")

    def debug(self, msg, **kwargs):
        print(f"DEBUG: {msg}")

    def warning(self, msg, **kwargs):
        print(f"WARNING: {msg}")

    def error(self, msg, **kwargs):
        print(f"ERROR: {msg}")

# Patch utils.logger before importing rate_limiter
class UtilsLoggerModule:
    @staticmethod
    def get_logger(name):
        return MockLogger()

sys.modules['utils.logger'] = UtilsLoggerModule()

# Now import rate_limiter
from services.rate_limiter import (
    Bucket,
    GlobalRateLimit,
    RateLimiter,
    get_rate_limiter
)


def test_bucket():
    """Test Bucket dataclass functionality."""
    print("\n=== Testing Bucket ===")

    # Create bucket
    bucket = Bucket(limit=5, remaining=3, reset_at=time.time() + 10)
    print(f"Created bucket: limit={bucket.limit}, remaining={bucket.remaining}")

    # Test is_rate_limited (should be False with remaining > 0)
    assert not bucket.is_rate_limited(), "Should not be rate limited with remaining > 0"
    print("✓ is_rate_limited() works with remaining > 0")

    # Consume requests
    bucket.consume()
    bucket.consume()
    bucket.consume()
    assert bucket.remaining == 0, "Remaining should be 0 after consuming 3"
    print(f"✓ consume() works, remaining: {bucket.remaining}")

    # Test is_rate_limited (should be True with remaining == 0)
    assert bucket.is_rate_limited(), "Should be rate limited with remaining == 0"
    print("✓ is_rate_limited() works with remaining == 0")

    # Test get_reset_after
    reset_after = bucket.get_reset_after()
    assert reset_after > 0, "Reset after should be > 0"
    print(f"✓ get_reset_after() works: {reset_after:.2f}s")

    # Test bucket that has reset
    bucket2 = Bucket(limit=5, remaining=0, reset_at=time.time() - 1)
    assert not bucket2.is_rate_limited(), "Should not be rate limited after reset time"
    print("✓ Bucket correctly handles expired reset time")

    print("✅ Bucket tests passed!")


def test_global_rate_limit():
    """Test GlobalRateLimit functionality."""
    print("\n=== Testing GlobalRateLimit ===")

    global_limit = GlobalRateLimit(max_requests=5, window_size=1.0)
    print(f"Created global limit: max={global_limit.max_requests}, window={global_limit.window_size}s")

    # Add requests
    for i in range(3):
        global_limit.consume()

    assert len(global_limit.request_times) == 3, "Should have 3 requests"
    print(f"✓ consume() works, requests: {len(global_limit.request_times)}")

    # Check not rate limited yet
    assert not global_limit.is_rate_limited(), "Should not be rate limited at 3/5"
    print("✓ is_rate_limited() works below limit")

    # Fill up to limit
    global_limit.consume()
    global_limit.consume()

    assert global_limit.is_rate_limited(), "Should be rate limited at 5/5"
    print("✓ is_rate_limited() works at limit")

    # Get wait time
    wait_time = global_limit.get_wait_time()
    assert wait_time > 0, "Wait time should be > 0 when rate limited"
    print(f"✓ get_wait_time() works: {wait_time:.2f}s")

    # Wait for window to pass
    print("Waiting for window to expire...")
    time.sleep(1.1)
    global_limit._cleanup_old_requests()

    assert len(global_limit.request_times) == 0, "Old requests should be cleaned up"
    assert not global_limit.is_rate_limited(), "Should not be rate limited after window"
    print("✓ Sliding window cleanup works")

    print("✅ GlobalRateLimit tests passed!")


async def test_rate_limiter():
    """Test RateLimiter functionality."""
    print("\n=== Testing RateLimiter ===")

    limiter = RateLimiter()
    print("Created RateLimiter instance")

    # Test route key normalization
    route1 = limiter._get_route_key("/channels/123/messages")
    route2 = limiter._get_route_key("/channels/456/messages")
    assert route1 == route2, "Routes with different IDs should normalize to same key"
    assert route1 == "/channels/{id}/messages", f"Expected '/channels/{{id}}/messages', got '{route1}'"
    print(f"✓ Route key normalization works: '{route1}'")

    # Test bucket creation
    bucket = limiter._get_bucket("/channels/{id}/messages")
    assert bucket is not None, "Bucket should be created"
    print("✓ Bucket creation works")

    # Test acquire (should not wait on first call)
    start = time.time()
    await limiter.acquire("/channels/123/messages")
    elapsed = time.time() - start
    assert elapsed < 0.1, "First acquire should not wait"
    print(f"✓ acquire() works without waiting ({elapsed*1000:.1f}ms)")

    # Test update from headers
    headers = {
        'X-RateLimit-Limit': '5',
        'X-RateLimit-Remaining': '4',
        'X-RateLimit-Reset': str(time.time() + 5),
        'X-RateLimit-Bucket': 'test-bucket-123'
    }
    limiter.update_from_response("/channels/123/messages", headers)

    bucket = limiter._get_bucket("/channels/{id}/messages")
    assert bucket.limit == 5, f"Expected limit 5, got {bucket.limit}"
    assert bucket.remaining == 4, f"Expected remaining 4, got {bucket.remaining}"
    assert bucket.bucket_id == 'test-bucket-123', "Bucket ID should be set"
    print(f"✓ update_from_response() works: limit={bucket.limit}, remaining={bucket.remaining}")

    # Test handle_rate_limit_response
    response_data = {
        "retry_after": 0.5,
        "global": False
    }
    wait_time = await limiter.handle_rate_limit_response(
        "/channels/123/messages",
        response_data,
        retry_count=0
    )

    assert wait_time == 0.5, f"Expected wait_time 0.5, got {wait_time}"
    print(f"✓ handle_rate_limit_response() works: wait_time={wait_time}s")

    # Verify bucket was updated
    bucket = limiter._get_bucket("/channels/{id}/messages")
    assert bucket.remaining == 0, "Bucket remaining should be 0 after rate limit"
    print(f"✓ Bucket updated after 429: remaining={bucket.remaining}")

    # Test max retries
    wait_time = await limiter.handle_rate_limit_response(
        "/channels/123/messages",
        {"retry_after": 1.0, "global": False},
        retry_count=3,
        max_retries=3
    )
    assert wait_time is None, "Should return None when max retries exceeded"
    print("✓ handle_rate_limit_response() respects max_retries")

    print("✅ RateLimiter tests passed!")


async def test_singleton():
    """Test get_rate_limiter singleton."""
    print("\n=== Testing Singleton ===")

    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()

    assert limiter1 is limiter2, "get_rate_limiter() should return same instance"
    print("✓ Singleton pattern works")

    print("✅ Singleton tests passed!")


async def test_rate_limiting_behavior():
    """Test actual rate limiting behavior."""
    print("\n=== Testing Rate Limiting Behavior ===")

    limiter = RateLimiter()

    # Set up a bucket with 2 requests remaining
    headers = {
        'X-RateLimit-Limit': '3',
        'X-RateLimit-Remaining': '2',
        'X-RateLimit-Reset': str(time.time() + 2),
        'X-RateLimit-Bucket': 'test-bucket'
    }
    limiter.update_from_response("/test/endpoint", headers)

    # Make 2 requests (should work without waiting)
    start = time.time()
    await limiter.acquire("/test/endpoint")
    await limiter.acquire("/test/endpoint")
    elapsed = time.time() - start

    assert elapsed < 0.2, "Should not wait for first 2 requests"
    print(f"✓ First 2 requests completed without waiting ({elapsed*1000:.1f}ms)")

    # Next request should wait because remaining is 0
    bucket = limiter._get_bucket(limiter._get_route_key("/test/endpoint"))
    assert bucket.remaining == 0, "Bucket should be exhausted"
    print(f"✓ Bucket exhausted: remaining={bucket.remaining}")

    # The next acquire should wait until reset
    print("Testing wait behavior (this should wait ~2s)...")
    start = time.time()
    await limiter.acquire("/test/endpoint")
    elapsed = time.time() - start

    assert elapsed >= 1.8, f"Should wait ~2s, waited {elapsed:.2f}s"
    print(f"✓ acquire() correctly waited for rate limit reset ({elapsed:.2f}s)")

    print("✅ Rate limiting behavior tests passed!")


async def test_global_rate_limit_integration():
    """Test global rate limit integration."""
    print("\n=== Testing Global Rate Limit Integration ===")

    limiter = RateLimiter()

    # Make many rapid requests (should not exceed global limit)
    start = time.time()
    for i in range(55):  # More than global limit of 50
        await limiter.acquire(f"/test/endpoint/{i}")
    elapsed = time.time() - start

    # Should take at least 1 second due to global limit
    assert elapsed >= 0.9, f"Should be rate limited by global limit, took {elapsed:.2f}s"
    print(f"✓ Global rate limit enforced over {elapsed:.2f}s")

    # Check that we didn't exceed 50 req/sec
    requests_in_window = len(limiter.global_limit.request_times)
    print(f"✓ Requests in current window: {requests_in_window}")

    print("✅ Global rate limit integration tests passed!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Rate Limiter Standalone Tests")
    print("=" * 60)

    try:
        # Synchronous tests
        test_bucket()
        test_global_rate_limit()

        # Asynchronous tests
        await test_singleton()
        await test_rate_limiter()
        await test_rate_limiting_behavior()
        await test_global_rate_limit_integration()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

        return 0

    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
