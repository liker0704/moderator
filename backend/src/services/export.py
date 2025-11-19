"""
Export Service.

Provides functionality to export user data to JSON format with optional anonymization.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal

from ..database.dao.export_dao import ExportDAO
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ExportService:
    """
    Service for exporting user data with optional anonymization.

    Handles data retrieval, anonymization, and JSON file generation.
    """

    def __init__(self):
        """Initialize the export service."""
        self.logger = logger

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """
        Serialize values for JSON export.

        Handles datetime, Decimal, and other non-JSON-serializable types.

        Args:
            value: Value to serialize

        Returns:
            JSON-serializable value
        """
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif value is None:
            return None
        return value

    @staticmethod
    def _serialize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize dictionary for JSON export.

        Args:
            data: Dictionary to serialize

        Returns:
            JSON-serializable dictionary
        """
        return {key: ExportService._serialize_value(value) for key, value in data.items()}

    @staticmethod
    def _anonymize_messages(
        messages: List[Dict[str, Any]],
        anonymization_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Anonymize message data.

        Replaces usernames and channel IDs with generic identifiers.

        Args:
            messages: List of message dictionaries
            anonymization_map: Mapping of original values to anonymized values

        Returns:
            List of anonymized message dictionaries
        """
        anonymized = []
        for msg in messages:
            anonymized_msg = msg.copy()

            # Anonymize author information
            author_id = msg.get('author_id')
            if author_id and author_id not in anonymization_map:
                anonymization_map[author_id] = f"User_{len([k for k in anonymization_map.keys() if k.startswith('author_')]) + 1}"
            if author_id:
                anonymization_map[f"author_{author_id}"] = anonymization_map.get(author_id, author_id)
                anonymized_msg['author_id'] = anonymization_map[author_id]
                anonymized_msg['author_name'] = anonymization_map[author_id]

            # Anonymize channel/server IDs
            channel_id = msg.get('channel_id')
            if channel_id and channel_id not in anonymization_map:
                anonymization_map[channel_id] = f"Channel_{len([k for k in anonymization_map.keys() if k.startswith('channel_')]) + 1}"
            if channel_id:
                anonymization_map[f"channel_{channel_id}"] = anonymization_map.get(channel_id, channel_id)
                anonymized_msg['channel_id'] = anonymization_map[channel_id]

            server_id = msg.get('server_id')
            if server_id and server_id not in anonymization_map:
                anonymization_map[server_id] = f"Server_{len([k for k in anonymization_map.keys() if k.startswith('server_')]) + 1}"
            if server_id:
                anonymization_map[f"server_{server_id}"] = anonymization_map.get(server_id, server_id)
                anonymized_msg['server_id'] = anonymization_map[server_id]

            # Keep message content but remove external message ID
            anonymized_msg['ext_message_id'] = f"msg_{msg['id']}"

            anonymized.append(anonymized_msg)

        return anonymized

    @staticmethod
    def _anonymize_tasks(
        tasks: List[Dict[str, Any]],
        anonymization_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Anonymize task data.

        Args:
            tasks: List of task dictionaries
            anonymization_map: Mapping of original values to anonymized values

        Returns:
            List of anonymized task dictionaries
        """
        anonymized = []
        for task in tasks:
            anonymized_task = task.copy()

            # Anonymize author and channel info
            author_id = task.get('author_id')
            if author_id:
                anonymized_task['author_id'] = anonymization_map.get(author_id, f"User_{author_id}")
                anonymized_task['author_name'] = anonymization_map.get(author_id, f"User_{author_id}")

            channel_id = task.get('channel_id')
            if channel_id:
                anonymized_task['channel_id'] = anonymization_map.get(channel_id, f"Channel_{channel_id}")

            # Remove Telegram-specific IDs
            anonymized_task['tg_card_message_id'] = None

            anonymized.append(anonymized_task)

        return anonymized

    @staticmethod
    def _anonymize_replies(
        replies: List[Dict[str, Any]],
        anonymization_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Anonymize reply data.

        Args:
            replies: List of reply dictionaries
            anonymization_map: Mapping of original values to anonymized values

        Returns:
            List of anonymized reply dictionaries
        """
        anonymized = []
        for reply in replies:
            anonymized_reply = reply.copy()

            # Anonymize author and channel info
            author_id = reply.get('author_id')
            if author_id:
                anonymized_reply['author_id'] = anonymization_map.get(author_id, f"User_{author_id}")

            channel_id = reply.get('channel_id')
            if channel_id:
                anonymized_reply['channel_id'] = anonymization_map.get(channel_id, f"Channel_{channel_id}")

            # Remove platform-specific references
            anonymized_reply['platform_ref'] = None

            anonymized.append(anonymized_reply)

        return anonymized

    @staticmethod
    def _anonymize_allowlist(
        allowlist: List[Dict[str, Any]],
        anonymization_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Anonymize allowlist data.

        Args:
            allowlist: List of allowlist dictionaries
            anonymization_map: Mapping of original values to anonymized values

        Returns:
            List of anonymized allowlist dictionaries
        """
        anonymized = []
        for entry in allowlist:
            anonymized_entry = entry.copy()

            channel_id = entry.get('channel_id')
            if channel_id:
                anonymized_entry['channel_id'] = anonymization_map.get(channel_id, f"Channel_{channel_id}")

            server_id = entry.get('server_id')
            if server_id:
                anonymized_entry['server_id'] = anonymization_map.get(server_id, f"Server_{server_id}")

            anonymized.append(anonymized_entry)

        return anonymized

    async def export_all_data(
        self,
        conn,
        user_id: int,
        anonymize: bool = False,
        include_llm_requests: bool = False,
    ) -> Dict[str, Any]:
        """
        Export all user data to a dictionary.

        Args:
            conn: Database connection
            user_id: User ID to export data for
            anonymize: Whether to anonymize the data
            include_llm_requests: Whether to include LLM request logs

        Returns:
            Dictionary containing all exported data

        Example:
            >>> service = ExportService()
            >>> data = await service.export_all_data(conn, user_id=1, anonymize=True)
            >>> print(f"Exported {len(data['data']['messages'])} messages")
        """
        logger.info(f"Starting data export for user {user_id} (anonymize={anonymize})")

        # Retrieve all data
        messages = await ExportDAO.get_all_messages(conn, user_id)
        tasks = await ExportDAO.get_all_tasks(conn, user_id)
        replies = await ExportDAO.get_all_replies(conn, user_id)
        settings = await ExportDAO.get_all_settings(conn, user_id)
        allowlist = await ExportDAO.get_all_allowlist(conn, user_id)
        templates = await ExportDAO.get_all_templates(conn, user_id)

        llm_requests = []
        if include_llm_requests:
            llm_requests = await ExportDAO.get_all_llm_requests(conn, user_id)

        # Apply anonymization if requested
        anonymization_map = {}
        if anonymize:
            logger.info("Applying anonymization to exported data")
            messages = self._anonymize_messages(messages, anonymization_map)
            tasks = self._anonymize_tasks(tasks, anonymization_map)
            replies = self._anonymize_replies(replies, anonymization_map)
            allowlist = self._anonymize_allowlist(allowlist, anonymization_map)

        # Serialize all data
        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "user_id": user_id if not anonymize else "anonymized",
            "anonymized": anonymize,
            "counts": {
                "messages": len(messages),
                "tasks": len(tasks),
                "replies": len(replies),
                "allowlist": len(allowlist),
                "templates": len(templates),
                "llm_requests": len(llm_requests) if include_llm_requests else 0,
            },
            "data": {
                "messages": [self._serialize_dict(m) for m in messages],
                "tasks": [self._serialize_dict(t) for t in tasks],
                "replies": [self._serialize_dict(r) for r in replies],
                "settings": self._serialize_dict(settings) if settings else None,
                "allowlist": [self._serialize_dict(a) for a in allowlist],
                "templates": [self._serialize_dict(t) for t in templates],
            }
        }

        if include_llm_requests:
            export_data["data"]["llm_requests"] = [self._serialize_dict(lr) for lr in llm_requests]

        logger.info(
            f"Export completed: {len(messages)} messages, {len(tasks)} tasks, "
            f"{len(replies)} replies, {len(allowlist)} allowlist entries, "
            f"{len(templates)} templates"
        )

        return export_data

    async def create_export_file(
        self,
        conn,
        user_id: int,
        anonymize: bool = False,
        include_llm_requests: bool = False,
    ) -> Tuple[str, str]:
        """
        Create an export JSON file.

        Args:
            conn: Database connection
            user_id: User ID to export data for
            anonymize: Whether to anonymize the data
            include_llm_requests: Whether to include LLM request logs

        Returns:
            Tuple of (file_path, filename)

        Example:
            >>> service = ExportService()
            >>> file_path, filename = await service.create_export_file(conn, user_id=1)
            >>> print(f"Export file created: {file_path}")
        """
        # Get export data
        export_data = await self.export_all_data(
            conn,
            user_id,
            anonymize=anonymize,
            include_llm_requests=include_llm_requests,
        )

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        anonymize_suffix = "_anonymized" if anonymize else ""
        filename = f"moderator_export_{user_id}{anonymize_suffix}_{timestamp}.json"

        # Create temporary file
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)

        # Write JSON to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Export file created: {file_path}")

        return file_path, filename

    @staticmethod
    def cleanup_export_file(file_path: str) -> bool:
        """
        Delete an export file after it has been sent.

        Args:
            file_path: Path to the export file

        Returns:
            True if file was deleted, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up export file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup export file {file_path}: {e}")
            return False

    async def get_export_preview(
        self,
        conn,
        user_id: int,
    ) -> str:
        """
        Get a preview of what will be exported.

        Args:
            conn: Database connection
            user_id: User ID

        Returns:
            Formatted string with export statistics
        """
        stats = await ExportDAO.get_export_statistics(conn, user_id)

        preview = f"""📊 Export Preview

📨 Messages: {stats['messages']}
📋 Tasks: {stats['tasks']}
💬 Replies: {stats['replies']}
✅ Allowlist Entries: {stats['allowlist']}
📝 Templates: {stats['templates']}
🤖 LLM Requests: {stats['llm_requests']}

Use /export to export all data
Use /export anonymize to export with anonymization"""

        return preview
