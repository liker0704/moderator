"""
Redis Queue System for asynchronous task processing.

This module provides:
- Redis client management with connection pooling
- ARQ worker configuration and task execution
- Task enqueue functions for various operations
- Task handlers for processing messages and posts
- Retry logic and error handling for failed tasks
- Integration with Discord, Telegram, and LLM services

The queue system enables asynchronous processing of:
- Discord message forwarding to Telegram
- Telegram message forwarding to Discord
- Discord post creation
- Telegram post creation
- LLM response generation
- Scheduled reminders and notifications
"""

from .client import (
    init_redis_client,
    get_redis_client,
    close_redis_client,
)

from .tasks import (
    enqueue_discord_message,
    enqueue_telegram_message,
    enqueue_discord_post,
    enqueue_telegram_post,
    enqueue_llm_generation,
    enqueue_reminder,
)

from .handlers import (
    process_discord_message,
    process_telegram_message,
    post_to_discord,
    post_to_telegram,
    generate_llm_response,
    send_reminder,
)

from .worker import (
    create_worker_settings,
    create_worker,
)

__all__ = [
    # Client management
    "init_redis_client",
    "get_redis_client",
    "close_redis_client",
    # Task enqueue functions
    "enqueue_discord_message",
    "enqueue_telegram_message",
    "enqueue_discord_post",
    "enqueue_telegram_post",
    "enqueue_llm_generation",
    "enqueue_reminder",
    # Task handlers
    "process_discord_message",
    "process_telegram_message",
    "post_to_discord",
    "post_to_telegram",
    "generate_llm_response",
    "send_reminder",
    # Worker configuration
    "create_worker_settings",
    "create_worker",
]
