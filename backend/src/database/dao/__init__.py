"""
Data Access Object (DAO) Layer.

This module provides async database operations using asyncpg for all tables
in the moderator system. Each DAO class handles CRUD operations for a specific
table with proper error handling, type hints, and comprehensive documentation.

Available DAOs:
- MessageDAO: Message operations (messages table)
- TaskDAO: Task operations (tasks table)
- ReplyDAO: Reply operations (replies table)
- UserDAO: User and settings operations (users and settings tables)
- DiscordDAO: Discord connection operations (discord_connection table)
- AllowlistDAO: Channel allowlist operations (channels_allowlist table)
- AttachmentDAO: Attachment operations (attachments table)
- AuditDAO: Audit log operations (audit_log table)
- AIVariantDAO: AI response variant operations (ai_response_variants table)
- ChannelDAO: Discord channel caching operations (discord_channels table)

Usage:
    from database.dao import MessageDAO, TaskDAO, UserDAO
    import asyncpg

    # Establish connection
    conn = await asyncpg.connect(DATABASE_URL)

    # Use DAOs
    message_id = await MessageDAO.create_message(
        conn=conn,
        platform='discord',
        ext_message_id='123',
        channel_id='456',
        author_id='789',
        content='Hello, world!'
    )

    message = await MessageDAO.get_message_by_id(conn, message_id)

    # Close connection
    await conn.close()

All DAO methods:
- Are async and use asyncpg connections
- Accept 'conn' as the first parameter (database connection)
- Return dictionaries for single records, lists for multiple records
- Include proper error handling and type hints
- Have comprehensive docstrings with examples
- Handle NULL values gracefully
"""

from .message_dao import MessageDAO
from .task_dao import TaskDAO
from .reply_dao import ReplyDAO
from .user_dao import UserDAO
from .discord_dao import DiscordDAO
from .allowlist_dao import AllowlistDAO
from .attachment_dao import AttachmentDAO
from .audit_dao import AuditDAO
from .ai_variant_dao import AIVariantDAO
from .channel_dao import ChannelDAO

__all__ = [
    'MessageDAO',
    'TaskDAO',
    'ReplyDAO',
    'UserDAO',
    'DiscordDAO',
    'AllowlistDAO',
    'AttachmentDAO',
    'AuditDAO',
    'AIVariantDAO',
    'ChannelDAO',
]

# DAO method summary
DAO_SUMMARY = {
    'MessageDAO': [
        'create_message',
        'get_message_by_id',
        'get_message_by_external_id',
        'get_messages_by_channel',
        'get_context_messages',
        'get_messages_by_author',
        'count_messages_in_channel',
    ],
    'TaskDAO': [
        'create_task',
        'get_task_by_id',
        'get_task_by_message_id',
        'get_open_tasks',
        'get_tasks_by_status',
        'update_task_status',
        'update_task_card_id',
        'mark_task_answered',
        'increment_reminder_count',
        'delete_task',
        'count_tasks_by_status',
    ],
    'ReplyDAO': [
        'create_reply',
        'get_reply_by_id',
        'get_replies_for_task',
        'get_latest_reply_for_task',
        'mark_reply_confirmed',
        'mark_reply_posted',
        'update_reply_content',
        'get_confirmed_replies',
        'get_posted_replies',
        'delete_reply',
        'get_reply_history',
    ],
    'UserDAO': [
        'create_user',
        'get_user_by_id',
        'get_user_by_tg_id',
        'get_or_create_user',
        'update_username',
        'get_all_users',
        'delete_user',
        'get_user_settings',
        'create_default_settings',
        'get_or_create_settings',
        'update_dnd_settings',
        'update_reminders_enabled',
        'get_users_with_dnd_enabled',
    ],
    'DiscordDAO': [
        'save_discord_connection',
        'get_discord_connection',
        'get_discord_token',
        'update_connection_status',
        'delete_discord_connection',
        'get_all_connected',
        'get_all_connections',
        'update_super_properties',
        'clear_session',
    ],
    'AllowlistDAO': [
        'add_channel',
        'remove_channel',
        'is_channel_allowed',
        'get_all_channels',
        'get_channel_by_id',
        'update_channel_enabled',
        'update_thread_filter',
        'count_channels',
    ],
    'AttachmentDAO': [
        'create_attachment',
        'get_attachment_by_id',
        'get_attachments_for_message',
        'delete_attachment',
        'delete_attachments_for_message',
        'count_attachments_by_type',
        'get_images_for_message',
        'has_attachments',
        'bulk_create_attachments',
        'update_attachment_ref',
    ],
    'AuditDAO': [
        'log_event',
        'get_log_by_id',
        'get_recent_logs',
        'get_logs_by_kind',
        'get_logs_by_user',
        'get_logs_in_timerange',
        'count_logs_by_kind',
        'delete_old_logs',
        'get_event_statistics',
        'search_logs',
    ],
    'AIVariantDAO': [
        'create_variant',
        'get_variants_for_task',
        'get_variant_by_id',
        'mark_variant_selected',
        'unmark_all_selected_for_task',
        'get_selected_variant_for_task',
        'delete_variants_for_task',
        'delete_variant',
        'count_variants_for_task',
    ],
    'ChannelDAO': [
        'cache_channel',
        'get_channels_by_server',
        'get_channel_by_id',
        'bulk_update_channels',
    ],
}


def get_dao_summary() -> dict:
    """
    Get summary of all available DAO methods.

    Returns:
        Dictionary mapping DAO names to their method lists

    Example:
        >>> from database.dao import get_dao_summary
        >>> summary = get_dao_summary()
        >>> print(f"MessageDAO has {len(summary['MessageDAO'])} methods")
    """
    return DAO_SUMMARY


def print_dao_summary():
    """
    Print a formatted summary of all DAOs and their methods.

    Example:
        >>> from database.dao import print_dao_summary
        >>> print_dao_summary()
    """
    total_methods = 0
    print("=" * 70)
    print("DAO LAYER SUMMARY")
    print("=" * 70)

    for dao_name, methods in DAO_SUMMARY.items():
        print(f"\n{dao_name} ({len(methods)} methods):")
        for i, method in enumerate(methods, 1):
            print(f"  {i:2d}. {method}")
        total_methods += len(methods)

    print("\n" + "=" * 70)
    print(f"TOTAL: {len(DAO_SUMMARY)} DAOs, {total_methods} methods")
    print("=" * 70)
