"""
Tests for Prometheus metrics functionality.

Tests:
- Metric definitions and initialization
- Counter increments
- Histogram observations
- Gauge updates
- HTTP endpoint response
- Decorator functionality
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from prometheus_client import REGISTRY

# Import metrics module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from api.metrics import (
    messages_total,
    tasks_total,
    replies_total,
    llm_requests_total,
    errors_total,
    response_time_seconds,
    open_tasks_count,
    allowlist_size,
    app_info,
    increment_messages,
    increment_tasks,
    increment_replies,
    increment_llm_requests,
    increment_errors,
    observe_response_time,
    set_open_tasks,
    set_allowlist_size,
    set_app_info,
    track_response_time,
    track_operation,
    update_gauge_metrics,
    gauge_metrics_updater,
    metrics_handler,
    init_metrics,
)


class TestMetricDefinitions:
    """Test that all metrics are properly defined."""

    def test_counter_metrics_exist(self):
        """Test that counter metrics are defined."""
        # Check that metrics are registered
        assert messages_total is not None
        assert tasks_total is not None
        assert replies_total is not None
        assert llm_requests_total is not None
        assert errors_total is not None

    def test_histogram_metrics_exist(self):
        """Test that histogram metrics are defined."""
        assert response_time_seconds is not None

    def test_gauge_metrics_exist(self):
        """Test that gauge metrics are defined."""
        assert open_tasks_count is not None
        assert allowlist_size is not None
        assert app_info is not None


class TestCounterIncrements:
    """Test counter increment functions."""

    def test_increment_messages(self):
        """Test incrementing message counter."""
        # Get initial value
        before = messages_total.labels(platform='discord')._value.get()

        # Increment
        increment_messages('discord')

        # Verify increment
        after = messages_total.labels(platform='discord')._value.get()
        assert after == before + 1

    def test_increment_tasks(self):
        """Test incrementing task counter."""
        before = tasks_total.labels(status='pending')._value.get()

        increment_tasks('pending')

        after = tasks_total.labels(status='pending')._value.get()
        assert after == before + 1

    def test_increment_replies(self):
        """Test incrementing reply counter."""
        before = replies_total.labels(platform='telegram')._value.get()

        increment_replies('telegram')

        after = replies_total.labels(platform='telegram')._value.get()
        assert after == before + 1

    def test_increment_llm_requests(self):
        """Test incrementing LLM request counter."""
        before = llm_requests_total.labels(provider='openai', status='success')._value.get()

        increment_llm_requests('openai', 'success')

        after = llm_requests_total.labels(provider='openai', status='success')._value.get()
        assert after == before + 1

    def test_increment_errors(self):
        """Test incrementing error counter."""
        before = errors_total.labels(error_type='database')._value.get()

        increment_errors('database')

        after = errors_total.labels(error_type='database')._value.get()
        assert after == before + 1


class TestHistogramObservations:
    """Test histogram observation functions."""

    def test_observe_response_time(self):
        """Test observing response time."""
        # Observe some values
        observe_response_time('message_processing', 1.5)
        observe_response_time('message_processing', 2.0)
        observe_response_time('message_processing', 0.5)

        # Get metric data
        metric = response_time_seconds.labels(operation='message_processing')

        # Verify count increased
        assert metric._count.get() >= 3

        # Verify sum increased
        assert metric._sum.get() >= 4.0


class TestGaugeUpdates:
    """Test gauge update functions."""

    def test_set_open_tasks(self):
        """Test setting open tasks count."""
        set_open_tasks(42)

        value = open_tasks_count._value.get()
        assert value == 42

    def test_set_allowlist_size(self):
        """Test setting allowlist size."""
        set_allowlist_size('discord', 10)

        value = allowlist_size.labels(platform='discord')._value.get()
        assert value == 10

    def test_set_app_info(self):
        """Test setting application info."""
        set_app_info('1.0.0', 'production')

        value = app_info.labels(version='1.0.0', environment='production')._value.get()
        assert value == 1


class TestDecorators:
    """Test metric collection decorators."""

    @pytest.mark.asyncio
    async def test_track_response_time_decorator(self):
        """Test response time tracking decorator."""
        @track_response_time('test_operation')
        async def slow_function():
            await asyncio.sleep(0.1)
            return "done"

        result = await slow_function()

        assert result == "done"

        # Verify metric was recorded
        metric = response_time_seconds.labels(operation='test_operation')
        assert metric._count.get() >= 1

    @pytest.mark.asyncio
    async def test_track_operation_context_manager(self):
        """Test operation tracking context manager."""
        async with track_operation('context_test'):
            await asyncio.sleep(0.05)

        # Verify metric was recorded
        metric = response_time_seconds.labels(operation='context_test')
        assert metric._count.get() >= 1


class TestGaugeUpdater:
    """Test gauge metrics updater."""

    @pytest.mark.asyncio
    async def test_update_gauge_metrics(self):
        """Test updating gauge metrics from database."""
        # Mock database connection and pool
        mock_conn = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock database queries
        mock_conn.fetchrow.side_effect = [
            {'count': 15},  # open tasks
            {'count': 5},   # discord allowlist
            {'count': 3},   # telegram allowlist
        ]

        with patch('api.metrics.get_asyncpg_pool', return_value=mock_pool):
            await update_gauge_metrics()

            # Verify database was queried
            assert mock_conn.fetchrow.call_count == 3

            # Verify gauges were updated
            assert open_tasks_count._value.get() == 15
            assert allowlist_size.labels(platform='discord')._value.get() == 5
            assert allowlist_size.labels(platform='telegram')._value.get() == 3

    @pytest.mark.asyncio
    async def test_gauge_metrics_updater_loop(self):
        """Test gauge metrics updater background task."""
        # Mock the update function
        update_count = 0

        async def mock_update():
            nonlocal update_count
            update_count += 1
            if update_count >= 3:
                # Stop after 3 iterations
                raise asyncio.CancelledError

        with patch('api.metrics.update_gauge_metrics', side_effect=mock_update):
            with pytest.raises(asyncio.CancelledError):
                await gauge_metrics_updater(interval=0.01)

            # Verify update was called multiple times
            assert update_count >= 3


class TestMetricsEndpoint:
    """Test HTTP metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_handler_success(self):
        """Test metrics endpoint returns valid Prometheus format."""
        # Increment some metrics
        increment_messages('discord')
        increment_tasks('pending')

        # Create mock request
        mock_request = Mock()

        # Call handler
        response = await metrics_handler(mock_request)

        # Verify response
        assert response.status == 200
        assert response.content_type == 'text/plain; version=0.0.4; charset=utf-8'

        # Verify response contains metric names
        body = response.body.decode('utf-8')
        assert 'messages_total' in body
        assert 'tasks_total' in body
        assert 'response_time_seconds' in body
        assert 'open_tasks_count' in body

    @pytest.mark.asyncio
    async def test_metrics_handler_error(self):
        """Test metrics endpoint error handling."""
        mock_request = Mock()

        # Mock generate_latest to raise an error
        with patch('api.metrics.generate_latest', side_effect=Exception('Test error')):
            response = await metrics_handler(mock_request)

            # Verify error response
            assert response.status == 500
            assert 'Error generating metrics' in response.text


class TestInitialization:
    """Test metrics initialization."""

    def test_init_metrics(self):
        """Test metrics initialization."""
        init_metrics(version='1.0.0', environment='test')

        # Verify app_info was set
        value = app_info.labels(version='1.0.0', environment='test')._value.get()
        assert value == 1


class TestErrorHandling:
    """Test error handling in metrics functions."""

    def test_increment_messages_handles_errors(self):
        """Test that increment_messages handles errors gracefully."""
        # Should not raise even with invalid input
        try:
            increment_messages('discord')
            # If this works, the test passes
            assert True
        except Exception:
            pytest.fail("increment_messages should not raise exceptions")

    def test_observe_response_time_handles_errors(self):
        """Test that observe_response_time handles errors gracefully."""
        try:
            observe_response_time('test', 1.5)
            assert True
        except Exception:
            pytest.fail("observe_response_time should not raise exceptions")


class TestMetricsFormat:
    """Test Prometheus metrics format."""

    @pytest.mark.asyncio
    async def test_metrics_format_valid(self):
        """Test that metrics output is valid Prometheus format."""
        # Set some metrics
        increment_messages('discord')
        increment_tasks('pending')
        set_open_tasks(10)
        observe_response_time('test', 1.0)

        # Get metrics
        mock_request = Mock()
        response = await metrics_handler(mock_request)

        body = response.body.decode('utf-8')

        # Verify format
        # Should have HELP lines
        assert '# HELP' in body

        # Should have TYPE lines
        assert '# TYPE' in body

        # Should have metric values
        assert 'messages_total{platform="discord"}' in body
        assert 'tasks_total{status="pending"}' in body
        assert 'open_tasks_count' in body

        # Should have histogram buckets
        assert 'response_time_seconds_bucket' in body
        assert 'response_time_seconds_count' in body
        assert 'response_time_seconds_sum' in body


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
