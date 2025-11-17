"""
Discord Gateway connection and event handling.

This module manages the Discord Gateway WebSocket connection:
- Establishes and maintains persistent WebSocket connection to Discord Gateway
- Handles Discord authentication and heartbeat protocol
- Listens for MESSAGE_CREATE events from configured channels
- Processes incoming messages and filters based on configuration
- Implements reconnection logic with exponential backoff
- Handles rate limiting and connection errors gracefully

The gateway monitors specified Discord channels and triggers message processing
when new messages arrive from non-allowlisted users during active hours.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any, Callable
import websockets
from websockets.client import WebSocketClientProtocol

from .utils import parse_super_properties, validate_discord_token, format_discord_timestamp

# Set up logger
logger = logging.getLogger(__name__)


class DiscordGatewayClient:
    """
    Discord Gateway WebSocket client for receiving Discord events.

    This client implements the Discord Gateway protocol for user accounts,
    including authentication, heartbeat, event handling, and reconnection logic.

    Attributes:
        token (str): Discord user token for authentication
        super_properties (dict): Discord super properties for identify payload
        session_id (Optional[str]): Current session ID for resume
        sequence (Optional[int]): Last received sequence number
        heartbeat_interval (Optional[int]): Heartbeat interval in milliseconds
        ws (Optional[WebSocketClientProtocol]): WebSocket connection
        heartbeat_task (Optional[asyncio.Task]): Background heartbeat task
        event_handlers (Dict[str, Callable]): Event type to handler mapping
        is_connected (bool): Connection status flag
        reconnect_attempts (int): Number of reconnection attempts
        max_reconnect_attempts (int): Maximum reconnection attempts
    """

    GATEWAY_URL = "wss://gateway.discord.gg/?v=9&encoding=json"

    # Opcodes
    OP_DISPATCH = 0
    OP_HEARTBEAT = 1
    OP_IDENTIFY = 2
    OP_RESUME = 6
    OP_RECONNECT = 7
    OP_INVALID_SESSION = 9
    OP_HELLO = 10
    OP_HEARTBEAT_ACK = 11

    def __init__(
        self,
        token: str,
        super_properties: Optional[Dict[str, Any]] = None,
        event_handler: Optional[Callable] = None
    ):
        """
        Initialize Discord Gateway client.

        Args:
            token: Discord user token
            super_properties: Discord super properties (will use defaults if not provided)
            event_handler: Async callback for handling Discord events
        """
        self.token = validate_discord_token(token)
        self.super_properties = super_properties or parse_super_properties()

        # Connection state
        self.session_id: Optional[str] = None
        self.sequence: Optional[int] = None
        self.heartbeat_interval: Optional[int] = None
        self.ws: Optional[WebSocketClientProtocol] = None
        self.heartbeat_task: Optional[asyncio.Task] = None

        # Event handling
        self.event_handler = event_handler
        self.is_connected = False

        # Reconnection state
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10

        # Heartbeat ACK tracking
        self.last_heartbeat_sent: Optional[float] = None
        self.last_heartbeat_ack: Optional[float] = None
        self.heartbeat_ack_received = True

        logger.info("Discord Gateway client initialized")

    async def connect(self) -> None:
        """
        Connect to Discord Gateway and start event loop.

        This is the main entry point that establishes connection,
        handles authentication, and processes incoming events.
        """
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                async with websockets.connect(
                    self.GATEWAY_URL,
                    max_size=2**24,  # 16MB max message size
                    ping_interval=None,  # We handle heartbeat manually
                ) as ws:
                    self.ws = ws
                    logger.info("Connected to Discord Gateway")

                    await self._handle_connection()

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Connection closed: {e}")
                await self._handle_reconnect()

            except Exception as e:
                logger.error(f"Connection error: {e}", exc_info=True)
                await self._handle_reconnect()

        logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
        raise ConnectionError("Failed to maintain Discord Gateway connection")

    async def _handle_connection(self) -> None:
        """Handle the WebSocket connection lifecycle."""
        try:
            # Main event loop
            async for message in self.ws:
                try:
                    await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            raise

    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming Gateway message.

        Args:
            message: Raw JSON message from Gateway
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
            return

        op = data.get("op")
        d = data.get("d")
        t = data.get("t")
        s = data.get("s")

        # Update sequence number
        if s is not None:
            self.sequence = s

        # Handle different opcodes
        if op == self.OP_HELLO:
            await self._handle_hello(d)

        elif op == self.OP_HEARTBEAT_ACK:
            await self._handle_heartbeat_ack()

        elif op == self.OP_DISPATCH:
            await self._handle_dispatch(t, d)

        elif op == self.OP_RECONNECT:
            logger.info("Received reconnect request from Discord")
            await self._handle_reconnect()

        elif op == self.OP_INVALID_SESSION:
            await self._handle_invalid_session(d)

        else:
            logger.debug(f"Unhandled opcode: {op}")

    async def _handle_hello(self, data: Dict[str, Any]) -> None:
        """
        Handle Hello (Op 10) - receive heartbeat interval and authenticate.

        Args:
            data: Hello payload containing heartbeat_interval
        """
        self.heartbeat_interval = data.get("heartbeat_interval")
        logger.info(f"Received Hello with heartbeat interval: {self.heartbeat_interval}ms")

        # Start heartbeat
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Send Identify or Resume
        if self.session_id and self.sequence is not None:
            logger.info("Attempting to resume session")
            await self._send_resume()
        else:
            logger.info("Sending identify")
            await self._send_identify()

    async def _handle_heartbeat_ack(self) -> None:
        """Handle Heartbeat ACK (Op 11)."""
        self.last_heartbeat_ack = time.time()
        self.heartbeat_ack_received = True

        if self.last_heartbeat_sent:
            latency = (self.last_heartbeat_ack - self.last_heartbeat_sent) * 1000
            logger.debug(f"Heartbeat ACK received (latency: {latency:.2f}ms)")

    async def _handle_dispatch(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Handle Dispatch (Op 0) - process Discord events.

        Args:
            event_type: Event type (e.g., READY, MESSAGE_CREATE)
            data: Event payload
        """
        logger.debug(f"Received event: {event_type}")

        if event_type == "READY":
            await self._handle_ready(data)

        elif event_type == "MESSAGE_CREATE":
            await self._handle_message_create(data)

        # Call custom event handler if provided
        if self.event_handler:
            try:
                await self.event_handler(event_type, data)
            except Exception as e:
                logger.error(f"Error in custom event handler: {e}", exc_info=True)

    async def _handle_ready(self, data: Dict[str, Any]) -> None:
        """
        Handle READY event - save session information.

        Args:
            data: READY event payload
        """
        self.session_id = data.get("session_id")
        user = data.get("user", {})
        username = user.get("username", "Unknown")
        user_id = user.get("id", "Unknown")

        self.is_connected = True
        self.reconnect_attempts = 0  # Reset on successful connection

        logger.info(f"Gateway ready! Logged in as {username} ({user_id})")
        logger.info(f"Session ID: {self.session_id}")

    async def _handle_message_create(self, data: Dict[str, Any]) -> None:
        """
        Handle MESSAGE_CREATE event - process incoming Discord messages.

        Args:
            data: MESSAGE_CREATE event payload
        """
        message_id = data.get("id")
        channel_id = data.get("channel_id")
        guild_id = data.get("guild_id")
        author = data.get("author", {})
        author_id = author.get("id")
        author_username = author.get("username")
        content = data.get("content", "")
        timestamp = data.get("timestamp")
        attachments = data.get("attachments", [])

        logger.info(
            f"Message received: {message_id} from {author_username} ({author_id}) "
            f"in channel {channel_id} (guild: {guild_id})"
        )
        logger.debug(f"Content: {content[:100]}..." if len(content) > 100 else f"Content: {content}")

        # This will be handled by the external event handler
        # which should check allowlist, store to DB, and create tasks

    async def _handle_invalid_session(self, resumable: bool) -> None:
        """
        Handle Invalid Session (Op 9).

        Args:
            resumable: Whether the session can be resumed
        """
        if resumable:
            logger.info("Invalid session (resumable), waiting before resume")
            await asyncio.sleep(5)
            await self._send_resume()
        else:
            logger.warning("Invalid session (not resumable), clearing session and re-identifying")
            self.session_id = None
            self.sequence = None
            await asyncio.sleep(5)
            await self._send_identify()

    async def _send_identify(self) -> None:
        """Send Identify (Op 2) to authenticate with Discord."""
        # Build properties from super_properties
        properties = {
            "$os": self.super_properties.get("os", "linux"),
            "$browser": self.super_properties.get("browser", "Chrome"),
            "$device": self.super_properties.get("device", ""),
        }

        payload = {
            "op": self.OP_IDENTIFY,
            "d": {
                "token": self.token,
                "properties": properties,
                "compress": False,
                "presence": {
                    "status": "online",
                    "since": None,
                    "activities": [],
                    "afk": False
                },
                "intents": 32767  # All intents (including MESSAGE_CONTENT)
            }
        }

        await self._send_payload(payload)
        logger.info("Sent Identify payload")

    async def _send_resume(self) -> None:
        """Send Resume (Op 6) to resume a session after disconnect."""
        if not self.session_id or self.sequence is None:
            logger.warning("Cannot resume: missing session_id or sequence")
            await self._send_identify()
            return

        payload = {
            "op": self.OP_RESUME,
            "d": {
                "token": self.token,
                "session_id": self.session_id,
                "seq": self.sequence
            }
        }

        await self._send_payload(payload)
        logger.info(f"Sent Resume payload (seq: {self.sequence})")

    async def _send_heartbeat(self) -> None:
        """Send Heartbeat (Op 1) to keep connection alive."""
        payload = {
            "op": self.OP_HEARTBEAT,
            "d": self.sequence
        }

        self.last_heartbeat_sent = time.time()
        self.heartbeat_ack_received = False

        await self._send_payload(payload)
        logger.debug(f"Sent Heartbeat (seq: {self.sequence})")

    async def _heartbeat_loop(self) -> None:
        """Background task that sends periodic heartbeats."""
        if not self.heartbeat_interval:
            logger.error("Cannot start heartbeat: interval not set")
            return

        # Wait random interval before first heartbeat (Discord recommendation)
        import random
        initial_delay = random.random() * self.heartbeat_interval / 1000
        await asyncio.sleep(initial_delay)

        while True:
            try:
                # Check if we received ACK for last heartbeat
                if not self.heartbeat_ack_received:
                    logger.warning("Heartbeat ACK not received, connection may be dead")
                    # Don't reconnect here, let the main loop handle it

                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval / 1000)

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _send_payload(self, payload: Dict[str, Any]) -> None:
        """
        Send a payload to the Gateway.

        Args:
            payload: Payload dictionary to send
        """
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        await self.ws.send(json.dumps(payload))

    async def _handle_reconnect(self) -> None:
        """Handle reconnection with exponential backoff."""
        self.is_connected = False

        # Cancel heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

        # Close WebSocket if open
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

        # Calculate backoff delay
        self.reconnect_attempts += 1
        delay = min(2 ** self.reconnect_attempts, 60)  # Max 60 seconds

        logger.info(
            f"Reconnecting in {delay} seconds "
            f"(attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
        )

        await asyncio.sleep(delay)

    async def close(self) -> None:
        """Gracefully close the Gateway connection."""
        logger.info("Closing Discord Gateway connection")

        self.is_connected = False

        # Cancel heartbeat
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        if self.ws:
            await self.ws.close()

        logger.info("Discord Gateway connection closed")


class DiscordGatewayManager:
    """
    Higher-level manager for Discord Gateway client with database integration.

    This class wraps DiscordGatewayClient and integrates it with the
    application's database, configuration, and event processing logic.
    """

    def __init__(
        self,
        token: str,
        super_properties: Optional[Dict[str, Any]] = None,
        db_connection=None,
        config=None
    ):
        """
        Initialize Gateway manager.

        Args:
            token: Discord user token
            super_properties: Discord super properties
            db_connection: Database connection (for storing messages/tasks)
            config: Application configuration
        """
        self.token = token
        self.super_properties = super_properties
        self.db_connection = db_connection
        self.config = config

        self.client: Optional[DiscordGatewayClient] = None
        self._running = False

    async def start(self) -> None:
        """Start the Gateway client and event processing."""
        if self._running:
            logger.warning("Gateway manager already running")
            return

        self._running = True

        # Create client with event handler
        self.client = DiscordGatewayClient(
            token=self.token,
            super_properties=self.super_properties,
            event_handler=self._handle_discord_event
        )

        logger.info("Starting Discord Gateway manager")

        try:
            await self.client.connect()
        except Exception as e:
            logger.error(f"Gateway manager error: {e}", exc_info=True)
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop the Gateway client."""
        if not self._running:
            return

        self._running = False

        if self.client:
            await self.client.close()

        logger.info("Discord Gateway manager stopped")

    async def _handle_discord_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Handle Discord events from the Gateway.

        This is the integration point between the Gateway client and the
        application logic (database storage, task creation, etc.).

        Args:
            event_type: Type of Discord event
            data: Event payload
        """
        if event_type == "MESSAGE_CREATE":
            await self._process_message(data)

        # Handle other events as needed
        # elif event_type == "MESSAGE_UPDATE":
        #     await self._process_message_update(data)
        # elif event_type == "MESSAGE_DELETE":
        #     await self._process_message_delete(data)

    async def _process_message(self, message_data: Dict[str, Any]) -> None:
        """
        Process MESSAGE_CREATE event.

        This should:
        1. Check if channel is in allowlist
        2. Check if author is in channel allowlist (skip if yes)
        3. Store message in database
        4. Create task for moderator

        Args:
            message_data: MESSAGE_CREATE payload
        """
        # Extract message details
        message_id = message_data.get("id")
        channel_id = message_data.get("channel_id")
        guild_id = message_data.get("guild_id")
        author = message_data.get("author", {})
        author_id = author.get("id")
        author_username = author.get("username")
        content = message_data.get("content", "")
        timestamp = message_data.get("timestamp")
        attachments = message_data.get("attachments", [])

        # TODO: Implement actual database storage and task creation
        # This would require:
        # 1. Check channels_allowlist table
        # 2. Check user allowlist for this channel
        # 3. Store in messages table
        # 4. Store attachments in attachments table
        # 5. Create task in tasks table
        # 6. Send notification to Telegram

        logger.info(
            f"Processing message {message_id} from {author_username} "
            f"in channel {channel_id}"
        )

        # Placeholder for database integration
        # if self.db_connection:
        #     await self._store_message_to_db(message_data)
        #     await self._create_moderator_task(message_data)
