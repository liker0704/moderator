"""
Discord Connection Data Access Object.

Provides async database operations for discord_connection table using asyncpg.
Handles encrypted Discord tokens and connection status management.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import asyncpg


class DiscordDAO:
    """
    Data Access Object for discord_connection table.

    Manages Discord Gateway connection information including encrypted tokens.
    Note: Encryption/decryption should be handled by the encryption service.
    """

    @staticmethod
    async def save_discord_connection(
        conn: asyncpg.Connection,
        user_id: int,
        encrypted_token: str,
        super_properties: Optional[str] = None,
        status: str = 'disconnected',
    ) -> int:
        """
        Save or update Discord connection information for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            encrypted_token: Encrypted Discord user token
            super_properties: JSON string with Discord super properties (optional)
            status: Initial connection status (default: 'disconnected')

        Returns:
            int: ID of the created/updated connection record

        Raises:
            asyncpg.ForeignKeyViolationError: If user_id is invalid
            asyncpg.PostgresError: On other database errors

        Example:
            >>> from database.encryption import encrypt_token
            >>> encrypted = encrypt_token('discord_user_token_here')
            >>> conn_id = await DiscordDAO.save_discord_connection(
            ...     conn=conn,
            ...     user_id=1,
            ...     encrypted_token=encrypted,
            ...     super_properties='{"os":"Windows","browser":"Chrome"}'
            ... )
        """
        # Check if connection already exists for this user
        existing = await DiscordDAO.get_discord_connection(conn, user_id)

        now = datetime.utcnow()

        if existing:
            # Update existing connection
            query = """
                UPDATE discord_connection
                SET user_token_encrypted = $1,
                    super_properties = $2,
                    status = $3,
                    updated_at = $4
                WHERE user_id = $5
                RETURNING id
            """
            row = await conn.fetchrow(
                query,
                encrypted_token,
                super_properties,
                status,
                now,
                user_id,
            )
        else:
            # Create new connection
            query = """
                INSERT INTO discord_connection (
                    user_id, user_token_encrypted, super_properties,
                    status, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """
            row = await conn.fetchrow(
                query,
                user_id,
                encrypted_token,
                super_properties,
                status,
                now,
                now,
            )

        return row['id']

    @staticmethod
    async def get_discord_connection(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve Discord connection information for a user.

        Note: The returned token is still encrypted. Use encryption service to decrypt.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            Dictionary with connection data or None if not found

        Example:
            >>> connection = await DiscordDAO.get_discord_connection(conn, 1)
            >>> if connection:
            ...     print(f"Status: {connection['status']}")
            ...     # Decrypt token separately using encryption service
        """
        query = """
            SELECT
                id, user_id, user_token_encrypted, super_properties,
                session_id, last_connected_at, status, error_message,
                created_at, updated_at
            FROM discord_connection
            WHERE user_id = $1
        """

        row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None

    @staticmethod
    async def get_discord_token(
        conn: asyncpg.Connection,
        user_id: int,
        decrypt_func: callable,
    ) -> Optional[str]:
        """
        Retrieve and decrypt Discord token for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            decrypt_func: Function to decrypt the token (e.g., encryption.decrypt_token)

        Returns:
            Decrypted Discord token or None if connection not found

        Raises:
            EncryptionError: If decryption fails

        Example:
            >>> from database.encryption import decrypt_token
            >>> token = await DiscordDAO.get_discord_token(conn, 1, decrypt_token)
            >>> if token:
            ...     # Use token for Discord API calls
            ...     pass
        """
        connection = await DiscordDAO.get_discord_connection(conn, user_id)

        if not connection or not connection['user_token_encrypted']:
            return None

        # Decrypt the token using provided function
        decrypted_token = decrypt_func(connection['user_token_encrypted'])
        return decrypted_token

    @staticmethod
    async def update_connection_status(
        conn: asyncpg.Connection,
        user_id: int,
        status: str,
        session_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update Discord connection status.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            status: Connection status ('connected' | 'disconnected' | 'error')
            session_id: Discord session ID (optional, set when connected)
            error_message: Error message (optional, set when status='error')

        Returns:
            True if connection was updated, False if connection not found

        Example:
            >>> # Mark as connected
            >>> await DiscordDAO.update_connection_status(
            ...     conn, user_id=1, status='connected', session_id='abc123'
            ... )
            >>>
            >>> # Mark as error
            >>> await DiscordDAO.update_connection_status(
            ...     conn, user_id=1, status='error',
            ...     error_message='Authentication failed'
            ... )
        """
        now = datetime.utcnow()

        # Update last_connected_at if status is 'connected'
        if status == 'connected':
            query = """
                UPDATE discord_connection
                SET status = $1,
                    session_id = $2,
                    error_message = $3,
                    last_connected_at = $4,
                    updated_at = $5
                WHERE user_id = $6
            """
            result = await conn.execute(
                query,
                status,
                session_id,
                error_message,
                now,
                now,
                user_id,
            )
        else:
            query = """
                UPDATE discord_connection
                SET status = $1,
                    session_id = $2,
                    error_message = $3,
                    updated_at = $4
                WHERE user_id = $5
            """
            result = await conn.execute(
                query,
                status,
                session_id,
                error_message,
                now,
                user_id,
            )

        return result.split()[-1] != '0'

    @staticmethod
    async def delete_discord_connection(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> bool:
        """
        Delete Discord connection for a user.

        This removes the stored encrypted token and all connection data.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            True if connection was deleted, False if connection not found

        Example:
            >>> deleted = await DiscordDAO.delete_discord_connection(conn, 1)
        """
        query = "DELETE FROM discord_connection WHERE user_id = $1"
        result = await conn.execute(query, user_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def get_all_connected(
        conn: asyncpg.Connection,
    ) -> list[Dict[str, Any]]:
        """
        Get all Discord connections with 'connected' status.

        Args:
            conn: AsyncPG database connection

        Returns:
            List of connection dictionaries

        Example:
            >>> connected = await DiscordDAO.get_all_connected(conn)
            >>> for conn_data in connected:
            ...     print(f"User {conn_data['user_id']} is connected")
        """
        query = """
            SELECT
                id, user_id, user_token_encrypted, super_properties,
                session_id, last_connected_at, status, error_message,
                created_at, updated_at
            FROM discord_connection
            WHERE status = 'connected'
            ORDER BY last_connected_at DESC
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_all_connections(
        conn: asyncpg.Connection,
    ) -> list[Dict[str, Any]]:
        """
        Get all Discord connections regardless of status.

        Args:
            conn: AsyncPG database connection

        Returns:
            List of connection dictionaries ordered by updated_at DESC

        Example:
            >>> all_conns = await DiscordDAO.get_all_connections(conn)
            >>> for conn_data in all_conns:
            ...     print(f"User {conn_data['user_id']}: {conn_data['status']}")
        """
        query = """
            SELECT
                id, user_id, user_token_encrypted, super_properties,
                session_id, last_connected_at, status, error_message,
                created_at, updated_at
            FROM discord_connection
            ORDER BY updated_at DESC
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    async def update_super_properties(
        conn: asyncpg.Connection,
        user_id: int,
        super_properties: str,
    ) -> bool:
        """
        Update Discord super properties for a user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            super_properties: JSON string with Discord super properties

        Returns:
            True if connection was updated, False if connection not found

        Example:
            >>> import json
            >>> props = json.dumps({
            ...     "os": "Windows",
            ...     "browser": "Chrome",
            ...     "device": "",
            ...     "system_locale": "en-US"
            ... })
            >>> updated = await DiscordDAO.update_super_properties(conn, 1, props)
        """
        query = """
            UPDATE discord_connection
            SET super_properties = $1,
                updated_at = $2
            WHERE user_id = $3
        """

        result = await conn.execute(
            query,
            super_properties,
            datetime.utcnow(),
            user_id,
        )

        return result.split()[-1] != '0'

    @staticmethod
    async def clear_session(
        conn: asyncpg.Connection,
        user_id: int,
    ) -> bool:
        """
        Clear session ID and mark as disconnected.

        Args:
            conn: AsyncPG database connection
            user_id: User ID

        Returns:
            True if connection was updated, False if connection not found

        Example:
            >>> cleared = await DiscordDAO.clear_session(conn, 1)
        """
        query = """
            UPDATE discord_connection
            SET session_id = NULL,
                status = 'disconnected',
                updated_at = $1
            WHERE user_id = $2
        """

        result = await conn.execute(query, datetime.utcnow(), user_id)
        return result.split()[-1] != '0'
