"""Alert system for sending notifications to admin chat."""

import asyncio
import aiohttp
from typing import Optional, Dict
from datetime import datetime, timedelta

from config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)

# Throttle cache: {throttle_key: last_sent_time}
_alert_throttle_cache: Dict[str, datetime] = {}

# Alert throttling: track recent alerts to prevent spam
# Format: {alert_key: last_sent_timestamp}
_alert_history: Dict[str, datetime] = {}


async def send_alert(
    telegram_bot,
    message: str,
    alert_type: str = "ERROR",
    throttle_key: Optional[str] = None,
    throttle_seconds: int = 300
) -> bool:
    """
    Send alert to admin chat with throttling.

    Args:
        telegram_bot: TelegramBot instance
        message: Alert message text
        alert_type: Type of alert (ERROR, WARNING, INFO, CRITICAL)
        throttle_key: Unique key for throttling (prevents spam)
        throttle_seconds: Minimum seconds between alerts with same key

    Returns:
        True if alert was sent, False if throttled
    """
    # Check throttling
    if throttle_key:
        last_sent = _alert_throttle_cache.get(throttle_key)
        if last_sent:
            time_since_last = (datetime.now() - last_sent).total_seconds()
            if time_since_last < throttle_seconds:
                logger.debug(f"Alert throttled: {throttle_key} (sent {time_since_last:.0f}s ago)")
                return False

    # Format alert with type emoji
    type_emoji = {
        'ERROR': '❌',
        'WARNING': '⚠️',
        'INFO': 'ℹ️',
        'CRITICAL': '🚨'
    }.get(alert_type.upper(), '⚡')

    alert_text = f"""{type_emoji} {alert_type.upper()} ALERT

{message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    try:
        # Get moderator user ID from config
        config = get_config()
        moderator_id = config.telegram.moderator_user_id

        # Send alert
        result = await telegram_bot.send_message(
            chat_id=moderator_id,
            text=alert_text
        )

        # Update throttle cache
        if throttle_key:
            _alert_throttle_cache[throttle_key] = datetime.now()

        logger.info(f"Alert sent: {alert_type} - {message[:50]}")
        return True

    except Exception as e:
        logger.error(f"Failed to send alert: {e}", exc_info=True)
        return False


async def alert_discord_error(telegram_bot, error_message: str):
    """Send alert for Discord connection error."""
    await send_alert(
        telegram_bot,
        f"Discord connection error:\n{error_message}",
        alert_type="ERROR",
        throttle_key="discord_connection",
        throttle_seconds=600  # 10 minutes
    )


async def alert_database_error(telegram_bot, error_message: str):
    """Send alert for database error."""
    await send_alert(
        telegram_bot,
        f"Database error:\n{error_message}",
        alert_type="CRITICAL",
        throttle_key="database_error",
        throttle_seconds=300  # 5 minutes
    )


async def alert_service_down(telegram_bot, service_name: str):
    """Send alert when a service goes down."""
    await send_alert(
        telegram_bot,
        f"Service down: {service_name}",
        alert_type="CRITICAL",
        throttle_key=f"service_down_{service_name}",
        throttle_seconds=600  # 10 minutes
    )


async def clear_alert_throttle(throttle_key: Optional[str] = None):
    """Clear throttle cache for specific key or all keys."""
    if throttle_key:
        _alert_throttle_cache.pop(throttle_key, None)
    else:
        _alert_throttle_cache.clear()


# Legacy API compatibility - these maintain the old interface for existing code
async def send_error_alert(
    error_message: str,
    context: Optional[Dict] = None,
    throttle_key: Optional[str] = None
) -> bool:
    """
    Send an error alert with optional context information (legacy API).

    This function uses the old API for backward compatibility.
    """
    try:
        message = f"*Error:* {error_message}"

        if context:
            message += "\n\n*Context:*"
            for key, value in context.items():
                message += f"\n• {key}: `{value}`"

        # Get configuration
        config = get_config()
        alert_chat_id = config.telegram.alert_chat_id
        bot_token = config.telegram.bot_token

        # Check throttling
        if throttle_key and _should_throttle_alert(throttle_key, 300):
            logger.debug(f"Alert throttled: {throttle_key}")
            return False

        # Format alert message
        emoji = "🔴"
        formatted_message = _format_alert_message(message, "ERROR", emoji)

        # Send message via Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    'chat_id': alert_chat_id,
                    'text': formatted_message,
                    'parse_mode': 'Markdown'
                }
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    raise Exception(f"Telegram API error: {result.get('description')}")

        # Update throttle history
        if throttle_key:
            _alert_history[throttle_key] = datetime.now()

        logger.info(f"Alert sent: ERROR")
        return True

    except Exception as e:
        logger.error(f"Error sending alert: {e}", exc_info=True)
        return False


async def send_warning_alert(
    warning_message: str,
    context: Optional[Dict] = None,
    throttle_key: Optional[str] = None
) -> bool:
    """Send a warning alert (legacy API)."""
    try:
        message = f"*Warning:* {warning_message}"

        if context:
            message += "\n\n*Details:*"
            for key, value in context.items():
                message += f"\n• {key}: `{value}`"

        config = get_config()
        alert_chat_id = config.telegram.alert_chat_id
        bot_token = config.telegram.bot_token

        if throttle_key and _should_throttle_alert(throttle_key, 300):
            logger.debug(f"Alert throttled: {throttle_key}")
            return False

        emoji = "🟡"
        formatted_message = _format_alert_message(message, "WARNING", emoji)

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    'chat_id': alert_chat_id,
                    'text': formatted_message,
                    'parse_mode': 'Markdown'
                }
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    raise Exception(f"Telegram API error: {result.get('description')}")

        if throttle_key:
            _alert_history[throttle_key] = datetime.now()

        logger.info(f"Alert sent: WARNING")
        return True

    except Exception as e:
        logger.error(f"Error sending alert: {e}", exc_info=True)
        return False


async def send_info_alert(
    info_message: str,
    context: Optional[Dict] = None
) -> bool:
    """Send an informational alert (legacy API)."""
    try:
        message = f"*Info:* {info_message}"

        if context:
            message += "\n\n*Details:*"
            for key, value in context.items():
                message += f"\n• {key}: `{value}`"

        config = get_config()
        alert_chat_id = config.telegram.alert_chat_id
        bot_token = config.telegram.bot_token

        emoji = "🔵"
        formatted_message = _format_alert_message(message, "INFO", emoji)

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    'chat_id': alert_chat_id,
                    'text': formatted_message,
                    'parse_mode': 'Markdown'
                }
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    raise Exception(f"Telegram API error: {result.get('description')}")

        logger.info(f"Alert sent: INFO")
        return True

    except Exception as e:
        logger.error(f"Error sending alert: {e}", exc_info=True)
        return False


async def send_success_alert(
    success_message: str,
    context: Optional[Dict] = None
) -> bool:
    """Send a success alert (legacy API)."""
    try:
        message = f"*Success:* {success_message}"

        if context:
            message += "\n\n*Details:*"
            for key, value in context.items():
                message += f"\n• {key}: `{value}`"

        config = get_config()
        alert_chat_id = config.telegram.alert_chat_id
        bot_token = config.telegram.bot_token

        emoji = "🟢"
        formatted_message = _format_alert_message(message, "SUCCESS", emoji)

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    'chat_id': alert_chat_id,
                    'text': formatted_message,
                    'parse_mode': 'Markdown'
                }
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    raise Exception(f"Telegram API error: {result.get('description')}")

        logger.info(f"Alert sent: SUCCESS")
        return True

    except Exception as e:
        logger.error(f"Error sending alert: {e}", exc_info=True)
        return False


async def send_critical_alert(
    critical_message: str,
    context: Optional[Dict] = None
) -> bool:
    """Send a critical alert that bypasses throttling (legacy API)."""
    try:
        message = f"*CRITICAL:* {critical_message}"

        if context:
            message += "\n\n*Context:*"
            for key, value in context.items():
                message += f"\n• {key}: `{value}`"

        config = get_config()
        alert_chat_id = config.telegram.alert_chat_id
        bot_token = config.telegram.bot_token

        emoji = "🚨"
        formatted_message = _format_alert_message(message, "CRITICAL", emoji)

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    'chat_id': alert_chat_id,
                    'text': formatted_message,
                    'parse_mode': 'Markdown'
                }
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    raise Exception(f"Telegram API error: {result.get('description')}")

        logger.info(f"Alert sent: CRITICAL")
        return True

    except Exception as e:
        logger.error(f"Error sending alert: {e}", exc_info=True)
        return False


def _format_alert_message(
    message: str,
    alert_type: str,
    emoji: str
) -> str:
    """Format an alert message with emoji and timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    formatted = f"{emoji} *{alert_type.upper()}*\n\n"
    formatted += f"{message}\n\n"
    formatted += f"_Time: {timestamp}_"

    return formatted


def _should_throttle_alert(
    throttle_key: str,
    throttle_seconds: int
) -> bool:
    """Check if an alert should be throttled."""
    if throttle_key not in _alert_history:
        return False

    last_sent = _alert_history[throttle_key]
    time_since_last = datetime.now() - last_sent

    return time_since_last.total_seconds() < throttle_seconds


def clear_alert_history(throttle_key: Optional[str] = None) -> None:
    """Clear alert history for throttling."""
    global _alert_history

    if throttle_key:
        _alert_history.pop(throttle_key, None)
        logger.debug(f"Cleared alert history for: {throttle_key}")
    else:
        _alert_history.clear()
        logger.debug("Cleared all alert history")


def get_alert_history() -> Dict[str, datetime]:
    """Get the current alert history (for debugging/monitoring)."""
    return _alert_history.copy()


async def test_alert_system() -> bool:
    """Test the alert system by sending a test message."""
    return await send_info_alert(
        "Alert system test",
        context={"status": "operational"}
    )
