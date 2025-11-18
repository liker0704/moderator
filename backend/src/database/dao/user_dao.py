"""
User Data Access Object.

Provides async database operations for users and settings tables using asyncpg.
Handles user creation, retrieval, and settings management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class UserDAO:
    """
    Data Access Object for users table.

    Manages system users (moderators) and their settings.
    """

    @staticmethod
    async def create_user(
        conn: asyncpg.Connection,
        tg_user_id: int,
        username: Optional[str] = None,
    ) -> int:
        """
        Create a new user (moderator).

        Args:
            conn: AsyncPG database connection
            tg_user_id: Telegram user ID (unique identifier)
            username: Username or display name (optional)

        Returns:
            int: ID of the created user

        Raises:
            asyncpg.UniqueViolationError: If user with same tg_user_id exists
            asyncpg.PostgresError: On other database errors

        Example:
            >>> user_id = await UserDAO.create_user(
            ...     conn=conn,
            ...     tg_user_id=123456789,
            ...     username='moderator1'
            ... )
        """
        query = """
            INSERT INTO users (tg_user_id, username, created_at, updated_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(query, tg_user_id, username, now, now)
        return row['id']

    @staticmethod
    async def get_user_by_id(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by internal ID.

        Args:
            conn: AsyncPG database connection
            user_id: Internal user ID

        Returns:
            Dictionary with user data or None if not found

        Example:
            >>> user = await UserDAO.get_user_by_id(conn, 1)
            >>> if user:
            ...     print(f"Username: {user['username']}")
        """
        query = """
            SELECT id, tg_user_id, username, created_at, updated_at
            FROM users
            WHERE id = $1
        """

        row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None

    @staticmethod
    async def get_user_by_tg_id(
        conn: asyncpg.Connection,
        tg_user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by Telegram user ID.

        Args:
            conn: AsyncPG database connection
            tg_user_id: Telegram user ID

        Returns:
            Dictionary with user data or None if not found

        Example:
            >>> user = await UserDAO.get_user_by_tg_id(conn, 123456789)
            >>> if user:
            ...     print(f"User ID: {user['id']}")
        """
        query = """
            SELECT id, tg_user_id, username, created_at, updated_at
            FROM users
            WHERE tg_user_id = $1
        """

        row = await conn.fetchrow(query, tg_user_id)
        return dict(row) if row else None

    @staticmethod
    async def get_or_create_user(
        conn: asyncpg.Connection,
        tg_user_id: int,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get existing user or create new one if not exists.

        Args:
            conn: AsyncPG database connection
            tg_user_id: Telegram user ID
            username: Username (optional, only used for new users)

        Returns:
            Dictionary with user data

        Example:
            >>> user = await UserDAO.get_or_create_user(conn, 123456789, 'moderator1')
            >>> print(f"User ID: {user['id']}")
        """
        # Try to get existing user first
        user = await UserDAO.get_user_by_tg_id(conn, tg_user_id)

        if user:
            return user

        # Create new user
        user_id = await UserDAO.create_user(conn, tg_user_id, username)
        return await UserDAO.get_user_by_id(conn, user_id)

    @staticmethod
    async def update_username(
        conn: asyncpg.Connection,
        user_id: int,
        username: str,
    ) -> bool:
        """
        Update user's username.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            username: New username

        Returns:
            True if user was updated, False if user not found

        Example:
            >>> updated = await UserDAO.update_username(conn, 1, 'new_username')
        """
        query = """
            UPDATE users
            SET username = $1,
                updated_at = $2
            WHERE id = $3
        """

        result = await conn.execute(query, username, datetime.utcnow(), user_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def get_all_users(
        conn: asyncpg.Connection,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all users.

        Args:
            conn: AsyncPG database connection

        Returns:
            List of user dictionaries ordered by created_at ASC

        Example:
            >>> users = await UserDAO.get_all_users(conn)
            >>> for user in users:
            ...     print(f"{user['id']}: {user['username']}")
        """
        query = """
            SELECT id, tg_user_id, username, created_at, updated_at
            FROM users
            ORDER BY created_at ASC
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    async def delete_user(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> bool:
        """
        Delete a user by ID.

        Note: This will cascade delete all associated data (tasks, settings, etc.)

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            True if user was deleted, False if user not found

        Example:
            >>> deleted = await UserDAO.delete_user(conn, 1)
        """
        query = "DELETE FROM users WHERE id = $1"
        result = await conn.execute(query, user_id)
        return result.split()[-1] != '0'

    # Settings-related methods

    @staticmethod
    async def get_user_settings(
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
            >>> settings = await UserDAO.get_user_settings(conn, 1)
            >>> if settings:
            ...     print(f"DND enabled: {settings['dnd_enabled']}")
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
    async def create_default_settings(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> int:
        """
        Create default settings for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            int: ID of the created settings record

        Raises:
            asyncpg.UniqueViolationError: If settings already exist for user
            asyncpg.ForeignKeyViolationError: If user_id is invalid
            asyncpg.PostgresError: On other database errors

        Example:
            >>> settings_id = await UserDAO.create_default_settings(conn, 1)
        """
        query = """
            INSERT INTO settings (
                user_id, dnd_enabled, dnd_schedule_json,
                reminders_enabled, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        now = datetime.utcnow()
        row = await conn.fetchrow(
            query,
            user_id,
            False,  # dnd_enabled
            None,   # dnd_schedule_json
            False,  # reminders_enabled
            now,
            now,
        )

        return row['id']

    @staticmethod
    async def get_or_create_settings(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Get existing settings or create default settings if not exist.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            Dictionary with settings data

        Example:
            >>> settings = await UserDAO.get_or_create_settings(conn, 1)
        """
        # Try to get existing settings first
        settings = await UserDAO.get_user_settings(conn, user_id)

        if settings:
            return settings

        # Create default settings
        settings_id = await UserDAO.create_default_settings(conn, user_id)
        return await UserDAO.get_user_settings(conn, user_id)

    @staticmethod
    async def update_dnd_settings(
        conn: asyncpg.Connection,
        user_id: int,
        dnd_enabled: Optional[bool] = None,
        dnd_schedule_json: Optional[str] = None,
    ) -> bool:
        """
        Update Do Not Disturb settings for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            dnd_enabled: Whether DND mode is enabled (optional, only updates if provided)
            dnd_schedule_json: JSON string with DND schedule (optional, only updates if provided)
                              e.g., '[{"start": "22:00", "end": "08:00", "days": [0,1,2,3,4]}]'

        Returns:
            True if settings were updated, False if settings not found

        Example:
            >>> import json
            >>> # Update only DND enabled
            >>> await UserDAO.update_dnd_settings(conn, user_id=1, dnd_enabled=True)
            >>> # Update only schedule
            >>> schedule = json.dumps([{"start": "22:00", "end": "08:00", "days": [0,1,2,3,4]}])
            >>> await UserDAO.update_dnd_settings(conn, user_id=1, dnd_schedule_json=schedule)
            >>> # Update both
            >>> await UserDAO.update_dnd_settings(
            ...     conn, user_id=1, dnd_enabled=True, dnd_schedule_json=schedule
            ... )
        """
        # Build dynamic update query based on provided parameters
        update_fields = []
        params = []
        param_count = 1

        if dnd_enabled is not None:
            update_fields.append(f"dnd_enabled = ${param_count}")
            params.append(dnd_enabled)
            param_count += 1

        if dnd_schedule_json is not None:
            update_fields.append(f"dnd_schedule_json = ${param_count}")
            params.append(dnd_schedule_json)
            param_count += 1

        if not update_fields:
            # No fields to update
            return False

        # Add updated_at
        update_fields.append(f"updated_at = ${param_count}")
        params.append(datetime.utcnow())
        param_count += 1

        # Add user_id for WHERE clause
        params.append(user_id)

        query = f"""
            INSERT INTO settings (user_id, dnd_enabled, dnd_schedule_json, created_at, updated_at)
            VALUES (${param_count}, FALSE, NULL, NOW(), NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET {', '.join(update_fields)}
        """

        result = await conn.execute(query, *params)
        return True

    @staticmethod
    async def update_reminders_enabled(
        conn: asyncpg.Connection,
        user_id: int,
        reminders_enabled: bool,
    ) -> bool:
        """
        Update reminder settings for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            reminders_enabled: Whether reminders are enabled

        Returns:
            True if settings were updated, False if settings not found

        Example:
            >>> updated = await UserDAO.update_reminders_enabled(conn, 1, True)
        """
        query = """
            UPDATE settings
            SET reminders_enabled = $1,
                updated_at = $2
            WHERE user_id = $3
        """

        result = await conn.execute(
            query,
            reminders_enabled,
            datetime.utcnow(),
            user_id,
        )

        return result.split()[-1] != '0'

    @staticmethod
    async def get_users_with_dnd_enabled(
        conn: asyncpg.Connection,
    ) -> List[Dict[str, Any]]:
        """
        Get all users who have DND mode enabled.

        Args:
            conn: AsyncPG database connection

        Returns:
            List of user dictionaries with their DND settings

        Example:
            >>> dnd_users = await UserDAO.get_users_with_dnd_enabled(conn)
            >>> for user in dnd_users:
            ...     print(f"User {user['username']} has DND enabled")
        """
        query = """
            SELECT u.id, u.tg_user_id, u.username,
                   s.dnd_enabled, s.dnd_schedule_json
            FROM users u
            INNER JOIN settings s ON u.id = s.user_id
            WHERE s.dnd_enabled = TRUE
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]
