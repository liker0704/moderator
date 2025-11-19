"""
Comprehensive unit tests for reply editing feature.

Tests both ReplyDAO and ReplyEditorService for:
- Permission validation
- Reply creation with edit_of
- Edit history tracking
- Audit logging
- Error handling
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta
import json

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from backend.src.services.reply_editor import ReplyEditorService
from backend.src.database.dao.reply_dao import ReplyDAO


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_conn():
    """Mock asyncpg.Connection for database operations."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    return conn


@pytest.fixture
def posted_reply():
    """Sample reply that was posted 1 hour ago."""
    return {
        'id': 100,
        'task_id': 1,
        'content': 'Original reply content',
        'generated_by': 'human',
        'llm_confidence': None,
        'confirmed': True,
        'posted_at': datetime.utcnow() - timedelta(hours=1),
        'platform_ref': json.dumps({
            'platform': 'telegram',
            'chat_id': '12345',
            'message_id': '67890'
        }),
        'edit_of': None,
        'created_at': datetime.utcnow() - timedelta(hours=2),
        'assignee_user_id': 1,
        'platform': 'telegram',
        'channel_id': '12345',
        'hours_since_posted': 1.0
    }


@pytest.fixture
def old_reply():
    """Sample reply that was posted 50 hours ago (too old to edit)."""
    return {
        'id': 101,
        'task_id': 1,
        'content': 'Old reply content',
        'generated_by': 'human',
        'llm_confidence': None,
        'confirmed': True,
        'posted_at': datetime.utcnow() - timedelta(hours=50),
        'platform_ref': '{"platform": "telegram"}',
        'edit_of': None,
        'created_at': datetime.utcnow() - timedelta(hours=51),
        'assignee_user_id': 1,
        'platform': 'telegram',
        'channel_id': '12345',
        'hours_since_posted': 50.0
    }


@pytest.fixture
def unposted_reply():
    """Sample reply that hasn't been posted yet."""
    return {
        'id': 102,
        'task_id': 1,
        'content': 'Unposted reply',
        'generated_by': 'human',
        'llm_confidence': None,
        'confirmed': True,
        'posted_at': None,
        'platform_ref': None,
        'edit_of': None,
        'created_at': datetime.utcnow(),
        'assignee_user_id': 1,
        'platform': None,
        'channel_id': None,
        'hours_since_posted': None
    }


@pytest.fixture
def sample_task():
    """Sample task for testing."""
    return {
        'id': 1,
        'source_message_id': 1,
        'assignee_user_id': 1,
        'status': 'pending',
        'created_at': datetime.utcnow()
    }


@pytest.fixture
def muted_task():
    """Sample muted task."""
    return {
        'id': 2,
        'source_message_id': 2,
        'assignee_user_id': 1,
        'status': 'muted',
        'created_at': datetime.utcnow()
    }


# ============================================================================
# Tests for ReplyDAO.can_edit_reply()
# ============================================================================

class TestReplyDAOCanEdit:
    """Test ReplyDAO.can_edit_reply() validation logic."""

    @pytest.mark.asyncio
    async def test_can_edit_valid_reply(self, mock_conn, posted_reply):
        """Test that a valid reply can be edited."""
        mock_conn.fetchrow.return_value = posted_reply

        result = await ReplyDAO.can_edit_reply(mock_conn, reply_id=100, user_id=1)

        assert result['can_edit'] is True
        assert 'reply' in result
        assert result['reply']['id'] == 100
        assert result['hours_since_posted'] == 1.0
        assert 'reason' not in result

    @pytest.mark.asyncio
    async def test_cannot_edit_old_reply(self, mock_conn, old_reply):
        """Test that a reply older than 48 hours cannot be edited."""
        mock_conn.fetchrow.return_value = old_reply

        result = await ReplyDAO.can_edit_reply(
            mock_conn, reply_id=101, user_id=1, time_limit_hours=48
        )

        assert result['can_edit'] is False
        assert result['reason'] == 'time_expired'
        assert result['hours_since_posted'] == 50.0

    @pytest.mark.asyncio
    async def test_cannot_edit_nonexistent_reply(self, mock_conn):
        """Test that a non-existent reply returns not_found."""
        mock_conn.fetchrow.return_value = None

        result = await ReplyDAO.can_edit_reply(mock_conn, reply_id=999, user_id=1)

        assert result['can_edit'] is False
        assert result['reason'] == 'not_found'
        assert result['reply'] is None

    @pytest.mark.asyncio
    async def test_cannot_edit_unposted_reply(self, mock_conn, unposted_reply):
        """Test that an unposted reply cannot be edited."""
        mock_conn.fetchrow.return_value = unposted_reply

        result = await ReplyDAO.can_edit_reply(mock_conn, reply_id=102, user_id=1)

        assert result['can_edit'] is False
        assert result['reason'] == 'not_posted'
        assert result['reply']['posted_at'] is None

    @pytest.mark.asyncio
    async def test_cannot_edit_other_users_reply(self, mock_conn, posted_reply):
        """Test that a user cannot edit another user's reply."""
        # Reply belongs to user 1, but user 2 is trying to edit
        mock_conn.fetchrow.return_value = posted_reply

        result = await ReplyDAO.can_edit_reply(mock_conn, reply_id=100, user_id=2)

        assert result['can_edit'] is False
        assert result['reason'] == 'permission_denied'

    @pytest.mark.asyncio
    async def test_custom_time_limit(self, mock_conn):
        """Test can_edit_reply with custom time limit."""
        # Reply posted 3 hours ago
        reply = {
            'id': 103,
            'task_id': 1,
            'posted_at': datetime.utcnow() - timedelta(hours=3),
            'assignee_user_id': 1,
            'hours_since_posted': 3.0
        }
        mock_conn.fetchrow.return_value = reply

        # Should fail with 2-hour limit
        result = await ReplyDAO.can_edit_reply(
            mock_conn, reply_id=103, user_id=1, time_limit_hours=2
        )

        assert result['can_edit'] is False
        assert result['reason'] == 'time_expired'


# ============================================================================
# Tests for ReplyDAO.create_edited_reply()
# ============================================================================

class TestReplyDAOCreateEdit:
    """Test ReplyDAO.create_edited_reply() functionality."""

    @pytest.mark.asyncio
    async def test_create_edited_reply_success(self, mock_conn, posted_reply):
        """Test successfully creating an edited reply."""
        # Mock can_edit_reply to return valid
        with patch.object(ReplyDAO, 'can_edit_reply', new_callable=AsyncMock) as mock_can_edit:
            mock_can_edit.return_value = {
                'can_edit': True,
                'reply': posted_reply,
                'hours_since_posted': 1.0
            }

            # Mock the INSERT query
            mock_conn.fetchrow.return_value = {'id': 200}

            # Mock audit logging
            with patch('backend.src.database.dao.reply_dao.AuditDAO.log_event', new_callable=AsyncMock) as mock_audit:
                new_reply_id = await ReplyDAO.create_edited_reply(
                    mock_conn,
                    original_reply_id=100,
                    new_content='Updated content',
                    user_id=1
                )

                assert new_reply_id == 200

                # Verify INSERT was called with correct parameters
                insert_call = mock_conn.fetchrow.call_args
                assert insert_call[0][1] == 1  # task_id
                assert insert_call[0][2] == 'Updated content'  # content
                assert insert_call[0][3] == 'human'  # generated_by
                assert insert_call[0][6] == 100  # edit_of

                # Verify audit log was created
                mock_audit.assert_called_once()
                audit_args = mock_audit.call_args
                assert audit_args[1]['kind'] == 'reply.edit_started'

    @pytest.mark.asyncio
    async def test_create_edited_reply_sets_edit_of(self, mock_conn, posted_reply):
        """Test that create_edited_reply correctly sets edit_of field."""
        with patch.object(ReplyDAO, 'can_edit_reply', new_callable=AsyncMock) as mock_can_edit:
            mock_can_edit.return_value = {
                'can_edit': True,
                'reply': posted_reply,
                'hours_since_posted': 1.0
            }

            mock_conn.fetchrow.return_value = {'id': 201}

            with patch('backend.src.database.dao.reply_dao.AuditDAO.log_event', new_callable=AsyncMock):
                await ReplyDAO.create_edited_reply(
                    mock_conn,
                    original_reply_id=100,
                    new_content='New content',
                    user_id=1
                )

                # Check that edit_of was set to 100
                insert_call = mock_conn.fetchrow.call_args
                assert insert_call[0][6] == 100  # edit_of parameter

    @pytest.mark.asyncio
    async def test_create_edited_reply_audit_log(self, mock_conn, posted_reply):
        """Test that create_edited_reply creates proper audit log entry."""
        with patch.object(ReplyDAO, 'can_edit_reply', new_callable=AsyncMock) as mock_can_edit:
            mock_can_edit.return_value = {
                'can_edit': True,
                'reply': posted_reply,
                'hours_since_posted': 1.0
            }

            mock_conn.fetchrow.return_value = {'id': 202}

            with patch('backend.src.database.dao.reply_dao.AuditDAO.log_event', new_callable=AsyncMock) as mock_audit:
                await ReplyDAO.create_edited_reply(
                    mock_conn,
                    original_reply_id=100,
                    new_content='Edited text',
                    user_id=1
                )

                # Verify audit log payload
                audit_call = mock_audit.call_args
                payload = json.loads(audit_call[1]['payload_json'])

                assert payload['original_reply_id'] == 100
                assert payload['new_reply_id'] == 202
                assert payload['task_id'] == 1
                assert payload['user_id'] == 1
                assert payload['new_content_length'] == len('Edited text')

    @pytest.mark.asyncio
    async def test_create_edited_reply_preserves_task_id(self, mock_conn, posted_reply):
        """Test that create_edited_reply preserves the original task_id."""
        with patch.object(ReplyDAO, 'can_edit_reply', new_callable=AsyncMock) as mock_can_edit:
            mock_can_edit.return_value = {
                'can_edit': True,
                'reply': posted_reply,
                'hours_since_posted': 1.0
            }

            mock_conn.fetchrow.return_value = {'id': 203}

            with patch('backend.src.database.dao.reply_dao.AuditDAO.log_event', new_callable=AsyncMock):
                await ReplyDAO.create_edited_reply(
                    mock_conn,
                    original_reply_id=100,
                    new_content='Content',
                    user_id=1
                )

                # Verify task_id is preserved
                insert_call = mock_conn.fetchrow.call_args
                assert insert_call[0][1] == 1  # task_id should match original

    @pytest.mark.asyncio
    async def test_create_edited_reply_validation_fails(self, mock_conn):
        """Test that create_edited_reply raises error when validation fails."""
        with patch.object(ReplyDAO, 'can_edit_reply', new_callable=AsyncMock) as mock_can_edit:
            mock_can_edit.return_value = {
                'can_edit': False,
                'reason': 'time_expired',
                'hours_since_posted': 50.0
            }

            with pytest.raises(ValueError) as excinfo:
                await ReplyDAO.create_edited_reply(
                    mock_conn,
                    original_reply_id=100,
                    new_content='Content',
                    user_id=1
                )

            assert 'time limit exceeded' in str(excinfo.value)


# ============================================================================
# Tests for ReplyEditorService.validate_edit_permission()
# ============================================================================

class TestReplyEditorValidation:
    """Test ReplyEditorService.validate_edit_permission()."""

    @pytest.mark.asyncio
    async def test_validate_permission_success(self, mock_conn, posted_reply, sample_task):
        """Test successful permission validation."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            with patch('backend.src.services.reply_editor.TaskDAO.get_task_by_id', new_callable=AsyncMock) as mock_get_task:
                mock_get_reply.return_value = posted_reply
                mock_get_task.return_value = sample_task

                result = await ReplyEditorService.validate_edit_permission(
                    mock_conn,
                    reply_id=100,
                    user_id=1
                )

                assert result['can_edit'] is True
                assert 'reply' in result
                assert 'task' in result
                assert 'reason' not in result

    @pytest.mark.asyncio
    async def test_validate_permission_reply_not_found(self, mock_conn):
        """Test validation when reply doesn't exist."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            mock_get_reply.return_value = None

            result = await ReplyEditorService.validate_edit_permission(
                mock_conn,
                reply_id=999,
                user_id=1
            )

            assert result['can_edit'] is False
            assert result['reason'] == 'Reply not found'

    @pytest.mark.asyncio
    async def test_validate_permission_not_posted(self, mock_conn, unposted_reply):
        """Test validation when reply hasn't been posted."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            mock_get_reply.return_value = unposted_reply

            result = await ReplyEditorService.validate_edit_permission(
                mock_conn,
                reply_id=102,
                user_id=1
            )

            assert result['can_edit'] is False
            assert result['reason'] == 'Reply has not been posted yet'

    @pytest.mark.asyncio
    async def test_validate_permission_task_not_found(self, mock_conn, posted_reply):
        """Test validation when task doesn't exist."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            with patch('backend.src.services.reply_editor.TaskDAO.get_task_by_id', new_callable=AsyncMock) as mock_get_task:
                mock_get_reply.return_value = posted_reply
                mock_get_task.return_value = None

                result = await ReplyEditorService.validate_edit_permission(
                    mock_conn,
                    reply_id=100,
                    user_id=1
                )

                assert result['can_edit'] is False
                assert result['reason'] == 'Associated task not found'

    @pytest.mark.asyncio
    async def test_validate_permission_wrong_user(self, mock_conn, posted_reply, sample_task):
        """Test validation when user doesn't own the task."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            with patch('backend.src.services.reply_editor.TaskDAO.get_task_by_id', new_callable=AsyncMock) as mock_get_task:
                mock_get_reply.return_value = posted_reply
                mock_get_task.return_value = sample_task

                # User 2 trying to edit user 1's reply
                result = await ReplyEditorService.validate_edit_permission(
                    mock_conn,
                    reply_id=100,
                    user_id=2
                )

                assert result['can_edit'] is False
                assert result['reason'] == 'You do not have permission to edit this reply'

    @pytest.mark.asyncio
    async def test_validate_permission_muted_task(self, mock_conn, posted_reply, muted_task):
        """Test validation when task is muted."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            with patch('backend.src.services.reply_editor.TaskDAO.get_task_by_id', new_callable=AsyncMock) as mock_get_task:
                mock_get_reply.return_value = posted_reply
                mock_get_task.return_value = muted_task

                result = await ReplyEditorService.validate_edit_permission(
                    mock_conn,
                    reply_id=100,
                    user_id=1
                )

                assert result['can_edit'] is False
                assert result['reason'] == 'Cannot edit reply for muted task'

    @pytest.mark.asyncio
    async def test_validate_permission_time_expired(self, mock_conn, old_reply, sample_task):
        """Test validation when time limit has expired."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get_reply:
            with patch('backend.src.services.reply_editor.TaskDAO.get_task_by_id', new_callable=AsyncMock) as mock_get_task:
                mock_get_reply.return_value = old_reply
                mock_get_task.return_value = sample_task

                result = await ReplyEditorService.validate_edit_permission(
                    mock_conn,
                    reply_id=101,
                    user_id=1,
                    time_limit_hours=48
                )

                assert result['can_edit'] is False
                assert '48 hours' in result['reason']


# ============================================================================
# Tests for ReplyEditorService.create_edited_reply()
# ============================================================================

class TestReplyEditorCreate:
    """Test ReplyEditorService.create_edited_reply()."""

    @pytest.mark.asyncio
    async def test_create_edited_reply_success(self, mock_conn, posted_reply):
        """Test creating an edited reply successfully."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'create_reply', new_callable=AsyncMock) as mock_create:
                with patch.object(ReplyDAO, 'mark_reply_confirmed', new_callable=AsyncMock):
                    mock_get.return_value = posted_reply
                    mock_create.return_value = 300

                    new_id = await ReplyEditorService.create_edited_reply(
                        mock_conn,
                        original_reply_id=100,
                        new_content='Edited content',
                        user_id=1
                    )

                    assert new_id == 300

                    # Verify create_reply was called with correct params
                    mock_create.assert_called_once()
                    create_args = mock_create.call_args[1]
                    assert create_args['task_id'] == 1
                    assert create_args['content'] == 'Edited content'
                    assert create_args['edit_of'] == 100

    @pytest.mark.asyncio
    async def test_create_edited_reply_marks_confirmed(self, mock_conn, posted_reply):
        """Test that edited reply is marked as confirmed."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'create_reply', new_callable=AsyncMock) as mock_create:
                with patch.object(ReplyDAO, 'mark_reply_confirmed', new_callable=AsyncMock) as mock_confirm:
                    mock_get.return_value = posted_reply
                    mock_create.return_value = 301

                    await ReplyEditorService.create_edited_reply(
                        mock_conn,
                        original_reply_id=100,
                        new_content='Content',
                        user_id=1
                    )

                    # Verify mark_reply_confirmed was called with new ID
                    mock_confirm.assert_called_once_with(mock_conn, 301)

    @pytest.mark.asyncio
    async def test_create_edited_reply_original_not_found(self, mock_conn):
        """Test error when original reply doesn't exist."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError) as excinfo:
                await ReplyEditorService.create_edited_reply(
                    mock_conn,
                    original_reply_id=999,
                    new_content='Content',
                    user_id=1
                )

            assert 'not found' in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_create_edited_reply_preserves_metadata(self, mock_conn, posted_reply):
        """Test that edited reply preserves original metadata."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'create_reply', new_callable=AsyncMock) as mock_create:
                with patch.object(ReplyDAO, 'mark_reply_confirmed', new_callable=AsyncMock):
                    mock_get.return_value = posted_reply
                    mock_create.return_value = 302

                    await ReplyEditorService.create_edited_reply(
                        mock_conn,
                        original_reply_id=100,
                        new_content='New content',
                        user_id=1
                    )

                    # Verify metadata is preserved
                    create_args = mock_create.call_args[1]
                    assert create_args['generated_by'] == 'human'
                    assert create_args['llm_confidence'] is None


# ============================================================================
# Tests for ReplyEditorService.get_edit_history()
# ============================================================================

class TestReplyEditorHistory:
    """Test ReplyEditorService.get_edit_history()."""

    @pytest.mark.asyncio
    async def test_get_edit_history_single_edit(self, mock_conn):
        """Test getting edit history with one edit."""
        original = {
            'id': 100,
            'content': 'Original content',
            'created_at': datetime.utcnow() - timedelta(hours=2),
            'edit_of': None,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow() - timedelta(hours=2)
        }
        edited = {
            'id': 200,
            'content': 'Edited content',
            'created_at': datetime.utcnow() - timedelta(hours=1),
            'edit_of': 100,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow() - timedelta(hours=1)
        }

        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'get_reply_history', new_callable=AsyncMock) as mock_history:
                mock_get.return_value = edited
                mock_history.return_value = [original, edited]

                history = await ReplyEditorService.get_edit_history(mock_conn, reply_id=200)

                assert len(history) == 2
                assert history[0]['is_current'] is True
                assert history[0]['id'] == 200
                assert history[1]['is_original'] is True
                assert history[1]['id'] == 100

    @pytest.mark.asyncio
    async def test_get_edit_history_multiple_edits(self, mock_conn):
        """Test getting edit history with multiple edits (chain)."""
        original = {
            'id': 100,
            'content': 'Original',
            'created_at': datetime.utcnow() - timedelta(hours=3),
            'edit_of': None,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow() - timedelta(hours=3)
        }
        edit1 = {
            'id': 200,
            'content': 'First edit',
            'created_at': datetime.utcnow() - timedelta(hours=2),
            'edit_of': 100,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow() - timedelta(hours=2)
        }
        edit2 = {
            'id': 300,
            'content': 'Second edit',
            'created_at': datetime.utcnow() - timedelta(hours=1),
            'edit_of': 200,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow() - timedelta(hours=1)
        }

        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'get_reply_history', new_callable=AsyncMock) as mock_history:
                # Simulate walking back to find original
                mock_get.side_effect = [edit2, edit1, original]
                mock_history.return_value = [original, edit1, edit2]

                history = await ReplyEditorService.get_edit_history(mock_conn, reply_id=300)

                assert len(history) == 3
                assert history[0]['is_current'] is True
                assert history[0]['id'] == 300
                assert history[1]['id'] == 200
                assert history[2]['is_original'] is True
                assert history[2]['id'] == 100

    @pytest.mark.asyncio
    async def test_get_edit_history_no_edits(self, mock_conn):
        """Test getting edit history for original message (no edits)."""
        original = {
            'id': 100,
            'content': 'Original content',
            'created_at': datetime.utcnow(),
            'edit_of': None,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow()
        }

        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'get_reply_history', new_callable=AsyncMock) as mock_history:
                mock_get.return_value = original
                mock_history.return_value = [original]

                history = await ReplyEditorService.get_edit_history(mock_conn, reply_id=100)

                assert len(history) == 1
                assert history[0]['is_current'] is True
                assert history[0]['is_original'] is True
                assert history[0]['id'] == 100

    @pytest.mark.asyncio
    async def test_get_edit_history_reply_not_found(self, mock_conn):
        """Test getting edit history when reply doesn't exist."""
        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            history = await ReplyEditorService.get_edit_history(mock_conn, reply_id=999)

            assert history == []

    @pytest.mark.asyncio
    async def test_get_edit_history_content_truncation(self, mock_conn):
        """Test that edit history truncates content correctly."""
        long_content = 'x' * 200
        original = {
            'id': 100,
            'content': long_content,
            'created_at': datetime.utcnow(),
            'edit_of': None,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow()
        }

        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'get_reply_history', new_callable=AsyncMock) as mock_history:
                mock_get.return_value = original
                mock_history.return_value = [original]

                history = await ReplyEditorService.get_edit_history(mock_conn, reply_id=100)

                assert len(history[0]['content']) == 103  # 100 chars + '...'
                assert history[0]['content'].endswith('...')
                assert len(history[0]['content_preview']) == 53  # 50 chars + '...'
                assert history[0]['full_content'] == long_content

    @pytest.mark.asyncio
    async def test_get_edit_history_broken_chain(self, mock_conn):
        """Test handling of broken edit chain."""
        edit = {
            'id': 200,
            'content': 'Edited content',
            'created_at': datetime.utcnow(),
            'edit_of': 100,
            'generated_by': 'human',
            'confirmed': True,
            'posted_at': datetime.utcnow()
        }

        with patch.object(ReplyDAO, 'get_reply_by_id', new_callable=AsyncMock) as mock_get:
            with patch.object(ReplyDAO, 'get_reply_history', new_callable=AsyncMock) as mock_history:
                # First call returns edit, second returns None (broken chain)
                mock_get.side_effect = [edit, None]
                mock_history.return_value = []

                history = await ReplyEditorService.get_edit_history(mock_conn, reply_id=200)

                assert history == []
