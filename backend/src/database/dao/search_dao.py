"""
Search Data Access Object.

Provides async database operations for searching messages with advanced filters.
Handles full-text search, filtering by author, channel, dates, and pagination.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
import asyncpg


class SearchDAO:
    """
    Data Access Object for message search operations.

    All methods are async and use asyncpg connections for high-performance
    database operations with complex filtering and pagination.
    """

    @staticmethod
    async def search_messages(
        conn: asyncpg.Connection,
        user_id: int,
        filters: Dict[str, Any],
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search messages with advanced filtering and pagination.

        Args:
            conn: AsyncPG database connection
            user_id: User ID (for future multi-user support, currently unused)
            filters: Dictionary of search filters:
                - text_query (str): Text content search (case-insensitive)
                - author_username (str): Filter by author name (partial match)
                - author_id (str): Filter by exact author ID
                - channel_id (str): Filter by channel ID
                - server_id (str): Filter by Discord server ID
                - date_from (date/datetime/str): Messages from this date (inclusive)
                - date_to (date/datetime/str): Messages until this date (inclusive)
                - platform (str): Filter by platform ('discord' or 'telegram')
                - has_image (bool): Filter messages with/without images
            limit: Maximum number of results to return (default: 10)
            offset: Number of results to skip (default: 0)

        Returns:
            List of message dictionaries with all message fields, ordered by created_at DESC

        Example:
            >>> filters = {
            ...     'text_query': 'hello',
            ...     'author_username': 'john',
            ...     'date_from': date(2025, 11, 1)
            ... }
            >>> messages = await SearchDAO.search_messages(conn, user_id=1, filters=filters, limit=20)
            >>> for msg in messages:
            ...     print(f"{msg['author_name']}: {msg['content']}")
        """
        # Build WHERE conditions dynamically
        conditions = []
        params = []
        param_count = 0

        # Text search (case-insensitive, supports ILIKE pattern matching)
        if filters.get('text_query'):
            param_count += 1
            conditions.append(f"content ILIKE ${param_count}")
            params.append(f"%{filters['text_query']}%")

        # Author username search (partial match, case-insensitive)
        if filters.get('author_username'):
            param_count += 1
            conditions.append(f"author_name ILIKE ${param_count}")
            params.append(f"%{filters['author_username']}%")

        # Author ID (exact match)
        if filters.get('author_id'):
            param_count += 1
            conditions.append(f"author_id = ${param_count}")
            params.append(filters['author_id'])

        # Channel ID
        if filters.get('channel_id'):
            param_count += 1
            conditions.append(f"channel_id = ${param_count}")
            params.append(filters['channel_id'])

        # Server ID
        if filters.get('server_id'):
            param_count += 1
            conditions.append(f"server_id = ${param_count}")
            params.append(filters['server_id'])

        # Platform
        if filters.get('platform'):
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(filters['platform'])

        # Has image
        if filters.get('has_image') is not None:
            param_count += 1
            conditions.append(f"has_image = ${param_count}")
            params.append(filters['has_image'])

        # Date range filters
        if filters.get('date_from'):
            param_count += 1
            date_from = filters['date_from']
            # Handle different date formats
            if isinstance(date_from, str):
                conditions.append(f"created_at >= ${param_count}::timestamp")
                params.append(date_from)
            elif isinstance(date_from, date) and not isinstance(date_from, datetime):
                conditions.append(f"created_at >= ${param_count}::date")
                params.append(date_from)
            else:
                conditions.append(f"created_at >= ${param_count}")
                params.append(date_from)

        if filters.get('date_to'):
            param_count += 1
            date_to = filters['date_to']
            # Handle different date formats (add 1 day for inclusive end)
            if isinstance(date_to, str):
                conditions.append(f"created_at < (${param_count}::timestamp + interval '1 day')")
                params.append(date_to)
            elif isinstance(date_to, date) and not isinstance(date_to, datetime):
                conditions.append(f"created_at < (${param_count}::date + interval '1 day')")
                params.append(date_to)
            else:
                conditions.append(f"created_at <= ${param_count}")
                params.append(date_to)

        # Build WHERE clause
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Add LIMIT and OFFSET
        param_count += 1
        limit_placeholder = f"${param_count}"
        params.append(limit)

        param_count += 1
        offset_placeholder = f"${param_count}"
        params.append(offset)

        # Build and execute query
        query = f"""
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at
            FROM messages
            {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    @staticmethod
    async def count_search_results(
        conn: asyncpg.Connection,
        user_id: int,
        filters: Dict[str, Any],
    ) -> int:
        """
        Count total number of messages matching search filters.

        This is used for pagination to show total results and calculate page count.

        Args:
            conn: AsyncPG database connection
            user_id: User ID (for future multi-user support, currently unused)
            filters: Dictionary of search filters (same as search_messages)

        Returns:
            Total count of matching messages

        Example:
            >>> filters = {'text_query': 'hello', 'author_username': 'john'}
            >>> total = await SearchDAO.count_search_results(conn, user_id=1, filters=filters)
            >>> print(f"Found {total} messages")
        """
        # Build WHERE conditions (same logic as search_messages)
        conditions = []
        params = []
        param_count = 0

        # Text search
        if filters.get('text_query'):
            param_count += 1
            conditions.append(f"content ILIKE ${param_count}")
            params.append(f"%{filters['text_query']}%")

        # Author username search
        if filters.get('author_username'):
            param_count += 1
            conditions.append(f"author_name ILIKE ${param_count}")
            params.append(f"%{filters['author_username']}%")

        # Author ID
        if filters.get('author_id'):
            param_count += 1
            conditions.append(f"author_id = ${param_count}")
            params.append(filters['author_id'])

        # Channel ID
        if filters.get('channel_id'):
            param_count += 1
            conditions.append(f"channel_id = ${param_count}")
            params.append(filters['channel_id'])

        # Server ID
        if filters.get('server_id'):
            param_count += 1
            conditions.append(f"server_id = ${param_count}")
            params.append(filters['server_id'])

        # Platform
        if filters.get('platform'):
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(filters['platform'])

        # Has image
        if filters.get('has_image') is not None:
            param_count += 1
            conditions.append(f"has_image = ${param_count}")
            params.append(filters['has_image'])

        # Date range filters
        if filters.get('date_from'):
            param_count += 1
            date_from = filters['date_from']
            if isinstance(date_from, str):
                conditions.append(f"created_at >= ${param_count}::timestamp")
                params.append(date_from)
            elif isinstance(date_from, date) and not isinstance(date_from, datetime):
                conditions.append(f"created_at >= ${param_count}::date")
                params.append(date_from)
            else:
                conditions.append(f"created_at >= ${param_count}")
                params.append(date_from)

        if filters.get('date_to'):
            param_count += 1
            date_to = filters['date_to']
            if isinstance(date_to, str):
                conditions.append(f"created_at < (${param_count}::timestamp + interval '1 day')")
                params.append(date_to)
            elif isinstance(date_to, date) and not isinstance(date_to, datetime):
                conditions.append(f"created_at < (${param_count}::date + interval '1 day')")
                params.append(date_to)
            else:
                conditions.append(f"created_at <= ${param_count}")
                params.append(date_to)

        # Build WHERE clause
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Build and execute count query
        query = f"""
            SELECT COUNT(*) as count
            FROM messages
            {where_clause}
        """

        row = await conn.fetchrow(query, *params)
        return row['count']

    @staticmethod
    async def search_messages_fulltext(
        conn: asyncpg.Connection,
        user_id: int,
        search_query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search messages using PostgreSQL full-text search (if tsvector column exists).

        This is more efficient than ILIKE for large datasets but requires
        migration 006_search_indexes.sql to be applied.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            search_query: Full-text search query (supports operators like & | !)
            filters: Additional filters (channel_id, server_id, date_from, date_to, etc.)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of message dictionaries ordered by relevance and date

        Example:
            >>> # Search for messages containing both "hello" and "world"
            >>> messages = await SearchDAO.search_messages_fulltext(
            ...     conn, user_id=1, search_query="hello & world"
            ... )
            >>> # Search with OR operator
            >>> messages = await SearchDAO.search_messages_fulltext(
            ...     conn, user_id=1, search_query="hello | hi"
            ... )
        """
        filters = filters or {}

        # Build WHERE conditions
        conditions = []
        params = []
        param_count = 0

        # Full-text search condition
        if search_query:
            param_count += 1
            conditions.append(f"content_tsvector @@ to_tsquery('english', ${param_count})")
            params.append(search_query)

        # Add other filters
        if filters.get('channel_id'):
            param_count += 1
            conditions.append(f"channel_id = ${param_count}")
            params.append(filters['channel_id'])

        if filters.get('server_id'):
            param_count += 1
            conditions.append(f"server_id = ${param_count}")
            params.append(filters['server_id'])

        if filters.get('platform'):
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(filters['platform'])

        if filters.get('date_from'):
            param_count += 1
            date_from = filters['date_from']
            if isinstance(date_from, str):
                conditions.append(f"created_at >= ${param_count}::timestamp")
                params.append(date_from)
            else:
                conditions.append(f"created_at >= ${param_count}")
                params.append(date_from)

        if filters.get('date_to'):
            param_count += 1
            date_to = filters['date_to']
            if isinstance(date_to, str):
                conditions.append(f"created_at <= ${param_count}::timestamp")
                params.append(date_to)
            else:
                conditions.append(f"created_at <= ${param_count}")
                params.append(date_to)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Add LIMIT and OFFSET
        param_count += 1
        limit_placeholder = f"${param_count}"
        params.append(limit)

        param_count += 1
        offset_placeholder = f"${param_count}"
        params.append(offset)

        # Build query with ranking
        query = f"""
            SELECT
                id, platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image, context_ref,
                created_at, platform_created_at,
                ts_rank(content_tsvector, to_tsquery('english', $1)) as rank
            FROM messages
            {where_clause}
            ORDER BY rank DESC, created_at DESC
            LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]
