"""
Statistics Data Access Object.

Provides async database operations for statistics and metrics using asyncpg.
Handles retrieval of various statistics including response times, channel load,
LLM usage, and task metrics.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import asyncpg

logger = logging.getLogger(__name__)


class StatsDAO:
    """
    Data Access Object for statistics queries.

    Provides comprehensive statistics for monitoring and analytics including
    task metrics, response times, channel activity, and LLM usage.
    """

    @staticmethod
    async def get_average_response_time(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> Optional[float]:
        """
        Calculate average response time from task creation to posting reply.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            Average response time in seconds, or None if no data

        Example:
            >>> avg_time = await StatsDAO.get_average_response_time(conn, user_id=1)
            >>> print(f"Average response: {avg_time / 60:.1f} minutes")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT AVG(EXTRACT(EPOCH FROM (r.posted_at - t.created_at))) as avg_seconds
            FROM tasks t
            JOIN replies r ON r.task_id = t.id
            WHERE t.assignee_user_id = $1
                AND t.created_at >= $2
                AND r.posted_at IS NOT NULL
                AND t.answered_at IS NOT NULL
        """

        row = await conn.fetchrow(query, user_id, cutoff_date)
        return float(row['avg_seconds']) if row and row['avg_seconds'] else None

    @staticmethod
    async def get_response_time_distribution(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> Dict[str, int]:
        """
        Get response time distribution in buckets.

        Buckets: <5min, <30min, <1h, <6h, >6h

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with bucket counts

        Example:
            >>> dist = await StatsDAO.get_response_time_distribution(conn, 1)
            >>> print(f"Under 5 min: {dist['under_5min']}")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) < 300
                ) as under_5min,
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) >= 300
                    AND EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) < 1800
                ) as under_30min,
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) >= 1800
                    AND EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) < 3600
                ) as under_1h,
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) >= 3600
                    AND EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) < 21600
                ) as under_6h,
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM (r.posted_at - t.created_at)) >= 21600
                ) as over_6h
            FROM tasks t
            JOIN replies r ON r.task_id = t.id
            WHERE t.assignee_user_id = $1
                AND t.created_at >= $2
                AND r.posted_at IS NOT NULL
        """

        row = await conn.fetchrow(query, user_id, cutoff_date)

        if row:
            return {
                'under_5min': row['under_5min'],
                'under_30min': row['under_30min'],
                'under_1h': row['under_1h'],
                'under_6h': row['under_6h'],
                'over_6h': row['over_6h']
            }
        else:
            return {
                'under_5min': 0,
                'under_30min': 0,
                'under_1h': 0,
                'under_6h': 0,
                'over_6h': 0
            }

    @staticmethod
    async def get_channel_load(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top N channels by message count.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by (tasks assigned to this user)
            days: Number of days to look back (default: 30)
            limit: Maximum number of channels to return (default: 10)

        Returns:
            List of channel dicts with message counts, sorted by count DESC

        Example:
            >>> channels = await StatsDAO.get_channel_load(conn, 1, limit=5)
            >>> for ch in channels:
            ...     print(f"{ch['channel_id']}: {ch['message_count']} messages")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                m.platform,
                m.server_id,
                m.channel_id,
                COUNT(*) as message_count
            FROM messages m
            JOIN tasks t ON t.source_message_id = m.id
            WHERE t.assignee_user_id = $1
                AND m.created_at >= $2
            GROUP BY m.platform, m.server_id, m.channel_id
            ORDER BY message_count DESC
            LIMIT $3
        """

        rows = await conn.fetch(query, user_id, cutoff_date, limit)
        channels = []

        for row in rows:
            channels.append({
                'platform': row['platform'],
                'server_id': row['server_id'],
                'channel_id': row['channel_id'],
                'message_count': row['message_count']
            })

        logger.debug(f"Retrieved {len(channels)} top channels for user {user_id}")
        return channels

    @staticmethod
    async def get_unclosed_tasks(
        conn: asyncpg.Connection,
        user_id: int,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get tasks older than N hours that are still open.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            hours: Age threshold in hours (default: 24)

        Returns:
            List of unclosed task dicts with age information

        Example:
            >>> old_tasks = await StatsDAO.get_unclosed_tasks(conn, 1, hours=24)
            >>> print(f"Found {len(old_tasks)} tasks older than 24 hours")
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = """
            SELECT
                t.id,
                t.source_message_id,
                t.created_at,
                EXTRACT(EPOCH FROM (NOW() - t.created_at)) as age_seconds,
                m.platform,
                m.server_id,
                m.channel_id,
                m.author_name,
                m.content
            FROM tasks t
            JOIN messages m ON m.id = t.source_message_id
            WHERE t.assignee_user_id = $1
                AND t.status = 'open'
                AND t.created_at < $2
            ORDER BY t.created_at ASC
        """

        rows = await conn.fetch(query, user_id, cutoff_time)
        tasks = []

        for row in rows:
            tasks.append({
                'id': row['id'],
                'source_message_id': row['source_message_id'],
                'created_at': row['created_at'],
                'age_seconds': int(row['age_seconds']),
                'platform': row['platform'],
                'server_id': row['server_id'],
                'channel_id': row['channel_id'],
                'author_name': row['author_name'],
                'content': row['content']
            })

        logger.debug(f"Found {len(tasks)} unclosed tasks older than {hours}h for user {user_id}")
        return tasks

    @staticmethod
    async def get_llm_usage_stats(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get LLM usage statistics (requests, cost, tokens).

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by (via tasks)
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with LLM usage statistics

        Example:
            >>> stats = await StatsDAO.get_llm_usage_stats(conn, 1)
            >>> print(f"Total cost: ${stats['total_cost']:.2f}")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                COUNT(*) as total_requests,
                COUNT(*) FILTER (WHERE lr.status = 'success') as successful_requests,
                COUNT(*) FILTER (WHERE lr.status = 'error') as failed_requests,
                COALESCE(SUM(lr.cost), 0) as total_cost,
                COALESCE(AVG(lr.cost), 0) as avg_cost,
                COALESCE(SUM(lr.prompt_tokens), 0) as total_prompt_tokens,
                COALESCE(SUM(lr.completion_tokens), 0) as total_completion_tokens,
                COALESCE(SUM(lr.total_tokens), 0) as total_tokens,
                COALESCE(AVG(lr.total_tokens), 0) as avg_tokens,
                COALESCE(AVG(lr.duration_ms), 0) as avg_duration_ms
            FROM llm_requests lr
            JOIN tasks t ON t.id = lr.task_id
            WHERE t.assignee_user_id = $1
                AND lr.created_at >= $2
        """

        row = await conn.fetchrow(query, user_id, cutoff_date)

        if row:
            return {
                'total_requests': row['total_requests'],
                'successful_requests': row['successful_requests'],
                'failed_requests': row['failed_requests'],
                'total_cost': float(row['total_cost']),
                'avg_cost': float(row['avg_cost']),
                'total_prompt_tokens': int(row['total_prompt_tokens']),
                'total_completion_tokens': int(row['total_completion_tokens']),
                'total_tokens': int(row['total_tokens']),
                'avg_tokens': float(row['avg_tokens']),
                'avg_duration_ms': float(row['avg_duration_ms'])
            }
        else:
            return {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'total_cost': 0.0,
                'avg_cost': 0.0,
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0,
                'total_tokens': 0,
                'avg_tokens': 0.0,
                'avg_duration_ms': 0.0
            }

    @staticmethod
    async def get_task_stats(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> Dict[str, int]:
        """
        Get task statistics (total, completed, pending).

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with task counts

        Example:
            >>> stats = await StatsDAO.get_task_stats(conn, 1)
            >>> print(f"Completed: {stats['completed']}/{stats['total']}")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'answered') as completed,
                COUNT(*) FILTER (WHERE status = 'open') as pending,
                COUNT(*) FILTER (WHERE status = 'muted') as muted,
                COUNT(*) FILTER (WHERE status = 'error') as error
            FROM tasks
            WHERE assignee_user_id = $1
                AND created_at >= $2
        """

        row = await conn.fetchrow(query, user_id, cutoff_date)

        if row:
            return {
                'total': row['total'],
                'completed': row['completed'],
                'pending': row['pending'],
                'muted': row['muted'],
                'error': row['error']
            }
        else:
            return {
                'total': 0,
                'completed': 0,
                'pending': 0,
                'muted': 0,
                'error': 0
            }

    @staticmethod
    async def get_platform_breakdown(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> Dict[str, int]:
        """
        Get message count breakdown by platform (Discord/Telegram).

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with platform message counts

        Example:
            >>> breakdown = await StatsDAO.get_platform_breakdown(conn, 1)
            >>> print(f"Discord: {breakdown['discord']}, Telegram: {breakdown['telegram']}")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                m.platform,
                COUNT(*) as message_count
            FROM messages m
            JOIN tasks t ON t.source_message_id = m.id
            WHERE t.assignee_user_id = $1
                AND m.created_at >= $2
            GROUP BY m.platform
        """

        rows = await conn.fetch(query, user_id, cutoff_date)

        breakdown = {'discord': 0, 'telegram': 0}
        for row in rows:
            platform = row['platform'].lower()
            if platform in breakdown:
                breakdown[platform] = row['message_count']

        return breakdown

    @staticmethod
    async def get_hourly_distribution(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 7
    ) -> Dict[int, int]:
        """
        Get message distribution by hour of day (0-23).

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 7)

        Returns:
            Dictionary mapping hour (0-23) to message count

        Example:
            >>> dist = await StatsDAO.get_hourly_distribution(conn, 1)
            >>> for hour in range(24):
            ...     print(f"{hour:02d}:00 - {dist.get(hour, 0)} messages")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                EXTRACT(HOUR FROM m.created_at) as hour,
                COUNT(*) as message_count
            FROM messages m
            JOIN tasks t ON t.source_message_id = m.id
            WHERE t.assignee_user_id = $1
                AND m.created_at >= $2
            GROUP BY EXTRACT(HOUR FROM m.created_at)
            ORDER BY hour
        """

        rows = await conn.fetch(query, user_id, cutoff_date)

        # Initialize all hours to 0
        distribution = {hour: 0 for hour in range(24)}

        for row in rows:
            hour = int(row['hour'])
            distribution[hour] = row['message_count']

        return distribution

    @staticmethod
    async def get_response_time_percentiles(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Optional[float]]:
        """
        Calculate response time percentiles (P50, P95, P99).

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            Dictionary with percentile values in seconds

        Example:
            >>> percentiles = await StatsDAO.get_response_time_percentiles(conn, 1)
            >>> print(f"P95: {percentiles['p95'] / 60:.1f} minutes")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                PERCENTILE_CONT(0.50) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (r.posted_at - t.created_at))
                ) as p50,
                PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (r.posted_at - t.created_at))
                ) as p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (r.posted_at - t.created_at))
                ) as p99
            FROM tasks t
            JOIN replies r ON r.task_id = t.id
            WHERE t.assignee_user_id = $1
                AND t.created_at >= $2
                AND r.posted_at IS NOT NULL
        """

        row = await conn.fetchrow(query, user_id, cutoff_date)

        if row:
            return {
                'p50': float(row['p50']) if row['p50'] else None,
                'p95': float(row['p95']) if row['p95'] else None,
                'p99': float(row['p99']) if row['p99'] else None
            }
        else:
            return {
                'p50': None,
                'p95': None,
                'p99': None
            }

    @staticmethod
    async def get_llm_provider_breakdown(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get LLM usage breakdown by provider and model.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            List of provider/model statistics

        Example:
            >>> breakdown = await StatsDAO.get_llm_provider_breakdown(conn, 1)
            >>> for item in breakdown:
            ...     print(f"{item['provider']} {item['model']}: ${item['cost']:.2f}")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                lr.provider,
                lr.model,
                COUNT(*) as request_count,
                COALESCE(SUM(lr.cost), 0) as total_cost,
                COALESCE(SUM(lr.total_tokens), 0) as total_tokens
            FROM llm_requests lr
            JOIN tasks t ON t.id = lr.task_id
            WHERE t.assignee_user_id = $1
                AND lr.created_at >= $2
                AND lr.status = 'success'
            GROUP BY lr.provider, lr.model
            ORDER BY total_cost DESC
        """

        rows = await conn.fetch(query, user_id, cutoff_date)

        breakdown = []
        for row in rows:
            breakdown.append({
                'provider': row['provider'],
                'model': row['model'],
                'request_count': row['request_count'],
                'total_cost': float(row['total_cost']),
                'total_tokens': int(row['total_tokens'])
            })

        return breakdown

    @staticmethod
    async def get_daily_task_trend(
        conn: asyncpg.Connection,
        user_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily task creation trend.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            List of daily statistics ordered by date DESC

        Example:
            >>> trend = await StatsDAO.get_daily_task_trend(conn, 1, days=7)
            >>> for day in trend:
            ...     print(f"{day['date']}: {day['task_count']} tasks")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as task_count,
                COUNT(*) FILTER (WHERE status = 'answered') as completed_count
            FROM tasks
            WHERE assignee_user_id = $1
                AND created_at >= $2
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """

        rows = await conn.fetch(query, user_id, cutoff_date)

        trend = []
        for row in rows:
            trend.append({
                'date': row['date'],
                'task_count': row['task_count'],
                'completed_count': row['completed_count']
            })

        return trend
