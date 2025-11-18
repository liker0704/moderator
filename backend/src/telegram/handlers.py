"""
Telegram command and callback handlers.

This module implements all Telegram bot interaction handlers:

Commands:
- /start: Welcome message and bot introduction
- /help: Display available commands and usage instructions
- /setup_discord: FSM dialog for Discord token input
- /test_connection: Test Discord connection
- /discord_status: Show Discord connection status
- /status: Show current bot status and configurations
- /dnd [on|off]: Toggle or configure Do Not Disturb mode
- /allow_channel {server_id} {channel_id}: Add channel to allowlist
- /unallow_channel {channel_id}: Remove channel from allowlist
- /settings: View and edit settings

Callback handlers:
- reply_{task_id}: Start reply flow for a task
- more_{task_id}: Load more context for a task
- confirm_{reply_id}: Confirm and send a reply
- retry_{task_id}: Retry failed posting
- toggle_dnd: Toggle DND mode

Each handler processes user input, interacts with services layer,
and provides appropriate responses and keyboard layouts.
"""

from typing import TYPE_CHECKING

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .bot import TelegramBot

logger = get_logger(__name__)


# =============================================================================
# Command Handlers
# =============================================================================

async def cmd_start(message: dict, bot: 'TelegramBot'):
    """
    Handle /start command.

    Sends welcome message with bot introduction and creates user in database if needed.
    """
    user = message['from']
    user_id = user['id']
    first_name = user.get('first_name', 'User')
    username = user.get('username')

    # Ensure user exists in database
    with bot.db.session_scope() as session:
        from ..database.dao import UserDAO

        existing_user = UserDAO.get_user_by_tg_id(session, user_id)
        if not existing_user:
            UserDAO.create_user(session, user_id, username)
            logger.info(f"Created new user in database: {user_id}")

    welcome_text = f"""👋 Welcome to Moderator Console, {first_name}!

This bot helps you moderate Discord and Telegram messages from a unified interface.

📌 Quick Start:
1. Use /setup_discord to configure Discord connection
2. Use /allow_channel to add channels to monitor
3. Receive message cards and respond directly

💡 Use /help to see all available commands."""

    await bot.send_message(user_id, welcome_text)
    logger.info(f"Sent welcome message to user {user_id}")


async def cmd_help(message: dict, bot: 'TelegramBot'):
    """
    Handle /help command.

    Displays available commands and usage instructions.
    """
    user_id = message['from']['id']

    help_text = """📖 Available Commands:

🔧 Setup & Configuration:
/setup_discord - Configure Discord connection (token input)
/test_connection - Test Discord connection
/discord_status - Check Discord connection status
/allow_channel <server_id> <channel_id> - Add channel to monitoring
/unallow_channel <channel_id> - Remove channel from monitoring

⚙️ Settings & Status:
/status - Show system status (DND, channels, etc.)
/dnd [on|off] - Toggle or configure DND mode
/settings - View/edit all settings

ℹ️ General:
/help - Show this help message
/start - Welcome message

📝 Working with Message Cards:
When you receive a message card:
• Click "Ответить" to reply
• Click "Показать больше" to load more context
• Click "DND" to toggle Do Not Disturb mode
• After typing reply, confirm before sending

🔐 Security:
Only authorized users can access this bot."""

    await bot.send_message(user_id, help_text)
    logger.info(f"Sent help message to user {user_id}")


async def cmd_setup_discord(message: dict, bot: 'TelegramBot'):
    """
    Handle /setup_discord command.

    Starts FSM dialog for Discord token input.
    """
    user_id = message['from']['id']

    # Set FSM state to awaiting Discord token
    bot.set_user_state(user_id, 'awaiting_discord_token')

    setup_text = """🔐 Discord Setup

Please send your Discord User Token.

⚠️ Security Warning:
• User tokens are against Discord ToS
• Use at your own risk
• Token will be encrypted in database
• Never share your token with others

📝 How to get your token:
1. Open Discord in browser (desktop app won't work)
2. Press F12 to open DevTools
3. Go to Console tab
4. Type: (webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
5. Copy the token (including quotes)

Type /cancel to abort setup."""

    await bot.send_message(user_id, setup_text)
    logger.info(f"Started Discord setup for user {user_id}")


async def cmd_test_connection(message: dict, bot: 'TelegramBot'):
    """
    Handle /test_connection command.

    Tests Discord connection and reports status.
    """
    user_id = message['from']['id']

    with bot.db.session_scope() as session:
        from ..database.dao import UserDAO, DiscordDAO

        user = UserDAO.get_user_by_tg_id(session, user_id)
        if not user:
            await bot.send_message(user_id, "❌ User not found. Use /start first.")
            return

        discord_conn = DiscordDAO.get_discord_connection(session, user['id'])
        if not discord_conn:
            await bot.send_message(user_id,
                "❌ No Discord connection configured.\n"
                "Use /setup_discord to configure."
            )
            return

        # Check status
        status = discord_conn.get('status', 'unknown')
        if status == 'connected':
            await bot.send_message(user_id,
                f"✅ Discord connection active\n"
                f"Session: {discord_conn.get('session_id', 'N/A')[:16] if discord_conn.get('session_id') else 'N/A'}...\n"
                f"Last connected: {discord_conn.get('last_connected_at', 'N/A')}"
            )
        else:
            await bot.send_message(user_id,
                f"❌ Discord not connected\n"
                f"Status: {status}\n"
                f"Error: {discord_conn.get('error_message', 'None')}"
            )

    logger.info(f"Connection test requested by user {user_id}")


async def cmd_discord_status(message: dict, bot: 'TelegramBot'):
    """
    Handle /discord_status command.

    Shows Discord connection status and statistics.
    """
    user_id = message['from']['id']

    # TODO: Get actual Discord status from gateway service
    status_text = """📊 Discord Connection Status

Connection: ❌ Not Connected
Token: Not configured
Monitored Servers: 0
Monitored Channels: 0

Use /setup_discord to configure connection."""

    await bot.send_message(user_id, status_text)
    logger.info(f"Discord status requested by user {user_id}")


async def cmd_status(message: dict, bot: 'TelegramBot'):
    """
    Handle /status command.

    Shows overall system status including DND, channels, and statistics.
    """
    user_id = message['from']['id']

    with bot.db.session_scope() as session:
        from ..database.dao import UserDAO, DiscordDAO, TaskDAO, AllowlistDAO

        user = UserDAO.get_user_by_tg_id(session, user_id)
        if not user:
            await bot.send_message(user_id, "❌ User not found")
            return

        # Get Discord status
        discord_conn = DiscordDAO.get_discord_connection(session, user['id'])
        discord_status = "✅ Connected" if discord_conn and discord_conn['status'] == 'connected' else "❌ Disconnected"

        # Get open tasks
        open_tasks = TaskDAO.get_open_tasks(session, user['id'])
        open_count = len(open_tasks)

        # Get DND status
        settings = UserDAO.get_user_settings(session, user['id'])
        dnd_status = "🔕 ON" if settings and settings.get('dnd_enabled') else "🔔 OFF"

        # Get allowlist count
        channels = AllowlistDAO.get_all_channels(session, platform='discord')
        channel_count = len(channels)

        status_text = (
            f"📊 System Status\n\n"
            f"Discord: {discord_status}\n"
            f"Open Tasks: {open_count}\n"
            f"DND Mode: {dnd_status}\n"
            f"Allowed Channels: {channel_count}\n"
            f"Database: ✅ Connected"
        )

        await bot.send_message(user_id, status_text)

    logger.info(f"System status requested by user {user_id}")


async def cmd_dnd(message: dict, bot: 'TelegramBot'):
    """
    Handle /dnd command.

    Toggle or configure Do Not Disturb mode.
    Supports: /dnd, /dnd on, /dnd off
    """
    user_id = message['from']['id']
    text = message.get('text', '')
    parts = text.split()

    # TODO: Integrate with actual DND service
    if len(parts) == 1:
        # Just /dnd - show current status
        dnd_text = """⏸️ Do Not Disturb Settings

Current Status: Disabled

Commands:
• /dnd on - Enable DND mode
• /dnd off - Disable DND mode

When DND is enabled, you won't receive message notifications. Messages will be queued for later review."""

        await bot.send_message(user_id, dnd_text)

    elif len(parts) == 2:
        mode = parts[1].lower()

        if mode == 'on':
            # Enable DND
            with bot.db.session_scope() as session:
                from ..database.dao import UserDAO
                user = UserDAO.get_user_by_tg_id(session, user_id)
                if user:
                    UserDAO.update_dnd_settings(session, user['id'], dnd_enabled=True)
                    await bot.send_message(user_id, "🔕 DND mode: ON\nYou will not receive message cards.")
            logger.info(f"DND enabled by user {user_id}")

        elif mode == 'off':
            # Disable DND
            with bot.db.session_scope() as session:
                from ..database.dao import UserDAO
                user = UserDAO.get_user_by_tg_id(session, user_id)
                if user:
                    UserDAO.update_dnd_settings(session, user['id'], dnd_enabled=False)
                    await bot.send_message(user_id, "🔔 DND mode: OFF\nYou will receive message cards.")
            logger.info(f"DND disabled by user {user_id}")

        else:
            await bot.send_message(user_id, "❌ Invalid option. Use: /dnd on or /dnd off")

    else:
        await bot.send_message(user_id, "❌ Invalid usage. Use: /dnd [on|off]")


async def cmd_allow_channel(message: dict, bot: 'TelegramBot'):
    """
    Handle /allow_channel command.

    Add a channel to the monitoring allowlist.
    Usage: /allow_channel <server_id> <channel_id>
    """
    user_id = message['from']['id']
    text = message.get('text', '')
    parts = text.split()

    if len(parts) != 3:
        error_text = """❌ Invalid usage

Correct format:
/allow_channel <server_id> <channel_id>

Example:
/allow_channel 123456789 987654321

To get IDs:
1. Enable Developer Mode in Discord settings
2. Right-click server/channel
3. Click "Copy ID" """

        await bot.send_message(user_id, error_text)
        return

    server_id = parts[1]
    channel_id = parts[2]

    # Validate IDs are numeric
    if not server_id.isdigit() or not channel_id.isdigit():
        await bot.send_message(user_id, "❌ Server ID and Channel ID must be numeric")
        return

    # Add channel to allowlist in database
    with bot.db.session_scope() as session:
        from ..database.dao import AllowlistDAO

        AllowlistDAO.add_channel(
            session,
            platform='discord',
            channel_id=channel_id,
            server_id=server_id
        )

        success_text = f"""✅ Channel Added to Allowlist

Server ID: {server_id}
Channel ID: {channel_id}

Messages from this channel will now be monitored."""

        await bot.send_message(user_id, success_text)

    logger.info(f"Channel {channel_id} in server {server_id} added to allowlist by user {user_id}")


async def cmd_unallow_channel(message: dict, bot: 'TelegramBot'):
    """
    Handle /unallow_channel command.

    Remove a channel from the monitoring allowlist.
    Usage: /unallow_channel <channel_id>
    """
    user_id = message['from']['id']
    text = message.get('text', '')
    parts = text.split()

    if len(parts) != 2:
        error_text = """❌ Invalid usage

Correct format:
/unallow_channel <channel_id>

Example:
/unallow_channel 987654321"""

        await bot.send_message(user_id, error_text)
        return

    channel_id = parts[1]

    # Validate ID is numeric
    if not channel_id.isdigit():
        await bot.send_message(user_id, "❌ Channel ID must be numeric")
        return

    # Remove channel from allowlist in database
    with bot.db.session_scope() as session:
        from ..database.dao import AllowlistDAO

        AllowlistDAO.remove_channel(session, channel_id, platform='discord')

        success_text = f"""✅ Channel Removed from Allowlist

Channel ID: {channel_id}

Messages from this channel will no longer be monitored."""

        await bot.send_message(user_id, success_text)

    logger.info(f"Channel {channel_id} removed from allowlist by user {user_id}")


async def cmd_settings(message: dict, bot: 'TelegramBot'):
    """
    Handle /settings command.

    Display current settings with inline keyboard for editing.
    """
    user_id = message['from']['id']

    # TODO: Get actual settings from database
    settings_text = """⚙️ Current Settings

🎮 Discord:
  • Status: Not Connected
  • Token: Not configured

📋 Monitoring:
  • Channels: 0
  • Allowlist: Empty

⏸️ Do Not Disturb:
  • Status: Disabled
  • Schedule: None

🔔 Notifications:
  • Enabled: Yes
  • Context Window: 10 messages

Use specific commands to change settings:
/setup_discord - Configure Discord
/dnd - Toggle DND mode
/allow_channel - Add channels"""

    await bot.send_message(user_id, settings_text)
    logger.info(f"Settings displayed for user {user_id}")


async def cmd_cancel(message: dict, bot: 'TelegramBot'):
    """
    Handle /cancel command.

    Cancel current FSM operation and clear state.
    """
    user_id = message['from']['id']

    state = bot.get_user_state(user_id)

    if state:
        bot.clear_user_state(user_id)
        await bot.send_message(user_id, "❌ Operation cancelled.")
        logger.info(f"Operation cancelled by user {user_id}, state was: {state.get('state')}")
    else:
        await bot.send_message(user_id, "ℹ️ No active operation to cancel.")


# =============================================================================
# Callback Query Handlers
# =============================================================================

async def callback_reply(query: dict, bot: 'TelegramBot'):
    """
    Handle reply_{task_id} callback.

    Initiates reply flow for a task.
    """
    user_id = query['from']['id']
    data = query['data']
    message = query['message']
    chat_id = message['chat']['id']

    # Extract task_id from callback data
    try:
        task_id = int(data.split('_')[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        return

    # Set FSM state to awaiting reply
    bot.set_user_state(user_id, f'awaiting_reply_{task_id}', {'message_id': message['message_id']})

    reply_text = """✍️ Enter Your Reply

Type your message below. It will be sent to the original channel/user.

After typing, you'll be asked to confirm before sending.

Use /cancel to abort."""

    await bot.send_message(chat_id, reply_text)
    logger.info(f"User {user_id} started reply flow for task {task_id}")


async def callback_more(query: dict, bot: 'TelegramBot'):
    """
    Handle more_{task_id} callback.

    Load and display more context for a task.
    """
    user_id = query['from']['id']
    data = query['data']
    message = query['message']
    chat_id = message['chat']['id']
    message_id = message['message_id']

    # Extract task_id from callback data
    try:
        task_id = int(data.split('_')[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        return

    # TODO: Load more context from database and update card
    # For now, just acknowledge
    await bot.send_message(chat_id, "🔄 Loading more context... (Not implemented yet)")
    logger.info(f"User {user_id} requested more context for task {task_id}")


async def callback_confirm(query: dict, bot: 'TelegramBot'):
    """
    Handle confirm_{reply_id} callback.

    Confirm and send a reply to Discord/Telegram.
    """
    user_id = query['from']['id']
    data = query['data']
    message = query['message']
    chat_id = message['chat']['id']

    # Extract reply_id from callback data
    try:
        reply_id = int(data.split('_')[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        await bot.send_message(chat_id, "❌ Error: Invalid callback data")
        return

    # Get reply from database and post to appropriate platform
    from ..database.connection import get_asyncpg_pool
    from ..database.dao.reply_dao import ReplyDAO
    import json

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get reply
            reply = await ReplyDAO.get_reply_by_id(conn, reply_id)
            if not reply:
                await bot.send_message(chat_id, "❌ Error: Reply not found")
                return

            # Get task
            task_query = "SELECT * FROM tasks WHERE id = (SELECT task_id FROM replies WHERE id = $1)"
            task_row = await conn.fetchrow(task_query, reply_id)
            if not task_row:
                await bot.send_message(chat_id, "❌ Error: Task not found")
                return
            task = dict(task_row)

            # Get message
            message_query = "SELECT * FROM messages WHERE id = $1"
            message_row = await conn.fetchrow(message_query, task['source_message_id'])
            if not message_row:
                await bot.send_message(chat_id, "❌ Error: Message not found")
                return
            msg_data = dict(message_row)

            # Determine platform and post
            platform = msg_data['platform']
            reply_text = reply['content']

            await bot.send_message(chat_id, "🔄 Sending reply...")

            if platform == 'discord':
                # Get user's Discord token from database
                from ..database.dao import DiscordDAO

                with bot.db.session_scope() as session:
                    from ..database.dao import UserDAO
                    user_db = UserDAO.get_user_by_tg_id(session, user_id)
                    if not user_db:
                        await bot.send_message(chat_id, "❌ Error: User not found in database")
                        return

                    discord_conn = DiscordDAO.get_discord_connection(session, user_db['id'])
                    if not discord_conn:
                        await bot.send_message(
                            chat_id,
                            "❌ Discord not configured. Use /setup_discord to configure."
                        )
                        return

                    # Decrypt token
                    from ..database.encryption import get_encryption_service
                    encryption_service = get_encryption_service()
                    try:
                        discord_token = encryption_service.decrypt(discord_conn['user_token_encrypted'])
                    except Exception as e:
                        logger.error(f"Failed to decrypt Discord token: {e}", exc_info=True)
                        await bot.send_message(chat_id, "❌ Error decrypting Discord token")
                        return

                # Use Discord poster
                from ..discord.poster import DiscordPoster
                poster = DiscordPoster(token=discord_token)

                result = await poster.post_message(
                    channel_id=msg_data['channel_id'],
                    content=reply_text,
                    thread_id=msg_data.get('thread_id'),
                    reply_to=msg_data['ext_message_id']
                )

                if result.get('success'):
                    # Mark reply as confirmed and posted
                    await ReplyDAO.mark_reply_confirmed(conn, reply_id)
                    platform_ref = json.dumps({
                        'platform': 'discord',
                        'message_id': result.get('message_id'),
                        'channel_id': msg_data['channel_id']
                    })
                    await ReplyDAO.mark_reply_posted(conn, reply_id, platform_ref)

                    # Update task status
                    update_task_query = """
                        UPDATE tasks
                        SET status = 'answered', answered_at = NOW(), updated_at = NOW()
                        WHERE id = $1
                    """
                    await conn.execute(update_task_query, task['id'])

                    await bot.send_message(chat_id, "✅ Reply sent to Discord!")
                    logger.info(f"Reply {reply_id} sent to Discord successfully")
                else:
                    # Update with error - mark as not posted
                    error_message = result.get('error', 'Unknown error')
                    await bot.send_message(
                        chat_id,
                        f"❌ Failed to send reply: {error_message}\n"
                        f"Use /retry to try again."
                    )
                    logger.error(f"Failed to send reply {reply_id}: {error_message}")

            elif platform == 'telegram':
                # Use Telegram poster
                from ..telegram.poster import TelegramPoster
                from ..config import get_config

                config = get_config()
                poster = TelegramPoster(token=config.telegram.bot_token)

                # Convert channel_id to int for Telegram
                try:
                    tg_chat_id = int(msg_data['channel_id'])
                except ValueError:
                    await bot.send_message(chat_id, "❌ Error: Invalid Telegram chat ID")
                    return

                # Convert ext_message_id to int if available
                reply_to_msg_id = None
                if msg_data.get('ext_message_id'):
                    try:
                        reply_to_msg_id = int(msg_data['ext_message_id'])
                    except ValueError:
                        pass

                result = await poster.post_message(
                    chat_id=tg_chat_id,
                    text=reply_text,
                    reply_to_message_id=reply_to_msg_id
                )

                if result.get('success'):
                    # Mark reply as confirmed and posted
                    await ReplyDAO.mark_reply_confirmed(conn, reply_id)
                    platform_ref = json.dumps({
                        'platform': 'telegram',
                        'message_id': result.get('message_id'),
                        'chat_id': tg_chat_id
                    })
                    await ReplyDAO.mark_reply_posted(conn, reply_id, platform_ref)

                    # Update task status
                    update_task_query = """
                        UPDATE tasks
                        SET status = 'answered', answered_at = NOW(), updated_at = NOW()
                        WHERE id = $1
                    """
                    await conn.execute(update_task_query, task['id'])

                    await bot.send_message(chat_id, "✅ Reply sent to Telegram!")
                    logger.info(f"Reply {reply_id} sent to Telegram successfully")
                else:
                    error_message = result.get('error', 'Unknown error')
                    await bot.send_message(
                        chat_id,
                        f"❌ Failed to send reply: {error_message}\n"
                        f"Use /retry to try again."
                    )
                    logger.error(f"Failed to send reply {reply_id}: {error_message}")

            else:
                await bot.send_message(chat_id, f"❌ Unsupported platform: {platform}")
                logger.error(f"Unsupported platform {platform} for reply {reply_id}")

        # Clear user state after posting attempt
        bot.clear_user_state(user_id)

    except Exception as e:
        logger.error(f"Error confirming reply {reply_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")
        bot.clear_user_state(user_id)


async def callback_retry(query: dict, bot: 'TelegramBot'):
    """
    Handle retry_{task_id} callback.

    Retry posting a failed reply.
    """
    user_id = query['from']['id']
    data = query['data']
    message = query['message']
    chat_id = message['chat']['id']

    # Extract task_id from callback data
    try:
        task_id = int(data.split('_')[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        await bot.send_message(chat_id, "❌ Error: Invalid callback data")
        return

    # Get latest reply for this task and retry posting
    from ..database.connection import get_asyncpg_pool
    from ..database.dao.reply_dao import ReplyDAO
    import json

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get task
            task_query = "SELECT * FROM tasks WHERE id = $1"
            task_row = await conn.fetchrow(task_query, task_id)
            if not task_row:
                await bot.send_message(chat_id, "❌ Error: Task not found")
                return
            task = dict(task_row)

            # Get latest reply for this task
            reply = await ReplyDAO.get_latest_reply_for_task(conn, task_id)
            if not reply:
                await bot.send_message(chat_id, "❌ Error: No reply found for this task")
                return

            reply_id = reply['id']

            # Get message
            message_query = "SELECT * FROM messages WHERE id = $1"
            message_row = await conn.fetchrow(message_query, task['source_message_id'])
            if not message_row:
                await bot.send_message(chat_id, "❌ Error: Message not found")
                return
            msg_data = dict(message_row)

            # Retry posting (same logic as callback_confirm)
            platform = msg_data['platform']
            reply_text = reply['content']

            await bot.send_message(chat_id, "🔄 Retrying...")

            if platform == 'discord':
                # Get user's Discord token from database
                from ..database.dao import DiscordDAO

                with bot.db.session_scope() as session:
                    from ..database.dao import UserDAO
                    user_db = UserDAO.get_user_by_tg_id(session, user_id)
                    if not user_db:
                        await bot.send_message(chat_id, "❌ Error: User not found in database")
                        return

                    discord_conn = DiscordDAO.get_discord_connection(session, user_db['id'])
                    if not discord_conn:
                        await bot.send_message(
                            chat_id,
                            "❌ Discord not configured. Use /setup_discord to configure."
                        )
                        return

                    # Decrypt token
                    from ..database.encryption import get_encryption_service
                    encryption_service = get_encryption_service()
                    try:
                        discord_token = encryption_service.decrypt(discord_conn['user_token_encrypted'])
                    except Exception as e:
                        logger.error(f"Failed to decrypt Discord token: {e}", exc_info=True)
                        await bot.send_message(chat_id, "❌ Error decrypting Discord token")
                        return

                # Use Discord poster
                from ..discord.poster import DiscordPoster
                poster = DiscordPoster(token=discord_token)

                result = await poster.post_message(
                    channel_id=msg_data['channel_id'],
                    content=reply_text,
                    thread_id=msg_data.get('thread_id'),
                    reply_to=msg_data['ext_message_id']
                )

                if result.get('success'):
                    # Mark reply as confirmed and posted
                    await ReplyDAO.mark_reply_confirmed(conn, reply_id)
                    platform_ref = json.dumps({
                        'platform': 'discord',
                        'message_id': result.get('message_id'),
                        'channel_id': msg_data['channel_id']
                    })
                    await ReplyDAO.mark_reply_posted(conn, reply_id, platform_ref)

                    # Update task status
                    update_task_query = """
                        UPDATE tasks
                        SET status = 'answered', answered_at = NOW(), updated_at = NOW()
                        WHERE id = $1
                    """
                    await conn.execute(update_task_query, task['id'])

                    await bot.send_message(chat_id, "✅ Reply sent to Discord!")
                    logger.info(f"Reply {reply_id} retried and sent to Discord successfully")
                else:
                    error_message = result.get('error', 'Unknown error')
                    await bot.send_message(
                        chat_id,
                        f"❌ Retry failed: {error_message}\n"
                        f"Please check your Discord connection or try again later."
                    )
                    logger.error(f"Failed to retry reply {reply_id}: {error_message}")

            elif platform == 'telegram':
                # Use Telegram poster
                from ..telegram.poster import TelegramPoster
                from ..config import get_config

                config = get_config()
                poster = TelegramPoster(token=config.telegram.bot_token)

                # Convert channel_id to int for Telegram
                try:
                    tg_chat_id = int(msg_data['channel_id'])
                except ValueError:
                    await bot.send_message(chat_id, "❌ Error: Invalid Telegram chat ID")
                    return

                # Convert ext_message_id to int if available
                reply_to_msg_id = None
                if msg_data.get('ext_message_id'):
                    try:
                        reply_to_msg_id = int(msg_data['ext_message_id'])
                    except ValueError:
                        pass

                result = await poster.post_message(
                    chat_id=tg_chat_id,
                    text=reply_text,
                    reply_to_message_id=reply_to_msg_id
                )

                if result.get('success'):
                    # Mark reply as confirmed and posted
                    await ReplyDAO.mark_reply_confirmed(conn, reply_id)
                    platform_ref = json.dumps({
                        'platform': 'telegram',
                        'message_id': result.get('message_id'),
                        'chat_id': tg_chat_id
                    })
                    await ReplyDAO.mark_reply_posted(conn, reply_id, platform_ref)

                    # Update task status
                    update_task_query = """
                        UPDATE tasks
                        SET status = 'answered', answered_at = NOW(), updated_at = NOW()
                        WHERE id = $1
                    """
                    await conn.execute(update_task_query, task['id'])

                    await bot.send_message(chat_id, "✅ Reply sent to Telegram!")
                    logger.info(f"Reply {reply_id} retried and sent to Telegram successfully")
                else:
                    error_message = result.get('error', 'Unknown error')
                    await bot.send_message(
                        chat_id,
                        f"❌ Retry failed: {error_message}\n"
                        f"Please try again later."
                    )
                    logger.error(f"Failed to retry reply {reply_id}: {error_message}")

            else:
                await bot.send_message(chat_id, f"❌ Unsupported platform: {platform}")
                logger.error(f"Unsupported platform {platform} for reply {reply_id}")

    except Exception as e:
        logger.error(f"Error retrying task {task_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


async def callback_toggle_dnd(query: dict, bot: 'TelegramBot'):
    """
    Handle toggle_dnd callback.

    Toggle Do Not Disturb mode.
    """
    user_id = query['from']['id']
    message = query['message']
    chat_id = message['chat']['id']

    # TODO: Toggle DND in database
    await bot.send_message(chat_id, "⏸️ DND toggled (Not fully implemented yet)")
    logger.info(f"User {user_id} toggled DND mode")


# =============================================================================
# Message Handlers (for FSM states)
# =============================================================================

async def handle_fsm_message(message: dict, bot: 'TelegramBot') -> bool:
    """
    Handle messages based on current FSM state.

    Returns:
        True if message was handled, False otherwise
    """
    user_id = message['from']['id']
    text = message.get('text', '')

    # Get current state
    state_data = bot.get_user_state(user_id)

    if not state_data:
        return False

    state = state_data.get('state', '')

    # Handle Discord token input
    if state == 'awaiting_discord_token':
        await handle_discord_token_input(message, bot)
        return True

    # Handle reply text input
    if state.startswith('awaiting_reply_'):
        await handle_reply_text_input(message, bot, state)
        return True

    return False


async def handle_discord_token_input(message: dict, bot: 'TelegramBot'):
    """
    Handle Discord token input during setup.
    """
    user_id = message['from']['id']
    token = message.get('text', '').strip()

    # Validate token format (basic check)
    if not token or len(token) < 50:
        await bot.send_message(user_id, "❌ Invalid token format. Please try again or /cancel")
        return

    with bot.db.session_scope() as session:
        from ..database.dao import UserDAO, DiscordDAO
        from ..database.encryption import get_encryption_service

        # Get or create user
        user = UserDAO.get_user_by_tg_id(session, user_id)
        if not user:
            user_id_db = UserDAO.create_user(session, user_id)
        else:
            user_id_db = user['id']

        # Encrypt and save token
        encryption_service = get_encryption_service()
        encrypted_token = encryption_service.encrypt(token)

        DiscordDAO.save_discord_connection(
            session,
            user_id=user_id_db,
            encrypted_token=encrypted_token,
            super_properties=None  # Auto-generated by gateway
        )

        await bot.send_message(user_id,
            "✅ Discord token saved and encrypted\n"
            "🔄 Connecting to Discord Gateway...\n"
            "Please wait..."
        )

        # Mark as saved (gateway connection will be handled separately)
        DiscordDAO.update_connection_status(session, user_id_db, 'disconnected')

        await bot.send_message(user_id,
            "✅ Token saved! Use /test_connection to verify."
        )

    # Clear state
    bot.clear_user_state(user_id)

    logger.info(f"Discord token configured by user {user_id}")


async def handle_reply_text_input(message: dict, bot: 'TelegramBot', state: str):
    """
    Handle reply text input.
    """
    user_id = message['from']['id']
    reply_text = message.get('text', '')
    chat_id = message['chat']['id']

    if not reply_text.strip():
        await bot.send_message(user_id, "❌ Reply cannot be empty. Please type your message or /cancel")
        return

    # Extract task_id from state
    try:
        task_id = int(state.split('_')[-1])
    except ValueError:
        logger.error(f"Invalid state format: {state}")
        bot.clear_user_state(user_id)
        await bot.send_message(user_id, "❌ Error: Invalid state. Please try again.")
        return

    # Store reply in database with pending status
    from ..database.connection import get_asyncpg_pool
    from ..database.dao.reply_dao import ReplyDAO

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Create reply with 'human' generation and not confirmed yet
            reply_id = await ReplyDAO.create_reply(
                conn,
                task_id=task_id,
                content=reply_text,
                generated_by='human',
                llm_confidence=None,
                edit_of=None
            )

            logger.info(f"Created reply {reply_id} for task {task_id}")

    except Exception as e:
        logger.error(f"Failed to create reply in database: {e}", exc_info=True)
        await bot.send_message(user_id, f"❌ Error saving reply: {str(e)}")
        bot.clear_user_state(user_id)
        return

    # Show confirmation message with reply preview
    preview_text = f"""✅ Reply Preview

Your reply:
---
{reply_text}
---

Please confirm to send this message."""

    # Create confirmation keyboard with reply_id
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '✅ Confirm & Send', 'callback_data': f'confirm_{reply_id}'},
                {'text': '❌ Cancel', 'callback_data': f'cancel_reply_{reply_id}'}
            ]
        ]
    }

    await bot.send_message(chat_id, preview_text, reply_markup=keyboard)

    # Update state to awaiting confirmation with reply_id
    bot.set_user_state(user_id, f'awaiting_confirm_{task_id}', {
        'reply_text': reply_text,
        'reply_id': reply_id
    })

    logger.info(f"User {user_id} submitted reply for task {task_id}, awaiting confirmation")


async def callback_cancel_reply(query: dict, bot: 'TelegramBot'):
    """
    Handle cancel_reply_{reply_id} callback.

    Cancel the reply confirmation and delete the reply from database.
    """
    user_id = query['from']['id']
    chat_id = query['message']['chat']['id']
    data = query['data']

    # Extract reply_id if present
    reply_id = None
    if '_' in data and len(data.split('_')) >= 3:
        try:
            reply_id = int(data.split('_')[2])
        except (IndexError, ValueError):
            logger.warning(f"Could not extract reply_id from callback data: {data}")

    # Delete reply from database if we have reply_id
    if reply_id:
        from ..database.connection import get_asyncpg_pool
        from ..database.dao.reply_dao import ReplyDAO

        db_pool = get_asyncpg_pool()

        try:
            async with db_pool.acquire() as conn:
                deleted = await ReplyDAO.delete_reply(conn, reply_id)
                if deleted:
                    logger.info(f"Deleted reply {reply_id} (cancelled by user {user_id})")
                else:
                    logger.warning(f"Reply {reply_id} not found when trying to delete")
        except Exception as e:
            logger.error(f"Error deleting reply {reply_id}: {e}", exc_info=True)

    # Clear state
    bot.clear_user_state(user_id)

    await bot.send_message(chat_id, "❌ Reply cancelled.")
    logger.info(f"User {user_id} cancelled reply")


# =============================================================================
# Handler Registration
# =============================================================================

def register_all_handlers(bot: 'TelegramBot'):
    """
    Register all command and callback handlers with the bot.

    Args:
        bot: TelegramBot instance
    """
    # Command handlers
    bot.register_command_handler('/start', cmd_start)
    bot.register_command_handler('/help', cmd_help)
    bot.register_command_handler('/setup_discord', cmd_setup_discord)
    bot.register_command_handler('/test_connection', cmd_test_connection)
    bot.register_command_handler('/discord_status', cmd_discord_status)
    bot.register_command_handler('/status', cmd_status)
    bot.register_command_handler('/dnd', cmd_dnd)
    bot.register_command_handler('/allow_channel', cmd_allow_channel)
    bot.register_command_handler('/unallow_channel', cmd_unallow_channel)
    bot.register_command_handler('/settings', cmd_settings)
    bot.register_command_handler('/cancel', cmd_cancel)

    # Callback handlers
    bot.register_callback_handler('reply_', callback_reply)
    bot.register_callback_handler('more_', callback_more)
    bot.register_callback_handler('confirm_', callback_confirm)
    bot.register_callback_handler('retry_', callback_retry)
    bot.register_callback_handler('toggle_dnd', callback_toggle_dnd)
    bot.register_callback_handler('cancel_reply', callback_cancel_reply)

    # Message handlers (FSM)
    bot.register_message_handler(handle_fsm_message)

    logger.info("All handlers registered successfully")
