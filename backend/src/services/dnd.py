"""DND (Do Not Disturb) mode management with schedule support."""

from typing import Optional, List, Dict, Any
from datetime import datetime, time as datetime_time
import json
import logging

logger = logging.getLogger(__name__)


def parse_dnd_schedule(schedule_json: str) -> List[Dict[str, Any]]:
    """
    Parse DND schedule from JSON string.

    Format: [{"start": "22:00", "end": "08:00", "days": [0,1,2,3,4,5,6]}]

    Days: 0=Monday, 1=Tuesday, ..., 6=Sunday
    """
    try:
        schedules = json.loads(schedule_json)
        if not isinstance(schedules, list):
            return []
        return schedules
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse DND schedule: {schedule_json}")
        return []


def is_in_dnd_schedule(schedule_json: str, check_time: Optional[datetime] = None) -> bool:
    """
    Check if current time falls within DND schedule.

    Args:
        schedule_json: JSON string with schedule intervals
        check_time: Time to check (defaults to now)

    Returns:
        True if time is within any DND interval
    """
    if not schedule_json:
        return False

    if check_time is None:
        check_time = datetime.now()

    schedules = parse_dnd_schedule(schedule_json)
    if not schedules:
        return False

    current_weekday = check_time.weekday()  # 0=Monday, 6=Sunday
    current_time = check_time.time()

    for schedule in schedules:
        # Check if today is in the schedule
        days = schedule.get('days', [])
        if current_weekday not in days:
            continue

        # Parse start and end times
        try:
            start_str = schedule.get('start', '00:00')
            end_str = schedule.get('end', '00:00')

            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()

            # Check if current time is in interval
            if start_time <= end_time:
                # Normal interval (e.g., 09:00-17:00)
                if start_time <= current_time <= end_time:
                    return True
            else:
                # Overnight interval (e.g., 22:00-08:00)
                if current_time >= start_time or current_time <= end_time:
                    return True

        except ValueError as e:
            logger.warning(f"Invalid time format in schedule: {schedule}, error: {e}")
            continue

    return False


async def is_dnd_active(conn, user_id: int, check_time: Optional[datetime] = None) -> bool:
    """
    Check if DND is currently active for user.

    Checks both enabled flag and schedule.
    """
    from ..database.dao.user_dao import UserDAO

    settings = await UserDAO.get_user_settings(conn, user_id)
    if not settings:
        return False

    dnd_enabled = settings.get('dnd_enabled', False)
    if not dnd_enabled:
        return False

    # If DND enabled but no schedule, it's always active
    schedule_json = settings.get('dnd_schedule_json')
    if not schedule_json:
        return True

    # Check if current time is in schedule
    return is_in_dnd_schedule(schedule_json, check_time)


async def get_dnd_settings(conn, user_id: int) -> Optional[Dict[str, Any]]:
    """Get user's DND settings."""
    from ..database.dao.user_dao import UserDAO

    settings = await UserDAO.get_user_settings(conn, user_id)
    if not settings:
        return None

    return {
        'dnd_enabled': settings.get('dnd_enabled', False),
        'dnd_schedule_json': settings.get('dnd_schedule_json')
    }


async def update_dnd_settings(
    conn,
    user_id: int,
    dnd_enabled: Optional[bool] = None,
    dnd_schedule_json: Optional[str] = None
):
    """Update user's DND settings."""
    from ..database.dao.user_dao import UserDAO

    await UserDAO.update_dnd_settings(
        conn,
        user_id=user_id,
        dnd_enabled=dnd_enabled,
        dnd_schedule_json=dnd_schedule_json
    )
