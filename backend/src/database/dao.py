"""
Data Access Objects for database operations.

This module provides DAO classes for each database model:
- UserDAO: User operations (create, get, update DND settings)
- DiscordDAO: Discord connection management
- TaskDAO: Task operations
- AllowlistDAO: Channel allowlist management
- MessageDAO: Message operations
- ReplyDAO: Reply operations

All DAOs use SQLAlchemy sessions and provide clean interfaces for handlers.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session

from .models import (
    User,
    DiscordConnection,
    Task,
    ChannelsAllowlist,
    Message,
    Reply,
    Settings,
    AuditLog,
)


class UserDAO:
    """Data Access Object for User operations."""

    @staticmethod
    def get_user_by_tg_id(session: Session, tg_user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by Telegram user ID.

        Args:
            session: Database session
            tg_user_id: Telegram user ID

        Returns:
            User dictionary or None if not found
        """
        result = session.execute(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            return {
                'id': user.id,
                'tg_user_id': user.tg_user_id,
                'username': user.username,
                'created_at': user.created_at,
                'updated_at': user.updated_at,
            }
        return None

    @staticmethod
    def create_user(session: Session, tg_user_id: int, username: Optional[str] = None) -> int:
        """
        Create a new user.

        Args:
            session: Database session
            tg_user_id: Telegram user ID
            username: Optional username

        Returns:
            Created user ID
        """
        user = User(
            tg_user_id=tg_user_id,
            username=username,
        )
        session.add(user)
        session.flush()  # Get ID without committing

        # Create default settings for the user
        settings = Settings(
            user_id=user.id,
            dnd_enabled=False,
            reminders_enabled=False,
        )
        session.add(settings)
        session.flush()

        return user.id

    @staticmethod
    def update_dnd_settings(
        session: Session,
        user_id: int,
        dnd_enabled: bool,
        dnd_schedule_json: Optional[str] = None
    ) -> bool:
        """
        Update DND settings for a user.

        Args:
            session: Database session
            user_id: User ID
            dnd_enabled: Whether DND is enabled
            dnd_schedule_json: Optional DND schedule JSON

        Returns:
            True if successful
        """
        stmt = (
            update(Settings)
            .where(Settings.user_id == user_id)
            .values(
                dnd_enabled=dnd_enabled,
                dnd_schedule_json=dnd_schedule_json,
                updated_at=datetime.utcnow()
            )
        )
        result = session.execute(stmt)

        # If no settings exist, create them
        if result.rowcount == 0:
            settings = Settings(
                user_id=user_id,
                dnd_enabled=dnd_enabled,
                dnd_schedule_json=dnd_schedule_json,
            )
            session.add(settings)
            session.flush()

        return True

    @staticmethod
    def get_user_settings(session: Session, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user settings.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            Settings dictionary or None
        """
        result = session.execute(
            select(Settings).where(Settings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            return {
                'id': settings.id,
                'user_id': settings.user_id,
                'dnd_enabled': settings.dnd_enabled,
                'dnd_schedule_json': settings.dnd_schedule_json,
                'reminders_enabled': settings.reminders_enabled,
                'created_at': settings.created_at,
                'updated_at': settings.updated_at,
            }
        return None


class DiscordDAO:
    """Data Access Object for Discord connection operations."""

    @staticmethod
    def save_discord_connection(
        session: Session,
        user_id: int,
        encrypted_token: str,
        super_properties: Optional[str] = None
    ) -> int:
        """
        Save or update Discord connection.

        Args:
            session: Database session
            user_id: User ID
            encrypted_token: Encrypted Discord token
            super_properties: Optional super properties JSON

        Returns:
            Connection ID
        """
        # Check if connection already exists
        result = session.execute(
            select(DiscordConnection).where(DiscordConnection.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing connection
            existing.user_token_encrypted = encrypted_token
            existing.super_properties = super_properties
            existing.status = 'disconnected'
            existing.updated_at = datetime.utcnow()
            session.flush()
            return existing.id
        else:
            # Create new connection
            connection = DiscordConnection(
                user_id=user_id,
                user_token_encrypted=encrypted_token,
                super_properties=super_properties,
                status='disconnected',
            )
            session.add(connection)
            session.flush()
            return connection.id

    @staticmethod
    def get_discord_connection(session: Session, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get Discord connection for a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            Connection dictionary or None
        """
        result = session.execute(
            select(DiscordConnection).where(DiscordConnection.user_id == user_id)
        )
        conn = result.scalar_one_or_none()

        if conn:
            return {
                'id': conn.id,
                'user_id': conn.user_id,
                'user_token_encrypted': conn.user_token_encrypted,
                'super_properties': conn.super_properties,
                'session_id': conn.session_id,
                'last_connected_at': conn.last_connected_at,
                'status': conn.status,
                'error_message': conn.error_message,
                'created_at': conn.created_at,
                'updated_at': conn.updated_at,
            }
        return None

    @staticmethod
    def update_connection_status(
        session: Session,
        user_id: int,
        status: str,
        session_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update Discord connection status.

        Args:
            session: Database session
            user_id: User ID
            status: Connection status ('connected', 'disconnected', 'error')
            session_id: Optional session ID
            error_message: Optional error message

        Returns:
            True if successful
        """
        values = {
            'status': status,
            'updated_at': datetime.utcnow(),
        }

        if session_id:
            values['session_id'] = session_id

        if status == 'connected':
            values['last_connected_at'] = datetime.utcnow()

        if error_message:
            values['error_message'] = error_message

        stmt = (
            update(DiscordConnection)
            .where(DiscordConnection.user_id == user_id)
            .values(**values)
        )
        result = session.execute(stmt)
        return result.rowcount > 0


class TaskDAO:
    """Data Access Object for Task operations."""

    @staticmethod
    def get_open_tasks(session: Session, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all open tasks for a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            List of task dictionaries
        """
        result = session.execute(
            select(Task)
            .where(Task.assignee_user_id == user_id)
            .where(Task.status == 'open')
            .order_by(Task.created_at.desc())
        )
        tasks = result.scalars().all()

        return [
            {
                'id': task.id,
                'source_message_id': task.source_message_id,
                'status': task.status,
                'assignee_user_id': task.assignee_user_id,
                'tg_card_message_id': task.tg_card_message_id,
                'error_message': task.error_message,
                'reminder_count': task.reminder_count,
                'created_at': task.created_at,
                'updated_at': task.updated_at,
                'answered_at': task.answered_at,
            }
            for task in tasks
        ]

    @staticmethod
    def get_task_by_id(session: Session, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get task by ID.

        Args:
            session: Database session
            task_id: Task ID

        Returns:
            Task dictionary or None
        """
        result = session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()

        if task:
            return {
                'id': task.id,
                'source_message_id': task.source_message_id,
                'status': task.status,
                'assignee_user_id': task.assignee_user_id,
                'tg_card_message_id': task.tg_card_message_id,
                'error_message': task.error_message,
                'reminder_count': task.reminder_count,
                'created_at': task.created_at,
                'updated_at': task.updated_at,
                'answered_at': task.answered_at,
            }
        return None


class AllowlistDAO:
    """Data Access Object for Channel Allowlist operations."""

    @staticmethod
    def add_channel(
        session: Session,
        platform: str,
        channel_id: str,
        server_id: Optional[str] = None,
        thread_filter_json: Optional[str] = None,
        enabled: bool = True
    ) -> int:
        """
        Add a channel to the allowlist.

        Args:
            session: Database session
            platform: Platform name ('discord', 'telegram')
            channel_id: Channel ID
            server_id: Optional server ID (for Discord)
            thread_filter_json: Optional thread filter JSON
            enabled: Whether the channel is enabled

        Returns:
            Allowlist entry ID
        """
        # Check if already exists
        result = session.execute(
            select(ChannelsAllowlist)
            .where(ChannelsAllowlist.platform == platform)
            .where(ChannelsAllowlist.channel_id == channel_id)
            .where(
                (ChannelsAllowlist.server_id == server_id) if server_id
                else (ChannelsAllowlist.server_id.is_(None))
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing entry
            existing.enabled = enabled
            existing.thread_filter_json = thread_filter_json
            existing.updated_at = datetime.utcnow()
            session.flush()
            return existing.id
        else:
            # Create new entry
            entry = ChannelsAllowlist(
                platform=platform,
                server_id=server_id,
                channel_id=channel_id,
                thread_filter_json=thread_filter_json,
                enabled=enabled,
            )
            session.add(entry)
            session.flush()
            return entry.id

    @staticmethod
    def remove_channel(
        session: Session,
        channel_id: str,
        platform: str = 'discord'
    ) -> bool:
        """
        Remove a channel from the allowlist.

        Args:
            session: Database session
            channel_id: Channel ID
            platform: Platform name

        Returns:
            True if successful
        """
        stmt = delete(ChannelsAllowlist).where(
            ChannelsAllowlist.platform == platform,
            ChannelsAllowlist.channel_id == channel_id
        )
        result = session.execute(stmt)
        return result.rowcount > 0

    @staticmethod
    def get_all_channels(
        session: Session,
        platform: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all channels in the allowlist.

        Args:
            session: Database session
            platform: Optional platform filter
            enabled_only: Whether to return only enabled channels

        Returns:
            List of allowlist entry dictionaries
        """
        stmt = select(ChannelsAllowlist)

        if platform:
            stmt = stmt.where(ChannelsAllowlist.platform == platform)

        if enabled_only:
            stmt = stmt.where(ChannelsAllowlist.enabled == True)

        result = session.execute(stmt)
        channels = result.scalars().all()

        return [
            {
                'id': ch.id,
                'platform': ch.platform,
                'server_id': ch.server_id,
                'channel_id': ch.channel_id,
                'thread_filter_json': ch.thread_filter_json,
                'enabled': ch.enabled,
                'created_at': ch.created_at,
                'updated_at': ch.updated_at,
            }
            for ch in channels
        ]

    @staticmethod
    def is_channel_allowed(
        session: Session,
        platform: str,
        channel_id: str,
        server_id: Optional[str] = None
    ) -> bool:
        """
        Check if a channel is in the allowlist.

        Args:
            session: Database session
            platform: Platform name
            channel_id: Channel ID
            server_id: Optional server ID

        Returns:
            True if channel is allowed
        """
        stmt = (
            select(ChannelsAllowlist)
            .where(ChannelsAllowlist.platform == platform)
            .where(ChannelsAllowlist.channel_id == channel_id)
            .where(ChannelsAllowlist.enabled == True)
        )

        if server_id:
            stmt = stmt.where(ChannelsAllowlist.server_id == server_id)

        result = session.execute(stmt)
        return result.scalar_one_or_none() is not None


# ============================================================================
# Asyncpg-based DAOs for async operations
# ============================================================================


class MessageDAO:
    """Async Data Access Object for Message operations using asyncpg."""

    @staticmethod
    async def create_message(
        conn,
        platform: str,
        ext_message_id: str,
        server_id: Optional[str],
        channel_id: str,
        thread_id: Optional[str],
        author_id: str,
        author_name: Optional[str],
        content: Optional[str],
        has_image: bool = False,
        platform_created_at: Optional[str] = None,
        context_ref: Optional[int] = None
    ) -> int:
        """
        Create a new message.

        Args:
            conn: asyncpg connection
            platform: Platform name
            ext_message_id: External message ID
            server_id: Server/guild ID
            channel_id: Channel ID
            thread_id: Thread ID
            author_id: Author ID
            author_name: Author name
            content: Message content
            has_image: Whether message has images
            platform_created_at: Platform timestamp
            context_ref: Context reference

        Returns:
            Created message ID
        """
        # Parse platform_created_at if provided
        platform_dt = None
        if platform_created_at:
            try:
                platform_dt = datetime.fromisoformat(
                    platform_created_at.replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                pass

        query = """
            INSERT INTO messages (
                platform, ext_message_id, server_id, channel_id, thread_id,
                author_id, author_name, content, has_image,
                platform_created_at, context_ref, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            RETURNING id
        """

        row = await conn.fetchrow(
            query,
            platform,
            ext_message_id,
            server_id,
            channel_id,
            thread_id,
            author_id,
            author_name,
            content,
            has_image,
            platform_dt,
            context_ref
        )

        return row['id']

    @staticmethod
    async def get_message_by_id(conn, message_id: int) -> Optional[Dict[str, Any]]:
        """Get a message by its ID."""
        query = """
            SELECT * FROM messages WHERE id = $1
        """
        row = await conn.fetchrow(query, message_id)
        return dict(row) if row else None


class AttachmentDAO:
    """Async Data Access Object for Attachment operations using asyncpg."""

    @staticmethod
    async def create_attachment(
        conn,
        message_id: int,
        kind: str,
        ref: str,
        meta: Optional[str] = None
    ) -> int:
        """
        Create a new attachment.

        Args:
            conn: asyncpg connection
            message_id: Message ID
            kind: Attachment kind
            ref: Reference/URL
            meta: Metadata JSON

        Returns:
            Created attachment ID
        """
        query = """
            INSERT INTO attachments (message_id, kind, ref, meta, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id
        """

        row = await conn.fetchrow(query, message_id, kind, ref, meta)
        return row['id']


class AsyncTaskDAO:
    """Async Data Access Object for Task operations using asyncpg."""

    @staticmethod
    async def create_task(
        conn,
        source_message_id: int,
        assignee_user_id: int,
        status: str = 'open'
    ) -> int:
        """
        Create a new task.

        Args:
            conn: asyncpg connection
            source_message_id: Source message ID
            assignee_user_id: Assignee user ID
            status: Task status

        Returns:
            Created task ID
        """
        query = """
            INSERT INTO tasks (
                source_message_id, assignee_user_id, status,
                reminder_count, created_at, updated_at
            )
            VALUES ($1, $2, $3, 0, NOW(), NOW())
            RETURNING id
        """

        row = await conn.fetchrow(query, source_message_id, assignee_user_id, status)
        return row['id']

    @staticmethod
    async def update_task_status(
        conn,
        task_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update task status."""
        query = """
            UPDATE tasks
            SET status = $2,
                error_message = $3,
                updated_at = NOW(),
                answered_at = CASE WHEN $2 = 'answered' THEN NOW() ELSE answered_at END
            WHERE id = $1
        """

        await conn.execute(query, task_id, status, error_message)

    @staticmethod
    async def update_task_card_id(
        conn,
        task_id: int,
        tg_card_message_id: int
    ) -> None:
        """Update the Telegram card message ID for a task."""
        query = """
            UPDATE tasks
            SET tg_card_message_id = $2, updated_at = NOW()
            WHERE id = $1
        """

        await conn.execute(query, task_id, tg_card_message_id)


class AsyncUserDAO:
    """Async Data Access Object for User operations using asyncpg."""

    @staticmethod
    async def create_user(
        conn,
        tg_user_id: int,
        username: Optional[str] = None
    ) -> int:
        """
        Create a new user.

        Args:
            conn: asyncpg connection
            tg_user_id: Telegram user ID
            username: Optional username

        Returns:
            Created user ID
        """
        query = """
            INSERT INTO users (tg_user_id, username, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW())
            ON CONFLICT (tg_user_id) DO UPDATE
            SET username = EXCLUDED.username, updated_at = NOW()
            RETURNING id
        """

        row = await conn.fetchrow(query, tg_user_id, username)
        return row['id']

    @staticmethod
    async def get_user_by_tg_id(conn, tg_user_id: int) -> Optional[Dict[str, Any]]:
        """Get a user by Telegram ID."""
        query = """
            SELECT * FROM users WHERE tg_user_id = $1
        """
        row = await conn.fetchrow(query, tg_user_id)
        return dict(row) if row else None
