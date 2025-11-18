"""
LLM Monitoring Data Access Object.

Provides async database operations for LLM monitoring tables using asyncpg.
Handles retrieval of LLM request logs, usage statistics, and budget information.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import asyncpg

logger = logging.getLogger(__name__)


class LLMMonitoringDAO:
    """
    Data Access Object for LLM monitoring tables.

    Provides efficient queries for LLM request tracking, usage analytics,
    and budget management.
    """

    @staticmethod
    async def get_request_by_id(
        conn: asyncpg.Connection,
        request_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific LLM request by ID.

        Args:
            conn: AsyncPG database connection
            request_id: LLM request ID

        Returns:
            Dictionary with request data or None if not found

        Example:
            >>> request = await LLMMonitoringDAO.get_request_by_id(conn, 123)
            >>> if request:
            ...     print(f"Cost: ${request['cost']:.6f}")
        """
        query = """
            SELECT
                id, task_id, provider, model, request_type,
                prompt_tokens, completion_tokens, total_tokens,
                cost, duration_ms, status, error_message,
                metadata_json, created_at
            FROM llm_requests
            WHERE id = $1
        """

        row = await conn.fetchrow(query, request_id)
        return dict(row) if row else None

    @staticmethod
    async def get_requests_by_task(
        conn: asyncpg.Connection,
        task_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all LLM requests for a specific task.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID

        Returns:
            List of request dictionaries ordered by created_at DESC

        Example:
            >>> requests = await LLMMonitoringDAO.get_requests_by_task(conn, 42)
            >>> total_cost = sum(r['cost'] for r in requests)
        """
        query = """
            SELECT
                id, task_id, provider, model, request_type,
                prompt_tokens, completion_tokens, total_tokens,
                cost, duration_ms, status, error_message,
                metadata_json, created_at
            FROM llm_requests
            WHERE task_id = $1
            ORDER BY created_at DESC
        """

        rows = await conn.fetch(query, task_id)
        requests = [dict(row) for row in rows]

        logger.debug(
            f"Retrieved {len(requests)} LLM requests for task {task_id}",
            extra={"task_id": task_id, "count": len(requests)}
        )

        return requests

    @staticmethod
    async def get_requests_by_period(
        conn: asyncpg.Connection,
        start_date: datetime,
        end_date: datetime,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get LLM requests within a specific time period with optional filters.

        Args:
            conn: AsyncPG database connection
            start_date: Start of period
            end_date: End of period
            provider: Filter by provider ('openai' or 'anthropic')
            model: Filter by specific model
            status: Filter by status ('success', 'error', 'timeout')
            limit: Maximum number of requests to return (default: 1000)

        Returns:
            List of request dictionaries ordered by created_at DESC

        Example:
            >>> yesterday = datetime.utcnow() - timedelta(days=1)
            >>> now = datetime.utcnow()
            >>> requests = await LLMMonitoringDAO.get_requests_by_period(
            ...     conn, yesterday, now, provider="openai"
            ... )
        """
        # Build dynamic query with optional filters
        conditions = ["created_at >= $1", "created_at <= $2"]
        params = [start_date, end_date]
        param_idx = 3

        if provider:
            conditions.append(f"provider = ${param_idx}")
            params.append(provider)
            param_idx += 1

        if model:
            conditions.append(f"model = ${param_idx}")
            params.append(model)
            param_idx += 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                id, task_id, provider, model, request_type,
                prompt_tokens, completion_tokens, total_tokens,
                cost, duration_ms, status, error_message,
                metadata_json, created_at
            FROM llm_requests
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx}
        """

        params.append(limit)

        rows = await conn.fetch(query, *params)
        requests = [dict(row) for row in rows]

        logger.debug(
            f"Retrieved {len(requests)} LLM requests for period "
            f"{start_date.date()} to {end_date.date()}"
        )

        return requests

    @staticmethod
    async def get_daily_summary(
        conn: asyncpg.Connection,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated summary for a specific day.

        Uses the llm_daily_totals view for efficient querying.

        Args:
            conn: AsyncPG database connection
            date: Date to get summary for (default: today)

        Returns:
            Dictionary with daily summary:
                - usage_date: Date of the summary
                - total_requests: Total requests
                - successful_requests: Successful requests
                - failed_requests: Failed requests
                - total_tokens: Total tokens used
                - total_cost: Total cost in USD
                - avg_duration_ms: Average duration

        Example:
            >>> summary = await LLMMonitoringDAO.get_daily_summary(conn)
            >>> print(f"Today's cost: ${summary['total_cost']:.2f}")
        """
        if not date:
            date = datetime.utcnow()

        query = """
            SELECT
                usage_date, total_requests, successful_requests,
                failed_requests, total_tokens, total_cost, avg_duration_ms
            FROM llm_daily_totals
            WHERE usage_date = $1
        """

        row = await conn.fetchrow(query, date.date())

        if row:
            return dict(row)
        else:
            # Return empty summary if no data for this date
            return {
                "usage_date": date.date(),
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_duration_ms": 0.0
            }

    @staticmethod
    async def get_usage_summary_by_model(
        conn: asyncpg.Connection,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get usage summary grouped by provider and model.

        Uses the llm_usage_summary view for efficient querying.

        Args:
            conn: AsyncPG database connection
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: today)
            limit: Maximum number of results (default: 50)

        Returns:
            List of summary dictionaries ordered by total_cost DESC

        Example:
            >>> summaries = await LLMMonitoringDAO.get_usage_summary_by_model(conn)
            >>> for summary in summaries:
            ...     print(f"{summary['model']}: ${summary['total_cost']:.2f}")
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        query = """
            SELECT
                provider, model, usage_date,
                request_count, successful_requests, failed_requests, timeout_requests,
                total_prompt_tokens, total_completion_tokens, total_tokens,
                total_cost, avg_cost_per_request, avg_duration_ms,
                max_cost, min_cost
            FROM llm_usage_summary
            WHERE usage_date >= $1 AND usage_date <= $2
            ORDER BY total_cost DESC
            LIMIT $3
        """

        rows = await conn.fetch(query, start_date.date(), end_date.date(), limit)
        summaries = [dict(row) for row in rows]

        logger.debug(f"Retrieved {len(summaries)} usage summaries")

        return summaries

    @staticmethod
    async def get_provider_comparison(
        conn: asyncpg.Connection
    ) -> List[Dict[str, Any]]:
        """
        Get comparison of usage across different LLM providers.

        Uses the llm_provider_comparison view.

        Args:
            conn: AsyncPG database connection

        Returns:
            List of provider comparison dictionaries

        Example:
            >>> comparison = await LLMMonitoringDAO.get_provider_comparison(conn)
            >>> for provider_stats in comparison:
            ...     print(f"{provider_stats['provider']}: "
            ...           f"{provider_stats['success_rate_pct']:.1f}% success rate")
        """
        query = """
            SELECT
                provider, total_requests, successful_requests,
                success_rate_pct, total_tokens, total_cost,
                avg_cost_per_request, avg_duration_ms
            FROM llm_provider_comparison
            ORDER BY total_cost DESC
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_recent_requests(
        conn: asyncpg.Connection,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get most recent LLM requests.

        Args:
            conn: AsyncPG database connection
            limit: Maximum number of requests to return (default: 50)
            status: Filter by status (optional)

        Returns:
            List of recent request dictionaries

        Example:
            >>> recent = await LLMMonitoringDAO.get_recent_requests(conn, limit=10)
            >>> for req in recent:
            ...     print(f"{req['created_at']}: {req['model']} - ${req['cost']:.6f}")
        """
        if status:
            query = """
                SELECT
                    id, task_id, provider, model, request_type,
                    prompt_tokens, completion_tokens, total_tokens,
                    cost, duration_ms, status, error_message,
                    metadata_json, created_at
                FROM llm_requests
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, status, limit)
        else:
            query = """
                SELECT
                    id, task_id, provider, model, request_type,
                    prompt_tokens, completion_tokens, total_tokens,
                    cost, duration_ms, status, error_message,
                    metadata_json, created_at
                FROM llm_requests
                ORDER BY created_at DESC
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_budget_status(
        conn: asyncpg.Connection,
        period: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get current budget status for a specific period.

        Args:
            conn: AsyncPG database connection
            period: Budget period ('daily', 'weekly', 'monthly')

        Returns:
            Dictionary with budget status or None if no active budget

        Example:
            >>> budget = await LLMMonitoringDAO.get_budget_status(conn, "daily")
            >>> if budget:
            ...     usage_pct = (budget['current_usage'] / budget['budget_limit']) * 100
            ...     print(f"Budget usage: {usage_pct:.1f}%")
        """
        now = datetime.utcnow()

        query = """
            SELECT
                id, period, period_start, period_end,
                budget_limit, current_usage, alert_threshold, alert_triggered,
                created_at, updated_at
            FROM llm_usage_budgets
            WHERE period = $1
                AND period_start <= $2
                AND period_end >= $2
            ORDER BY period_start DESC
            LIMIT 1
        """

        row = await conn.fetchrow(query, period, now)
        return dict(row) if row else None

    @staticmethod
    async def get_all_budgets(
        conn: asyncpg.Connection,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all budgets, optionally filtering to active ones only.

        Args:
            conn: AsyncPG database connection
            active_only: If True, only return currently active budgets

        Returns:
            List of budget dictionaries

        Example:
            >>> budgets = await LLMMonitoringDAO.get_all_budgets(conn, active_only=True)
            >>> for budget in budgets:
            ...     print(f"{budget['period']}: ${budget['current_usage']:.2f} / "
            ...           f"${budget['budget_limit']:.2f}")
        """
        if active_only:
            now = datetime.utcnow()
            query = """
                SELECT
                    id, period, period_start, period_end,
                    budget_limit, current_usage, alert_threshold, alert_triggered,
                    created_at, updated_at
                FROM llm_usage_budgets
                WHERE period_start <= $1 AND period_end >= $1
                ORDER BY period_start DESC
            """
            rows = await conn.fetch(query, now)
        else:
            query = """
                SELECT
                    id, period, period_start, period_end,
                    budget_limit, current_usage, alert_threshold, alert_triggered,
                    created_at, updated_at
                FROM llm_usage_budgets
                ORDER BY period_start DESC
            """
            rows = await conn.fetch(query)

        return [dict(row) for row in rows]

    @staticmethod
    async def count_requests_by_status(
        conn: asyncpg.Connection,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Count requests grouped by status for a given period.

        Args:
            conn: AsyncPG database connection
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            Dictionary with status counts: {'success': 100, 'error': 5, 'timeout': 2}

        Example:
            >>> counts = await LLMMonitoringDAO.count_requests_by_status(conn)
            >>> print(f"Success rate: {counts['success'] / sum(counts.values()) * 100:.1f}%")
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        query = """
            SELECT
                status,
                COUNT(*) as count
            FROM llm_requests
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY status
        """

        rows = await conn.fetch(query, start_date, end_date)

        # Convert to dict
        counts = {row['status']: row['count'] for row in rows}

        # Ensure all statuses are present
        for status in ['success', 'error', 'timeout']:
            if status not in counts:
                counts[status] = 0

        return counts

    @staticmethod
    async def get_total_cost_by_period(
        conn: asyncpg.Connection,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """
        Get total cost for a specific period.

        Args:
            conn: AsyncPG database connection
            start_date: Start of period
            end_date: End of period

        Returns:
            Total cost in USD

        Example:
            >>> today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
            >>> now = datetime.utcnow()
            >>> cost = await LLMMonitoringDAO.get_total_cost_by_period(conn, today_start, now)
            >>> print(f"Today's cost: ${cost:.2f}")
        """
        query = """
            SELECT COALESCE(SUM(cost), 0) as total_cost
            FROM llm_requests
            WHERE created_at >= $1 AND created_at <= $2
        """

        row = await conn.fetchrow(query, start_date, end_date)
        return float(row['total_cost']) if row else 0.0

    @staticmethod
    async def delete_old_requests(
        conn: asyncpg.Connection,
        older_than_days: int = 90
    ) -> int:
        """
        Delete LLM requests older than specified number of days.

        Useful for cleanup and maintaining database performance.

        Args:
            conn: AsyncPG database connection
            older_than_days: Delete requests older than this many days (default: 90)

        Returns:
            Number of requests deleted

        Example:
            >>> deleted = await LLMMonitoringDAO.delete_old_requests(conn, older_than_days=180)
            >>> print(f"Deleted {deleted} old LLM requests")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        query = "DELETE FROM llm_requests WHERE created_at < $1"
        result = await conn.execute(query, cutoff_date)

        # Extract count from result string "DELETE N"
        count = int(result.split()[-1]) if result and ' ' in result else 0

        logger.info(
            f"Deleted {count} LLM requests older than {older_than_days} days",
            extra={"count": count, "cutoff_date": cutoff_date}
        )

        return count
