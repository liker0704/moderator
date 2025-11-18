"""
Channel allowlist management service.

This module manages channel-specific allowlists:
- Checks if channels are allowlisted for message monitoring
- Adds and removes channels from allowlist
- Provides allowlist querying and listing for channels
- Handles thread filtering for Discord channels
- Validates platform-specific channel configurations

The allowlist determines which channels' messages are monitored
and forwarded to the moderator for review.
"""

import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChannelAllowlist:
    """
    Represents a channel allowlist entry.

    Attributes:
        id: Internal database ID
        platform: Platform name ('discord' or 'telegram')
        server_id: Server/guild ID (Discord only, None for Telegram)
        channel_id: Channel/chat ID
        thread_filter: Thread filter configuration (optional)
        enabled: Whether this allowlist entry is active
        created_at: When the entry was created
        updated_at: When the entry was last updated
    """
    id: int
    platform: str
    server_id: Optional[str]
    channel_id: str
    thread_filter: Optional[Dict[str, Any]]
    enabled: bool
    created_at: datetime
    updated_at: datetime


async def is_channel_allowed(
    conn,
    platform: str,
    channel_id: str,
    server_id: Optional[str] = None,
    thread_id: Optional[str] = None
) -> bool:
    """
    Check if a channel is in the allowlist and should be monitored.

    This function verifies whether messages from a specific channel should
    be forwarded for moderation based on the allowlist configuration.
    For Discord channels with thread filters, it also validates thread IDs.

    Args:
        conn: Database connection (asyncpg connection or pool)
        platform: Platform name ('discord' or 'telegram')
        channel_id: Channel or chat ID
        server_id: Server/guild ID (required for Discord, None for Telegram)
        thread_id: Thread ID (optional, for Discord threads)

    Returns:
        True if the channel is allowed and should be monitored, False otherwise

    Example:
        >>> async with pool.acquire() as conn:
        >>>     allowed = await is_channel_allowed(
        >>>         conn, "discord", "123456789", server_id="987654321"
        >>>     )
        >>>     if allowed:
        >>>         # Process message
    """
    try:
        # Query for matching allowlist entry
        query = """
            SELECT id, thread_filter_json, enabled
            FROM channels_allowlist
            WHERE platform = $1
              AND channel_id = $2
              AND (server_id = $3 OR (server_id IS NULL AND $3 IS NULL))
            LIMIT 1
        """

        row = await conn.fetchrow(query, platform, channel_id, server_id)

        if not row:
            logger.debug(
                f"Channel not in allowlist: {platform}/{channel_id}",
                extra={"platform": platform, "channel_id": channel_id}
            )
            return False

        # Check if entry is enabled
        if not row["enabled"]:
            logger.debug(
                f"Channel allowlist entry is disabled: {platform}/{channel_id}",
                extra={"platform": platform, "channel_id": channel_id}
            )
            return False

        # If no thread_id provided or no filter configured, allow
        if not thread_id or not row["thread_filter_json"]:
            return True

        # Parse thread filter
        try:
            thread_filter = json.loads(row["thread_filter_json"])
        except json.JSONDecodeError:
            logger.warning(
                f"Invalid thread_filter_json for allowlist entry {row['id']}",
                extra={"allowlist_id": row["id"]}
            )
            return True  # Allow by default if filter is invalid

        # Check thread_ids filter
        if "thread_ids" in thread_filter:
            allowed_threads = thread_filter["thread_ids"]
            if isinstance(allowed_threads, list):
                return thread_id in allowed_threads

        # Check thread_name_pattern filter (requires thread name, not just ID)
        # This is a basic check - actual thread name matching would require
        # additional context
        if "thread_name_pattern" in thread_filter:
            # For now, if pattern exists but we only have ID, allow it
            # The caller should provide thread name for proper filtering
            return True

        # If filter exists but doesn't match known patterns, allow by default
        return True

    except Exception as e:
        logger.error(
            f"Error checking channel allowlist: {e}",
            extra={"platform": platform, "channel_id": channel_id},
            exc_info=True
        )
        # Fail open - allow the channel if there's an error
        return True


async def add_channel_to_allowlist(
    conn,
    platform: str,
    channel_id: str,
    server_id: Optional[str] = None,
    thread_filter: Optional[Dict[str, Any]] = None,
    enabled: bool = True
) -> int:
    """
    Add a channel to the allowlist.

    This function adds a new channel to the monitoring allowlist. If the
    channel already exists, it updates the existing entry.

    Args:
        conn: Database connection (asyncpg connection or pool)
        platform: Platform name ('discord' or 'telegram')
        channel_id: Channel or chat ID
        server_id: Server/guild ID (required for Discord, None for Telegram)
        thread_filter: Optional thread filter configuration
            Examples:
            - {"thread_ids": ["123", "456"]} - specific threads only
            - {"thread_name_pattern": "^Support-"} - threads matching pattern
        enabled: Whether to enable this allowlist entry (default: True)

    Returns:
        The ID of the created or updated allowlist entry

    Raises:
        ValueError: If platform is invalid or required parameters are missing
        Exception: If database operation fails

    Example:
        >>> async with pool.acquire() as conn:
        >>>     entry_id = await add_channel_to_allowlist(
        >>>         conn,
        >>>         platform="discord",
        >>>         server_id="111222333",
        >>>         channel_id="444555666",
        >>>         thread_filter={"thread_ids": ["789", "012"]}
        >>>     )
    """
    # Validate platform
    if platform not in ["discord", "telegram"]:
        raise ValueError(f"Invalid platform: {platform}. Must be 'discord' or 'telegram'")

    # Validate server_id for Discord
    if platform == "discord" and not server_id:
        raise ValueError("server_id is required for Discord channels")

    try:
        # Convert thread_filter to JSON string
        thread_filter_json = json.dumps(thread_filter) if thread_filter else None

        # Upsert query (insert or update on conflict)
        query = """
            INSERT INTO channels_allowlist (
                platform, server_id, channel_id, thread_filter_json, enabled, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
            ON CONFLICT (platform, server_id, channel_id)
            DO UPDATE SET
                thread_filter_json = EXCLUDED.thread_filter_json,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            RETURNING id
        """

        row = await conn.fetchrow(
            query,
            platform,
            server_id,
            channel_id,
            thread_filter_json,
            enabled
        )

        entry_id = row["id"]

        logger.info(
            f"Added channel to allowlist: {platform}/{channel_id}",
            extra={
                "platform": platform,
                "channel_id": channel_id,
                "server_id": server_id,
                "allowlist_id": entry_id
            }
        )

        return entry_id

    except Exception as e:
        logger.error(
            f"Error adding channel to allowlist: {e}",
            extra={
                "platform": platform,
                "channel_id": channel_id,
                "server_id": server_id
            },
            exc_info=True
        )
        raise


async def remove_channel_from_allowlist(
    conn,
    channel_id: str,
    platform: Optional[str] = None,
    server_id: Optional[str] = None
) -> bool:
    """
    Remove a channel from the allowlist.

    This function removes a channel from the monitoring allowlist by
    setting its 'enabled' flag to False. The entry is not deleted to
    maintain audit history.

    Args:
        conn: Database connection (asyncpg connection or pool)
        channel_id: Channel or chat ID to remove
        platform: Optional platform filter
        server_id: Optional server/guild ID filter

    Returns:
        True if a channel was removed, False if no matching channel was found

    Example:
        >>> async with pool.acquire() as conn:
        >>>     removed = await remove_channel_from_allowlist(
        >>>         conn,
        >>>         channel_id="444555666",
        >>>         platform="discord"
        >>>     )
    """
    try:
        # Build query based on provided parameters
        conditions = ["channel_id = $1"]
        params = [channel_id]
        param_count = 1

        if platform:
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(platform)

        if server_id:
            param_count += 1
            conditions.append(f"server_id = ${param_count}")
            params.append(server_id)

        query = f"""
            UPDATE channels_allowlist
            SET enabled = false, updated_at = NOW()
            WHERE {' AND '.join(conditions)}
            RETURNING id
        """

        rows = await conn.fetch(query, *params)

        if rows:
            logger.info(
                f"Removed {len(rows)} channel(s) from allowlist",
                extra={
                    "channel_id": channel_id,
                    "platform": platform,
                    "count": len(rows)
                }
            )
            return True
        else:
            logger.warning(
                f"No matching channel found to remove from allowlist",
                extra={
                    "channel_id": channel_id,
                    "platform": platform
                }
            )
            return False

    except Exception as e:
        logger.error(
            f"Error removing channel from allowlist: {e}",
            extra={"channel_id": channel_id, "platform": platform},
            exc_info=True
        )
        raise


async def get_allowlist_channels(
    conn,
    platform: Optional[str] = None,
    enabled_only: bool = True
) -> List[ChannelAllowlist]:
    """
    Get list of channels in the allowlist.

    This function retrieves all channels in the allowlist, optionally
    filtered by platform and enabled status.

    Args:
        conn: Database connection (asyncpg connection or pool)
        platform: Optional platform filter ('discord' or 'telegram')
        enabled_only: If True, only return enabled channels (default: True)

    Returns:
        List of ChannelAllowlist objects

    Example:
        >>> async with pool.acquire() as conn:
        >>>     discord_channels = await get_allowlist_channels(
        >>>         conn,
        >>>         platform="discord"
        >>>     )
        >>>     for channel in discord_channels:
        >>>         print(f"Channel: {channel.channel_id}")
    """
    try:
        # Build query based on filters
        conditions = []
        params = []
        param_count = 0

        if platform:
            param_count += 1
            conditions.append(f"platform = ${param_count}")
            params.append(platform)

        if enabled_only:
            conditions.append("enabled = true")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT
                id,
                platform,
                server_id,
                channel_id,
                thread_filter_json,
                enabled,
                created_at,
                updated_at
            FROM channels_allowlist
            {where_clause}
            ORDER BY created_at DESC
        """

        rows = await conn.fetch(query, *params)

        channels = []
        for row in rows:
            # Parse thread filter JSON
            thread_filter = None
            if row["thread_filter_json"]:
                try:
                    thread_filter = json.loads(row["thread_filter_json"])
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid thread_filter_json for allowlist entry {row['id']}",
                        extra={"allowlist_id": row["id"]}
                    )

            channel = ChannelAllowlist(
                id=row["id"],
                platform=row["platform"],
                server_id=row["server_id"],
                channel_id=row["channel_id"],
                thread_filter=thread_filter,
                enabled=row["enabled"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            channels.append(channel)

        logger.debug(
            f"Retrieved {len(channels)} allowlist channels",
            extra={"platform": platform, "count": len(channels)}
        )

        return channels

    except Exception as e:
        logger.error(
            f"Error retrieving allowlist channels: {e}",
            extra={"platform": platform},
            exc_info=True
        )
        raise
