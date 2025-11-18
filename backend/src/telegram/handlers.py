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
- /dnd [on|off|schedule]: Toggle or configure Do Not Disturb mode with confirmation dialogs
- /allow_channel {server_id} {channel_id}: Add channel to allowlist
- /unallow_channel [channel_id]: Remove channel from allowlist (with interactive selection)
- /settings: View and edit settings with action buttons

Callback handlers:
- reply_{task_id}: Start reply flow for a task
- more_{task_id}: Load more context for a task
- confirm_{reply_id}: Confirm and send a reply
- retry_{task_id}: Retry failed posting
- toggle_dnd: Toggle DND mode (shows confirmation dialog)
- confirm_toggle_dnd_{state}: Execute DND toggle after confirmation
- cancel_toggle_dnd: Cancel DND toggle action
- cancel_reply_{reply_id}: Cancel reply submission
- use_variant_{variant_id}: Select AI-generated response variant
- soften_{task_id}: Regenerate response with soft tone
- more_variants_{task_id}: Generate additional response variants
- unallow_select_{allowlist_id}: Select channel for removal
- unallow_confirm_{allowlist_id}: Confirm channel removal
- unallow_cancel: Cancel removal operation
- settings_add_channel: Guide user to add channel
- settings_remove_channel: Show removal dialog
- settings_refresh: Refresh settings display
- edit_reply_{reply_id}: Start editing an existing reply
- confirm_edit_{new_reply_id}: Confirm and post edited reply
- cancel_edit_{reply_id}: Cancel reply edit operation
- show_history_{reply_id}: Display edit history for a reply

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
/unallow_channel [channel_id] - Remove channel (interactive or by ID)

⚙️ Settings & Status:
/status - Show system status (DND, channels, etc.)
/dnd [on|off|schedule] - Toggle or configure DND mode
/settings - View/edit all settings (with action buttons)

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

    Toggle or configure Do Not Disturb mode with confirmation dialogs.
    Supports: /dnd, /dnd on, /dnd off, /dnd schedule
    """
    user_id = message['from']['id']
    text = message.get('text', '')
    parts = text.split()

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.user_dao import UserDAO
    from ..services.dnd import get_dnd_settings, is_dnd_active
    from .confirmations import create_dnd_toggle_confirmation, ConfirmationBuilder

    db_pool = get_asyncpg_pool()

    async with db_pool.acquire() as conn:
        user = await UserDAO.get_user_by_tg_id(conn, user_id)
        if not user:
            await bot.send_message(user_id, "❌ User not found. Use /start first.")
            return

        user_id_db = user['id']

        if len(parts) == 1:
            # Just /dnd - show current status
            settings = await get_dnd_settings(conn, user_id_db)
            is_active = await is_dnd_active(conn, user_id_db)

            status_text = "🔕 Enabled" if settings['dnd_enabled'] else "🔔 Disabled"
            active_text = "✅ Currently active" if is_active else "⏸️ Not active now"

            schedule_text = "None"
            if settings.get('dnd_schedule_json'):
                schedule_text = f"Custom schedule configured"

            dnd_text = f"""⏸️ Do Not Disturb Settings

Status: {status_text}
{active_text}
Schedule: {schedule_text}

Commands:
• /dnd on - Enable DND mode
• /dnd off - Disable DND mode
• /dnd schedule - Configure schedule

When DND is enabled, you won't receive message notifications."""

            await bot.send_message(user_id, dnd_text)

        elif len(parts) == 2:
            mode = parts[1].lower()

            if mode == 'on' or mode == 'off':
                # Get current DND state
                settings = await get_dnd_settings(conn, user_id_db)
                current_state = settings['dnd_enabled']

                # Determine desired new state
                desired_state = (mode == 'on')

                # Check if already in desired state
                if current_state == desired_state:
                    state_word = "enabled" if desired_state else "disabled"
                    emoji = "🔕" if desired_state else "🔔"
                    await bot.send_message(
                        user_id,
                        f"{emoji} DND mode is already {state_word}."
                    )
                    return

                # Show confirmation dialog
                dialog = create_dnd_toggle_confirmation(current_state)
                text_msg, keyboard = ConfirmationBuilder.format_confirmation(dialog)

                # Store pending action in user state
                bot.set_user_state(user_id, 'awaiting_dnd_confirmation', {
                    'new_state': desired_state,
                    'user_id_db': user_id_db
                })

                await bot.send_message(user_id, text_msg, reply_markup=keyboard, parse_mode='Markdown')
                logger.info(
                    f"DND toggle confirmation shown to user {user_id}: "
                    f"{current_state} -> {desired_state}"
                )

            elif mode == 'schedule':
                # Open schedule configuration dialog
                schedule_text = """⏰ DND Schedule Configuration

Schedule format: Time intervals per day

Example: "22:00-08:00 Mon-Fri" (nights on weekdays)

Send your schedule or /cancel to abort."""

                await bot.send_message(user_id, schedule_text)
                bot.set_user_state(user_id, 'awaiting_dnd_schedule')
                logger.info(f"DND schedule configuration started for user {user_id}")

            else:
                await bot.send_message(user_id, "❌ Invalid option. Use: /dnd on, /dnd off, or /dnd schedule")

        else:
            await bot.send_message(user_id, "❌ Invalid usage. Use: /dnd [on|off|schedule]")


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
    Usage:
    - /unallow_channel - Show interactive selection dialog
    - /unallow_channel <channel_id> - Legacy mode (direct removal)
    """
    user_id = message['from']['id']
    text = message.get('text', '')
    parts = text.split()

    # Check if channel_id was provided (legacy mode)
    if len(parts) == 2:
        # Legacy mode: direct removal by channel_id
        await _unallow_channel_by_id(message, bot, parts[1])
    elif len(parts) == 1:
        # New mode: show interactive selection dialog
        await _show_allowlist_selection(user_id, bot)
    else:
        error_text = """❌ Invalid usage

Usage:
• /unallow_channel - Show selection dialog
• /unallow_channel <channel_id> - Remove specific channel

Example:
/unallow_channel 987654321"""

        await bot.send_message(user_id, error_text)


async def _show_allowlist_selection(user_id: int, bot: 'TelegramBot'):
    """
    Show interactive allowlist selection dialog.

    Args:
        user_id: Telegram user ID
        bot: TelegramBot instance
    """
    from ..database.connection import get_asyncpg_pool
    from ..database.dao.allowlist_dao import AllowlistDAO
    from ..services.allowlist import get_channel_display_name

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get all allowed channels
            channels = await AllowlistDAO.get_all_channels(conn, platform='discord', enabled_only=True)

            if not channels:
                await bot.send_message(
                    user_id,
                    "ℹ️ No channels in allowlist.\n\nUse /allow_channel to add channels."
                )
                return

            # Build message text
            text = "📋 Select Channel to Remove\n\n"
            text += "Current allowlist:\n\n"

            # Build inline keyboard with channel selection buttons
            keyboard_rows = []

            for channel in channels[:20]:  # Limit to 20 channels for UI
                display_name = get_channel_display_name(
                    channel.get('server_id'),
                    channel.get('channel_id')
                )
                allowlist_id = channel.get('id')

                # Add to text
                platform_emoji = "💬" if channel.get('platform') == 'telegram' else "📝"
                text += f"{platform_emoji} {display_name}\n"

                # Add button for this channel
                keyboard_rows.append([{
                    'text': f"❌ Remove: {display_name[:30]}...",
                    'callback_data': f'unallow_select_{allowlist_id}'
                }])

            if len(channels) > 20:
                text += f"\n... and {len(channels) - 20} more channel(s)"

            # Add cancel button at the bottom
            keyboard_rows.append([{
                'text': '🔙 Cancel',
                'callback_data': 'unallow_cancel'
            }])

            keyboard = {'inline_keyboard': keyboard_rows}

            await bot.send_message(user_id, text, reply_markup=keyboard)
            logger.info(f"Showed allowlist selection to user {user_id}, {len(channels)} channels")

    except Exception as e:
        logger.error(f"Error showing allowlist selection: {e}", exc_info=True)
        await bot.send_message(user_id, f"❌ Error loading allowlist: {str(e)}")


async def _unallow_channel_by_id(message: dict, bot: 'TelegramBot', channel_id: str):
    """
    Legacy mode: Remove channel by ID directly.

    Args:
        message: Telegram message dict
        bot: TelegramBot instance
        channel_id: Channel ID to remove
    """
    user_id = message['from']['id']

    # Validate ID is numeric
    if not channel_id.isdigit():
        await bot.send_message(user_id, "❌ Channel ID must be numeric")
        return

    # Remove channel from allowlist in database
    with bot.db.session_scope() as session:
        from ..database.dao import AllowlistDAO

        removed = AllowlistDAO.remove_channel(session, channel_id, platform='discord')

        if removed:
            success_text = f"""✅ Channel Removed from Allowlist

Channel ID: {channel_id}

Messages from this channel will no longer be monitored."""
        else:
            success_text = f"""⚠️ Channel Not Found

Channel ID: {channel_id}

This channel was not in the allowlist."""

        await bot.send_message(user_id, success_text)

    logger.info(f"Channel {channel_id} removed from allowlist by user {user_id} (legacy mode)")


async def cmd_settings(message: dict, bot: 'TelegramBot'):
    """
    Handle /settings command.

    Display current settings with inline keyboard for editing.
    Shows actual allowlist from database and provides action buttons.
    """
    user_id = message['from']['id']

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.allowlist_dao import AllowlistDAO
    from ..services.allowlist import format_allowlist_display

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            from ..database.dao.user_dao import UserDAO

            # Get user
            user = await UserDAO.get_user_by_tg_id(conn, user_id)
            if not user:
                await bot.send_message(user_id, "❌ User not found. Use /start first.")
                return

            user_id_db = user['id']

            # Get Discord status
            discord_status = "❌ Not Connected"
            with bot.db.session_scope() as session:
                from ..database.dao import DiscordDAO
                discord_conn = DiscordDAO.get_discord_connection(session, user_id_db)
                if discord_conn and discord_conn.get('status') == 'connected':
                    discord_status = "✅ Connected"

            # Get DND status
            from ..services.dnd import get_dnd_settings, is_dnd_active
            dnd_settings = await get_dnd_settings(conn, user_id_db)
            dnd_status = "🔕 Enabled" if dnd_settings.get('dnd_enabled') else "🔔 Disabled"
            is_active = await is_dnd_active(conn, user_id_db)
            if is_active:
                dnd_status += " (Active now)"

            # Get allowlist channels
            channels = await AllowlistDAO.get_all_channels(conn, platform='discord', enabled_only=True)
            channel_count = len(channels)

            # Format allowlist display
            if channels:
                allowlist_display = format_allowlist_display(channels, max_display=5)
            else:
                allowlist_display = "Empty"

            # Build settings text
            settings_text = f"""⚙️ Current Settings

🎮 Discord:
  • Status: {discord_status}

📋 Monitoring:
  • Channels: {channel_count}

Allowlist (top 5):
{allowlist_display}

⏸️ Do Not Disturb:
  • Status: {dnd_status}
  • Schedule: {"Configured" if dnd_settings.get('dnd_schedule_json') else "None"}

🔔 Notifications:
  • Enabled: Yes
  • Context Window: 10 messages"""

            # Create action buttons keyboard
            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '➕ Add Channel', 'callback_data': 'settings_add_channel'},
                        {'text': '➖ Remove Channel', 'callback_data': 'settings_remove_channel'}
                    ],
                    [
                        {'text': '🔕 Toggle DND', 'callback_data': 'toggle_dnd'},
                        {'text': '🔄 Refresh', 'callback_data': 'settings_refresh'}
                    ]
                ]
            }

            await bot.send_message(user_id, settings_text, reply_markup=keyboard)
            logger.info(f"Settings displayed for user {user_id}, {channel_count} channels in allowlist")

    except Exception as e:
        logger.error(f"Error showing settings: {e}", exc_info=True)
        await bot.send_message(user_id, f"❌ Error loading settings: {str(e)}")


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

    # Get task and message from database
    from ..database.connection import get_asyncpg_pool
    from ..database.dao.task_dao import TaskDAO
    from ..database.dao.message_dao import MessageDAO
    from ..services.context import get_context_by_channel
    from ..telegram.cards import format_card, create_card_keyboard

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get task
            task = await TaskDAO.get_task_by_id(conn, task_id)
            if not task:
                await bot.send_message(chat_id, "❌ Task not found")
                return

            # Get main message
            msg = await MessageDAO.get_message_by_id(conn, task['source_message_id'])
            if not msg:
                await bot.send_message(chat_id, "❌ Message not found")
                return

            # Get current offset from user state or default to 10
            state = bot.get_user_state(user_id) or {}
            state_data = state.get('data', {}) if isinstance(state.get('data'), dict) else {}
            current_offset = state_data.get(f'offset_{task_id}', 10)

            # Load MORE context (next 10 messages before current offset)
            # We want to get messages BEFORE the original message, using the limit as cumulative count
            extended_context_list = await get_context_by_channel(
                conn,
                platform=msg['platform'],
                channel_id=msg['channel_id'],
                server_id=msg.get('server_id'),
                thread_id=msg.get('thread_id'),
                before_message_id=msg['id'],
                limit=current_offset + 10  # Load 10 more (cumulative)
            )

            # Convert Message objects to dicts for format_card
            extended_context = []
            for ctx_msg in extended_context_list:
                # Check if it's already a dict or a Message object
                if hasattr(ctx_msg, '__dict__'):
                    # It's a Message dataclass, convert to dict
                    extended_context.append({
                        'id': ctx_msg.id,
                        'platform': ctx_msg.platform,
                        'ext_message_id': ctx_msg.ext_message_id,
                        'server_id': ctx_msg.server_id,
                        'channel_id': ctx_msg.channel_id,
                        'thread_id': ctx_msg.thread_id,
                        'author_id': ctx_msg.author_id,
                        'author_name': ctx_msg.author_name,
                        'content': ctx_msg.content,
                        'has_image': ctx_msg.has_image,
                        'context_ref': ctx_msg.context_ref,
                        'created_at': ctx_msg.created_at,
                        'platform_created_at': ctx_msg.platform_created_at
                    })
                else:
                    # It's already a dict
                    extended_context.append(ctx_msg)

            # Update offset for next "more" click
            new_offset = current_offset + 10

            # Update user state with new offset
            bot.set_user_state(user_id, 'viewing_task', {
                **state_data,
                f'offset_{task_id}': new_offset
            })

            # Reformat card with extended context
            updated_card = format_card(msg, extended_context)

            # Determine if there are more messages available
            # If we got fewer messages than requested, there are no more
            show_more_button = len(extended_context) >= new_offset

            keyboard = create_card_keyboard(task_id, show_more=show_more_button)

            # Edit message with updated card
            success = await bot.edit_message(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_card,
                reply_markup=keyboard
            )

            if success:
                logger.info(f"Extended context for task {task_id}, offset now {new_offset}, total context: {len(extended_context)}")
            else:
                await bot.send_message(chat_id, "⚠️ Could not update card")

    except Exception as e:
        logger.error(f"Error loading more context for task {task_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error loading context: {str(e)}")


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


async def callback_dnd_toggle_confirm(query: dict, bot: 'TelegramBot'):
    """
    Handle confirm_toggle_dnd_{state} callback.

    Execute DND toggle after user confirmation.
    """
    user_id = query['from']['id']
    message = query['message']
    chat_id = message['chat']['id']
    data = query['data']

    # Get user state to retrieve pending action
    state_data = bot.get_user_state(user_id)

    if not state_data or state_data.get('state') != 'awaiting_dnd_confirmation':
        await bot.send_message(chat_id, "❌ No pending DND action found.")
        logger.warning(f"DND confirmation callback without proper state for user {user_id}")
        return

    # Extract new state and user_id_db from state
    pending_data = state_data.get('data', {})
    new_state = pending_data.get('new_state')
    user_id_db = pending_data.get('user_id_db')

    if new_state is None or user_id_db is None:
        await bot.send_message(chat_id, "❌ Invalid confirmation state.")
        logger.error(f"Missing data in DND confirmation state for user {user_id}")
        bot.clear_user_state(user_id)
        return

    # Update DND setting in database
    from ..database.connection import get_asyncpg_pool
    from ..services.dnd import update_dnd_settings

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            await update_dnd_settings(conn, user_id_db, dnd_enabled=new_state)

        # Send success message
        if new_state:
            success_msg = "🔕 **DND Mode: ON**\n\nYou will not receive message cards."
        else:
            success_msg = "🔔 **DND Mode: OFF**\n\nYou will receive message cards normally."

        await bot.send_message(chat_id, success_msg, parse_mode='Markdown')

        logger.info(f"DND {'enabled' if new_state else 'disabled'} by user {user_id}")

    except Exception as e:
        logger.error(f"Error updating DND setting for user {user_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error updating DND mode: {str(e)}")

    finally:
        # Clear user state
        bot.clear_user_state(user_id)


async def callback_dnd_toggle_cancel(query: dict, bot: 'TelegramBot'):
    """
    Handle cancel_toggle_dnd callback.

    Cancel DND toggle action without making changes.
    """
    user_id = query['from']['id']
    message = query['message']
    chat_id = message['chat']['id']

    # Clear user state
    bot.clear_user_state(user_id)

    await bot.send_message(chat_id, "❌ DND toggle cancelled. No changes made.")
    logger.info(f"User {user_id} cancelled DND toggle")


async def callback_toggle_dnd(query: dict, bot: 'TelegramBot'):
    """
    Handle toggle_dnd callback (legacy - for backwards compatibility).

    Toggle Do Not Disturb mode from message card buttons.
    Shows confirmation dialog before toggling.
    """
    user_id = query['from']['id']
    message = query['message']
    chat_id = message['chat']['id']

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.user_dao import UserDAO
    from ..services.dnd import get_dnd_settings
    from .confirmations import create_dnd_toggle_confirmation, ConfirmationBuilder

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            user = await UserDAO.get_user_by_tg_id(conn, user_id)
            if not user:
                await bot.send_message(chat_id, "❌ User not found.")
                return

            user_id_db = user['id']

            # Get current DND state
            settings = await get_dnd_settings(conn, user_id_db)
            current_state = settings['dnd_enabled']

            # Create confirmation dialog
            dialog = create_dnd_toggle_confirmation(current_state)
            text_msg, keyboard = ConfirmationBuilder.format_confirmation(dialog)

            # Store pending action in user state
            bot.set_user_state(user_id, 'awaiting_dnd_confirmation', {
                'new_state': not current_state,
                'user_id_db': user_id_db
            })

            await bot.send_message(chat_id, text_msg, reply_markup=keyboard, parse_mode='Markdown')
            logger.info(f"DND toggle confirmation shown to user {user_id}")

    except Exception as e:
        logger.error(f"Error showing DND toggle confirmation: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


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

    # Handle edit reply text input
    if state.startswith('awaiting_edit_text_'):
        await handle_edit_text_input(message, bot, state)
        return True

    # Handle DND schedule input
    if state == 'awaiting_dnd_schedule':
        await handle_dnd_schedule_input(message, bot)
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


async def handle_dnd_schedule_input(message: dict, bot: 'TelegramBot'):
    """Handle DND schedule configuration input."""
    import json

    user_id = message['from']['id']
    schedule_text = message.get('text', '').strip()

    # Simple format: "22:00-08:00 Mon-Sun" or "weeknights" presets
    # For MVP, just store as JSON directly or use presets

    # Example: preset for weeknights
    if schedule_text.lower() == 'weeknights':
        schedule_json = json.dumps([{
            "start": "22:00",
            "end": "08:00",
            "days": [0, 1, 2, 3, 4]  # Mon-Fri
        }])
    elif schedule_text.lower() == 'always':
        schedule_json = json.dumps([{
            "start": "00:00",
            "end": "23:59",
            "days": [0, 1, 2, 3, 4, 5, 6]  # All days
        }])
    else:
        # TODO: Parse custom schedule format
        await bot.send_message(user_id,
            "❌ Custom schedules not yet supported. Use presets:\n"
            "• weeknights - 22:00-08:00 Mon-Fri\n"
            "• always - All day every day"
        )
        return

    # Save schedule
    from ..database.connection import get_asyncpg_pool
    from ..database.dao.user_dao import UserDAO
    from ..services.dnd import update_dnd_settings

    db_pool = get_asyncpg_pool()

    async with db_pool.acquire() as conn:
        user = await UserDAO.get_user_by_tg_id(conn, user_id)
        if user:
            await update_dnd_settings(conn, user['id'], dnd_schedule_json=schedule_json)
            await bot.send_message(user_id, "✅ DND schedule configured!")
            logger.info(f"DND schedule set for user {user_id}: {schedule_json}")

    bot.clear_user_state(user_id)


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


async def callback_use_variant(query: dict, bot: 'TelegramBot'):
    """
    Handle use_variant_{variant_id} callback.

    User selected an AI-generated variant to use as their reply.
    """
    user_id = query['from']['id']
    data = query['data']
    chat_id = query['message']['chat']['id']

    # Extract variant_id
    try:
        variant_id = int(data.split('_')[2])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        await bot.send_message(chat_id, "❌ Error: Invalid callback data")
        return

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.ai_variant_dao import AIVariantDAO
    from ..database.dao.reply_dao import ReplyDAO

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get variant
            variant_query = "SELECT * FROM ai_response_variants WHERE id = $1"
            variant_row = await conn.fetchrow(variant_query, variant_id)

            if not variant_row:
                await bot.send_message(chat_id, "❌ Variant not found")
                return

            variant = dict(variant_row)
            task_id = variant['task_id']
            variant_text = variant['variant_text']

            # Create reply with AI-generated text
            reply_id = await ReplyDAO.create_reply(
                conn,
                task_id=task_id,
                content=variant_text,
                generated_by='ai',
                llm_confidence=variant.get('confidence_score'),
                edit_of=None
            )

            # Mark variant as selected
            await AIVariantDAO.mark_variant_selected(conn, variant_id)

            logger.info(f"User {user_id} selected AI variant {variant_id} for task {task_id}")

            # Show confirmation with preview
            preview_text = f"""✅ **AI Response Selected**

Your reply (AI-generated):
---
{variant_text}
---

Confidence: {int(variant.get('confidence_score', 0) * 100)}%
Provider: {variant.get('provider', 'unknown')}

Please confirm to send this message."""

            # Confirmation keyboard
            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '✅ Confirm & Send', 'callback_data': f'confirm_{reply_id}'},
                        {'text': '✏️ Edit', 'callback_data': f'edit_reply_{reply_id}'},
                        {'text': '❌ Cancel', 'callback_data': f'cancel_reply_{reply_id}'}
                    ]
                ]
            }

            await bot.send_message(chat_id, preview_text, reply_markup=keyboard, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error using variant {variant_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


async def callback_soften(query: dict, bot: 'TelegramBot'):
    """
    Handle soften_{task_id} callback.

    Regenerate response variants with 'soft' tone.
    """
    user_id = query['from']['id']
    data = query['data']
    chat_id = query['message']['chat']['id']
    message_id = query['message']['message_id']

    # Extract task_id
    try:
        task_id = int(data.split('_')[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        return

    await bot.send_message(chat_id, "🎨 Softening response... Please wait.")

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.task_dao import TaskDAO
    from ..services.response_generation import ResponseGenerationService
    from ..telegram.cards import format_card, create_card_keyboard

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get task
            task = await TaskDAO.get_task_by_id(conn, task_id)
            if not task:
                await bot.send_message(chat_id, "❌ Task not found")
                return

            message_id_db = task['source_message_id']

            # Generate soft variants
            variants = await ResponseGenerationService.soften_response(task_id, message_id_db)

            if not variants:
                await bot.send_message(chat_id, "❌ Failed to generate soft responses")
                return

            # Get message for card
            from ..database.dao.message_dao import MessageDAO
            msg = await MessageDAO.get_message_by_id(conn, message_id_db)

            # Reload context
            from ..services.context import get_context_by_channel
            context_messages = await get_context_by_channel(
                conn,
                platform=msg['platform'],
                channel_id=msg['channel_id'],
                server_id=msg.get('server_id'),
                thread_id=msg.get('thread_id'),
                before_message_id=message_id_db,
                limit=10
            )

            # Update card with new variants
            updated_card = format_card(msg, context_messages, variants=variants)
            keyboard = create_card_keyboard(task_id, variants=variants)

            success = await bot.edit_message(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_card,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

            if success:
                logger.info(f"Softened response for task {task_id}, {len(variants)} new variants")
            else:
                await bot.send_message(chat_id, f"✅ Generated {len(variants)} soft responses (see above)")

    except Exception as e:
        logger.error(f"Error softening response for task {task_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


async def callback_more_variants(query: dict, bot: 'TelegramBot'):
    """
    Handle more_variants_{task_id} callback.

    Generate additional response variants.
    """
    user_id = query['from']['id']
    data = query['data']
    chat_id = query['message']['chat']['id']
    message_id = query['message']['message_id']

    # Extract task_id
    try:
        task_id = int(data.split('_')[2])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        return

    await bot.send_message(chat_id, "🔄 Generating more variants... Please wait.")

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.task_dao import TaskDAO
    from ..services.response_generation import ResponseGenerationService
    from ..telegram.cards import format_card, create_card_keyboard

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get task
            task = await TaskDAO.get_task_by_id(conn, task_id)
            if not task:
                await bot.send_message(chat_id, "❌ Task not found")
                return

            message_id_db = task['source_message_id']

            # Generate more variants
            variants = await ResponseGenerationService.generate_variants(task_id, message_id_db)

            if not variants:
                await bot.send_message(chat_id, "❌ Failed to generate variants")
                return

            # Get message for card
            from ..database.dao.message_dao import MessageDAO
            msg = await MessageDAO.get_message_by_id(conn, message_id_db)

            # Reload context
            from ..services.context import get_context_by_channel
            context_messages = await get_context_by_channel(
                conn,
                platform=msg['platform'],
                channel_id=msg['channel_id'],
                server_id=msg.get('server_id'),
                thread_id=msg.get('thread_id'),
                before_message_id=message_id_db,
                limit=10
            )

            # Update card with new variants
            updated_card = format_card(msg, context_messages, variants=variants)
            keyboard = create_card_keyboard(task_id, variants=variants)

            success = await bot.edit_message(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_card,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

            if success:
                logger.info(f"Generated {len(variants)} new variants for task {task_id}")
            else:
                await bot.send_message(chat_id, f"✅ Generated {len(variants)} variants (see above)")

    except Exception as e:
        logger.error(f"Error generating variants for task {task_id}: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


async def callback_unallow_select(query: dict, bot: 'TelegramBot'):
    """
    Handle unallow_select_{allowlist_id} callback.

    User selected a channel to remove from allowlist, show confirmation.
    """
    user_id = query['from']['id']
    data = query['data']
    chat_id = query['message']['chat']['id']

    # Extract allowlist_id from callback data
    try:
        allowlist_id = int(data.split('_')[2])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        await bot.send_message(chat_id, "❌ Error: Invalid callback data")
        return

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.allowlist_dao import AllowlistDAO
    from ..services.allowlist import get_channel_display_name

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get channel details
            channel = await AllowlistDAO.get_channel_by_id(conn, allowlist_id)

            if not channel:
                await bot.send_message(chat_id, "❌ Channel not found in allowlist")
                return

            # Get display name
            display_name = get_channel_display_name(
                channel.get('server_id'),
                channel.get('channel_id')
            )

            # Show confirmation dialog
            confirmation_text = f"""⚠️ Confirm Removal

Are you sure you want to remove this channel from allowlist?

{display_name}

This will stop monitoring messages from this channel."""

            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '✅ Confirm Removal', 'callback_data': f'unallow_confirm_{allowlist_id}'},
                        {'text': '❌ Cancel', 'callback_data': 'unallow_cancel'}
                    ]
                ]
            }

            await bot.send_message(chat_id, confirmation_text, reply_markup=keyboard)
            logger.info(f"User {user_id} requested confirmation to remove allowlist {allowlist_id}")

    except Exception as e:
        logger.error(f"Error processing unallow_select: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


async def callback_unallow_confirm(query: dict, bot: 'TelegramBot'):
    """
    Handle unallow_confirm_{allowlist_id} callback.

    Actually remove the channel from allowlist after confirmation.
    """
    user_id = query['from']['id']
    data = query['data']
    chat_id = query['message']['chat']['id']

    # Extract allowlist_id from callback data
    try:
        allowlist_id = int(data.split('_')[2])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data format: {data}")
        await bot.send_message(chat_id, "❌ Error: Invalid callback data")
        return

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.allowlist_dao import AllowlistDAO
    from ..services.allowlist import get_channel_display_name

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            # Get channel details before removal
            channel = await AllowlistDAO.get_channel_by_id(conn, allowlist_id)

            if not channel:
                await bot.send_message(chat_id, "❌ Channel not found in allowlist")
                return

            channel_id = channel.get('channel_id')
            platform = channel.get('platform', 'discord')

            # Remove channel
            removed = await AllowlistDAO.remove_channel(conn, channel_id, platform=platform)

            if removed:
                display_name = get_channel_display_name(
                    channel.get('server_id'),
                    channel.get('channel_id')
                )

                success_text = f"""✅ Channel Removed from Allowlist

{display_name}

Messages from this channel will no longer be monitored."""

                await bot.send_message(chat_id, success_text)
                logger.info(f"User {user_id} removed allowlist entry {allowlist_id} (channel {channel_id})")
            else:
                await bot.send_message(chat_id, "❌ Failed to remove channel from allowlist")

    except Exception as e:
        logger.error(f"Error confirming unallow: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")


async def callback_unallow_cancel(query: dict, bot: 'TelegramBot'):
    """
    Handle unallow_cancel callback.

    Cancel the unallow operation.
    """
    user_id = query['from']['id']
    chat_id = query['message']['chat']['id']

    await bot.send_message(chat_id, "❌ Operation cancelled. No changes made to allowlist.")
    logger.info(f"User {user_id} cancelled unallow operation")


async def callback_settings_add_channel(query: dict, bot: 'TelegramBot'):
    """
    Handle settings_add_channel callback.

    Guide user to add a channel to allowlist.
    """
    user_id = query['from']['id']
    chat_id = query['message']['chat']['id']

    help_text = """➕ Add Channel to Allowlist

To add a channel, use:
/allow_channel <server_id> <channel_id>

📝 How to get IDs:
1. Enable Developer Mode in Discord settings
2. Right-click server/channel
3. Click "Copy ID"

Example:
/allow_channel 123456789 987654321"""

    await bot.send_message(chat_id, help_text)
    logger.info(f"User {user_id} requested help to add channel")


async def callback_settings_remove_channel(query: dict, bot: 'TelegramBot'):
    """
    Handle settings_remove_channel callback.

    Show allowlist selection for removal.
    """
    user_id = query['from']['id']

    # Reuse the _show_allowlist_selection function
    await _show_allowlist_selection(user_id, bot)
    logger.info(f"User {user_id} requested channel removal from settings")


async def callback_settings_refresh(query: dict, bot: 'TelegramBot'):
    """
    Handle settings_refresh callback.

    Refresh the settings display.
    """
    user_id = query['from']['id']
    message_id = query['message']['message_id']
    chat_id = query['message']['chat']['id']

    from ..database.connection import get_asyncpg_pool
    from ..database.dao.allowlist_dao import AllowlistDAO
    from ..services.allowlist import format_allowlist_display

    db_pool = get_asyncpg_pool()

    try:
        async with db_pool.acquire() as conn:
            from ..database.dao.user_dao import UserDAO

            # Get user
            user = await UserDAO.get_user_by_tg_id(conn, user_id)
            if not user:
                await bot.send_message(user_id, "❌ User not found. Use /start first.")
                return

            user_id_db = user['id']

            # Get Discord status
            discord_status = "❌ Not Connected"
            with bot.db.session_scope() as session:
                from ..database.dao import DiscordDAO
                discord_conn = DiscordDAO.get_discord_connection(session, user_id_db)
                if discord_conn and discord_conn.get('status') == 'connected':
                    discord_status = "✅ Connected"

            # Get DND status
            from ..services.dnd import get_dnd_settings, is_dnd_active
            dnd_settings = await get_dnd_settings(conn, user_id_db)
            dnd_status = "🔕 Enabled" if dnd_settings.get('dnd_enabled') else "🔔 Disabled"
            is_active = await is_dnd_active(conn, user_id_db)
            if is_active:
                dnd_status += " (Active now)"

            # Get allowlist channels
            channels = await AllowlistDAO.get_all_channels(conn, platform='discord', enabled_only=True)
            channel_count = len(channels)

            # Format allowlist display
            if channels:
                allowlist_display = format_allowlist_display(channels, max_display=5)
            else:
                allowlist_display = "Empty"

            # Build settings text
            settings_text = f"""⚙️ Current Settings (Refreshed)

🎮 Discord:
  • Status: {discord_status}

📋 Monitoring:
  • Channels: {channel_count}

Allowlist (top 5):
{allowlist_display}

⏸️ Do Not Disturb:
  • Status: {dnd_status}
  • Schedule: {"Configured" if dnd_settings.get('dnd_schedule_json') else "None"}

🔔 Notifications:
  • Enabled: Yes
  • Context Window: 10 messages"""

            # Create action buttons keyboard
            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '➕ Add Channel', 'callback_data': 'settings_add_channel'},
                        {'text': '➖ Remove Channel', 'callback_data': 'settings_remove_channel'}
                    ],
                    [
                        {'text': '🔕 Toggle DND', 'callback_data': 'toggle_dnd'},
                        {'text': '🔄 Refresh', 'callback_data': 'settings_refresh'}
                    ]
                ]
            }

            # Try to edit the original message
            success = await bot.edit_message(chat_id, message_id, settings_text, reply_markup=keyboard)
            if not success:
                # If edit failed, send a new message
                await bot.send_message(user_id, settings_text, reply_markup=keyboard)

            logger.info(f"Settings refreshed for user {user_id}")

    except Exception as e:
        logger.error(f"Error refreshing settings: {e}", exc_info=True)
        await bot.send_message(user_id, f"❌ Error refreshing settings: {str(e)}")


# =============================================================================
# Edit Reply Callback Handlers
# =============================================================================

async def callback_edit_reply(query: dict, bot: 'TelegramBot'):
    """
    Handle edit_reply_{reply_id} callback.

    Flow:
    1. Extract reply_id from callback_data
    2. Get user_id from query
    3. Validate edit permission via ReplyEditorService
    4. If allowed - set FSM state awaiting_edit_text_{reply_id}
    5. If not - show error with reason
    """
    callback_data = query['data']
    reply_id = int(callback_data.split('_')[2])  # edit_reply_123
    user_id = query['from']['id']
    message_id = query['message']['message_id']
    chat_id = query['message']['chat']['id']

    try:
        from ..database.connection import get_asyncpg_pool
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            from ..services.reply_editor import ReplyEditorService

            # Validate
            validation = await ReplyEditorService.validate_edit_permission(
                conn, reply_id, user_id
            )

            if not validation['can_edit']:
                # Show error
                error_reasons = {
                    'not_found': 'Reply not found',
                    'not_posted': 'Reply not posted yet',
                    'time_expired': f"⏰ Edit window expired (>48h)\n\nReply was posted {validation.get('hours_since_posted', 0):.1f}h ago",
                    'permission_denied': '🚫 You cannot edit this reply',
                    'task_muted': 'Task is muted - cannot edit'
                }
                error_msg = error_reasons.get(validation['reason'], f"Cannot edit: {validation['reason']}")

                await bot.answer_callback_query(
                    query['id'],
                    text=error_msg,
                    show_alert=True
                )
                return

            # Set FSM state
            bot.set_user_state(user_id, f"awaiting_edit_text_{reply_id}", {
                'reply_id': reply_id,
                'original_content': validation['reply']['content'],
                'task_id': validation['task']['id']
            })

            # Prompt for new text
            await bot.send_message(
                chat_id,
                f"✏️ **Edit Reply**\n\n"
                f"Current text:\n{validation['reply']['content'][:200]}...\n\n"
                f"Send me the new text:",
                parse_mode='Markdown'
            )

            await bot.answer_callback_query(query['id'])

    except Exception as e:
        logger.error(f"Error in edit_reply callback: {e}", exc_info=True)
        await bot.answer_callback_query(
            query['id'],
            text=f"Error: {str(e)}",
            show_alert=True
        )


async def handle_edit_text_input(message: dict, bot: 'TelegramBot', state: str):
    """
    Handle awaiting_edit_text_{reply_id} FSM state.

    User typed new text for edited reply.

    Flow:
    1. Get new text from message
    2. Validate length (not empty, not too long)
    3. Show confirmation with preview
    4. Create temp edited reply in DB (not posted yet)
    5. Set FSM state to awaiting_edit_confirm_{new_reply_id}
    """
    user_id = message['from']['id']
    chat_id = message['chat']['id']
    new_content = message.get('text', '')

    state_data = bot.get_user_state(user_id)
    if not state_data:
        await bot.send_message(chat_id, "⚠️ Session expired. Please try again.")
        return

    original_reply_id = state_data['data']['reply_id']
    original_content = state_data['data']['original_content']

    # Validate new text
    if not new_content or not new_content.strip():
        await bot.send_message(
            chat_id,
            "❌ New text cannot be empty. Please send the new text:"
        )
        return

    if len(new_content) > 2000:  # Discord limit
        await bot.send_message(
            chat_id,
            "❌ Text too long (max 2000 characters). Please shorten it:"
        )
        return

    try:
        from ..database.connection import get_asyncpg_pool
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            # Create edited reply (not posted yet)
            from ..database.dao.reply_dao import ReplyDAO
            new_reply_id = await ReplyDAO.create_edited_reply(
                conn, original_reply_id, new_content, user_id
            )

        # Show confirmation
        from .confirmations import create_edit_confirmation
        confirmation = create_edit_confirmation(
            original_content, new_content, new_reply_id
        )

        await bot.send_message(
            chat_id,
            confirmation['text'],
            reply_markup={'inline_keyboard': confirmation['buttons']},
            parse_mode='Markdown'
        )

        # Update FSM
        bot.set_user_state(user_id, f"awaiting_edit_confirm_{new_reply_id}", {
            'new_reply_id': new_reply_id,
            'original_reply_id': original_reply_id
        })

    except Exception as e:
        logger.error(f"Error creating edited reply: {e}", exc_info=True)
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")
        bot.clear_user_state(user_id)


async def callback_confirm_edit(query: dict, bot: 'TelegramBot'):
    """
    Handle confirm_edit_{new_reply_id} callback.

    Flow:
    1. Get new_reply from DB
    2. Get original reply platform_ref
    3. Post to platform via ReplyEditorService.edit_reply()
    4. Update card showing success
    5. Clear FSM state
    """
    callback_data = query['data']
    new_reply_id = int(callback_data.split('_')[2])  # confirm_edit_123
    user_id = query['from']['id']
    chat_id = query['message']['chat']['id']

    try:
        from ..database.connection import get_asyncpg_pool
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            from ..services.reply_editor import ReplyEditorService
            from ..database.dao.reply_dao import ReplyDAO

            # Get new reply to find original
            new_reply = await ReplyDAO.get_reply_by_id(conn, new_reply_id)
            if not new_reply:
                await bot.answer_callback_query(query['id'], text="Reply not found", show_alert=True)
                return

            original_reply_id = new_reply['edit_of']
            new_content = new_reply['content']

            # Get posters (from bot instance or create)
            telegram_poster = bot  # bot itself has send_message
            discord_poster = getattr(bot, 'discord_poster', None)

            # Execute edit via service
            result = await ReplyEditorService.edit_reply(
                conn,
                original_reply_id,
                new_content,
                user_id,
                telegram_poster,
                discord_poster
            )

            if result['success']:
                platform = result['platform']
                await bot.edit_message_text(
                    chat_id,
                    query['message']['message_id'],
                    f"✅ **Reply edited successfully!**\n\n"
                    f"Platform: {platform.capitalize()}\n"
                    f"New reply ID: {result['new_reply_id']}\n\n"
                    f"The message has been updated on {platform}.",
                    parse_mode='Markdown'
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                error_code = result.get('error_code', 'unknown')

                await bot.edit_message_text(
                    chat_id,
                    query['message']['message_id'],
                    f"❌ **Edit failed**\n\n"
                    f"Error: {error_msg}\n"
                    f"Code: {error_code}\n\n"
                    f"Please try again or contact support.",
                    parse_mode='Markdown'
                )

            await bot.answer_callback_query(query['id'])
            bot.clear_user_state(user_id)

    except Exception as e:
        logger.error(f"Error confirming edit: {e}", exc_info=True)
        await bot.answer_callback_query(
            query['id'],
            text=f"Error: {str(e)}",
            show_alert=True
        )


async def callback_cancel_edit(query: dict, bot: 'TelegramBot'):
    """
    Handle cancel_edit_{reply_id} callback.

    Flow:
    1. Delete temp edited reply from DB (if created)
    2. Clear FSM state
    3. Show cancellation message
    """
    callback_data = query['data']
    reply_id = int(callback_data.split('_')[2])  # cancel_edit_123
    user_id = query['from']['id']
    chat_id = query['message']['chat']['id']

    try:
        from ..database.connection import get_asyncpg_pool
        db_pool = get_asyncpg_pool()

        # Delete temp reply if exists
        async with db_pool.acquire() as conn:
            from ..database.dao.reply_dao import ReplyDAO
            await ReplyDAO.delete_reply(conn, reply_id)

        await bot.edit_message_text(
            chat_id,
            query['message']['message_id'],
            "❌ Edit cancelled. No changes were made.",
            parse_mode='Markdown'
        )

        await bot.answer_callback_query(query['id'], text="Edit cancelled")
        bot.clear_user_state(user_id)

    except Exception as e:
        logger.error(f"Error cancelling edit: {e}", exc_info=True)
        await bot.answer_callback_query(query['id'], text="Cancelled")
        bot.clear_user_state(user_id)


async def callback_show_edit_history(query: dict, bot: 'TelegramBot'):
    """
    Handle show_history_{reply_id} callback.

    Shows all edit versions with timestamps.
    """
    callback_data = query['data']
    reply_id = int(callback_data.split('_')[2])  # show_history_123
    chat_id = query['message']['chat']['id']

    try:
        from ..database.connection import get_asyncpg_pool
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            from ..services.reply_editor import ReplyEditorService

            history = await ReplyEditorService.get_edit_history(conn, reply_id)

            if not history:
                await bot.answer_callback_query(
                    query['id'],
                    text="No edit history found",
                    show_alert=True
                )
                return

            # Format history
            lines = ["📊 **Edit History**\n"]
            for idx, item in enumerate(history, 1):
                status_badge = "🟢 CURRENT" if item['is_current'] else "📝 ORIGINAL" if item['is_original'] else f"✏️ EDIT #{idx-1}"
                timestamp = item['created_at'].strftime('%Y-%m-%d %H:%M')

                lines.append(
                    f"{status_badge}\n"
                    f"Time: {timestamp}\n"
                    f"Text: {item['content_preview']}\n"
                )

            history_text = "\n".join(lines)

            await bot.send_message(
                chat_id,
                history_text,
                parse_mode='Markdown'
            )

            await bot.answer_callback_query(query['id'])

    except Exception as e:
        logger.error(f"Error showing history: {e}", exc_info=True)
        await bot.answer_callback_query(
            query['id'],
            text=f"Error: {str(e)}",
            show_alert=True
        )


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
    bot.register_callback_handler('confirm_toggle_dnd', callback_dnd_toggle_confirm)
    bot.register_callback_handler('cancel_toggle_dnd', callback_dnd_toggle_cancel)
    bot.register_callback_handler('cancel_reply', callback_cancel_reply)
    bot.register_callback_handler('use_variant_', callback_use_variant)
    bot.register_callback_handler('soften_', callback_soften)
    bot.register_callback_handler('more_variants_', callback_more_variants)

    # Allowlist management callbacks
    bot.register_callback_handler('unallow_select_', callback_unallow_select)
    bot.register_callback_handler('unallow_confirm_', callback_unallow_confirm)
    bot.register_callback_handler('unallow_cancel', callback_unallow_cancel)

    # Settings callbacks
    bot.register_callback_handler('settings_add_channel', callback_settings_add_channel)
    bot.register_callback_handler('settings_remove_channel', callback_settings_remove_channel)
    bot.register_callback_handler('settings_refresh', callback_settings_refresh)

    # Edit reply callbacks
    bot.register_callback_handler('edit_reply_', callback_edit_reply)
    bot.register_callback_handler('confirm_edit_', callback_confirm_edit)
    bot.register_callback_handler('cancel_edit_', callback_cancel_edit)
    bot.register_callback_handler('show_history_', callback_show_edit_history)

    # Message handlers (FSM)
    bot.register_message_handler(handle_fsm_message)

    logger.info("All handlers registered successfully")
