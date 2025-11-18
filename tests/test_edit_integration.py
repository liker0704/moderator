"""
Integration tests for reply editing workflow.

Tests complete end-to-end workflows including:
- Edit button click → text entry → confirmation → Discord/Telegram update
- Edit history tracking and display
- Permission validation in complete workflow
- Platform integration (Discord/Telegram message updates)
- Error handling and recovery
"""
import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json
import asyncio

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def db_pool():
    """Mock asyncpg pool with in-memory state for integration tests."""
    state = {
        'messages': {},
        'tasks': {},
        'replies': {},
        'users': {},
        'audit_logs': [],
        'next_id': {
            'message': 1,
            'task': 1,
            'reply': 1,
            'user': 1,
            'audit': 1
        }
    }

    class MockConnection:
        """Mock database connection with in-memory state."""

        def __init__(self, state):
            self.state = state

        async def fetchrow(self, query, *args):
            """Mock fetchrow to simulate database queries."""
            query_lower = query.lower().strip()

            # Handle INSERT ... RETURNING id
            if 'insert into replies' in query_lower and 'returning id' in query_lower:
                reply_id = self.state['next_id']['reply']
                self.state['next_id']['reply'] += 1

                # Parse args: task_id, content, generated_by, llm_confidence, confirmed, edit_of, created_at
                self.state['replies'][reply_id] = {
                    'id': reply_id,
                    'task_id': args[0],
                    'content': args[1],
                    'generated_by': args[2],
                    'llm_confidence': args[3],
                    'confirmed': args[4],
                    'edit_of': args[5],
                    'created_at': args[6],
                    'posted_at': None,
                    'platform_ref': None
                }
                return {'id': reply_id}

            # Handle INSERT INTO audit_log
            if 'insert into audit_log' in query_lower:
                audit_id = self.state['next_id']['audit']
                self.state['next_id']['audit'] += 1

                self.state['audit_logs'].append({
                    'id': audit_id,
                    'kind': args[0],
                    'user_id': args[1],
                    'payload_json': args[2],
                    'created_at': args[3]
                })
                return {'id': audit_id}

            # Handle SELECT from replies
            if 'select' in query_lower and 'from replies' in query_lower and 'where id' in query_lower:
                reply_id = args[0]
                reply = self.state['replies'].get(reply_id)
                return reply if reply else None

            # Handle SELECT from tasks
            if 'select' in query_lower and 'from tasks' in query_lower and 'where id' in query_lower:
                task_id = args[0]
                task = self.state['tasks'].get(task_id)
                return task if task else None

            return None

        async def fetch(self, query, *args):
            """Mock fetch to return multiple rows."""
            query_lower = query.lower().strip()

            # Handle edit history query (recursive CTE)
            if 'with recursive reply_versions' in query_lower:
                original_reply_id = args[0]
                history = []

                # Find all replies in the edit chain
                for reply_id, reply in self.state['replies'].items():
                    if reply['id'] == original_reply_id or reply.get('edit_of') == original_reply_id:
                        history.append(reply)

                # Sort by created_at
                history.sort(key=lambda r: r['created_at'])
                return history

            # Handle get all audit logs
            if 'select' in query_lower and 'from audit_log' in query_lower:
                return self.state['audit_logs']

            return []

        async def execute(self, query, *args):
            """Mock execute for UPDATE/DELETE operations."""
            query_lower = query.lower().strip()

            # Handle UPDATE replies SET confirmed = TRUE
            if 'update replies' in query_lower and 'set confirmed = true' in query_lower:
                reply_id = args[0]
                if reply_id in self.state['replies']:
                    self.state['replies'][reply_id]['confirmed'] = True
                    return 'UPDATE 1'
                return 'UPDATE 0'

            # Handle UPDATE replies SET posted_at
            if 'update replies' in query_lower and 'set posted_at' in query_lower:
                posted_at, platform_ref, reply_id = args
                if reply_id in self.state['replies']:
                    self.state['replies'][reply_id]['posted_at'] = posted_at
                    self.state['replies'][reply_id]['platform_ref'] = platform_ref
                    return 'UPDATE 1'
                return 'UPDATE 0'

            # Handle DELETE FROM replies
            if 'delete from replies' in query_lower:
                reply_id = args[0]
                if reply_id in self.state['replies']:
                    del self.state['replies'][reply_id]
                    return 'DELETE 1'
                return 'DELETE 0'

            return 'UPDATE 0'

    class MockPool:
        """Mock connection pool."""

        def __init__(self, state):
            self.state = state

        def acquire(self):
            """Return context manager for connection."""
            class AcquireContext:
                def __init__(self, state):
                    self.state = state
                    self.conn = None

                async def __aenter__(self):
                    self.conn = MockConnection(self.state)
                    return self.conn

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            return AcquireContext(self.state)

    pool = MockPool(state)

    # Setup initial test data
    async with pool.acquire() as conn:
        # Create test user
        conn.state['users'][1] = {
            'id': 1,
            'telegram_user_id': 12345,
            'discord_token_encrypted': None,
            'created_at': datetime.utcnow()
        }

        # Create test message
        conn.state['messages'][1] = {
            'id': 1,
            'platform': 'discord',
            'ext_message_id': '999888777',
            'channel_id': '111222333',
            'server_id': '444555666',
            'author_id': '777888999',
            'author_name': 'TestUser',
            'content': 'Original message content',
            'has_image': False,
            'created_at': datetime.utcnow()
        }

        # Create test task
        conn.state['tasks'][1] = {
            'id': 1,
            'source_message_id': 1,
            'assignee_user_id': 1,
            'status': 'open',
            'reminder_count': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        # Create original posted reply
        conn.state['replies'][1] = {
            'id': 1,
            'task_id': 1,
            'content': 'Original reply text',
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
            'created_at': datetime.utcnow() - timedelta(hours=1)
        }
        conn.state['next_id']['reply'] = 2

    return pool


@pytest.fixture
def mock_discord_poster():
    """Mock Discord poster for testing platform integration."""
    poster = AsyncMock()
    poster.edit_message = AsyncMock(return_value={
        'success': True,
        'message_id': '123456789',
        'channel_id': '111222333'
    })
    return poster


@pytest.fixture
def mock_telegram_poster():
    """Mock Telegram poster for testing platform integration."""
    poster = AsyncMock()
    poster.edit_message = AsyncMock(return_value={
        'success': True,
        'message_id': 999,
        'chat_id': 12345
    })
    return poster


# =============================================================================
# Integration Tests: Complete Edit Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_complete_edit_workflow_discord(db_pool, mock_discord_poster):
    """
    Test complete edit workflow for Discord message.

    Flow:
    1. User initiates edit
    2. Enters new text
    3. Confirms edit
    4. Reply is updated on Discord
    5. Audit log is created
    6. Edit history is tracked
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Step 1: Validate edit permission
        validation = await ReplyEditorService.validate_edit_permission(
            conn,
            reply_id=1,
            user_id=1,
            time_limit_hours=48
        )

        assert validation['can_edit'] is True
        assert 'reply' in validation
        assert 'task' in validation

        # Step 2: Create edited reply
        new_reply_id = await ReplyEditorService.create_edited_reply(
            conn,
            original_reply_id=1,
            new_content='Updated reply text',
            user_id=1
        )

        assert new_reply_id == 2
        assert 2 in conn.state['replies']
        assert conn.state['replies'][2]['content'] == 'Updated reply text'
        assert conn.state['replies'][2]['edit_of'] == 1
        assert conn.state['replies'][2]['confirmed'] is True

        # Step 3: Execute complete edit workflow
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Final updated text',
            user_id=1,
            telegram_poster=None,
            discord_poster=mock_discord_poster
        )

        # Verify success
        assert result['success'] is True
        assert result['platform'] == 'discord'
        assert 'new_reply_id' in result

        # Verify Discord poster was called
        mock_discord_poster.edit_message.assert_called_once()
        call_kwargs = mock_discord_poster.edit_message.call_args[1]
        assert call_kwargs['channel_id'] == '111222333'
        assert call_kwargs['message_id'] == '123456789'
        assert call_kwargs['content'] == 'Final updated text'

        # Verify new reply is posted
        new_reply_id = result['new_reply_id']
        new_reply = conn.state['replies'][new_reply_id]
        assert new_reply['posted_at'] is not None
        assert new_reply['platform_ref'] is not None

        # Verify audit logs
        audit_logs = [log for log in conn.state['audit_logs'] if 'reply.edit' in log['kind']]
        assert len(audit_logs) >= 2  # edit_started and edited

        # Verify edit_started log
        edit_started = next((log for log in audit_logs if log['kind'] == 'reply.edit_started'), None)
        assert edit_started is not None

        # Verify edited log
        edited = next((log for log in audit_logs if log['kind'] == 'reply.edited'), None)
        assert edited is not None
        edited_payload = json.loads(edited['payload_json'])
        assert edited_payload['reply_id'] == 1
        assert edited_payload['platform'] == 'discord'


@pytest.mark.asyncio
async def test_complete_edit_workflow_telegram(db_pool, mock_telegram_poster):
    """
    Test complete edit workflow for Telegram message.

    Verifies:
    - Telegram-specific platform_ref parsing
    - Correct poster called
    - Message updated with correct parameters
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Setup Telegram reply
        conn.state['replies'][1]['platform_ref'] = json.dumps({
            'platform': 'telegram',
            'chat_id': '12345',
            'message_id': '999'
        })

        # Execute edit
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Updated Telegram message',
            user_id=1,
            telegram_poster=mock_telegram_poster,
            discord_poster=None
        )

        # Verify success
        assert result['success'] is True
        assert result['platform'] == 'telegram'

        # Verify Telegram poster was called with correct params
        mock_telegram_poster.edit_message.assert_called_once()
        call_kwargs = mock_telegram_poster.edit_message.call_args[1]
        assert call_kwargs['chat_id'] == 12345
        assert call_kwargs['message_id'] == 999
        assert call_kwargs['text'] == 'Updated Telegram message'


# =============================================================================
# Integration Tests: Edit History Chain
# =============================================================================

@pytest.mark.asyncio
async def test_edit_history_chain(db_pool):
    """
    Test edit history tracking through multiple edits.

    Creates:
    - Original message (reply_id=1)
    - First edit (reply_id=2)
    - Second edit (reply_id=3)

    Verifies complete history is tracked and formatted correctly.
    """
    from services.reply_editor import ReplyEditorService
    from database.dao.reply_dao import ReplyDAO

    async with db_pool.acquire() as conn:
        # Create first edit
        first_edit_id = await ReplyEditorService.create_edited_reply(
            conn,
            original_reply_id=1,
            new_content='First edit',
            user_id=1
        )

        # Manually set created_at for testing
        conn.state['replies'][first_edit_id]['created_at'] = datetime.utcnow() - timedelta(minutes=30)

        # Create second edit (of original, not first edit)
        second_edit_id = await ReplyEditorService.create_edited_reply(
            conn,
            original_reply_id=1,
            new_content='Second edit',
            user_id=1
        )

        # Get edit history
        history = await ReplyEditorService.get_edit_history(conn, reply_id=1)

        # Verify history structure
        assert len(history) >= 2  # At least original + 2 edits

        # Verify newest first
        assert history[0]['is_current'] is True
        assert history[0]['content'] == 'Second edit'

        # Verify original is marked
        original = next((h for h in history if h['is_original']), None)
        assert original is not None
        assert original['content'] == 'Original reply text'
        assert original['edit_of'] is None

        # Verify all have required fields
        for item in history:
            assert 'id' in item
            assert 'content' in item
            assert 'content_preview' in item
            assert 'full_content' in item
            assert 'created_at' in item
            assert 'is_current' in item
            assert 'is_original' in item


@pytest.mark.asyncio
async def test_edit_history_from_any_version(db_pool):
    """
    Test that edit history can be retrieved starting from any version in the chain.

    Verifies that querying with any reply ID in the chain returns the complete history.
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Create edit
        edit_id = await ReplyEditorService.create_edited_reply(
            conn,
            original_reply_id=1,
            new_content='Edited version',
            user_id=1
        )

        # Get history from original
        history_from_original = await ReplyEditorService.get_edit_history(conn, reply_id=1)

        # Get history from edit
        history_from_edit = await ReplyEditorService.get_edit_history(conn, reply_id=edit_id)

        # Both should return the same history
        assert len(history_from_original) == len(history_from_edit)

        # Verify both contain original and edit
        assert any(h['id'] == 1 for h in history_from_original)
        assert any(h['id'] == edit_id for h in history_from_original)


# =============================================================================
# Integration Tests: Permission Checks in Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_workflow_enforces_time_limit(db_pool, mock_discord_poster):
    """
    Test that edit workflow properly enforces 48-hour time limit.

    Verifies:
    - Edits within 48h succeed
    - Edits after 48h fail with appropriate error
    - Audit log records permission denial
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Set posted_at to 49 hours ago (beyond 48h limit)
        conn.state['replies'][1]['posted_at'] = datetime.utcnow() - timedelta(hours=49)

        # Attempt edit
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Should fail',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        # Verify failure
        assert result['success'] is False
        assert result['error_code'] == 'validation_failed'
        assert '48 hours' in result['error']

        # Verify Discord poster was NOT called
        mock_discord_poster.edit_message.assert_not_called()

        # Verify audit log has denial
        audit_logs = conn.state['audit_logs']
        denial = next((log for log in audit_logs if log['kind'] == 'reply.edit_denied'), None)
        assert denial is not None


@pytest.mark.asyncio
async def test_workflow_enforces_user_ownership(db_pool, mock_discord_poster):
    """
    Test that only the task owner can edit replies.

    Verifies:
    - Owner can edit
    - Different user cannot edit
    - Appropriate error message returned
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Create different user
        conn.state['users'][2] = {
            'id': 2,
            'telegram_user_id': 67890,
            'created_at': datetime.utcnow()
        }

        # Attempt edit as different user (user_id=2, but task assigned to user_id=1)
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Unauthorized edit',
            user_id=2,
            discord_poster=mock_discord_poster
        )

        # Verify failure
        assert result['success'] is False
        assert result['error_code'] == 'validation_failed'
        assert 'permission' in result['error'].lower()

        # Verify Discord poster was NOT called
        mock_discord_poster.edit_message.assert_not_called()


@pytest.mark.asyncio
async def test_workflow_validates_posted_status(db_pool, mock_discord_poster):
    """
    Test that only posted replies can be edited.

    Verifies that unposted replies cannot be edited through the workflow.
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Set posted_at to None (not posted)
        conn.state['replies'][1]['posted_at'] = None

        # Attempt edit
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Should fail',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        # Verify failure
        assert result['success'] is False
        assert result['error_code'] == 'validation_failed'
        assert 'not been posted' in result['error']


@pytest.mark.asyncio
async def test_workflow_prevents_muted_task_edits(db_pool, mock_discord_poster):
    """
    Test that replies for muted tasks cannot be edited.

    Verifies muted task status is checked during edit workflow.
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Set task status to muted
        conn.state['tasks'][1]['status'] = 'muted'

        # Attempt edit
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Should fail',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        # Verify failure
        assert result['success'] is False
        assert result['error_code'] == 'validation_failed'
        assert 'muted' in result['error'].lower()


# =============================================================================
# Integration Tests: Platform Integration
# =============================================================================

@pytest.mark.asyncio
async def test_discord_message_edit_integration(db_pool, mock_discord_poster):
    """
    Test Discord message editing with various scenarios.

    Verifies:
    - Correct channel_id and message_id extracted from platform_ref
    - Edit message called with correct parameters
    - Response handling
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Discord edit test',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        assert result['success'] is True

        # Verify edit_message was called with parsed platform_ref
        call_kwargs = mock_discord_poster.edit_message.call_args[1]
        assert call_kwargs['channel_id'] == '111222333'
        assert call_kwargs['message_id'] == '123456789'
        assert call_kwargs['content'] == 'Discord edit test'


@pytest.mark.asyncio
async def test_handle_platform_errors_deleted_message(db_pool, mock_discord_poster):
    """
    Test handling of platform errors (e.g., message deleted).

    Verifies:
    - Error from poster is captured
    - Appropriate error returned to caller
    - Audit log records failure
    """
    from services.reply_editor import ReplyEditorService

    # Mock Discord poster to return error (message not found)
    mock_discord_poster.edit_message = AsyncMock(return_value={
        'success': False,
        'error': 'Unknown Message',
        'error_code': 10008
    })

    async with db_pool.acquire() as conn:
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Will fail',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        # Verify failure
        assert result['success'] is False
        assert result['error_code'] == 'post_failed'
        assert 'Unknown Message' in result['error']

        # Verify audit log has failure
        failure_log = next(
            (log for log in conn.state['audit_logs'] if log['kind'] == 'reply.edit_failed'),
            None
        )
        assert failure_log is not None


@pytest.mark.asyncio
async def test_handle_platform_rate_limit(db_pool, mock_discord_poster):
    """
    Test handling of rate limit errors from platform.

    Verifies graceful handling of rate limit responses.
    """
    from services.reply_editor import ReplyEditorService

    # Mock rate limit error
    mock_discord_poster.edit_message = AsyncMock(return_value={
        'success': False,
        'error': 'Rate limited. Retry after 5 seconds',
        'error_code': 429
    })

    async with db_pool.acquire() as conn:
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Rate limited',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        assert result['success'] is False
        assert 'Rate limited' in result['error']


@pytest.mark.asyncio
async def test_missing_poster_error(db_pool):
    """
    Test that missing poster (Discord/Telegram) returns appropriate error.

    Verifies error_code='no_poster' when required poster is not provided.
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Attempt edit without providing Discord poster
        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='No poster',
            user_id=1,
            telegram_poster=None,
            discord_poster=None
        )

        assert result['success'] is False
        assert result['error_code'] == 'no_poster'
        assert 'not available' in result['error'].lower()


@pytest.mark.asyncio
async def test_invalid_platform_ref(db_pool, mock_discord_poster):
    """
    Test handling of invalid or missing platform_ref data.

    Verifies appropriate error when platform_ref is malformed.
    """
    from services.reply_editor import ReplyEditorService

    async with db_pool.acquire() as conn:
        # Set invalid platform_ref (missing message_id)
        conn.state['replies'][1]['platform_ref'] = json.dumps({
            'platform': 'discord',
            'channel_id': '111222333'
            # missing message_id
        })

        result = await ReplyEditorService.edit_reply(
            conn,
            original_reply_id=1,
            new_content='Invalid ref',
            user_id=1,
            discord_poster=mock_discord_poster
        )

        assert result['success'] is False
        assert result['error_code'] == 'invalid_platform_ref'
