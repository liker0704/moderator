"""
Tests for statistics and metrics functionality.

Tests StatsDAO, StatsService, and stats formatting.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal


@pytest.mark.asyncio
async def test_stats_dao_imports():
    """Test that StatsDAO can be imported."""
    from backend.src.database.dao.stats_dao import StatsDAO
    assert StatsDAO is not None


@pytest.mark.asyncio
async def test_stats_service_imports():
    """Test that StatsService can be imported."""
    from backend.src.services.stats import StatsService
    assert StatsService is not None


@pytest.mark.asyncio
async def test_stats_formatting_functions():
    """Test StatsService formatting functions."""
    from backend.src.services.stats import StatsService

    # Test format_duration
    assert StatsService.format_duration(30) == "30s"
    assert StatsService.format_duration(300) == "5m"
    assert StatsService.format_duration(3600) == "1h"
    assert StatsService.format_duration(3660) == "1h 1m"
    assert StatsService.format_duration(86400) == "1d"
    assert StatsService.format_duration(90000) == "1d 1h"
    assert StatsService.format_duration(None) == "N/A"

    # Test format_cost
    assert StatsService.format_cost(0) == "$0.00"
    assert StatsService.format_cost(1.23456) == "$1.23"
    assert StatsService.format_cost(0.001234) == "$0.0012"
    assert StatsService.format_cost(100.5) == "$100.50"

    # Test format_number
    assert StatsService.format_number(1234) == "1,234"
    assert StatsService.format_number(1234567) == "1,234,567"

    # Test format_tokens
    assert StatsService.format_tokens(500) == "500"
    assert StatsService.format_tokens(1500) == "1.5K"
    assert StatsService.format_tokens(1500000) == "1.50M"

    # Test format_percentage
    assert StatsService.format_percentage(75.5) == "75.5%"
    assert StatsService.format_percentage(100.0) == "100.0%"

    # Test calculate_completion_rate
    assert StatsService.calculate_completion_rate(75, 100) == 75.0
    assert StatsService.calculate_completion_rate(0, 0) == 0.0

    # Test calculate_success_rate
    assert StatsService.calculate_success_rate(95, 100) == 95.0
    assert StatsService.calculate_success_rate(0, 0) == 0.0


@pytest.mark.asyncio
async def test_stats_progress_bar():
    """Test progress bar generation."""
    from backend.src.services.stats import StatsService

    # Test normal cases
    bar = StatsService.create_progress_bar(5, 10, width=10)
    assert len(bar) == 10
    assert bar.count("█") == 5
    assert bar.count("░") == 5

    # Test full bar
    bar = StatsService.create_progress_bar(10, 10, width=10)
    assert bar == "█" * 10

    # Test empty bar
    bar = StatsService.create_progress_bar(0, 10, width=10)
    assert bar == "░" * 10

    # Test zero max_value
    bar = StatsService.create_progress_bar(5, 0, width=10)
    assert bar == "░" * 10


@pytest.mark.asyncio
async def test_stats_percentile_calculation():
    """Test percentile calculation."""
    from backend.src.services.stats import StatsService

    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    # Test P50 (median)
    p50 = StatsService.calculate_percentile(values, 0.50)
    assert p50 == 5.5

    # Test P95
    p95 = StatsService.calculate_percentile(values, 0.95)
    assert p95 == 9.5

    # Test P99
    p99 = StatsService.calculate_percentile(values, 0.99)
    assert p99 == 9.9

    # Test empty list
    assert StatsService.calculate_percentile([], 0.5) is None


@pytest.mark.asyncio
async def test_stats_card_formatting_imports():
    """Test that stats card formatting functions can be imported."""
    from backend.src.telegram.cards import format_stats_card, create_stats_keyboard

    assert format_stats_card is not None
    assert create_stats_keyboard is not None


@pytest.mark.asyncio
async def test_stats_keyboard_generation():
    """Test stats keyboard generation."""
    from backend.src.telegram.cards import create_stats_keyboard

    # Test with default period
    keyboard = create_stats_keyboard(30)
    assert 'inline_keyboard' in keyboard
    assert len(keyboard['inline_keyboard']) == 2  # Period row + Refresh row

    # Check period buttons
    period_row = keyboard['inline_keyboard'][0]
    assert len(period_row) == 3  # 7, 30, 90 days

    # Check that current period is marked
    assert any('✓' in btn['text'] for btn in period_row)

    # Test with different period
    keyboard = create_stats_keyboard(7)
    period_row = keyboard['inline_keyboard'][0]
    assert '✓ 7 days' in [btn['text'] for btn in period_row]


@pytest.mark.asyncio
async def test_stats_helper_functions():
    """Test StatsService helper functions."""
    from backend.src.services.stats import StatsService

    # Test get_peak_hour
    hourly_dist = {9: 10, 10: 15, 11: 8}
    assert StatsService.get_peak_hour(hourly_dist) == 10
    assert StatsService.get_peak_hour({}) is None

    # Test format_channel_id
    assert StatsService.format_channel_id("123456789012345678", 12) == "123456789012..."
    assert StatsService.format_channel_id("123", 12) == "123"
    assert StatsService.format_channel_id(None, 12) == "Unknown"

    # Test get_trend_indicator
    assert StatsService.get_trend_indicator(100, 80) == "↑"
    assert StatsService.get_trend_indicator(80, 100) == "↓"
    assert StatsService.get_trend_indicator(100, 100) == "→"

    # Test summarize_response_distribution
    dist = {'under_5min': 10, 'under_30min': 20, 'under_1h': 5, 'under_6h': 3, 'over_6h': 2}
    summary = StatsService.summarize_response_distribution(dist)
    assert "75%" in summary  # (10+20)/40 = 75%
    assert "30 min" in summary

    # Test format_unclosed_task_summary
    assert StatsService.format_unclosed_task_summary([]) == "No unclosed tasks over 24h"

    tasks = [
        {'age_seconds': 86400, 'id': 1},
        {'age_seconds': 172800, 'id': 2}
    ]
    summary = StatsService.format_unclosed_task_summary(tasks)
    assert "2 tasks" in summary
    assert "2d" in summary  # Oldest is 172800 seconds = 2 days


@pytest.mark.asyncio
async def test_stats_card_generation():
    """Test stats card generation with mock data."""
    from backend.src.telegram.cards import format_stats_card

    # Create mock stats data
    mock_stats = {
        'period_days': 30,
        'generated_at': datetime.utcnow(),
        'task_stats': {
            'total': 100,
            'completed': 75,
            'pending': 20,
            'muted': 3,
            'error': 2
        },
        'response_time': {
            'average': 1800,  # 30 minutes
            'percentiles': {
                'p50': 1200,
                'p95': 3600,
                'p99': 7200
            },
            'distribution': {
                'under_5min': 10,
                'under_30min': 50,
                'under_1h': 20,
                'under_6h': 10,
                'over_6h': 10
            }
        },
        'channel_load': [
            {'platform': 'discord', 'channel_id': '123456789', 'message_count': 50},
            {'platform': 'telegram', 'channel_id': '987654321', 'message_count': 30}
        ],
        'unclosed_tasks': [],
        'llm_usage': {
            'total_requests': 50,
            'successful_requests': 48,
            'failed_requests': 2,
            'total_cost': 1.25,
            'avg_cost': 0.025,
            'total_tokens': 100000,
            'avg_tokens': 2000,
            'total_prompt_tokens': 60000,
            'total_completion_tokens': 40000,
            'avg_duration_ms': 1500
        },
        'llm_breakdown': [
            {
                'provider': 'openai',
                'model': 'gpt-4-turbo',
                'request_count': 30,
                'total_cost': 0.90,
                'total_tokens': 60000
            }
        ],
        'platform_breakdown': {
            'discord': 70,
            'telegram': 30
        },
        'hourly_distribution': {
            9: 10, 10: 15, 11: 12, 14: 20, 15: 18
        }
    }

    # Generate card
    card = format_stats_card(mock_stats, 30)

    # Verify card content
    assert "📊 Statistics Report" in card
    assert "Last 30 days" in card
    assert "Task Overview" in card
    assert "Response Time" in card
    assert "Channel Activity" in card
    assert "LLM Usage" in card
    assert "Activity Pattern" in card

    # Verify stats are included
    assert "100" in card  # total tasks
    assert "75" in card   # completed tasks
    assert "$1.25" in card  # total cost

    # Verify it's not truncated (should be under limit)
    assert "[Report truncated...]" not in card


@pytest.mark.asyncio
async def test_stats_command_handler_import():
    """Test that stats command handler can be imported."""
    from backend.src.telegram.handlers import cmd_stats
    assert cmd_stats is not None


@pytest.mark.asyncio
async def test_stats_callback_handlers_import():
    """Test that stats callback handlers can be imported."""
    from backend.src.telegram.handlers import callback_stats_period, callback_stats_refresh
    assert callback_stats_period is not None
    assert callback_stats_refresh is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
