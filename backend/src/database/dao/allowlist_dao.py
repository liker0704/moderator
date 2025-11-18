"""
Allowlist Data Access Object.

Provides async database operations for channels_allowlist table using asyncpg.
Handles channel allowlist management for Discord and Telegram.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class AllowlistDAO:
    """
    Data Access Object for channels_allowlist table.

    Manages allowed channels for message reception with optional thread filtering.
    """

    @staticmethod
    async def add_channel(
        conn: asyncpg.Connection,
        platform: str,
        channel_id: str,
        server_id: Optional[str] = None,
        thread_filter_json: Optional[str] = None,
        enabled: bool = True,
    ) -> int:
        """
        Add a channel to the allowlist.

        Args:
            conn: AsyncPG database connection
            platform: Platform name ('discord' | 'telegram')
            channel_id: Channel ID
            server_id: Server/guild ID (required for Discord, None for Telegram)
            thread_filter_json: JSON string with thread filters (optional)
                               e.g., '{"allowed_threads": ["123", "456"]}'
            enabled: Whether the channel is enabled (default: True)

        Returns:
            int: ID of the created allowlist entry

        Raises:
            asyncpg.UniqueViolationError: If channel already exists in allowlist
            asyncpg.PostgresError: On other database errors

        Example:
            >>> # Add Discord channel
            >>> entry_id = await AllowlistDAO.add_channel(
            ...     conn=conn,
            ...     platform='discord',
            ...     channel_id='9876543210',
            ...     server_id='1111111111'
            ... )
            >>>
            >>> # Add Telegram channel
            >>> entry_id = await AllowlistDAO.add_channel(
            ...     conn=conn,
            ...     platform='telegram',
            ...     channel_id='telegram_chat_id'
            ... )
        """
        query = """
            INSERT INTO channels_allowlist (
                platform, server_id, channel_id, thread_filter_json,
                enabled, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(
            query,
            platform,
            server_id,
            channel_id,
            thread_filter_json,
            enabled,
            now,
            now,
        )

        return row['id']

    @staticmethod
    async def remove_channel(
        conn: asyncpg.Connection,
        channel_id: str,
        platform: Optional[str] = None,
    ) -> bool:
        """
        Remove a channel from the allowlist.

        Args:
            conn: AsyncPG database connection
            channel_id: Channel ID
            platform: Platform name (optional, for specificity)

        Returns:
            True if channel was removed, False if channel not found

        Example:
            >>> removed = await AllowlistDAO.remove_channel(
            ...     conn, channel_id='9876543210', platform='discord'
            ... )
        """
        if platform:
            query = "DELETE FROM channels_allowlist WHERE channel_id = $1 AND platform = $2"
            result = await conn.execute(query, channel_id, platform)
        else:
            query = "DELETE FROM channels_allowlist WHERE channel_id = $1"
            result = await conn.execute(query, channel_id)

        return result.split()[-1] != '0'

    @staticmethod
    async def is_channel_allowed(
        conn: asyncpg.Connection,
        platform: str,
        channel_id: str,
        server_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a channel (and optionally thread) is allowed.

        Args:
            conn: AsyncPG database connection
            platform: Platform name ('discord' | 'telegram')
            channel_id: Channel ID
            server_id: Server/guild ID (optional, for Discord)
            thread_id: Thread ID (optional, for thread-specific checks)

        Returns:
            True if channel is allowed, False otherwise

        Example:
            >>> allowed = await AllowlistDAO.is_channel_allowed(
            ...     conn,
            ...     platform='discord',
            ...     channel_id='9876543210',
            ...     server_id='1111111111'
            ... )
            >>> if allowed:
            ...     # Process message
            ...     pass
        """
        # Build query based on parameters
        if server_id:
            query = """
                SELECT id, thread_filter_json
                FROM channels_allowlist
                WHERE platform = $1
                  AND channel_id = $2
                  AND server_id = $3
                  AND enabled = TRUE
            """
            row = await conn.fetchrow(query, platform, channel_id, server_id)
        else:
            query = """
                SELECT id, thread_filter_json
                FROM channels_allowlist
                WHERE platform = $1
                  AND channel_id = $2
                  AND enabled = TRUE
            """
            row = await conn.fetchrow(query, platform, channel_id)

        if not row:
            return False

        # If no thread_id specified, channel is allowed
        if not thread_id:
            return True

        # Check thread filter if exists
        thread_filter = row['thread_filter_json']
        if not thread_filter:
            # No filter means all threads allowed
            return True

        # Parse thread filter and check if thread is allowed
        # This is a simple check - actual implementation may need JSON parsing
        # Example filter: '{"allowed_threads": ["123", "456"]}'
        import json
        try:
            filter_data = json.loads(thread_filter)
            allowed_threads = filter_data.get('allowed_threads', [])

            if not allowed_threads:
                # Empty list means all threads allowed
                return True

            return thread_id in allowed_threads
        except (json.JSONDecodeError, KeyError):
            # If filter is invalid, allow by default
            return True

    @staticmethod
    async def get_all_channels(
        conn: asyncpg.Connection,
        platform: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all allowed channels, optionally filtered by platform.

        Args:
            conn: AsyncPG database connection
            platform: Filter by platform (None for all platforms)
            enabled_only: Only return enabled channels (default: True)

        Returns:
            List of channel dictionaries ordered by created_at ASC

        Example:
            >>> channels = await AllowlistDAO.get_all_channels(conn, platform='discord')
            >>> for channel in channels:
            ...     print(f"{channel['platform']}: {channel['channel_id']}")
        """
        conditions = []
        params = []
        param_count = 0

        if platform:
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(platform)

        if enabled_only:
            conditions.append("enabled = TRUE")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT
                id, platform, server_id, channel_id, thread_filter_json,
                enabled, created_at, updated_at
            FROM channels_allowlist
            WHERE {where_clause}
            ORDER BY created_at ASC
        """

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_channel_by_id(
        conn: asyncpg.Connection,
        allowlist_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a channel allowlist entry by its ID.

        Args:
            conn: AsyncPG database connection
            allowlist_id: Allowlist entry ID

        Returns:
            Dictionary with channel data or None if not found

        Example:
            >>> channel = await AllowlistDAO.get_channel_by_id(conn, 1)
        """
        query = """
            SELECT
                id, platform, server_id, channel_id, thread_filter_json,
                enabled, created_at, updated_at
            FROM channels_allowlist
            WHERE id = $1
        """

        row = await conn.fetchrow(query, allowlist_id)
        return dict(row) if row else None

    @staticmethod
    async def update_channel_enabled(
        conn: asyncpg.Connection,
        channel_id: str,
        enabled: bool,
        platform: Optional[str] = None,
    ) -> bool:
        """
        Enable or disable a channel in the allowlist.

        Args:
            conn: AsyncPG database connection
            channel_id: Channel ID
            enabled: Whether to enable or disable the channel
            platform: Platform name (optional, for specificity)

        Returns:
            True if channel was updated, False if channel not found

        Example:
            >>> # Disable a channel
            >>> updated = await AllowlistDAO.update_channel_enabled(
            ...     conn, channel_id='9876543210', enabled=False, platform='discord'
            ... )
        """
        if platform:
            query = """
                UPDATE channels_allowlist
                SET enabled = $1,
                    updated_at = $2
                WHERE channel_id = $3 AND platform = $4
            """
            result = await conn.execute(
                query,
                enabled,
                datetime.utcnow(),
                channel_id,
                platform,
            )
        else:
            query = """
                UPDATE channels_allowlist
                SET enabled = $1,
                    updated_at = $2
                WHERE channel_id = $3
            """
            result = await conn.execute(query, enabled, datetime.utcnow(), channel_id)

        return result.split()[-1] != '0'

    @staticmethod
    async def update_thread_filter(
        conn: asyncpg.Connection,
        channel_id: str,
        thread_filter_json: Optional[str],
        platform: Optional[str] = None,
    ) -> bool:
        """
        Update thread filter for a channel.

        Args:
            conn: AsyncPG database connection
            channel_id: Channel ID
            thread_filter_json: JSON string with thread filters or None to remove filter
            platform: Platform name (optional, for specificity)

        Returns:
            True if channel was updated, False if channel not found

        Example:
            >>> import json
            >>> filter_json = json.dumps({"allowed_threads": ["123", "456"]})
            >>> updated = await AllowlistDAO.update_thread_filter(
            ...     conn, channel_id='9876543210',
            ...     thread_filter_json=filter_json, platform='discord'
            ... )
        """
        if platform:
            query = """
                UPDATE channels_allowlist
                SET thread_filter_json = $1,
                    updated_at = $2
                WHERE channel_id = $3 AND platform = $4
            """
            result = await conn.execute(
                query,
                thread_filter_json,
                datetime.utcnow(),
                channel_id,
                platform,
            )
        else:
            query = """
                UPDATE channels_allowlist
                SET thread_filter_json = $1,
                    updated_at = $2
                WHERE channel_id = $3
            """
            result = await conn.execute(
                query,
                thread_filter_json,
                datetime.utcnow(),
                channel_id,
            )

        return result.split()[-1] != '0'

    @staticmethod
    async def count_channels(
        conn: asyncpg.Connection,
        platform: Optional[str] = None,
        enabled_only: bool = True,
    ) -> int:
        """
        Count allowed channels, optionally filtered by platform.

        Args:
            conn: AsyncPG database connection
            platform: Filter by platform (None for all platforms)
            enabled_only: Only count enabled channels (default: True)

        Returns:
            Channel count

        Example:
            >>> count = await AllowlistDAO.count_channels(conn, platform='discord')
            >>> print(f"Discord channels: {count}")
        """
        conditions = []
        params = []
        param_count = 0

        if platform:
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(platform)

        if enabled_only:
            conditions.append("enabled = TRUE")

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT COUNT(*) as count
            FROM channels_allowlist
            WHERE {where_clause}
        """

        row = await conn.fetchrow(query, *params)
        return row['count'] if row else 0
