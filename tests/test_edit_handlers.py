"""
Telegram handler tests for reply editing.

Tests Telegram bot handlers for the edit workflow:
- callback_edit_reply: Initiates edit, validates permission, sets FSM state
- handle_edit_text_input: Processes new text, creates temp reply, shows confirmation
- callback_confirm_edit: Executes edit via ReplyEditorService, updates platform
- callback_cancel_edit: Cancels edit, deletes temp reply, clears FSM
- callback_show_edit_history: Displays formatted edit history
"""
import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot with FSM state management."""
    bot = AsyncMock()

    # FSM state storage
    bot.user_states = {}

    # Mock state management
    def get_user_state(user_id):
        return bot.user_states.get(user_id)

    def set_user_state(user_id, state, data=None):
        bot.user_states[user_id] = {'state': state, 'data': data or {}}

    def clear_user_state(user_id):
        if user_id in bot.user_states:
            del bot.user_states[user_id]

    bot.get_user_state = Mock(side_effect=get_user_state)
    bot.set_user_state = Mock(side_effect=set_user_state)
    bot.clear_user_state = Mock(side_effect=clear_user_state)

    # Mock message methods
    bot.send_message = AsyncMock(return_value={'message_id': 123})
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()

    # Mock Discord poster
    bot.discord_poster = AsyncMock()
    bot.discord_poster.edit_message = AsyncMock(return_value={'success': True})

    return bot


@pytest.fixture
def mock_db_pool():
    """Mock database pool for handler tests."""
    pool = AsyncMock()

    # Mock connection
    conn = AsyncMock()

    # Setup mock data
    conn.state = {
        'replies': {
            1: {
                'id': 1,
                'task_id': 1,
                'content': 'Original reply content',
                'generated_by': 'human',
                'llm_confidence': None,
                'confirmed': True,
                'posted_at': datetime.utcnow() - timedelta(hours=1),
                'platform_ref': json.dumps({
                    'platform': 'discord',
                    'channel_id': '111222333',
                    'message_id': '123456789'
                }),
                'edit_of': None,
                'created_at': datetime.utcnow() - timedelta(hours=2)
            },
            2: {
                'id': 2,
                'task_id': 1,
                'content': 'Edited reply content',
                'generated_by': 'human',
                'llm_confidence': None,
                'confirmed': False,
                'posted_at': None,
                'platform_ref': None,
                'edit_of': 1,
                'created_at': datetime.utcnow()
            }
        },
        'tasks': {
            1: {
                'id': 1,
                'source_message_id': 1,
                'assignee_user_id': 12345,
                'status': 'open',
                'created_at': datetime.utcnow()
            }
        }
    }

    # Mock acquire context manager
    class AcquireContext:
        def __init__(self, conn):
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    pool.acquire = Mock(return_value=AcquireContext(conn))

    return pool


# =============================================================================
# Tests: callback_edit_reply
# =============================================================================

@pytest.mark.asyncio
async def test_callback_edit_reply_success(mock_telegram_bot, mock_db_pool):
    """
    Test callback_edit_reply successfully initiates edit.

    Verifies:
    - Permission validation called
    - FSM state set to awaiting_edit_text_{reply_id}
    - User prompted for new text
    - Current content shown in prompt
    """
    from telegram.handlers import callback_edit_reply

    # Mock query
    query = {
        'id': 'callback_123',
        'data': 'edit_reply_1',
        'from': {'id': 12345},
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    # Mock validation
    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyEditorService') as mock_service:
            mock_service.validate_edit_permission = AsyncMock(return_value={
                'can_edit': True,
                'reply': {
                    'id': 1,
                    'content': 'Original reply content',
                    'posted_at': datetime.utcnow() - timedelta(hours=1)
                },
                'task': {
                    'id': 1,
                    'assignee_user_id': 12345
                }
            })

            await callback_edit_reply(query, mock_telegram_bot)

            # Verify validation was called
            mock_service.validate_edit_permission.assert_called_once_with(
                mock_db_pool.acquire().conn,
                1,
                12345
            )

            # Verify FSM state set
            state = mock_telegram_bot.get_user_state(12345)
            assert state is not None
            assert state['state'] == 'awaiting_edit_text_1'
            assert state['data']['reply_id'] == 1
            assert state['data']['task_id'] == 1

            # Verify user prompted
            mock_telegram_bot.send_message.assert_called_once()
            call_args = mock_telegram_bot.send_message.call_args
            assert 'Edit Reply' in call_args[0][1]
            assert 'Current text:' in call_args[0][1]

            # Verify callback answered
            mock_telegram_bot.answer_callback_query.assert_called_once()


@pytest.mark.asyncio
async def test_callback_edit_reply_permission_denied(mock_telegram_bot, mock_db_pool):
    """
    Test callback_edit_reply when permission is denied.

    Verifies:
    - Error shown to user
    - FSM state NOT set
    - Reason displayed in alert
    """
    from telegram.handlers import callback_edit_reply

    query = {
        'id': 'callback_123',
        'data': 'edit_reply_1',
        'from': {'id': 12345},
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyEditorService') as mock_service:
            mock_service.validate_edit_permission = AsyncMock(return_value={
                'can_edit': False,
                'reason': 'time_expired',
                'hours_since_posted': 50.5
            })

            await callback_edit_reply(query, mock_telegram_bot)

            # Verify error shown
            mock_telegram_bot.answer_callback_query.assert_called_once()
            call_args = mock_telegram_bot.answer_callback_query.call_args
            assert '48h' in call_args[1]['text'] or 'expired' in call_args[1]['text'].lower()
            assert call_args[1]['show_alert'] is True

            # Verify FSM state NOT set
            state = mock_telegram_bot.get_user_state(12345)
            assert state is None

            # Verify user NOT prompted for text
            mock_telegram_bot.send_message.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('reason,expected_msg', [
    ('not_found', 'not found'),
    ('not_posted', 'not posted'),
    ('permission_denied', 'cannot edit'),
    ('task_muted', 'muted'),
])
async def test_callback_edit_reply_various_denials(
    mock_telegram_bot,
    mock_db_pool,
    reason,
    expected_msg
):
    """
    Test callback_edit_reply with various permission denial reasons.

    Verifies appropriate error messages for different denial reasons.
    """
    from telegram.handlers import callback_edit_reply

    query = {
        'id': 'callback_123',
        'data': 'edit_reply_1',
        'from': {'id': 12345},
        'message': {'chat': {'id': 12345}, 'message_id': 100}
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyEditorService') as mock_service:
            mock_service.validate_edit_permission = AsyncMock(return_value={
                'can_edit': False,
                'reason': reason
            })

            await callback_edit_reply(query, mock_telegram_bot)

            # Verify appropriate error shown
            call_args = mock_telegram_bot.answer_callback_query.call_args
            assert expected_msg.lower() in call_args[1]['text'].lower()


# =============================================================================
# Tests: handle_edit_text_input
# =============================================================================

@pytest.mark.asyncio
async def test_handle_edit_text_input_success(mock_telegram_bot, mock_db_pool):
    """
    Test handle_edit_text_input successfully processes new text.

    Verifies:
    - New text validated (not empty, length check)
    - Temp reply created in DB
    - Confirmation dialog shown
    - FSM state updated to awaiting_edit_confirm
    """
    from telegram.handlers import handle_edit_text_input

    # Set initial FSM state
    mock_telegram_bot.set_user_state(12345, 'awaiting_edit_text_1', {
        'reply_id': 1,
        'original_content': 'Original reply content',
        'task_id': 1
    })

    # Mock message with new text
    message = {
        'from': {'id': 12345},
        'chat': {'id': 12345},
        'text': 'New edited reply text'
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyDAO') as mock_dao:
            mock_dao.create_edited_reply = AsyncMock(return_value=2)

            with patch('telegram.handlers.create_edit_confirmation') as mock_confirm:
                mock_confirm.return_value = {
                    'text': 'Confirm edit?',
                    'buttons': [[{'text': 'Confirm', 'callback_data': 'confirm_edit_2'}]]
                }

                await handle_edit_text_input(message, mock_telegram_bot, 'awaiting_edit_text_1')

                # Verify temp reply created
                mock_dao.create_edited_reply.assert_called_once_with(
                    mock_db_pool.acquire().conn,
                    1,
                    'New edited reply text',
                    12345
                )

                # Verify confirmation shown
                mock_telegram_bot.send_message.assert_called_once()
                call_args = mock_telegram_bot.send_message.call_args
                assert 'Confirm edit?' in call_args[0][1]

                # Verify FSM state updated
                state = mock_telegram_bot.get_user_state(12345)
                assert state['state'] == 'awaiting_edit_confirm_2'
                assert state['data']['new_reply_id'] == 2
                assert state['data']['original_reply_id'] == 1


@pytest.mark.asyncio
async def test_handle_edit_text_input_empty_text(mock_telegram_bot, mock_db_pool):
    """
    Test handle_edit_text_input rejects empty text.

    Verifies:
    - Empty text rejected
    - User prompted to retry
    - FSM state unchanged
    """
    from telegram.handlers import handle_edit_text_input

    mock_telegram_bot.set_user_state(12345, 'awaiting_edit_text_1', {
        'reply_id': 1,
        'original_content': 'Original',
        'task_id': 1
    })

    message = {
        'from': {'id': 12345},
        'chat': {'id': 12345},
        'text': '   '  # Empty/whitespace only
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        await handle_edit_text_input(message, mock_telegram_bot, 'awaiting_edit_text_1')

        # Verify error shown
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert 'cannot be empty' in call_args[0][1].lower()

        # Verify FSM state unchanged
        state = mock_telegram_bot.get_user_state(12345)
        assert state['state'] == 'awaiting_edit_text_1'


@pytest.mark.asyncio
async def test_handle_edit_text_input_too_long(mock_telegram_bot, mock_db_pool):
    """
    Test handle_edit_text_input rejects text over 2000 characters.

    Verifies Discord character limit is enforced.
    """
    from telegram.handlers import handle_edit_text_input

    mock_telegram_bot.set_user_state(12345, 'awaiting_edit_text_1', {
        'reply_id': 1,
        'original_content': 'Original',
        'task_id': 1
    })

    message = {
        'from': {'id': 12345},
        'chat': {'id': 12345},
        'text': 'x' * 2001  # Over Discord limit
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        await handle_edit_text_input(message, mock_telegram_bot, 'awaiting_edit_text_1')

        # Verify error shown
        call_args = mock_telegram_bot.send_message.call_args
        assert 'too long' in call_args[0][1].lower()
        assert '2000' in call_args[0][1]


@pytest.mark.asyncio
async def test_handle_edit_text_input_session_expired(mock_telegram_bot, mock_db_pool):
    """
    Test handle_edit_text_input when FSM state is missing (session expired).

    Verifies graceful handling of expired sessions.
    """
    from telegram.handlers import handle_edit_text_input

    # No state set (expired)
    message = {
        'from': {'id': 12345},
        'chat': {'id': 12345},
        'text': 'New text'
    }

    await handle_edit_text_input(message, mock_telegram_bot, 'awaiting_edit_text_1')

    # Verify session expired message
    call_args = mock_telegram_bot.send_message.call_args
    assert 'expired' in call_args[0][1].lower()


# =============================================================================
# Tests: callback_confirm_edit
# =============================================================================

@pytest.mark.asyncio
async def test_callback_confirm_edit_success(mock_telegram_bot, mock_db_pool):
    """
    Test callback_confirm_edit successfully executes edit.

    Verifies:
    - ReplyEditorService.edit_reply called
    - Platform message updated
    - Success message shown
    - FSM state cleared
    """
    from telegram.handlers import callback_confirm_edit

    # Set FSM state
    mock_telegram_bot.set_user_state(12345, 'awaiting_edit_confirm_2', {
        'new_reply_id': 2,
        'original_reply_id': 1
    })

    query = {
        'id': 'callback_123',
        'data': 'confirm_edit_2',
        'from': {'id': 12345},
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyDAO') as mock_dao:
            mock_dao.get_reply_by_id = AsyncMock(return_value={
                'id': 2,
                'content': 'New edited content',
                'edit_of': 1
            })

            with patch('telegram.handlers.ReplyEditorService') as mock_service:
                mock_service.edit_reply = AsyncMock(return_value={
                    'success': True,
                    'new_reply_id': 2,
                    'platform': 'discord'
                })

                await callback_confirm_edit(query, mock_telegram_bot)

                # Verify service called
                mock_service.edit_reply.assert_called_once()

                # Verify success message shown
                mock_telegram_bot.edit_message_text.assert_called_once()
                call_args = mock_telegram_bot.edit_message_text.call_args
                assert 'successfully' in call_args[0][2].lower()
                assert 'discord' in call_args[0][2].lower()

                # Verify FSM state cleared
                state = mock_telegram_bot.get_user_state(12345)
                assert state is None


@pytest.mark.asyncio
async def test_callback_confirm_edit_failure(mock_telegram_bot, mock_db_pool):
    """
    Test callback_confirm_edit when edit fails.

    Verifies:
    - Error message shown to user
    - Error code included
    - FSM state cleared
    """
    from telegram.handlers import callback_confirm_edit

    mock_telegram_bot.set_user_state(12345, 'awaiting_edit_confirm_2', {
        'new_reply_id': 2,
        'original_reply_id': 1
    })

    query = {
        'id': 'callback_123',
        'data': 'confirm_edit_2',
        'from': {'id': 12345},
        'message': {'chat': {'id': 12345}, 'message_id': 100}
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyDAO') as mock_dao:
            mock_dao.get_reply_by_id = AsyncMock(return_value={
                'id': 2,
                'content': 'New content',
                'edit_of': 1
            })

            with patch('telegram.handlers.ReplyEditorService') as mock_service:
                mock_service.edit_reply = AsyncMock(return_value={
                    'success': False,
                    'error': 'Message not found',
                    'error_code': 'post_failed'
                })

                await callback_confirm_edit(query, mock_telegram_bot)

                # Verify error message shown
                call_args = mock_telegram_bot.edit_message_text.call_args
                assert 'failed' in call_args[0][2].lower()
                assert 'Message not found' in call_args[0][2]
                assert 'post_failed' in call_args[0][2]

                # Verify FSM state cleared
                state = mock_telegram_bot.get_user_state(12345)
                assert state is None


# =============================================================================
# Tests: callback_cancel_edit
# =============================================================================

@pytest.mark.asyncio
async def test_callback_cancel_edit_success(mock_telegram_bot, mock_db_pool):
    """
    Test callback_cancel_edit successfully cancels edit.

    Verifies:
    - Temp reply deleted from DB
    - Cancellation message shown
    - FSM state cleared
    """
    from telegram.handlers import callback_cancel_edit

    query = {
        'id': 'callback_123',
        'data': 'cancel_edit_2',
        'from': {'id': 12345},
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyDAO') as mock_dao:
            mock_dao.delete_reply = AsyncMock(return_value=True)

            await callback_cancel_edit(query, mock_telegram_bot)

            # Verify temp reply deleted
            mock_dao.delete_reply.assert_called_once_with(
                mock_db_pool.acquire().conn,
                2
            )

            # Verify cancellation message
            call_args = mock_telegram_bot.edit_message_text.call_args
            assert 'cancelled' in call_args[0][2].lower()

            # Verify callback answered
            mock_telegram_bot.answer_callback_query.assert_called_once()

            # Verify FSM state cleared
            state = mock_telegram_bot.get_user_state(12345)
            assert state is None


@pytest.mark.asyncio
async def test_callback_cancel_edit_handles_errors(mock_telegram_bot, mock_db_pool):
    """
    Test callback_cancel_edit handles deletion errors gracefully.

    Verifies that errors during deletion don't crash the handler.
    """
    from telegram.handlers import callback_cancel_edit

    query = {
        'id': 'callback_123',
        'data': 'cancel_edit_2',
        'from': {'id': 12345},
        'message': {'chat': {'id': 12345}, 'message_id': 100}
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyDAO') as mock_dao:
            # Simulate deletion error
            mock_dao.delete_reply = AsyncMock(side_effect=Exception('DB error'))

            await callback_cancel_edit(query, mock_telegram_bot)

            # Verify callback still answered
            mock_telegram_bot.answer_callback_query.assert_called_once()

            # Verify FSM state cleared
            state = mock_telegram_bot.get_user_state(12345)
            assert state is None


# =============================================================================
# Tests: callback_show_edit_history
# =============================================================================

@pytest.mark.asyncio
async def test_callback_show_edit_history_success(mock_telegram_bot, mock_db_pool):
    """
    Test callback_show_edit_history displays formatted history.

    Verifies:
    - History retrieved via ReplyEditorService
    - Formatted with timestamps
    - Status badges shown (CURRENT, ORIGINAL, EDIT)
    """
    from telegram.handlers import callback_show_edit_history

    query = {
        'id': 'callback_123',
        'data': 'show_history_1',
        'from': {'id': 12345},
        'message': {'chat': {'id': 12345}, 'message_id': 100}
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyEditorService') as mock_service:
            mock_service.get_edit_history = AsyncMock(return_value=[
                {
                    'id': 2,
                    'content': 'Latest edit',
                    'content_preview': 'Latest edit',
                    'created_at': datetime.utcnow(),
                    'is_current': True,
                    'is_original': False
                },
                {
                    'id': 1,
                    'content': 'Original text',
                    'content_preview': 'Original text',
                    'created_at': datetime.utcnow() - timedelta(hours=2),
                    'is_current': False,
                    'is_original': True
                }
            ])

            await callback_show_edit_history(query, mock_telegram_bot)

            # Verify history retrieved
            mock_service.get_edit_history.assert_called_once_with(
                mock_db_pool.acquire().conn,
                1
            )

            # Verify message sent (history display)
            mock_telegram_bot.send_message.assert_called_once()
            call_args = mock_telegram_bot.send_message.call_args
            message_text = call_args[0][1]

            # Verify formatting
            assert 'Edit History' in message_text
            assert 'CURRENT' in message_text
            assert 'ORIGINAL' in message_text
            assert 'Latest edit' in message_text
            assert 'Original text' in message_text


@pytest.mark.asyncio
async def test_callback_show_edit_history_no_edits(mock_telegram_bot, mock_db_pool):
    """
    Test callback_show_edit_history when no edits exist.

    Verifies appropriate message shown when history is empty.
    """
    from telegram.handlers import callback_show_edit_history

    query = {
        'id': 'callback_123',
        'data': 'show_history_1',
        'from': {'id': 12345},
        'message': {'chat': {'id': 12345}, 'message_id': 100}
    }

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyEditorService') as mock_service:
            mock_service.get_edit_history = AsyncMock(return_value=[])

            await callback_show_edit_history(query, mock_telegram_bot)

            # Verify "no history" alert shown
            call_args = mock_telegram_bot.answer_callback_query.call_args
            assert 'no' in call_args[1]['text'].lower()
            assert 'history' in call_args[1]['text'].lower()
            assert call_args[1]['show_alert'] is True


@pytest.mark.asyncio
async def test_callback_show_edit_history_formats_timestamps(mock_telegram_bot, mock_db_pool):
    """
    Test that edit history displays properly formatted timestamps.

    Verifies timestamps are human-readable.
    """
    from telegram.handlers import callback_show_edit_history

    query = {
        'id': 'callback_123',
        'data': 'show_history_1',
        'from': {'id': 12345},
        'message': {'chat': {'id': 12345}, 'message_id': 100}
    }

    test_time = datetime(2024, 1, 15, 14, 30, 0)

    with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_db_pool):
        with patch('telegram.handlers.ReplyEditorService') as mock_service:
            mock_service.get_edit_history = AsyncMock(return_value=[
                {
                    'id': 1,
                    'content': 'Test',
                    'content_preview': 'Test',
                    'created_at': test_time,
                    'is_current': True,
                    'is_original': True
                }
            ])

            await callback_show_edit_history(query, mock_telegram_bot)

            call_args = mock_telegram_bot.send_message.call_args
            message_text = call_args[0][1]

            # Verify timestamp formatting (YYYY-MM-DD HH:MM)
            assert '2024-01-15' in message_text
            assert '14:30' in message_text
