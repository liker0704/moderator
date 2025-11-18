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

def format_card(message: dict, context_messages: list) -> str:
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

    Returns:
        Formatted card text string
    """
    # Platform emoji
    platform_emoji = "💬" if message.get('platform') == 'telegram' else "📝"

    # Build header
    header_parts = [platform_emoji, message.get('platform', 'unknown').title()]

    # Add server name for Discord (if available)
    if message.get('server_id'):
        # TODO: Get server name from Discord or cache
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
    if message.get('has_image'):
        message_content += "\n📎 [Has attachments]"

    message_section = f"\n\n💬 Current Message:\n{message_content}"

    # Build card
    card = f"{header}{context_text}{message_section}"

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


# =============================================================================
# Keyboard Creation Functions
# =============================================================================

def create_card_keyboard(task_id: int) -> dict:
    """
    Create inline keyboard for message card.

    Args:
        task_id: Task ID for callback data

    Returns:
        Telegram inline keyboard dict
    """
    return {
        "inline_keyboard": [
            [
                {"text": "✍️ Ответить", "callback_data": f"reply_{task_id}"},
                {"text": "📖 Показать больше", "callback_data": f"more_{task_id}"}
            ],
            [
                {"text": "🔕 DND", "callback_data": "toggle_dnd"}
            ]
        ]
    }


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


if __name__ == '__main__':
    # Test card generation
    card_text, keyboard = create_example_card()
    print("Example Card:")
    print(card_text)
    print("\nKeyboard:")
    print(keyboard)
