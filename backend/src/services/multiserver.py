"""
Multi-Server Management Service.

This module provides high-level operations for managing multi-server Discord
configurations, including server discovery, channel management, and bulk allowlist
operations across multiple servers.

Key Features:
- Server enumeration with allowlist statistics
- Channel discovery and filtering by type
- Bulk operations for adding/removing channels from allowlist
- Allowlist summary with server metadata
- Validation of channel existence before operations
"""

from typing import List, Dict, Optional, Any
import asyncpg


class MultiServerService:
    """
    Service for managing multi-server operations.

    Provides high-level operations for Discord multi-server support including
    server discovery, channel management, and bulk allowlist operations.
    All methods are static and async, designed to work with asyncpg connections.
    """

    @staticmethod
    async def get_available_servers(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Get all available Discord servers with allowlist statistics.

        Retrieves all cached servers from the database and enhances each with
        the count of allowed channels for the specified user. This provides
        a complete overview of available servers and their configuration status.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to get allowlist statistics for

        Returns:
            List of server dictionaries, each containing:
                - id (int): Database ID
                - server_id (str): Discord guild ID
                - name (str): Server name
                - icon_url (str): Server icon URL
                - member_count (int): Number of members
                - owner_id (str): Discord user ID of server owner
                - created_at (datetime): When cached
                - updated_at (datetime): Last cache update
                - allowed_channels (int): Count of allowed channels for this user

        Raises:
            asyncpg.PostgresError: On database errors

        Example:
            >>> async with pool.acquire() as conn:
            ...     servers = await MultiServerService.get_available_servers(
            ...         conn, user_id=1
            ...     )
            ...     for server in servers:
            ...         print(f"{server['name']}: {server['allowed_channels']} allowed channels")
            ...         # Output: "My Server: 5 allowed channels"
        """
        from backend.src.database.dao.server_dao import ServerDAO
        from backend.src.database.dao.allowlist_dao import AllowlistDAO

        # Get all cached servers
        servers = await ServerDAO.get_all_servers(conn)

        # Get allowlist statistics (server_id -> count)
        allowlist_stats = await AllowlistDAO.get_allowlist_stats(conn, user_id)

        # Enhance each server with allowlist count
        for server in servers:
            server_id = server['server_id']
            server['allowed_channels'] = allowlist_stats.get(server_id, 0)

        return servers

    @staticmethod
    async def get_server_channels(
        conn: asyncpg.Connection,
        server_id: str,
        channel_type: Optional[str] = 'text',
    ) -> List[Dict[str, Any]]:
        """
        Get channels for a specific Discord server, optionally filtered by type.

        Retrieves all cached channels for a server from the database. Supports
        filtering by channel type to get only specific channel types (e.g., text
        channels, voice channels, threads).

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild/server ID
            channel_type: Optional channel type filter. Valid values:
                - 'text': Text channels only
                - 'voice': Voice channels only
                - 'category': Category channels only
                - 'thread': Thread channels only
                - 'forum': Forum channels only
                - None: All channel types
                Default: 'text'

        Returns:
            List of channel dictionaries ordered by position ASC, name ASC.
            Each dictionary contains:
                - id (int): Database ID
                - server_id (str): Discord guild ID
                - channel_id (str): Discord channel ID
                - name (str): Channel name
                - type (str): Channel type
                - position (int): Channel position in list
                - parent_id (str): Parent category/channel ID
                - cached_at (datetime): When cached
                - updated_at (datetime): Last cache update

        Raises:
            asyncpg.PostgresError: On database errors

        Example:
            >>> # Get all text channels for a server
            >>> async with pool.acquire() as conn:
            ...     channels = await MultiServerService.get_server_channels(
            ...         conn, server_id='1111111111', channel_type='text'
            ...     )
            ...     for channel in channels:
            ...         print(f"{channel['name']} ({channel['type']})")
            ...         # Output: "general (text)"
            >>>
            >>> # Get all channels regardless of type
            >>> all_channels = await MultiServerService.get_server_channels(
            ...     conn, server_id='1111111111', channel_type=None
            ... )
        """
        from backend.src.database.dao.channel_dao import ChannelDAO

        # Get channels from DAO with optional type filter
        channels = await ChannelDAO.get_channels_by_server(
            conn,
            server_id=server_id,
            channel_type=channel_type,
        )

        return channels

    @staticmethod
    async def bulk_add_to_allowlist(
        conn: asyncpg.Connection,
        user_id: int,
        server_id: str,
        channel_ids: List[str],
    ) -> int:
        """
        Add multiple channels to the allowlist for a specific server.

        Validates that all specified channel IDs exist in the channel cache for
        the given server before performing the bulk insert. This prevents adding
        invalid or non-existent channels to the allowlist.

        All channels must belong to the specified server. Uses bulk insert
        operation for efficiency, skipping channels that are already in the
        allowlist.

        Args:
            conn: AsyncPG database connection
            user_id: User ID who owns this allowlist entry
            server_id: Discord guild/server ID (all channels must be from this server)
            channel_ids: List of Discord channel IDs to add to allowlist

        Returns:
            Number of channels actually added to allowlist (excludes duplicates)

        Raises:
            ValueError: If any channel_ids don't exist in the channel cache
                       for the specified server, or if parameters are invalid
            asyncpg.PostgresError: On database errors

        Example:
            >>> async with pool.acquire() as conn:
            ...     # Add multiple channels to allowlist
            ...     channels_to_add = ['123456789', '987654321', '555555555']
            ...     count = await MultiServerService.bulk_add_to_allowlist(
            ...         conn,
            ...         user_id=1,
            ...         server_id='1111111111',
            ...         channel_ids=channels_to_add
            ...     )
            ...     print(f"Added {count} channels to allowlist")
            ...     # Output: "Added 3 channels to allowlist"

        Note:
            - Empty channel_ids list returns 0 without error
            - Channels already in allowlist are skipped (not counted in return value)
            - All-or-nothing validation: if any channel is invalid, none are added
        """
        from backend.src.database.dao.channel_dao import ChannelDAO
        from backend.src.database.dao.allowlist_dao import AllowlistDAO

        # Handle edge case: empty list
        if not channel_ids:
            return 0

        # Validate parameters
        if not server_id or not server_id.strip():
            raise ValueError("server_id cannot be empty")

        if not user_id or user_id <= 0:
            raise ValueError("user_id must be a positive integer")

        # Validate that all channel_ids exist for this server
        # Get all channels for the server
        existing_channels = await ChannelDAO.get_channels_by_server(
            conn,
            server_id=server_id,
            channel_type=None,  # Get all types
        )

        # Create set of existing channel IDs for fast lookup
        existing_channel_ids = {ch['channel_id'] for ch in existing_channels}

        # Check if all requested channel_ids exist
        invalid_channels = [ch_id for ch_id in channel_ids if ch_id not in existing_channel_ids]

        if invalid_channels:
            raise ValueError(
                f"The following channel IDs do not exist in server {server_id}: "
                f"{', '.join(invalid_channels)}"
            )

        # All channels validated, perform bulk add
        count = await AllowlistDAO.add_channels_bulk(
            conn,
            user_id=user_id,
            server_id=server_id,
            channel_ids=channel_ids,
        )

        return count

    @staticmethod
    async def bulk_remove_from_allowlist(
        conn: asyncpg.Connection,
        user_id: int,
        channel_ids: List[str],
    ) -> int:
        """
        Remove multiple channels from the allowlist.

        Performs a bulk delete operation to remove multiple channels from the
        allowlist at once. Only removes channels owned by the specified user.

        This operation is safe to call with non-existent channel IDs - they will
        simply be skipped. No validation is performed before deletion.

        Args:
            conn: AsyncPG database connection
            user_id: User ID who owns these allowlist entries
            channel_ids: List of Discord channel IDs to remove from allowlist

        Returns:
            Number of channels actually removed from allowlist

        Raises:
            ValueError: If parameters are invalid
            asyncpg.PostgresError: On database errors

        Example:
            >>> async with pool.acquire() as conn:
            ...     # Remove multiple channels from allowlist
            ...     channels_to_remove = ['123456789', '987654321']
            ...     count = await MultiServerService.bulk_remove_from_allowlist(
            ...         conn,
            ...         user_id=1,
            ...         channel_ids=channels_to_remove
            ...     )
            ...     print(f"Removed {count} channels from allowlist")
            ...     # Output: "Removed 2 channels from allowlist"

        Note:
            - Empty channel_ids list returns 0 without error
            - Non-existent channels are silently skipped
            - Only removes channels owned by the specified user_id
        """
        from backend.src.database.dao.allowlist_dao import AllowlistDAO

        # Handle edge case: empty list
        if not channel_ids:
            return 0

        # Validate user_id
        if not user_id or user_id <= 0:
            raise ValueError("user_id must be a positive integer")

        # Perform bulk remove
        count = await AllowlistDAO.remove_channels_bulk(
            conn,
            user_id=user_id,
            channel_ids=channel_ids,
        )

        return count

    @staticmethod
    async def get_allowlist_summary(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get allowlist summary with server names and channel counts.

        Retrieves statistics about which servers have allowed channels, including
        the server name and count of allowed channels. This provides a high-level
        overview of the user's multi-server allowlist configuration.

        Args:
            conn: AsyncPG database connection
            user_id: User ID to get allowlist summary for

        Returns:
            Dictionary mapping server_id to server information:
                {
                    "server_123": {
                        "name": "My Server",
                        "count": 5,
                        "icon_url": "https://...",
                        "member_count": 150
                    },
                    "server_456": {
                        "name": "Another Server",
                        "count": 3,
                        "icon_url": "https://...",
                        "member_count": 75
                    }
                }
            Returns empty dict if user has no allowed channels.

        Raises:
            asyncpg.PostgresError: On database errors

        Example:
            >>> async with pool.acquire() as conn:
            ...     summary = await MultiServerService.get_allowlist_summary(
            ...         conn, user_id=1
            ...     )
            ...     for server_id, info in summary.items():
            ...         print(f"{info['name']}: {info['count']} channels")
            ...         # Output: "My Server: 5 channels"
            ...         # Output: "Another Server: 3 channels"

        Note:
            - Only includes servers with at least one allowed channel
            - If a server is in allowlist but not cached, it will be omitted
            - Returns empty dict if user has no allowed channels
        """
        from backend.src.database.dao.server_dao import ServerDAO
        from backend.src.database.dao.allowlist_dao import AllowlistDAO

        # Get allowlist statistics (server_id -> count)
        allowlist_stats = await AllowlistDAO.get_allowlist_stats(conn, user_id)

        # If no stats, return empty dict
        if not allowlist_stats:
            return {}

        # Enhance with server information
        summary = {}

        for server_id, count in allowlist_stats.items():
            # Get server information from cache
            server = await ServerDAO.get_server_by_id(conn, server_id)

            if server:
                summary[server_id] = {
                    'name': server['name'],
                    'count': count,
                    'icon_url': server.get('icon_url'),
                    'member_count': server.get('member_count'),
                }
            else:
                # Server not cached - provide minimal info
                summary[server_id] = {
                    'name': f'Unknown Server ({server_id})',
                    'count': count,
                    'icon_url': None,
                    'member_count': None,
                }

        return summary
