"""
Export Data Access Object.

Provides async database operations for exporting user data using asyncpg.
Handles retrieval of all user data for export and anonymization purposes.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class ExportDAO:
    """
    Data Access Object for data export operations.

    Provides methods to retrieve all user data for export functionality.
    """

    @staticmethod
    async def get_all_messages(
        conn: asyncpg.Connection,
        user_id: int,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all messages for a user's monitored channels.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            limit: Optional limit on number of messages (None for all)

        Returns:
            List of message dictionaries ordered by created_at DESC

        Example:
            >>> messages = await ExportDAO.get_all_messages(conn, user_id=1)
            >>> print(f"Exported {len(messages)} messages")
        """
        # Get all messages from channels the user is monitoring
        query = """
            SELECT DISTINCT
                m.id, m.platform, m.ext_message_id, m.server_id,
                m.channel_id, m.thread_id, m.author_id, m.author_name,
                m.content, m.has_image, m.context_ref,
                m.created_at, m.platform_created_at
            FROM messages m
            INNER JOIN channels_allowlist ca
                ON m.platform = ca.platform
                AND m.channel_id = ca.channel_id
            WHERE ca.user_id = $1
            ORDER BY m.created_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_all_tasks(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all tasks for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            List of task dictionaries ordered by created_at DESC

        Example:
            >>> tasks = await ExportDAO.get_all_tasks(conn, user_id=1)
        """
        query = """
            SELECT
                t.id, t.source_message_id, t.status, t.assignee_user_id,
                t.tg_card_message_id, t.error_message, t.reminder_count,
                t.created_at, t.updated_at, t.answered_at,
                m.platform, m.channel_id, m.author_id, m.author_name,
                m.content as message_content
            FROM tasks t
            INNER JOIN messages m ON t.source_message_id = m.id
            WHERE t.assignee_user_id = $1
            ORDER BY t.created_at DESC
        """

        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_all_replies(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all replies for a user's tasks.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            List of reply dictionaries ordered by created_at DESC

        Example:
            >>> replies = await ExportDAO.get_all_replies(conn, user_id=1)
        """
        query = """
            SELECT
                r.id, r.task_id, r.content, r.generated_by,
                r.llm_confidence, r.confirmed, r.posted_at,
                r.platform_ref, r.edit_of, r.created_at,
                t.source_message_id, t.status as task_status,
                m.platform, m.channel_id, m.author_id
            FROM replies r
            INNER JOIN tasks t ON r.task_id = t.id
            INNER JOIN messages m ON t.source_message_id = m.id
            WHERE t.assignee_user_id = $1
            ORDER BY r.created_at DESC
        """

        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_all_settings(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve user settings.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            Dictionary with settings data or None if not found

        Example:
            >>> settings = await ExportDAO.get_all_settings(conn, user_id=1)
        """
        query = """
            SELECT
                id, user_id, dnd_enabled, dnd_schedule_json,
                reminders_enabled, created_at, updated_at
            FROM settings
            WHERE user_id = $1
        """

        row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None

    @staticmethod
    async def get_all_allowlist(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all allowlist entries for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            List of allowlist dictionaries ordered by created_at DESC

        Example:
            >>> allowlist = await ExportDAO.get_all_allowlist(conn, user_id=1)
        """
        # Check if user_id column exists in channels_allowlist
        # If it does, filter by user_id; otherwise, return all entries
        check_column_query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'channels_allowlist'
            AND column_name = 'user_id'
        """

        has_user_id = await conn.fetchrow(check_column_query)

        if has_user_id:
            query = """
                SELECT
                    id, user_id, platform, server_id, channel_id,
                    thread_filter_json, enabled, created_at, updated_at
                FROM channels_allowlist
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            rows = await conn.fetch(query, user_id)
        else:
            # Fallback: return all allowlist entries if user_id column doesn't exist
            query = """
                SELECT
                    id, platform, server_id, channel_id,
                    thread_filter_json, enabled, created_at, updated_at
                FROM channels_allowlist
                ORDER BY created_at DESC
            """
            rows = await conn.fetch(query)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_all_templates(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all templates for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            List of template dictionaries ordered by created_at DESC

        Example:
            >>> templates = await ExportDAO.get_all_templates(conn, user_id=1)
        """
        query = """
            SELECT
                id, user_id, name, content, usage_count,
                created_at, updated_at
            FROM templates
            WHERE user_id = $1
            ORDER BY created_at DESC
        """

        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_all_llm_requests(
        conn: asyncpg.Connection,
        user_id: int,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all LLM requests for a user's tasks.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            limit: Optional limit on number of requests (None for all)

        Returns:
            List of LLM request dictionaries ordered by created_at DESC

        Example:
            >>> llm_requests = await ExportDAO.get_all_llm_requests(conn, user_id=1)
        """
        query = """
            SELECT
                lr.id, lr.task_id, lr.provider, lr.model,
                lr.request_type, lr.prompt_tokens, lr.completion_tokens,
                lr.total_tokens, lr.cost, lr.duration_ms,
                lr.status, lr.error_message, lr.metadata_json,
                lr.created_at
            FROM llm_requests lr
            INNER JOIN tasks t ON lr.task_id = t.id
            WHERE t.assignee_user_id = $1
            ORDER BY lr.created_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_export_statistics(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> Dict[str, int]:
        """
        Get statistics about exportable data for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            Dictionary with counts of different data types

        Example:
            >>> stats = await ExportDAO.get_export_statistics(conn, user_id=1)
            >>> print(f"Messages: {stats['messages']}, Tasks: {stats['tasks']}")
        """
        # Count messages
        messages_query = """
            SELECT COUNT(DISTINCT m.id) as count
            FROM messages m
            INNER JOIN channels_allowlist ca
                ON m.platform = ca.platform
                AND m.channel_id = ca.channel_id
            WHERE ca.user_id = $1
        """
        messages_row = await conn.fetchrow(messages_query, user_id)
        messages_count = messages_row['count'] if messages_row else 0

        # Count tasks
        tasks_query = """
            SELECT COUNT(*) as count
            FROM tasks
            WHERE assignee_user_id = $1
        """
        tasks_row = await conn.fetchrow(tasks_query, user_id)
        tasks_count = tasks_row['count'] if tasks_row else 0

        # Count replies
        replies_query = """
            SELECT COUNT(*) as count
            FROM replies r
            INNER JOIN tasks t ON r.task_id = t.id
            WHERE t.assignee_user_id = $1
        """
        replies_row = await conn.fetchrow(replies_query, user_id)
        replies_count = replies_row['count'] if replies_row else 0

        # Count allowlist entries
        allowlist_query = """
            SELECT COUNT(*) as count
            FROM channels_allowlist
            WHERE user_id = $1
        """
        allowlist_row = await conn.fetchrow(allowlist_query, user_id)
        allowlist_count = allowlist_row['count'] if allowlist_row else 0

        # Count LLM requests
        llm_query = """
            SELECT COUNT(*) as count
            FROM llm_requests lr
            INNER JOIN tasks t ON lr.task_id = t.id
            WHERE t.assignee_user_id = $1
        """
        llm_row = await conn.fetchrow(llm_query, user_id)
        llm_count = llm_row['count'] if llm_row else 0

        # Count templates
        templates_query = """
            SELECT COUNT(*) as count
            FROM templates
            WHERE user_id = $1
        """
        templates_row = await conn.fetchrow(templates_query, user_id)
        templates_count = templates_row['count'] if templates_row else 0

        return {
            'messages': messages_count,
            'tasks': tasks_count,
            'replies': replies_count,
            'allowlist': allowlist_count,
            'templates': templates_count,
            'llm_requests': llm_count,
        }
