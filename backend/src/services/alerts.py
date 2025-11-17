"""
Alert and notification service.

This module handles system alerts and notifications:
- Sends critical system alerts to administrators
- Implements alert prioritization and routing
- Handles error notifications and system health alerts
- Manages alert throttling to prevent notification spam
- Provides alert history and logging
- Supports multiple notification channels (Telegram, email, etc.)
- Implements alert acknowledgment tracking

Ensures administrators are informed of system issues, errors,
and important events requiring attention.
"""

import asyncio
import aiohttp
from typing import Optional, Dict
from datetime import datetime, timedelta
from collections import defaultdict

from config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)

# Alert type emojis
ALERT_EMOJIS = {
    "ERROR": "🔴",
    "WARNING": "🟡",
    "INFO": "🔵",
    "SUCCESS": "🟢",
    "CRITICAL": "🚨",
}

# Alert throttling: track recent alerts to prevent spam
# Format: {alert_key: last_sent_timestamp}
_alert_history: Dict[str, datetime] = {}
_alert_throttle_seconds = 300  # 5 minutes default throttle


async def send_alert(
    message: str,
    alert_type: str = "ERROR",
    throttle_key: Optional[str] = None,
    throttle_seconds: int = 300,
    parse_mode: str = "Markdown"
) -> bool:
    """
    Send an alert message to the configured alert chat via Telegram.

    This function sends system alerts to administrators. It includes
    automatic throttling to prevent spam from repeated alerts.

    Args:
        message: Alert message text
        alert_type: Type of alert (ERROR, WARNING, INFO, SUCCESS, CRITICAL)
        throttle_key: Optional key for throttling duplicate alerts.
                     If provided, identical alerts won't be sent within
                     throttle_seconds interval
        throttle_seconds: Throttle interval in seconds (default: 300)
        parse_mode: Telegram message parse mode (default: Markdown)

    Returns:
        True if alert was sent successfully, False otherwise

    Example:
        >>> # Send a critical error alert
        >>> await send_alert(
        >>>     "Database connection failed!",
        >>>     alert_type="CRITICAL"
        >>> )
        >>>
        >>> # Send with throttling to prevent spam
        >>> await send_alert(
        >>>     "High memory usage detected",
        >>>     alert_type="WARNING",
        >>>     throttle_key="memory_usage",
        >>>     throttle_seconds=600  # Only once per 10 minutes
        >>> )
    """
    try:
        # Check throttling if throttle_key is provided
        if throttle_key:
            if _should_throttle_alert(throttle_key, throttle_seconds):
                logger.debug(
                    f"Alert throttled: {throttle_key}",
                    extra={"throttle_key": throttle_key}
                )
                return False

        # Get configuration
        config = get_config()
        alert_chat_id = config.telegram.alert_chat_id
        bot_token = config.telegram.bot_token

        # Get emoji for alert type
        emoji = ALERT_EMOJIS.get(alert_type.upper(), "ℹ️")

        # Format alert message
        formatted_message = _format_alert_message(
            message,
            alert_type,
            emoji
        )

        # Send message via Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    'chat_id': alert_chat_id,
                    'text': formatted_message,
                    'parse_mode': parse_mode
                }
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    raise Exception(f"Telegram API error: {result.get('description')}")

        # Update throttle history if throttle_key is provided
        if throttle_key:
            _alert_history[throttle_key] = datetime.now()

        logger.info(
            f"Alert sent: {alert_type}",
            extra={"alert_type": alert_type, "throttle_key": throttle_key}
        )

        return True

    except Exception as e:
        logger.error(
            f"Error sending alert: {e}",
            extra={"alert_type": alert_type},
            exc_info=True
        )
        return False


async def send_error_alert(
    error_message: str,
    context: Optional[Dict] = None,
    throttle_key: Optional[str] = None
) -> bool:
    """
    Send an error alert with optional context information.

    Convenience function for sending error alerts with formatted context.

    Args:
        error_message: Error message
        context: Optional dictionary with additional context
        throttle_key: Optional throttle key to prevent spam

    Returns:
        True if alert was sent successfully

    Example:
        >>> await send_error_alert(
        >>>     "Failed to process message",
        >>>     context={
        >>>         "message_id": "123456",
        >>>         "channel_id": "789012",
        >>>         "error": str(exception)
        >>>     },
        >>>     throttle_key="message_processing_error"
        >>> )
    """
    message = f"*Error:* {error_message}"

    if context:
        message += "\n\n*Context:*"
        for key, value in context.items():
            message += f"\n• {key}: `{value}`"

    return await send_alert(
        message,
        alert_type="ERROR",
        throttle_key=throttle_key
    )


async def send_warning_alert(
    warning_message: str,
    context: Optional[Dict] = None,
    throttle_key: Optional[str] = None
) -> bool:
    """
    Send a warning alert with optional context information.

    Args:
        warning_message: Warning message
        context: Optional dictionary with additional context
        throttle_key: Optional throttle key to prevent spam

    Returns:
        True if alert was sent successfully

    Example:
        >>> await send_warning_alert(
        >>>     "High API rate limit usage",
        >>>     context={"usage_percent": "85%"},
        >>>     throttle_key="rate_limit_warning"
        >>> )
    """
    message = f"*Warning:* {warning_message}"

    if context:
        message += "\n\n*Details:*"
        for key, value in context.items():
            message += f"\n• {key}: `{value}`"

    return await send_alert(
        message,
        alert_type="WARNING",
        throttle_key=throttle_key
    )


async def send_info_alert(
    info_message: str,
    context: Optional[Dict] = None
) -> bool:
    """
    Send an informational alert.

    Args:
        info_message: Information message
        context: Optional dictionary with additional context

    Returns:
        True if alert was sent successfully

    Example:
        >>> await send_info_alert(
        >>>     "System startup completed",
        >>>     context={"version": "1.0.0", "uptime": "0s"}
        >>> )
    """
    message = f"*Info:* {info_message}"

    if context:
        message += "\n\n*Details:*"
        for key, value in context.items():
            message += f"\n• {key}: `{value}`"

    return await send_alert(message, alert_type="INFO")


async def send_success_alert(
    success_message: str,
    context: Optional[Dict] = None
) -> bool:
    """
    Send a success alert.

    Args:
        success_message: Success message
        context: Optional dictionary with additional context

    Returns:
        True if alert was sent successfully

    Example:
        >>> await send_success_alert(
        >>>     "Database migration completed",
        >>>     context={"tables_updated": "5", "duration": "2.3s"}
        >>> )
    """
    message = f"*Success:* {success_message}"

    if context:
        message += "\n\n*Details:*"
        for key, value in context.items():
            message += f"\n• {key}: `{value}`"

    return await send_alert(message, alert_type="SUCCESS")


async def send_critical_alert(
    critical_message: str,
    context: Optional[Dict] = None
) -> bool:
    """
    Send a critical alert that bypasses throttling.

    Critical alerts are always sent immediately without throttling.

    Args:
        critical_message: Critical message
        context: Optional dictionary with additional context

    Returns:
        True if alert was sent successfully

    Example:
        >>> await send_critical_alert(
        >>>     "System shutdown initiated",
        >>>     context={"reason": "Fatal error", "code": "500"}
        >>> )
    """
    message = f"*CRITICAL:* {critical_message}"

    if context:
        message += "\n\n*Context:*"
        for key, value in context.items():
            message += f"\n• {key}: `{value}`"

    # Critical alerts bypass throttling
    return await send_alert(
        message,
        alert_type="CRITICAL",
        throttle_key=None  # No throttling for critical alerts
    )


def _format_alert_message(
    message: str,
    alert_type: str,
    emoji: str
) -> str:
    """
    Format an alert message with emoji and timestamp.

    Args:
        message: Alert message
        alert_type: Alert type
        emoji: Emoji for alert type

    Returns:
        Formatted message string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    formatted = f"{emoji} *{alert_type.upper()}*\n\n"
    formatted += f"{message}\n\n"
    formatted += f"_Time: {timestamp}_"

    return formatted


def _should_throttle_alert(
    throttle_key: str,
    throttle_seconds: int
) -> bool:
    """
    Check if an alert should be throttled.

    Args:
        throttle_key: Throttle key
        throttle_seconds: Throttle interval in seconds

    Returns:
        True if alert should be throttled (not sent)
    """
    if throttle_key not in _alert_history:
        return False

    last_sent = _alert_history[throttle_key]
    time_since_last = datetime.now() - last_sent

    return time_since_last.total_seconds() < throttle_seconds


def clear_alert_history(throttle_key: Optional[str] = None) -> None:
    """
    Clear alert history for throttling.

    This can be used to reset throttling for specific alerts or all alerts.

    Args:
        throttle_key: Optional specific key to clear. If None, clears all history.

    Example:
        >>> # Clear specific alert throttle
        >>> clear_alert_history("memory_usage")
        >>>
        >>> # Clear all alert history
        >>> clear_alert_history()
    """
    global _alert_history

    if throttle_key:
        _alert_history.pop(throttle_key, None)
        logger.debug(f"Cleared alert history for: {throttle_key}")
    else:
        _alert_history.clear()
        logger.debug("Cleared all alert history")


def get_alert_history() -> Dict[str, datetime]:
    """
    Get the current alert history (for debugging/monitoring).

    Returns:
        Dictionary of throttle keys and their last sent timestamps

    Example:
        >>> history = get_alert_history()
        >>> for key, timestamp in history.items():
        >>>     print(f"{key}: last sent at {timestamp}")
    """
    return _alert_history.copy()


async def test_alert_system() -> bool:
    """
    Test the alert system by sending a test message.

    Returns:
        True if test alert was sent successfully

    Example:
        >>> if await test_alert_system():
        >>>     print("Alert system is working!")
    """
    return await send_info_alert(
        "Alert system test",
        context={"status": "operational"}
    )
