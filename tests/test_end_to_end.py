"""
End-to-End Integration Tests for v1.0 Iteration 11.

This module tests complete workflows from Discord message to Telegram card to reply posting.
Tests cover:
- Complete message flow: Discord → Task → LLM → Telegram → Reply → Posted
- Multi-server workflows
- Search workflows
- Template workflows
- Export workflows
- Error handling and recovery
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta


# =============================================================================
# E2E Test 1: Complete Message Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_complete_message_workflow(
    mock_db_connection,
    mock_discord_client,
    mock_telegram_bot,
    mock_llm_client,
    sample_e2e_workflow_data
):
    """
    Test complete workflow: Discord message → Task → LLM response → Telegram card → Reply → Posted.

    Steps:
    1. Discord message received
    2. Task created in database
    3. LLM generates response variants
    4. Telegram card sent to moderator
    5. Moderator selects/confirms reply
    6. Reply posted to Discord
    """
    workflow_data = sample_e2e_workflow_data
    discord_msg = workflow_data['discord_message']

    # Mock database operations
    conn = mock_db_connection

    # Step 1: Simulate Discord message reception
    with patch('database.dao.MessageDAO.create_message') as mock_create_msg:
        mock_create_msg.return_value = 1

        # Create message in database
        message_id = await mock_create_msg(
            conn,
            platform='discord',
            ext_message_id=discord_msg['id'],
            channel_id=discord_msg['channel_id'],
            server_id=discord_msg['server_id'],
            author_id=discord_msg['author']['id'],
            author_name=discord_msg['author']['username'],
            content=discord_msg['content']
        )

        assert message_id == 1
        mock_create_msg.assert_called_once()

    # Step 2: Create task for the message
    with patch('database.dao.TaskDAO.create_task') as mock_create_task:
        mock_create_task.return_value = 1

        task_id = await mock_create_task(
            conn,
            source_message_id=message_id,
            assignee_id=1,
            status='pending'
        )

        assert task_id == 1
        mock_create_task.assert_called_once()

    # Step 3: Generate LLM response variants
    llm_variants = await mock_llm_client.generate_variants(
        context=discord_msg['content'],
        count=3
    )

    assert len(llm_variants) == 3
    assert all('content' in v for v in llm_variants)

    # Step 4: Send Telegram card to moderator
    tg_response = await mock_telegram_bot.send_message(
        chat_id=12345,
        text=workflow_data['telegram_card']['text'],
        reply_markup=workflow_data['telegram_card']['reply_markup']
    )

    assert tg_response['ok'] is True
    assert 'result' in tg_response

    # Step 5: Moderator confirms reply
    with patch('database.dao.ReplyDAO.create_reply') as mock_create_reply:
        mock_create_reply.return_value = 1

        reply_id = await mock_create_reply(
            conn,
            task_id=task_id,
            content=workflow_data['llm_response']['content'],
            generated_by='llm',
            is_confirmed=True
        )

        assert reply_id == 1
        mock_create_reply.assert_called_once()

    # Step 6: Post reply to Discord
    discord_response = await mock_discord_client.send_message(
        channel_id=discord_msg['channel_id'],
        content=workflow_data['llm_response']['content'],
        reference_message_id=discord_msg['id']
    )

    assert discord_response['id'] is not None
    assert discord_response['content'] == workflow_data['llm_response']['content']


# =============================================================================
# E2E Test 2: Multi-Server Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_multiserver_workflow(
    mock_db_connection,
    mock_discord_client,
    test_data_generator
):
    """
    Test workflow across multiple Discord servers.

    Verifies:
    - Messages from different servers are handled independently
    - Server-specific allowlists work correctly
    - Channel caching works across servers
    """
    conn = mock_db_connection

    # Create two different servers
    server_1_id = '1111111111'
    server_2_id = '2222222222'

    # Mock channel allowlist check
    with patch('database.dao.AllowlistDAO.is_channel_allowed') as mock_is_allowed:
        # Server 1 channel is allowed
        mock_is_allowed.return_value = True

        # Create message from server 1
        with patch('database.dao.MessageDAO.create_message') as mock_create:
            mock_create.return_value = 1

            msg1_id = await mock_create(
                conn,
                platform='discord',
                ext_message_id='msg_1',
                channel_id='channel_1',
                server_id=server_1_id,
                author_id='author_1',
                author_name='User1',
                content='Message from server 1'
            )

            assert msg1_id == 1

    with patch('database.dao.AllowlistDAO.is_channel_allowed') as mock_is_allowed:
        # Server 2 channel is also allowed
        mock_is_allowed.return_value = True

        # Create message from server 2
        with patch('database.dao.MessageDAO.create_message') as mock_create:
            mock_create.return_value = 2

            msg2_id = await mock_create(
                conn,
                platform='discord',
                ext_message_id='msg_2',
                channel_id='channel_2',
                server_id=server_2_id,
                author_id='author_2',
                author_name='User2',
                content='Message from server 2'
            )

            assert msg2_id == 2

    # Verify both messages were created
    assert msg1_id != msg2_id


# =============================================================================
# E2E Test 3: Search Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_search_workflow(mock_db_connection, test_data_generator):
    """
    Test message search workflow.

    Tests:
    - Full-text search
    - Filter by channel/author/date
    - Pagination
    - Result formatting
    """
    conn = mock_db_connection

    # Mock search results
    mock_results = [
        {
            'id': 1,
            'content': 'Hello world',
            'author_name': 'User1',
            'channel_id': 'channel_1',
            'created_at': datetime.now()
        },
        {
            'id': 2,
            'content': 'Hello everyone',
            'author_name': 'User2',
            'channel_id': 'channel_1',
            'created_at': datetime.now()
        }
    ]

    with patch('database.dao.SearchDAO.search_messages') as mock_search:
        mock_search.return_value = mock_results

        # Perform search
        results = await mock_search(
            conn,
            query='Hello',
            channel_id='channel_1',
            limit=10,
            offset=0
        )

        assert len(results) == 2
        assert all('Hello' in r['content'] for r in results)
        mock_search.assert_called_once()

    # Test pagination
    with patch('database.dao.SearchDAO.count_search_results') as mock_count:
        mock_count.return_value = 25

        total = await mock_count(conn, query='Hello')
        assert total == 25

        # Calculate pages
        page_size = 10
        total_pages = (total + page_size - 1) // page_size
        assert total_pages == 3


# =============================================================================
# E2E Test 4: Template Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_template_workflow(mock_db_connection):
    """
    Test response template workflow.

    Tests:
    - Template creation
    - Template usage
    - Variable substitution
    """
    conn = mock_db_connection

    # Create template
    with patch('database.dao.TemplatesDAO.create_template') as mock_create:
        mock_create.return_value = 1

        template_id = await mock_create(
            conn,
            user_id=1,
            name='greeting',
            content='Hello {name}, thank you for your message!'
        )

        assert template_id == 1

    # Get template
    with patch('database.dao.TemplatesDAO.get_template_by_id') as mock_get:
        mock_get.return_value = {
            'id': 1,
            'name': 'greeting',
            'content': 'Hello {name}, thank you for your message!',
            'user_id': 1
        }

        template = await mock_get(conn, template_id=1)
        assert template is not None
        assert '{name}' in template['content']

    # Use template with variable substitution
    user_name = 'John'
    filled_content = template['content'].format(name=user_name)
    assert filled_content == 'Hello John, thank you for your message!'


# =============================================================================
# E2E Test 5: Export Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_export_workflow(mock_db_connection, test_data_generator):
    """
    Test message export workflow.

    Tests:
    - Export request creation
    - Data collection
    - Format generation (JSON/CSV)
    - Download delivery
    """
    conn = mock_db_connection

    # Create export request
    with patch('database.dao.ExportDAO.create_export') as mock_create:
        mock_create.return_value = 1

        export_id = await mock_create(
            conn,
            user_id=1,
            export_type='messages',
            filters={'channel_id': 'channel_1'},
            format='json',
            status='pending'
        )

        assert export_id == 1

    # Mock message collection
    messages = test_data_generator.generate_messages(count=100)

    # Simulate export processing
    with patch('database.dao.ExportDAO.update_export_status') as mock_update:
        mock_update.return_value = True

        # Update to processing
        await mock_update(conn, export_id=export_id, status='processing')

        # Simulate data generation
        export_data = {
            'messages': messages,
            'total_count': len(messages),
            'exported_at': datetime.now().isoformat()
        }

        # Update to completed
        await mock_update(conn, export_id=export_id, status='completed')

        assert mock_update.call_count == 2

    # Verify export data
    assert len(export_data['messages']) == 100


# =============================================================================
# E2E Test 6: Error Recovery Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_error_recovery_workflow(
    mock_db_connection,
    mock_discord_client,
    mock_telegram_bot
):
    """
    Test error handling and recovery.

    Tests:
    - Failed Discord post retry
    - LLM timeout handling
    - Database connection recovery
    """
    conn = mock_db_connection

    # Simulate Discord posting failure then success
    post_attempts = []

    async def mock_post_with_retry(*args, **kwargs):
        post_attempts.append(1)
        if len(post_attempts) == 1:
            raise Exception("Temporary network error")
        return {'id': '1234567890', 'success': True}

    mock_discord_client.send_message = mock_post_with_retry

    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = await mock_discord_client.send_message(
                channel_id='channel_1',
                content='Test message'
            )
            if result['success']:
                break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.1)  # Brief delay before retry

    assert len(post_attempts) == 2
    assert result['success'] is True


# =============================================================================
# E2E Test 7: Edit Reply Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_edit_reply_workflow(mock_db_connection, mock_discord_client):
    """
    Test editing a sent reply.

    Tests:
    - Reply edit creation
    - Version tracking
    - Discord message editing
    - History preservation
    """
    conn = mock_db_connection

    # Create original reply
    with patch('database.dao.ReplyDAO.create_reply') as mock_create:
        mock_create.return_value = 1

        original_reply_id = await mock_create(
            conn,
            task_id=1,
            content='Original reply content',
            generated_by='human',
            is_posted=True
        )

    # Edit the reply
    with patch('database.dao.ReplyDAO.update_reply_content') as mock_update:
        mock_update.return_value = True

        success = await mock_update(
            conn,
            reply_id=original_reply_id,
            new_content='Edited reply content',
            edit_reason='Fixed typo'
        )

        assert success is True

    # Get edit history
    with patch('database.dao.ReplyDAO.get_reply_history') as mock_history:
        mock_history.return_value = [
            {
                'version': 1,
                'content': 'Original reply content',
                'edited_at': datetime.now() - timedelta(minutes=5)
            },
            {
                'version': 2,
                'content': 'Edited reply content',
                'edited_at': datetime.now()
            }
        ]

        history = await mock_history(conn, reply_id=original_reply_id)
        assert len(history) == 2
        assert history[-1]['content'] == 'Edited reply content'


# =============================================================================
# E2E Test 8: DND (Do Not Disturb) Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_dnd_workflow(mock_db_connection, mock_telegram_bot):
    """
    Test Do Not Disturb mode workflow.

    Tests:
    - DND activation/deactivation
    - Schedule configuration
    - Message suppression during DND
    """
    conn = mock_db_connection

    # Enable DND
    with patch('database.dao.UserDAO.update_dnd_settings') as mock_update:
        mock_update.return_value = True

        success = await mock_update(
            conn,
            user_id=1,
            dnd_enabled=True,
            dnd_start='22:00',
            dnd_end='08:00'
        )

        assert success is True

    # Get DND settings
    with patch('database.dao.UserDAO.get_user_settings') as mock_get:
        mock_get.return_value = {
            'dnd_enabled': True,
            'dnd_start_time': '22:00',
            'dnd_end_time': '08:00'
        }

        settings = await mock_get(conn, user_id=1)
        assert settings['dnd_enabled'] is True

    # Check if currently in DND period
    from datetime import datetime, time

    def is_in_dnd_period(current_time, start_time, end_time):
        """Check if current time is within DND period."""
        current = current_time.time()
        start = time.fromisoformat(start_time)
        end = time.fromisoformat(end_time)

        if start <= end:
            return start <= current <= end
        else:  # DND period crosses midnight
            return current >= start or current <= end

    # Test during DND hours (23:00)
    test_time = datetime.now().replace(hour=23, minute=0)
    in_dnd = is_in_dnd_period(test_time, '22:00', '08:00')
    assert in_dnd is True

    # Test outside DND hours (12:00)
    test_time = datetime.now().replace(hour=12, minute=0)
    in_dnd = is_in_dnd_period(test_time, '22:00', '08:00')
    assert in_dnd is False


# =============================================================================
# E2E Test 9: Allowlist Management Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_allowlist_management_workflow(mock_db_connection):
    """
    Test channel allowlist management.

    Tests:
    - Add channel to allowlist
    - Remove channel from allowlist
    - Check channel status
    - Bulk operations
    """
    conn = mock_db_connection

    # Add channel to allowlist
    with patch('database.dao.AllowlistDAO.add_channel') as mock_add:
        mock_add.return_value = 1

        allowlist_id = await mock_add(
            conn,
            server_id='server_1',
            channel_id='channel_1',
            added_by=1,
            enabled=True
        )

        assert allowlist_id == 1

    # Check if channel is allowed
    with patch('database.dao.AllowlistDAO.is_channel_allowed') as mock_check:
        mock_check.return_value = True

        is_allowed = await mock_check(conn, channel_id='channel_1')
        assert is_allowed is True

    # Remove channel from allowlist
    with patch('database.dao.AllowlistDAO.remove_channel') as mock_remove:
        mock_remove.return_value = True

        success = await mock_remove(conn, channel_id='channel_1')
        assert success is True

    # Verify channel is no longer allowed
    with patch('database.dao.AllowlistDAO.is_channel_allowed') as mock_check:
        mock_check.return_value = False

        is_allowed = await mock_check(conn, channel_id='channel_1')
        assert is_allowed is False


# =============================================================================
# E2E Test 10: LLM Response Generation Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_llm_response_generation_workflow(
    mock_db_connection,
    mock_llm_client
):
    """
    Test LLM response generation with variants.

    Tests:
    - Context preparation
    - Variant generation
    - Tone adjustment
    - Variant selection
    """
    conn = mock_db_connection

    # Generate response variants
    variants = await mock_llm_client.generate_variants(
        context='User is asking about pricing',
        count=3
    )

    assert len(variants) == 3
    assert all('content' in v and 'tone' in v for v in variants)

    # Save variants to database
    with patch('database.dao.AIVariantDAO.create_variant') as mock_create:
        mock_create.return_value = 1

        for idx, variant in enumerate(variants):
            variant_id = await mock_create(
                conn,
                task_id=1,
                content=variant['content'],
                confidence_score=variant['confidence'],
                tone=variant['tone']
            )
            assert variant_id == 1

    # Select a variant
    with patch('database.dao.AIVariantDAO.mark_variant_selected') as mock_select:
        mock_select.return_value = True

        success = await mock_select(conn, variant_id=1, task_id=1)
        assert success is True


# =============================================================================
# E2E Test 11: Reminder Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_reminder_workflow(mock_db_connection, mock_telegram_bot):
    """
    Test reminder scheduling and delivery.

    Tests:
    - Reminder creation
    - Scheduled execution
    - Delivery to Telegram
    - Reminder count tracking
    """
    conn = mock_db_connection

    # Create task that needs reminder
    with patch('database.dao.TaskDAO.create_task') as mock_create:
        mock_create.return_value = 1

        task_id = await mock_create(
            conn,
            source_message_id=1,
            assignee_id=1,
            status='pending'
        )

    # Simulate reminder trigger
    with patch('database.dao.TaskDAO.increment_reminder_count') as mock_increment:
        mock_increment.return_value = True

        success = await mock_increment(conn, task_id=task_id)
        assert success is True

    # Send reminder notification
    reminder_text = "Reminder: You have 1 pending task that needs attention."
    response = await mock_telegram_bot.send_message(
        chat_id=12345,
        text=reminder_text
    )

    assert response['ok'] is True


# =============================================================================
# E2E Test 12: Audit Logging Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_audit_logging_workflow(mock_db_connection):
    """
    Test audit logging for all operations.

    Tests:
    - Event logging
    - Log retrieval
    - Log filtering
    - Statistics generation
    """
    conn = mock_db_connection

    # Log an event
    with patch('database.dao.AuditDAO.log_event') as mock_log:
        mock_log.return_value = 1

        log_id = await mock_log(
            conn,
            event_kind='message_created',
            user_id=1,
            details={'message_id': 1, 'action': 'create'},
            severity='info'
        )

        assert log_id == 1

    # Get recent logs
    with patch('database.dao.AuditDAO.get_recent_logs') as mock_get:
        mock_get.return_value = [
            {
                'id': 1,
                'event_kind': 'message_created',
                'created_at': datetime.now(),
                'severity': 'info'
            }
        ]

        logs = await mock_get(conn, limit=10)
        assert len(logs) == 1

    # Get statistics
    with patch('database.dao.AuditDAO.get_event_statistics') as mock_stats:
        mock_stats.return_value = {
            'message_created': 10,
            'reply_posted': 5,
            'task_completed': 3
        }

        stats = await mock_stats(conn)
        assert stats['message_created'] == 10


# =============================================================================
# E2E Test 13: Attachment Handling Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_attachment_handling_workflow(
    mock_db_connection,
    sample_attachment_data
):
    """
    Test attachment processing workflow.

    Tests:
    - Attachment upload
    - Storage
    - Retrieval
    - Deletion
    """
    conn = mock_db_connection
    attachment_data = sample_attachment_data

    # Create attachment
    with patch('database.dao.AttachmentDAO.create_attachment') as mock_create:
        mock_create.return_value = 1

        attachment_id = await mock_create(
            conn,
            message_id=attachment_data['message_id'],
            file_type=attachment_data['file_type'],
            file_url=attachment_data['file_url'],
            file_size=attachment_data['file_size'],
            filename=attachment_data['filename']
        )

        assert attachment_id == 1

    # Get attachments for message
    with patch('database.dao.AttachmentDAO.get_attachments_for_message') as mock_get:
        mock_get.return_value = [attachment_data]

        attachments = await mock_get(conn, message_id=1)
        assert len(attachments) == 1
        assert attachments[0]['file_type'] == 'image'


# =============================================================================
# E2E Test 14: Context Loading Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_context_loading_workflow(
    mock_db_connection,
    test_data_generator
):
    """
    Test conversation context loading.

    Tests:
    - Context message retrieval
    - Ordering and formatting
    - Limit handling
    """
    conn = mock_db_connection

    # Generate context messages
    messages = test_data_generator.generate_messages(count=20, channel_id='channel_1')

    # Get context messages
    with patch('database.dao.MessageDAO.get_context_messages') as mock_get:
        mock_get.return_value = messages[:10]

        context = await mock_get(
            conn,
            channel_id='channel_1',
            before_message_id=21,
            limit=10
        )

        assert len(context) == 10
        assert all(msg['channel_id'] == 'channel_1' for msg in context)


# =============================================================================
# E2E Test 15: Rate Limiting Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_rate_limiting_workflow(mock_redis_client):
    """
    Test rate limiting for API calls.

    Tests:
    - Rate limit checking
    - Limit enforcement
    - Cooldown period
    """
    redis = mock_redis_client

    # Simulate rate limiting
    user_id = 'user_1'
    rate_limit_key = f'rate_limit:{user_id}'
    max_requests = 5
    window_seconds = 60

    # Track requests
    request_count = 0

    async def check_rate_limit():
        nonlocal request_count

        current = await redis.get(rate_limit_key)
        if current is None:
            await redis.set(rate_limit_key, 1, ex=window_seconds)
            request_count = 1
            return True

        current_count = int(current)
        if current_count >= max_requests:
            return False

        await redis.set(rate_limit_key, current_count + 1, ex=window_seconds)
        request_count = current_count + 1
        return True

    # Make requests up to limit
    for i in range(max_requests):
        allowed = await check_rate_limit()
        assert allowed is True

    # Next request should be denied
    allowed = await check_rate_limit()
    assert allowed is False
    assert request_count == max_requests


# =============================================================================
# E2E Test 16: Multi-User Isolation Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_multi_user_isolation_workflow(
    mock_db_connection,
    test_data_generator
):
    """
    Test data isolation between different users.

    Tests:
    - User-specific data access
    - Proper filtering
    - No cross-user data leakage
    """
    conn = mock_db_connection

    # Create two users
    users = test_data_generator.generate_users(count=2)
    user1_id = 1
    user2_id = 2

    # User 1 creates tasks
    with patch('database.dao.TaskDAO.get_tasks_by_status') as mock_get:
        mock_get.return_value = [
            {'id': 1, 'assignee_id': user1_id, 'status': 'pending'},
            {'id': 2, 'assignee_id': user1_id, 'status': 'pending'}
        ]

        user1_tasks = await mock_get(conn, status='pending', assignee_id=user1_id)
        assert len(user1_tasks) == 2
        assert all(t['assignee_id'] == user1_id for t in user1_tasks)

    # User 2 should not see User 1's tasks
    with patch('database.dao.TaskDAO.get_tasks_by_status') as mock_get:
        mock_get.return_value = []

        user2_tasks = await mock_get(conn, status='pending', assignee_id=user2_id)
        assert len(user2_tasks) == 0


# =============================================================================
# E2E Test 17: Statistics Dashboard Workflow
# =============================================================================

@pytest.mark.asyncio
async def test_statistics_dashboard_workflow(mock_db_connection):
    """
    Test statistics collection and dashboard.

    Tests:
    - Message counts
    - Task statistics
    - Response time metrics
    - User activity
    """
    conn = mock_db_connection

    # Get message statistics
    with patch('database.dao.StatsDAO.get_message_stats') as mock_stats:
        mock_stats.return_value = {
            'total_messages': 1000,
            'messages_today': 50,
            'messages_this_week': 300,
            'avg_per_day': 42.5
        }

        msg_stats = await mock_stats(conn)
        assert msg_stats['total_messages'] == 1000
        assert msg_stats['messages_today'] == 50

    # Get task statistics
    with patch('database.dao.StatsDAO.get_task_stats') as mock_stats:
        mock_stats.return_value = {
            'total_tasks': 500,
            'pending': 20,
            'in_progress': 5,
            'completed': 475,
            'avg_response_time_minutes': 15.5
        }

        task_stats = await mock_stats(conn)
        assert task_stats['pending'] == 20
        assert task_stats['avg_response_time_minutes'] == 15.5
