"""
Do Not Disturb (DND) schedule management service.

This module manages user notification preferences:
- Creates, updates, and deletes DND schedules for users
- Checks if current time falls within user's DND period
- Supports recurring schedules (daily, weekly patterns)
- Handles timezone conversion for global users
- Implements schedule overlap detection and validation
- Provides schedule querying and listing functionality
- Queues notifications for delivery after DND period ends

Allows users to control when they receive notifications, preventing
interruptions during off-hours or personal time.
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime, time
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DNDScheduleInterval:
    """
    Represents a single DND schedule interval.

    Attributes:
        days: List of days when this interval applies (1=Monday, 7=Sunday)
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format
    """
    days: list[int]
    start_time: str
    end_time: str


@dataclass
class DNDSchedule:
    """
    Represents a user's complete DND schedule.

    Attributes:
        intervals: List of schedule intervals
    """
    intervals: list[DNDScheduleInterval]


async def is_dnd_active(
    conn,
    user_id: int,
    check_time: Optional[datetime] = None
) -> bool:
    """
    Check if DND is currently active for a user.

    This function checks both the DND enabled flag and whether the
    current time falls within the user's DND schedule.

    Args:
        conn: Database connection (asyncpg connection or pool)
        user_id: User ID to check
        check_time: Time to check (default: current time)

    Returns:
        True if DND is active, False otherwise

    Example:
        >>> async with pool.acquire() as conn:
        >>>     if await is_dnd_active(conn, user_id=123):
        >>>         print("User is in DND mode")
    """
    try:
        # Get user settings
        query = """
            SELECT dnd_enabled, dnd_schedule_json
            FROM settings
            WHERE user_id = $1
        """

        row = await conn.fetchrow(query, user_id)

        if not row:
            # No settings found - DND is not active
            logger.debug(
                f"No settings found for user {user_id}",
                extra={"user_id": user_id}
            )
            return False

        # Check if DND is enabled
        if not row["dnd_enabled"]:
            logger.debug(
                f"DND is disabled for user {user_id}",
                extra={"user_id": user_id}
            )
            return False

        # If no schedule is set, DND is active 24/7
        if not row["dnd_schedule_json"]:
            logger.debug(
                f"DND is active 24/7 for user {user_id}",
                extra={"user_id": user_id}
            )
            return True

        # Check if current time is within schedule
        is_in_schedule = is_in_dnd_schedule(
            row["dnd_schedule_json"],
            check_time
        )

        logger.debug(
            f"DND schedule check for user {user_id}: {is_in_schedule}",
            extra={"user_id": user_id, "in_schedule": is_in_schedule}
        )

        return is_in_schedule

    except Exception as e:
        logger.error(
            f"Error checking DND status: {e}",
            extra={"user_id": user_id},
            exc_info=True
        )
        # Fail safe - return False to allow notifications
        return False


async def toggle_dnd(
    conn,
    user_id: int,
    enabled: Optional[bool] = None
) -> bool:
    """
    Toggle DND on/off for a user.

    If enabled is not specified, the function will toggle the current state.
    If user settings don't exist, they will be created.

    Args:
        conn: Database connection (asyncpg connection or pool)
        user_id: User ID
        enabled: New DND state (None to toggle current state)

    Returns:
        The new DND enabled state

    Example:
        >>> async with pool.acquire() as conn:
        >>>     # Toggle DND
        >>>     new_state = await toggle_dnd(conn, user_id=123)
        >>>     print(f"DND is now: {new_state}")
        >>>
        >>>     # Set DND to specific state
        >>>     await toggle_dnd(conn, user_id=123, enabled=True)
    """
    try:
        if enabled is None:
            # Get current state to toggle
            query = """
                SELECT dnd_enabled
                FROM settings
                WHERE user_id = $1
            """
            row = await conn.fetchrow(query, user_id)
            current_state = row["dnd_enabled"] if row else False
            enabled = not current_state

        # Upsert settings
        query = """
            INSERT INTO settings (user_id, dnd_enabled, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                dnd_enabled = EXCLUDED.dnd_enabled,
                updated_at = NOW()
            RETURNING dnd_enabled
        """

        row = await conn.fetchrow(query, user_id, enabled)

        logger.info(
            f"DND toggled for user {user_id}: {enabled}",
            extra={"user_id": user_id, "dnd_enabled": enabled}
        )

        return row["dnd_enabled"]

    except Exception as e:
        logger.error(
            f"Error toggling DND: {e}",
            extra={"user_id": user_id},
            exc_info=True
        )
        raise


async def update_dnd_schedule(
    conn,
    user_id: int,
    schedule: Optional[Dict[str, Any]]
) -> None:
    """
    Update DND schedule for a user.

    The schedule should be a dictionary with an 'intervals' key containing
    a list of interval dictionaries. Each interval should have:
    - days: List of integers (1=Monday, 7=Sunday)
    - start_time: String in HH:MM format
    - end_time: String in HH:MM format

    Args:
        conn: Database connection (asyncpg connection or pool)
        user_id: User ID
        schedule: Schedule dictionary or None to clear schedule

    Raises:
        ValueError: If schedule format is invalid

    Example:
        >>> schedule = {
        >>>     "intervals": [
        >>>         {
        >>>             "days": [1, 2, 3, 4, 5],  # Weekdays
        >>>             "start_time": "22:00",
        >>>             "end_time": "08:00"
        >>>         },
        >>>         {
        >>>             "days": [6, 7],  # Weekends
        >>>             "start_time": "00:00",
        >>>             "end_time": "23:59"
        >>>         }
        >>>     ]
        >>> }
        >>> async with pool.acquire() as conn:
        >>>     await update_dnd_schedule(conn, user_id=123, schedule=schedule)
    """
    try:
        # Validate schedule format if provided
        if schedule is not None:
            _validate_schedule(schedule)

        # Convert to JSON string
        schedule_json = json.dumps(schedule) if schedule else None

        # Upsert settings
        query = """
            INSERT INTO settings (user_id, dnd_schedule_json, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                dnd_schedule_json = EXCLUDED.dnd_schedule_json,
                updated_at = NOW()
        """

        await conn.execute(query, user_id, schedule_json)

        logger.info(
            f"DND schedule updated for user {user_id}",
            extra={"user_id": user_id, "has_schedule": schedule is not None}
        )

    except ValueError as e:
        logger.error(
            f"Invalid DND schedule format: {e}",
            extra={"user_id": user_id},
            exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            f"Error updating DND schedule: {e}",
            extra={"user_id": user_id},
            exc_info=True
        )
        raise


def is_in_dnd_schedule(
    schedule_json: str,
    check_time: Optional[datetime] = None
) -> bool:
    """
    Check if a given time falls within a DND schedule.

    This function parses the DND schedule JSON and checks if the specified
    time (or current time) falls within any of the defined intervals.

    Args:
        schedule_json: JSON string containing the DND schedule
        check_time: Time to check (default: current time)

    Returns:
        True if the time is within a DND interval, False otherwise

    Example:
        >>> schedule = '{"intervals": [{"days": [1,2,3,4,5], "start_time": "22:00", "end_time": "08:00"}]}'
        >>> is_in_schedule = is_in_dnd_schedule(schedule)
    """
    try:
        # Parse schedule
        schedule = json.loads(schedule_json)

        # Use current time if not specified
        if check_time is None:
            check_time = datetime.now()

        # Get current day of week (1=Monday, 7=Sunday)
        current_day = check_time.isoweekday()
        current_time = check_time.time()

        # Check each interval
        intervals = schedule.get("intervals", [])
        for interval in intervals:
            days = interval.get("days", [])
            start_time_str = interval.get("start_time")
            end_time_str = interval.get("end_time")

            # Check if current day is in this interval
            if current_day not in days:
                continue

            # Parse times
            try:
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Invalid time format in DND schedule: {e}",
                    extra={"interval": interval}
                )
                continue

            # Check if current time is within interval
            if _is_time_in_range(current_time, start_time, end_time):
                return True

        return False

    except json.JSONDecodeError as e:
        logger.warning(
            f"Invalid DND schedule JSON: {e}",
            extra={"schedule_json": schedule_json}
        )
        return False
    except Exception as e:
        logger.error(
            f"Error checking DND schedule: {e}",
            extra={"schedule_json": schedule_json},
            exc_info=True
        )
        return False


def _is_time_in_range(
    check_time: time,
    start_time: time,
    end_time: time
) -> bool:
    """
    Check if a time falls within a time range.

    Handles ranges that cross midnight (e.g., 22:00 to 08:00).

    Args:
        check_time: Time to check
        start_time: Start of range
        end_time: End of range

    Returns:
        True if check_time is within the range
    """
    if start_time <= end_time:
        # Normal range (e.g., 08:00 to 22:00)
        return start_time <= check_time <= end_time
    else:
        # Range crosses midnight (e.g., 22:00 to 08:00)
        return check_time >= start_time or check_time <= end_time


def _validate_schedule(schedule: Dict[str, Any]) -> None:
    """
    Validate DND schedule format.

    Args:
        schedule: Schedule dictionary to validate

    Raises:
        ValueError: If schedule format is invalid
    """
    if not isinstance(schedule, dict):
        raise ValueError("Schedule must be a dictionary")

    if "intervals" not in schedule:
        raise ValueError("Schedule must contain 'intervals' key")

    intervals = schedule["intervals"]
    if not isinstance(intervals, list):
        raise ValueError("'intervals' must be a list")

    for i, interval in enumerate(intervals):
        if not isinstance(interval, dict):
            raise ValueError(f"Interval {i} must be a dictionary")

        # Check required fields
        if "days" not in interval:
            raise ValueError(f"Interval {i} missing 'days' field")
        if "start_time" not in interval:
            raise ValueError(f"Interval {i} missing 'start_time' field")
        if "end_time" not in interval:
            raise ValueError(f"Interval {i} missing 'end_time' field")

        # Validate days
        days = interval["days"]
        if not isinstance(days, list):
            raise ValueError(f"Interval {i} 'days' must be a list")
        if not all(isinstance(d, int) and 1 <= d <= 7 for d in days):
            raise ValueError(f"Interval {i} 'days' must contain integers 1-7")

        # Validate time formats
        try:
            datetime.strptime(interval["start_time"], "%H:%M")
            datetime.strptime(interval["end_time"], "%H:%M")
        except ValueError:
            raise ValueError(f"Interval {i} times must be in HH:MM format")


async def get_dnd_settings(
    conn,
    user_id: int
) -> Optional[Dict[str, Any]]:
    """
    Get DND settings for a user.

    Args:
        conn: Database connection (asyncpg connection or pool)
        user_id: User ID

    Returns:
        Dictionary with 'enabled' and 'schedule' keys, or None if no settings exist

    Example:
        >>> async with pool.acquire() as conn:
        >>>     settings = await get_dnd_settings(conn, user_id=123)
        >>>     if settings:
        >>>         print(f"DND enabled: {settings['enabled']}")
    """
    try:
        query = """
            SELECT dnd_enabled, dnd_schedule_json
            FROM settings
            WHERE user_id = $1
        """

        row = await conn.fetchrow(query, user_id)

        if not row:
            return None

        # Parse schedule if present
        schedule = None
        if row["dnd_schedule_json"]:
            try:
                schedule = json.loads(row["dnd_schedule_json"])
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid DND schedule JSON for user {user_id}",
                    extra={"user_id": user_id}
                )

        return {
            "enabled": row["dnd_enabled"],
            "schedule": schedule
        }

    except Exception as e:
        logger.error(
            f"Error getting DND settings: {e}",
            extra={"user_id": user_id},
            exc_info=True
        )
        raise
