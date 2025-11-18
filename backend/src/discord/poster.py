"""
Discord message posting via REST API.

This module handles posting messages back to Discord:
- Posts formatted message summaries to configured Discord channels
- Implements Discord REST API client for message creation
- Handles message formatting and embed creation
- Manages rate limiting and retry logic for API calls
- Supports rich embeds with author info, timestamps, and formatting
- Handles attachment and link inclusion in posts

Used by the Telegram handlers to post curated message summaries back to Discord
channels after user review and approval.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class DiscordPoster:
    """
    Discord REST API client for posting messages.

    This class provides methods to interact with Discord's REST API to post,
    edit, and retrieve information about messages and channels. It includes
    robust error handling, rate limiting, and retry logic.

    Attributes:
        token: Discord user token for authentication
        base_url: Discord API base URL (v9)
        max_retries: Maximum number of retry attempts for failed requests
        timeout: Request timeout in seconds
    """

    def __init__(self, token: str, max_retries: int = 3, timeout: int = 30):
        """
        Initialize the Discord poster.

        Args:
            token: Discord user token for authentication
            max_retries: Maximum number of retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 30)
        """
        self.token = token
        self.base_url = "https://discord.com/api/v9"
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        logger.info("DiscordPoster initialized", extra={"platform": "discord"})

    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for Discord API requests.

        Returns:
            Dictionary containing required headers including authorization
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
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Discord API with retry logic.

        Implements exponential backoff for retries and handles rate limiting.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            endpoint: API endpoint path
            json_data: Optional JSON payload
            retry_count: Current retry attempt number

        Returns:
            Dictionary containing the API response or error information
        """
        url = f"{self.base_url}{endpoint}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.request(
                    method,
                    url,
                    headers=self._get_headers(),
                    json=json_data
                ) as response:
                    response_data = await response.json()

                    # Handle rate limiting (429)
                    if response.status == 429:
                        retry_after = response_data.get("retry_after", 1)
                        logger.warning(
                            f"Rate limited, retrying after {retry_after}s",
                            extra={"platform": "discord", "retry_after": retry_after}
                        )

                        if retry_count < self.max_retries:
                            await asyncio.sleep(retry_after)
                            return await self._make_request(
                                method, endpoint, json_data, retry_count + 1
                            )
                        else:
                            return {
                                "success": False,
                                "error": "Rate limit exceeded, max retries reached",
                                "error_code": 429
                            }

                    # Handle authentication errors (401)
                    elif response.status == 401:
                        logger.error(
                            "Authentication failed - invalid token",
                            extra={"platform": "discord"}
                        )
                        return {
                            "success": False,
                            "error": "Authentication failed - invalid token",
                            "error_code": 401
                        }

                    # Handle permission errors (403)
                    elif response.status == 403:
                        logger.error(
                            "Permission denied",
                            extra={"platform": "discord", "endpoint": endpoint}
                        )
                        return {
                            "success": False,
                            "error": "Permission denied - insufficient permissions",
                            "error_code": 403
                        }

                    # Handle not found errors (404)
                    elif response.status == 404:
                        logger.error(
                            "Resource not found",
                            extra={"platform": "discord", "endpoint": endpoint}
                        )
                        return {
                            "success": False,
                            "error": "Resource not found",
                            "error_code": 404
                        }

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
                        return {
                            "success": False,
                            "error": error_message,
                            "error_code": response.status
                        }

                    # Handle server errors (5xx) with retry
                    elif response.status >= 500:
                        logger.warning(
                            f"Server error {response.status}, retrying...",
                            extra={"platform": "discord", "retry_count": retry_count}
                        )

                        if retry_count < self.max_retries:
                            # Exponential backoff: 1s, 2s, 4s
                            wait_time = 2 ** retry_count
                            await asyncio.sleep(wait_time)
                            return await self._make_request(
                                method, endpoint, json_data, retry_count + 1
                            )
                        else:
                            return {
                                "success": False,
                                "error": f"Server error {response.status}, max retries reached",
                                "error_code": response.status
                            }

                    # Successful response (2xx)
                    else:
                        return {
                            "success": True,
                            "data": response_data
                        }

        except asyncio.TimeoutError:
            logger.error(
                "Request timeout",
                extra={"platform": "discord", "endpoint": endpoint}
            )

            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, endpoint, json_data, retry_count + 1
                )
            else:
                return {
                    "success": False,
                    "error": "Request timeout, max retries reached",
                    "error_code": 0
                }

        except aiohttp.ClientError as e:
            logger.error(
                f"Network error: {str(e)}",
                extra={"platform": "discord", "endpoint": endpoint}
            )

            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, endpoint, json_data, retry_count + 1
                )
            else:
                return {
                    "success": False,
                    "error": f"Network error: {str(e)}",
                    "error_code": 0
                }

        except Exception as e:
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={"platform": "discord", "endpoint": endpoint},
                exc_info=True
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_code": 0
            }

    async def post_message(
        self,
        channel_id: str,
        content: str,
        thread_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post a message to a Discord channel or thread.

        This method sends a message to the specified channel. It supports
        posting to threads and replying to specific messages.

        Args:
            channel_id: Discord channel ID where the message should be posted
            content: Message content (text)
            thread_id: Optional thread ID (if posting to a thread, use this as channel_id)
            reply_to: Optional message ID to reply to

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - message_id (str): ID of the created message (if successful)
                - error (str): Error message (if failed)
                - error_code (int): HTTP error code (if applicable)

        Example:
            >>> poster = DiscordPoster(token="your_token")
            >>> result = await poster.post_message(
            ...     channel_id="123456789",
            ...     content="Hello, Discord!",
            ...     reply_to="987654321"
            ... )
            >>> if result["success"]:
            ...     print(f"Message posted: {result['message_id']}")
        """
        # Use thread_id as channel_id if provided (threads are channels in Discord API)
        target_channel = thread_id if thread_id else channel_id

        logger.info(
            f"Posting message to channel {target_channel}",
            extra={
                "platform": "discord",
                "channel_id": target_channel,
                "has_reply": reply_to is not None
            }
        )

        # Build message payload
        payload: Dict[str, Any] = {
            "content": content
        }

        # Add message reference for replies
        if reply_to:
            payload["message_reference"] = {
                "message_id": reply_to
            }

        # Make API request
        endpoint = f"/channels/{target_channel}/messages"
        result = await self._make_request("POST", endpoint, payload)

        if result["success"]:
            message_id = result["data"].get("id")
            logger.info(
                f"Message posted successfully: {message_id}",
                extra={
                    "platform": "discord",
                    "channel_id": target_channel,
                    "message_id": message_id
                }
            )
            return {
                "success": True,
                "message_id": message_id,
                "data": result["data"]
            }
        else:
            logger.error(
                f"Failed to post message: {result.get('error')}",
                extra={
                    "platform": "discord",
                    "channel_id": target_channel,
                    "error_code": result.get("error_code")
                }
            )
            return result

    async def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Edit an existing Discord message.

        This method modifies the content of an existing message. Only messages
        sent by the authenticated user can be edited.

        Args:
            channel_id: Discord channel ID where the message is located
            message_id: ID of the message to edit
            content: New message content

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - message_id (str): ID of the edited message (if successful)
                - error (str): Error message (if failed)
                - error_code (int): HTTP error code (if applicable)

        Example:
            >>> poster = DiscordPoster(token="your_token")
            >>> result = await poster.edit_message(
            ...     channel_id="123456789",
            ...     message_id="987654321",
            ...     content="Updated content"
            ... )
            >>> if result["success"]:
            ...     print("Message updated successfully")
        """
        logger.info(
            f"Editing message {message_id} in channel {channel_id}",
            extra={
                "platform": "discord",
                "channel_id": channel_id,
                "message_id": message_id
            }
        )

        # Build edit payload
        payload = {
            "content": content
        }

        # Make API request
        endpoint = f"/channels/{channel_id}/messages/{message_id}"
        result = await self._make_request("PATCH", endpoint, payload)

        if result["success"]:
            logger.info(
                f"Message edited successfully: {message_id}",
                extra={
                    "platform": "discord",
                    "channel_id": channel_id,
                    "message_id": message_id
                }
            )
            return {
                "success": True,
                "message_id": message_id,
                "data": result["data"]
            }
        else:
            logger.error(
                f"Failed to edit message: {result.get('error')}",
                extra={
                    "platform": "discord",
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "error_code": result.get("error_code")
                }
            )
            return result

    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Retrieve information about a Discord channel.

        This method fetches channel metadata including name, type, and other
        properties. Useful for validating channel access and getting channel details.

        Args:
            channel_id: Discord channel ID

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - data (dict): Channel information (if successful)
                - error (str): Error message (if failed)
                - error_code (int): HTTP error code (if applicable)

        Example:
            >>> poster = DiscordPoster(token="your_token")
            >>> result = await poster.get_channel_info("123456789")
            >>> if result["success"]:
            ...     print(f"Channel name: {result['data']['name']}")
        """
        logger.info(
            f"Fetching info for channel {channel_id}",
            extra={"platform": "discord", "channel_id": channel_id}
        )

        # Make API request
        endpoint = f"/channels/{channel_id}"
        result = await self._make_request("GET", endpoint)

        if result["success"]:
            channel_name = result["data"].get("name", "Unknown")
            logger.info(
                f"Channel info retrieved: {channel_name}",
                extra={
                    "platform": "discord",
                    "channel_id": channel_id,
                    "channel_name": channel_name
                }
            )
            return result
        else:
            logger.error(
                f"Failed to get channel info: {result.get('error')}",
                extra={
                    "platform": "discord",
                    "channel_id": channel_id,
                    "error_code": result.get("error_code")
                }
            )
            return result


# Example usage and testing
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def test_poster():
        """Test the Discord poster functionality."""
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("Error: DISCORD_TOKEN not found in environment")
            return

        poster = DiscordPoster(token)

        # Test channel info
        channel_id = os.getenv("TEST_CHANNEL_ID")
        if channel_id:
            print(f"\nTesting get_channel_info for channel {channel_id}...")
            result = await poster.get_channel_info(channel_id)
            print(f"Result: {result}")

            if result["success"]:
                # Test posting
                print("\nTesting post_message...")
                post_result = await poster.post_message(
                    channel_id=channel_id,
                    content="Test message from Discord poster"
                )
                print(f"Result: {post_result}")

                # Test editing (if post was successful)
                if post_result["success"]:
                    message_id = post_result["message_id"]
                    print(f"\nTesting edit_message for message {message_id}...")
                    edit_result = await poster.edit_message(
                        channel_id=channel_id,
                        message_id=message_id,
                        content="Updated test message"
                    )
                    print(f"Result: {edit_result}")

    # Run tests
    asyncio.run(test_poster())
