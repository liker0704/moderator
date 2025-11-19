"""
Pytest configuration and shared fixtures.
"""
import sys
import os
import pytest
from unittest.mock import Mock, MagicMock
import asyncio
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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


# =============================================================================
# Enhanced Test Fixtures for Comprehensive Test Suite
# =============================================================================

@pytest.fixture
async def db_pool():
    """
    Create a test database connection pool.

    Note: This fixture requires a running PostgreSQL test database.
    For unit tests, use mock_db_connection instead.
    """
    import asyncpg
    try:
        pool = await asyncpg.create_pool(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', '5432')),
            database=os.environ.get('DB_NAME', 'moderator_test'),
            user=os.environ.get('DB_USER', 'test'),
            password=os.environ.get('DB_PASSWORD', 'test'),
            min_size=1,
            max_size=5
        )
        yield pool
        await pool.close()
    except Exception as e:
        # If database is not available, skip tests that require it
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
async def db_connection(db_pool):
    """Get a database connection from the pool."""
    async with db_pool.acquire() as conn:
        # Start a transaction for isolation
        async with conn.transaction():
            yield conn
            # Transaction will be rolled back after test


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'telegram_user_id': 12345,
        'username': 'test_user',
        'created_at': datetime.now()
    }


@pytest.fixture
def sample_discord_connection_data():
    """Sample Discord connection data for testing."""
    return {
        'user_id': 1,
        'discord_user_token': 'test_discord_token_encrypted',
        'discord_user_id': '9876543210',
        'client_build_number': '12345',
        'status': 'connected'
    }


@pytest.fixture
def sample_attachment_data():
    """Sample attachment data for testing."""
    return {
        'message_id': 1,
        'file_type': 'image',
        'file_url': 'https://example.com/image.png',
        'file_size': 1024000,
        'filename': 'test_image.png'
    }


@pytest.fixture
def sample_audit_log_data():
    """Sample audit log data for testing."""
    return {
        'event_kind': 'message_created',
        'user_id': 1,
        'details': {'message_id': 1, 'action': 'create'},
        'severity': 'info'
    }


@pytest.fixture
def sample_ai_variant_data():
    """Sample AI variant data for testing."""
    return {
        'task_id': 1,
        'content': 'AI generated response',
        'confidence_score': 0.85,
        'tone': 'neutral'
    }


@pytest.fixture
def sample_allowlist_data():
    """Sample allowlist data for testing."""
    return {
        'server_id': '1111111111',
        'channel_id': '9876543210',
        'added_by': 1,
        'enabled': True,
        'thread_filter': 'all'
    }


@pytest.fixture
def sample_channel_data():
    """Sample channel data for testing."""
    return {
        'server_id': '1111111111',
        'channel_id': '9876543210',
        'channel_name': 'general',
        'channel_type': 'text'
    }


@pytest.fixture
def mock_discord_client():
    """Mock Discord API client for testing."""
    client = MagicMock()

    async def mock_send_message(*args, **kwargs):
        return {
            'id': '1234567890',
            'channel_id': kwargs.get('channel_id', '9876543210'),
            'content': kwargs.get('content', ''),
            'timestamp': datetime.now().isoformat()
        }

    async def mock_get_message(*args, **kwargs):
        return {
            'id': args[0] if args else '1234567890',
            'channel_id': '9876543210',
            'content': 'Test message',
            'author': {'id': '2222222222', 'username': 'testuser'}
        }

    async def mock_get_channels(*args, **kwargs):
        return [
            {'id': '9876543210', 'name': 'general', 'type': 0},
            {'id': '9876543211', 'name': 'random', 'type': 0}
        ]

    client.send_message = mock_send_message
    client.get_message = mock_get_message
    client.get_channels = mock_get_channels
    client.connected = True

    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = MagicMock()

    async def mock_generate_response(*args, **kwargs):
        return {
            'content': 'This is a mock LLM response.',
            'confidence': 0.85,
            'tokens_used': 150
        }

    async def mock_generate_variants(*args, **kwargs):
        return [
            {'content': 'Variant 1', 'confidence': 0.90, 'tone': 'neutral'},
            {'content': 'Variant 2', 'confidence': 0.85, 'tone': 'soft'},
            {'content': 'Variant 3', 'confidence': 0.80, 'tone': 'formal'}
        ]

    client.generate_response = mock_generate_response
    client.generate_variants = mock_generate_variants
    client.provider = 'openai'
    client.model = 'gpt-4-turbo'

    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    client = MagicMock()
    storage = {}

    async def mock_get(key):
        return storage.get(key)

    async def mock_set(key, value, *args, **kwargs):
        storage[key] = value
        return True

    async def mock_delete(key):
        if key in storage:
            del storage[key]
        return True

    async def mock_exists(key):
        return key in storage

    client.get = mock_get
    client.set = mock_set
    client.delete = mock_delete
    client.exists = mock_exists
    client.storage = storage

    return client


@pytest.fixture
def sample_e2e_workflow_data():
    """Sample data for end-to-end workflow testing."""
    return {
        'discord_message': {
            'id': '1234567890',
            'channel_id': '9876543210',
            'server_id': '1111111111',
            'author': {
                'id': '2222222222',
                'username': 'testuser'
            },
            'content': 'Hello, I need help with something!',
            'timestamp': datetime.now().isoformat()
        },
        'telegram_card': {
            'text': '**New Message from Discord**\n\nFrom: testuser\nChannel: general\n\nHello, I need help with something!',
            'reply_markup': {
                'inline_keyboard': [[
                    {'text': 'Reply', 'callback_data': 'reply_1'},
                    {'text': 'More Context', 'callback_data': 'more_1'}
                ]]
            }
        },
        'llm_response': {
            'content': 'Thank you for reaching out! How can I assist you?',
            'confidence': 0.88,
            'tone': 'neutral'
        },
        'moderator_reply': {
            'content': 'Thank you for reaching out! How can I assist you?',
            'confirmed': True,
            'posted': False
        }
    }


@pytest.fixture
def test_data_generator():
    """Factory fixture for generating test data."""
    class TestDataGenerator:
        @staticmethod
        def generate_message(override=None):
            """Generate a sample message."""
            data = {
                'platform': 'discord',
                'ext_message_id': f'msg_{id(override)}',
                'channel_id': '9876543210',
                'server_id': '1111111111',
                'author_id': '2222222222',
                'author_name': 'TestUser',
                'content': 'Test message content',
                'has_image': False,
                'created_at': datetime.now()
            }
            if override:
                data.update(override)
            return data

        @staticmethod
        def generate_task(override=None):
            """Generate a sample task."""
            data = {
                'source_message_id': 1,
                'assignee_id': 1,
                'status': 'pending',
                'created_at': datetime.now()
            }
            if override:
                data.update(override)
            return data

        @staticmethod
        def generate_reply(override=None):
            """Generate a sample reply."""
            data = {
                'task_id': 1,
                'content': 'Test reply content',
                'generated_by': 'human',
                'is_confirmed': False,
                'is_posted': False,
                'created_at': datetime.now()
            }
            if override:
                data.update(override)
            return data

        @staticmethod
        def generate_users(count=5):
            """Generate multiple test users."""
            return [
                {
                    'telegram_user_id': 10000 + i,
                    'username': f'user_{i}',
                    'created_at': datetime.now()
                }
                for i in range(count)
            ]

        @staticmethod
        def generate_messages(count=10, channel_id='9876543210'):
            """Generate multiple test messages."""
            return [
                {
                    'platform': 'discord',
                    'ext_message_id': f'msg_{i}',
                    'channel_id': channel_id,
                    'server_id': '1111111111',
                    'author_id': f'author_{i % 3}',
                    'author_name': f'User_{i % 3}',
                    'content': f'Test message {i}',
                    'has_image': i % 3 == 0,
                    'created_at': datetime.now()
                }
                for i in range(count)
            ]

    return TestDataGenerator()


@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.duration = None

        def start(self):
            """Start the timer."""
            self.start_time = time.time()

        def stop(self):
            """Stop the timer and return duration in ms."""
            self.end_time = time.time()
            self.duration = (self.end_time - self.start_time) * 1000
            return self.duration

        def get_duration_ms(self):
            """Get duration in milliseconds."""
            if self.duration is None:
                return (time.time() - self.start_time) * 1000
            return self.duration

    return PerformanceTimer()


@pytest.fixture
def cleanup_helper():
    """Helper fixture for test cleanup operations."""
    cleanup_tasks = []

    def add_cleanup(func, *args, **kwargs):
        """Add a cleanup task to be executed after test."""
        cleanup_tasks.append((func, args, kwargs))

    yield add_cleanup

    # Execute cleanup tasks
    for func, args, kwargs in cleanup_tasks:
        try:
            if asyncio.iscoroutinefunction(func):
                asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
            else:
                func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Cleanup task failed: {e}")


