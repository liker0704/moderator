"""
Pytest configuration and shared fixtures.
"""
import sys
import os
import pytest
from unittest.mock import Mock, MagicMock
import asyncio

# Add backend/src to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

# Set test environment variables
os.environ['ENV'] = 'test'
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'moderator_test'
os.environ['DB_USER'] = 'test'
os.environ['DB_PASSWORD'] = 'test'
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_bot_token'
os.environ['TELEGRAM_MODERATOR_USER_ID'] = '12345'
os.environ['DISCORD_USER_TOKEN'] = 'test_discord_token'
os.environ['ENCRYPTION_KEY'] = 'test_encryption_key_32_characters'

# Generate a proper 32-byte base64 key for Fernet
from cryptography.fernet import Fernet
test_key = Fernet.generate_key().decode()
os.environ['ENCRYPTION_KEY'] = test_key

# Mock config module to prevent relative import errors
mock_config = Mock()
mock_config.get_config = Mock(return_value=Mock(
    telegram=Mock(
        bot_token='test_bot_token_12345',
        moderator_user_id=12345,
        alert_chat_id='12345'
    ),
    discord=Mock(
        user_token='test_discord_token',
        client_build_number='12345'
    ),
    database=Mock(
        host='localhost',
        port=5432,
        name='moderator_test',
        user='test',
        password='test'
    ),
    encryption_key='test_encryption_key_32_characters',
    llm=Mock(
        provider='openai',
        model='gpt-4-turbo',
        openai_api_key='test_openai_key',
        anthropic_api_key='test_anthropic_key'
    )
))
sys.modules['config'] = mock_config


@pytest.fixture
def sample_message_data():
    """Sample message data for testing"""
    return {
        'platform': 'discord',
        'ext_message_id': '1234567890',
        'channel_id': '9876543210',
        'server_id': '1111111111',
        'author_id': '2222222222',
        'author_name': 'TestUser',
        'content': 'Test message content',
        'has_image': False
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        'source_message_id': 1,
        'assignee_id': 1,
        'status': 'pending'
    }


@pytest.fixture
def sample_reply_data():
    """Sample reply data for testing"""
    return {
        'task_id': 1,
        'content': 'Test reply content',
        'generated_by': 'human'
    }


@pytest.fixture
def mock_db_connection():
    """Mock database connection for tests that need it."""
    conn = MagicMock()
    conn.execute = MagicMock(return_value=asyncio.Future())
    conn.execute.return_value.set_result(None)
    conn.fetch = MagicMock(return_value=asyncio.Future())
    conn.fetch.return_value.set_result([])
    conn.fetchrow = MagicMock(return_value=asyncio.Future())
    conn.fetchrow.return_value.set_result(None)
    conn.fetchval = MagicMock(return_value=asyncio.Future())
    conn.fetchval.return_value.set_result(None)
    return conn


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for alert tests."""
    bot = MagicMock()

    # Mock send_message to return a proper async future
    async def mock_send_message(*args, **kwargs):
        return {'ok': True, 'result': {'message_id': 123}}

    bot.send_message = mock_send_message
    bot.get_user_state = MagicMock(return_value={})
    bot.set_user_state = MagicMock()
    return bot
