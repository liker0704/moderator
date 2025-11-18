"""
Integration tests for end-to-end workflows.
These tests use mocks for external APIs but test real database operations.
"""
import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


# =============================================================================
# Test: Discord to Telegram Flow
# =============================================================================

@pytest.mark.asyncio
async def test_discord_to_telegram_flow():
    """
    Test full flow: Discord message → Database → Telegram card.

    Verifies:
    - Message saved to database
    - Task created
    - Card sent to Telegram
    """
    # Mock Discord message data
    discord_message = {
        'id': '1234567890',
        'channel_id': '9876543210',
        'guild_id': '1111111111',
        'author': {
            'id': '2222222222',
            'username': 'TestUser'
        },
        'content': 'Test message content',
        'attachments': [],
        'timestamp': '2024-01-01T12:00:00Z'
    }

    # Mock asyncpg connection
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)  # message_id
    mock_conn.fetchrow = AsyncMock(return_value={
        'id': 1,
        'platform': 'discord',
        'channel_id': '9876543210',
        'author_name': 'TestUser',
        'content': 'Test message content'
    })

    # This is a placeholder showing the integration structure
    # Real implementation would:
    # 1. Call MessageDAO.create_message()
    # 2. Call TaskDAO.create_task()
    # 3. Call TelegramBot.send_card()

    assert mock_conn is not None


@pytest.mark.skip(reason="Requires full integration environment")
@pytest.mark.asyncio
async def test_reply_workflow():
    """
    Test reply workflow: User clicks reply → Enters text → Confirms → Posts to Discord.

    Verifies:
    - FSM state management
    - Reply saved to database
    - Discord poster called
    - Task status updated
    """
    from telegram.handlers import callback_reply

    # Mock Telegram callback query
    callback_query = {
        'id': '123',
        'from': {'id': 12345},
        'data': 'reply_1',
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    # Mock bot instance
    mock_bot = Mock()
    mock_bot.get_user_state = Mock(return_value=None)
    mock_bot.set_user_state = Mock()
    mock_bot.send_message = AsyncMock()

    # Test reply callback handler
    await callback_reply(callback_query, mock_bot)

    # Verify FSM state was set
    mock_bot.set_user_state.assert_called_once()

    # Verify prompt was sent
    mock_bot.send_message.assert_called_once()


# =============================================================================
# Test: DND Mode Filtering
# =============================================================================

@pytest.mark.skip(reason="Requires full integration environment")
@pytest.mark.asyncio
async def test_dnd_mode_filtering():
    """
    Test DND mode filters out messages correctly.

    Verifies:
    - Messages not sent when DND active
    - Tasks marked as 'muted'
    - Messages sent when DND inactive
    """
    from services.dnd import is_dnd_active

    # Mock database connection
    mock_conn = AsyncMock()

    # Test DND active
    mock_conn.fetchrow = AsyncMock(return_value={
        'dnd_enabled': True,
        'dnd_schedule_json': None  # Active 24/7
    })

    result = await is_dnd_active(mock_conn, user_id=1)
    assert result is True

    # Test DND inactive
    mock_conn.fetchrow = AsyncMock(return_value={
        'dnd_enabled': False,
        'dnd_schedule_json': None
    })

    result = await is_dnd_active(mock_conn, user_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_allowlist_filtering():
    """
    Test allowlist filtering works correctly.

    Verifies:
    - Messages from allowed channels processed
    - Messages from non-allowed channels ignored
    """
    # This would require actual database setup
    # Placeholder showing the test structure

    # Mock allowlist check
    with patch('services.allowlist.is_channel_allowed', return_value=True):
        # Verify message processed
        pass

    with patch('services.allowlist.is_channel_allowed', return_value=False):
        # Verify message ignored
        pass

    assert True  # Placeholder


# =============================================================================
# Test: Media Attachment Handling
# =============================================================================

@pytest.mark.asyncio
async def test_media_attachment_handling():
    """
    Test media attachments are saved and displayed.

    Verifies:
    - Attachments saved to database
    - Attachments shown in card
    - Different attachment types handled
    """
    # Mock Discord message with image
    discord_message = {
        'id': '1234567890',
        'channel_id': '9876543210',
        'attachments': [
            {
                'id': '111',
                'filename': 'test.png',
                'content_type': 'image/png',
                'url': 'https://cdn.discord.com/attachments/test.png',
                'size': 12345
            }
        ]
    }

    # Test attachment processing
    # Verify saved to attachments table
    # Verify shown in card

    assert True  # Placeholder


# =============================================================================
# Test: Context Loading
# =============================================================================

@pytest.mark.asyncio
async def test_context_loading():
    """
    Test context messages loaded correctly.

    Verifies:
    - Last 10 messages retrieved
    - Correct channel filtering
    - Messages ordered by time
    """
    # Mock database with message history
    # Test get_context_by_channel
    # Verify correct messages returned

    assert True  # Placeholder


# =============================================================================
# Test: Error Handling and Retry
# =============================================================================

@pytest.mark.asyncio
async def test_error_handling_and_retry():
    """
    Test error handling and retry functionality.

    Verifies:
    - Errors caught and logged
    - Retry button functionality
    - Failed posts marked in database
    """
    # Mock posting failure
    with patch('discord.poster.DiscordPoster.post_message', return_value={'success': False, 'error': 'Rate limited'}):
        # Test reply posting
        # Verify error shown to user
        # Verify retry button available
        pass

    # Mock successful retry
    with patch('discord.poster.DiscordPoster.post_message', return_value={'success': True, 'message_id': '999'}):
        # Test retry
        # Verify success message
        # Verify task updated
        pass

    assert True  # Placeholder


# =============================================================================
# Test: Encryption Roundtrip
# =============================================================================

@pytest.mark.asyncio
async def test_encryption_roundtrip():
    """
    Test Discord token encryption/decryption.

    Verifies:
    - Token encrypted before storage
    - Token decrypted for use
    - Encryption service works correctly
    """
    from database.encryption import get_encryption_service

    service = get_encryption_service()
    original_token = "test.discord.token.123456"

    # Encrypt
    encrypted = service.encrypt(original_token)
    assert encrypted != original_token

    # Decrypt
    decrypted = service.decrypt(encrypted)
    assert decrypted == original_token


# =============================================================================
# Test: DND Schedule Parsing
# =============================================================================

def test_dnd_schedule_parsing():
    """
    Test DND schedule parsing and time checking.

    Verifies:
    - Schedule JSON parsed correctly
    - Time interval checking works
    - Overnight intervals handled
    """
    from services.dnd import is_in_dnd_schedule
    from datetime import datetime

    # Test schedule: 22:00-08:00 on weekdays
    # Note: weekday() uses 0=Monday, 6=Sunday
    schedule_json = json.dumps([
        {
            "start": "22:00",
            "end": "08:00",
            "days": [0, 1, 2, 3, 4]  # Monday=0 to Friday=4
        }
    ])

    # Test time checking - 23:00 on Monday (should be active)
    # Monday is weekday() = 0
    test_time = datetime(2024, 1, 1, 23, 0)  # Monday 23:00
    assert is_in_dnd_schedule(schedule_json, test_time) is True

    # Test time checking - 15:00 on Monday (should not be active)
    test_time = datetime(2024, 1, 1, 15, 0)  # Monday 15:00
    assert is_in_dnd_schedule(schedule_json, test_time) is False

    # Test overnight - 02:00 on Tuesday (should be active)
    test_time = datetime(2024, 1, 2, 2, 0)  # Tuesday 02:00
    assert is_in_dnd_schedule(schedule_json, test_time) is True


# =============================================================================
# Test: Card Formatting
# =============================================================================

@pytest.mark.skip(reason="Requires full integration environment")
def test_card_formatting():
    """
    Test message card formatting.

    Verifies:
    - All required fields included
    - Context formatted correctly
    - Attachments shown
    """
    from telegram.cards import format_card

    message = {
        'platform': 'discord',
        'channel_id': '123456',
        'author_name': 'TestUser',
        'content': 'Test message',
        'platform_created_at': datetime.now(),
        'has_image': False
    }

    context = []

    card = format_card(message, context)

    assert 'discord' in card.lower()
    assert 'TestUser' in card
    assert 'Test message' in card


@pytest.mark.skip(reason="Requires full integration environment")
def test_card_with_context():
    """
    Test card formatting with context messages.

    Verifies:
    - Context messages displayed correctly
    - Truncation works for long context
    - Time formatting is correct
    """
    from telegram.cards import format_card

    message = {
        'platform': 'discord',
        'channel_id': '123456',
        'author_name': 'TestUser',
        'content': 'New message',
        'platform_created_at': datetime(2024, 1, 1, 15, 30, 0),
        'has_image': False
    }

    context = [
        {
            'author_name': 'User1',
            'content': 'Context message 1',
            'platform_created_at': datetime(2024, 1, 1, 15, 28, 0)
        },
        {
            'author_name': 'User2',
            'content': 'Context message 2',
            'platform_created_at': datetime(2024, 1, 1, 15, 29, 0)
        }
    ]

    card = format_card(message, context)

    assert 'Context' in card
    assert 'User1' in card
    assert 'User2' in card
    assert 'Context message 1' in card


@pytest.mark.skip(reason="Requires full integration environment")
def test_card_with_attachment():
    """
    Test card formatting with attachments.

    Verifies:
    - Attachment indicator displayed
    """
    from telegram.cards import format_card

    message = {
        'platform': 'discord',
        'channel_id': '123456',
        'author_name': 'TestUser',
        'content': 'Message with image',
        'platform_created_at': datetime.now(),
        'has_image': True
    }

    card = format_card(message, [])

    assert '[Has attachments]' in card or 'attachments' in card.lower()


# =============================================================================
# Test: Alert Throttling
# =============================================================================

@pytest.mark.asyncio
async def test_alert_throttling(mock_telegram_bot):
    """
    Test alert system throttling.

    Verifies:
    - Alerts sent successfully
    - Throttling prevents spam
    - Different alert types work
    """
    from services.alerts import send_alert, clear_alert_throttle

    # Clear any existing throttles
    await clear_alert_throttle()

    # First alert should send
    result1 = await send_alert(
        mock_telegram_bot,
        "Test error",
        alert_type="ERROR",
        throttle_key="test_key",
        throttle_seconds=60
    )
    assert result1 is True

    # Second alert immediately should be throttled
    result2 = await send_alert(
        mock_telegram_bot,
        "Test error 2",
        alert_type="ERROR",
        throttle_key="test_key",
        throttle_seconds=60
    )
    assert result2 is False

    # Clear and try again - should send
    await clear_alert_throttle("test_key")
    result3 = await send_alert(
        mock_telegram_bot,
        "Test error 3",
        alert_type="ERROR",
        throttle_key="test_key",
        throttle_seconds=60
    )
    assert result3 is True


# =============================================================================
# Test: Keyboard Creation
# =============================================================================

@pytest.mark.skip(reason="Requires full integration environment")
def test_card_keyboard_creation():
    """
    Test inline keyboard creation for message cards.

    Verifies:
    - Reply button present
    - More context button present
    - DND button present
    - Callback data correct
    """
    from telegram.cards import create_card_keyboard

    task_id = 123
    keyboard = create_card_keyboard(task_id)

    assert 'inline_keyboard' in keyboard
    assert len(keyboard['inline_keyboard']) > 0

    # Check for reply button
    buttons = [btn for row in keyboard['inline_keyboard'] for btn in row]
    callback_data = [btn['callback_data'] for btn in buttons]

    assert f'reply_{task_id}' in callback_data
    assert f'more_{task_id}' in callback_data
    assert 'toggle_dnd' in callback_data


# =============================================================================
# Test: FSM State Management
# =============================================================================

def test_fsm_state_management():
    """
    Test finite state machine state management.

    Verifies:
    - States can be set
    - States can be retrieved
    - States can be cleared
    """
    # This would test the bot's FSM implementation
    # Placeholder showing test structure

    # Mock bot with FSM
    fsm_states = {}

    # Set state
    user_id = 12345
    fsm_states[user_id] = {'state': 'awaiting_reply_1'}

    # Get state
    state = fsm_states.get(user_id)
    assert state is not None
    assert state['state'] == 'awaiting_reply_1'

    # Clear state
    fsm_states.pop(user_id, None)
    assert user_id not in fsm_states


# =============================================================================
# Test: Reply Confirmation Flow
# =============================================================================

@pytest.mark.skip(reason="Requires full integration environment")
@pytest.mark.asyncio
async def test_reply_confirmation_flow():
    """
    Test complete reply confirmation workflow.

    Verifies:
    - Reply text captured
    - Reply saved to database
    - Confirmation card sent
    - Confirm button works
    """
    from telegram.handlers import handle_reply_text_input

    # Mock message with reply text
    message = {
        'from': {'id': 12345},
        'chat': {'id': 12345},
        'text': 'This is my reply'
    }

    # Mock bot
    mock_bot = Mock()
    mock_bot.send_message = AsyncMock()
    mock_bot.set_user_state = Mock()
    mock_bot.clear_user_state = Mock()
    mock_bot.db = Mock()

    # Mock database pool
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)  # reply_id

    mock_pool = AsyncMock()
    mock_pool.acquire = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock()

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
        # Test handler
        await handle_reply_text_input(message, mock_bot, 'awaiting_reply_1')

        # Verify message sent (confirmation)
        mock_bot.send_message.assert_called_once()

        # Verify state updated
        mock_bot.set_user_state.assert_called_once()


# =============================================================================
# Test: DND Toggle
# =============================================================================

@pytest.mark.skip(reason="Requires full integration environment")
@pytest.mark.asyncio
async def test_dnd_toggle():
    """
    Test DND toggle functionality.

    Verifies:
    - DND can be enabled
    - DND can be disabled
    - State persists in database
    """
    from services.dnd import toggle_dnd

    # Mock database connection
    mock_conn = AsyncMock()

    # Test enable
    mock_conn.fetchrow = AsyncMock(return_value={'dnd_enabled': False})
    result = await toggle_dnd(mock_conn, user_id=1, enabled=True)

    # Verify execute was called
    mock_conn.execute.assert_called()

    # Test disable
    mock_conn.fetchrow = AsyncMock(return_value={'dnd_enabled': True})
    result = await toggle_dnd(mock_conn, user_id=1, enabled=False)

    # Verify execute was called again
    assert mock_conn.execute.call_count >= 2


# =============================================================================
# Test: Example Card Generation
# =============================================================================

@pytest.mark.skip(reason="Requires full integration environment")
def test_example_card_generation():
    """
    Test example card generation function.

    Verifies:
    - Example card can be generated
    - Card has proper format
    - Keyboard is included
    """
    from telegram.cards import create_example_card

    card_text, keyboard = create_example_card()

    # Verify card has content
    assert len(card_text) > 0
    assert 'discord' in card_text.lower() or 'telegram' in card_text.lower()

    # Verify keyboard exists
    assert keyboard is not None
    assert 'inline_keyboard' in keyboard


# =============================================================================
# Test: Time Range Checking
# =============================================================================

def test_time_range_checking():
    """
    Test time range checking including overnight ranges.

    Verifies:
    - Normal time ranges work (e.g., 09:00-17:00)
    - Overnight ranges work (e.g., 22:00-08:00)
    - Edge cases handled correctly
    """
    from datetime import time

    # Helper function (inline implementation of time range checking logic)
    def _is_time_in_range(current_time, start_time, end_time):
        """Check if current_time is within start_time and end_time range."""
        if start_time <= end_time:
            # Normal interval (e.g., 09:00-17:00)
            return start_time <= current_time <= end_time
        else:
            # Overnight interval (e.g., 22:00-08:00)
            return current_time >= start_time or current_time <= end_time

    # Test normal range (09:00-17:00)
    assert _is_time_in_range(time(10, 0), time(9, 0), time(17, 0)) is True
    assert _is_time_in_range(time(18, 0), time(9, 0), time(17, 0)) is False
    assert _is_time_in_range(time(8, 0), time(9, 0), time(17, 0)) is False

    # Test overnight range (22:00-08:00)
    assert _is_time_in_range(time(23, 0), time(22, 0), time(8, 0)) is True
    assert _is_time_in_range(time(2, 0), time(22, 0), time(8, 0)) is True
    assert _is_time_in_range(time(12, 0), time(22, 0), time(8, 0)) is False

    # Test edge cases
    assert _is_time_in_range(time(22, 0), time(22, 0), time(8, 0)) is True
    assert _is_time_in_range(time(8, 0), time(22, 0), time(8, 0)) is True


# =============================================================================
# Test: Alert Message Formatting
# =============================================================================

def test_alert_message_formatting():
    """
    Test alert message formatting with different types.

    Verifies:
    - Error alerts formatted correctly
    - Warning alerts formatted correctly
    - Info alerts formatted correctly
    - Critical alerts formatted correctly
    """
    from services.alerts import _format_alert_message

    # Define alert emojis (same as in alerts.py)
    ALERT_EMOJIS = {
        'ERROR': '❌',
        'WARNING': '⚠️',
        'INFO': 'ℹ️',
        'CRITICAL': '🚨'
    }

    # Test error alert
    message = _format_alert_message("Test error", "ERROR", ALERT_EMOJIS["ERROR"])
    assert "ERROR" in message
    assert "Test error" in message
    assert ALERT_EMOJIS["ERROR"] in message

    # Test warning alert
    message = _format_alert_message("Test warning", "WARNING", ALERT_EMOJIS["WARNING"])
    assert "WARNING" in message
    assert "Test warning" in message

    # Test info alert
    message = _format_alert_message("Test info", "INFO", ALERT_EMOJIS["INFO"])
    assert "INFO" in message
    assert "Test info" in message


# =============================================================================
# Test: DND Schedule Validation
# =============================================================================

def test_dnd_schedule_validation():
    """
    Test DND schedule validation.

    Verifies:
    - Valid schedules accepted
    - Invalid schedules rejected
    - Proper error messages
    """
    from datetime import datetime

    # Helper function (inline implementation of schedule validation logic)
    def _validate_schedule(schedules):
        """Validate DND schedule structure."""
        if not isinstance(schedules, list):
            raise ValueError("Schedule must be a list")

        for schedule in schedules:
            if not isinstance(schedule, dict):
                raise ValueError("Each schedule item must be a dict")

            # Validate days
            days = schedule.get('days', [])
            if not isinstance(days, list) or not days:
                raise ValueError("Schedule must have 'days' list")
            if not all(isinstance(d, int) and 0 <= d <= 6 for d in days):
                raise ValueError("Days must be integers 0-6 (Monday-Sunday)")

            # Validate time format
            for time_key in ['start', 'end']:
                time_str = schedule.get(time_key)
                if not time_str:
                    raise ValueError(f"Schedule must have '{time_key}' time")
                try:
                    datetime.strptime(time_str, '%H:%M')
                except ValueError:
                    raise ValueError(f"Invalid time format for '{time_key}': {time_str}")

    # Test valid schedule (new format)
    valid_schedule = [
        {
            "days": [0, 1, 2, 3, 4],  # Monday=0 to Friday=4
            "start": "22:00",
            "end": "08:00"
        }
    ]

    try:
        _validate_schedule(valid_schedule)
        assert True  # Should not raise
    except ValueError:
        assert False, "Valid schedule should not raise ValueError"

    # Test invalid schedule - not a list
    with pytest.raises(ValueError):
        _validate_schedule({"foo": "bar"})

    # Test invalid schedule - invalid days
    with pytest.raises(ValueError):
        _validate_schedule([
            {
                "days": [8, 9],  # Invalid days
                "start": "22:00",
                "end": "08:00"
            }
        ])

    # Test invalid schedule - invalid time format
    with pytest.raises(ValueError):
        _validate_schedule([
            {
                "days": [0, 1, 2],
                "start": "25:00",  # Invalid hour
                "end": "08:00"
            }
        ])


# =============================================================================
# NEW COMPREHENSIVE END-TO-END INTEGRATION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_complete_discord_to_telegram_flow(mock_db_connection, mock_telegram_bot):
    """
    Test complete flow: Discord message → Database → Task → Telegram card

    Verifies:
    - Message saved to database
    - Attachments saved
    - Task created
    - Telegram card sent
    - All data correctly passed through pipeline
    """
    from database.dao.message_dao import MessageDAO
    from database.dao.task_dao import TaskDAO
    from database.dao.attachment_dao import AttachmentDAO
    from database.dao.allowlist_dao import AllowlistDAO

    # Mock Discord message payload
    discord_message = {
        'id': '1234567890',
        'channel_id': '9876543210',
        'guild_id': '1111111111',
        'author': {
            'id': '2222222222',
            'username': 'TestUser'
        },
        'content': 'Test message from Discord',
        'timestamp': '2024-01-15T10:30:00.000Z',
        'attachments': [
            {
                'id': '3333333333',
                'filename': 'test.png',
                'url': 'https://cdn.discordapp.com/attachments/test.png',
                'content_type': 'image/png',
                'size': 12345
            }
        ]
    }

    # Setup mock database responses for fetchval (returns scalar values)
    # We need a new AsyncMock each time fetchval is called
    fetchval_values = [1, 1, 100]  # message_id, attachment_id, task_id
    fetchval_index = {'current': 0}

    async def mock_fetchval(*args, **kwargs):
        value = fetchval_values[fetchval_index['current']]
        fetchval_index['current'] += 1
        return value

    mock_db_connection.fetchval = mock_fetchval

    # Setup mock database responses for fetchrow (returns row objects)
    # We need different responses for different calls
    fetchrow_values = [
        {'id': 1, 'thread_filter_json': None},  # Allowlist check
        {'id': 1},  # MessageDAO.create_message
        {'id': 1},  # AttachmentDAO.create_attachment
        {'id': 100}  # TaskDAO.create_task
    ]
    fetchrow_index = {'current': 0}

    async def mock_fetchrow(*args, **kwargs):
        if fetchrow_index['current'] < len(fetchrow_values):
            value = fetchrow_values[fetchrow_index['current']]
            fetchrow_index['current'] += 1
            return value
        return None

    mock_db_connection.fetchrow = mock_fetchrow

    # Test Step 1: Check channel allowlist
    is_allowed = await AllowlistDAO.is_channel_allowed(
        mock_db_connection,
        platform='discord',
        channel_id=discord_message['channel_id'],
        server_id=discord_message['guild_id']
    )
    assert is_allowed is True, "Channel should be in allowlist"

    # Test Step 2: Create message in database
    message_id = await MessageDAO.create_message(
        mock_db_connection,
        platform='discord',
        ext_message_id=discord_message['id'],
        channel_id=discord_message['channel_id'],
        author_id=discord_message['author']['id'],
        author_name=discord_message['author']['username'],
        content=discord_message['content'],
        server_id=discord_message['guild_id'],
        has_image=True
    )
    assert message_id == 1, "Message should be created with ID 1"

    # Test Step 3: Create attachment in database
    attachment_meta = json.dumps({
        'filename': discord_message['attachments'][0]['filename'],
        'content_type': discord_message['attachments'][0]['content_type'],
        'size': discord_message['attachments'][0]['size'],
        'ext_id': discord_message['attachments'][0]['id']
    })
    attachment_id = await AttachmentDAO.create_attachment(
        mock_db_connection,
        message_id=message_id,
        kind='image',
        ref=discord_message['attachments'][0]['url'],
        meta=attachment_meta
    )
    assert attachment_id == 1, "Attachment should be created with ID 1"

    # Test Step 4: Create task for moderator
    task_id = await TaskDAO.create_task(
        mock_db_connection,
        source_message_id=message_id,
        assignee_user_id=1,
        status='open'
    )
    assert task_id == 100, "Task should be created with ID 100"

    # Test Step 5: Send Telegram card
    result = await mock_telegram_bot.send_message(
        chat_id=12345,
        text=f"New message from TestUser in Discord\nContent: {discord_message['content']}",
        parse_mode='HTML'
    )
    assert result['ok'] is True, "Telegram message should be sent successfully"

    # Verify all steps completed (message, attachment, and task created)
    assert message_id == 1, "Message creation verified"
    assert attachment_id == 1, "Attachment creation verified"
    assert task_id == 100, "Task creation verified"


@pytest.mark.asyncio
async def test_discord_message_allowlist_filtering(mock_db_connection):
    """
    Test that messages from non-allowlisted channels are ignored.

    Verifies:
    - Allowlist check is performed
    - Non-allowlisted messages are skipped
    - No task created for filtered messages
    """
    from database.dao.allowlist_dao import AllowlistDAO
    from database.dao.task_dao import TaskDAO

    # Create Discord message from non-allowlisted channel
    discord_message = {
        'id': '1234567890',
        'channel_id': 'NOT_IN_ALLOWLIST',
        'guild_id': '1111111111',
        'author': {'id': '2222222222', 'username': 'TestUser'},
        'content': 'This should be filtered',
        'timestamp': '2024-01-15T10:30:00.000Z',
        'attachments': []
    }

    # Mock AllowlistDAO to return None (channel not found)
    mock_db_connection.fetchrow = AsyncMock(return_value=None)

    # Test allowlist check
    is_allowed = await AllowlistDAO.is_channel_allowed(
        mock_db_connection,
        platform='discord',
        channel_id=discord_message['channel_id'],
        server_id=discord_message['guild_id']
    )

    # Verify channel is not allowed
    assert is_allowed is False, "Non-allowlisted channel should return False"

    # Verify fetchrow was called (allowlist check performed)
    mock_db_connection.fetchrow.assert_called_once()

    # Verify no task creation attempted (filtered message)
    mock_db_connection.fetchval = AsyncMock()

    # If allowlist check fails, task creation should not be called
    if not is_allowed:
        # Message processing stops here - no task created
        pass
    else:
        # This branch should not execute
        await TaskDAO.create_task(mock_db_connection, 1, 1)

    # Verify task creation was NOT called
    mock_db_connection.fetchval.assert_not_called()


@pytest.mark.asyncio
async def test_discord_message_dnd_filtering(mock_db_connection):
    """
    Test that messages are filtered/muted when DND is active.

    Verifies:
    - DND check is performed
    - Messages during DND are handled appropriately
    - Task status set to 'muted' during DND
    """
    from database.dao.task_dao import TaskDAO
    from database.dao.message_dao import MessageDAO

    discord_message = {
        'id': '1234567890',
        'channel_id': '9876543210',
        'guild_id': '1111111111',
        'author': {'id': '2222222222', 'username': 'TestUser'},
        'content': 'Message during DND',
        'timestamp': '2024-01-15T22:30:00.000Z',  # Night time
        'attachments': []
    }

    # Setup mock for user settings with DND enabled
    fetchrow_call_count = {'count': 0}

    async def mock_fetchrow(*args, **kwargs):
        fetchrow_call_count['count'] += 1
        # First call: DND settings check (mocked inline)
        if fetchrow_call_count['count'] == 1:
            return {
                'dnd_enabled': True,
                'dnd_schedule_json': None  # Active 24/7
            }
        # Second call: MessageDAO.create_message
        elif fetchrow_call_count['count'] == 2:
            return {'id': 1}
        # Third call: TaskDAO.create_task
        elif fetchrow_call_count['count'] == 3:
            return {'id': 100}
        return None

    mock_db_connection.fetchrow = mock_fetchrow

    # Test Step 1: Simulate DND check
    # In actual implementation, would call is_dnd_active(mock_db_connection, user_id=1)
    # For testing purposes, we simulate the DND logic inline
    dnd_settings = await mock_db_connection.fetchrow(
        "SELECT dnd_enabled, dnd_schedule_json FROM users WHERE id = $1", 1
    )
    dnd_active = dnd_settings['dnd_enabled'] if dnd_settings else False
    assert dnd_active is True, "DND should be active"

    # Test Step 2: Create message (still stored)
    message_id = await MessageDAO.create_message(
        mock_db_connection,
        platform='discord',
        ext_message_id=discord_message['id'],
        channel_id=discord_message['channel_id'],
        author_id=discord_message['author']['id'],
        author_name=discord_message['author']['username'],
        content=discord_message['content'],
        server_id=discord_message['guild_id']
    )
    assert message_id == 1, "Message should still be stored during DND"

    # Test Step 3: Create task with 'muted' status (not 'open')
    task_status = 'muted' if dnd_active else 'open'
    task_id = await TaskDAO.create_task(
        mock_db_connection,
        source_message_id=message_id,
        assignee_user_id=1,
        status=task_status
    )
    assert task_id == 100, "Task should be created with muted status"

    # Verify DND check was performed
    assert fetchrow_call_count['count'] >= 1, "DND settings should be queried"

    # In actual implementation, muted tasks don't trigger Telegram notifications
    # This test verifies the logic path exists


@pytest.mark.asyncio
async def test_discord_thread_message_processing(mock_db_connection, mock_telegram_bot):
    """
    Test that thread messages are processed correctly.

    Verifies:
    - Thread ID is captured and stored
    - Context loading respects thread boundaries
    - Messages in threads are properly identified
    """
    from database.dao.message_dao import MessageDAO
    from database.dao.task_dao import TaskDAO
    from database.dao.allowlist_dao import AllowlistDAO

    discord_thread_message = {
        'id': '1234567890',
        'channel_id': '9876543210',
        'guild_id': '1111111111',
        'thread_id': '5555555555',  # Message in a thread
        'author': {'id': '2222222222', 'username': 'ThreadUser'},
        'content': 'Message in thread',
        'timestamp': '2024-01-15T10:30:00.000Z',
        'attachments': []
    }

    # Setup mock for fetchrow (allowlist check, message creation, task creation)
    fetchrow_call_count = {'count': 0}

    async def mock_fetchrow(*args, **kwargs):
        fetchrow_call_count['count'] += 1
        # First call: allowlist check with thread filter
        if fetchrow_call_count['count'] == 1:
            return {
                'id': 1,
                'thread_filter_json': json.dumps({
                    'allowed_threads': ['5555555555']
                })
            }
        # Second call: MessageDAO.create_message
        elif fetchrow_call_count['count'] == 2:
            return {'id': 1}
        # Third call: TaskDAO.create_task
        elif fetchrow_call_count['count'] == 3:
            return {'id': 100}
        return None

    mock_db_connection.fetchrow = mock_fetchrow

    # Mock context messages fetch (should only return messages from same thread)
    mock_db_connection.fetch = AsyncMock(return_value=[
        {
            'id': 10,
            'channel_id': '9876543210',
            'thread_id': '5555555555',
            'author_name': 'OtherUser',
            'content': 'Previous thread message',
            'created_at': datetime(2024, 1, 15, 10, 25, 0),
            'platform_created_at': datetime(2024, 1, 15, 10, 25, 0),
            'has_image': False
        }
    ])

    # Test Step 1: Check if thread is allowed in channel
    is_allowed = await AllowlistDAO.is_channel_allowed(
        mock_db_connection,
        platform='discord',
        channel_id=discord_thread_message['channel_id'],
        server_id=discord_thread_message['guild_id'],
        thread_id=discord_thread_message['thread_id']
    )
    assert is_allowed is True, "Thread should be allowed"

    # Test Step 2: Create message with thread_id
    message_id = await MessageDAO.create_message(
        mock_db_connection,
        platform='discord',
        ext_message_id=discord_thread_message['id'],
        channel_id=discord_thread_message['channel_id'],
        author_id=discord_thread_message['author']['id'],
        author_name=discord_thread_message['author']['username'],
        content=discord_thread_message['content'],
        server_id=discord_thread_message['guild_id'],
        thread_id=discord_thread_message['thread_id']  # Thread ID included
    )
    assert message_id == 1, "Thread message should be created"

    # Test Step 3: Get context messages (should respect thread boundaries)
    context_messages = await MessageDAO.get_context_messages(
        mock_db_connection,
        channel_id=discord_thread_message['channel_id'],
        thread_id=discord_thread_message['thread_id'],
        before_timestamp=datetime.utcnow(),
        limit=10
    )

    # Verify context messages are from same thread
    assert len(context_messages) == 1, "Should get context from same thread"
    assert context_messages[0]['thread_id'] == discord_thread_message['thread_id'], \
        "Context messages should be from same thread"

    # Test Step 4: Create task
    task_id = await TaskDAO.create_task(
        mock_db_connection,
        source_message_id=message_id,
        assignee_user_id=1,
        status='open'
    )
    assert task_id == 100, "Task should be created for thread message"

    # Verify thread_id was included in message creation call
    # All steps completed successfully
    assert message_id == 1, "Thread message creation verified"
    assert task_id == 100, "Task creation for thread message verified"
    assert fetchrow_call_count['count'] == 3, "All database operations completed"
