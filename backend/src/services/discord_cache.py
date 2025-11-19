"""
Discord Cache Service.

Service for managing Discord server and channel metadata caching.
This service:
- Fetches server and channel data from Discord API
- Caches metadata in local database for performance
- Provides fallback-safe display names
- Handles bulk cache refresh operations
- Filters channels to relevant types (text channels and threads)

The cache reduces API calls to Discord and provides offline access
to server/channel metadata for the application.
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import asyncpg

from backend.src.database.dao.server_dao import ServerDAO
from backend.src.database.dao.channel_dao import ChannelDAO
from backend.src.discord.api_client import DiscordAPIClient

logger = logging.getLogger(__name__)


class DiscordCacheService:
    """
    Service for managing Discord server and channel metadata cache.

    This service integrates with the Discord API to fetch and cache
    server and channel information, providing fast access to metadata
    and reducing API calls.
    """

    # Channel type constants from Discord API
    # https://discord.com/developers/docs/resources/channel#channel-object-channel-types
    CHANNEL_TYPE_TEXT = 0
    CHANNEL_TYPE_THREAD = 11  # Public thread
    CHANNEL_TYPE_PRIVATE_THREAD = 12  # Private thread

    # Allowed channel types for message monitoring
    ALLOWED_CHANNEL_TYPES = {CHANNEL_TYPE_TEXT, CHANNEL_TYPE_THREAD, CHANNEL_TYPE_PRIVATE_THREAD}

    @staticmethod
    async def fetch_user_servers(discord_token: str) -> List[Dict]:
        """
        Fetch all Discord servers (guilds) for the authenticated user.

        Uses the Discord API to retrieve the list of servers the bot
        has access to. This does not update the cache - use refresh_server_cache
        for that.

        Args:
            discord_token: Discord bot token for authentication

        Returns:
            List of server dictionaries from Discord API. Each dict contains:
                - id (str): Server/guild ID
                - name (str): Server name
                - icon (str, optional): Icon hash
                - owner_id (str): User ID of server owner
                - approximate_member_count (int, optional): Member count
                And other Discord guild fields...

        Raises:
            Exception: If Discord API call fails

        Example:
            >>> servers = await DiscordCacheService.fetch_user_servers(token)
            >>> for server in servers:
            ...     print(f"Server: {server['name']} (ID: {server['id']})")
        """
        try:
            logger.info("Fetching user servers from Discord API")
            servers = await DiscordAPIClient.fetch_guilds(discord_token)

            logger.info(
                f"Successfully fetched {len(servers)} servers from Discord API",
                extra={"server_count": len(servers)}
            )

            return servers

        except Exception as e:
            logger.error(
                f"Failed to fetch user servers from Discord API: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    async def fetch_server_channels(
        discord_token: str,
        server_id: str
    ) -> List[Dict]:
        """
        Fetch channels for a specific Discord server.

        Retrieves all channels from Discord API and filters to only
        text channels (type 0) and threads (type 11, 12). Other channel
        types (voice, categories, etc.) are excluded as they're not
        relevant for message monitoring.

        Args:
            discord_token: Discord bot token for authentication
            server_id: Discord guild/server ID

        Returns:
            List of filtered channel dictionaries. Each dict contains:
                - id (str): Channel ID
                - name (str): Channel name
                - type (int): Channel type (0, 11, or 12)
                - position (int, optional): Channel position
                - parent_id (str, optional): Parent category/channel ID
                And other Discord channel fields...

        Raises:
            Exception: If Discord API call fails

        Example:
            >>> channels = await DiscordCacheService.fetch_server_channels(
            ...     token, server_id="123456789"
            ... )
            >>> for channel in channels:
            ...     print(f"Channel: {channel['name']} (Type: {channel['type']})")
        """
        try:
            logger.info(
                f"Fetching channels for server {server_id}",
                extra={"server_id": server_id}
            )

            # Fetch all channels from Discord API
            all_channels = await DiscordAPIClient.fetch_channels(
                discord_token,
                server_id
            )

            # Filter to only text channels and threads
            filtered_channels = [
                channel for channel in all_channels
                if channel.get('type') in DiscordCacheService.ALLOWED_CHANNEL_TYPES
            ]

            logger.info(
                f"Fetched {len(filtered_channels)} text/thread channels "
                f"(out of {len(all_channels)} total) for server {server_id}",
                extra={
                    "server_id": server_id,
                    "filtered_count": len(filtered_channels),
                    "total_count": len(all_channels)
                }
            )

            return filtered_channels

        except Exception as e:
            logger.error(
                f"Failed to fetch channels for server {server_id}: {e}",
                extra={"server_id": server_id},
                exc_info=True
            )
            raise

    @staticmethod
    async def refresh_server_cache(
        conn: asyncpg.Connection,
        discord_token: str
    ) -> int:
        """
        Refresh the entire server and channel cache from Discord API.

        This method performs a full cache refresh:
        1. Fetches all servers from Discord API
        2. Updates server cache in database
        3. For each server, fetches and caches channels
        4. Uses bulk update for efficient channel caching

        Individual server/channel errors are logged but don't stop the
        entire refresh process. This ensures partial cache updates succeed
        even if some servers fail.

        Args:
            conn: AsyncPG database connection
            discord_token: Discord bot token for authentication

        Returns:
            int: Number of servers successfully cached

        Raises:
            Exception: Only if fetching the initial server list fails.
                      Individual server errors are caught and logged.

        Example:
            >>> async with pool.acquire() as conn:
            ...     count = await DiscordCacheService.refresh_server_cache(
            ...         conn, discord_token
            ...     )
            ...     print(f"Cached {count} servers")
        """
        try:
            logger.info("Starting full server cache refresh")

            # Fetch all servers from Discord API
            servers = await DiscordCacheService.fetch_user_servers(discord_token)

            cached_count = 0

            # Process each server
            for server in servers:
                try:
                    server_id = server.get('id')
                    server_name = server.get('name', 'Unknown')

                    logger.debug(
                        f"Caching server: {server_name} (ID: {server_id})",
                        extra={"server_id": server_id}
                    )

                    # Prepare server data for database
                    server_data = {
                        'server_id': server_id,
                        'name': server_name,
                        'icon_url': _build_icon_url(server.get('icon'), server_id),
                        'member_count': server.get('approximate_member_count'),
                        'owner_id': server.get('owner_id'),
                    }

                    # Cache server in database
                    await ServerDAO.cache_server(conn, server_data)

                    # Fetch and cache channels for this server
                    try:
                        channels = await DiscordCacheService.fetch_server_channels(
                            discord_token,
                            server_id
                        )

                        # Prepare channel data for bulk update
                        channel_data_list = []
                        for channel in channels:
                            channel_data = {
                                'channel_id': channel.get('id'),
                                'name': channel.get('name', 'unknown'),
                                'type': _map_channel_type(channel.get('type')),
                                'position': channel.get('position'),
                                'parent_id': channel.get('parent_id'),
                            }
                            channel_data_list.append(channel_data)

                        # Bulk update channels
                        if channel_data_list:
                            await ChannelDAO.bulk_update_channels(
                                conn,
                                server_id,
                                channel_data_list
                            )

                            logger.debug(
                                f"Cached {len(channel_data_list)} channels for server {server_id}",
                                extra={
                                    "server_id": server_id,
                                    "channel_count": len(channel_data_list)
                                }
                            )

                    except Exception as channel_error:
                        # Log channel fetch error but continue with other servers
                        logger.error(
                            f"Failed to cache channels for server {server_id}: {channel_error}",
                            extra={"server_id": server_id},
                            exc_info=True
                        )
                        # Still count the server as cached even if channels failed

                    cached_count += 1

                except Exception as server_error:
                    # Log individual server error but continue with others
                    logger.error(
                        f"Failed to cache server {server.get('id', 'unknown')}: {server_error}",
                        extra={"server_id": server.get('id')},
                        exc_info=True
                    )
                    continue

            logger.info(
                f"Server cache refresh complete: {cached_count}/{len(servers)} servers cached",
                extra={
                    "cached_count": cached_count,
                    "total_count": len(servers)
                }
            )

            return cached_count

        except Exception as e:
            logger.error(
                f"Failed to refresh server cache: {e}",
                exc_info=True
            )
            raise

    @staticmethod
    async def get_or_fetch_server(
        conn: asyncpg.Connection,
        server_id: str,
        discord_token: str
    ) -> Dict:
        """
        Get server from cache or fetch from Discord API if stale/missing.

        This method implements a cache-first strategy with automatic refresh:
        1. Check if server exists in cache
        2. If cached and fresh (< 24 hours), return cached data
        3. If stale or missing, fetch from Discord API
        4. Update cache with fresh data
        5. Return server data

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild/server ID
            discord_token: Discord bot token for authentication

        Returns:
            Dictionary containing server data with keys:
                - server_id (str): Discord guild ID
                - name (str): Server name
                - icon_url (str, optional): Server icon URL
                - member_count (int, optional): Member count
                - owner_id (str, optional): Owner user ID
                - updated_at (datetime): Last update timestamp
                And other cached fields...

        Raises:
            Exception: If both cache lookup and API fetch fail

        Example:
            >>> async with pool.acquire() as conn:
            ...     server = await DiscordCacheService.get_or_fetch_server(
            ...         conn, server_id="123456789", discord_token=token
            ...     )
            ...     print(f"Server name: {server['name']}")
        """
        try:
            # Check if cache is stale (older than 24 hours)
            is_stale = await ServerDAO.is_server_cache_stale(
                conn,
                server_id,
                max_age_hours=24
            )

            if not is_stale:
                # Cache is fresh, return cached data
                server = await ServerDAO.get_server_by_id(conn, server_id)

                if server:
                    logger.debug(
                        f"Returning cached server data for {server_id}",
                        extra={"server_id": server_id}
                    )
                    return server

            # Cache is stale or missing, fetch from Discord API
            logger.info(
                f"Fetching fresh server data for {server_id} from Discord API",
                extra={"server_id": server_id}
            )

            # Fetch server from Discord API
            # Note: Discord API doesn't have a single guild endpoint,
            # we need to fetch all guilds and filter
            servers = await DiscordCacheService.fetch_user_servers(discord_token)

            # Find the specific server
            server_data = None
            for server in servers:
                if server.get('id') == server_id:
                    server_data = server
                    break

            if not server_data:
                logger.warning(
                    f"Server {server_id} not found in user's guilds",
                    extra={"server_id": server_id}
                )
                # Return a minimal server record if not found
                return {
                    'server_id': server_id,
                    'name': f'Server {server_id[:8]}...',
                    'icon_url': None,
                    'member_count': None,
                    'owner_id': None,
                }

            # Prepare and cache server data
            cache_data = {
                'server_id': server_data.get('id'),
                'name': server_data.get('name', 'Unknown'),
                'icon_url': _build_icon_url(server_data.get('icon'), server_id),
                'member_count': server_data.get('approximate_member_count'),
                'owner_id': server_data.get('owner_id'),
            }

            await ServerDAO.cache_server(conn, cache_data)

            # Fetch and return updated cache
            cached_server = await ServerDAO.get_server_by_id(conn, server_id)

            logger.info(
                f"Cached fresh server data for {server_id}",
                extra={"server_id": server_id}
            )

            return cached_server

        except Exception as e:
            logger.error(
                f"Failed to get or fetch server {server_id}: {e}",
                extra={"server_id": server_id},
                exc_info=True
            )
            raise

    @staticmethod
    async def get_server_display_name(
        conn: asyncpg.Connection,
        server_id: str
    ) -> str:
        """
        Get server display name from cache with fallback.

        Retrieves the server name from the cache. If the server is not
        found in cache, returns a truncated server ID as a fallback.
        This method never raises exceptions and always returns a
        displayable string.

        Args:
            conn: AsyncPG database connection
            server_id: Discord guild/server ID

        Returns:
            Server name from cache, or formatted server ID if not found.
            Format: "Server Name" or "12345678..." (first 8 chars + ...)

        Example:
            >>> async with pool.acquire() as conn:
            ...     name = await DiscordCacheService.get_server_display_name(
            ...         conn, server_id="123456789012345"
            ...     )
            ...     print(name)  # "My Server" or "12345678..."
        """
        try:
            # Try to get server from cache
            server = await ServerDAO.get_server_by_id(conn, server_id)

            if server and server.get('name'):
                return server['name']

            # Fallback: truncated server ID
            fallback_name = f"{server_id[:8]}..." if len(server_id) > 8 else server_id

            logger.debug(
                f"Server {server_id} not in cache, using fallback name",
                extra={"server_id": server_id, "fallback_name": fallback_name}
            )

            return fallback_name

        except Exception as e:
            # Even on error, return a safe fallback
            logger.warning(
                f"Error getting server display name for {server_id}: {e}",
                extra={"server_id": server_id}
            )
            return f"{server_id[:8]}..." if len(server_id) > 8 else server_id


# Helper functions

def _build_icon_url(icon_hash: Optional[str], server_id: str) -> Optional[str]:
    """
    Build Discord CDN URL for server icon.

    Args:
        icon_hash: Icon hash from Discord API
        server_id: Server/guild ID

    Returns:
        CDN URL for the icon, or None if no icon
    """
    if not icon_hash:
        return None

    # Discord CDN URL format
    # https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png
    return f"https://cdn.discordapp.com/icons/{server_id}/{icon_hash}.png"


def _map_channel_type(discord_type: int) -> str:
    """
    Map Discord channel type integer to string representation.

    Args:
        discord_type: Discord channel type integer

    Returns:
        String representation of channel type
    """
    type_mapping = {
        0: 'text',
        11: 'thread',
        12: 'thread',
    }
    return type_mapping.get(discord_type, 'unknown')


# Export public API
__all__ = [
    "DiscordCacheService",
]
