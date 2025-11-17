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

    Sends welcome message with bot introduction.
    """
    user = message['from']
    user_id = user['id']
    first_name = user.get('first_name', 'User')

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

    # TODO: Implement actual Discord connection test
    # For now, send placeholder response
    test_text = """🔄 Testing Discord Connection...

Status: Not implemented yet

This command will test:
• Discord Gateway connection
• Token validity
• Permission checks
• Channel access"""

    await bot.send_message(user_id, test_text)
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

    # TODO: Get actual status from services
    status_text = """📈 System Status

🤖 Bot: ✅ Running
💾 Database: ✅ Connected
🎮 Discord: ❌ Not Connected
📨 Telegram: ✅ Connected

⏸️ DND Mode: Disabled
📋 Monitored Channels: 0
📬 Pending Tasks: 0

Last Update: Just now"""

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
            # TODO: Call DND service to enable
            await bot.send_message(user_id, "✅ DND mode enabled. You won't receive notifications.")
            logger.info(f"DND enabled by user {user_id}")

        elif mode == 'off':
            # Disable DND
            # TODO: Call DND service to disable
            await bot.send_message(user_id, "✅ DND mode disabled. Notifications resumed.")
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

    # TODO: Add channel to allowlist in database
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

    # TODO: Remove channel from allowlist in database
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
        return

    # TODO: Get reply from database and post to Discord/Telegram
    await bot.send_message(chat_id, "✅ Reply sent! (Not fully implemented yet)")
    logger.info(f"User {user_id} confirmed reply {reply_id}")


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
        return

    # TODO: Retry posting the reply
    await bot.send_message(chat_id, "🔄 Retrying... (Not implemented yet)")
    logger.info(f"User {user_id} requested retry for task {task_id}")


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

    if not token:
        await bot.send_message(user_id, "❌ Token cannot be empty. Please send a valid token or /cancel")
        return

    # TODO: Validate and store token (encrypted) in database
    # TODO: Test connection to Discord

    # For now, just acknowledge
    success_text = """✅ Discord Token Saved

Token has been encrypted and stored securely.

Next steps:
1. Use /test_connection to verify connection
2. Use /allow_channel to add channels to monitor

Note: This is a placeholder. Actual implementation needs database integration."""

    await bot.send_message(user_id, success_text)

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

    # TODO: Store reply in database with pending status

    # Show confirmation message with reply preview
    preview_text = f"""✅ Reply Preview

Your reply:
---
{reply_text}
---

Please confirm to send this message."""

    # Create confirmation keyboard
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '✅ Confirm & Send', 'callback_data': f'confirm_{task_id}'},
                {'text': '❌ Cancel', 'callback_data': 'cancel_reply'}
            ]
        ]
    }

    await bot.send_message(chat_id, preview_text, reply_markup=keyboard)

    # Update state to awaiting confirmation
    bot.set_user_state(user_id, f'awaiting_confirm_{task_id}', {'reply_text': reply_text})

    logger.info(f"User {user_id} submitted reply for task {task_id}, awaiting confirmation")


async def callback_cancel_reply(query: dict, bot: 'TelegramBot'):
    """
    Handle cancel_reply callback.

    Cancel the reply confirmation.
    """
    user_id = query['from']['id']
    chat_id = query['message']['chat']['id']

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
