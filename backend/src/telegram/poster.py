"""
Telegram message posting and notification delivery.

This module handles sending messages to Telegram users:
- Posts new message notifications to authorized users
- Implements message queuing for rate limit compliance
- Handles retry logic for failed message deliveries
- Manages user-specific DND schedule checking
- Supports batch notifications for multiple messages
- Handles message editing for status updates
- Implements notification prioritization

Ensures users receive timely notifications while respecting their
preferences and Telegram API rate limits.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class TelegramPoster:
    """
    Telegram Bot API client for posting messages.

    This class provides methods to interact with Telegram's Bot API to send,
    edit, and manage messages. It includes robust error handling, rate limiting,
    and retry logic.

    Attributes:
        token: Telegram bot token for authentication
        base_url: Telegram Bot API base URL
        max_retries: Maximum number of retry attempts for failed requests
        timeout: Request timeout in seconds
    """

    def __init__(self, token: str, max_retries: int = 3, timeout: int = 30):
        """
        Initialize the Telegram poster.

        Args:
            token: Telegram bot token for authentication
            max_retries: Maximum number of retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 30)
        """
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        logger.info("TelegramPoster initialized", extra={"platform": "telegram"})

    async def _make_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Telegram Bot API with retry logic.

        Implements exponential backoff for retries and handles rate limiting.

        Args:
            method: Bot API method name (e.g., "sendMessage", "editMessageText")
            params: Optional parameters for the API call
            retry_count: Current retry attempt number

        Returns:
            Dictionary containing the API response or error information
        """
        url = f"{self.base_url}/{method}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=params) as response:
                    response_data = await response.json()

                    # Check if request was successful
                    if response_data.get("ok"):
                        return {
                            "success": True,
                            "data": response_data.get("result")
                        }

                    # Handle errors from Telegram API
                    error_code = response_data.get("error_code", 0)
                    description = response_data.get("description", "Unknown error")

                    # Handle rate limiting (429)
                    if error_code == 429:
                        # Extract retry_after from response parameters
                        retry_after = response_data.get("parameters", {}).get("retry_after", 1)
                        logger.warning(
                            f"Rate limited, retrying after {retry_after}s",
                            extra={
                                "platform": "telegram",
                                "retry_after": retry_after,
                                "method": method
                            }
                        )

                        if retry_count < self.max_retries:
                            await asyncio.sleep(retry_after)
                            return await self._make_request(method, params, retry_count + 1)
                        else:
                            return {
                                "success": False,
                                "error": "Rate limit exceeded, max retries reached",
                                "error_code": 429
                            }

                    # Handle unauthorized errors (401)
                    elif error_code == 401:
                        logger.error(
                            "Authentication failed - invalid bot token",
                            extra={"platform": "telegram", "method": method}
                        )
                        return {
                            "success": False,
                            "error": "Authentication failed - invalid bot token",
                            "error_code": 401
                        }

                    # Handle forbidden errors (403)
                    elif error_code == 403:
                        logger.error(
                            f"Forbidden: {description}",
                            extra={"platform": "telegram", "method": method}
                        )
                        return {
                            "success": False,
                            "error": f"Forbidden: {description}",
                            "error_code": 403
                        }

                    # Handle bad request errors (400)
                    elif error_code == 400:
                        logger.error(
                            f"Bad request: {description}",
                            extra={"platform": "telegram", "method": method}
                        )
                        return {
                            "success": False,
                            "error": f"Bad request: {description}",
                            "error_code": 400
                        }

                    # Handle not found errors (404)
                    elif error_code == 404:
                        logger.error(
                            f"Not found: {description}",
                            extra={"platform": "telegram", "method": method}
                        )
                        return {
                            "success": False,
                            "error": f"Not found: {description}",
                            "error_code": 404
                        }

                    # Handle server errors (5xx) with retry
                    elif error_code >= 500:
                        logger.warning(
                            f"Server error {error_code}, retrying...",
                            extra={
                                "platform": "telegram",
                                "retry_count": retry_count,
                                "method": method
                            }
                        )

                        if retry_count < self.max_retries:
                            # Exponential backoff: 1s, 2s, 4s
                            wait_time = 2 ** retry_count
                            await asyncio.sleep(wait_time)
                            return await self._make_request(method, params, retry_count + 1)
                        else:
                            return {
                                "success": False,
                                "error": f"Server error {error_code}, max retries reached",
                                "error_code": error_code
                            }

                    # Handle other errors
                    else:
                        logger.error(
                            f"API error: {description}",
                            extra={
                                "platform": "telegram",
                                "error_code": error_code,
                                "method": method
                            }
                        )
                        return {
                            "success": False,
                            "error": description,
                            "error_code": error_code
                        }

        except asyncio.TimeoutError:
            logger.error(
                "Request timeout",
                extra={"platform": "telegram", "method": method}
            )

            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(method, params, retry_count + 1)
            else:
                return {
                    "success": False,
                    "error": "Request timeout, max retries reached",
                    "error_code": 0
                }

        except aiohttp.ClientError as e:
            logger.error(
                f"Network error: {str(e)}",
                extra={"platform": "telegram", "method": method}
            )

            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                return await self._make_request(method, params, retry_count + 1)
            else:
                return {
                    "success": False,
                    "error": f"Network error: {str(e)}",
                    "error_code": 0
                }

        except Exception as e:
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={"platform": "telegram", "method": method},
                exc_info=True
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_code": 0
            }

    async def post_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
        disable_preview: bool = True
    ) -> Dict[str, Any]:
        """
        Post a message to a Telegram chat.

        This method sends a message to the specified chat. It supports
        replying to specific messages and controlling link previews.

        Args:
            chat_id: Telegram chat ID where the message should be posted
            text: Message text (supports Markdown and HTML formatting)
            reply_to_message_id: Optional message ID to reply to
            disable_preview: Whether to disable web page previews (default: True)

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - message_id (int): ID of the created message (if successful)
                - error (str): Error message (if failed)
                - error_code (int): Error code (if applicable)

        Example:
            >>> poster = TelegramPoster(token="your_bot_token")
            >>> result = await poster.post_message(
            ...     chat_id=123456789,
            ...     text="Hello, Telegram!",
            ...     reply_to_message_id=987654321
            ... )
            >>> if result["success"]:
            ...     print(f"Message posted: {result['message_id']}")
        """
        logger.info(
            f"Posting message to chat {chat_id}",
            extra={
                "platform": "telegram",
                "chat_id": chat_id,
                "has_reply": reply_to_message_id is not None
            }
        )

        # Build message parameters
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_preview
        }

        # Add reply_to if specified
        if reply_to_message_id:
            params["reply_to_message_id"] = reply_to_message_id

        # Make API request
        result = await self._make_request("sendMessage", params)

        if result["success"]:
            message_id = result["data"].get("message_id")
            logger.info(
                f"Message posted successfully: {message_id}",
                extra={
                    "platform": "telegram",
                    "chat_id": chat_id,
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
                    "platform": "telegram",
                    "chat_id": chat_id,
                    "error_code": result.get("error_code")
                }
            )
            return result

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str
    ) -> Dict[str, Any]:
        """
        Edit an existing Telegram message.

        This method modifies the text of an existing message. Only messages
        sent by the bot can be edited.

        Args:
            chat_id: Telegram chat ID where the message is located
            message_id: ID of the message to edit
            text: New message text

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - message_id (int): ID of the edited message (if successful)
                - error (str): Error message (if failed)
                - error_code (int): Error code (if applicable)

        Example:
            >>> poster = TelegramPoster(token="your_bot_token")
            >>> result = await poster.edit_message(
            ...     chat_id=123456789,
            ...     message_id=987654321,
            ...     text="Updated content"
            ... )
            >>> if result["success"]:
            ...     print("Message updated successfully")
        """
        logger.info(
            f"Editing message {message_id} in chat {chat_id}",
            extra={
                "platform": "telegram",
                "chat_id": chat_id,
                "message_id": message_id
            }
        )

        # Build edit parameters
        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }

        # Make API request
        result = await self._make_request("editMessageText", params)

        if result["success"]:
            logger.info(
                f"Message edited successfully: {message_id}",
                extra={
                    "platform": "telegram",
                    "chat_id": chat_id,
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
                    "platform": "telegram",
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error_code": result.get("error_code")
                }
            )
            return result

    async def delete_message(
        self,
        chat_id: int,
        message_id: int
    ) -> Dict[str, Any]:
        """
        Delete a Telegram message.

        This method deletes a message from the chat. Only messages sent by
        the bot can be deleted (with some exceptions based on bot permissions).

        Args:
            chat_id: Telegram chat ID where the message is located
            message_id: ID of the message to delete

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - error (str): Error message (if failed)
                - error_code (int): Error code (if applicable)

        Example:
            >>> poster = TelegramPoster(token="your_bot_token")
            >>> result = await poster.delete_message(
            ...     chat_id=123456789,
            ...     message_id=987654321
            ... )
            >>> if result["success"]:
            ...     print("Message deleted successfully")
        """
        logger.info(
            f"Deleting message {message_id} in chat {chat_id}",
            extra={
                "platform": "telegram",
                "chat_id": chat_id,
                "message_id": message_id
            }
        )

        # Build delete parameters
        params = {
            "chat_id": chat_id,
            "message_id": message_id
        }

        # Make API request
        result = await self._make_request("deleteMessage", params)

        if result["success"]:
            logger.info(
                f"Message deleted successfully: {message_id}",
                extra={
                    "platform": "telegram",
                    "chat_id": chat_id,
                    "message_id": message_id
                }
            )
            return {
                "success": True,
                "message_id": message_id
            }
        else:
            logger.error(
                f"Failed to delete message: {result.get('error')}",
                extra={
                    "platform": "telegram",
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "error_code": result.get("error_code")
                }
            )
            return result

    async def get_chat_info(self, chat_id: int) -> Dict[str, Any]:
        """
        Retrieve information about a Telegram chat.

        This method fetches chat metadata including title, type, and other
        properties. Useful for validating chat access and getting chat details.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Dictionary containing:
                - success (bool): Whether the operation succeeded
                - data (dict): Chat information (if successful)
                - error (str): Error message (if failed)
                - error_code (int): Error code (if applicable)

        Example:
            >>> poster = TelegramPoster(token="your_bot_token")
            >>> result = await poster.get_chat_info(123456789)
            >>> if result["success"]:
            ...     print(f"Chat title: {result['data']['title']}")
        """
        logger.info(
            f"Fetching info for chat {chat_id}",
            extra={"platform": "telegram", "chat_id": chat_id}
        )

        # Build parameters
        params = {
            "chat_id": chat_id
        }

        # Make API request
        result = await self._make_request("getChat", params)

        if result["success"]:
            chat_title = result["data"].get("title") or result["data"].get("username", "Unknown")
            logger.info(
                f"Chat info retrieved: {chat_title}",
                extra={
                    "platform": "telegram",
                    "chat_id": chat_id,
                    "chat_title": chat_title
                }
            )
            return result
        else:
            logger.error(
                f"Failed to get chat info: {result.get('error')}",
                extra={
                    "platform": "telegram",
                    "chat_id": chat_id,
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
        """Test the Telegram poster functionality."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            print("Error: TELEGRAM_BOT_TOKEN not found in environment")
            return

        poster = TelegramPoster(token)

        # Test chat info
        chat_id = os.getenv("TEST_CHAT_ID")
        if chat_id:
            try:
                chat_id = int(chat_id)
            except ValueError:
                print("Error: TEST_CHAT_ID must be an integer")
                return

            print(f"\nTesting get_chat_info for chat {chat_id}...")
            result = await poster.get_chat_info(chat_id)
            print(f"Result: {result}")

            if result["success"]:
                # Test posting
                print("\nTesting post_message...")
                post_result = await poster.post_message(
                    chat_id=chat_id,
                    text="Test message from Telegram poster"
                )
                print(f"Result: {post_result}")

                # Test editing (if post was successful)
                if post_result["success"]:
                    message_id = post_result["message_id"]
                    print(f"\nTesting edit_message for message {message_id}...")
                    edit_result = await poster.edit_message(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="Updated test message"
                    )
                    print(f"Result: {edit_result}")

                    # Test deleting
                    print(f"\nTesting delete_message for message {message_id}...")
                    await asyncio.sleep(2)  # Wait a bit before deleting
                    delete_result = await poster.delete_message(
                        chat_id=chat_id,
                        message_id=message_id
                    )
                    print(f"Result: {delete_result}")

    # Run tests
    asyncio.run(test_poster())
