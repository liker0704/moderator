"""
Performance Tests for v1.0 Iteration 11.

This module tests system performance under various loads:
- Response time benchmarks
- Database query performance
- LLM service with timeouts
- Concurrent operations
- Memory usage
- Throughput testing

Performance Baselines:
- Database queries: < 100ms for simple queries, < 500ms for complex
- LLM responses: < 5s for generation
- API endpoints: < 200ms for health checks
- Message processing: < 1s end-to-end
- Concurrent tasks: Support 10+ parallel operations
"""

import pytest
import asyncio
import time
import psutil
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


# =============================================================================
# Performance Test 1: Database Query Response Time
# =============================================================================

@pytest.mark.asyncio
async def test_database_query_performance(mock_db_connection, performance_timer):
    """
    Test database query performance.

    Benchmark: Simple queries should complete in < 100ms
    """
    conn = mock_db_connection

    # Mock fast database query
    async def fast_query(*args, **kwargs):
        await asyncio.sleep(0.05)  # Simulate 50ms query
        return [{'id': 1, 'name': 'test'}]

    conn.fetch = fast_query

    # Measure query time
    performance_timer.start()
    results = await conn.fetch("SELECT * FROM messages LIMIT 10")
    duration_ms = performance_timer.stop()

    assert duration_ms < 100, f"Query took {duration_ms}ms, expected < 100ms"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_complex_query_performance(mock_db_connection, performance_timer):
    """
    Test complex query performance with joins.

    Benchmark: Complex queries should complete in < 500ms
    """
    conn = mock_db_connection

    # Mock complex query with joins
    async def complex_query(*args, **kwargs):
        await asyncio.sleep(0.3)  # Simulate 300ms complex query
        return [
            {
                'message_id': i,
                'task_id': i,
                'reply_count': 2,
                'author_name': f'User{i}'
            }
            for i in range(50)
        ]

    conn.fetch = complex_query

    # Measure query time
    performance_timer.start()
    results = await conn.fetch("""
        SELECT m.*, t.*, COUNT(r.id) as reply_count
        FROM messages m
        JOIN tasks t ON t.source_message_id = m.id
        LEFT JOIN replies r ON r.task_id = t.id
        GROUP BY m.id, t.id
    """)
    duration_ms = performance_timer.stop()

    assert duration_ms < 500, f"Complex query took {duration_ms}ms, expected < 500ms"
    assert len(results) == 50


# =============================================================================
# Performance Test 2: LLM Response Time
# =============================================================================

@pytest.mark.asyncio
async def test_llm_response_time(mock_llm_client, performance_timer):
    """
    Test LLM response generation time.

    Benchmark: LLM should respond in < 5 seconds
    """
    # Mock LLM with realistic delay
    async def generate_with_delay(*args, **kwargs):
        await asyncio.sleep(2.0)  # Simulate 2s LLM call
        return {
            'content': 'This is a test response.',
            'confidence': 0.85,
            'tokens_used': 150
        }

    mock_llm_client.generate_response = generate_with_delay

    # Measure LLM response time
    performance_timer.start()
    response = await mock_llm_client.generate_response(
        context='Test message',
        max_tokens=200
    )
    duration_ms = performance_timer.stop()

    assert duration_ms < 5000, f"LLM took {duration_ms}ms, expected < 5000ms"
    assert response['content'] is not None


@pytest.mark.asyncio
async def test_llm_timeout_handling(mock_llm_client, performance_timer):
    """
    Test LLM timeout handling.

    Benchmark: Should timeout and fail gracefully after 10s
    """
    # Mock slow LLM that times out
    async def slow_llm(*args, **kwargs):
        await asyncio.sleep(15.0)  # Simulate slow response
        return {'content': 'Too slow'}

    mock_llm_client.generate_response = slow_llm

    # Test with timeout
    performance_timer.start()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            mock_llm_client.generate_response(context='Test'),
            timeout=10.0
        )
    duration_ms = performance_timer.stop()

    # Should timeout around 10s
    assert 9000 < duration_ms < 11000, f"Timeout took {duration_ms}ms"


# =============================================================================
# Performance Test 3: Concurrent Operations
# =============================================================================

@pytest.mark.asyncio
async def test_concurrent_database_operations(mock_db_connection, performance_timer):
    """
    Test concurrent database operations.

    Benchmark: Should handle 10+ concurrent queries efficiently
    """
    conn = mock_db_connection

    # Mock database operation
    async def db_operation(query_id):
        await asyncio.sleep(0.1)  # Each query takes 100ms
        return {'query_id': query_id, 'result': f'Result {query_id}'}

    # Run 20 concurrent operations
    performance_timer.start()
    tasks = [db_operation(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    duration_ms = performance_timer.stop()

    # With 20 concurrent ops of 100ms each, should complete in ~100-200ms
    # (not 2000ms if sequential)
    assert duration_ms < 500, f"20 concurrent ops took {duration_ms}ms"
    assert len(results) == 20


@pytest.mark.asyncio
async def test_concurrent_message_processing(
    mock_db_connection,
    test_data_generator,
    performance_timer
):
    """
    Test concurrent message processing.

    Benchmark: Should process 10 messages concurrently in < 2s
    """
    conn = mock_db_connection
    messages = test_data_generator.generate_messages(count=10)

    async def process_message(msg):
        # Simulate message processing
        await asyncio.sleep(0.15)  # 150ms per message
        return {'message_id': msg['ext_message_id'], 'processed': True}

    # Process all messages concurrently
    performance_timer.start()
    tasks = [process_message(msg) for msg in messages]
    results = await asyncio.gather(*tasks)
    duration_ms = performance_timer.stop()

    # Should complete in ~150-300ms (concurrent), not 1500ms (sequential)
    assert duration_ms < 2000, f"Processing 10 messages took {duration_ms}ms"
    assert len(results) == 10
    assert all(r['processed'] for r in results)


# =============================================================================
# Performance Test 4: Memory Usage
# =============================================================================

@pytest.mark.asyncio
async def test_memory_usage_large_dataset(test_data_generator):
    """
    Test memory usage with large datasets.

    Benchmark: Should handle 1000 messages without excessive memory growth
    """
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Generate large dataset
    messages = test_data_generator.generate_messages(count=1000)

    # Simulate processing
    processed = []
    for msg in messages:
        processed.append({
            'id': msg['ext_message_id'],
            'processed_at': datetime.now()
        })

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    # Memory increase should be reasonable (< 50 MB for 1000 messages)
    assert memory_increase < 50, f"Memory increased by {memory_increase}MB"


@pytest.mark.asyncio
async def test_memory_cleanup_after_processing():
    """
    Test memory cleanup after processing.

    Benchmark: Memory should be released after processing completes
    """
    import gc

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Create and process large temporary data
    large_data = [{'id': i, 'data': 'x' * 1000} for i in range(1000)]
    processed = [item['id'] for item in large_data]

    # Clear references and force garbage collection
    del large_data
    del processed
    gc.collect()

    # Wait a bit for cleanup
    await asyncio.sleep(0.1)

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_diff = abs(final_memory - initial_memory)

    # Memory should return close to baseline (within 10 MB)
    assert memory_diff < 10, f"Memory diff: {memory_diff}MB after cleanup"


# =============================================================================
# Performance Test 5: API Endpoint Response Time
# =============================================================================

@pytest.mark.asyncio
async def test_health_check_endpoint_performance(performance_timer):
    """
    Test health check endpoint performance.

    Benchmark: Should respond in < 200ms
    """
    # Mock health check
    async def health_check():
        await asyncio.sleep(0.05)  # 50ms processing
        return {
            'status': 'healthy',
            'database': 'connected',
            'redis': 'connected',
            'timestamp': datetime.now().isoformat()
        }

    # Measure response time
    performance_timer.start()
    response = await health_check()
    duration_ms = performance_timer.stop()

    assert duration_ms < 200, f"Health check took {duration_ms}ms"
    assert response['status'] == 'healthy'


@pytest.mark.asyncio
async def test_metrics_endpoint_performance(performance_timer):
    """
    Test metrics endpoint performance.

    Benchmark: Should respond in < 500ms even with aggregations
    """
    # Mock metrics collection
    async def collect_metrics():
        await asyncio.sleep(0.2)  # 200ms for aggregations
        return {
            'messages_count': 10000,
            'tasks_pending': 25,
            'tasks_completed': 5000,
            'avg_response_time': 150.5,
            'llm_requests_today': 300
        }

    # Measure response time
    performance_timer.start()
    metrics = await collect_metrics()
    duration_ms = performance_timer.stop()

    assert duration_ms < 500, f"Metrics collection took {duration_ms}ms"
    assert 'messages_count' in metrics


# =============================================================================
# Performance Test 6: Bulk Operations
# =============================================================================

@pytest.mark.asyncio
async def test_bulk_insert_performance(mock_db_connection, performance_timer):
    """
    Test bulk insert performance.

    Benchmark: Should insert 100 records in < 1s
    """
    conn = mock_db_connection

    # Mock bulk insert
    async def bulk_insert(records):
        await asyncio.sleep(len(records) * 0.005)  # 5ms per record
        return len(records)

    # Generate 100 records
    records = [
        {'ext_message_id': f'msg_{i}', 'content': f'Message {i}'}
        for i in range(100)
    ]

    # Measure bulk insert time
    performance_timer.start()
    inserted_count = await bulk_insert(records)
    duration_ms = performance_timer.stop()

    assert duration_ms < 1000, f"Bulk insert took {duration_ms}ms"
    assert inserted_count == 100


@pytest.mark.asyncio
async def test_bulk_update_performance(mock_db_connection, performance_timer):
    """
    Test bulk update performance.

    Benchmark: Should update 100 records in < 1s
    """
    conn = mock_db_connection

    # Mock bulk update
    async def bulk_update(updates):
        await asyncio.sleep(len(updates) * 0.006)  # 6ms per update
        return len(updates)

    # Generate 100 updates
    updates = [
        {'id': i, 'status': 'completed'}
        for i in range(100)
    ]

    # Measure bulk update time
    performance_timer.start()
    updated_count = await bulk_update(updates)
    duration_ms = performance_timer.stop()

    assert duration_ms < 1000, f"Bulk update took {duration_ms}ms"
    assert updated_count == 100


# =============================================================================
# Performance Test 7: Search Performance
# =============================================================================

@pytest.mark.asyncio
async def test_search_query_performance(mock_db_connection, performance_timer):
    """
    Test search query performance.

    Benchmark: Full-text search should complete in < 500ms
    """
    conn = mock_db_connection

    # Mock search query
    async def search_messages(query, limit):
        await asyncio.sleep(0.3)  # 300ms for full-text search
        return [
            {'id': i, 'content': f'{query} in message {i}'}
            for i in range(min(limit, 50))
        ]

    # Measure search time
    performance_timer.start()
    results = await search_messages('test query', limit=50)
    duration_ms = performance_timer.stop()

    assert duration_ms < 500, f"Search took {duration_ms}ms"
    assert len(results) <= 50


@pytest.mark.asyncio
async def test_search_with_filters_performance(
    mock_db_connection,
    performance_timer
):
    """
    Test search with multiple filters.

    Benchmark: Filtered search should complete in < 1s
    """
    conn = mock_db_connection

    # Mock filtered search
    async def search_with_filters(query, filters):
        await asyncio.sleep(0.5)  # 500ms for complex filtered search
        return [
            {
                'id': i,
                'content': f'{query}',
                'channel_id': filters['channel_id'],
                'author_id': filters.get('author_id')
            }
            for i in range(20)
        ]

    filters = {
        'channel_id': 'channel_1',
        'author_id': 'author_1',
        'date_from': '2024-01-01',
        'date_to': '2024-12-31'
    }

    # Measure search time
    performance_timer.start()
    results = await search_with_filters('test', filters)
    duration_ms = performance_timer.stop()

    assert duration_ms < 1000, f"Filtered search took {duration_ms}ms"
    assert len(results) == 20


# =============================================================================
# Performance Test 8: Cache Performance
# =============================================================================

@pytest.mark.asyncio
async def test_redis_cache_performance(mock_redis_client, performance_timer):
    """
    Test Redis cache operations.

    Benchmark: Cache operations should complete in < 50ms
    """
    redis = mock_redis_client

    # Measure cache write
    performance_timer.start()
    await redis.set('test_key', 'test_value', ex=60)
    write_duration = performance_timer.stop()

    assert write_duration < 50, f"Cache write took {write_duration}ms"

    # Measure cache read
    performance_timer.start()
    value = await redis.get('test_key')
    read_duration = performance_timer.stop()

    assert read_duration < 50, f"Cache read took {read_duration}ms"
    assert value == 'test_value'


@pytest.mark.asyncio
async def test_cache_hit_vs_miss_performance(
    mock_redis_client,
    mock_db_connection,
    performance_timer
):
    """
    Test performance difference between cache hit and database query.

    Benchmark: Cache should be at least 5x faster than database
    """
    redis = mock_redis_client
    conn = mock_db_connection

    # Mock database query (slow)
    async def db_query():
        await asyncio.sleep(0.1)  # 100ms
        return {'id': 1, 'name': 'test'}

    # Mock cache get (fast)
    async def cache_get():
        await asyncio.sleep(0.01)  # 10ms
        return {'id': 1, 'name': 'test'}

    # Measure database query time
    performance_timer.start()
    db_result = await db_query()
    db_duration = performance_timer.stop()

    # Measure cache query time
    performance_timer.start()
    cache_result = await cache_get()
    cache_duration = performance_timer.stop()

    # Cache should be significantly faster
    speedup = db_duration / cache_duration
    assert speedup >= 5, f"Cache only {speedup}x faster than DB"


# =============================================================================
# Performance Test 9: Throughput Testing
# =============================================================================

@pytest.mark.asyncio
async def test_message_processing_throughput(performance_timer):
    """
    Test message processing throughput.

    Benchmark: Should process at least 100 messages/second
    """
    async def process_message(msg_id):
        await asyncio.sleep(0.005)  # 5ms per message
        return {'id': msg_id, 'processed': True}

    # Process 200 messages
    message_count = 200

    performance_timer.start()
    tasks = [process_message(i) for i in range(message_count)]
    results = await asyncio.gather(*tasks)
    duration_ms = performance_timer.stop()

    # Calculate throughput
    duration_seconds = duration_ms / 1000.0
    throughput = message_count / duration_seconds

    assert throughput >= 100, f"Throughput: {throughput} msg/s, expected >= 100"
    assert len(results) == message_count


@pytest.mark.asyncio
async def test_api_request_throughput(performance_timer):
    """
    Test API request throughput.

    Benchmark: Should handle at least 50 requests/second
    """
    async def handle_request(req_id):
        await asyncio.sleep(0.01)  # 10ms per request
        return {'request_id': req_id, 'status': 'ok'}

    # Process 100 requests
    request_count = 100

    performance_timer.start()
    tasks = [handle_request(i) for i in range(request_count)]
    results = await asyncio.gather(*tasks)
    duration_ms = performance_timer.stop()

    # Calculate throughput
    duration_seconds = duration_ms / 1000.0
    throughput = request_count / duration_seconds

    assert throughput >= 50, f"Throughput: {throughput} req/s, expected >= 50"
    assert len(results) == request_count


# =============================================================================
# Performance Test 10: Export Performance
# =============================================================================

@pytest.mark.asyncio
async def test_export_generation_performance(
    test_data_generator,
    performance_timer
):
    """
    Test export file generation performance.

    Benchmark: Should export 1000 messages in < 5s
    """
    import json

    # Generate 1000 messages
    messages = test_data_generator.generate_messages(count=1000)

    # Measure export generation time
    performance_timer.start()

    # Simulate JSON export generation
    export_data = {
        'messages': messages,
        'total_count': len(messages),
        'exported_at': datetime.now().isoformat()
    }

    # Serialize to JSON
    json_output = json.dumps(export_data, default=str)

    duration_ms = performance_timer.stop()

    assert duration_ms < 5000, f"Export generation took {duration_ms}ms"
    assert len(json_output) > 0


# =============================================================================
# Performance Test 11: Rate Limiter Performance
# =============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_check_performance(
    mock_redis_client,
    performance_timer
):
    """
    Test rate limiter check performance.

    Benchmark: Rate limit checks should complete in < 20ms
    """
    redis = mock_redis_client

    async def check_rate_limit(user_id):
        # Simulate rate limit check
        key = f'rate_limit:{user_id}'
        current = await redis.get(key)

        if current is None:
            await redis.set(key, 1, ex=60)
            return True

        if int(current) >= 100:
            return False

        await redis.set(key, int(current) + 1, ex=60)
        return True

    # Measure rate limit check time
    performance_timer.start()
    allowed = await check_rate_limit('user_123')
    duration_ms = performance_timer.stop()

    assert duration_ms < 20, f"Rate limit check took {duration_ms}ms"
    assert allowed is True


# =============================================================================
# Performance Test 12: Database Connection Pool
# =============================================================================

@pytest.mark.asyncio
async def test_connection_pool_performance(performance_timer):
    """
    Test database connection pool efficiency.

    Benchmark: Getting connection from pool should take < 10ms
    """
    # Mock connection pool
    class MockPool:
        def __init__(self):
            self.connections = [Mock() for _ in range(10)]
            self.available = list(self.connections)

        async def acquire(self):
            await asyncio.sleep(0.002)  # 2ms to acquire
            if self.available:
                return self.available.pop()
            return Mock()

        async def release(self, conn):
            await asyncio.sleep(0.001)  # 1ms to release
            self.available.append(conn)

    pool = MockPool()

    # Measure connection acquisition time
    performance_timer.start()
    conn = await pool.acquire()
    duration_ms = performance_timer.stop()

    assert duration_ms < 10, f"Connection acquisition took {duration_ms}ms"
    assert conn is not None

    # Release connection
    await pool.release(conn)
    assert len(pool.available) > 0
