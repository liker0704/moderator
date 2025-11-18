"""
Test DAO modules for basic functionality.
These are unit tests that don't require a database connection.
"""
import sys
import os
import pytest

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


def test_message_dao_methods_exist():
    """Test that MessageDAO has expected methods"""
    from database.dao.message_dao import MessageDAO

    # Check that main methods exist
    assert hasattr(MessageDAO, 'create_message')
    assert hasattr(MessageDAO, 'get_message_by_id')
    assert hasattr(MessageDAO, 'get_messages_by_channel')
    assert callable(MessageDAO.create_message)
    assert callable(MessageDAO.get_message_by_id)


def test_task_dao_methods_exist():
    """Test that TaskDAO has expected methods"""
    from database.dao.task_dao import TaskDAO

    assert hasattr(TaskDAO, 'create_task')
    assert hasattr(TaskDAO, 'get_task_by_id')
    assert hasattr(TaskDAO, 'update_task_status')
    assert hasattr(TaskDAO, 'get_open_tasks')
    assert callable(TaskDAO.create_task)
    assert callable(TaskDAO.get_task_by_id)


def test_reply_dao_methods_exist():
    """Test that ReplyDAO has expected methods"""
    from database.dao.reply_dao import ReplyDAO

    assert hasattr(ReplyDAO, 'create_reply')
    assert hasattr(ReplyDAO, 'get_reply_by_id')
    assert hasattr(ReplyDAO, 'mark_reply_confirmed')
    assert hasattr(ReplyDAO, 'mark_reply_posted')
    assert hasattr(ReplyDAO, 'delete_reply')
    assert hasattr(ReplyDAO, 'can_edit_reply')
    assert hasattr(ReplyDAO, 'create_edited_reply')
    assert callable(ReplyDAO.create_reply)
    assert callable(ReplyDAO.get_reply_by_id)
    assert callable(ReplyDAO.can_edit_reply)
    assert callable(ReplyDAO.create_edited_reply)


def test_user_dao_methods_exist():
    """Test that UserDAO has expected methods"""
    from database.dao.user_dao import UserDAO

    assert hasattr(UserDAO, 'create_user')
    assert hasattr(UserDAO, 'get_user_by_tg_id')
    assert hasattr(UserDAO, 'update_dnd_settings')
    assert callable(UserDAO.create_user)
    assert callable(UserDAO.get_user_by_tg_id)


def test_discord_dao_methods_exist():
    """Test that DiscordDAO has expected methods"""
    from database.dao.discord_dao import DiscordDAO

    assert hasattr(DiscordDAO, 'save_discord_connection')
    assert hasattr(DiscordDAO, 'get_discord_connection')
    assert hasattr(DiscordDAO, 'update_connection_status')
    assert callable(DiscordDAO.save_discord_connection)
    assert callable(DiscordDAO.get_discord_connection)


def test_allowlist_dao_methods_exist():
    """Test that AllowlistDAO has expected methods"""
    from database.dao.allowlist_dao import AllowlistDAO

    assert hasattr(AllowlistDAO, 'add_channel')
    assert hasattr(AllowlistDAO, 'remove_channel')
    assert hasattr(AllowlistDAO, 'is_channel_allowed')
    assert callable(AllowlistDAO.add_channel)
    assert callable(AllowlistDAO.is_channel_allowed)


def test_attachment_dao_methods_exist():
    """Test that AttachmentDAO has expected methods"""
    from database.dao.attachment_dao import AttachmentDAO

    assert hasattr(AttachmentDAO, 'create_attachment')
    assert hasattr(AttachmentDAO, 'get_attachments_for_message')
    assert callable(AttachmentDAO.create_attachment)
    assert callable(AttachmentDAO.get_attachments_for_message)


def test_audit_dao_methods_exist():
    """Test that AuditDAO has expected methods"""
    from database.dao.audit_dao import AuditDAO

    assert hasattr(AuditDAO, 'log_event')
    assert hasattr(AuditDAO, 'get_recent_logs')
    assert callable(AuditDAO.log_event)
    assert callable(AuditDAO.get_recent_logs)
