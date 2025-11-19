"""
Reminder System for sending periodic notifications about open tasks.

This module implements the reminder system that:
- Scans open tasks periodically (every 30 minutes)
- Sends reminders to moderators for unanswered tasks
- Respects DND (Do Not Disturb) mode
- Limits reminders to MAX_REMINDERS per task
- Integrates with Telegram bot for notifications
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from ..database.connection import get_asyncpg_pool
from ..database.dao.task_dao import TaskDAO
from ..database.dao.user_dao import UserDAO
from ..database.dao.message_dao import MessageDAO
from ..services.dnd import is_dnd_active
from ..config import get_config
from ..utils.logger import get_logger

# Constants
REMINDER_INTERVAL_MINUTES = 30
MAX_REMINDERS = 3
MIN_TASK_AGE_MINUTES = 30  # Don't remind for tasks younger than 30 minutes

# Logger
logger = get_logger(__name__)


class ReminderService:
    """
    Service for managing task reminders.

    Periodically scans open tasks and sends reminders via Telegram
    when appropriate conditions are met.
    """

    def __init__(self, telegram_bot):
        """
        Initialize the reminder service.

        Args:
            telegram_bot: TelegramBot instance for sending notifications
        """
        self.telegram_bot = telegram_bot
        self.config = get_config()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        logger.info("ReminderService initialized")

    async def start(self):
        """Start the reminder scheduler."""
        if self._running:
            logger.warning("Reminder service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Reminder service started")

    async def stop(self):
        """Stop the reminder scheduler gracefully."""
        if not self._running:
            return

        logger.info("Stopping reminder service...")
        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Reminder service stopped")

    async def _run_scheduler(self):
        """
        Main scheduler loop that runs periodically.

        Executes scan_and_send_reminders every REMINDER_INTERVAL_MINUTES.
        """
        logger.info(f"Reminder scheduler started (interval: {REMINDER_INTERVAL_MINUTES} minutes)")

        while self._running:
            try:
                # Run the reminder scan
                await self.scan_and_send_reminders()

                # Wait for next interval
                await asyncio.sleep(REMINDER_INTERVAL_MINUTES * 60)

            except asyncio.CancelledError:
                logger.info("Reminder scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in reminder scheduler: {e}", exc_info=True)
                # Continue running even if one iteration fails
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def scan_and_send_reminders(self):
        """
        Scan all open tasks and send reminders where appropriate.

        This is the main periodic task that:
        1. Gets all open tasks from database
        2. Checks each task with _should_send_reminder()
        3. Sends reminders via _send_reminder()
        4. Updates reminder_count in database
        """
        logger.info("Starting reminder scan...")

        try:
            pool = get_asyncpg_pool()

            async with pool.acquire() as conn:
                # Get all open tasks
                open_tasks = await TaskDAO.get_open_tasks(conn, user_id=None, limit=1000)

                if not open_tasks:
                    logger.debug("No open tasks found")
                    return

                logger.info(f"Found {len(open_tasks)} open tasks to check")

                reminders_sent = 0
                reminders_skipped = 0

                for task in open_tasks:
                    try:
                        # Check if we should send reminder for this task
                        should_send, reason = await self._should_send_reminder(conn, task)

                        if should_send:
                            # Send reminder
                            success = await self._send_reminder(conn, task)

                            if success:
                                # Increment reminder count
                                new_count = await TaskDAO.increment_reminder_count(
                                    conn,
                                    task['id']
                                )
                                logger.info(
                                    f"Sent reminder for task {task['id']} "
                                    f"(count: {new_count})"
                                )
                                reminders_sent += 1
                            else:
                                logger.warning(
                                    f"Failed to send reminder for task {task['id']}"
                                )
                        else:
                            logger.debug(
                                f"Skipping task {task['id']}: {reason}"
                            )
                            reminders_skipped += 1

                    except Exception as e:
                        logger.error(
                            f"Error processing task {task['id']}: {e}",
                            exc_info=True
                        )
                        continue

                logger.info(
                    f"Reminder scan complete: {reminders_sent} sent, "
                    f"{reminders_skipped} skipped"
                )

        except Exception as e:
            logger.error(f"Error in scan_and_send_reminders: {e}", exc_info=True)

    async def _should_send_reminder(
        self,
        conn,
        task: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Check if a reminder should be sent for a task.

        Args:
            conn: Database connection
            task: Task dictionary from database

        Returns:
            Tuple of (should_send: bool, reason: str)
            - (True, "ok") if reminder should be sent
            - (False, reason) if reminder should be skipped with explanation
        """
        task_id = task['id']
        assignee_user_id = task['assignee_user_id']
        reminder_count = task['reminder_count']
        created_at = task['created_at']
        updated_at = task['updated_at']

        # Check 1: Max reminders reached
        if reminder_count >= MAX_REMINDERS:
            return False, f"max reminders reached ({MAX_REMINDERS})"

        # Check 2: Task too new (created less than MIN_TASK_AGE_MINUTES ago)
        now = datetime.utcnow()
        task_age = now - created_at
        if task_age < timedelta(minutes=MIN_TASK_AGE_MINUTES):
            return False, f"task too new ({task_age.total_seconds() / 60:.1f} min)"

        # Check 3: Not enough time passed since last update
        time_since_update = now - updated_at
        if time_since_update < timedelta(minutes=REMINDER_INTERVAL_MINUTES):
            return False, (
                f"not enough time since last update "
                f"({time_since_update.total_seconds() / 60:.1f} min)"
            )

        # Check 4: Get user settings
        settings = await UserDAO.get_user_settings(conn, assignee_user_id)

        # Check 5: User has reminders disabled
        if settings and not settings.get('reminders_enabled', False):
            return False, "user has reminders disabled"

        # Check 6: DND mode active
        if await is_dnd_active(conn, assignee_user_id):
            return False, "DND mode active"

        # All checks passed
        return True, "ok"

    async def _send_reminder(
        self,
        conn,
        task: Dict[str, Any]
    ) -> bool:
        """
        Send a reminder notification via Telegram.

        Args:
            conn: Database connection
            task: Task dictionary from database

        Returns:
            True if reminder was sent successfully, False otherwise
        """
        try:
            # Get source message details
            message = await MessageDAO.get_message_by_id(
                conn,
                task['source_message_id']
            )

            if not message:
                logger.error(
                    f"Source message {task['source_message_id']} not found "
                    f"for task {task['id']}"
                )
                return False

            # Build reminder text
            reminder_text = self._build_reminder_text(task, message)

            # Send via Telegram
            result = await self.telegram_bot.send_message(
                chat_id=self.config.telegram.moderator_user_id,
                text=reminder_text,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )

            if result and result.get('ok'):
                logger.info(
                    f"Reminder sent for task {task['id']}, "
                    f"Telegram message: {result['result']['message_id']}"
                )
                return True
            else:
                logger.error(
                    f"Failed to send reminder for task {task['id']}: "
                    f"{result.get('description') if result else 'No response'}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Error sending reminder for task {task['id']}: {e}",
                exc_info=True
            )
            return False

    def _build_reminder_text(
        self,
        task: Dict[str, Any],
        message: Dict[str, Any]
    ) -> str:
        """
        Build formatted reminder notification text.

        Args:
            task: Task dictionary from database
            message: Source message dictionary from database

        Returns:
            Formatted reminder text for Telegram
        """
        reminder_count = task['reminder_count']
        task_id = task['id']
        created_at = task['created_at']

        # Calculate task age
        now = datetime.utcnow()
        task_age = now - created_at
        hours = int(task_age.total_seconds() / 3600)
        minutes = int((task_age.total_seconds() % 3600) / 60)

        # Format age string
        if hours > 0:
            age_str = f"{hours}h {minutes}m"
        else:
            age_str = f"{minutes}m"

        # Get message details
        platform = message.get('platform', 'unknown')
        author_name = message.get('author_name', 'Unknown')
        content = message.get('content', '(no content)')
        channel_id = message.get('channel_id', 'unknown')

        # Truncate content if too long
        max_content_length = 200
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        # Build reminder text
        reminder_emoji = "🔔"
        if reminder_count == 0:
            reminder_label = "Reminder"
        elif reminder_count == 1:
            reminder_label = "2nd Reminder"
        elif reminder_count == 2:
            reminder_label = "Final Reminder"
        else:
            reminder_label = f"Reminder #{reminder_count + 1}"

        text = f"""{reminder_emoji} *{reminder_label}*

*Task #{task_id}* has been open for *{age_str}*

*From:* {author_name} ({platform})
*Channel:* {channel_id}

*Message:*
{content}

⚠️ *Action Required:* Please respond to this message or mute the task.
"""

        return text


# Singleton instance
_reminder_service: Optional[ReminderService] = None


def get_reminder_service() -> Optional[ReminderService]:
    """
    Get the singleton reminder service instance.

    Returns:
        ReminderService instance or None if not initialized
    """
    return _reminder_service


def init_reminder_service(telegram_bot) -> ReminderService:
    """
    Initialize the global reminder service instance.

    Args:
        telegram_bot: TelegramBot instance for sending notifications

    Returns:
        ReminderService instance
    """
    global _reminder_service

    if _reminder_service is not None:
        logger.warning("Reminder service already initialized")
        return _reminder_service

    _reminder_service = ReminderService(telegram_bot)
    logger.info("Global reminder service initialized")

    return _reminder_service


async def start_reminder_scheduler(telegram_bot) -> ReminderService:
    """
    Entry point for starting the reminder scheduler.

    This function should be called from main.py during application startup.

    Args:
        telegram_bot: TelegramBot instance for sending notifications

    Returns:
        ReminderService instance

    Example:
        >>> # In main.py initialization
        >>> from services.reminders import start_reminder_scheduler
        >>> reminder_service = await start_reminder_scheduler(telegram_bot)
    """
    # Initialize service if not already done
    service = get_reminder_service()
    if service is None:
        service = init_reminder_service(telegram_bot)

    # Start the scheduler
    await service.start()

    logger.info("Reminder scheduler started successfully")
    return service


async def stop_reminder_scheduler():
    """
    Stop the reminder scheduler gracefully.

    This function should be called during application shutdown.
    """
    service = get_reminder_service()
    if service:
        await service.stop()
        logger.info("Reminder scheduler stopped")
    else:
        logger.warning("Reminder service not initialized, nothing to stop")
