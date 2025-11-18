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
import json
from typing import Optional
from datetime import datetime

from config import get_config
from utils.logger import setup_logger, get_logger
from database.connection import init_db, close_db, session_scope, init_asyncpg_pool, get_asyncpg_pool, close_asyncpg_pool
from database.encryption import init_encryption, get_encryption_service
from database.models import User, Settings, Task, Message, ChannelsAllowlist
from database.dao import MessageDAO, AttachmentDAO, AsyncTaskDAO, AsyncUserDAO
from discord.gateway import DiscordGatewayManager
from telegram.bot import create_bot
from telegram.handlers import register_all_handlers
from telegram.cards import format_card, create_card_keyboard
from services.allowlist import is_channel_allowed
from services.context import get_context_by_channel
from services.dnd import is_dnd_active
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
        self.db_pool = None
        self.encryption_service = None
        self.telegram_bot = None
        self.discord_gateway = None
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Tasks for concurrent operations
        self._telegram_task: Optional[asyncio.Task] = None
        self._discord_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None

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

            # 2. Initialize database connection pool (SQLAlchemy)
            logger.info("Initializing database connection...")
            self.db = init_db(
                database_url=self.config.database.connection_string,
                pool_size=5,
                max_overflow=10,
                echo=self.config.is_development
            )
            logger.info("Database connection established")

            # 2b. Initialize asyncpg connection pool for async operations
            logger.info("Initializing asyncpg connection pool...")
            self.db_pool = await init_asyncpg_pool(
                database_url=self.config.database.connection_string,
                min_size=5,
                max_size=15
            )
            logger.info("Asyncpg connection pool established")

            # 2c. Initialize Redis client (if configured)
            if self.config.redis:
                logger.info("Initializing Redis client...")
                from job_queue.client import init_redis_client
                await init_redis_client()
                logger.info("Redis client initialized")
            else:
                logger.warning("Redis configuration not found - Redis integration disabled")

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

            # Attach database connection to bot
            self.telegram_bot.db = self.db

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
                    config=self.config,
                    on_new_task_callback=self.send_card_to_telegram
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
                    self._run_discord_gateway(),
                    name="discord_gateway"
                )

            # Start database health monitoring
            logger.info("Starting database health monitoring...")
            self._monitoring_task = asyncio.create_task(
                self.monitor_database_health(),
                name="database_health_monitor"
            )

            # Start Health Check API server
            logger.info("Starting Health Check API server...")
            from api.server import run_health_check_server
            import os

            health_check_port = int(os.getenv('HEALTH_CHECK_PORT', '8000'))
            self._health_check_task = asyncio.create_task(
                run_health_check_server(
                    discord_gateway=self.discord_gateway,
                    port=health_check_port
                ),
                name="health_check_api"
            )
            logger.info(f"Health Check API server started on port {health_check_port}")

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

            # Stop monitoring task
            if self._monitoring_task and not self._monitoring_task.done():
                logger.info("Stopping database health monitoring...")
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                logger.info("Database health monitoring stopped")

            # Stop Health Check API server
            if self._health_check_task and not self._health_check_task.done():
                logger.info("Stopping Health Check API server...")
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
                logger.info("Health Check API server stopped")

            # Close database connections
            if self.db_pool:
                logger.info("Closing asyncpg connection pool...")
                await close_asyncpg_pool()
                logger.info("Asyncpg pool closed")

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
        """Handle incoming Discord MESSAGE_CREATE event and save to database."""
        if event_type != "MESSAGE_CREATE":
            return

        try:
            # Extract data
            channel_id = message_data.get('channel_id')
            guild_id = message_data.get('guild_id')
            thread_id = message_data.get('thread_id')  # For threads
            author = message_data.get('author', {})
            content = message_data.get('content', '')
            attachments = message_data.get('attachments', [])
            timestamp = message_data.get('timestamp')
            ext_message_id = message_data.get('id')

            logger.info(
                f"Discord message received: {ext_message_id} from {author.get('username')} in channel {channel_id}",
                extra={
                    "platform": "discord",
                    "channel_id": channel_id,
                    "author_id": author.get('id')
                }
            )

            # 1. Check allowlist
            async with self.db_pool.acquire() as conn:
                from services.allowlist import is_channel_allowed
                allowed = await is_channel_allowed(
                    conn,
                    platform='discord',
                    channel_id=channel_id,
                    server_id=guild_id,
                    thread_id=thread_id
                )

                if not allowed:
                    logger.debug(f"Message from non-allowlisted channel {channel_id}")
                    return

                # 2. Save message to database
                from database.dao import MessageDAO, AttachmentDAO
                message_id = await MessageDAO.create_message(
                    conn,
                    platform='discord',
                    ext_message_id=ext_message_id,
                    server_id=guild_id,
                    channel_id=channel_id,
                    thread_id=thread_id,
                    author_id=author.get('id'),
                    author_name=author.get('username'),
                    content=content,
                    has_image=len(attachments) > 0,
                    platform_created_at=timestamp
                )

                # 3. Save attachments
                for attachment in attachments:
                    content_type = attachment.get('content_type', '')
                    kind = 'image' if content_type.startswith('image') else 'file'

                    attachment_id = await AttachmentDAO.create_attachment(
                        conn,
                        message_id=message_id,
                        kind=kind,
                        ref=attachment.get('url'),
                        meta=json.dumps({
                            'filename': attachment.get('filename'),
                            'size': attachment.get('size'),
                            'width': attachment.get('width'),
                            'height': attachment.get('height')
                        })
                    )

                    logger.debug(
                        f"Saved attachment {attachment.get('id')} for message {message_id} "
                        f"(kind: {kind}, filename: {attachment.get('filename')})"
                    )

                # 4. Create task for moderator
                from database.dao import AsyncTaskDAO, AsyncUserDAO
                # Get moderator user_id (from config or settings)
                moderator_tg_id = self.config.telegram.moderator_user_id
                user = await AsyncUserDAO.get_user_by_tg_id(conn, moderator_tg_id)
                if not user:
                    # Create user if doesn't exist
                    user_id = await AsyncUserDAO.create_user(conn, moderator_tg_id)
                else:
                    user_id = user['id']

                # Check DND mode
                from services.dnd import is_dnd_active
                if await is_dnd_active(conn, user_id):
                    logger.info(f"DND active, skipping card for message {ext_message_id}")
                    # Create task but mark as muted
                    task_id = await AsyncTaskDAO.create_task(conn, message_id, user_id)
                    await AsyncTaskDAO.update_task_status(conn, task_id, 'muted')
                    return

                task_id = await AsyncTaskDAO.create_task(conn, message_id, user_id)

                # 5. Send card to Telegram
                await self.send_card_to_telegram(task_id, message_id)

            logger.info(f"Processed Discord message {ext_message_id}, created task {task_id}")

        except Exception as e:
            logger.error(f"Error handling Discord message: {e}", exc_info=True)

            # Alert on repeated errors
            from services.alerts import send_alert
            await send_alert(
                self.telegram_bot,
                f"Failed to process Discord message: {str(e)}",
                alert_type="ERROR",
                throttle_key="discord_message_error",
                throttle_seconds=900  # 15 minutes
            )

    async def _run_discord_gateway(self):
        """Run Discord Gateway with error handling and alerting."""
        try:
            if self.discord_gateway:
                await self.discord_gateway.start()
        except Exception as e:
            logger.error(f"Discord gateway error: {e}", exc_info=True)

            # Send alert
            from services.alerts import alert_discord_error
            await alert_discord_error(self.telegram_bot, str(e))

            # Attempt reconnection after delay
            await asyncio.sleep(30)
            if self._running:
                logger.info("Attempting to restart Discord Gateway...")
                self._discord_task = asyncio.create_task(
                    self._run_discord_gateway(),
                    name="discord_gateway"
                )

    async def monitor_database_health(self):
        """Monitor database health and alert on failures."""
        from database.connection import check_database_health
        from services.alerts import alert_database_error

        while self._running:
            await asyncio.sleep(300)  # Check every 5 minutes

            if not await check_database_health():
                await alert_database_error(
                    self.telegram_bot,
                    "Database connection unhealthy"
                )

    async def send_card_to_telegram(self, task_id: int, message_id: int):
        """
        Send a message card to Telegram when a new task is created.

        Args:
            task_id: ID of the newly created task
            message_id: ID of the source Discord message
        """
        try:
            # Get async database connection from pool
            conn = await get_asyncpg_pool().acquire()

            try:
                # 1. Get message and attachments from database
                message_record = await MessageDAO.get_message_by_id(conn, message_id)
                if not message_record:
                    logger.error(f"Message {message_id} not found for task {task_id}")
                    return

                # Convert asyncpg.Record to dict
                message = dict(message_record)

                # Load attachments
                attachments = await AttachmentDAO.get_attachments_for_message(conn, message_id)
                message['attachments'] = attachments

                # 2. Load context messages (10 messages before current one)
                context_messages = await get_context_by_channel(
                    conn,
                    platform=message['platform'],
                    channel_id=message['channel_id'],
                    server_id=message.get('server_id'),
                    thread_id=message.get('thread_id'),
                    before_message_id=message_id,
                    limit=10
                )

                # Convert context messages (Message dataclass instances) to dicts
                context_messages = [vars(msg) for msg in context_messages]

                # 3. Format card
                card_text = format_card(message, context_messages)

                # 4. Create keyboard
                keyboard = create_card_keyboard(task_id, show_more=True)

                # 5. Send to Telegram
                result = await self.telegram_bot.send_message(
                    chat_id=self.config.telegram.moderator_user_id,
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )

                if result.get('ok'):
                    # Save Telegram message ID in task
                    tg_message_id = result['result']['message_id']
                    await AsyncTaskDAO.update_task_card_id(conn, task_id, tg_message_id)
                    logger.info(f"Sent card for task {task_id}, TG message {tg_message_id}")
                else:
                    logger.error(f"Failed to send card for task {task_id}: {result.get('description')}")
                    await AsyncTaskDAO.update_task_status(conn, task_id, 'error', f"Failed to send card: {result.get('description')}")

            finally:
                # Always release the connection back to the pool
                await get_asyncpg_pool().release(conn)

        except Exception as e:
            logger.error(f"Error sending card to Telegram: {e}", exc_info=True)
            # Send error alert but don't crash the application
            await send_error_alert(
                "Error sending card to Telegram",
                context={
                    "task_id": task_id,
                    "message_id": message_id,
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
