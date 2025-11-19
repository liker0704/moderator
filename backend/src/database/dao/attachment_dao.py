"""
Attachment Data Access Object.

Provides async database operations for attachments table using asyncpg.
Handles message attachments (images, links, videos, files).
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncpg


class AttachmentDAO:
    """
    Data Access Object for attachments table.

    Manages file and media attachments associated with messages.
    """

    @staticmethod
    async def create_attachment(
        conn: asyncpg.Connection,
        message_id: int,
        kind: str,
        ref: str,
        meta: Optional[str] = None,
    ) -> int:
        """
        Create a new attachment record.

        Args:
            conn: AsyncPG database connection
            message_id: ID of the message this attachment belongs to
            kind: Attachment type ('image' | 'link' | 'video' | 'file')
            ref: URL or file path to the attachment
            meta: JSON string with metadata (optional)
                  e.g., '{"size": 1024, "type": "image/png", "width": 800, "height": 600}'

        Returns:
            int: ID of the created attachment

        Raises:
            asyncpg.ForeignKeyViolationError: If message_id is invalid
            asyncpg.PostgresError: On other database errors

        Example:
            >>> import json
            >>> meta = json.dumps({"size": 2048, "type": "image/jpeg"})
            >>> attachment_id = await AttachmentDAO.create_attachment(
            ...     conn=conn,
            ...     message_id=123,
            ...     kind='image',
            ...     ref='https://cdn.discord.com/attachments/...',
            ...     meta=meta
            ... )
        """
        query = """
            INSERT INTO attachments (
                message_id, kind, ref, meta, created_at
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """

        row = await conn.fetchrow(
            query,
            message_id,
            kind,
            ref,
            meta,
            datetime.utcnow(),
        )

        return row['id']

    @staticmethod
    async def get_attachment_by_id(
        conn: asyncpg.Connection,
        attachment_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve an attachment by its ID.

        Args:
            conn: AsyncPG database connection
            attachment_id: Attachment ID

        Returns:
            Dictionary with attachment data or None if not found

        Example:
            >>> attachment = await AttachmentDAO.get_attachment_by_id(conn, 1)
            >>> if attachment:
            ...     print(f"Type: {attachment['kind']}, URL: {attachment['ref']}")
        """
        query = """
            SELECT id, message_id, kind, ref, meta, created_at
            FROM attachments
            WHERE id = $1
        """

        row = await conn.fetchrow(query, attachment_id)
        return dict(row) if row else None

    @staticmethod
    async def get_attachments_for_message(
        conn: asyncpg.Connection,
        message_id: int,
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all attachments for a specific message.

        Args:
            conn: AsyncPG database connection
            message_id: Message ID
            kind: Filter by attachment type (optional)

        Returns:
            List of attachment dictionaries ordered by created_at ASC

        Example:
            >>> # Get all attachments
            >>> attachments = await AttachmentDAO.get_attachments_for_message(conn, 123)
            >>>
            >>> # Get only images
            >>> images = await AttachmentDAO.get_attachments_for_message(
            ...     conn, 123, kind='image'
            ... )
            >>> for img in images:
            ...     print(f"Image URL: {img['ref']}")
        """
        if kind:
            query = """
                SELECT id, message_id, kind, ref, meta, created_at
                FROM attachments
                WHERE message_id = $1 AND kind = $2
                ORDER BY created_at ASC
            """
            rows = await conn.fetch(query, message_id, kind)
        else:
            query = """
                SELECT id, message_id, kind, ref, meta, created_at
                FROM attachments
                WHERE message_id = $1
                ORDER BY created_at ASC
            """
            rows = await conn.fetch(query, message_id)

        return [dict(row) for row in rows]

    @staticmethod
    async def delete_attachment(
        conn: asyncpg.Connection,
        attachment_id: int,
    ) -> bool:
        """
        Delete an attachment by ID.

        Args:
            conn: AsyncPG database connection
            attachment_id: Attachment ID

        Returns:
            True if attachment was deleted, False if attachment not found

        Example:
            >>> deleted = await AttachmentDAO.delete_attachment(conn, 1)
        """
        query = "DELETE FROM attachments WHERE id = $1"
        result = await conn.execute(query, attachment_id)
        return result.split()[-1] != '0'

    @staticmethod
    async def delete_attachments_for_message(
        conn: asyncpg.Connection,
        message_id: int,
    ) -> int:
        """
        Delete all attachments for a specific message.

        Args:
            conn: AsyncPG database connection
            message_id: Message ID

        Returns:
            Number of attachments deleted

        Example:
            >>> count = await AttachmentDAO.delete_attachments_for_message(conn, 123)
            >>> print(f"Deleted {count} attachments")
        """
        query = "DELETE FROM attachments WHERE message_id = $1"
        result = await conn.execute(query, message_id)
        return int(result.split()[-1])

    @staticmethod
    async def count_attachments_by_type(
        conn: asyncpg.Connection,
        message_id: int,
    ) -> Dict[str, int]:
        """
        Count attachments by type for a message.

        Args:
            conn: AsyncPG database connection
            message_id: Message ID

        Returns:
            Dictionary mapping attachment kinds to counts

        Example:
            >>> counts = await AttachmentDAO.count_attachments_by_type(conn, 123)
            >>> print(counts)  # {'image': 2, 'link': 1, 'video': 0, 'file': 1}
        """
        query = """
            SELECT kind, COUNT(*) as count
            FROM attachments
            WHERE message_id = $1
            GROUP BY kind
        """

        rows = await conn.fetch(query, message_id)
        return {row['kind']: row['count'] for row in rows}

    @staticmethod
    async def get_images_for_message(
        conn: asyncpg.Connection,
        message_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all image attachments for a message.

        Convenience method for getting images specifically.

        Args:
            conn: AsyncPG database connection
            message_id: Message ID

        Returns:
            List of image attachment dictionaries

        Example:
            >>> images = await AttachmentDAO.get_images_for_message(conn, 123)
            >>> for img in images:
            ...     print(f"Image: {img['ref']}")
        """
        return await AttachmentDAO.get_attachments_for_message(
            conn, message_id, kind='image'
        )

    @staticmethod
    async def has_attachments(
        conn: asyncpg.Connection,
        message_id: int,
        kind: Optional[str] = None,
    ) -> bool:
        """
        Check if a message has any attachments.

        Args:
            conn: AsyncPG database connection
            message_id: Message ID
            kind: Filter by attachment type (optional)

        Returns:
            True if message has attachments, False otherwise

        Example:
            >>> has_any = await AttachmentDAO.has_attachments(conn, 123)
            >>> has_images = await AttachmentDAO.has_attachments(conn, 123, kind='image')
        """
        if kind:
            query = """
                SELECT EXISTS(
                    SELECT 1 FROM attachments
                    WHERE message_id = $1 AND kind = $2
                ) as exists
            """
            row = await conn.fetchrow(query, message_id, kind)
        else:
            query = """
                SELECT EXISTS(
                    SELECT 1 FROM attachments
                    WHERE message_id = $1
                ) as exists
            """
            row = await conn.fetchrow(query, message_id)

        return row['exists'] if row else False

    @staticmethod
    async def bulk_create_attachments(
        conn: asyncpg.Connection,
        attachments: List[Dict[str, Any]],
    ) -> List[int]:
        """
        Create multiple attachments in a single operation.

        Args:
            conn: AsyncPG database connection
            attachments: List of attachment dictionaries with keys:
                        - message_id (int)
                        - kind (str)
                        - ref (str)
                        - meta (str, optional)

        Returns:
            List of created attachment IDs

        Example:
            >>> attachments = [
            ...     {
            ...         "message_id": 123,
            ...         "kind": "image",
            ...         "ref": "https://example.com/image1.jpg",
            ...         "meta": '{"size": 1024}'
            ...     },
            ...     {
            ...         "message_id": 123,
            ...         "kind": "link",
            ...         "ref": "https://example.com",
            ...         "meta": None
            ...     }
            ... ]
            >>> ids = await AttachmentDAO.bulk_create_attachments(conn, attachments)
        """
        if not attachments:
            return []

        # Prepare values for bulk insert
        values = []
        now = datetime.utcnow()

        for att in attachments:
            values.append((
                att['message_id'],
                att['kind'],
                att['ref'],
                att.get('meta'),
                now,
            ))

        # Use executemany for bulk insert
        query = """
            INSERT INTO attachments (message_id, kind, ref, meta, created_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """

        # Execute multiple inserts and collect IDs
        ids = []
        for value_tuple in values:
            row = await conn.fetchrow(query, *value_tuple)
            ids.append(row['id'])

        return ids

    @staticmethod
    async def update_attachment_ref(
        conn: asyncpg.Connection,
        attachment_id: int,
        new_ref: str,
    ) -> bool:
        """
        Update the reference (URL/path) of an attachment.

        Useful if files are moved to different storage or CDN.

        Args:
            conn: AsyncPG database connection
            attachment_id: Attachment ID
            new_ref: New URL or file path

        Returns:
            True if attachment was updated, False if attachment not found

        Example:
            >>> updated = await AttachmentDAO.update_attachment_ref(
            ...     conn, attachment_id=1, new_ref='https://cdn.example.com/new-url.jpg'
            ... )
        """
        query = """
            UPDATE attachments
            SET ref = $1
            WHERE id = $2
        """

        result = await conn.execute(query, new_ref, attachment_id)
        return result.split()[-1] != '0'
