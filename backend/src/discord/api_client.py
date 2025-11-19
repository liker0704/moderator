"""
Discord REST API client for fetching server and channel information.

This module provides a REST API client for Discord metadata operations:
- Fetches guilds (servers) the user has access to
- Retrieves guild information (name, icon, member count, etc.)
- Gets channel lists for guilds
- Handles rate limiting and error responses
- Supports async context manager usage

This complements the Gateway (WebSocket) client by providing REST API
functionality for fetching server/channel metadata that isn't available
through the Gateway events.

Usage:
    >>> async with DiscordAPIClient(token) as client:
    ...     guilds = await client.get_guilds()
    ...     channels = await client.get_guild_channels(guild_id)
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from utils.logger import get_logger
from services.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class DiscordAPIError(Exception):
    """
    Custom exception for Discord API errors.

    This exception is raised when Discord API requests fail, providing
    structured error information including status code and error message.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code (e.g., 403, 404, 429)
        response_data: Raw response data from Discord API (if available)
    """

    def __init__(self, message: str, status_code: int, response_data: Optional[Dict] = None):
        """
        Initialize the Discord API error.

        Args:
            message: Error message describing what went wrong
            status_code: HTTP status code from the failed request
            response_data: Optional raw response data from Discord
        """
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        return f"DiscordAPIError [{self.status_code}]: {self.message}"


class DiscordAPIClient:
    """
    Discord REST API client for fetching server and channel metadata.

    This client provides methods to interact with Discord's REST API for
    retrieving guild (server) and channel information. It includes robust
    error handling, rate limiting, and can be used as an async context manager.

    Features:
    - Fetch user's guilds (servers)
    - Get detailed guild information
    - Retrieve guild channels
    - Automatic rate limit handling
    - Proper error handling with custom exceptions
    - Async context manager support

    Attributes:
        token: Discord user token for authentication
        base_url: Discord API base URL (v10)
        session: aiohttp ClientSession for making requests
        rate_limiter: Rate limiter instance for API compliance
        timeout: Request timeout configuration

    Example:
        >>> async with DiscordAPIClient(token) as client:
        ...     guilds = await client.get_guilds()
        ...     for guild in guilds:
        ...         print(f"Guild: {guild['name']} ({guild['id']})")
        ...         channels = await client.get_guild_channels(guild['id'])
        ...         for channel in channels:
        ...             print(f"  Channel: {channel['name']}")
    """

    def __init__(self, token: str, timeout: int = 30):
        """
        Initialize the Discord API client.

        Creates a new API client with the provided token. The aiohttp session
        is initialized and will be used for all subsequent requests.

        Args:
            token: Discord user token for authentication
            timeout: Request timeout in seconds (default: 30)

        Example:
            >>> client = DiscordAPIClient(token="your_discord_token")
            >>> # Remember to close the client when done
            >>> await client.close()
        """
        self.token = token
        self.base_url = "https://discord.com/api/v10"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = get_rate_limiter()

        logger.info(
            "DiscordAPIClient initialized",
            extra={"platform": "discord", "api_version": "v10"}
        )

    async def __aenter__(self):
        """
        Async context manager entry.

        Initializes the aiohttp session when entering the context.

        Returns:
            Self for use in async with statements
        """
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.

        Closes the aiohttp session when exiting the context.

        Args:
            exc_type: Exception type (if an exception occurred)
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        await self.close()

    async def _ensure_session(self) -> None:
        """
        Ensure aiohttp session is initialized.

        Creates a new session if one doesn't exist. This is called automatically
        by all request methods.
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            logger.debug("Created new aiohttp session")

    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for Discord API requests.

        Returns the required headers for authenticating with Discord's API,
        including the authorization token, content type, and user agent.

        Returns:
            Dictionary containing required headers for Discord API
        """
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (moderator-bot, 1.0.0)"
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Discord API with rate limiting and error handling.

        This internal method handles:
        - Rate limit checking and waiting
        - HTTP request execution
        - Response parsing
        - Error handling (403, 404, 429, 5xx)
        - Automatic retries with exponential backoff

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/users/@me/guilds")
            retry_count: Current retry attempt number
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed JSON response from Discord API

        Raises:
            DiscordAPIError: If the request fails (403, 404, etc.)
        """
        await self._ensure_session()
        url = f"{self.base_url}{endpoint}"

        # Acquire rate limit before making request
        await self.rate_limiter.acquire(endpoint)

        logger.debug(
            f"Making {method} request to {endpoint}",
            extra={"method": method, "endpoint": endpoint}
        )

        try:
            async with self.session.request(
                method,
                url,
                headers=self._get_headers()
            ) as response:
                # Update rate limit state from response headers
                self.rate_limiter.update_from_response(endpoint, dict(response.headers))

                # Get response data
                try:
                    response_data = await response.json()
                except aiohttp.ContentTypeError:
                    # Handle non-JSON responses
                    response_data = {"error": await response.text()}

                # Handle rate limiting (429)
                if response.status == 429:
                    wait_time = await self.rate_limiter.handle_rate_limit_response(
                        endpoint,
                        response_data,
                        retry_count,
                        max_retries
                    )

                    if wait_time is not None:
                        logger.warning(
                            f"Rate limited, retrying after {wait_time}s",
                            extra={
                                "platform": "discord",
                                "retry_after": wait_time,
                                "retry_count": retry_count,
                                "endpoint": endpoint
                            }
                        )
                        await asyncio.sleep(wait_time)
                        return await self._make_request(method, endpoint, retry_count + 1, max_retries)
                    else:
                        raise DiscordAPIError(
                            "Rate limit exceeded, max retries reached",
                            429,
                            response_data
                        )

                # Handle authentication errors (401)
                elif response.status == 401:
                    logger.error(
                        "Authentication failed - invalid token",
                        extra={"platform": "discord"}
                    )
                    raise DiscordAPIError(
                        "Authentication failed - invalid token",
                        401,
                        response_data
                    )

                # Handle permission errors (403)
                elif response.status == 403:
                    logger.error(
                        "Permission denied",
                        extra={"platform": "discord", "endpoint": endpoint}
                    )
                    raise DiscordAPIError(
                        "Permission denied - insufficient permissions or access",
                        403,
                        response_data
                    )

                # Handle not found errors (404)
                elif response.status == 404:
                    logger.error(
                        "Resource not found",
                        extra={"platform": "discord", "endpoint": endpoint}
                    )
                    raise DiscordAPIError(
                        "Resource not found",
                        404,
                        response_data
                    )

                # Handle other client errors (4xx)
                elif 400 <= response.status < 500:
                    error_message = response_data.get("message", "Client error")
                    logger.error(
                        f"Client error: {error_message}",
                        extra={
                            "platform": "discord",
                            "status": response.status,
                            "endpoint": endpoint
                        }
                    )
                    raise DiscordAPIError(
                        error_message,
                        response.status,
                        response_data
                    )

                # Handle server errors (5xx) with retry
                elif response.status >= 500:
                    logger.warning(
                        f"Server error {response.status}, retrying...",
                        extra={"platform": "discord", "retry_count": retry_count}
                    )

                    if retry_count < max_retries:
                        # Exponential backoff: 1s, 2s, 4s
                        wait_time = 2 ** retry_count
                        await asyncio.sleep(wait_time)
                        return await self._make_request(method, endpoint, retry_count + 1, max_retries)
                    else:
                        raise DiscordAPIError(
                            f"Server error {response.status}, max retries reached",
                            response.status,
                            response_data
                        )

                # Successful response (2xx)
                else:
                    logger.debug(
                        f"Request successful: {method} {endpoint}",
                        extra={"status": response.status}
                    )
                    return response_data

        except asyncio.TimeoutError:
            logger.error(
                "Request timeout",
                extra={"platform": "discord", "endpoint": endpoint}
            )

            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(method, endpoint, retry_count + 1, max_retries)
            else:
                raise DiscordAPIError(
                    "Request timeout, max retries reached",
                    0
                )

        except aiohttp.ClientError as e:
            logger.error(
                f"Network error: {str(e)}",
                extra={"platform": "discord", "endpoint": endpoint}
            )

            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(method, endpoint, retry_count + 1, max_retries)
            else:
                raise DiscordAPIError(
                    f"Network error: {str(e)}",
                    0
                )

        except DiscordAPIError:
            # Re-raise Discord API errors as-is
            raise

        except Exception as e:
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={"platform": "discord", "endpoint": endpoint},
                exc_info=True
            )
            raise DiscordAPIError(
                f"Unexpected error: {str(e)}",
                0
            )

    async def get_guilds(self) -> List[Dict]:
        """
        Get list of guilds (servers) the user has access to.

        Fetches all guilds that the authenticated user is a member of.
        This includes basic information like guild ID, name, icon, and
        permissions.

        Returns:
            List of guild dictionaries, each containing:
                - id (str): Guild ID
                - name (str): Guild name
                - icon (str): Icon hash (can be None)
                - owner (bool): Whether user owns the guild
                - permissions (str): User's permissions in the guild
                - features (List[str]): Guild features

        Raises:
            DiscordAPIError: If the request fails

        Example:
            >>> guilds = await client.get_guilds()
            >>> for guild in guilds:
            ...     print(f"{guild['name']} (ID: {guild['id']})")
        """
        logger.info(
            "Fetching user guilds",
            extra={"platform": "discord"}
        )

        guilds = await self._make_request("GET", "/users/@me/guilds")

        logger.info(
            f"Retrieved {len(guilds)} guilds",
            extra={"platform": "discord", "guild_count": len(guilds)}
        )

        return guilds

    async def get_guild(self, guild_id: str) -> Dict:
        """
        Get detailed information about a specific guild.

        Fetches comprehensive information about a guild including name,
        icon, member count, roles, and other metadata. Requires the user
        to be a member of the guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Dictionary containing guild information:
                - id (str): Guild ID
                - name (str): Guild name
                - icon (str): Icon hash
                - description (str): Guild description
                - member_count (int): Approximate member count
                - premium_tier (int): Server boost level
                - features (List[str]): Guild features
                - owner_id (str): User ID of guild owner
                ... and many other fields

        Raises:
            DiscordAPIError: If the request fails (403 = no access, 404 = not found)

        Example:
            >>> guild = await client.get_guild("123456789")
            >>> print(f"{guild['name']}: {guild['member_count']} members")
        """
        logger.info(
            f"Fetching guild info for {guild_id}",
            extra={"platform": "discord", "guild_id": guild_id}
        )

        guild = await self._make_request("GET", f"/guilds/{guild_id}")

        logger.info(
            f"Retrieved guild: {guild.get('name', 'Unknown')}",
            extra={
                "platform": "discord",
                "guild_id": guild_id,
                "guild_name": guild.get('name'),
                "member_count": guild.get('approximate_member_count')
            }
        )

        return guild

    async def get_guild_channels(self, guild_id: str) -> List[Dict]:
        """
        Get list of channels in a guild.

        Fetches all channels in the specified guild that the user has
        access to. This includes text channels, voice channels, categories,
        announcements, threads, and other channel types.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of channel dictionaries, each containing:
                - id (str): Channel ID
                - name (str): Channel name
                - type (int): Channel type (0=text, 2=voice, 4=category, etc.)
                - position (int): Channel position in the list
                - parent_id (str): Parent category ID (if applicable)
                - topic (str): Channel topic/description (for text channels)
                - nsfw (bool): Whether channel is NSFW
                - permission_overwrites (List): Permission overwrites

        Raises:
            DiscordAPIError: If the request fails

        Example:
            >>> channels = await client.get_guild_channels("123456789")
            >>> text_channels = [c for c in channels if c['type'] == 0]
            >>> for channel in text_channels:
            ...     print(f"#{channel['name']}")

        Note:
            Channel types:
            - 0: GUILD_TEXT (text channel)
            - 2: GUILD_VOICE (voice channel)
            - 4: GUILD_CATEGORY (category)
            - 5: GUILD_ANNOUNCEMENT (announcement channel)
            - 10-12: Various thread types
            - 13: GUILD_STAGE_VOICE (stage channel)
            - 15: GUILD_FORUM (forum channel)
        """
        logger.info(
            f"Fetching channels for guild {guild_id}",
            extra={"platform": "discord", "guild_id": guild_id}
        )

        channels = await self._make_request("GET", f"/guilds/{guild_id}/channels")

        # Count channels by type for logging
        text_channels = sum(1 for c in channels if c.get('type') == 0)
        voice_channels = sum(1 for c in channels if c.get('type') == 2)

        logger.info(
            f"Retrieved {len(channels)} channels ({text_channels} text, {voice_channels} voice)",
            extra={
                "platform": "discord",
                "guild_id": guild_id,
                "total_channels": len(channels),
                "text_channels": text_channels,
                "voice_channels": voice_channels
            }
        )

        return channels

    async def close(self) -> None:
        """
        Close the aiohttp session.

        Properly closes the HTTP session and releases resources.
        Should be called when the client is no longer needed.

        If using the client as an async context manager, this is called
        automatically when exiting the context.

        Example:
            >>> client = DiscordAPIClient(token)
            >>> try:
            ...     guilds = await client.get_guilds()
            ... finally:
            ...     await client.close()
        """
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info(
                "DiscordAPIClient session closed",
                extra={"platform": "discord"}
            )


# Example usage and testing
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def test_api_client():
        """Test the Discord API client functionality."""
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("Error: DISCORD_TOKEN not found in environment")
            return

        # Test using async context manager
        async with DiscordAPIClient(token) as client:
            try:
                # Test 1: Get guilds
                print("\n=== Testing get_guilds() ===")
                guilds = await client.get_guilds()
                print(f"Found {len(guilds)} guilds:")
                for guild in guilds[:5]:  # Show first 5
                    print(f"  - {guild['name']} (ID: {guild['id']})")

                if guilds:
                    guild_id = guilds[0]['id']

                    # Test 2: Get guild details
                    print(f"\n=== Testing get_guild({guild_id}) ===")
                    guild = await client.get_guild(guild_id)
                    print(f"Guild: {guild['name']}")
                    print(f"  Members: ~{guild.get('approximate_member_count', 'N/A')}")
                    print(f"  Description: {guild.get('description', 'None')}")

                    # Test 3: Get guild channels
                    print(f"\n=== Testing get_guild_channels({guild_id}) ===")
                    channels = await client.get_guild_channels(guild_id)
                    print(f"Found {len(channels)} channels:")

                    # Filter and show text channels
                    text_channels = [c for c in channels if c.get('type') == 0]
                    for channel in text_channels[:10]:  # Show first 10
                        print(f"  #{channel['name']} (ID: {channel['id']})")

                print("\n✅ All tests completed successfully!")

            except DiscordAPIError as e:
                print(f"\n❌ Discord API Error: {e}")
                print(f"   Status Code: {e.status_code}")
                if e.response_data:
                    print(f"   Response: {e.response_data}")

            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                import traceback
                traceback.print_exc()

    # Run tests
    asyncio.run(test_api_client())
