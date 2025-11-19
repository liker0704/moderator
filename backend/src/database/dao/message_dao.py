"""
Message Data Access Object.

Provides async database operations for messages table using asyncpg.
Handles message creation, retrieval, and context queries for Discord/Telegram messages.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class MessageDAO:
    """
    Data Access Object for messages table.

    All methods are async and use asyncpg connections for high-performance
    database operations.
    """

    @staticmethod
    async def create_message(
        conn: asyncpg.Connection,
        platform: str,
        ext_message_id: str,
        channel_id: str,
        author_id: str,
        content: Optional[str] = None,
        author_name: Optional[str] = None,
        server_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        has_image: bool = False,
        context_ref: Optional[int] = None,
        platform_created_at: Optional[datetime] = None,
    ) -> int:
        """
        Create a new message record.

        Args:
            conn: AsyncPG database connection
            platform: Platform name ('discord' | 'telegram')
            ext_message_id: External platform message ID
            channel_id: Channel ID where message was posted
            author_id: Author's external ID
            content: Message text content (optional)
            author_name: Author's display name (optional)
            server_id: Server/guild ID (Discord only, optional)
            thread_id: Thread ID if message is in a thread (optional)
            has_image: Whether message contains images
            context_ref: Reference to parent message ID for context
            platform_created_at: Original timestamp from platform (optional)

        Returns:
            int: ID of the created message

        Raises:
            asyncpg.UniqueViolationError: If message with same platform+ext_message_id exists
            asyncpg.PostgresError: On other database errors

        Example:
            >>> message_id = await MessageDAO.create_message(
            ...     conn=conn,
            ...     platform='discord',
            ...     ext_message_id='1234567890',
            ...     channel_id='9876543210',
            ...     author_id='1111111111',
            ...     author_name='JohnDoe',
            ...     content='Hello, world!',
            ...     has_image=False
            ... )
        """
        query = """
            INSERT INTO messages (
                platform, ext_message_id, channel_id, author_id, content,
                author_name, server_id, thread_id, has_image, context_ref,
                platform_created_at, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """

        row = await conn.fetchrow(
            query,
            platform,
            ext_message_id,
            channel_id,
            author_id,
            content,
            author_name,
            server_id,
            thread_id,
            has_image,
            context_ref,
            platform_created_at,
            datetime.utcnow(),
        )

        return row['id']

    @staticmethod
    async def get_message_by_id(
        conn: asyncpg.Connection,
        message_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a message by its internal ID.

        Args:
            conn: AsyncPG database connection
            message_id: Internal message ID

        Returns:
            Dictionary with message data or None if not found

        Example:
            >>> message = await MessageDAO.get_message_by_id(conn, 123)
            >>> if message:
            ...     print(f"Content: {message['content']}")
        """
        query = """
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at
            FROM messages
            WHERE id = $1
        """

        row = await conn.fetchrow(query, message_id)
        return dict(row) if row else None

    @staticmethod
    async def get_message_by_external_id(
        conn: asyncpg.Connection,
        platform: str,
        ext_message_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a message by platform and external message ID.

        Args:
            conn: AsyncPG database connection
            platform: Platform name ('discord' | 'telegram')
            ext_message_id: External platform message ID

        Returns:
            Dictionary with message data or None if not found

        Example:
            >>> message = await MessageDAO.get_message_by_external_id(
            ...     conn, 'discord', '1234567890'
            ... )
        """
        query = """
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at
            FROM messages
            WHERE platform = $1 AND ext_message_id = $2
        """

        row = await conn.fetchrow(query, platform, ext_message_id)
        return dict(row) if row else None

    @staticmethod
    async def get_messages_by_channel(
        conn: asyncpg.Connection,
        platform: str,
        channel_id: str,
        server_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from a specific channel with pagination.

        Args:
            conn: AsyncPG database connection
            platform: Platform name ('discord' | 'telegram')
            channel_id: Channel ID
            server_id: Server/guild ID (optional, for Discord)
            thread_id: Thread ID (optional)
            limit: Maximum number of messages to return (default: 50)
            offset: Number of messages to skip (default: 0)

        Returns:
            List of message dictionaries ordered by created_at DESC

        Example:
            >>> messages = await MessageDAO.get_messages_by_channel(
            ...     conn, 'discord', '9876543210', limit=10
            ... )
            >>> for msg in messages:
            ...     print(f"{msg['author_name']}: {msg['content']}")
        """
        # Build query based on filters
        conditions = ["platform = $1", "channel_id = $2"]
        params = [platform, channel_id]
        param_count = 2

        if server_id is not None:
            param_count += 1
            conditions.append(f"server_id = ${param_count}")
            params.append(server_id)

        if thread_id is not None:
            param_count += 1
            conditions.append(f"thread_id = ${param_count}")
            params.append(thread_id)

        # Add limit and offset
        param_count += 1
        limit_placeholder = f"${param_count}"
        params.append(limit)

        param_count += 1
        offset_placeholder = f"${param_count}"
        params.append(offset)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_context_messages(
        conn: asyncpg.Connection,
        channel_id: str,
        thread_id: Optional[str],
        before_timestamp: datetime,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context messages before a specific timestamp.

        Used to get conversation context for AI processing.

        Args:
            conn: AsyncPG database connection
            channel_id: Channel ID
            thread_id: Thread ID (can be None for non-threaded channels)
            before_timestamp: Get messages before this timestamp
            limit: Maximum number of context messages (default: 10)

        Returns:
            List of message dictionaries ordered by created_at ASC (oldest first)

        Example:
            >>> context = await MessageDAO.get_context_messages(
            ...     conn,
            ...     channel_id='9876543210',
            ...     thread_id=None,
            ...     before_timestamp=datetime.utcnow(),
            ...     limit=5
            ... )
        """
        query = """
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at
            FROM messages
            WHERE channel_id = $1
              AND (thread_id = $2 OR (thread_id IS NULL AND $2 IS NULL))
              AND created_at < $3
            ORDER BY created_at DESC
            LIMIT $4
        """

        rows = await conn.fetch(query, channel_id, thread_id, before_timestamp, limit)
        # Reverse to get chronological order (oldest first)
        return [dict(row) for row in reversed(rows)]

    @staticmethod
    async def get_messages_by_author(
        conn: asyncpg.Connection,
        platform: str,
        author_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from a specific author.

        Args:
            conn: AsyncPG database connection
            platform: Platform name ('discord' | 'telegram')
            author_id: Author's external ID
            limit: Maximum number of messages to return (default: 50)

        Returns:
            List of message dictionaries ordered by created_at DESC

        Example:
            >>> messages = await MessageDAO.get_messages_by_author(
            ...     conn, 'discord', '1111111111', limit=20
            ... )
        """
        query = """
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at
            FROM messages
            WHERE platform = $1 AND author_id = $2
            ORDER BY created_at DESC
            LIMIT $3
        """

        rows = await conn.fetch(query, platform, author_id, limit)
        return [dict(row) for row in rows]

    @staticmethod
    async def count_messages_in_channel(
        conn: asyncpg.Connection,
        channel_id: str,
        thread_id: Optional[str] = None,
    ) -> int:
        """
        Count total messages in a channel/thread.

        Args:
            conn: AsyncPG database connection
            channel_id: Channel ID
            thread_id: Thread ID (optional)

        Returns:
            Total message count

        Example:
            >>> count = await MessageDAO.count_messages_in_channel(conn, '9876543210')
            >>> print(f"Total messages: {count}")
        """
        query = """
            SELECT COUNT(*) as count
            FROM messages
            WHERE channel_id = $1
              AND (thread_id = $2 OR (thread_id IS NULL AND $2 IS NULL))
        """

        row = await conn.fetchrow(query, channel_id, thread_id)
        return row['count']
