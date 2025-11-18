"""
Task enqueue functions for Redis queue.

This module provides:
- Functions to enqueue various types of tasks
- Job scheduling and deferred execution
- Priority queue support
- Job metadata and tracking
- Error handling for enqueue operations

Tasks can be enqueued from anywhere in the application
and will be processed asynchronously by worker processes.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)


async def get_arq_redis() -> ArqRedis:
    """
    Get ARQ Redis connection for enqueueing tasks.

    Returns:
        ArqRedis connection instance

    Raises:
        RuntimeError: If Redis configuration is not available
    """
    config = get_config()

    if not config.redis:
        raise RuntimeError(
            "Redis configuration not available. "
            "Set REDIS_HOST environment variable."
        )

    redis_settings = RedisSettings(
        host=config.redis.host,
        port=config.redis.port,
        password=config.redis.password if config.redis.password else None,
        database=0,
    )

    pool = await create_pool(redis_settings)
    return pool


async def enqueue_discord_message(
    message_id: str,
    channel_id: str,
    content: str,
    author_id: str,
    author_name: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    embeds: Optional[List[Dict[str, Any]]] = None,
    priority: int = 0,
    defer_seconds: Optional[int] = None,
) -> Optional[str]:
    """
    Enqueue Discord message processing task.

    Args:
        message_id: Discord message ID
        channel_id: Discord channel ID
        content: Message content
        author_id: Author user ID
        author_name: Author username
        attachments: List of attachment objects
        embeds: List of embed objects
        priority: Task priority (higher = more urgent)
        defer_seconds: Defer execution by N seconds

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    try:
        redis = await get_arq_redis()

        job = await redis.enqueue_job(
            "process_discord_message",
            message_id,
            channel_id,
            content,
            author_id,
            author_name,
            attachments or [],
            embeds or [],
            _queue_name="moderator:queue",
            _defer_by=defer_seconds,
        )

        logger.info(
            f"Enqueued Discord message processing: {message_id}",
            extra={
                "job_id": job.job_id,
                "message_id": message_id,
                "channel_id": channel_id,
            }
        )

        return job.job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue Discord message: {e}",
            exc_info=True,
            extra={"message_id": message_id}
        )
        return None


async def enqueue_telegram_message(
    message_id: int,
    chat_id: int,
    text: str,
    user_id: int,
    username: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
    priority: int = 0,
    defer_seconds: Optional[int] = None,
) -> Optional[str]:
    """
    Enqueue Telegram message processing task.

    Args:
        message_id: Telegram message ID
        chat_id: Telegram chat ID
        text: Message text
        user_id: User ID
        username: Username
        reply_to_message_id: ID of message being replied to
        priority: Task priority
        defer_seconds: Defer execution by N seconds

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    try:
        redis = await get_arq_redis()

        job = await redis.enqueue_job(
            "process_telegram_message",
            message_id,
            chat_id,
            text,
            user_id,
            username,
            reply_to_message_id,
            _queue_name="moderator:queue",
            _defer_by=defer_seconds,
        )

        logger.info(
            f"Enqueued Telegram message processing: {message_id}",
            extra={
                "job_id": job.job_id,
                "message_id": message_id,
                "chat_id": chat_id,
            }
        )

        return job.job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue Telegram message: {e}",
            exc_info=True,
            extra={"message_id": message_id}
        )
        return None


async def enqueue_discord_post(
    channel_id: str,
    content: str,
    embeds: Optional[List[Dict[str, Any]]] = None,
    reference_message_id: Optional[str] = None,
    priority: int = 0,
    defer_seconds: Optional[int] = None,
) -> Optional[str]:
    """
    Enqueue Discord post creation task.

    Args:
        channel_id: Discord channel ID
        content: Message content
        embeds: List of embed objects
        reference_message_id: Message ID to reply to
        priority: Task priority
        defer_seconds: Defer execution by N seconds

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    try:
        redis = await get_arq_redis()

        job = await redis.enqueue_job(
            "post_to_discord",
            channel_id,
            content,
            embeds or [],
            reference_message_id,
            _queue_name="moderator:queue",
            _defer_by=defer_seconds,
        )

        logger.info(
            f"Enqueued Discord post: {channel_id}",
            extra={
                "job_id": job.job_id,
                "channel_id": channel_id,
            }
        )

        return job.job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue Discord post: {e}",
            exc_info=True,
            extra={"channel_id": channel_id}
        )
        return None


async def enqueue_telegram_post(
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
    parse_mode: Optional[str] = "HTML",
    priority: int = 0,
    defer_seconds: Optional[int] = None,
) -> Optional[str]:
    """
    Enqueue Telegram post creation task.

    Args:
        chat_id: Telegram chat ID
        text: Message text
        reply_to_message_id: Message ID to reply to
        parse_mode: Message parse mode (HTML, Markdown)
        priority: Task priority
        defer_seconds: Defer execution by N seconds

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    try:
        redis = await get_arq_redis()

        job = await redis.enqueue_job(
            "post_to_telegram",
            chat_id,
            text,
            reply_to_message_id,
            parse_mode,
            _queue_name="moderator:queue",
            _defer_by=defer_seconds,
        )

        logger.info(
            f"Enqueued Telegram post: {chat_id}",
            extra={
                "job_id": job.job_id,
                "chat_id": chat_id,
            }
        )

        return job.job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue Telegram post: {e}",
            exc_info=True,
            extra={"chat_id": chat_id}
        )
        return None


async def enqueue_llm_generation(
    message_id: str,
    platform: str,
    context: str,
    prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 500,
    priority: int = 1,
    defer_seconds: Optional[int] = None,
) -> Optional[str]:
    """
    Enqueue LLM response generation task.

    Args:
        message_id: Original message ID
        platform: Platform (discord/telegram)
        context: Conversation context
        prompt: User prompt
        model: LLM model to use
        max_tokens: Maximum tokens in response
        priority: Task priority
        defer_seconds: Defer execution by N seconds

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    try:
        redis = await get_arq_redis()

        job = await redis.enqueue_job(
            "generate_llm_response",
            message_id,
            platform,
            context,
            prompt,
            model,
            max_tokens,
            _queue_name="moderator:queue",
            _defer_by=defer_seconds,
        )

        logger.info(
            f"Enqueued LLM generation for message: {message_id}",
            extra={
                "job_id": job.job_id,
                "message_id": message_id,
                "platform": platform,
            }
        )

        return job.job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue LLM generation: {e}",
            exc_info=True,
            extra={"message_id": message_id}
        )
        return None


async def enqueue_reminder(
    user_id: str,
    platform: str,
    message: str,
    send_at: datetime,
) -> Optional[str]:
    """
    Enqueue reminder task to be sent at specific time.

    Args:
        user_id: User ID to send reminder to
        platform: Platform (discord/telegram)
        message: Reminder message
        send_at: When to send the reminder

    Returns:
        Job ID if enqueued successfully, None otherwise
    """
    try:
        redis = await get_arq_redis()

        # Calculate defer time
        now = datetime.utcnow()
        defer_seconds = int((send_at - now).total_seconds())

        if defer_seconds < 0:
            logger.warning(
                f"Reminder time is in the past, sending immediately",
                extra={"user_id": user_id, "send_at": send_at}
            )
            defer_seconds = 0

        job = await redis.enqueue_job(
            "send_reminder",
            user_id,
            platform,
            message,
            _queue_name="moderator:queue",
            _defer_by=defer_seconds,
        )

        logger.info(
            f"Enqueued reminder for user: {user_id}",
            extra={
                "job_id": job.job_id,
                "user_id": user_id,
                "platform": platform,
                "send_at": send_at.isoformat(),
            }
        )

        return job.job_id

    except Exception as e:
        logger.error(
            f"Failed to enqueue reminder: {e}",
            exc_info=True,
            extra={"user_id": user_id}
        )
        return None
