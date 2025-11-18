"""
Audit Log Data Access Object.

Provides async database operations for audit_log table using asyncpg.
Handles system audit logging for security and debugging.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncpg


class AuditDAO:
    """
    Data Access Object for audit_log table.

    Records all significant system events for security monitoring and debugging.
    """

    @staticmethod
    async def log_event(
        conn: asyncpg.Connection,
        kind: str,
        payload_json: str,
        user_id: Optional[int] = None,
    ) -> int:
        """
        Log an audit event.

        Args:
            conn: AsyncPG database connection
            kind: Event type/category (e.g., 'user.login', 'message.received',
                  'reply.posted', 'discord.connected', 'error.occurred')
            payload_json: JSON string with event details
            user_id: User ID associated with the event (optional)

        Returns:
            int: ID of the created audit log entry

        Raises:
            asyncpg.PostgresError: On database errors

        Example:
            >>> import json
            >>> payload = json.dumps({
            ...     "action": "login",
            ...     "ip_address": "192.168.1.1",
            ...     "user_agent": "TelegramBot/1.0"
            ... })
            >>> log_id = await AuditDAO.log_event(
            ...     conn=conn,
            ...     kind='user.login',
            ...     payload_json=payload,
            ...     user_id=1
            ... )
        """
        query = """
            INSERT INTO audit_log (kind, user_id, payload_json, created_at)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """

        row = await conn.fetchrow(
            query,
            kind,
            user_id,
            payload_json,
            datetime.utcnow(),
        )

        return row['id']

    @staticmethod
    async def get_log_by_id(
        conn: asyncpg.Connection,
        log_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve an audit log entry by ID.

        Args:
            conn: AsyncPG database connection
            log_id: Audit log ID

        Returns:
            Dictionary with log data or None if not found

        Example:
            >>> log = await AuditDAO.get_log_by_id(conn, 123)
            >>> if log:
            ...     print(f"Event: {log['kind']}, Time: {log['created_at']}")
        """
        query = """
            SELECT id, kind, user_id, payload_json, created_at
            FROM audit_log
            WHERE id = $1
        """

        row = await conn.fetchrow(query, log_id)
        return dict(row) if row else None

    @staticmethod
    async def get_recent_logs(
        conn: asyncpg.Connection,
        limit: int = 100,
        kind: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent audit logs with optional filtering.

        Args:
            conn: AsyncPG database connection
            limit: Maximum number of logs to return (default: 100)
            kind: Filter by event kind (optional)
            user_id: Filter by user ID (optional)

        Returns:
            List of log dictionaries ordered by created_at DESC (newest first)

        Example:
            >>> # Get all recent logs
            >>> recent = await AuditDAO.get_recent_logs(conn, limit=50)
            >>>
            >>> # Get recent login events
            >>> logins = await AuditDAO.get_recent_logs(
            ...     conn, limit=20, kind='user.login'
            ... )
            >>>
            >>> # Get recent events for specific user
            >>> user_events = await AuditDAO.get_recent_logs(
            ...     conn, limit=30, user_id=1
            ... )
        """
        conditions = []
        params = []
        param_count = 0

        if kind:
            param_count += 1
            conditions.append(f"kind = ${param_count}")
            params.append(kind)

        if user_id is not None:
            param_count += 1
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        param_count += 1
        limit_placeholder = f"${param_count}"
        params.append(limit)

        query = f"""
            SELECT id, kind, user_id, payload_json, created_at
            FROM audit_log
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit_placeholder}
        """

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_logs_by_kind(
        conn: asyncpg.Connection,
        kind: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs by event kind.

        Args:
            conn: AsyncPG database connection
            kind: Event kind to filter by
            limit: Maximum number of logs to return (default: 100)
            since: Only get logs created after this timestamp (optional)

        Returns:
            List of log dictionaries ordered by created_at DESC

        Example:
            >>> from datetime import datetime, timedelta
            >>> yesterday = datetime.utcnow() - timedelta(days=1)
            >>> errors = await AuditDAO.get_logs_by_kind(
            ...     conn, kind='error.occurred', limit=50, since=yesterday
            ... )
        """
        if since:
            query = """
                SELECT id, kind, user_id, payload_json, created_at
                FROM audit_log
                WHERE kind = $1 AND created_at >= $2
                ORDER BY created_at DESC
                LIMIT $3
            """
            rows = await conn.fetch(query, kind, since, limit)
        else:
            query = """
                SELECT id, kind, user_id, payload_json, created_at
                FROM audit_log
                WHERE kind = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, kind, limit)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_logs_by_user(
        conn: asyncpg.Connection,
        user_id: int,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs for a specific user.

        Args:
            conn: AsyncPG database connection
            user_id: User ID
            limit: Maximum number of logs to return (default: 100)
            since: Only get logs created after this timestamp (optional)

        Returns:
            List of log dictionaries ordered by created_at DESC

        Example:
            >>> user_logs = await AuditDAO.get_logs_by_user(conn, user_id=1, limit=50)
        """
        if since:
            query = """
                SELECT id, kind, user_id, payload_json, created_at
                FROM audit_log
                WHERE user_id = $1 AND created_at >= $2
                ORDER BY created_at DESC
                LIMIT $3
            """
            rows = await conn.fetch(query, user_id, since, limit)
        else:
            query = """
                SELECT id, kind, user_id, payload_json, created_at
                FROM audit_log
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, user_id, limit)

        return [dict(row) for row in rows]

    @staticmethod
    async def get_logs_in_timerange(
        conn: asyncpg.Connection,
        start_time: datetime,
        end_time: datetime,
        kind: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs within a specific time range.

        Args:
            conn: AsyncPG database connection
            start_time: Start of time range
            end_time: End of time range
            kind: Filter by event kind (optional)
            user_id: Filter by user ID (optional)
            limit: Maximum number of logs to return (default: 1000)

        Returns:
            List of log dictionaries ordered by created_at ASC

        Example:
            >>> from datetime import datetime, timedelta
            >>> start = datetime.utcnow() - timedelta(hours=24)
            >>> end = datetime.utcnow()
            >>> logs = await AuditDAO.get_logs_in_timerange(
            ...     conn, start, end, kind='message.received'
            ... )
        """
        conditions = ["created_at >= $1", "created_at <= $2"]
        params = [start_time, end_time]
        param_count = 2

        if kind:
            param_count += 1
            conditions.append(f"kind = ${param_count}")
            params.append(kind)

        if user_id is not None:
            param_count += 1
            conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        where_clause = " AND ".join(conditions)

        param_count += 1
        limit_placeholder = f"${param_count}"
        params.append(limit)

        query = f"""
            SELECT id, kind, user_id, payload_json, created_at
            FROM audit_log
            WHERE {where_clause}
            ORDER BY created_at ASC
            LIMIT {limit_placeholder}
        """

        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

    @staticmethod
    async def count_logs_by_kind(
        conn: asyncpg.Connection,
        kind: str,
        since: Optional[datetime] = None,
    ) -> int:
        """
        Count audit logs by event kind.

        Args:
            conn: AsyncPG database connection
            kind: Event kind
            since: Only count logs created after this timestamp (optional)

        Returns:
            Log count

        Example:
            >>> from datetime import datetime, timedelta
            >>> today = datetime.utcnow().replace(hour=0, minute=0, second=0)
            >>> error_count = await AuditDAO.count_logs_by_kind(
            ...     conn, kind='error.occurred', since=today
            ... )
            >>> print(f"Errors today: {error_count}")
        """
        if since:
            query = """
                SELECT COUNT(*) as count
                FROM audit_log
                WHERE kind = $1 AND created_at >= $2
            """
            row = await conn.fetchrow(query, kind, since)
        else:
            query = """
                SELECT COUNT(*) as count
                FROM audit_log
                WHERE kind = $1
            """
            row = await conn.fetchrow(query, kind)

        return row['count'] if row else 0

    @staticmethod
    async def delete_old_logs(
        conn: asyncpg.Connection,
        older_than_days: int = 90,
    ) -> int:
        """
        Delete audit logs older than specified days.

        Used for log rotation and database maintenance.

        Args:
            conn: AsyncPG database connection
            older_than_days: Delete logs older than this many days (default: 90)

        Returns:
            Number of logs deleted

        Example:
            >>> # Delete logs older than 90 days
            >>> deleted = await AuditDAO.delete_old_logs(conn, older_than_days=90)
            >>> print(f"Deleted {deleted} old log entries")
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

        query = "DELETE FROM audit_log WHERE created_at < $1"
        result = await conn.execute(query, cutoff_date)
        return int(result.split()[-1])

    @staticmethod
    async def get_event_statistics(
        conn: asyncpg.Connection,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get statistics of event types and their counts.

        Args:
            conn: AsyncPG database connection
            since: Only count events after this timestamp (optional)

        Returns:
            List of dictionaries with 'kind' and 'count' keys, ordered by count DESC

        Example:
            >>> from datetime import datetime, timedelta
            >>> last_week = datetime.utcnow() - timedelta(days=7)
            >>> stats = await AuditDAO.get_event_statistics(conn, since=last_week)
            >>> for stat in stats:
            ...     print(f"{stat['kind']}: {stat['count']} events")
        """
        if since:
            query = """
                SELECT kind, COUNT(*) as count
                FROM audit_log
                WHERE created_at >= $1
                GROUP BY kind
                ORDER BY count DESC
            """
            rows = await conn.fetch(query, since)
        else:
            query = """
                SELECT kind, COUNT(*) as count
                FROM audit_log
                GROUP BY kind
                ORDER BY count DESC
            """
            rows = await conn.fetch(query)

        return [dict(row) for row in rows]

    @staticmethod
    async def search_logs(
        conn: asyncpg.Connection,
        search_term: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search audit logs by payload content.

        Performs a simple text search in the payload_json field.

        Args:
            conn: AsyncPG database connection
            search_term: Term to search for in payload
            limit: Maximum number of results (default: 100)

        Returns:
            List of log dictionaries ordered by created_at DESC

        Example:
            >>> # Search for logs mentioning a specific Discord channel
            >>> logs = await AuditDAO.search_logs(conn, '9876543210', limit=50)
        """
        query = """
            SELECT id, kind, user_id, payload_json, created_at
            FROM audit_log
            WHERE payload_json ILIKE $1
            ORDER BY created_at DESC
            LIMIT $2
        """

        search_pattern = f'%{search_term}%'
        rows = await conn.fetch(query, search_pattern, limit)
        return [dict(row) for row in rows]
