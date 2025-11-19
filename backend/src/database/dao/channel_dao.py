"""
Discord Channel Data Access Object.

Provides async database operations for discord_channels table using asyncpg.
Handles Discord channel caching and retrieval for multi-server support.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class ChannelDAO:
    """
    Data Access Object for discord_channels table.

    Manages Discord channel metadata caching including channel names, types,
    positions, and hierarchical relationships (categories, threads).
    """

    @staticmethod
    async def cache_channel(
        conn: asyncpg.Connection,
        channel_data: Dict[str, Any],
    ) -> int:
        """
        Insert or update a channel in the discord_channels table.

        Uses ON CONFLICT DO UPDATE (upsert) to handle both new channels
        and updates to existing channels. Updates the updated_at timestamp
        on every call.

        Args:
            conn: AsyncPG database connection
            channel_data: Dictionary containing channel information with keys:
                - server_id (str): Discord guild/server ID
                - channel_id (str): Discord channel ID (unique)
                - name (str): Channel name
                - type (str): Channel type ('text', 'voice', 'category', 'thread', 'forum')
                - position (int, optional): Channel position in list
                - parent_id (str, optional): Parent category/channel ID (None for top-level)

        Returns:
            int: ID of the cached channel record

        Raises:
            asyncpg.ForeignKeyViolationError: If server_id doesn't exist in discord_servers
            asyncpg.NotNullViolationError: If required fields are missing
            asyncpg.PostgresError: On other database errors

        Example:
            >>> channel_data = {
            ...     'server_id': '1111111111',
            ...     'channel_id': '2222222222',
            ...     'name': 'general',
            ...     'type': 'text',
            ...     'position': 0,
            ...     'parent_id': None
            ... }
            >>> channel_id = await ChannelDAO.cache_channel(conn, channel_data)
        """
        query = """
            INSERT INTO discord_channels (
                server_id, channel_id, name, type, position, parent_id,
                cached_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (channel_id)
            DO UPDATE SET
                server_id = EXCLUDED.server_id,
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                position = EXCLUDED.position,
                parent_id = EXCLUDED.parent_id,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(
            query,
            channel_data['server_id'],
            channel_data['channel_id'],
            channel_data['name'],
            channel_data['type'],
            channel_data.get('position'),
            channel_data.get('parent_id'),
            now,
            now,
        )

        return row['id']

    @staticmethod
    async def get_channels_by_server(
        conn: asyncpg.Connection,
        server_id: str,
        channel_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all channels for a specific Discord server.

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild/server ID
            channel_type: Optional filter by channel type
                         ('text', 'voice', 'category', 'thread', 'forum')

        Returns:
            List of channel dictionaries ordered by position ASC, name ASC.
            Each dictionary contains: id, server_id, channel_id, name, type,
            position, parent_id, cached_at, updated_at

        Example:
            >>> # Get all channels for a server
            >>> channels = await ChannelDAO.get_channels_by_server(
            ...     conn, server_id='1111111111'
            ... )
            >>> for channel in channels:
            ...     print(f"{channel['name']} ({channel['type']})")
            >>>
            >>> # Get only text channels
            >>> text_channels = await ChannelDAO.get_channels_by_server(
            ...     conn, server_id='1111111111', channel_type='text'
            ... )
        """
        if channel_type:
            query = """
                SELECT
                    id, server_id, channel_id, name, type, position,
                    parent_id, cached_at, updated_at
                FROM discord_channels
                WHERE server_id = $1 AND type = $2
                ORDER BY position ASC NULLS LAST, name ASC
            """
            rows = await conn.fetch(query, server_id, channel_type)
        else:
            query = """
                SELECT
                    id, server_id, channel_id, name, type, position,
                    parent_id, cached_at, updated_at
                FROM discord_channels
                WHERE server_id = $1
                ORDER BY position ASC NULLS LAST, name ASC
            """
            rows = await conn.fetch(query, server_id)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_channel_by_id(
        conn: asyncpg.Connection,
        channel_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached channel information by channel ID.

        Args:
            conn: AsyncPG database connection
            channel_id: Discord channel ID

        Returns:
            Dictionary with channel data or None if not found.
            Dictionary contains: id, server_id, channel_id, name, type,
            position, parent_id, cached_at, updated_at

        Example:
            >>> channel = await ChannelDAO.get_channel_by_id(conn, '2222222222')
            >>> if channel:
            ...     print(f"Channel: {channel['name']} in server {channel['server_id']}")
            ... else:
            ...     print("Channel not cached")
        """
        query = """
            SELECT
                id, server_id, channel_id, name, type, position,
                parent_id, cached_at, updated_at
            FROM discord_channels
            WHERE channel_id = $1
        """

        row = await conn.fetchrow(query, channel_id)
        return dict(row) if row else None

    @staticmethod
    async def bulk_update_channels(
        conn: asyncpg.Connection,
        server_id: str,
        channels: List[Dict[str, Any]],
    ) -> int:
        """
        Batch update/insert channels for a server.

        This method atomically:
        1. Deletes channels that exist in DB but not in the provided list
           (channels removed from Discord)
        2. Inserts or updates all channels in the provided list

        Uses a transaction to ensure atomicity - either all changes succeed
        or none are applied.

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild/server ID
            channels: List of channel dictionaries, each containing:
                - channel_id (str): Discord channel ID
                - name (str): Channel name
                - type (str): Channel type
                - position (int, optional): Channel position
                - parent_id (str, optional): Parent category/channel ID

        Returns:
            int: Number of channels updated/inserted (does not include deletions)

        Raises:
            asyncpg.PostgresError: On database errors (transaction will be rolled back)

        Example:
            >>> channels = [
            ...     {
            ...         'channel_id': '2222222222',
            ...         'name': 'general',
            ...         'type': 'text',
            ...         'position': 0,
            ...         'parent_id': None
            ...     },
            ...     {
            ...         'channel_id': '3333333333',
            ...         'name': 'announcements',
            ...         'type': 'text',
            ...         'position': 1,
            ...         'parent_id': None
            ...     }
            ... ]
            >>> count = await ChannelDAO.bulk_update_channels(
            ...     conn, server_id='1111111111', channels=channels
            ... )
            >>> print(f"Updated {count} channels")
        """
        # Extract channel IDs from the provided list
        channel_ids = [ch['channel_id'] for ch in channels]

        # Delete channels that are no longer present
        if channel_ids:
            delete_query = """
                DELETE FROM discord_channels
                WHERE server_id = $1
                  AND channel_id != ALL($2::varchar[])
            """
            await conn.execute(delete_query, server_id, channel_ids)
        else:
            # If no channels provided, delete all channels for this server
            delete_query = """
                DELETE FROM discord_channels
                WHERE server_id = $1
            """
            await conn.execute(delete_query, server_id)

        # Insert or update each channel
        upsert_query = """
            INSERT INTO discord_channels (
                server_id, channel_id, name, type, position, parent_id,
                cached_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (channel_id)
            DO UPDATE SET
                server_id = EXCLUDED.server_id,
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                position = EXCLUDED.position,
                parent_id = EXCLUDED.parent_id,
                updated_at = EXCLUDED.updated_at
        """

        now = datetime.utcnow()
        count = 0

        for channel in channels:
            await conn.execute(
                upsert_query,
                server_id,
                channel['channel_id'],
                channel['name'],
                channel['type'],
                channel.get('position'),
                channel.get('parent_id'),
                now,
                now,
            )
            count += 1

        return count
