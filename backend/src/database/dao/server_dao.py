"""
Server Data Access Object.

Provides async database operations for discord_servers table using asyncpg.
Handles caching of Discord server information for performance and offline access.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncpg


class ServerDAO:
    """
    Data Access Object for discord_servers table.

    Manages Discord server metadata caching to reduce API calls and provide
    offline access to server information.
    """

    @staticmethod
    async def cache_server(
        conn: asyncpg.Connection,
        server_data: Dict[str, Any],
    ) -> int:
        """
        Insert or update server in discord_servers table.

        Uses ON CONFLICT DO UPDATE for upsert functionality. Automatically
        updates the updated_at timestamp on both insert and update operations.

        Args:
            conn: AsyncPG database connection
            server_data: Dictionary containing server information with keys:
                - server_id (str): Discord guild ID (required)
                - name (str): Server name (required)
                - icon_url (str): Server icon URL (optional)
                - member_count (int): Number of members (optional)
                - owner_id (str): Discord user ID of server owner (optional)

        Returns:
            int: Database ID of the cached server record

        Raises:
            KeyError: If required fields (server_id, name) are missing
            asyncpg.PostgresError: On database errors

        Example:
            >>> server_data = {
            ...     'server_id': '123456789',
            ...     'name': 'My Discord Server',
            ...     'icon_url': 'https://cdn.discordapp.com/icons/...',
            ...     'member_count': 150,
            ...     'owner_id': '987654321'
            ... }
            >>> server_id = await ServerDAO.cache_server(conn, server_data)
            >>> print(f"Cached server with ID: {server_id}")
        """
        # Validate required fields
        if 'server_id' not in server_data or 'name' not in server_data:
            raise KeyError("server_data must contain 'server_id' and 'name'")

        query = """
            INSERT INTO discord_servers (
                server_id, name, icon_url, member_count, owner_id,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (server_id) DO UPDATE SET
                name = EXCLUDED.name,
                icon_url = EXCLUDED.icon_url,
                member_count = EXCLUDED.member_count,
                owner_id = EXCLUDED.owner_id,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(
            query,
            server_data['server_id'],
            server_data['name'],
            server_data.get('icon_url'),
            server_data.get('member_count'),
            server_data.get('owner_id'),
            now,
            now,
        )

        return row['id']

    @staticmethod
    async def get_server_by_id(
        conn: asyncpg.Connection,
        server_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached server information by Discord server ID.

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild ID

        Returns:
            Dictionary containing server data with all fields, or None if not found.
            Fields include: id, server_id, name, icon_url, member_count,
            owner_id, created_at, updated_at

        Example:
            >>> server = await ServerDAO.get_server_by_id(conn, '123456789')
            >>> if server:
            ...     print(f"Server: {server['name']}")
            ...     print(f"Members: {server['member_count']}")
            ... else:
            ...     print("Server not found in cache")
        """
        query = """
            SELECT
                id, server_id, name, icon_url, member_count,
                owner_id, created_at, updated_at
            FROM discord_servers
            WHERE server_id = $1
        """

        row = await conn.fetchrow(query, server_id)
        return dict(row) if row else None

    @staticmethod
    async def get_all_servers(
        conn: asyncpg.Connection,
    ) -> List[Dict[str, Any]]:
        """
        Get all cached Discord servers.

        Returns servers ordered alphabetically by name for consistent
        display in user interfaces.

        Args:
            conn: AsyncPG database connection

        Returns:
            List of dictionaries containing server data, ordered by name ASC.
            Each dictionary includes: id, server_id, name, icon_url,
            member_count, owner_id, created_at, updated_at

        Example:
            >>> servers = await ServerDAO.get_all_servers(conn)
            >>> for server in servers:
            ...     print(f"{server['name']}: {server['member_count']} members")
        """
        query = """
            SELECT
                id, server_id, name, icon_url, member_count,
                owner_id, created_at, updated_at
            FROM discord_servers
            ORDER BY name ASC
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    async def update_server_info(
        conn: asyncpg.Connection,
        server_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update specific fields of a cached server.

        Only updates provided fields (name, icon_url, member_count).
        Automatically updates the updated_at timestamp.

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild ID
            updates: Dictionary with fields to update. Valid keys:
                - name (str): New server name
                - icon_url (str): New icon URL
                - member_count (int): New member count

        Returns:
            True if server was found and updated, False if server not found

        Example:
            >>> updated = await ServerDAO.update_server_info(
            ...     conn,
            ...     server_id='123456789',
            ...     updates={'member_count': 200, 'name': 'Updated Server Name'}
            ... )
            >>> if updated:
            ...     print("Server updated successfully")
            ... else:
            ...     print("Server not found")
        """
        # Build dynamic UPDATE query based on provided fields
        valid_fields = {'name', 'icon_url', 'member_count'}
        update_fields = {k: v for k, v in updates.items() if k in valid_fields}

        if not update_fields:
            # No valid fields to update
            return False

        # Build SET clause dynamically
        set_clauses = [f"{field} = ${i+2}" for i, field in enumerate(update_fields.keys())]
        set_clauses.append(f"updated_at = ${len(update_fields) + 2}")

        query = f"""
            UPDATE discord_servers
            SET {', '.join(set_clauses)}
            WHERE server_id = $1
        """

        # Build parameter list: server_id, field values, updated_at
        params = [server_id] + list(update_fields.values()) + [datetime.utcnow()]

        result = await conn.execute(query, *params)
        return result.split()[-1] != '0'

    @staticmethod
    async def is_server_cache_stale(
        conn: asyncpg.Connection,
        server_id: str,
        max_age_hours: int = 24,
    ) -> bool:
        """
        Check if server cache is older than the specified age.

        Useful for determining when to refresh server data from Discord API.
        Returns True if the cache doesn't exist or is stale, False if fresh.

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild ID
            max_age_hours: Maximum cache age in hours (default: 24)

        Returns:
            True if cache is stale (older than max_age_hours) or not found.
            False if cache is fresh (within max_age_hours).

        Example:
            >>> if await ServerDAO.is_server_cache_stale(conn, '123456789', max_age_hours=6):
            ...     # Refresh server data from Discord API
            ...     server_data = await discord_api.get_server('123456789')
            ...     await ServerDAO.cache_server(conn, server_data)
            ... else:
            ...     # Use cached data
            ...     server = await ServerDAO.get_server_by_id(conn, '123456789')
        """
        query = """
            SELECT updated_at
            FROM discord_servers
            WHERE server_id = $1
        """

        row = await conn.fetchrow(query, server_id)

        # If server not found in cache, it's stale
        if not row:
            return True

        # Calculate age of cache
        updated_at = row['updated_at']
        age = datetime.utcnow() - updated_at
        max_age = timedelta(hours=max_age_hours)

        # Return True if stale (age exceeds max_age)
        return age > max_age
