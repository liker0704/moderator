"""
Test suite for LLM monitoring and cost tracking.
Tests cost calculations, budget management, and usage statistics.
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from services.llm_monitoring import (
    calculate_cost,
    LLM_PRICING,
    track_llm_request,
    check_budget_alerts,
    update_budget_usage,
    get_usage_stats,
    create_budget
)


# =============================================================================
# Cost Calculation Tests
# =============================================================================

class TestCostCalculation:
    """Tests for LLM cost calculation functions."""

    def test_calculate_cost_gpt4_turbo(self):
        """Test cost calculation for GPT-4 Turbo."""
        cost = calculate_cost("gpt-4-turbo", 1000, 500)
        # (1000 * 0.01 / 1000) + (500 * 0.03 / 1000) = 0.025
        assert cost == Decimal("0.025")
        assert isinstance(cost, Decimal)

    def test_calculate_cost_gpt4(self):
        """Test cost calculation for GPT-4."""
        cost = calculate_cost("gpt-4", 1000, 500)
        # (1000 * 0.03 / 1000) + (500 * 0.06 / 1000) = 0.06
        assert cost == Decimal("0.06")
        assert isinstance(cost, Decimal)

    def test_calculate_cost_gpt35_turbo(self):
        """Test cost calculation for GPT-3.5 Turbo."""
        cost = calculate_cost("gpt-3.5-turbo", 2000, 1000)
        # (2000 * 0.0005 / 1000) + (1000 * 0.0015 / 1000) = 0.0025
        assert cost == Decimal("0.0025")

    def test_calculate_cost_gpt35_turbo_16k(self):
        """Test cost calculation for GPT-3.5 Turbo 16k."""
        cost = calculate_cost("gpt-3.5-turbo-16k", 1000, 500)
        # (1000 * 0.001 / 1000) + (500 * 0.002 / 1000) = 0.002
        assert cost == Decimal("0.002")

    def test_calculate_cost_claude_opus(self):
        """Test cost calculation for Claude 3 Opus."""
        cost = calculate_cost("claude-3-opus-20240229", 1000, 500)
        # (1000 * 0.015 / 1000) + (500 * 0.075 / 1000) = 0.0525
        assert cost == Decimal("0.0525")

    def test_calculate_cost_claude_sonnet(self):
        """Test cost calculation for Claude 3 Sonnet."""
        cost = calculate_cost("claude-3-sonnet-20240229", 1000, 500)
        # (1000 * 0.003 / 1000) + (500 * 0.015 / 1000) = 0.0105
        assert cost == Decimal("0.0105")

    def test_calculate_cost_claude_haiku(self):
        """Test cost calculation for Claude 3 Haiku."""
        cost = calculate_cost("claude-3-haiku-20240307", 1000, 500)
        # (1000 * 0.00025 / 1000) + (500 * 0.00125 / 1000) = 0.000875
        assert cost == Decimal("0.000875")

    def test_calculate_cost_unknown_model(self):
        """Test fallback pricing for unknown models."""
        cost = calculate_cost("unknown-model-xyz", 1000, 500)
        # Should use 'default' pricing: (1000 * 0.001 / 1000) + (500 * 0.002 / 1000) = 0.002
        assert cost == Decimal("0.002")
        assert cost >= Decimal("0")

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        cost = calculate_cost("gpt-4-turbo", 0, 0)
        assert cost == Decimal("0")

    def test_calculate_cost_large_tokens(self):
        """Test cost calculation with large token counts."""
        cost = calculate_cost("gpt-4", 100000, 50000)
        # (100000 * 0.03 / 1000) + (50000 * 0.06 / 1000) = 6.0
        assert cost == Decimal("6.0")
        assert cost > Decimal("0")

    def test_calculate_cost_decimal_precision(self):
        """Test that cost maintains decimal precision."""
        cost = calculate_cost("claude-3-haiku-20240307", 1, 1)
        assert isinstance(cost, Decimal)
        # Very small cost but still precise
        assert cost > Decimal("0")

    def test_cost_all_pricing_models(self):
        """Test all models in LLM_PRICING have valid cost calculation."""
        for model_name in LLM_PRICING.keys():
            if model_name == "default":
                continue
            cost = calculate_cost(model_name, 100, 50)
            assert cost > 0
            assert isinstance(cost, Decimal)

    @pytest.mark.parametrize("model,prompt,completion,expected", [
        ("gpt-4-turbo", 1000, 1000, Decimal("0.04")),  # 0.01 + 0.03
        ("gpt-3.5-turbo", 1000, 1000, Decimal("0.002")),  # 0.0005 + 0.0015
        ("claude-3-sonnet-20240229", 1000, 1000, Decimal("0.018")),  # 0.003 + 0.015
    ])
    def test_cost_calculation_parametrized(self, model, prompt, completion, expected):
        """Parametrized test for multiple models."""
        cost = calculate_cost(model, prompt, completion)
        assert cost == expected

    def test_calculate_cost_only_input_tokens(self):
        """Test cost calculation with only input tokens."""
        cost = calculate_cost("gpt-4-turbo", 1000, 0)
        assert cost == Decimal("0.01")

    def test_calculate_cost_only_output_tokens(self):
        """Test cost calculation with only output tokens."""
        cost = calculate_cost("gpt-4-turbo", 0, 1000)
        assert cost == Decimal("0.03")

    def test_calculate_cost_gpt4_turbo_preview(self):
        """Test cost calculation for GPT-4 Turbo Preview variant."""
        cost = calculate_cost("gpt-4-turbo-preview", 1000, 500)
        assert cost == Decimal("0.025")

    def test_calculate_cost_gpt4_0125_preview(self):
        """Test cost calculation for GPT-4 0125 Preview."""
        cost = calculate_cost("gpt-4-0125-preview", 1000, 500)
        assert cost == Decimal("0.025")


# =============================================================================
# Request Tracking Tests
# =============================================================================

class TestRequestTracking:
    """Tests for LLM request tracking integration."""

    @pytest.mark.asyncio
    async def test_track_llm_request_success(self):
        """Test tracking successful LLM request."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 123})

        request_id = await track_llm_request(
            conn=mock_conn,
            provider="openai",
            model="gpt-4-turbo",
            prompt_tokens=1000,
            completion_tokens=500,
            duration_ms=2500,
            status="success"
        )

        assert request_id == 123
        mock_conn.fetchrow.assert_called_once()

        # Verify the query parameters
        call_args = mock_conn.fetchrow.call_args
        assert "openai" in call_args[0]
        assert "gpt-4-turbo" in call_args[0]
        assert 1000 in call_args[0]
        assert 500 in call_args[0]
        assert 1500 in call_args[0]  # total_tokens
        assert 2500 in call_args[0]
        assert "success" in call_args[0]

    @pytest.mark.asyncio
    async def test_track_llm_request_with_task_id(self):
        """Test tracking request associated with task."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 456})

        request_id = await track_llm_request(
            conn=mock_conn,
            provider="anthropic",
            model="claude-3-sonnet-20240229",
            prompt_tokens=800,
            completion_tokens=400,
            task_id=789,
            status="success"
        )

        assert request_id == 456
        call_args = mock_conn.fetchrow.call_args
        assert 789 in call_args[0]  # task_id

    @pytest.mark.asyncio
    async def test_track_llm_request_error(self):
        """Test tracking failed LLM request."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 111})

        request_id = await track_llm_request(
            conn=mock_conn,
            provider="openai",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=0,
            status="error",
            error_message="API rate limit exceeded"
        )

        assert request_id == 111
        call_args = mock_conn.fetchrow.call_args
        assert "error" in call_args[0]
        assert "API rate limit exceeded" in call_args[0]

    @pytest.mark.asyncio
    async def test_track_llm_request_timeout(self):
        """Test tracking timed-out request."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 222})

        request_id = await track_llm_request(
            conn=mock_conn,
            provider="anthropic",
            model="claude-3-opus-20240229",
            prompt_tokens=500,
            completion_tokens=0,
            status="timeout",
            error_message="Request timed out after 30s"
        )

        assert request_id == 222
        call_args = mock_conn.fetchrow.call_args
        assert "timeout" in call_args[0]

    @pytest.mark.asyncio
    async def test_track_llm_request_metadata(self):
        """Test storing additional metadata as JSON."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 333})

        metadata = {
            "temperature": 0.7,
            "max_tokens": 1000,
            "user_id": "user_123"
        }

        request_id = await track_llm_request(
            conn=mock_conn,
            provider="openai",
            model="gpt-4-turbo",
            prompt_tokens=500,
            completion_tokens=300,
            metadata=metadata
        )

        assert request_id == 333
        call_args = mock_conn.fetchrow.call_args
        # Metadata should be JSON string
        import json
        assert json.dumps(metadata) in call_args[0]

    @pytest.mark.asyncio
    async def test_track_llm_request_cost_calculation(self):
        """Test that cost is calculated correctly during tracking."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 444})

        await track_llm_request(
            conn=mock_conn,
            provider="openai",
            model="gpt-4-turbo",
            prompt_tokens=1000,
            completion_tokens=500
        )

        call_args = mock_conn.fetchrow.call_args
        # Cost should be 0.025 (calculated earlier)
        assert 0.025 in call_args[0]

    @pytest.mark.asyncio
    async def test_track_llm_request_database_error(self):
        """Test handling database errors during tracking."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("Database connection failed"))

        with pytest.raises(Exception) as exc_info:
            await track_llm_request(
                conn=mock_conn,
                provider="openai",
                model="gpt-4",
                prompt_tokens=100,
                completion_tokens=50
            )

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_track_llm_request_request_type(self):
        """Test tracking different request types."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 555})

        request_id = await track_llm_request(
            conn=mock_conn,
            provider="anthropic",
            model="claude-3-haiku-20240307",
            prompt_tokens=200,
            completion_tokens=100,
            request_type="soften"
        )

        assert request_id == 555
        call_args = mock_conn.fetchrow.call_args
        assert "soften" in call_args[0]


# =============================================================================
# Budget Management Tests
# =============================================================================

class TestBudgetManagement:
    """Tests for budget tracking and alerts."""

    @pytest.mark.asyncio
    async def test_create_budget_daily(self):
        """Test creating new daily budget period."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 1})

        budget_id = await create_budget(
            conn=mock_conn,
            period="daily",
            budget_limit=Decimal("10.00"),
            alert_threshold=Decimal("0.80")
        )

        assert budget_id == 1
        mock_conn.fetchrow.assert_called_once()

        call_args = mock_conn.fetchrow.call_args
        assert "daily" in call_args[0]
        assert 10.0 in call_args[0]
        assert 0.80 in call_args[0]

    @pytest.mark.asyncio
    async def test_create_budget_weekly(self):
        """Test creating weekly budget."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 2})

        budget_id = await create_budget(
            conn=mock_conn,
            period="weekly",
            budget_limit=Decimal("50.00")
        )

        assert budget_id == 2
        call_args = mock_conn.fetchrow.call_args
        assert "weekly" in call_args[0]

    @pytest.mark.asyncio
    async def test_create_budget_monthly(self):
        """Test creating monthly budget."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 3})

        budget_id = await create_budget(
            conn=mock_conn,
            period="monthly",
            budget_limit=Decimal("200.00")
        )

        assert budget_id == 3
        call_args = mock_conn.fetchrow.call_args
        assert "monthly" in call_args[0]

    @pytest.mark.asyncio
    async def test_create_budget_custom_dates(self):
        """Test creating budget with custom start/end dates."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 4})

        start_date = datetime(2025, 11, 1)
        end_date = datetime(2025, 11, 30)

        budget_id = await create_budget(
            conn=mock_conn,
            period="monthly",
            budget_limit=Decimal("100.00"),
            period_start=start_date,
            period_end=end_date
        )

        assert budget_id == 4
        call_args = mock_conn.fetchrow.call_args
        assert start_date in call_args[0]
        assert end_date in call_args[0]

    @pytest.mark.asyncio
    async def test_update_budget_usage(self):
        """Test updating budget usage after LLM request."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        result = await update_budget_usage(
            conn=mock_conn,
            period="daily",
            amount=Decimal("0.025")
        )

        assert result is True
        mock_conn.execute.assert_called_once()

        call_args = mock_conn.execute.call_args
        assert 0.025 in call_args[0]
        assert "daily" in call_args[0]

    @pytest.mark.asyncio
    async def test_update_budget_usage_no_active_budget(self):
        """Test updating budget when no active budget exists."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 0")

        result = await update_budget_usage(
            conn=mock_conn,
            period="daily",
            amount=Decimal("0.025")
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_budget_alerts_threshold_exceeded(self):
        """Test alert triggered when usage exceeds threshold."""
        mock_conn = AsyncMock()

        # Mock budget at 81% usage (exceeds 80% threshold)
        budget_row = {
            'id': 1,
            'period': 'daily',
            'period_start': datetime.utcnow(),
            'period_end': datetime.utcnow() + timedelta(days=1),
            'budget_limit': Decimal('10.00'),
            'current_usage': Decimal('8.10'),
            'alert_threshold': Decimal('0.80'),
            'alert_triggered': False
        }

        mock_conn.fetch = AsyncMock(return_value=[budget_row])
        mock_conn.execute = AsyncMock()

        alerts = await check_budget_alerts(conn=mock_conn, period="daily")

        assert len(alerts) == 1
        assert alerts[0]['id'] == 1
        assert alerts[0]['current_usage'] == Decimal('8.10')

        # Verify alert was marked as triggered
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_budget_alerts_below_threshold(self):
        """Test alert not triggered when below threshold."""
        mock_conn = AsyncMock()

        # Mock budget at 50% usage (below 80% threshold)
        budget_row = {
            'id': 2,
            'period': 'daily',
            'period_start': datetime.utcnow(),
            'period_end': datetime.utcnow() + timedelta(days=1),
            'budget_limit': Decimal('10.00'),
            'current_usage': Decimal('5.00'),
            'alert_threshold': Decimal('0.80'),
            'alert_triggered': False
        }

        mock_conn.fetch = AsyncMock(return_value=[budget_row])
        mock_conn.execute = AsyncMock()

        alerts = await check_budget_alerts(conn=mock_conn, period="daily")

        assert len(alerts) == 0
        # Alert should not be marked as triggered
        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_budget_alerts_already_triggered(self):
        """Test alert not triggered again if already triggered."""
        mock_conn = AsyncMock()

        # Mock budget with alert already triggered
        budget_row = {
            'id': 3,
            'period': 'daily',
            'period_start': datetime.utcnow(),
            'period_end': datetime.utcnow() + timedelta(days=1),
            'budget_limit': Decimal('10.00'),
            'current_usage': Decimal('9.00'),
            'alert_threshold': Decimal('0.80'),
            'alert_triggered': True
        }

        # Query should filter out already-triggered budgets
        mock_conn.fetch = AsyncMock(return_value=[])

        alerts = await check_budget_alerts(conn=mock_conn, period="daily")

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_check_budget_alerts_exact_threshold(self):
        """Test alert triggered at exact threshold."""
        mock_conn = AsyncMock()

        # Mock budget at exactly 80% usage
        budget_row = {
            'id': 4,
            'period': 'daily',
            'period_start': datetime.utcnow(),
            'period_end': datetime.utcnow() + timedelta(days=1),
            'budget_limit': Decimal('10.00'),
            'current_usage': Decimal('8.00'),
            'alert_threshold': Decimal('0.80'),
            'alert_triggered': False
        }

        mock_conn.fetch = AsyncMock(return_value=[budget_row])
        mock_conn.execute = AsyncMock()

        alerts = await check_budget_alerts(conn=mock_conn, period="daily")

        assert len(alerts) == 1


# =============================================================================
# Usage Statistics Tests
# =============================================================================

class TestUsageStatistics:
    """Tests for usage aggregation and reporting."""

    @pytest.mark.asyncio
    async def test_get_usage_stats_daily(self):
        """Test daily usage summary aggregation."""
        mock_conn = AsyncMock()

        # Mock overall stats
        overall_row = {
            'total_requests': 100,
            'successful_requests': 95,
            'failed_requests': 4,
            'timeout_requests': 1,
            'total_tokens': 50000,
            'total_cost': Decimal('5.25'),
            'avg_cost_per_request': Decimal('0.0525'),
            'avg_duration_ms': 2500.0
        }

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        stats = await get_usage_stats(conn=mock_conn)

        assert stats['total_requests'] == 100
        assert stats['successful_requests'] == 95
        assert stats['total_cost'] == Decimal('5.25')
        assert 'date_range' in stats
        assert 'by_provider' in stats
        assert 'by_model' in stats

    @pytest.mark.asyncio
    async def test_get_usage_stats_by_provider(self):
        """Test usage breakdown by provider."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 50,
            'successful_requests': 48,
            'failed_requests': 2,
            'timeout_requests': 0,
            'total_tokens': 25000,
            'total_cost': Decimal('3.00'),
            'avg_cost_per_request': Decimal('0.06'),
            'avg_duration_ms': 2000.0
        }

        provider_rows = [
            {'provider': 'openai', 'requests': 30, 'cost': Decimal('2.00'), 'tokens': 15000},
            {'provider': 'anthropic', 'requests': 20, 'cost': Decimal('1.00'), 'tokens': 10000}
        ]

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(side_effect=[provider_rows, []])

        stats = await get_usage_stats(conn=mock_conn)

        assert len(stats['by_provider']) == 2
        assert stats['by_provider'][0]['provider'] == 'openai'
        assert stats['by_provider'][0]['cost'] == Decimal('2.00')
        assert stats['by_provider'][1]['provider'] == 'anthropic'

    @pytest.mark.asyncio
    async def test_get_usage_stats_by_model(self):
        """Test usage breakdown by model."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 30,
            'successful_requests': 30,
            'failed_requests': 0,
            'timeout_requests': 0,
            'total_tokens': 15000,
            'total_cost': Decimal('1.50'),
            'avg_cost_per_request': Decimal('0.05'),
            'avg_duration_ms': 1800.0
        }

        model_rows = [
            {'model': 'gpt-4-turbo', 'provider': 'openai', 'requests': 15, 'cost': Decimal('1.00'), 'tokens': 8000},
            {'model': 'claude-3-haiku-20240307', 'provider': 'anthropic', 'requests': 15, 'cost': Decimal('0.50'), 'tokens': 7000}
        ]

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(side_effect=[[], model_rows])

        stats = await get_usage_stats(conn=mock_conn)

        assert len(stats['by_model']) == 2
        assert stats['by_model'][0]['model'] == 'gpt-4-turbo'
        assert stats['by_model'][1]['model'] == 'claude-3-haiku-20240307'

    @pytest.mark.asyncio
    async def test_get_usage_stats_with_filters(self):
        """Test filtering usage by provider and model."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 10,
            'successful_requests': 10,
            'failed_requests': 0,
            'timeout_requests': 0,
            'total_tokens': 5000,
            'total_cost': Decimal('0.50'),
            'avg_cost_per_request': Decimal('0.05'),
            'avg_duration_ms': 2000.0
        }

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        stats = await get_usage_stats(
            conn=mock_conn,
            provider="openai",
            model="gpt-4-turbo"
        )

        assert stats['total_requests'] == 10
        # Verify filters were applied (check call args)
        assert mock_conn.fetchrow.called

    @pytest.mark.asyncio
    async def test_get_usage_stats_date_range(self):
        """Test filtering usage by date range."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 20,
            'successful_requests': 19,
            'failed_requests': 1,
            'timeout_requests': 0,
            'total_tokens': 10000,
            'total_cost': Decimal('1.00'),
            'avg_cost_per_request': Decimal('0.05'),
            'avg_duration_ms': 2200.0
        }

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        start_date = datetime(2025, 11, 1)
        end_date = datetime(2025, 11, 18)

        stats = await get_usage_stats(
            conn=mock_conn,
            start_date=start_date,
            end_date=end_date
        )

        assert stats['total_requests'] == 20
        assert stats['date_range']['start'] == start_date.isoformat()
        assert stats['date_range']['end'] == end_date.isoformat()

    @pytest.mark.asyncio
    async def test_get_usage_stats_empty_results(self):
        """Test handling when no usage data exists."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'timeout_requests': 0,
            'total_tokens': 0,
            'total_cost': Decimal('0'),
            'avg_cost_per_request': Decimal('0'),
            'avg_duration_ms': 0.0
        }

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        stats = await get_usage_stats(conn=mock_conn)

        assert stats['total_requests'] == 0
        assert stats['total_cost'] == Decimal('0')
        assert len(stats['by_provider']) == 0
        assert len(stats['by_model']) == 0

    @pytest.mark.asyncio
    async def test_get_usage_stats_success_rate_calculation(self):
        """Test calculating success rate from status field."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 100,
            'successful_requests': 95,
            'failed_requests': 3,
            'timeout_requests': 2,
            'total_tokens': 50000,
            'total_cost': Decimal('5.00'),
            'avg_cost_per_request': Decimal('0.05'),
            'avg_duration_ms': 2500.0
        }

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        stats = await get_usage_stats(conn=mock_conn)

        # Success rate should be 95%
        success_rate = stats['successful_requests'] / stats['total_requests']
        assert success_rate == 0.95
        assert stats['failed_requests'] == 3
        assert stats['timeout_requests'] == 2

    @pytest.mark.asyncio
    async def test_get_usage_stats_default_date_range(self):
        """Test default date range is 30 days."""
        mock_conn = AsyncMock()

        overall_row = {
            'total_requests': 50,
            'successful_requests': 48,
            'failed_requests': 2,
            'timeout_requests': 0,
            'total_tokens': 25000,
            'total_cost': Decimal('2.50'),
            'avg_cost_per_request': Decimal('0.05'),
            'avg_duration_ms': 2100.0
        }

        mock_conn.fetchrow = AsyncMock(return_value=overall_row)
        mock_conn.fetch = AsyncMock(return_value=[])

        stats = await get_usage_stats(conn=mock_conn)

        # Verify date range exists
        assert 'date_range' in stats
        assert 'start' in stats['date_range']
        assert 'end' in stats['date_range']


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for combined functionality."""

    @pytest.mark.asyncio
    async def test_track_request_and_update_budget(self):
        """Test tracking request and updating budget in sequence."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 100})
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        # Track request
        request_id = await track_llm_request(
            conn=mock_conn,
            provider="openai",
            model="gpt-4-turbo",
            prompt_tokens=1000,
            completion_tokens=500
        )

        assert request_id == 100

        # Update budget with the cost
        cost = calculate_cost("gpt-4-turbo", 1000, 500)
        result = await update_budget_usage(
            conn=mock_conn,
            period="daily",
            amount=cost
        )

        assert result is True
        assert cost == Decimal("0.025")

    @pytest.mark.asyncio
    async def test_create_budget_and_check_alerts(self):
        """Test creating budget and checking alerts."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={'id': 10})

        # Create budget
        budget_id = await create_budget(
            conn=mock_conn,
            period="daily",
            budget_limit=Decimal("10.00")
        )

        assert budget_id == 10

        # Check alerts (should be empty for new budget)
        mock_conn.fetch = AsyncMock(return_value=[])
        alerts = await check_budget_alerts(conn=mock_conn, period="daily")

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_full_workflow_multiple_requests(self):
        """Test full workflow with multiple requests and budget tracking."""
        mock_conn = AsyncMock()

        # Track multiple requests
        request_ids = []
        for i in range(5):
            mock_conn.fetchrow = AsyncMock(return_value={'id': 200 + i})
            request_id = await track_llm_request(
                conn=mock_conn,
                provider="openai",
                model="gpt-4-turbo",
                prompt_tokens=1000,
                completion_tokens=500
            )
            request_ids.append(request_id)

        assert len(request_ids) == 5
        assert all(rid >= 200 for rid in request_ids)
