"""
Task Data Access Object.

Provides async database operations for tasks table using asyncpg.
Handles task creation, status updates, and moderator task management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class TaskDAO:
    """
    Data Access Object for tasks table.

    Manages moderator tasks that represent incoming messages requiring responses.
    """

    @staticmethod
    async def create_task(
        conn: asyncpg.Connection,
        source_message_id: int,
        assignee_user_id: int,
        status: str = 'open',
    ) -> int:
        """
        Create a new task for a moderator.

        Args:
            conn: AsyncPG database connection
            source_message_id: ID of the message that triggered this task
            assignee_user_id: User ID of the assigned moderator
            status: Initial task status (default: 'open')

        Returns:
            int: ID of the created task

        Raises:
            asyncpg.ForeignKeyViolationError: If source_message_id or assignee_user_id invalid
            asyncpg.PostgresError: On other database errors

        Example:
            >>> task_id = await TaskDAO.create_task(
            ...     conn=conn,
            ...     source_message_id=123,
            ...     assignee_user_id=1
            ... )
        """
        query = """
            INSERT INTO tasks (
                source_message_id, assignee_user_id, status,
                reminder_count, created_at, updated_at
            )
            VALUES ($1, $2, $3, 0, $4, $5)
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(
            query,
            source_message_id,
            assignee_user_id,
            status,
            now,
            now,
        )

        return row['id']

    @staticmethod
    async def get_task_by_id(
        conn: asyncpg.Connection,
        task_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a task by its ID.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID

        Returns:
            Dictionary with task data or None if not found

        Example:
            >>> task = await TaskDAO.get_task_by_id(conn, 42)
            >>> if task:
            ...     print(f"Status: {task['status']}")
        """
        query = """
            SELECT
                id, source_message_id, status, assignee_user_id,
                tg_card_message_id, error_message, reminder_count,
                created_at, updated_at, answered_at
            FROM tasks
            WHERE id = $1
        """

        row = await conn.fetchrow(query, task_id)
        return dict(row) if row else None

    @staticmethod
    async def get_task_by_message_id(
        conn: asyncpg.Connection,
        source_message_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a task by its source message ID.

        Args:
            conn: AsyncPG database connection
            source_message_id: Source message ID

        Returns:
            Dictionary with task data or None if not found

        Example:
            >>> task = await TaskDAO.get_task_by_message_id(conn, 123)
        """
        query = """
            SELECT
                id, source_message_id, status, assignee_user_id,
                tg_card_message_id, error_message, reminder_count,
                created_at, updated_at, answered_at
            FROM tasks
            WHERE source_message_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """

        row = await conn.fetchrow(query, source_message_id)
        return dict(row) if row else None

    @staticmethod
    async def get_open_tasks(
        conn: asyncpg.Connection,
        user_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve open tasks, optionally filtered by assignee.

        Args:
            conn: AsyncPG database connection
            user_id: Filter by assignee user ID (None for all users)
            limit: Maximum number of tasks to return (default: 100)

        Returns:
            List of task dictionaries ordered by created_at ASC (oldest first)

        Example:
            >>> open_tasks = await TaskDAO.get_open_tasks(conn, user_id=1)
            >>> print(f"You have {len(open_tasks)} open tasks")
        """
        if user_id is not None:
            query = """
                SELECT
                    id, source_message_id, status, assignee_user_id,
                    tg_card_message_id, error_message, reminder_count,
                    created_at, updated_at, answered_at
                FROM tasks
                WHERE status = 'open' AND assignee_user_id = $1
                ORDER BY created_at ASC
                LIMIT $2
            """
            rows = await conn.fetch(query, user_id, limit)
        else:
            query = """
                SELECT
                    id, source_message_id, status, assignee_user_id,
                    tg_card_message_id, error_message, reminder_count,
                    created_at, updated_at, answered_at
                FROM tasks
                WHERE status = 'open'
                ORDER BY created_at ASC
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_tasks_by_status(
        conn: asyncpg.Connection,
        status: str,
        user_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve tasks by status, optionally filtered by assignee.

        Args:
            conn: AsyncPG database connection
            status: Task status ('open' | 'answered' | 'muted' | 'error')
            user_id: Filter by assignee user ID (optional)
            limit: Maximum number of tasks to return (default: 100)

        Returns:
            List of task dictionaries ordered by created_at DESC

        Example:
            >>> answered_tasks = await TaskDAO.get_tasks_by_status(
            ...     conn, 'answered', user_id=1, limit=10
            ... )
        """
        if user_id is not None:
            query = """
                SELECT
                    id, source_message_id, status, assignee_user_id,
                    tg_card_message_id, error_message, reminder_count,
                    created_at, updated_at, answered_at
                FROM tasks
                WHERE status = $1 AND assignee_user_id = $2
                ORDER BY created_at DESC
                LIMIT $3
            """
            rows = await conn.fetch(query, status, user_id, limit)
        else:
            query = """
                SELECT
                    id, source_message_id, status, assignee_user_id,
                    tg_card_message_id, error_message, reminder_count,
                    created_at, updated_at, answered_at
                FROM tasks
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, status, limit)

        return [dict(row) for row in rows]

    @staticmethod
    async def update_task_status(
        conn: asyncpg.Connection,
        task_id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update task status and optionally set error message.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID
            status: New status ('open' | 'answered' | 'muted' | 'error')
            error_message: Error message (required if status='error')

        Returns:
            True if task was updated, False if task not found

        Example:
            >>> success = await TaskDAO.update_task_status(
            ...     conn, task_id=42, status='error',
            ...     error_message='Failed to post reply'
            ... )
        """
        query = """
            UPDATE tasks
            SET status = $1,
                error_message = $2,
                updated_at = $3
            WHERE id = $4
        """

        result = await conn.execute(
            query,
            status,
            error_message,
            datetime.utcnow(),
            task_id,
        )

        # Check if any rows were updated
        return result.split()[-1] != '0'

    @staticmethod
    async def update_task_card_id(
        conn: asyncpg.Connection,
        task_id: int,
        tg_card_message_id: int,
    ) -> bool:
        """
        Update task with Telegram card message ID.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID
            tg_card_message_id: Telegram message ID of the task card

        Returns:
            True if task was updated, False if task not found

        Example:
            >>> await TaskDAO.update_task_card_id(conn, task_id=42, tg_card_message_id=999)
        """
        query = """
            UPDATE tasks
            SET tg_card_message_id = $1,
                updated_at = $2
            WHERE id = $3
        """

        result = await conn.execute(
            query,
            tg_card_message_id,
            datetime.utcnow(),
            task_id,
        )

        return result.split()[-1] != '0'

    @staticmethod
    async def mark_task_answered(
        conn: asyncpg.Connection,
        task_id: int,
    ) -> bool:
        """
        Mark a task as answered and record the timestamp.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID

        Returns:
            True if task was updated, False if task not found

        Example:
            >>> await TaskDAO.mark_task_answered(conn, task_id=42)
        """
        now = datetime.utcnow()
        query = """
            UPDATE tasks
            SET status = 'answered',
                answered_at = $1,
                updated_at = $2
            WHERE id = $3
        """

        result = await conn.execute(query, now, now, task_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def increment_reminder_count(
        conn: asyncpg.Connection,
        task_id: int,
    ) -> int:
        """
        Increment the reminder count for a task.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID

        Returns:
            New reminder count

        Example:
            >>> count = await TaskDAO.increment_reminder_count(conn, task_id=42)
            >>> print(f"Reminder sent {count} times")
        """
        query = """
            UPDATE tasks
            SET reminder_count = reminder_count + 1,
                updated_at = $1
            WHERE id = $2
            RETURNING reminder_count
        """

        row = await conn.fetchrow(query, datetime.utcnow(), task_id)
        return row['reminder_count'] if row else 0

    @staticmethod
    async def delete_task(
        conn: asyncpg.Connection,
        task_id: int,
    ) -> bool:
        """
        Delete a task by ID.

        Note: This will cascade delete all associated replies.

        Args:
            conn: AsyncPG database connection
            task_id: Task ID

        Returns:
            True if task was deleted, False if task not found

        Example:
            >>> deleted = await TaskDAO.delete_task(conn, task_id=42)
        """
        query = "DELETE FROM tasks WHERE id = $1"
        result = await conn.execute(query, task_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def count_tasks_by_status(
        conn: asyncpg.Connection,
        status: str,
        user_id: Optional[int] = None,
    ) -> int:
        """
        Count tasks by status, optionally filtered by user.

        Args:
            conn: AsyncPG database connection
            status: Task status
            user_id: Filter by assignee user ID (optional)

        Returns:
            Task count

        Example:
            >>> open_count = await TaskDAO.count_tasks_by_status(conn, 'open', user_id=1)
        """
        if user_id is not None:
            query = """
                SELECT COUNT(*) as count
                FROM tasks
                WHERE status = $1 AND assignee_user_id = $2
            """
            row = await conn.fetchrow(query, status, user_id)
        else:
            query = """
                SELECT COUNT(*) as count
                FROM tasks
                WHERE status = $1
            """
            row = await conn.fetchrow(query, status)

        return row['count'] if row else 0
