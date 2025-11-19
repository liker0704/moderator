"""
Statistics Service.

Provides high-level statistics generation and formatting services.
Aggregates data from StatsDAO and formats it for display.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncpg

from ..database.dao.stats_dao import StatsDAO
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StatsService:
    """
    Service for generating and formatting statistics reports.

    Provides methods to generate comprehensive statistics reports and
    format data for human-readable display.
    """

    @staticmethod
    async def generate_stats_report(
        conn: asyncpg.Connection,
        user_id: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive statistics report for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to generate stats for
            period_days: Number of days to analyze (default: 30)

        Returns:
            Dictionary containing all statistics

        Example:
            >>> report = await StatsService.generate_stats_report(conn, user_id=1, period_days=30)
            >>> print(f"Tasks completed: {report['task_stats']['completed']}")
        """
        logger.info(f"Generating stats report for user {user_id}, period: {period_days} days")

        # Gather all statistics in parallel where possible
        task_stats = await StatsDAO.get_task_stats(conn, user_id, period_days)
        avg_response_time = await StatsDAO.get_average_response_time(conn, user_id, period_days)
        response_percentiles = await StatsDAO.get_response_time_percentiles(conn, user_id, period_days)
        response_distribution = await StatsDAO.get_response_time_distribution(conn, user_id, period_days)
        channel_load = await StatsDAO.get_channel_load(conn, user_id, period_days, limit=10)
        unclosed_tasks = await StatsDAO.get_unclosed_tasks(conn, user_id, hours=24)
        llm_stats = await StatsDAO.get_llm_usage_stats(conn, user_id, period_days)
        llm_breakdown = await StatsDAO.get_llm_provider_breakdown(conn, user_id, period_days)
        platform_breakdown = await StatsDAO.get_platform_breakdown(conn, user_id, period_days)
        hourly_distribution = await StatsDAO.get_hourly_distribution(conn, user_id, days=min(period_days, 7))

        report = {
            'period_days': period_days,
            'generated_at': datetime.utcnow(),
            'task_stats': task_stats,
            'response_time': {
                'average': avg_response_time,
                'percentiles': response_percentiles,
                'distribution': response_distribution
            },
            'channel_load': channel_load,
            'unclosed_tasks': unclosed_tasks,
            'llm_usage': llm_stats,
            'llm_breakdown': llm_breakdown,
            'platform_breakdown': platform_breakdown,
            'hourly_distribution': hourly_distribution
        }

        logger.info(f"Stats report generated successfully for user {user_id}")
        return report

    @staticmethod
    def format_duration(seconds: Optional[float]) -> str:
        """
        Format duration in seconds to human-readable string.

        Args:
            seconds: Duration in seconds (can be None)

        Returns:
            Formatted duration string (e.g., "5m", "2h 30m", "1d 3h")

        Example:
            >>> StatsService.format_duration(300)
            '5m'
            >>> StatsService.format_duration(7200)
            '2h'
            >>> StatsService.format_duration(90000)
            '1d 1h'
        """
        if seconds is None or seconds < 0:
            return "N/A"

        seconds = int(seconds)

        if seconds < 60:
            return f"{seconds}s"

        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"

        hours = minutes // 60
        remaining_minutes = minutes % 60
        if hours < 24:
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            return f"{hours}h"

        days = hours // 24
        remaining_hours = hours % 24
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        return f"{days}d"

    @staticmethod
    def format_cost(amount: float) -> str:
        """
        Format cost amount in USD.

        Args:
            amount: Cost in USD

        Returns:
            Formatted cost string

        Example:
            >>> StatsService.format_cost(1.23456)
            '$1.23'
            >>> StatsService.format_cost(0.001234)
            '$0.0012'
        """
        if amount == 0:
            return "$0.00"

        # For very small amounts, show more decimals
        if amount < 0.01:
            return f"${amount:.4f}"
        elif amount < 1:
            return f"${amount:.3f}"
        else:
            return f"${amount:.2f}"

    @staticmethod
    def calculate_percentile(values: List[float], percentile: float) -> Optional[float]:
        """
        Calculate percentile from list of values.

        Args:
            values: List of numeric values
            percentile: Percentile to calculate (0-1, e.g., 0.95 for P95)

        Returns:
            Percentile value or None if no values

        Example:
            >>> values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            >>> StatsService.calculate_percentile(values, 0.95)
            9.5
        """
        if not values:
            return None

        sorted_values = sorted(values)
        n = len(sorted_values)
        index = percentile * (n - 1)

        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, n - 1)
            fraction = index - lower_index
            return sorted_values[lower_index] * (1 - fraction) + sorted_values[upper_index] * fraction

    @staticmethod
    def format_number(number: int) -> str:
        """
        Format large numbers with thousands separators.

        Args:
            number: Number to format

        Returns:
            Formatted number string

        Example:
            >>> StatsService.format_number(1234567)
            '1,234,567'
        """
        return f"{number:,}"

    @staticmethod
    def create_progress_bar(
        value: int,
        max_value: int,
        width: int = 10,
        filled_char: str = "█",
        empty_char: str = "░"
    ) -> str:
        """
        Create a text-based progress bar.

        Args:
            value: Current value
            max_value: Maximum value
            width: Width of the bar in characters
            filled_char: Character for filled portion
            empty_char: Character for empty portion

        Returns:
            Progress bar string

        Example:
            >>> StatsService.create_progress_bar(7, 10, width=10)
            '███████░░░'
        """
        if max_value == 0:
            return empty_char * width

        ratio = min(value / max_value, 1.0)
        filled = int(ratio * width)
        empty = width - filled

        return filled_char * filled + empty_char * empty

    @staticmethod
    def calculate_completion_rate(completed: int, total: int) -> float:
        """
        Calculate completion rate as percentage.

        Args:
            completed: Number of completed items
            total: Total number of items

        Returns:
            Completion rate (0-100)

        Example:
            >>> StatsService.calculate_completion_rate(75, 100)
            75.0
        """
        if total == 0:
            return 0.0
        return (completed / total) * 100

    @staticmethod
    def get_peak_hour(hourly_distribution: Dict[int, int]) -> Optional[int]:
        """
        Get the hour with the most activity.

        Args:
            hourly_distribution: Dictionary mapping hour (0-23) to count

        Returns:
            Hour with most activity (0-23) or None if no data

        Example:
            >>> dist = {9: 10, 10: 15, 11: 8}
            >>> StatsService.get_peak_hour(dist)
            10
        """
        if not hourly_distribution:
            return None

        max_count = 0
        peak_hour = None

        for hour, count in hourly_distribution.items():
            if count > max_count:
                max_count = count
                peak_hour = hour

        return peak_hour

    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Format percentage value.

        Args:
            value: Percentage value (0-100)
            decimals: Number of decimal places

        Returns:
            Formatted percentage string

        Example:
            >>> StatsService.format_percentage(75.5)
            '75.5%'
        """
        return f"{value:.{decimals}f}%"

    @staticmethod
    def get_trend_indicator(current: int, previous: int) -> str:
        """
        Get trend indicator emoji based on comparison.

        Args:
            current: Current value
            previous: Previous value

        Returns:
            Trend indicator emoji

        Example:
            >>> StatsService.get_trend_indicator(100, 80)
            '↑'
        """
        if current > previous:
            return "↑"
        elif current < previous:
            return "↓"
        else:
            return "→"

    @staticmethod
    def format_channel_id(channel_id: str, max_length: int = 12) -> str:
        """
        Format channel ID for display.

        Args:
            channel_id: Channel ID string
            max_length: Maximum length to display

        Returns:
            Formatted channel ID

        Example:
            >>> StatsService.format_channel_id("123456789012345678")
            '123456789012...'
        """
        if not channel_id:
            return "Unknown"

        channel_id = str(channel_id)
        if len(channel_id) <= max_length:
            return channel_id

        return channel_id[:max_length] + "..."

    @staticmethod
    def calculate_success_rate(successful: int, total: int) -> float:
        """
        Calculate success rate as percentage.

        Args:
            successful: Number of successful items
            total: Total number of items

        Returns:
            Success rate (0-100)

        Example:
            >>> StatsService.calculate_success_rate(95, 100)
            95.0
        """
        if total == 0:
            return 0.0
        return (successful / total) * 100

    @staticmethod
    def format_tokens(tokens: int) -> str:
        """
        Format token count for display.

        Args:
            tokens: Number of tokens

        Returns:
            Formatted token count

        Example:
            >>> StatsService.format_tokens(1234567)
            '1.23M'
        """
        if tokens < 1000:
            return str(tokens)
        elif tokens < 1000000:
            return f"{tokens / 1000:.1f}K"
        else:
            return f"{tokens / 1000000:.2f}M"

    @staticmethod
    def get_busiest_channels(
        channel_load: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get the busiest channels from channel load data.

        Args:
            channel_load: List of channel load dicts
            limit: Maximum number of channels to return

        Returns:
            Top N busiest channels

        Example:
            >>> channels = [{'channel_id': '123', 'message_count': 100}, ...]
            >>> top = StatsService.get_busiest_channels(channels, limit=3)
        """
        return channel_load[:limit]

    @staticmethod
    def summarize_response_distribution(
        distribution: Dict[str, int]
    ) -> str:
        """
        Create a summary of response time distribution.

        Args:
            distribution: Response time distribution dict

        Returns:
            Summary string

        Example:
            >>> dist = {'under_5min': 10, 'under_30min': 20, 'under_1h': 5, 'under_6h': 3, 'over_6h': 2}
            >>> summary = StatsService.summarize_response_distribution(dist)
        """
        total = sum(distribution.values())
        if total == 0:
            return "No data"

        quick_responses = distribution.get('under_5min', 0) + distribution.get('under_30min', 0)
        quick_pct = (quick_responses / total) * 100

        return f"{quick_pct:.0f}% under 30 min"

    @staticmethod
    def format_unclosed_task_summary(
        unclosed_tasks: List[Dict[str, Any]]
    ) -> str:
        """
        Format summary of unclosed tasks.

        Args:
            unclosed_tasks: List of unclosed task dicts

        Returns:
            Summary string

        Example:
            >>> tasks = [{'age_seconds': 86400, ...}, {'age_seconds': 172800, ...}]
            >>> summary = StatsService.format_unclosed_task_summary(tasks)
        """
        if not unclosed_tasks:
            return "No unclosed tasks over 24h"

        count = len(unclosed_tasks)
        oldest_age = max(task['age_seconds'] for task in unclosed_tasks)
        oldest_formatted = StatsService.format_duration(oldest_age)

        return f"{count} task{'s' if count != 1 else ''}, oldest: {oldest_formatted}"
