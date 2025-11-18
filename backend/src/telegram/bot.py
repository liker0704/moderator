"""
Telegram bot initialization and core functionality.

This module manages the Telegram bot instance:
- Initializes bot with API token from configuration
- Implements long polling with getUpdates endpoint
- Manages bot lifecycle (start, stop, error handling)
- Implements middleware for authentication and authorization
- Handles bot commands registration and routing
- Manages conversation states and user sessions (FSM)
- Processes message and callback_query updates

The bot serves as the primary interface for moderators to receive notifications
and interact with Discord message moderation workflow.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

import aiohttp

from ..config import get_config
from ..utils.logger import get_logger

# Get logger for this module
logger = get_logger(__name__)


class TelegramBot:
    """
    Main Telegram Bot class implementing long polling and message handling.

    Attributes:
        token: Telegram Bot API token
        moderator_id: Authorized moderator's Telegram user ID
        base_url: Telegram Bot API base URL
        offset: Current update offset for long polling
        timeout: Long polling timeout in seconds
        running: Bot running state flag
        session: aiohttp ClientSession for HTTP requests
        user_states: In-memory FSM state storage {user_id: state}
        message_handlers: Dictionary of message handlers
        callback_handlers: Dictionary of callback query handlers
        command_handlers: Dictionary of command handlers
    """

    def __init__(self, token: str, moderator_id: int):
        """
        Initialize the Telegram bot.

        Args:
            token: Telegram Bot API token
            moderator_id: Authorized moderator's Telegram user ID
        """
        self.token = token
        self.moderator_id = moderator_id
        self.base_url = f"https://api.telegram.org/bot{token}"

        # Long polling configuration
        self.offset = 0
        self.timeout = 30  # Long polling timeout in seconds

        # Bot state
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None

        # FSM: In-memory state storage for user conversations
        # Format: {user_id: {"state": "awaiting_reply_123", "data": {...}}}
        self.user_states: Dict[int, Dict[str, Any]] = {}

        # Handler registries
        self.message_handlers: list[Callable] = []
        self.callback_handlers: Dict[str, Callable] = {}
        self.command_handlers: Dict[str, Callable] = {}

        logger.info(f"TelegramBot initialized for moderator ID: {moderator_id}")

    async def start(self):
        """
        Start the bot with long polling.

        Initializes aiohttp session and begins the main polling loop.
        Handles reconnection on errors with exponential backoff.
        """
        logger.info("Starting Telegram bot with long polling...")
        self.running = True

        # Initialize aiohttp session
        self.session = aiohttp.ClientSession()

        # Set bot commands
        await self._set_bot_commands()

        retry_delay = 1
        max_retry_delay = 60

        while self.running:
            try:
                await self._poll_updates()
                retry_delay = 1  # Reset on successful poll

            except asyncio.CancelledError:
                logger.info("Bot polling cancelled")
                break

            except Exception as e:
                logger.error(f"Error in polling loop: {e}", exc_info=True)

                if self.running:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_retry_delay)

        # Cleanup
        if self.session:
            await self.session.close()

        logger.info("Telegram bot stopped")

    async def stop(self):
        """Stop the bot gracefully."""
        logger.info("Stopping Telegram bot...")
        self.running = False

    async def _poll_updates(self):
        """
        Main polling loop using getUpdates endpoint.

        Implements long polling with timeout=30 to minimize API calls
        while maintaining responsive updates.
        """
        try:
            data = await self._get_updates(self.offset, self.timeout)

            if data.get('ok'):
                updates = data.get('result', [])

                for update in updates:
                    try:
                        await self.process_update(update)
                    except Exception as e:
                        logger.error(f"Error processing update {update.get('update_id')}: {e}", exc_info=True)

                    # Update offset to acknowledge this update
                    self.offset = update['update_id'] + 1
            else:
                error_description = data.get('description', 'Unknown error')
                logger.error(f"getUpdates failed: {error_description}")
                await asyncio.sleep(5)

        except asyncio.TimeoutError:
            # Timeout is expected with long polling, just continue
            pass
        except Exception as e:
            logger.error(f"Error in _poll_updates: {e}", exc_info=True)
            raise

    async def _get_updates(self, offset: int, timeout: int) -> dict:
        """
        Call Telegram getUpdates API method.

        Args:
            offset: Update offset (last update_id + 1)
            timeout: Long polling timeout in seconds

        Returns:
            API response as dictionary
        """
        params = {
            'offset': offset,
            'timeout': timeout,
            'allowed_updates': ['message', 'callback_query']
        }

        # Add extra time to aiohttp timeout to account for Telegram's long polling
        async with self.session.get(
            f"{self.base_url}/getUpdates",
            params=params,
            timeout=aiohttp.ClientTimeout(total=timeout + 10)
        ) as response:
            return await response.json()

    async def process_update(self, update: dict):
        """
        Process a single update from Telegram.

        Routes the update to appropriate handlers based on type:
        - message: Text messages, photos, commands
        - callback_query: Inline button clicks

        Args:
            update: Update dictionary from Telegram API
        """
        update_id = update.get('update_id')
        logger.debug(f"Processing update {update_id}")

        # Handle message updates
        if 'message' in update:
            await self._handle_message(update['message'])

        # Handle callback query updates (button clicks)
        elif 'callback_query' in update:
            await self._handle_callback_query(update['callback_query'])

    async def _handle_message(self, message: dict):
        """
        Handle incoming message.

        Filters for private chats only and checks authorization.
        Routes to command handlers or registered message handlers.

        Args:
            message: Message object from Telegram API
        """
        chat = message.get('chat', {})
        user = message.get('from', {})
        user_id = user.get('id')
        chat_type = chat.get('type')

        # Only accept private chats (DMs)
        if chat_type != 'private':
            logger.debug(f"Ignoring non-private chat: {chat_type}")
            return

        # Check authorization
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            await self.send_message(
                user_id,
                "⛔ You are not authorized to use this bot."
            )
            return

        # Extract message text
        text = message.get('text', '')

        # Handle commands
        if text.startswith('/'):
            command = text.split()[0].split('@')[0]  # Remove @botname if present
            await self._route_command(command, message)
            return

        # Handle regular messages through registered handlers
        for handler in self.message_handlers:
            try:
                if await handler(message, self):
                    break  # Handler processed the message
            except Exception as e:
                logger.error(f"Error in message handler: {e}", exc_info=True)

    async def _handle_callback_query(self, query: dict):
        """
        Handle callback query (inline button click).

        Checks authorization and routes to registered callback handlers.
        Always calls answerCallbackQuery to acknowledge the button press.

        Args:
            query: CallbackQuery object from Telegram API
        """
        query_id = query.get('id')
        user = query.get('from', {})
        user_id = user.get('id')
        data = query.get('data', '')

        # Check authorization
        if not self._is_authorized(user_id):
            logger.warning(f"Unauthorized callback query from user {user_id}")
            await self.answer_callback_query(query_id, "⛔ Unauthorized")
            return

        # Route to appropriate callback handler
        try:
            # Try to find matching handler by prefix
            handled = False
            for prefix, handler in self.callback_handlers.items():
                if data.startswith(prefix):
                    await handler(query, self)
                    handled = True
                    break

            if not handled:
                logger.warning(f"No handler found for callback data: {data}")
                await self.answer_callback_query(query_id, "⚠️ Unknown action")
            else:
                await self.answer_callback_query(query_id, "✓")

        except Exception as e:
            logger.error(f"Error handling callback query: {e}", exc_info=True)
            await self.answer_callback_query(query_id, "❌ Error occurred")

    async def _route_command(self, command: str, message: dict):
        """
        Route command to registered handler.

        Args:
            command: Command string (e.g., '/start')
            message: Message object containing the command
        """
        handler = self.command_handlers.get(command)

        if handler:
            try:
                await handler(message, self)
            except Exception as e:
                logger.error(f"Error handling command {command}: {e}", exc_info=True)
                await self.send_message(
                    message['from']['id'],
                    f"❌ Error executing command: {str(e)}"
                )
        else:
            logger.warning(f"Unknown command: {command}")
            await self.send_message(
                message['from']['id'],
                f"❓ Unknown command: {command}\nUse /help to see available commands."
            )

    def _is_authorized(self, user_id: int) -> bool:
        """
        Check if user is authorized to use the bot.

        Args:
            user_id: Telegram user ID

        Returns:
            True if authorized, False otherwise
        """
        return user_id == self.moderator_id

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[dict] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[dict]:
        """
        Send a message to a chat.

        Args:
            chat_id: Target chat ID
            text: Message text (max 4096 characters)
            reply_markup: Optional inline keyboard
            disable_web_page_preview: Disable link previews

        Returns:
            API response with sent message, or None on error
        """
        if not self.session:
            logger.error("Cannot send message: session not initialized")
            return None

        data = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': disable_web_page_preview
        }

        if reply_markup:
            data['reply_markup'] = reply_markup

        try:
            async with self.session.post(
                f"{self.base_url}/sendMessage",
                json=data
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    logger.error(f"Failed to send message: {result.get('description')}")
                    return None

                return result.get('result')

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return None

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[dict] = None
    ) -> bool:
        """
        Edit an existing message.

        Args:
            chat_id: Chat ID containing the message
            message_id: Message ID to edit
            text: New message text
            reply_markup: Optional new inline keyboard

        Returns:
            True if successful, False otherwise
        """
        if not self.session:
            logger.error("Cannot edit message: session not initialized")
            return False

        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'disable_web_page_preview': True
        }

        if reply_markup:
            data['reply_markup'] = reply_markup

        try:
            async with self.session.post(
                f"{self.base_url}/editMessageText",
                json=data
            ) as response:
                result = await response.json()

                if not result.get('ok'):
                    error_desc = result.get('description', '')
                    # Ignore "message is not modified" errors
                    if 'message is not modified' not in error_desc.lower():
                        logger.error(f"Failed to edit message: {error_desc}")
                    return False

                return True

        except Exception as e:
            logger.error(f"Error editing message: {e}", exc_info=True)
            return False

    async def answer_callback_query(
        self,
        query_id: str,
        text: str = "",
        show_alert: bool = False
    ) -> bool:
        """
        Answer a callback query (acknowledge button press).

        Args:
            query_id: Callback query ID from update
            text: Optional notification text to show user
            show_alert: If True, show as modal alert; if False, show as toast

        Returns:
            True if successful, False otherwise
        """
        if not self.session:
            logger.error("Cannot answer callback query: session not initialized")
            return False

        data = {
            'callback_query_id': query_id,
            'text': text,
            'show_alert': show_alert
        }

        try:
            async with self.session.post(
                f"{self.base_url}/answerCallbackQuery",
                json=data
            ) as response:
                result = await response.json()
                return result.get('ok', False)

        except Exception as e:
            logger.error(f"Error answering callback query: {e}", exc_info=True)
            return False

    async def _set_bot_commands(self):
        """Set bot commands for UI menu."""
        commands = [
            {"command": "start", "description": "Start the bot"},
            {"command": "help", "description": "Show help message"},
            {"command": "setup_discord", "description": "Configure Discord connection"},
            {"command": "test_connection", "description": "Test Discord connection"},
            {"command": "discord_status", "description": "Check Discord status"},
            {"command": "status", "description": "Show system status"},
            {"command": "dnd", "description": "Toggle DND mode"},
            {"command": "allow_channel", "description": "Add channel to allowlist"},
            {"command": "unallow_channel", "description": "Remove channel from allowlist"},
            {"command": "settings", "description": "View/edit settings"},
        ]

        try:
            async with self.session.post(
                f"{self.base_url}/setMyCommands",
                json={"commands": commands}
            ) as response:
                result = await response.json()
                if result.get('ok'):
                    logger.info("Bot commands set successfully")
                else:
                    logger.warning(f"Failed to set bot commands: {result.get('description')}")
        except Exception as e:
            logger.error(f"Error setting bot commands: {e}", exc_info=True)

    # FSM State Management

    def get_user_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current state for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            State dictionary or None if no state exists
        """
        return self.user_states.get(user_id)

    def set_user_state(self, user_id: int, state: str, data: Optional[Dict[str, Any]] = None):
        """
        Set state for a user.

        Args:
            user_id: Telegram user ID
            state: State string (e.g., 'awaiting_reply_123')
            data: Optional additional data to store with state
        """
        self.user_states[user_id] = {
            'state': state,
            'data': data or {},
            'timestamp': datetime.utcnow()
        }
        logger.debug(f"Set state for user {user_id}: {state}")

    def clear_user_state(self, user_id: int):
        """
        Clear state for a user.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self.user_states:
            del self.user_states[user_id]
            logger.debug(f"Cleared state for user {user_id}")

    # Handler Registration

    def register_message_handler(self, handler: Callable):
        """
        Register a message handler.

        Args:
            handler: Async function(message, bot) -> bool
                     Returns True if message was handled
        """
        self.message_handlers.append(handler)
        logger.debug(f"Registered message handler: {handler.__name__}")

    def register_callback_handler(self, prefix: str, handler: Callable):
        """
        Register a callback query handler.

        Args:
            prefix: Callback data prefix to match (e.g., 'reply_')
            handler: Async function(query, bot)
        """
        self.callback_handlers[prefix] = handler
        logger.debug(f"Registered callback handler for prefix: {prefix}")

    def register_command_handler(self, command: str, handler: Callable):
        """
        Register a command handler.

        Args:
            command: Command string with / (e.g., '/start')
            handler: Async function(message, bot)
        """
        self.command_handlers[command] = handler
        logger.debug(f"Registered command handler: {command}")


def create_bot() -> TelegramBot:
    """
    Create and configure TelegramBot instance from config.

    Returns:
        Configured TelegramBot instance
    """
    config = get_config()

    bot = TelegramBot(
        token=config.telegram.bot_token,
        moderator_id=config.telegram.moderator_user_id
    )

    return bot
