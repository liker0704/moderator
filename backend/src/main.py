"""
Main application entry point.

This module initializes and coordinates all components of the moderator application:
- Discord gateway connection for monitoring messages
- Telegram bot for user interactions
- Database connections and encryption setup
- Background services and schedulers

The application runs multiple concurrent tasks to handle:
- Discord message monitoring and forwarding
- Telegram command processing
- Context window management
- DND (Do Not Disturb) scheduling
- User allowlist management
- Alert notifications
"""

import asyncio
import signal
import sys
from typing import Optional
from datetime import datetime

from config import get_config
from utils.logger import setup_logger, get_logger
from database.connection import init_db, close_db, session_scope
from database.encryption import init_encryption, get_encryption_service
from database.models import User, Settings, Task, Message, ChannelsAllowlist
from discord.gateway import DiscordGatewayManager
from telegram.bot import create_bot
from telegram.handlers import register_all_handlers
from telegram.cards import format_card, create_card_keyboard
from services.allowlist import is_channel_allowed
from services.alerts import send_info_alert, send_error_alert, send_critical_alert

# Initialize logger
logger = get_logger(__name__)


class ModeratorApplication:
    """
    Main application orchestrator that manages all components.

    Handles:
    - Component lifecycle (initialization, startup, shutdown)
    - Event routing between Discord and Telegram
    - Database operations
    - Error handling and recovery
    """

    def __init__(self):
        """Initialize the application."""
        self.config = get_config()
        self.db = None
        self.encryption_service = None
        self.telegram_bot = None
        self.discord_gateway = None
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Tasks for concurrent operations
        self._telegram_task: Optional[asyncio.Task] = None
        self._discord_task: Optional[asyncio.Task] = None

        logger.info("ModeratorApplication instance created")

    async def initialize(self):
        """
        Initialize all application components.

        This method:
        1. Sets up logging configuration
        2. Initializes database connection pool
        3. Runs database migrations if needed
        4. Initializes encryption service
        5. Creates component instances

        Raises:
            Exception: If initialization fails
        """
        try:
            logger.info("="*60)
            logger.info("Starting Moderator Application")
            logger.info("="*60)

            # 1. Setup logging with file output if configured
            log_file = f"/var/log/moderator/app_{datetime.now().strftime('%Y%m%d')}.log"
            setup_logger(
                "moderator",
                level=self.config.log_level,
                log_file=log_file if not self.config.is_development else None,
                json_format=not self.config.is_development
            )
            logger.info(f"Logging initialized at level: {self.config.log_level}")

            # 2. Initialize database connection pool
            logger.info("Initializing database connection...")
            self.db = init_db(
                database_url=self.config.database.connection_string,
                pool_size=5,
                max_overflow=10,
                echo=self.config.is_development
            )
            logger.info("Database connection established")

            # 3. Check database health and run migrations if needed
            if not self.db.health_check():
                raise RuntimeError("Database health check failed")

            # TODO: Run Alembic migrations here
            # For now, we'll create tables directly (development only)
            if self.config.is_development:
                logger.warning("Development mode: Creating tables directly")
                self.db.create_all_tables()
                logger.info("Database tables created/verified")

            # 4. Initialize encryption service
            logger.info("Initializing encryption service...")
            self.encryption_service = init_encryption(
                encryption_key=self.config.encryption_key.encode()
            )
            logger.info("Encryption service initialized")

            # 5. Initialize Telegram Bot
            logger.info("Initializing Telegram bot...")
            self.telegram_bot = create_bot()

            # Register all handlers (commands, callbacks, FSM)
            register_all_handlers(self.telegram_bot)
            logger.info("Telegram bot initialized with all handlers")

            # 6. Initialize Discord Gateway (if configured)
            if self.config.discord:
                logger.info("Initializing Discord Gateway...")
                self.discord_gateway = DiscordGatewayManager(
                    token=self.config.discord.user_token,
                    super_properties=self.config.discord.super_properties,
                    db_connection=self.db,
                    config=self.config
                )
                logger.info("Discord Gateway initialized")
            else:
                logger.warning("Discord configuration not found - Discord integration disabled")

            # 7. Send startup alert
            await send_info_alert(
                "Moderator application starting",
                context={
                    "version": "0.1.0-mvp",
                    "log_level": self.config.log_level,
                    "discord_enabled": "Yes" if self.config.discord else "No"
                }
            )

            logger.info("Application initialization complete")

        except Exception as e:
            logger.critical(f"Failed to initialize application: {e}", exc_info=True)
            await send_critical_alert(
                "Application initialization failed",
                context={"error": str(e)}
            )
            raise

    async def start(self):
        """
        Start all application components.

        This method:
        1. Starts the Telegram bot (long polling)
        2. Starts the Discord Gateway (if configured)
        3. Sets up signal handlers for graceful shutdown
        4. Waits for shutdown signal
        """
        try:
            self._running = True
            logger.info("Starting application components...")

            # Start Telegram bot in background task
            logger.info("Starting Telegram bot...")
            self._telegram_task = asyncio.create_task(
                self.telegram_bot.start(),
                name="telegram_bot"
            )

            # Start Discord Gateway in background task (if configured)
            if self.discord_gateway:
                logger.info("Starting Discord Gateway...")
                self._discord_task = asyncio.create_task(
                    self.discord_gateway.start(),
                    name="discord_gateway"
                )

            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

            logger.info("="*60)
            logger.info("Application started successfully!")
            logger.info("="*60)

            # Send startup success alert
            await send_info_alert(
                "Moderator application started successfully",
                context={
                    "telegram_bot": "Running",
                    "discord_gateway": "Running" if self.discord_gateway else "Disabled"
                }
            )

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.critical(f"Error starting application: {e}", exc_info=True)
            await send_critical_alert(
                "Application startup failed",
                context={"error": str(e)}
            )
            raise

    async def stop(self):
        """
        Stop all application components gracefully.

        This method:
        1. Stops accepting new events
        2. Waits for pending operations to complete
        3. Closes Discord Gateway connection
        4. Stops Telegram bot
        5. Closes database connections
        6. Sends shutdown alert
        """
        if not self._running:
            return

        logger.info("="*60)
        logger.info("Shutting down application...")
        logger.info("="*60)

        self._running = False

        try:
            # Stop Discord Gateway
            if self.discord_gateway:
                logger.info("Stopping Discord Gateway...")
                await self.discord_gateway.stop()

                if self._discord_task and not self._discord_task.done():
                    self._discord_task.cancel()
                    try:
                        await self._discord_task
                    except asyncio.CancelledError:
                        pass

                logger.info("Discord Gateway stopped")

            # Stop Telegram bot
            if self.telegram_bot:
                logger.info("Stopping Telegram bot...")
                await self.telegram_bot.stop()

                if self._telegram_task and not self._telegram_task.done():
                    self._telegram_task.cancel()
                    try:
                        await self._telegram_task
                    except asyncio.CancelledError:
                        pass

                logger.info("Telegram bot stopped")

            # Close database connections
            if self.db:
                logger.info("Closing database connections...")
                close_db()
                logger.info("Database connections closed")

            # Send shutdown alert
            await send_info_alert(
                "Moderator application shut down",
                context={"status": "Clean shutdown"}
            )

            logger.info("="*60)
            logger.info("Application shutdown complete")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            await send_error_alert(
                "Error during application shutdown",
                context={"error": str(e)}
            )

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            logger.info(f"Received signal: {signal_name}")

            # Trigger shutdown
            asyncio.create_task(self._trigger_shutdown())

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Signal handlers registered (SIGINT, SIGTERM)")

    async def _trigger_shutdown(self):
        """Trigger graceful shutdown."""
        logger.info("Triggering graceful shutdown...")
        self._shutdown_event.set()

    async def handle_discord_message(self, event_type: str, message_data: dict):
        """
        Handle Discord MESSAGE_CREATE events.

        Event Flow:
        1. Extract message details
        2. Check if channel is in allowlist
        3. Store message in database
        4. Create task for moderator
        5. Send card to Telegram

        Args:
            event_type: Discord event type (MESSAGE_CREATE, etc.)
            message_data: Message payload from Discord
        """
        if event_type != "MESSAGE_CREATE":
            return

        try:
            # Extract message details
            message_id = message_data.get("id")
            channel_id = message_data.get("channel_id")
            guild_id = message_data.get("guild_id")
            author = message_data.get("author", {})
            author_id = author.get("id")
            author_username = author.get("username", "Unknown")
            content = message_data.get("content", "")
            timestamp_str = message_data.get("timestamp")
            attachments = message_data.get("attachments", [])

            logger.info(
                f"Discord message received: {message_id} from {author_username} in channel {channel_id}",
                extra={
                    "platform": "discord",
                    "channel_id": channel_id,
                    "author_id": author_id
                }
            )

            # TODO: Check if channel is in allowlist
            # For now, we'll skip this check in development
            # In production, uncomment:
            # async with self.db.session_scope() as session:
            #     allowed = await is_channel_allowed(
            #         session,
            #         platform="discord",
            #         channel_id=channel_id,
            #         server_id=guild_id
            #     )
            #
            #     if not allowed:
            #         logger.debug(f"Channel {channel_id} not in allowlist, ignoring message")
            #         return

            # TODO: Store message in database
            # TODO: Create task for moderator
            # TODO: Send card to Telegram

            # Placeholder implementation
            logger.info(f"Message {message_id} would be processed here")
            logger.debug(f"Content: {content[:100]}{'...' if len(content) > 100 else ''}")

        except Exception as e:
            logger.error(f"Error handling Discord message: {e}", exc_info=True)
            await send_error_alert(
                "Error processing Discord message",
                context={
                    "message_id": message_data.get("id"),
                    "error": str(e)
                },
                throttle_key="discord_message_error"
            )

    async def send_card_to_telegram(self, task: dict):
        """
        Send a task card to Telegram.

        Args:
            task: Task dictionary with message data
        """
        try:
            # TODO: Implement card sending logic
            # This would:
            # 1. Load context messages from database
            # 2. Format card using telegram.cards
            # 3. Create keyboard with action buttons
            # 4. Send to moderator via Telegram bot
            # 5. Store telegram message ID in task

            logger.info(f"Would send card for task {task.get('id')} to Telegram")

        except Exception as e:
            logger.error(f"Error sending card to Telegram: {e}", exc_info=True)
            await send_error_alert(
                "Error sending card to Telegram",
                context={
                    "task_id": task.get("id"),
                    "error": str(e)
                },
                throttle_key="telegram_card_error"
            )


async def main():
    """
    Main entry point for the application.

    This function:
    1. Creates ModeratorApplication instance
    2. Initializes all components
    3. Starts the application
    4. Handles errors and ensures cleanup
    """
    app = None

    try:
        # Create application instance
        app = ModeratorApplication()

        # Initialize all components
        await app.initialize()

        # Start the application (blocks until shutdown)
        await app.start()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")

    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)

        # Try to send critical alert
        try:
            await send_critical_alert(
                "Fatal application error",
                context={"error": str(e), "type": type(e).__name__}
            )
        except:
            pass  # Alert sending failed, but we're already in critical state

        sys.exit(1)

    finally:
        # Ensure cleanup happens
        if app:
            try:
                await app.stop()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}", exc_info=True)


def run():
    """
    Convenience function to run the application.

    This can be called from command line or other entry points.
    """
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    run()
