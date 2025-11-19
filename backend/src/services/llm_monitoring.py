"""
LLM Monitoring Service.

Tracks LLM API usage, calculates costs, manages budgets, and provides usage analytics.

Features:
- Automatic cost calculation based on token usage
- Budget tracking and alerts
- Usage statistics and analytics
- Support for OpenAI and Anthropic pricing models
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import asyncpg

logger = logging.getLogger(__name__)

# =============================================================================
# LLM Pricing Constants (USD per 1K tokens)
# =============================================================================

LLM_PRICING = {
    # OpenAI GPT-4 Models
    "gpt-4": {
        "input": Decimal("0.03"),   # $0.03 per 1K input tokens
        "output": Decimal("0.06"),  # $0.06 per 1K output tokens
    },
    "gpt-4-turbo": {
        "input": Decimal("0.01"),   # $0.01 per 1K input tokens
        "output": Decimal("0.03"),  # $0.03 per 1K output tokens
    },
    "gpt-4-turbo-preview": {
        "input": Decimal("0.01"),
        "output": Decimal("0.03"),
    },
    "gpt-4-0125-preview": {
        "input": Decimal("0.01"),
        "output": Decimal("0.03"),
    },
    "gpt-4-1106-preview": {
        "input": Decimal("0.01"),
        "output": Decimal("0.03"),
    },

    # OpenAI GPT-3.5 Models
    "gpt-3.5-turbo": {
        "input": Decimal("0.0005"),   # $0.0005 per 1K input tokens
        "output": Decimal("0.0015"),  # $0.0015 per 1K output tokens
    },
    "gpt-3.5-turbo-16k": {
        "input": Decimal("0.001"),
        "output": Decimal("0.002"),
    },

    # Anthropic Claude 3 Models
    "claude-3-opus-20240229": {
        "input": Decimal("0.015"),   # $0.015 per 1K input tokens
        "output": Decimal("0.075"),  # $0.075 per 1K output tokens
    },
    "claude-3-sonnet-20240229": {
        "input": Decimal("0.003"),   # $0.003 per 1K input tokens
        "output": Decimal("0.015"),  # $0.015 per 1K output tokens
    },
    "claude-3-haiku-20240307": {
        "input": Decimal("0.00025"),  # $0.00025 per 1K input tokens
        "output": Decimal("0.00125"), # $0.00125 per 1K output tokens
    },

    # Generic fallback (based on GPT-3.5 pricing)
    "default": {
        "input": Decimal("0.001"),
        "output": Decimal("0.002"),
    }
}


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> Decimal:
    """
    Calculate cost in USD for an LLM request.

    Args:
        model: Model identifier (e.g., "gpt-4-turbo", "claude-3-sonnet-20240229")
        prompt_tokens: Number of input/prompt tokens
        completion_tokens: Number of output/completion tokens

    Returns:
        Decimal: Cost in USD (with 6 decimal precision)

    Example:
        >>> cost = calculate_cost("gpt-4-turbo", 1000, 500)
        >>> print(f"Cost: ${cost:.6f}")
        Cost: $0.025000
    """
    # Get pricing for the model (fallback to default if not found)
    pricing = LLM_PRICING.get(model, LLM_PRICING["default"])

    # Calculate cost per token type (pricing is per 1K tokens)
    input_cost = (Decimal(prompt_tokens) / 1000) * pricing["input"]
    output_cost = (Decimal(completion_tokens) / 1000) * pricing["output"]

    total_cost = input_cost + output_cost

    logger.debug(
        f"Cost calculation for {model}: "
        f"{prompt_tokens} input + {completion_tokens} output = ${total_cost:.6f}"
    )

    return total_cost


async def track_llm_request(
    conn: asyncpg.Connection,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: Optional[int] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    task_id: Optional[int] = None,
    request_type: str = "generation",
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Track an LLM API request in the database.

    Args:
        conn: AsyncPG database connection
        provider: LLM provider ('openai' or 'anthropic')
        model: Model identifier
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        duration_ms: Request duration in milliseconds (optional)
        status: Request status ('success', 'error', 'timeout')
        error_message: Error details if status != 'success'
        task_id: Associated task ID (optional)
        request_type: Type of request ('generation', 'soften', 'other')
        metadata: Additional metadata as dict (will be converted to JSON)

    Returns:
        int: ID of the created llm_requests record

    Raises:
        asyncpg.PostgresError: On database errors

    Example:
        >>> request_id = await track_llm_request(
        ...     conn=conn,
        ...     provider="openai",
        ...     model="gpt-4-turbo",
        ...     prompt_tokens=1000,
        ...     completion_tokens=500,
        ...     duration_ms=2500,
        ...     task_id=123
        ... )
    """
    # Calculate cost
    total_tokens = prompt_tokens + completion_tokens
    cost = calculate_cost(model, prompt_tokens, completion_tokens)

    # Convert metadata to JSON string if provided
    import json
    metadata_json = json.dumps(metadata) if metadata else None

    query = """
        INSERT INTO llm_requests (
            task_id, provider, model, request_type,
            prompt_tokens, completion_tokens, total_tokens,
            cost, duration_ms, status, error_message, metadata_json
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING id
    """

    try:
        row = await conn.fetchrow(
            query,
            task_id,
            provider,
            model,
            request_type,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            float(cost),  # Convert Decimal to float for PostgreSQL DECIMAL type
            duration_ms,
            status,
            error_message,
            metadata_json
        )

        request_id = row['id']

        logger.info(
            f"Tracked LLM request {request_id}: {provider}/{model} "
            f"({total_tokens} tokens, ${cost:.6f}, status={status})"
        )

        return request_id

    except Exception as e:
        logger.error(f"Failed to track LLM request: {e}", exc_info=True)
        raise


async def check_budget_alerts(
    conn: asyncpg.Connection,
    period: str = "daily"
) -> List[Dict[str, Any]]:
    """
    Check if any budget alerts should be triggered.

    Scans active budgets for the specified period and checks if current usage
    has exceeded the alert threshold.

    Args:
        conn: AsyncPG database connection
        period: Budget period to check ('daily', 'weekly', 'monthly')

    Returns:
        List of budget dicts that have exceeded their alert threshold

    Example:
        >>> alerts = await check_budget_alerts(conn, period="daily")
        >>> for alert in alerts:
        ...     print(f"Budget alert: {alert['current_usage']}/{alert['budget_limit']}")
    """
    now = datetime.utcnow()

    # Query for active budgets in current period that haven't triggered yet
    query = """
        SELECT
            id, period, period_start, period_end,
            budget_limit, current_usage, alert_threshold, alert_triggered
        FROM llm_usage_budgets
        WHERE period = $1
            AND period_start <= $2
            AND period_end >= $2
            AND alert_triggered = FALSE
    """

    rows = await conn.fetch(query, period, now)
    budgets = [dict(row) for row in rows]

    alerts = []

    for budget in budgets:
        budget_limit = budget['budget_limit']
        current_usage = budget['current_usage']
        alert_threshold = budget['alert_threshold']

        # Calculate threshold amount
        threshold_amount = float(budget_limit) * float(alert_threshold)

        # Check if current usage exceeds threshold
        if float(current_usage) >= threshold_amount:
            alerts.append(budget)

            # Mark alert as triggered
            update_query = """
                UPDATE llm_usage_budgets
                SET alert_triggered = TRUE, updated_at = $1
                WHERE id = $2
            """
            await conn.execute(update_query, now, budget['id'])

            logger.warning(
                f"Budget alert triggered: {period} budget at "
                f"${current_usage:.2f} / ${budget_limit:.2f} "
                f"({alert_threshold * 100:.0f}% threshold)"
            )

    return alerts


async def update_budget_usage(
    conn: asyncpg.Connection,
    period: str,
    amount: Decimal
) -> bool:
    """
    Update current budget usage for the active period.

    Args:
        conn: AsyncPG database connection
        period: Budget period ('daily', 'weekly', 'monthly')
        amount: Amount to add to current usage (in USD)

    Returns:
        bool: True if budget was updated, False if no active budget found

    Example:
        >>> await update_budget_usage(conn, "daily", Decimal("0.025"))
    """
    now = datetime.utcnow()

    # Find active budget for this period
    query = """
        UPDATE llm_usage_budgets
        SET current_usage = current_usage + $1,
            updated_at = $2
        WHERE period = $3
            AND period_start <= $4
            AND period_end >= $4
    """

    result = await conn.execute(query, float(amount), now, period, now)

    # Check if any rows were updated
    rows_updated = int(result.split()[-1]) if result and ' ' in result else 0

    if rows_updated > 0:
        logger.debug(f"Updated {period} budget usage: +${amount:.6f}")
        return True
    else:
        logger.warning(f"No active {period} budget found to update")
        return False


async def get_usage_stats(
    conn: asyncpg.Connection,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get aggregated usage statistics for LLM requests.

    Args:
        conn: AsyncPG database connection
        start_date: Start date for filtering (default: 30 days ago)
        end_date: End date for filtering (default: now)
        provider: Filter by provider ('openai' or 'anthropic')
        model: Filter by specific model

    Returns:
        Dict with aggregated statistics:
            - total_requests: Total number of requests
            - successful_requests: Number of successful requests
            - failed_requests: Number of failed requests
            - total_tokens: Total tokens used
            - total_cost: Total cost in USD
            - avg_cost_per_request: Average cost per request
            - avg_duration_ms: Average request duration
            - by_provider: Breakdown by provider
            - by_model: Breakdown by model

    Example:
        >>> stats = await get_usage_stats(conn, provider="openai")
        >>> print(f"Total cost: ${stats['total_cost']:.2f}")
        >>> print(f"Requests: {stats['total_requests']}")
    """
    # Set default date range (last 30 days)
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Build base query with optional filters
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

    where_clause = " AND ".join(conditions)

    # Overall statistics
    overall_query = f"""
        SELECT
            COUNT(*) as total_requests,
            COUNT(*) FILTER (WHERE status = 'success') as successful_requests,
            COUNT(*) FILTER (WHERE status = 'error') as failed_requests,
            COUNT(*) FILTER (WHERE status = 'timeout') as timeout_requests,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(cost), 0) as total_cost,
            COALESCE(AVG(cost), 0) as avg_cost_per_request,
            COALESCE(AVG(duration_ms), 0) as avg_duration_ms
        FROM llm_requests
        WHERE {where_clause}
    """

    overall_row = await conn.fetchrow(overall_query, *params)
    overall_stats = dict(overall_row) if overall_row else {}

    # By provider breakdown
    provider_query = f"""
        SELECT
            provider,
            COUNT(*) as requests,
            COALESCE(SUM(cost), 0) as cost,
            COALESCE(SUM(total_tokens), 0) as tokens
        FROM llm_requests
        WHERE {where_clause}
        GROUP BY provider
        ORDER BY cost DESC
    """

    provider_rows = await conn.fetch(provider_query, *params)
    by_provider = [dict(row) for row in provider_rows]

    # By model breakdown
    model_query = f"""
        SELECT
            model,
            provider,
            COUNT(*) as requests,
            COALESCE(SUM(cost), 0) as cost,
            COALESCE(SUM(total_tokens), 0) as tokens
        FROM llm_requests
        WHERE {where_clause}
        GROUP BY model, provider
        ORDER BY cost DESC
    """

    model_rows = await conn.fetch(model_query, *params)
    by_model = [dict(row) for row in model_rows]

    # Combine all statistics
    stats = {
        **overall_stats,
        "by_provider": by_provider,
        "by_model": by_model,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }

    logger.debug(
        f"Usage stats: {stats['total_requests']} requests, "
        f"${stats['total_cost']:.2f} total cost"
    )

    return stats


async def create_budget(
    conn: asyncpg.Connection,
    period: str,
    budget_limit: Decimal,
    alert_threshold: Decimal = Decimal("0.80"),
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None
) -> int:
    """
    Create a new budget for LLM usage tracking.

    Args:
        conn: AsyncPG database connection
        period: Budget period ('daily', 'weekly', 'monthly')
        budget_limit: Maximum budget in USD
        alert_threshold: Alert when usage exceeds this % (0.0 - 1.0, default 0.80)
        period_start: Start of budget period (default: now)
        period_end: End of budget period (default: calculated based on period)

    Returns:
        int: ID of the created budget

    Example:
        >>> budget_id = await create_budget(
        ...     conn,
        ...     period="daily",
        ...     budget_limit=Decimal("10.00"),
        ...     alert_threshold=Decimal("0.80")
        ... )
    """
    # Set default period dates
    if not period_start:
        period_start = datetime.utcnow()

    if not period_end:
        if period == "daily":
            period_end = period_start + timedelta(days=1)
        elif period == "weekly":
            period_end = period_start + timedelta(weeks=1)
        elif period == "monthly":
            period_end = period_start + timedelta(days=30)
        else:
            raise ValueError(f"Invalid period: {period}")

    query = """
        INSERT INTO llm_usage_budgets (
            period, period_start, period_end,
            budget_limit, current_usage, alert_threshold
        )
        VALUES ($1, $2, $3, $4, 0.0, $5)
        RETURNING id
    """

    row = await conn.fetchrow(
        query,
        period,
        period_start,
        period_end,
        float(budget_limit),
        float(alert_threshold)
    )

    budget_id = row['id']

    logger.info(
        f"Created {period} budget {budget_id}: ${budget_limit:.2f} "
        f"({period_start.date()} to {period_end.date()})"
    )

    return budget_id


# Export public API
__all__ = [
    "LLM_PRICING",
    "calculate_cost",
    "track_llm_request",
    "check_budget_alerts",
    "update_budget_usage",
    "get_usage_stats",
    "create_budget",
]
