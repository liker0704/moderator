"""
Unit tests for Reminder Service.

Tests the reminder system functionality including:
- Reminder filtering logic
- Text formatting
- DND mode integration
- Max reminders limit
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncpg


# Test constants
REMINDER_INTERVAL_MINUTES = 30
MAX_REMINDERS = 3
MIN_TASK_AGE_MINUTES = 30


class TestReminderService:
    """Test cases for ReminderService class."""

    @pytest.fixture
    def mock_telegram_bot(self):
        """Create a mock Telegram bot."""
        bot = Mock()
        bot.send_message = AsyncMock(return_value={'ok': True, 'result': {'message_id': 123}})
        return bot

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock()
        config.telegram = Mock()
        config.telegram.moderator_user_id = 12345
        return config

    @pytest_asyncio.fixture
    async def reminder_service(self, mock_telegram_bot, mock_config):
        """Create a ReminderService instance."""
        with patch('services.reminders.get_config', return_value=mock_config):
            from services.reminders import ReminderService
            service = ReminderService(mock_telegram_bot)
            return service

    @pytest.mark.asyncio
    async def test_should_send_reminder_max_reminders_reached(self, reminder_service):
        """Test that reminders are not sent when max count is reached."""
        # Mock database connection
        mock_conn = AsyncMock()

        # Create task with max reminders
        task = {
            'id': 1,
            'assignee_user_id': 1,
            'reminder_count': MAX_REMINDERS,
            'created_at': datetime.utcnow() - timedelta(hours=2),
            'updated_at': datetime.utcnow() - timedelta(hours=1),
            'source_message_id': 100
        }

        should_send, reason = await reminder_service._should_send_reminder(mock_conn, task)

        assert should_send is False
        assert "max reminders reached" in reason

    @pytest.mark.asyncio
    async def test_should_send_reminder_task_too_new(self, reminder_service):
        """Test that reminders are not sent for new tasks."""
        mock_conn = AsyncMock()

        # Create task that's too new
        task = {
            'id': 1,
            'assignee_user_id': 1,
            'reminder_count': 0,
            'created_at': datetime.utcnow() - timedelta(minutes=10),
            'updated_at': datetime.utcnow() - timedelta(minutes=10),
            'source_message_id': 100
        }

        should_send, reason = await reminder_service._should_send_reminder(mock_conn, task)

        assert should_send is False
        assert "task too new" in reason

    @pytest.mark.asyncio
    async def test_should_send_reminder_not_enough_time_since_update(self, reminder_service):
        """Test that reminders respect minimum interval."""
        mock_conn = AsyncMock()

        # Create task updated recently
        task = {
            'id': 1,
            'assignee_user_id': 1,
            'reminder_count': 0,
            'created_at': datetime.utcnow() - timedelta(hours=2),
            'updated_at': datetime.utcnow() - timedelta(minutes=10),
            'source_message_id': 100
        }

        should_send, reason = await reminder_service._should_send_reminder(mock_conn, task)

        assert should_send is False
        assert "not enough time since last update" in reason

    @pytest.mark.asyncio
    async def test_should_send_reminder_user_disabled(self, reminder_service):
        """Test that reminders respect user settings."""
        mock_conn = AsyncMock()

        # Mock UserDAO to return settings with reminders disabled
        with patch('services.reminders.UserDAO') as MockUserDAO:
            MockUserDAO.get_user_settings = AsyncMock(return_value={
                'reminders_enabled': False,
                'dnd_enabled': False
            })

            task = {
                'id': 1,
                'assignee_user_id': 1,
                'reminder_count': 0,
                'created_at': datetime.utcnow() - timedelta(hours=2),
                'updated_at': datetime.utcnow() - timedelta(hours=1),
                'source_message_id': 100
            }

            should_send, reason = await reminder_service._should_send_reminder(mock_conn, task)

            assert should_send is False
            assert "user has reminders disabled" in reason

    @pytest.mark.asyncio
    async def test_should_send_reminder_dnd_active(self, reminder_service):
        """Test that reminders respect DND mode."""
        mock_conn = AsyncMock()

        # Mock UserDAO and is_dnd_active
        with patch('services.reminders.UserDAO') as MockUserDAO, \
             patch('services.reminders.is_dnd_active', new_callable=AsyncMock) as mock_dnd:

            MockUserDAO.get_user_settings = AsyncMock(return_value={
                'reminders_enabled': True,
                'dnd_enabled': True
            })
            mock_dnd.return_value = True

            task = {
                'id': 1,
                'assignee_user_id': 1,
                'reminder_count': 0,
                'created_at': datetime.utcnow() - timedelta(hours=2),
                'updated_at': datetime.utcnow() - timedelta(hours=1),
                'source_message_id': 100
            }

            should_send, reason = await reminder_service._should_send_reminder(mock_conn, task)

            assert should_send is False
            assert "DND mode active" in reason

    @pytest.mark.asyncio
    async def test_should_send_reminder_success(self, reminder_service):
        """Test successful reminder check."""
        mock_conn = AsyncMock()

        # Mock UserDAO and is_dnd_active
        with patch('services.reminders.UserDAO') as MockUserDAO, \
             patch('services.reminders.is_dnd_active', new_callable=AsyncMock) as mock_dnd:

            MockUserDAO.get_user_settings = AsyncMock(return_value={
                'reminders_enabled': True,
                'dnd_enabled': False
            })
            mock_dnd.return_value = False

            task = {
                'id': 1,
                'assignee_user_id': 1,
                'reminder_count': 0,
                'created_at': datetime.utcnow() - timedelta(hours=2),
                'updated_at': datetime.utcnow() - timedelta(hours=1),
                'source_message_id': 100
            }

            should_send, reason = await reminder_service._should_send_reminder(mock_conn, task)

            assert should_send is True
            assert reason == "ok"

    def test_build_reminder_text_first_reminder(self, reminder_service):
        """Test reminder text formatting for first reminder."""
        task = {
            'id': 42,
            'reminder_count': 0,
            'created_at': datetime.utcnow() - timedelta(hours=1, minutes=30)
        }

        message = {
            'platform': 'discord',
            'author_name': 'TestUser',
            'content': 'This is a test message',
            'channel_id': '123456789'
        }

        text = reminder_service._build_reminder_text(task, message)

        assert "🔔" in text
        assert "Reminder" in text
        assert "Task #42" in text
        assert "1h 30m" in text
        assert "TestUser" in text
        assert "discord" in text
        assert "This is a test message" in text

    def test_build_reminder_text_second_reminder(self, reminder_service):
        """Test reminder text formatting for second reminder."""
        task = {
            'id': 42,
            'reminder_count': 1,
            'created_at': datetime.utcnow() - timedelta(hours=2)
        }

        message = {
            'platform': 'discord',
            'author_name': 'TestUser',
            'content': 'Test message',
            'channel_id': '123456789'
        }

        text = reminder_service._build_reminder_text(task, message)

        assert "2nd Reminder" in text

    def test_build_reminder_text_final_reminder(self, reminder_service):
        """Test reminder text formatting for final reminder."""
        task = {
            'id': 42,
            'reminder_count': 2,
            'created_at': datetime.utcnow() - timedelta(hours=3)
        }

        message = {
            'platform': 'discord',
            'author_name': 'TestUser',
            'content': 'Test message',
            'channel_id': '123456789'
        }

        text = reminder_service._build_reminder_text(task, message)

        assert "Final Reminder" in text

    def test_build_reminder_text_truncate_long_content(self, reminder_service):
        """Test that long message content is truncated."""
        task = {
            'id': 42,
            'reminder_count': 0,
            'created_at': datetime.utcnow() - timedelta(hours=1)
        }

        # Create very long content
        long_content = "A" * 300

        message = {
            'platform': 'discord',
            'author_name': 'TestUser',
            'content': long_content,
            'channel_id': '123456789'
        }

        text = reminder_service._build_reminder_text(task, message)

        # Content should be truncated to 200 chars + "..."
        assert len(message['content']) > 200
        assert "..." in text
        assert text.count('A') < 300

    @pytest.mark.asyncio
    async def test_send_reminder_success(self, reminder_service, mock_telegram_bot):
        """Test successful reminder sending."""
        mock_conn = AsyncMock()

        # Mock MessageDAO
        with patch('services.reminders.MessageDAO') as MockMessageDAO:
            MockMessageDAO.get_message_by_id = AsyncMock(return_value={
                'platform': 'discord',
                'author_name': 'TestUser',
                'content': 'Test message',
                'channel_id': '123456789'
            })

            task = {
                'id': 42,
                'source_message_id': 100,
                'reminder_count': 0,
                'created_at': datetime.utcnow() - timedelta(hours=1)
            }

            success = await reminder_service._send_reminder(mock_conn, task)

            assert success is True
            mock_telegram_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_reminder_message_not_found(self, reminder_service, mock_telegram_bot):
        """Test reminder fails when message not found."""
        mock_conn = AsyncMock()

        # Mock MessageDAO to return None
        with patch('services.reminders.MessageDAO') as MockMessageDAO:
            MockMessageDAO.get_message_by_id = AsyncMock(return_value=None)

            task = {
                'id': 42,
                'source_message_id': 100,
                'reminder_count': 0,
                'created_at': datetime.utcnow() - timedelta(hours=1)
            }

            success = await reminder_service._send_reminder(mock_conn, task)

            assert success is False
            mock_telegram_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_reminder_telegram_error(self, reminder_service, mock_telegram_bot):
        """Test reminder handles Telegram send errors."""
        mock_conn = AsyncMock()

        # Mock MessageDAO
        with patch('services.reminders.MessageDAO') as MockMessageDAO:
            MockMessageDAO.get_message_by_id = AsyncMock(return_value={
                'platform': 'discord',
                'author_name': 'TestUser',
                'content': 'Test message',
                'channel_id': '123456789'
            })

            # Make send_message return error
            mock_telegram_bot.send_message.return_value = {
                'ok': False,
                'description': 'Bot was blocked by the user'
            }

            task = {
                'id': 42,
                'source_message_id': 100,
                'reminder_count': 0,
                'created_at': datetime.utcnow() - timedelta(hours=1)
            }

            success = await reminder_service._send_reminder(mock_conn, task)

            assert success is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
