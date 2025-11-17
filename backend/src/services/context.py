"""
Context window management service.

This module implements intelligent message grouping logic:
- Groups related Discord messages into context windows
- Implements time-based windowing (5-minute default window)
- Handles conversation thread detection and grouping
- Manages context window lifecycle (creation, updates, closure)
- Provides context retrieval for message review
- Implements "request more context" functionality
- Optimizes notification batching to reduce interruptions

Context windows ensure users receive complete conversation context
rather than individual isolated messages, improving moderation efficiency.
"""

from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """
    Represents a message from a platform.

    Attributes:
        id: Internal database ID
        platform: Platform name ('discord' or 'telegram')
        ext_message_id: External message ID on the platform
        server_id: Server/guild ID (Discord only)
        channel_id: Channel/chat ID
        thread_id: Thread ID (optional)
        author_id: Author's user ID
        author_name: Author's display name
        content: Message text content
        has_image: Whether the message has image attachments
        context_ref: Reference to parent message for threading
        created_at: When the message was stored in database
        platform_created_at: When the message was created on the platform
    """
    id: int
    platform: str
    ext_message_id: str
    server_id: Optional[str]
    channel_id: str
    thread_id: Optional[str]
    author_id: str
    author_name: Optional[str]
    content: Optional[str]
    has_image: bool
    context_ref: Optional[int]
    created_at: datetime
    platform_created_at: Optional[datetime]


async def get_context(
    conn,
    message: Message,
    limit: int = 10,
    offset: int = 0,
    include_current: bool = False
) -> List[Message]:
    """
    Retrieve message history context for a given message.

    This function fetches previous messages from the same channel/thread
    to provide context for moderation. Messages are ordered by their
    platform creation time in descending order (most recent first).

    Args:
        conn: Database connection (asyncpg connection or pool)
        message: The message to get context for
        limit: Maximum number of messages to retrieve (default: 10)
        offset: Number of messages to skip (for pagination, default: 0)
        include_current: If True, include the current message in results (default: False)

    Returns:
        List of Message objects ordered by platform_created_at DESC

    Example:
        >>> async with pool.acquire() as conn:
        >>>     # Get last 10 messages before this one
        >>>     context_messages = await get_context(conn, current_message, limit=10)
        >>>     for msg in context_messages:
        >>>         print(f"{msg.author_name}: {msg.content}")
    """
    try:
        # Build the query to fetch context messages
        # We want messages from the same channel/thread, ordered by time
        query = """
            SELECT
                id,
                platform,
                ext_message_id,
                server_id,
                channel_id,
                thread_id,
                author_id,
                author_name,
                content,
                has_image,
                context_ref,
                created_at,
                platform_created_at
            FROM messages
            WHERE platform = $1
              AND channel_id = $2
              AND (thread_id = $3 OR (thread_id IS NULL AND $3 IS NULL))
              AND (server_id = $4 OR (server_id IS NULL AND $4 IS NULL))
        """

        params = [
            message.platform,
            message.channel_id,
            message.thread_id,
            message.server_id
        ]

        # Exclude current message if requested
        if not include_current:
            query += " AND id != $5"
            params.append(message.id)

        # Order by platform timestamp (or database timestamp if not available)
        query += """
            ORDER BY
                COALESCE(platform_created_at, created_at) DESC
            LIMIT $%d OFFSET $%d
        """ % (len(params) + 1, len(params) + 2)

        params.extend([limit, offset])

        # Execute query
        rows = await conn.fetch(query, *params)

        # Convert rows to Message objects
        messages = []
        for row in rows:
            msg = Message(
                id=row["id"],
                platform=row["platform"],
                ext_message_id=row["ext_message_id"],
                server_id=row["server_id"],
                channel_id=row["channel_id"],
                thread_id=row["thread_id"],
                author_id=row["author_id"],
                author_name=row["author_name"],
                content=row["content"],
                has_image=row["has_image"],
                context_ref=row["context_ref"],
                created_at=row["created_at"],
                platform_created_at=row["platform_created_at"]
            )
            messages.append(msg)

        logger.debug(
            f"Retrieved {len(messages)} context messages",
            extra={
                "platform": message.platform,
                "channel_id": message.channel_id,
                "thread_id": message.thread_id,
                "count": len(messages),
                "limit": limit,
                "offset": offset
            }
        )

        return messages

    except Exception as e:
        logger.error(
            f"Error retrieving message context: {e}",
            extra={
                "platform": message.platform,
                "channel_id": message.channel_id,
                "message_id": message.id
            },
            exc_info=True
        )
        raise


async def get_context_by_channel(
    conn,
    platform: str,
    channel_id: str,
    server_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0
) -> List[Message]:
    """
    Retrieve recent messages from a specific channel/thread.

    This is a convenience function to get context without needing
    an existing Message object. Useful for fetching channel history.

    Args:
        conn: Database connection (asyncpg connection or pool)
        platform: Platform name ('discord' or 'telegram')
        channel_id: Channel or chat ID
        server_id: Server/guild ID (for Discord)
        thread_id: Thread ID (optional)
        limit: Maximum number of messages to retrieve (default: 10)
        offset: Number of messages to skip (default: 0)

    Returns:
        List of Message objects ordered by platform_created_at DESC

    Example:
        >>> async with pool.acquire() as conn:
        >>>     recent_messages = await get_context_by_channel(
        >>>         conn,
        >>>         platform="discord",
        >>>         channel_id="123456789",
        >>>         server_id="987654321",
        >>>         limit=20
        >>>     )
    """
    try:
        query = """
            SELECT
                id,
                platform,
                ext_message_id,
                server_id,
                channel_id,
                thread_id,
                author_id,
                author_name,
                content,
                has_image,
                context_ref,
                created_at,
                platform_created_at
            FROM messages
            WHERE platform = $1
              AND channel_id = $2
              AND (thread_id = $3 OR (thread_id IS NULL AND $3 IS NULL))
              AND (server_id = $4 OR (server_id IS NULL AND $4 IS NULL))
            ORDER BY
                COALESCE(platform_created_at, created_at) DESC
            LIMIT $5 OFFSET $6
        """

        rows = await conn.fetch(
            query,
            platform,
            channel_id,
            thread_id,
            server_id,
            limit,
            offset
        )

        messages = []
        for row in rows:
            msg = Message(
                id=row["id"],
                platform=row["platform"],
                ext_message_id=row["ext_message_id"],
                server_id=row["server_id"],
                channel_id=row["channel_id"],
                thread_id=row["thread_id"],
                author_id=row["author_id"],
                author_name=row["author_name"],
                content=row["content"],
                has_image=row["has_image"],
                context_ref=row["context_ref"],
                created_at=row["created_at"],
                platform_created_at=row["platform_created_at"]
            )
            messages.append(msg)

        logger.debug(
            f"Retrieved {len(messages)} messages from channel",
            extra={
                "platform": platform,
                "channel_id": channel_id,
                "thread_id": thread_id,
                "count": len(messages)
            }
        )

        return messages

    except Exception as e:
        logger.error(
            f"Error retrieving channel messages: {e}",
            extra={
                "platform": platform,
                "channel_id": channel_id
            },
            exc_info=True
        )
        raise


async def get_message_by_id(
    conn,
    message_id: int
) -> Optional[Message]:
    """
    Retrieve a single message by its internal database ID.

    Args:
        conn: Database connection (asyncpg connection or pool)
        message_id: Internal database message ID

    Returns:
        Message object if found, None otherwise

    Example:
        >>> async with pool.acquire() as conn:
        >>>     message = await get_message_by_id(conn, 12345)
        >>>     if message:
        >>>         print(f"Author: {message.author_name}")
    """
    try:
        query = """
            SELECT
                id,
                platform,
                ext_message_id,
                server_id,
                channel_id,
                thread_id,
                author_id,
                author_name,
                content,
                has_image,
                context_ref,
                created_at,
                platform_created_at
            FROM messages
            WHERE id = $1
        """

        row = await conn.fetchrow(query, message_id)

        if not row:
            logger.debug(
                f"Message not found: {message_id}",
                extra={"message_id": message_id}
            )
            return None

        message = Message(
            id=row["id"],
            platform=row["platform"],
            ext_message_id=row["ext_message_id"],
            server_id=row["server_id"],
            channel_id=row["channel_id"],
            thread_id=row["thread_id"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            content=row["content"],
            has_image=row["has_image"],
            context_ref=row["context_ref"],
            created_at=row["created_at"],
            platform_created_at=row["platform_created_at"]
        )

        return message

    except Exception as e:
        logger.error(
            f"Error retrieving message by ID: {e}",
            extra={"message_id": message_id},
            exc_info=True
        )
        raise


async def get_message_by_external_id(
    conn,
    platform: str,
    ext_message_id: str
) -> Optional[Message]:
    """
    Retrieve a message by its external platform ID.

    Args:
        conn: Database connection (asyncpg connection or pool)
        platform: Platform name ('discord' or 'telegram')
        ext_message_id: External message ID on the platform

    Returns:
        Message object if found, None otherwise

    Example:
        >>> async with pool.acquire() as conn:
        >>>     message = await get_message_by_external_id(
        >>>         conn,
        >>>         "discord",
        >>>         "1234567890123456789"
        >>>     )
    """
    try:
        query = """
            SELECT
                id,
                platform,
                ext_message_id,
                server_id,
                channel_id,
                thread_id,
                author_id,
                author_name,
                content,
                has_image,
                context_ref,
                created_at,
                platform_created_at
            FROM messages
            WHERE platform = $1 AND ext_message_id = $2
        """

        row = await conn.fetchrow(query, platform, ext_message_id)

        if not row:
            logger.debug(
                f"Message not found: {platform}/{ext_message_id}",
                extra={"platform": platform, "ext_message_id": ext_message_id}
            )
            return None

        message = Message(
            id=row["id"],
            platform=row["platform"],
            ext_message_id=row["ext_message_id"],
            server_id=row["server_id"],
            channel_id=row["channel_id"],
            thread_id=row["thread_id"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            content=row["content"],
            has_image=row["has_image"],
            context_ref=row["context_ref"],
            created_at=row["created_at"],
            platform_created_at=row["platform_created_at"]
        )

        return message

    except Exception as e:
        logger.error(
            f"Error retrieving message by external ID: {e}",
            extra={"platform": platform, "ext_message_id": ext_message_id},
            exc_info=True
        )
        raise
