"""
Telegram message card formatting and rendering.

This module creates rich formatted messages for Telegram:
- Formats Discord messages into Telegram cards with metadata
- Creates inline keyboard layouts for user actions
- Renders message context (previous messages in conversation)
- Formats author information and timestamps
- Handles text truncation and preview generation
- Creates summary cards for message batches
- Formats error messages and system notifications

Cards provide a consistent, user-friendly interface for message review
with all necessary context and action buttons.

Card Format:
```
Discord • Server Name • #channel • @author • 12:34

Context (last 10 messages):
[12:30] user1: Message 1
[12:32] user2: Message 2
...

[Ответить] [Показать больше] [DND]
```
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# Maximum message length for Telegram
MAX_MESSAGE_LENGTH = 4096

# Default context window size
DEFAULT_CONTEXT_SIZE = 10


# =============================================================================
# Card Formatting Functions
# =============================================================================

def format_variants_section(variants: List[Dict]) -> str:
    """
    Format AI response variants for display in card.

    Args:
        variants: List of variant dicts with keys: id, variant_text, confidence_score, provider

    Returns:
        Formatted markdown string
    """
    if not variants:
        return ""

    section = "\n\n🤖 **AI Suggested Responses:**\n"

    for idx, variant in enumerate(variants[:3], 1):  # Max 3 variants
        confidence = variant.get('confidence_score', 0.0)
        confidence_pct = int(confidence * 100)

        # Truncate long responses
        text = variant['variant_text']
        if len(text) > 150:
            text = text[:147] + "..."

        # Format with confidence indicator
        confidence_emoji = "🟢" if confidence >= 0.8 else "🟡" if confidence >= 0.6 else "🔴"

        section += f"\n**Option {idx}** {confidence_emoji} ({confidence_pct}%)\n"
        section += f"_{text}_\n"

    return section


def format_card(message: dict, context_messages: list, variants: Optional[List[Dict]] = None, server_name: Optional[str] = None) -> str:
    """
    Format a message card for Telegram display.

    Args:
        message: Message dict from MessageDAO with keys:
            - platform: 'discord' or 'telegram'
            - server_id: Discord guild ID (optional)
            - channel_id: Channel/chat ID
            - thread_id: Thread ID (optional)
            - author_name: Author username
            - content: Message text
            - platform_created_at: Timestamp
            - has_image: Boolean
        context_messages: List of previous messages (same format)
        variants: Optional list of AI variant dicts
        server_name: Optional server name to display (if None, falls back to truncated server_id)

    Returns:
        Formatted card text string
    """
    # Platform emoji
    platform_emoji = "💬" if message.get('platform') == 'telegram' else "📝"

    # Build header
    header_parts = [platform_emoji, message.get('platform', 'unknown').title()]

    # Add server name for Discord (if available)
    if message.get('server_id'):
        # Use server name if provided, otherwise fall back to truncated server_id
        if server_name:
            header_parts.append(server_name)
        else:
            server_id = str(message['server_id'])
            header_parts.append(f"Server:{server_id[:8]}...")

    # Add channel
    channel_id = message.get('channel_id')
    if channel_id:
        header_parts.append(f"#{str(channel_id)[:8]}...")
    else:
        header_parts.append("#unknown")

    # Add thread if present
    thread_id = message.get('thread_id')
    if thread_id:
        header_parts.append(f"Thread:{str(thread_id)[:8]}...")

    # Add author and time
    timestamp = message.get('platform_created_at')
    if isinstance(timestamp, str):
        time_str = timestamp.split('T')[1][:8] if 'T' in timestamp else "unknown"  # HH:MM:SS
    elif timestamp:
        time_str = timestamp.strftime("%H:%M:%S")
    else:
        time_str = "unknown"

    author_name = message.get('author_name') or 'Unknown'
    header_parts.append(f"@{author_name}")
    header_parts.append(time_str)

    header = " • ".join(header_parts)

    # Build context section
    context_lines = []
    if context_messages:
        context_lines.append("\n📚 Context (recent messages):")
        for ctx_msg in context_messages[-10:]:  # Last 10
            ctx_time = ctx_msg.get('platform_created_at')
            if isinstance(ctx_time, str):
                ctx_time_str = ctx_time.split('T')[1][:5] if 'T' in ctx_time else "??"  # HH:MM
            elif ctx_time:
                ctx_time_str = ctx_time.strftime("%H:%M")
            else:
                ctx_time_str = "??"

            ctx_content = ctx_msg.get('content', '')
            if len(ctx_content) > 100:
                ctx_content = ctx_content[:100] + "..."  # Truncate long messages

            ctx_author = ctx_msg.get('author_name', 'Unknown')
            context_lines.append(f"[{ctx_time_str}] {ctx_author}: {ctx_content}")

    context_text = "\n".join(context_lines) if context_lines else ""

    # Build message section
    message_content = message.get('content') or '[No content]'

    # Add attachment section if message has images/files
    attachment_text = ""
    if message.get('has_image') or message.get('attachments'):
        # Get attachments from message dict if available
        if 'attachments' in message and message['attachments']:
            attachment_text = "\n\n📎 Attachments:"
            for att in message['attachments']:
                if att['kind'] == 'image':
                    attachment_text += f"\n🖼 [Image]({att['ref']})"
                else:
                    # Get filename from meta if available
                    filename = att.get('filename', 'unknown')
                    if not filename or filename == 'unknown':
                        # Try to parse from meta JSON
                        meta = att.get('meta')
                        if meta:
                            try:
                                import json
                                meta_dict = json.loads(meta) if isinstance(meta, str) else meta
                                filename = meta_dict.get('filename', 'unknown')
                            except:
                                pass
                    attachment_text += f"\n📄 [File: {filename}]({att['ref']})"
        else:
            # Fallback if attachments array not loaded
            attachment_text = "\n\n📎 (Has attachments)"

    message_section = f"\n\n💬 Current Message:\n{message_content}{attachment_text}"

    # Add variants section if provided
    variants_section = ""
    if variants:
        variants_section = format_variants_section(variants)

    # Build card
    card = f"{header}{context_text}{message_section}{variants_section}"

    # Truncate if too long
    if len(card) > MAX_MESSAGE_LENGTH - 100:
        card = card[:MAX_MESSAGE_LENGTH - 200] + "\n\n[Message truncated...]"

    # Add footer
    card += "\n\n💡 Click 'Показать больше' for full history"

    return card


def _format_context(context: List[Dict[str, Any]]) -> str:
    """
    Format context messages into a readable list.

    Args:
        context: List of message dictionaries

    Returns:
        Formatted context string
    """
    if not context:
        return "Context: No previous messages\n"

    context_lines = [f"Context (last {len(context)} messages):"]

    for msg in context:
        author = msg.get('author', 'Unknown')
        content = msg.get('content', '')
        timestamp = msg.get('timestamp', datetime.utcnow())

        # Format timestamp
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                timestamp = datetime.utcnow()

        time_str = timestamp.strftime('%H:%M')

        # Truncate long messages in context
        if len(content) > 100:
            content = content[:97] + "..."

        context_lines.append(f"[{time_str}] {author}: {content}")

    return "\n".join(context_lines) + "\n"


def format_reply_confirmation(
    reply_text: str,
    original_message: str,
    platform: str = "Discord",
    channel_name: str = "unknown-channel"
) -> str:
    """
    Format a reply confirmation card.

    Args:
        reply_text: The reply text to send
        original_message: The original message being replied to
        platform: Platform name
        channel_name: Channel name

    Returns:
        Formatted confirmation card
    """
    card = f"""✅ Reply Confirmation

Platform: {platform}
Channel: #{channel_name}

Original Message:
---
{_truncate_text(original_message, 200)}
---

Your Reply:
---
{_truncate_text(reply_text, 500)}
---

Please confirm to send this message."""

    return card


def format_error_card(
    error_message: str,
    task_id: Optional[int] = None,
    details: Optional[str] = None
) -> str:
    """
    Format an error notification card.

    Args:
        error_message: Main error message
        task_id: Optional task ID related to the error
        details: Optional additional error details

    Returns:
        Formatted error card
    """
    card = f"❌ Error\n\n{error_message}"

    if task_id:
        card += f"\n\nTask ID: {task_id}"

    if details:
        card += f"\n\nDetails:\n{_truncate_text(details, 500)}"

    return card


def format_success_card(
    message: str,
    task_id: Optional[int] = None
) -> str:
    """
    Format a success notification card.

    Args:
        message: Success message
        task_id: Optional task ID related to success

    Returns:
        Formatted success card
    """
    card = f"✅ Success\n\n{message}"

    if task_id:
        card += f"\n\nTask ID: {task_id}"

    return card


def _truncate_text(text: str, max_length: int) -> str:
    """
    Truncate text to maximum length with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."


def format_server_list_card(servers: List[Dict], allowlist_stats: Dict) -> str:
    """
    Format a list of Discord servers with allowlist statistics.

    Args:
        servers: List of server dicts with keys:
            - id: Server ID
            - name: Server name
            - icon: Server icon URL (optional)
        allowlist_stats: Dict mapping server_id -> count of allowed channels

    Returns:
        Formatted server list card

    Example:
        >>> servers = [
        ...     {'id': '123', 'name': 'My Server'},
        ...     {'id': '456', 'name': 'Test Server'}
        ... ]
        >>> stats = {'123': 5, '456': 0}
        >>> card = format_server_list_card(servers, stats)
    """
    if not servers:
        return "🌐 Your Discord Servers\n\nNo servers found.\n\nPlease check your Discord connection."

    card = "🌐 Your Discord Servers\n"

    total_servers = len(servers)
    total_allowed = 0

    for server in servers:
        server_id = str(server.get('id', ''))
        server_name = server.get('name', 'Unknown Server')
        allowed_count = allowlist_stats.get(server_id, 0)
        total_allowed += allowed_count

        # Truncate long server names
        if len(server_name) > 40:
            server_name = server_name[:37] + "..."

        # Format with emoji and count
        card += f"\n🔷 {server_name} - {allowed_count} channel{'s' if allowed_count != 1 else ''} allowed"

    # Add summary footer
    card += f"\n\n📊 Total: {total_servers} server{'s' if total_servers != 1 else ''}, {total_allowed} channel{'s' if total_allowed != 1 else ''} allowed"

    return card


def format_channel_list_card(server: Dict, channels: List[Dict], allowlist: List[str]) -> str:
    """
    Format a list of channels in a server with allowlist status.

    Args:
        server: Server dict with keys:
            - id: Server ID
            - name: Server name
        channels: List of channel dicts with keys:
            - id: Channel ID
            - name: Channel name
            - type: Channel type (0=text, 2=voice, 4=category, 5=announcement, 10-12=thread variants)
            - parent_id: Parent category ID (optional)
        allowlist: List of channel IDs that are currently allowed

    Returns:
        Formatted channel list card

    Example:
        >>> server = {'id': '123', 'name': 'My Server'}
        >>> channels = [
        ...     {'id': '1', 'name': 'general', 'type': 0},
        ...     {'id': '2', 'name': 'random', 'type': 0}
        ... ]
        >>> allowlist = ['1']
        >>> card = format_channel_list_card(server, channels, allowlist)
    """
    server_name = server.get('name', 'Unknown Server')
    if len(server_name) > 50:
        server_name = server_name[:47] + "..."

    card = f"📡 Channels in \"{server_name}\"\n"

    if not channels:
        return card + "\nNo channels found in this server."

    # Channel type mapping
    type_emojis = {
        0: '📝',   # Text channel
        2: '🔊',   # Voice channel
        4: '📁',   # Category
        5: '📢',   # Announcement channel
        10: '🧵',  # Announcement thread
        11: '🧵',  # Public thread
        12: '🧵',  # Private thread
        13: '🎤',  # Stage channel
        15: '🗂️',  # Forum channel
    }

    type_labels = {
        0: 'Text Channels',
        2: 'Voice Channels',
        5: 'Announcement Channels',
        10: 'Threads',
        11: 'Threads',
        12: 'Threads',
        13: 'Stage Channels',
        15: 'Forum Channels',
    }

    # Group channels by type (exclude categories)
    channels_by_type = {}
    for channel in channels:
        channel_type = channel.get('type', 0)
        if channel_type == 4:  # Skip categories
            continue

        # Normalize thread types
        if channel_type in [10, 11, 12]:
            channel_type = 11  # Group all threads together

        if channel_type not in channels_by_type:
            channels_by_type[channel_type] = []

        channels_by_type[channel_type].append(channel)

    # Format channels by type
    total_channels = 0
    total_allowed = 0

    for channel_type in sorted(channels_by_type.keys()):
        type_label = type_labels.get(channel_type, 'Other Channels')
        type_emoji = type_emojis.get(channel_type, '📝')

        card += f"\n{type_emoji} {type_label}:\n"

        for channel in channels_by_type[channel_type]:
            channel_id = str(channel.get('id', ''))
            channel_name = channel.get('name', 'unknown')

            # Check if channel is in allowlist
            is_allowed = channel_id in allowlist
            status_emoji = "✅" if is_allowed else "❌"
            status_text = "allowed" if is_allowed else "not allowed"

            # Truncate long channel names
            if len(channel_name) > 35:
                channel_name = channel_name[:32] + "..."

            # Add # prefix for text channels
            prefix = "#" if channel_type in [0, 5] else ""

            card += f"{status_emoji} {prefix}{channel_name} ({status_text})\n"

            total_channels += 1
            if is_allowed:
                total_allowed += 1

    # Add summary footer
    card += f"\n📊 Total: {total_channels} channel{'s' if total_channels != 1 else ''} ({total_allowed} allowed)"

    return card


# =============================================================================
# Keyboard Creation Functions
# =============================================================================

def create_card_keyboard(
    task_id: int,
    show_more: bool = True,
    variants: Optional[List[Dict]] = None,
    show_ai_buttons: bool = True,
    posted_reply: Optional[Dict] = None
) -> dict:
    """
    Create inline keyboard for message card.

    Args:
        task_id: Task ID for callback data
        show_more: Whether to show "Показать больше" button (default: True)
        variants: AI response variants (if available)
        show_ai_buttons: Show AI-related buttons (Soften, More variants)
        posted_reply: Posted reply dict (optional) - enables Edit button

    Returns:
        Telegram inline keyboard dict

    Note:
        Edit button shows only if posted_reply provided and < 48h since posting
    """
    keyboard = {'inline_keyboard': []}

    # Variant selection buttons (if variants provided)
    if variants:
        variant_row = []
        for idx, variant in enumerate(variants[:3], 1):
            variant_id = variant['id']
            confidence = int(variant.get('confidence_score', 0) * 100)
            variant_row.append({
                'text': f'✨ Use Option {idx} ({confidence}%)',
                'callback_data': f'use_variant_{variant_id}'
            })

        # Split into rows if more than 1 variant
        if len(variant_row) > 1:
            keyboard['inline_keyboard'].append([variant_row[0]])
            if len(variant_row) > 1:
                keyboard['inline_keyboard'].append(variant_row[1:])
        else:
            keyboard['inline_keyboard'].append(variant_row)

    # Main action row
    main_row = [
        {'text': '✍️ Ответить', 'callback_data': f'reply_{task_id}'}
    ]
    if show_more:
        main_row.append({'text': '📖 Показать больше', 'callback_data': f'more_{task_id}'})
    keyboard['inline_keyboard'].append(main_row)

    # AI action row (if enabled)
    if show_ai_buttons:
        ai_row = [
            {'text': '🎨 Soften', 'callback_data': f'soften_{task_id}'},
            {'text': '🔄 More Variants', 'callback_data': f'more_variants_{task_id}'}
        ]
        keyboard['inline_keyboard'].append(ai_row)

    # Context row
    context_row = [
        {'text': '🔕 DND', 'callback_data': 'toggle_dnd'}
    ]
    keyboard['inline_keyboard'].append(context_row)

    # Edit buttons (if reply was posted and < 48 hours)
    if posted_reply and posted_reply.get('posted_at'):
        from datetime import timezone

        posted_at = posted_reply['posted_at']

        # Handle both datetime and string
        if isinstance(posted_at, str):
            posted_at = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))

        # Calculate hours since posting
        now = datetime.now(timezone.utc)
        hours_since = (now - posted_at).total_seconds() / 3600

        # Show Edit button only if < 48 hours
        if hours_since < 48:
            reply_id = posted_reply['id']
            keyboard['inline_keyboard'].append([
                {'text': '✏️ Edit Reply', 'callback_data': f'edit_reply_{reply_id}'}
            ])
            keyboard['inline_keyboard'].append([
                {'text': '📊 Show History', 'callback_data': f'show_history_{reply_id}'}
            ])

    return keyboard


def create_confirmation_keyboard(task_id: int) -> dict:
    """
    Create inline keyboard for reply confirmation.

    Args:
        task_id: Task ID for callback data

    Returns:
        Inline keyboard markup dictionary
    """
    keyboard = [
        [
            {'text': '✅ Подтвердить и отправить', 'callback_data': f'confirm_{task_id}'},
            {'text': '❌ Отменить', 'callback_data': 'cancel_reply'}
        ]
    ]

    return {'inline_keyboard': keyboard}


def create_settings_keyboard() -> dict:
    """
    Create inline keyboard for settings menu.

    Returns:
        Inline keyboard markup dictionary
    """
    keyboard = [
        [
            {'text': '🎮 Discord Settings', 'callback_data': 'settings_discord'},
            {'text': '⏸️ DND Settings', 'callback_data': 'settings_dnd'}
        ],
        [
            {'text': '📋 Allowlist', 'callback_data': 'settings_allowlist'},
            {'text': '🔔 Notifications', 'callback_data': 'settings_notifications'}
        ]
    ]

    return {'inline_keyboard': keyboard}


def create_dnd_keyboard(is_enabled: bool = False) -> dict:
    """
    Create inline keyboard for DND settings.

    Args:
        is_enabled: Current DND status

    Returns:
        Inline keyboard markup dictionary
    """
    toggle_text = '✅ Disable DND' if is_enabled else '⏸️ Enable DND'

    keyboard = [
        [
            {'text': toggle_text, 'callback_data': 'toggle_dnd'}
        ],
        [
            {'text': '⏰ Set Schedule', 'callback_data': 'dnd_schedule'},
            {'text': '🔙 Back', 'callback_data': 'settings_main'}
        ]
    ]

    return {'inline_keyboard': keyboard}


def create_pagination_keyboard(
    task_id: int,
    has_prev: bool = False,
    has_next: bool = False,
    current_page: int = 1,
    total_pages: int = 1
) -> dict:
    """
    Create pagination keyboard for context viewing.

    Args:
        task_id: Task ID for callback data
        has_prev: Whether previous page exists
        has_next: Whether next page exists
        current_page: Current page number
        total_pages: Total number of pages

    Returns:
        Inline keyboard markup dictionary
    """
    keyboard = []

    # Pagination row
    pagination_row = []

    if has_prev:
        pagination_row.append({'text': '◀️ Prev', 'callback_data': f'page_{task_id}_{current_page - 1}'})

    pagination_row.append({'text': f'📄 {current_page}/{total_pages}', 'callback_data': 'noop'})

    if has_next:
        pagination_row.append({'text': 'Next ▶️', 'callback_data': f'page_{task_id}_{current_page + 1}'})

    keyboard.append(pagination_row)

    # Action row
    keyboard.append([
        {'text': '✍️ Ответить', 'callback_data': f'reply_{task_id}'},
        {'text': '🔙 Back to Card', 'callback_data': f'card_{task_id}'}
    ])

    return {'inline_keyboard': keyboard}


def create_server_list_keyboard(servers: List[Dict]) -> dict:
    """
    Create inline keyboard for Discord server selection.

    Args:
        servers: List of server dicts with keys:
            - id: Server ID
            - name: Server name

    Returns:
        Telegram inline keyboard dict with server selection buttons

    Example:
        >>> servers = [
        ...     {'id': '123', 'name': 'My Server'},
        ...     {'id': '456', 'name': 'Test Server'}
        ... ]
        >>> keyboard = create_server_list_keyboard(servers)
    """
    keyboard = {'inline_keyboard': []}

    # Add one button per server (each on its own row)
    for server in servers:
        server_id = str(server.get('id', ''))
        server_name = server.get('name', 'Unknown Server')

        # Truncate server name to fit in button (max ~40 chars for readability)
        if len(server_name) > 35:
            server_name = server_name[:32] + "..."

        keyboard['inline_keyboard'].append([
            {'text': f'🔷 {server_name}', 'callback_data': f'server_select_{server_id}'}
        ])

    # Add refresh button at bottom
    keyboard['inline_keyboard'].append([
        {'text': '🔄 Refresh Cache', 'callback_data': 'refresh_server_cache'}
    ])

    return keyboard


def create_channel_list_keyboard(
    server_id: str,
    channels: List[Dict],
    selected: List[str],
    allowlist: List[str]
) -> dict:
    """
    Create inline keyboard for channel selection and allowlist management.

    Args:
        server_id: Server ID
        channels: List of channel dicts with keys:
            - id: Channel ID
            - name: Channel name
            - type: Channel type
        selected: List of currently selected channel IDs (for multi-select UI)
        allowlist: List of channel IDs currently in allowlist

    Returns:
        Telegram inline keyboard dict with channel toggle buttons

    Features:
        - Shows ✅/❌ based on current allowlist status
        - Shows ☑️/☐ for multi-select state
        - Handles pagination if > 15 channels
        - Includes action buttons: Select All, Save, Cancel

    Example:
        >>> channels = [
        ...     {'id': '1', 'name': 'general', 'type': 0},
        ...     {'id': '2', 'name': 'random', 'type': 0}
        ... ]
        >>> keyboard = create_channel_list_keyboard('123', channels, ['1'], ['1'])
    """
    keyboard = {'inline_keyboard': []}

    # Limit to 15 channels per page to avoid keyboard size limits
    MAX_CHANNELS_PER_PAGE = 15
    display_channels = channels[:MAX_CHANNELS_PER_PAGE]

    # Add channel toggle buttons
    for channel in display_channels:
        channel_id = str(channel.get('id', ''))
        channel_name = channel.get('name', 'unknown')
        channel_type = channel.get('type', 0)

        # Determine status emoji (allowlist status)
        is_allowed = channel_id in allowlist
        status_emoji = "✅" if is_allowed else "❌"

        # Determine selection emoji (current selection state)
        is_selected = channel_id in selected
        select_emoji = "☑️" if is_selected else "☐"

        # Add # prefix for text channels
        prefix = "#" if channel_type in [0, 5] else ""

        # Truncate channel name to fit in button
        if len(channel_name) > 25:
            channel_name = channel_name[:22] + "..."

        button_text = f"{status_emoji} {select_emoji} {prefix}{channel_name}"

        keyboard['inline_keyboard'].append([
            {'text': button_text, 'callback_data': f'channel_toggle_{channel_id}'}
        ])

    # Add pagination info if there are more channels
    if len(channels) > MAX_CHANNELS_PER_PAGE:
        remaining = len(channels) - MAX_CHANNELS_PER_PAGE
        keyboard['inline_keyboard'].append([
            {'text': f'⚠️ Showing first {MAX_CHANNELS_PER_PAGE} of {len(channels)} channels', 'callback_data': 'noop'}
        ])

    # Add action buttons row
    action_row = [
        {'text': '☑️ Select All', 'callback_data': f'channel_select_all_{server_id}'},
        {'text': '💾 Save', 'callback_data': f'channel_save_{server_id}'}
    ]
    keyboard['inline_keyboard'].append(action_row)

    # Add cancel button
    keyboard['inline_keyboard'].append([
        {'text': '❌ Cancel', 'callback_data': 'channel_cancel'}
    ])

    return keyboard


# =============================================================================
# Card Update Functions
# =============================================================================

async def update_card_with_status(
    bot,
    chat_id: int,
    message_id: int,
    status_text: str,
    keep_keyboard: bool = False
):
    """
    Update card with status message (success/error).

    Args:
        bot: TelegramBot instance
        chat_id: Chat ID
        message_id: Message ID to update
        status_text: Status to append
        keep_keyboard: Whether to keep the keyboard

    Note:
        This is a helper function that will be fully implemented
        when integrated with the TelegramBot class. For now, it
        provides the signature and documentation for the feature.
    """
    # TODO: Implementation will be completed during integration
    # Steps:
    # 1. Get current message text via bot.get_message() or cache
    # 2. Append status_text to the message
    # 3. Update message via bot.edit_message()
    # 4. Optionally keep or remove keyboard based on keep_keyboard flag
    pass


def update_card_with_more_context(
    original_card: str,
    additional_context: List[Dict[str, Any]]
) -> str:
    """
    Update card with additional context messages.

    Args:
        original_card: Original card text
        additional_context: Additional context messages to add

    Returns:
        Updated card text
    """
    # Extract the card header (first line)
    lines = original_card.split('\n')
    header = lines[0] if lines else ""

    # Format additional context
    context_text = _format_context(additional_context)

    # Find the "New Message" section and preserve it
    message_section = ""
    in_message = False

    for line in lines:
        if line.startswith('📩 New Message:'):
            in_message = True

        if in_message:
            message_section += line + "\n"

    # Rebuild card
    updated_card = f"{header}\n\n{context_text}{message_section}"

    # Truncate if necessary
    if len(updated_card) > MAX_MESSAGE_LENGTH - 100:
        updated_card = updated_card[:MAX_MESSAGE_LENGTH - 200] + "\n\n[Message truncated...]"

    return updated_card


def update_card_status(
    original_card: str,
    status: str,
    status_emoji: str = "ℹ️"
) -> str:
    """
    Update card with status message.

    Args:
        original_card: Original card text
        status: Status message to add
        status_emoji: Emoji for status

    Returns:
        Updated card with status
    """
    status_line = f"\n\n{status_emoji} Status: {status}"

    # Check if we need to truncate
    if len(original_card) + len(status_line) > MAX_MESSAGE_LENGTH:
        # Truncate original card to make room
        max_card_length = MAX_MESSAGE_LENGTH - len(status_line) - 50
        original_card = original_card[:max_card_length] + "\n[Truncated...]"

    return original_card + status_line


# =============================================================================
# Batch Card Functions
# =============================================================================

def format_batch_summary_card(
    tasks: List[Dict[str, Any]],
    platform: str = "Discord"
) -> str:
    """
    Format a summary card for multiple tasks.

    Args:
        tasks: List of task dictionaries
        platform: Platform name

    Returns:
        Formatted summary card
    """
    count = len(tasks)

    card = f"""📬 New Messages Summary

Platform: {platform}
Count: {count} message(s)

Messages:
"""

    for i, task in enumerate(tasks[:10], 1):  # Show max 10 in summary
        author = task.get('author', 'Unknown')
        content = task.get('content', '')
        preview = _truncate_text(content, 50)

        card += f"\n{i}. @{author}: {preview}"

    if count > 10:
        card += f"\n\n... and {count - 10} more"

    card += "\n\nIndividual cards will be sent shortly."

    return card


# =============================================================================
# Helper Functions
# =============================================================================

def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.

    Note: Currently we use plain text (no parse_mode),
    so this is not needed. Kept for future use.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

    for char in special_chars:
        text = text.replace(char, f'\\{char}')

    return text


def format_timestamp(timestamp: datetime, include_date: bool = False) -> str:
    """
    Format timestamp for card display.

    Args:
        timestamp: Datetime object
        include_date: Whether to include date

    Returns:
        Formatted timestamp string
    """
    if include_date:
        return timestamp.strftime('%Y-%m-%d %H:%M')
    else:
        return timestamp.strftime('%H:%M')


def create_simple_card(
    title: str,
    content: str,
    emoji: str = "📝"
) -> str:
    """
    Create a simple card with title and content.

    Args:
        title: Card title
        content: Card content
        emoji: Title emoji

    Returns:
        Formatted card
    """
    return f"{emoji} {title}\n\n{content}"


# =============================================================================
# Search Result Formatting Functions
# =============================================================================

def format_search_results(
    results: List[Dict[str, Any]],
    page: int,
    total_results: int,
    total_pages: int,
    filters: Dict[str, Any],
    query_string: str
) -> str:
    """
    Format search results for Telegram display.

    Args:
        results: List of message dictionaries from search
        page: Current page number
        total_results: Total number of matching messages
        total_pages: Total number of pages
        filters: Parsed filter dictionary
        query_string: Original search query string

    Returns:
        Formatted search results card

    Example:
        >>> results = [
        ...     {'author_name': 'john', 'content': 'Hello world', 'created_at': datetime.now()},
        ...     {'author_name': 'alice', 'content': 'Hi there', 'created_at': datetime.now()}
        ... ]
        >>> card = format_search_results(
        ...     results, page=1, total_results=25, total_pages=3,
        ...     filters={'text_query': 'hello'}, query_string='hello'
        ... )
    """
    from ..services.search import SearchService

    # Header
    card = f"🔍 Search Results\n"
    card += f"Query: \"{query_string}\"\n"
    card += f"\n📊 Page {page}/{total_pages} • Total: {total_results} message{'s' if total_results != 1 else ''}\n"

    # Show active filters
    if filters:
        filters_summary = SearchService.format_filters_summary(filters)
        card += f"\n📌 Filters:\n{filters_summary}\n"

    # Show results
    if not results:
        card += "\n❌ No messages found matching your search.\n"
        card += "\n💡 Try:\n"
        card += "• Using different search terms\n"
        card += "• Removing some filters\n"
        card += "• Checking date ranges\n"
        card += "\nUse /search_help for syntax help."
    else:
        card += "\n📝 Results:\n"

        for idx, msg in enumerate(results, 1):
            # Format timestamp
            timestamp = msg.get('created_at') or msg.get('platform_created_at')
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = None

            if timestamp:
                time_str = timestamp.strftime('%Y-%m-%d %H:%M')
            else:
                time_str = "Unknown date"

            # Platform emoji
            platform_emoji = "💬" if msg.get('platform') == 'telegram' else "📝"

            # Author
            author = msg.get('author_name', 'Unknown')

            # Content preview with highlighting
            content = msg.get('content', '[No content]')
            text_query = filters.get('text_query')
            content_preview = SearchService.highlight_text(content, text_query, max_length=100)

            # Channel info
            channel_id = msg.get('channel_id', '')
            channel_short = str(channel_id)[:8] if channel_id else 'unknown'

            # Build result entry
            card += f"\n{idx}. {platform_emoji} {author} • {time_str}\n"
            card += f"   Channel: {channel_short}... • ID: {msg['id']}\n"
            card += f"   {content_preview}\n"

        # Add footer
        card += f"\n💡 Use pagination buttons below to navigate"
        card += f"\n🔍 Use /search_help for syntax help"

    # Truncate if too long
    if len(card) > MAX_MESSAGE_LENGTH - 100:
        card = card[:MAX_MESSAGE_LENGTH - 200] + "\n\n[Results truncated...]"

    return card


def create_search_keyboard(
    query_string: str,
    page: int,
    total_pages: int,
    has_prev: bool,
    has_next: bool
) -> dict:
    """
    Create pagination keyboard for search results.

    Args:
        query_string: Original search query (encoded in callback data)
        page: Current page number
        total_pages: Total number of pages
        has_prev: Whether previous page exists
        has_next: Whether next page exists

    Returns:
        Telegram inline keyboard dict

    Example:
        >>> keyboard = create_search_keyboard(
        ...     query_string="hello author:john",
        ...     page=2,
        ...     total_pages=5,
        ...     has_prev=True,
        ...     has_next=True
        ... )
    """
    keyboard = {'inline_keyboard': []}

    # Pagination row
    pagination_row = []

    if has_prev:
        prev_page = page - 1
        pagination_row.append({
            'text': '◀️ Previous',
            'callback_data': f'search_page_{prev_page}'
        })

    # Page indicator (non-clickable)
    pagination_row.append({
        'text': f'📄 {page}/{total_pages}',
        'callback_data': 'noop'
    })

    if has_next:
        next_page = page + 1
        pagination_row.append({
            'text': 'Next ▶️',
            'callback_data': f'search_page_{next_page}'
        })

    keyboard['inline_keyboard'].append(pagination_row)

    # Action row
    action_row = [
        {'text': '🔍 New Search', 'callback_data': 'search_new'},
        {'text': '❓ Help', 'callback_data': 'search_help'}
    ]
    keyboard['inline_keyboard'].append(action_row)

    return keyboard


def format_search_help_card() -> str:
    """
    Format help card for search syntax.

    Returns:
        Formatted help card string
    """
    from ..services.search import SearchService
    return SearchService.get_search_help_text()


# =============================================================================
# Example Usage (for testing)
# =============================================================================

def create_example_card() -> tuple[str, dict]:
    """
    Create an example card for testing with database model format.

    Returns:
        Tuple of (card_text, keyboard)
    """
    # Example message from MessageDAO
    message = {
        'platform': 'discord',
        'server_id': '123456789012345678',
        'channel_id': '987654321098765432',
        'thread_id': None,
        'author_name': 'john_doe',
        'content': 'This is a test message that needs moderation review.',
        'platform_created_at': '2025-11-18T14:30:45.123456',
        'has_image': False
    }

    # Example context messages
    context_messages = [
        {
            'platform': 'discord',
            'channel_id': '987654321098765432',
            'author_name': 'alice',
            'content': 'Hey everyone!',
            'platform_created_at': '2025-11-18T14:28:12.123456',
            'has_image': False
        },
        {
            'platform': 'discord',
            'channel_id': '987654321098765432',
            'author_name': 'bob',
            'content': 'Hello Alice! How are you doing today?',
            'platform_created_at': '2025-11-18T14:29:30.123456',
            'has_image': False
        }
    ]

    card_text = format_card(
        message=message,
        context_messages=context_messages
    )

    keyboard = create_card_keyboard(task_id=123)

    return card_text, keyboard


def format_stats_card(stats: dict, period_days: int) -> str:
    """
    Format comprehensive statistics report for Telegram display.

    Args:
        stats: Statistics dictionary from StatsService.generate_stats_report()
        period_days: Number of days in the reporting period

    Returns:
        Formatted stats card text

    Example:
        >>> from ..services.stats import StatsService
        >>> report = await StatsService.generate_stats_report(conn, user_id=1, period_days=30)
        >>> card = format_stats_card(report, 30)
    """
    from ..services.stats import StatsService

    # Header
    card = f"📊 Statistics Report\n"
    card += f"Period: Last {period_days} day{'s' if period_days != 1 else ''}\n"
    card += f"Generated: {stats['generated_at'].strftime('%Y-%m-%d %H:%M UTC')}\n"

    # Task Overview Section
    card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    card += f"📋 Task Overview\n"
    card += f"━━━━━━━━━━━━━━━━━━━━\n"

    task_stats = stats['task_stats']
    total_tasks = task_stats['total']
    completed = task_stats['completed']
    pending = task_stats['pending']

    card += f"Total Tasks: {StatsService.format_number(total_tasks)}\n"
    card += f"✅ Completed: {StatsService.format_number(completed)}\n"
    card += f"⏳ Pending: {StatsService.format_number(pending)}\n"

    if task_stats['muted'] > 0:
        card += f"🔕 Muted: {StatsService.format_number(task_stats['muted'])}\n"
    if task_stats['error'] > 0:
        card += f"❌ Error: {StatsService.format_number(task_stats['error'])}\n"

    if total_tasks > 0:
        completion_rate = StatsService.calculate_completion_rate(completed, total_tasks)
        progress_bar = StatsService.create_progress_bar(completed, total_tasks, width=10)
        card += f"\nCompletion Rate: {StatsService.format_percentage(completion_rate)}\n"
        card += f"{progress_bar}\n"

    # Response Time Section
    card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    card += f"⏱️ Response Time\n"
    card += f"━━━━━━━━━━━━━━━━━━━━\n"

    avg_time = stats['response_time']['average']
    if avg_time is not None:
        card += f"Average: {StatsService.format_duration(avg_time)}\n"

        percentiles = stats['response_time']['percentiles']
        if percentiles['p50'] is not None:
            card += f"P50 (Median): {StatsService.format_duration(percentiles['p50'])}\n"
        if percentiles['p95'] is not None:
            card += f"P95: {StatsService.format_duration(percentiles['p95'])}\n"
        if percentiles['p99'] is not None:
            card += f"P99: {StatsService.format_duration(percentiles['p99'])}\n"

        # Distribution
        distribution = stats['response_time']['distribution']
        dist_total = sum(distribution.values())
        if dist_total > 0:
            card += f"\nDistribution:\n"
            card += f"  < 5 min:  {distribution['under_5min']:3d} {StatsService.create_progress_bar(distribution['under_5min'], dist_total, 5)}\n"
            card += f"  < 30 min: {distribution['under_30min']:3d} {StatsService.create_progress_bar(distribution['under_30min'], dist_total, 5)}\n"
            card += f"  < 1 hour: {distribution['under_1h']:3d} {StatsService.create_progress_bar(distribution['under_1h'], dist_total, 5)}\n"
            card += f"  < 6 hour: {distribution['under_6h']:3d} {StatsService.create_progress_bar(distribution['under_6h'], dist_total, 5)}\n"
            card += f"  > 6 hour: {distribution['over_6h']:3d} {StatsService.create_progress_bar(distribution['over_6h'], dist_total, 5)}\n"
    else:
        card += "No response data available\n"

    # Channel Activity Section
    card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    card += f"📡 Channel Activity\n"
    card += f"━━━━━━━━━━━━━━━━━━━━\n"

    channel_load = stats['channel_load']
    if channel_load:
        card += f"Top {min(len(channel_load), 5)} busiest channels:\n\n"
        for idx, channel in enumerate(channel_load[:5], 1):
            platform_emoji = "💬" if channel['platform'] == 'telegram' else "📝"
            channel_id_short = StatsService.format_channel_id(channel['channel_id'], 12)
            msg_count = channel['message_count']
            card += f"{idx}. {platform_emoji} {channel_id_short}\n"
            card += f"   Messages: {StatsService.format_number(msg_count)}\n"
    else:
        card += "No channel activity data\n"

    # Platform Breakdown
    platform_breakdown = stats['platform_breakdown']
    total_messages = sum(platform_breakdown.values())
    if total_messages > 0:
        card += f"\nPlatform Breakdown:\n"
        discord_count = platform_breakdown.get('discord', 0)
        telegram_count = platform_breakdown.get('telegram', 0)

        if discord_count > 0:
            discord_pct = (discord_count / total_messages) * 100
            card += f"📝 Discord: {StatsService.format_number(discord_count)} ({discord_pct:.0f}%)\n"

        if telegram_count > 0:
            telegram_pct = (telegram_count / total_messages) * 100
            card += f"💬 Telegram: {StatsService.format_number(telegram_count)} ({telegram_pct:.0f}%)\n"

    # LLM Usage Section
    card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    card += f"🤖 LLM Usage\n"
    card += f"━━━━━━━━━━━━━━━━━━━━\n"

    llm_stats = stats['llm_usage']
    total_requests = llm_stats['total_requests']

    if total_requests > 0:
        card += f"Total Requests: {StatsService.format_number(total_requests)}\n"
        card += f"✅ Successful: {StatsService.format_number(llm_stats['successful_requests'])}\n"
        if llm_stats['failed_requests'] > 0:
            card += f"❌ Failed: {StatsService.format_number(llm_stats['failed_requests'])}\n"

        success_rate = StatsService.calculate_success_rate(
            llm_stats['successful_requests'],
            total_requests
        )
        card += f"Success Rate: {StatsService.format_percentage(success_rate)}\n"

        card += f"\nCost: {StatsService.format_cost(llm_stats['total_cost'])}\n"
        card += f"Avg Cost/Request: {StatsService.format_cost(llm_stats['avg_cost'])}\n"

        card += f"\nTokens: {StatsService.format_tokens(llm_stats['total_tokens'])}\n"
        card += f"Avg Tokens/Request: {int(llm_stats['avg_tokens'])}\n"

        # LLM Provider Breakdown
        llm_breakdown = stats['llm_breakdown']
        if llm_breakdown:
            card += f"\nBy Provider/Model:\n"
            for item in llm_breakdown[:3]:  # Top 3
                provider = item['provider']
                model = item['model']
                cost = StatsService.format_cost(item['total_cost'])
                requests = item['request_count']
                card += f"  {provider}/{model[:20]}\n"
                card += f"    {requests} req, {cost}\n"
    else:
        card += "No LLM usage data\n"

    # Unclosed Tasks Section
    unclosed_tasks = stats['unclosed_tasks']
    if unclosed_tasks:
        card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        card += f"⚠️ Unclosed Tasks (>24h)\n"
        card += f"━━━━━━━━━━━━━━━━━━━━\n"
        card += f"Count: {len(unclosed_tasks)}\n\n"

        for idx, task in enumerate(unclosed_tasks[:5], 1):  # Show max 5
            age_str = StatsService.format_duration(task['age_seconds'])
            author = task['author_name'] or 'Unknown'
            content = task['content'] or '[No content]'
            if len(content) > 50:
                content = content[:47] + "..."

            card += f"{idx}. Task #{task['id']} ({age_str} old)\n"
            card += f"   From: {author}\n"
            card += f"   {content}\n"

        if len(unclosed_tasks) > 5:
            card += f"\n... and {len(unclosed_tasks) - 5} more\n"

    # Activity Distribution (optional)
    hourly_dist = stats['hourly_distribution']
    peak_hour = StatsService.get_peak_hour(hourly_dist)
    if peak_hour is not None:
        card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        card += f"📈 Activity Pattern\n"
        card += f"━━━━━━━━━━━━━━━━━━━━\n"
        card += f"Peak Hour: {peak_hour:02d}:00 UTC\n"

        # Show activity sparkline for peak hours
        max_count = max(hourly_dist.values()) if hourly_dist else 0
        if max_count > 0:
            card += f"\nBusiest Hours:\n"
            # Find top 5 hours
            sorted_hours = sorted(hourly_dist.items(), key=lambda x: x[1], reverse=True)[:5]
            for hour, count in sorted_hours:
                if count > 0:
                    bar = StatsService.create_progress_bar(count, max_count, width=8)
                    card += f"  {hour:02d}:00  {bar} {count}\n"

    # Footer
    card += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    card += f"💡 Use buttons below to change time period\n"

    # Truncate if too long
    if len(card) > MAX_MESSAGE_LENGTH - 100:
        card = card[:MAX_MESSAGE_LENGTH - 200] + "\n\n[Report truncated...]"

    return card


def create_stats_keyboard(current_period: int = 30) -> dict:
    """
    Create inline keyboard for statistics period selection.

    Args:
        current_period: Currently selected period in days

    Returns:
        Telegram inline keyboard dict

    Example:
        >>> keyboard = create_stats_keyboard(current_period=30)
    """
    keyboard = {'inline_keyboard': []}

    # Period selection row
    period_options = [7, 30, 90]
    period_row = []

    for period in period_options:
        # Mark current period with checkmark
        text = f"{'✓ ' if period == current_period else ''}{period} days"
        period_row.append({
            'text': text,
            'callback_data': f'stats_period_{period}'
        })

    keyboard['inline_keyboard'].append(period_row)

    # Refresh button
    keyboard['inline_keyboard'].append([
        {'text': '🔄 Refresh', 'callback_data': f'stats_refresh_{current_period}'}
    ])

    return keyboard


if __name__ == '__main__':
    # Test card generation
    card_text, keyboard = create_example_card()
    print("Example Card:")
    print(card_text)
    print("\nKeyboard:")
    print(keyboard)
