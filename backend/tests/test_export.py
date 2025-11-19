"""
Unit tests for Export functionality.

Tests the export service and DAO including:
- Data retrieval from database
- Anonymization logic
- JSON export generation
- File creation and cleanup
- Export statistics
"""

import pytest
import pytest_asyncio
import os
import json
import tempfile
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal


# Set required environment variables for tests
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up environment variables required for testing."""
    os.environ.setdefault('DB_NAME', 'test_db')
    os.environ.setdefault('DB_USER', 'test_user')
    os.environ.setdefault('DB_PASSWORD', 'test_password')
    os.environ.setdefault('DB_HOST', 'localhost')
    os.environ.setdefault('DB_PORT', '5432')
    os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
    os.environ.setdefault('TELEGRAM_MODERATOR_USER_ID', '123456')
    os.environ.setdefault('MODERATOR_TG_USER_ID', '123456')
    os.environ.setdefault('ALERT_CHAT_ID', '123456')
    os.environ.setdefault('ENCRYPTION_KEY', 'test_encryption_key_32_bytes_long!')
    yield


class TestExportService:
    """Test cases for ExportService."""

    @pytest.mark.asyncio
    async def test_serialize_datetime(self):
        """Test datetime serialization."""
        from services.export import ExportService

        now = datetime.utcnow()
        result = ExportService._serialize_value(now)

        assert isinstance(result, str)
        assert result == now.isoformat()

    @pytest.mark.asyncio
    async def test_serialize_decimal(self):
        """Test Decimal serialization."""
        from services.export import ExportService

        decimal_value = Decimal('123.456')
        result = ExportService._serialize_value(decimal_value)

        assert isinstance(result, float)
        assert result == 123.456

    @pytest.mark.asyncio
    async def test_serialize_none(self):
        """Test None serialization."""
        from services.export import ExportService

        result = ExportService._serialize_value(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_serialize_dict(self):
        """Test dictionary serialization."""
        from services.export import ExportService

        test_dict = {
            'id': 1,
            'created_at': datetime(2025, 1, 1, 12, 0, 0),
            'cost': Decimal('0.0001'),
            'name': 'test',
            'value': None,
        }

        result = ExportService._serialize_dict(test_dict)

        assert result['id'] == 1
        assert result['created_at'] == '2025-01-01T12:00:00'
        assert result['cost'] == 0.0001
        assert result['name'] == 'test'
        assert result['value'] is None

    @pytest.mark.asyncio
    async def test_anonymize_messages(self):
        """Test message anonymization."""
        from services.export import ExportService

        messages = [
            {
                'id': 1,
                'author_id': 'user123',
                'author_name': 'John Doe',
                'channel_id': 'channel456',
                'server_id': 'server789',
                'ext_message_id': 'msg999',
                'content': 'Test message',
            }
        ]

        anonymization_map = {}
        result = ExportService._anonymize_messages(messages, anonymization_map)

        assert len(result) == 1
        assert result[0]['author_id'].startswith('User_')
        assert result[0]['author_name'].startswith('User_')
        assert result[0]['channel_id'].startswith('Channel_')
        assert result[0]['server_id'].startswith('Server_')
        assert result[0]['ext_message_id'] == 'msg_1'
        assert result[0]['content'] == 'Test message'

    @pytest.mark.asyncio
    async def test_anonymize_tasks(self):
        """Test task anonymization."""
        from services.export import ExportService

        tasks = [
            {
                'id': 1,
                'author_id': 'user123',
                'author_name': 'John Doe',
                'channel_id': 'channel456',
                'tg_card_message_id': 12345,
                'status': 'open',
            }
        ]

        anonymization_map = {'user123': 'User_1', 'channel456': 'Channel_1'}
        result = ExportService._anonymize_tasks(tasks, anonymization_map)

        assert len(result) == 1
        assert result[0]['author_id'] == 'User_1'
        assert result[0]['author_name'] == 'User_1'
        assert result[0]['channel_id'] == 'Channel_1'
        assert result[0]['tg_card_message_id'] is None

    @pytest.mark.asyncio
    async def test_anonymize_replies(self):
        """Test reply anonymization."""
        from services.export import ExportService

        replies = [
            {
                'id': 1,
                'author_id': 'user123',
                'channel_id': 'channel456',
                'platform_ref': '{"message_id": "123"}',
                'content': 'Test reply',
            }
        ]

        anonymization_map = {'user123': 'User_1', 'channel456': 'Channel_1'}
        result = ExportService._anonymize_replies(replies, anonymization_map)

        assert len(result) == 1
        assert result[0]['author_id'] == 'User_1'
        assert result[0]['channel_id'] == 'Channel_1'
        assert result[0]['platform_ref'] is None

    @pytest.mark.asyncio
    async def test_anonymize_allowlist(self):
        """Test allowlist anonymization."""
        from services.export import ExportService

        allowlist = [
            {
                'id': 1,
                'channel_id': 'channel456',
                'server_id': 'server789',
                'platform': 'discord',
            }
        ]

        anonymization_map = {'channel456': 'Channel_1', 'server789': 'Server_1'}
        result = ExportService._anonymize_allowlist(allowlist, anonymization_map)

        assert len(result) == 1
        assert result[0]['channel_id'] == 'Channel_1'
        assert result[0]['server_id'] == 'Server_1'

    @pytest.mark.asyncio
    async def test_export_all_data_without_anonymization(self):
        """Test exporting data without anonymization."""
        from services.export import ExportService
        from database.dao.export_dao import ExportDAO

        # Mock the connection and DAO methods
        mock_conn = AsyncMock()

        # Mock data
        messages = [{'id': 1, 'content': 'Test', 'created_at': datetime.utcnow()}]
        tasks = [{'id': 1, 'status': 'open'}]
        replies = [{'id': 1, 'content': 'Reply'}]
        settings = {'dnd_enabled': False}
        allowlist = [{'id': 1, 'channel_id': 'ch1'}]
        templates = [{'id': 1, 'name': 'template1', 'content': 'Template content'}]

        with patch.object(ExportDAO, 'get_all_messages', return_value=messages), \
             patch.object(ExportDAO, 'get_all_tasks', return_value=tasks), \
             patch.object(ExportDAO, 'get_all_replies', return_value=replies), \
             patch.object(ExportDAO, 'get_all_settings', return_value=settings), \
             patch.object(ExportDAO, 'get_all_allowlist', return_value=allowlist), \
             patch.object(ExportDAO, 'get_all_templates', return_value=templates):

            service = ExportService()
            result = await service.export_all_data(mock_conn, user_id=1, anonymize=False)

            assert result['anonymized'] is False
            assert result['user_id'] == 1
            assert result['counts']['messages'] == 1
            assert result['counts']['tasks'] == 1
            assert result['counts']['replies'] == 1
            assert result['counts']['allowlist'] == 1
            assert result['counts']['templates'] == 1
            assert len(result['data']['messages']) == 1
            assert len(result['data']['tasks']) == 1
            assert len(result['data']['replies']) == 1
            assert len(result['data']['allowlist']) == 1
            assert len(result['data']['templates']) == 1

    @pytest.mark.asyncio
    async def test_export_all_data_with_anonymization(self):
        """Test exporting data with anonymization."""
        from services.export import ExportService
        from database.dao.export_dao import ExportDAO

        # Mock the connection and DAO methods
        mock_conn = AsyncMock()

        # Mock data
        messages = [{'id': 1, 'content': 'Test', 'author_id': 'user123',
                     'author_name': 'John', 'channel_id': 'ch1', 'server_id': 'srv1',
                     'ext_message_id': 'msg1', 'created_at': datetime.utcnow()}]
        tasks = [{'id': 1, 'status': 'open', 'author_id': 'user123',
                  'author_name': 'John', 'channel_id': 'ch1',
                  'tg_card_message_id': 123}]
        replies = [{'id': 1, 'content': 'Reply', 'author_id': 'user123',
                    'channel_id': 'ch1', 'platform_ref': '{}'}]
        settings = {'dnd_enabled': False}
        allowlist = [{'id': 1, 'channel_id': 'ch1', 'server_id': 'srv1'}]
        templates = [{'id': 1, 'name': 'template1', 'content': 'Template content'}]

        with patch.object(ExportDAO, 'get_all_messages', return_value=messages), \
             patch.object(ExportDAO, 'get_all_tasks', return_value=tasks), \
             patch.object(ExportDAO, 'get_all_replies', return_value=replies), \
             patch.object(ExportDAO, 'get_all_settings', return_value=settings), \
             patch.object(ExportDAO, 'get_all_allowlist', return_value=allowlist), \
             patch.object(ExportDAO, 'get_all_templates', return_value=templates):

            service = ExportService()
            result = await service.export_all_data(mock_conn, user_id=1, anonymize=True)

            assert result['anonymized'] is True
            assert result['user_id'] == 'anonymized'
            # Check that anonymization occurred
            assert result['data']['messages'][0]['author_id'].startswith('User_')
            assert result['data']['messages'][0]['channel_id'].startswith('Channel_')
            assert result['data']['tasks'][0]['tg_card_message_id'] is None

    @pytest.mark.asyncio
    async def test_create_export_file(self):
        """Test export file creation."""
        from services.export import ExportService
        from database.dao.export_dao import ExportDAO

        # Mock the connection and DAO methods
        mock_conn = AsyncMock()

        # Mock minimal data
        with patch.object(ExportDAO, 'get_all_messages', return_value=[]), \
             patch.object(ExportDAO, 'get_all_tasks', return_value=[]), \
             patch.object(ExportDAO, 'get_all_replies', return_value=[]), \
             patch.object(ExportDAO, 'get_all_settings', return_value=None), \
             patch.object(ExportDAO, 'get_all_allowlist', return_value=[]), \
             patch.object(ExportDAO, 'get_all_templates', return_value=[]):

            service = ExportService()
            file_path, filename = await service.create_export_file(
                mock_conn, user_id=1, anonymize=False
            )

            # Check file was created
            assert os.path.exists(file_path)
            assert filename.startswith('moderator_export_1_')
            assert filename.endswith('.json')

            # Check file contents
            with open(file_path, 'r') as f:
                data = json.load(f)
                assert 'export_date' in data
                assert 'user_id' in data
                assert 'anonymized' in data
                assert 'counts' in data
                assert 'data' in data

            # Cleanup
            ExportService.cleanup_export_file(file_path)
            assert not os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_cleanup_export_file(self):
        """Test export file cleanup."""
        from services.export import ExportService

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(b'test data')
        temp_file.close()

        # Verify file exists
        assert os.path.exists(temp_file.name)

        # Cleanup
        result = ExportService.cleanup_export_file(temp_file.name)

        # Verify file was deleted
        assert result is True
        assert not os.path.exists(temp_file.name)

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_file(self):
        """Test cleanup of non-existent file."""
        from services.export import ExportService

        result = ExportService.cleanup_export_file('/tmp/nonexistent_file.json')
        assert result is False

    @pytest.mark.asyncio
    async def test_get_export_preview(self):
        """Test export preview generation."""
        from services.export import ExportService
        from database.dao.export_dao import ExportDAO

        # Mock the connection
        mock_conn = AsyncMock()

        # Mock statistics
        stats = {
            'messages': 100,
            'tasks': 50,
            'replies': 45,
            'allowlist': 10,
            'templates': 5,
            'llm_requests': 75,
        }

        with patch.object(ExportDAO, 'get_export_statistics', return_value=stats):
            service = ExportService()
            preview = await service.get_export_preview(mock_conn, user_id=1)

            assert '📊 Export Preview' in preview
            assert '100' in preview  # messages count
            assert '50' in preview   # tasks count
            assert '45' in preview   # replies count
            assert '10' in preview   # allowlist count
            assert '5' in preview    # templates count
            assert '75' in preview   # llm_requests count


class TestExportDAO:
    """Test cases for ExportDAO."""

    @pytest.mark.asyncio
    async def test_get_export_statistics(self):
        """Test export statistics retrieval."""
        from database.dao.export_dao import ExportDAO

        # Mock connection with fetchrow
        mock_conn = AsyncMock()

        # Mock different counts for each query
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {'count': 100},  # messages
            {'count': 50},   # tasks
            {'count': 45},   # replies
            {'count': 10},   # allowlist
            {'count': 75},   # llm_requests
            {'count': 5},    # templates
        ])

        result = await ExportDAO.get_export_statistics(mock_conn, user_id=1)

        assert result['messages'] == 100
        assert result['tasks'] == 50
        assert result['replies'] == 45
        assert result['allowlist'] == 10
        assert result['templates'] == 5
        assert result['llm_requests'] == 75

    @pytest.mark.asyncio
    async def test_get_all_messages(self):
        """Test retrieving all messages."""
        from database.dao.export_dao import ExportDAO

        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {'id': 1, 'content': 'Message 1'},
            {'id': 2, 'content': 'Message 2'},
        ])

        result = await ExportDAO.get_all_messages(mock_conn, user_id=1)

        assert len(result) == 2
        assert result[0]['content'] == 'Message 1'
        assert result[1]['content'] == 'Message 2'

    @pytest.mark.asyncio
    async def test_get_all_tasks(self):
        """Test retrieving all tasks."""
        from database.dao.export_dao import ExportDAO

        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {'id': 1, 'status': 'open'},
            {'id': 2, 'status': 'answered'},
        ])

        result = await ExportDAO.get_all_tasks(mock_conn, user_id=1)

        assert len(result) == 2
        assert result[0]['status'] == 'open'
        assert result[1]['status'] == 'answered'

    @pytest.mark.asyncio
    async def test_get_all_replies(self):
        """Test retrieving all replies."""
        from database.dao.export_dao import ExportDAO

        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {'id': 1, 'content': 'Reply 1'},
            {'id': 2, 'content': 'Reply 2'},
        ])

        result = await ExportDAO.get_all_replies(mock_conn, user_id=1)

        assert len(result) == 2
        assert result[0]['content'] == 'Reply 1'
        assert result[1]['content'] == 'Reply 2'

    @pytest.mark.asyncio
    async def test_get_all_settings(self):
        """Test retrieving user settings."""
        from database.dao.export_dao import ExportDAO

        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            'id': 1,
            'dnd_enabled': True,
            'reminders_enabled': False,
        })

        result = await ExportDAO.get_all_settings(mock_conn, user_id=1)

        assert result['dnd_enabled'] is True
        assert result['reminders_enabled'] is False

    @pytest.mark.asyncio
    async def test_get_all_templates(self):
        """Test retrieving all templates."""
        from database.dao.export_dao import ExportDAO

        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {'id': 1, 'name': 'template1', 'content': 'Content 1'},
            {'id': 2, 'name': 'template2', 'content': 'Content 2'},
        ])

        result = await ExportDAO.get_all_templates(mock_conn, user_id=1)

        assert len(result) == 2
        assert result[0]['name'] == 'template1'
        assert result[1]['name'] == 'template2'
