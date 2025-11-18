"""
Reply editing service.

Handles the complete edit workflow including:
- Permission validation
- Edit history tracking
- Platform posting
- Audit logging
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncpg

from utils.logger import get_logger

logger = get_logger(__name__)


class ReplyEditorService:
    """Service for managing reply edits."""

    @staticmethod
    async def validate_edit_permission(
        conn: asyncpg.Connection,
        reply_id: int,
        user_id: int,
        time_limit_hours: int = 48
    ) -> Dict[str, Any]:
        """
        Check all edit preconditions.

        Validates:
        1. Reply exists and is posted
        2. User owns the task
        3. Reply was posted within time limit (default 48 hours)
        4. Task is not muted

        Args:
            conn: DB connection
            reply_id: Reply to check
            user_id: User attempting edit
            time_limit_hours: Maximum hours since posting (default: 48)

        Returns:
            {
                'can_edit': bool,
                'reason': str (if can_edit=False),
                'reply': Dict[str, Any] (if can_edit=True),
                'task': Dict[str, Any] (if can_edit=True)
            }
        """
        from database.dao.reply_dao import ReplyDAO
        from database.dao.task_dao import TaskDAO

        # 1. Get reply
        reply = await ReplyDAO.get_reply_by_id(conn, reply_id)
        if not reply:
            logger.warning(
                f"Edit permission denied: reply {reply_id} not found",
                extra={"reply_id": reply_id, "user_id": user_id}
            )
            return {
                'can_edit': False,
                'reason': 'Reply not found'
            }

        # 2. Check if reply was posted
        if not reply['posted_at']:
            logger.warning(
                f"Edit permission denied: reply {reply_id} not yet posted",
                extra={"reply_id": reply_id, "user_id": user_id}
            )
            return {
                'can_edit': False,
                'reason': 'Reply has not been posted yet'
            }

        # 3. Get task and check ownership
        task = await TaskDAO.get_task_by_id(conn, reply['task_id'])
        if not task:
            logger.error(
                f"Edit permission denied: task {reply['task_id']} not found for reply {reply_id}",
                extra={"reply_id": reply_id, "task_id": reply['task_id'], "user_id": user_id}
            )
            return {
                'can_edit': False,
                'reason': 'Associated task not found'
            }

        if task['assignee_user_id'] != user_id:
            logger.warning(
                f"Edit permission denied: user {user_id} does not own task {task['id']}",
                extra={
                    "reply_id": reply_id,
                    "task_id": task['id'],
                    "user_id": user_id,
                    "assignee_user_id": task['assignee_user_id']
                }
            )
            return {
                'can_edit': False,
                'reason': 'You do not have permission to edit this reply'
            }

        # 4. Check task status
        if task['status'] == 'muted':
            logger.warning(
                f"Edit permission denied: task {task['id']} is muted",
                extra={"reply_id": reply_id, "task_id": task['id'], "user_id": user_id}
            )
            return {
                'can_edit': False,
                'reason': 'Cannot edit reply for muted task'
            }

        # 5. Check time limit
        cutoff_time = datetime.utcnow() - timedelta(hours=time_limit_hours)
        if reply['posted_at'] < cutoff_time:
            hours_ago = (datetime.utcnow() - reply['posted_at']).total_seconds() / 3600
            logger.warning(
                f"Edit permission denied: reply {reply_id} posted {hours_ago:.1f} hours ago (limit: {time_limit_hours}h)",
                extra={
                    "reply_id": reply_id,
                    "user_id": user_id,
                    "hours_ago": hours_ago,
                    "time_limit_hours": time_limit_hours
                }
            )
            return {
                'can_edit': False,
                'reason': f'Reply can only be edited within {time_limit_hours} hours of posting'
            }

        # All checks passed
        logger.info(
            f"Edit permission granted for reply {reply_id}",
            extra={"reply_id": reply_id, "user_id": user_id, "task_id": task['id']}
        )
        return {
            'can_edit': True,
            'reply': reply,
            'task': task
        }

    @staticmethod
    async def create_edited_reply(
        conn: asyncpg.Connection,
        original_reply_id: int,
        new_content: str,
        user_id: int
    ) -> int:
        """
        Create a new reply record that represents an edit of the original.

        The new reply will have:
        - Same task_id as original
        - Same generated_by as original
        - edit_of pointing to original reply
        - confirmed = True (edits are implicitly confirmed)

        Args:
            conn: DB connection
            original_reply_id: Reply being edited
            new_content: New content
            user_id: User making the edit

        Returns:
            int: ID of the newly created reply
        """
        from database.dao.reply_dao import ReplyDAO

        # Get original reply to copy metadata
        original = await ReplyDAO.get_reply_by_id(conn, original_reply_id)
        if not original:
            raise ValueError(f"Original reply {original_reply_id} not found")

        # Create new reply as an edit
        new_reply_id = await ReplyDAO.create_reply(
            conn,
            task_id=original['task_id'],
            content=new_content,
            generated_by=original['generated_by'],
            llm_confidence=original.get('llm_confidence'),
            edit_of=original_reply_id
        )

        # Mark as confirmed (edits are implicitly confirmed)
        await ReplyDAO.mark_reply_confirmed(conn, new_reply_id)

        logger.info(
            f"Created edited reply {new_reply_id} for original {original_reply_id}",
            extra={
                "new_reply_id": new_reply_id,
                "original_reply_id": original_reply_id,
                "user_id": user_id,
                "task_id": original['task_id']
            }
        )

        return new_reply_id

    @staticmethod
    async def edit_reply(
        conn: asyncpg.Connection,
        original_reply_id: int,
        new_content: str,
        user_id: int,
        telegram_poster: Optional[Any] = None,
        discord_poster: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Complete edit workflow.

        Steps:
        1. Validate permission
        2. Create edited reply in DB
        3. Post to platform via poster
        4. Update platform_ref on new reply
        5. Final audit log

        Args:
            conn: DB connection
            original_reply_id: Reply to edit
            new_content: New text
            user_id: User editing
            telegram_poster: Telegram poster instance (optional)
            discord_poster: Discord poster instance (optional)

        Returns:
            {
                'success': bool,
                'new_reply_id': int (if success),
                'platform': str (discord/telegram),
                'error': str (if failed),
                'error_code': str (if failed)
            }

        Error codes:
        - 'validation_failed': Permission check failed
        - 'post_failed': Platform posting failed
        - 'db_error': Database error
        - 'no_poster': Required poster not provided
        """
        from database.dao.reply_dao import ReplyDAO
        from database.dao.audit_dao import AuditDAO

        try:
            # 1. Validate permission
            validation = await ReplyEditorService.validate_edit_permission(
                conn, original_reply_id, user_id
            )

            if not validation['can_edit']:
                # Audit log: edit permission denied
                await AuditDAO.log_event(
                    conn,
                    kind='reply.edit_denied',
                    payload_json=json.dumps({
                        'reply_id': original_reply_id,
                        'user_id': user_id,
                        'reason': validation['reason']
                    }),
                    user_id=user_id
                )

                return {
                    'success': False,
                    'error': validation['reason'],
                    'error_code': 'validation_failed'
                }

            original = validation['reply']
            task = validation['task']

            # 2. Parse platform info from original reply
            platform_data = {}
            if original.get('platform_ref'):
                try:
                    platform_data = json.loads(original['platform_ref'])
                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to parse platform_ref for reply {original_reply_id}",
                        extra={"reply_id": original_reply_id, "platform_ref": original.get('platform_ref')}
                    )

            platform = platform_data.get('platform', 'telegram')

            # Audit log: edit attempt started
            await AuditDAO.log_event(
                conn,
                kind='reply.edit_started',
                payload_json=json.dumps({
                    'reply_id': original_reply_id,
                    'user_id': user_id,
                    'task_id': task['id'],
                    'platform': platform,
                    'content_length': len(new_content)
                }),
                user_id=user_id
            )

            # 3. Create edited reply in DB
            new_reply_id = await ReplyEditorService.create_edited_reply(
                conn, original_reply_id, new_content, user_id
            )

            # 4. Post to platform
            post_result = None
            try:
                if platform == 'discord':
                    if not discord_poster:
                        logger.error(
                            f"Discord poster not provided for editing reply {original_reply_id}",
                            extra={"reply_id": original_reply_id, "platform": platform}
                        )
                        await AuditDAO.log_event(
                            conn,
                            kind='reply.edit_failed',
                            payload_json=json.dumps({
                                'reply_id': original_reply_id,
                                'new_reply_id': new_reply_id,
                                'user_id': user_id,
                                'error': 'Discord poster not provided',
                                'error_code': 'no_poster'
                            }),
                            user_id=user_id
                        )
                        return {
                            'success': False,
                            'error': 'Discord poster not available',
                            'error_code': 'no_poster',
                            'new_reply_id': new_reply_id
                        }

                    channel_id = platform_data.get('channel_id')
                    message_id = platform_data.get('message_id')

                    if not channel_id or not message_id:
                        logger.error(
                            f"Missing channel_id or message_id in platform_ref for reply {original_reply_id}",
                            extra={"reply_id": original_reply_id, "platform_data": platform_data}
                        )
                        await AuditDAO.log_event(
                            conn,
                            kind='reply.edit_failed',
                            payload_json=json.dumps({
                                'reply_id': original_reply_id,
                                'new_reply_id': new_reply_id,
                                'user_id': user_id,
                                'error': 'Missing platform reference data',
                                'error_code': 'invalid_platform_ref'
                            }),
                            user_id=user_id
                        )
                        return {
                            'success': False,
                            'error': 'Invalid platform reference data',
                            'error_code': 'invalid_platform_ref',
                            'new_reply_id': new_reply_id
                        }

                    logger.info(
                        f"Editing Discord message {message_id} in channel {channel_id}",
                        extra={
                            "reply_id": original_reply_id,
                            "new_reply_id": new_reply_id,
                            "channel_id": channel_id,
                            "message_id": message_id
                        }
                    )

                    post_result = await discord_poster.edit_message(
                        channel_id=channel_id,
                        message_id=message_id,
                        content=new_content
                    )

                elif platform == 'telegram':
                    if not telegram_poster:
                        logger.error(
                            f"Telegram poster not provided for editing reply {original_reply_id}",
                            extra={"reply_id": original_reply_id, "platform": platform}
                        )
                        await AuditDAO.log_event(
                            conn,
                            kind='reply.edit_failed',
                            payload_json=json.dumps({
                                'reply_id': original_reply_id,
                                'new_reply_id': new_reply_id,
                                'user_id': user_id,
                                'error': 'Telegram poster not provided',
                                'error_code': 'no_poster'
                            }),
                            user_id=user_id
                        )
                        return {
                            'success': False,
                            'error': 'Telegram poster not available',
                            'error_code': 'no_poster',
                            'new_reply_id': new_reply_id
                        }

                    chat_id = platform_data.get('chat_id')
                    message_id = platform_data.get('message_id')

                    if not chat_id or not message_id:
                        logger.error(
                            f"Missing chat_id or message_id in platform_ref for reply {original_reply_id}",
                            extra={"reply_id": original_reply_id, "platform_data": platform_data}
                        )
                        await AuditDAO.log_event(
                            conn,
                            kind='reply.edit_failed',
                            payload_json=json.dumps({
                                'reply_id': original_reply_id,
                                'new_reply_id': new_reply_id,
                                'user_id': user_id,
                                'error': 'Missing platform reference data',
                                'error_code': 'invalid_platform_ref'
                            }),
                            user_id=user_id
                        )
                        return {
                            'success': False,
                            'error': 'Invalid platform reference data',
                            'error_code': 'invalid_platform_ref',
                            'new_reply_id': new_reply_id
                        }

                    logger.info(
                        f"Editing Telegram message {message_id} in chat {chat_id}",
                        extra={
                            "reply_id": original_reply_id,
                            "new_reply_id": new_reply_id,
                            "chat_id": chat_id,
                            "message_id": message_id
                        }
                    )

                    post_result = await telegram_poster.edit_message(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                        text=new_content
                    )

                else:
                    logger.error(
                        f"Unknown platform '{platform}' for reply {original_reply_id}",
                        extra={"reply_id": original_reply_id, "platform": platform}
                    )
                    await AuditDAO.log_event(
                        conn,
                        kind='reply.edit_failed',
                        payload_json=json.dumps({
                            'reply_id': original_reply_id,
                            'new_reply_id': new_reply_id,
                            'user_id': user_id,
                            'error': f'Unknown platform: {platform}',
                            'error_code': 'unknown_platform'
                        }),
                        user_id=user_id
                    )
                    return {
                        'success': False,
                        'error': f'Unknown platform: {platform}',
                        'error_code': 'unknown_platform',
                        'new_reply_id': new_reply_id
                    }

            except Exception as e:
                logger.error(
                    f"Failed to post edited reply to {platform}: {str(e)}",
                    extra={
                        "reply_id": original_reply_id,
                        "new_reply_id": new_reply_id,
                        "platform": platform
                    },
                    exc_info=True
                )

                await AuditDAO.log_event(
                    conn,
                    kind='reply.edit_failed',
                    payload_json=json.dumps({
                        'reply_id': original_reply_id,
                        'new_reply_id': new_reply_id,
                        'user_id': user_id,
                        'platform': platform,
                        'error': str(e),
                        'error_code': 'post_exception'
                    }),
                    user_id=user_id
                )

                return {
                    'success': False,
                    'error': f'Failed to post to {platform}: {str(e)}',
                    'error_code': 'post_failed',
                    'new_reply_id': new_reply_id
                }

            # 5. Check post result
            if not post_result or not post_result.get('success'):
                error_msg = post_result.get('error', 'Unknown error') if post_result else 'No response from poster'
                error_code = post_result.get('error_code', 0) if post_result else 0

                logger.error(
                    f"Platform edit failed for reply {original_reply_id}: {error_msg}",
                    extra={
                        "reply_id": original_reply_id,
                        "new_reply_id": new_reply_id,
                        "platform": platform,
                        "error": error_msg,
                        "error_code": error_code
                    }
                )

                await AuditDAO.log_event(
                    conn,
                    kind='reply.edit_failed',
                    payload_json=json.dumps({
                        'reply_id': original_reply_id,
                        'new_reply_id': new_reply_id,
                        'user_id': user_id,
                        'platform': platform,
                        'error': error_msg,
                        'platform_error_code': error_code,
                        'error_code': 'platform_error'
                    }),
                    user_id=user_id
                )

                return {
                    'success': False,
                    'error': error_msg,
                    'error_code': 'post_failed',
                    'new_reply_id': new_reply_id
                }

            # 6. Update new reply with platform_ref (reuse original platform data)
            await ReplyDAO.mark_reply_posted(
                conn,
                reply_id=new_reply_id,
                platform_ref=original.get('platform_ref', '{}')
            )

            # 7. Final audit log: success
            await AuditDAO.log_event(
                conn,
                kind='reply.edited',
                payload_json=json.dumps({
                    'reply_id': original_reply_id,
                    'new_reply_id': new_reply_id,
                    'user_id': user_id,
                    'task_id': task['id'],
                    'platform': platform,
                    'content_length': len(new_content)
                }),
                user_id=user_id
            )

            logger.info(
                f"Successfully edited reply {original_reply_id} -> {new_reply_id} on {platform}",
                extra={
                    "original_reply_id": original_reply_id,
                    "new_reply_id": new_reply_id,
                    "user_id": user_id,
                    "platform": platform,
                    "task_id": task['id']
                }
            )

            return {
                'success': True,
                'new_reply_id': new_reply_id,
                'platform': platform
            }

        except Exception as e:
            logger.error(
                f"Unexpected error editing reply {original_reply_id}: {str(e)}",
                extra={"reply_id": original_reply_id, "user_id": user_id},
                exc_info=True
            )

            try:
                await AuditDAO.log_event(
                    conn,
                    kind='reply.edit_failed',
                    payload_json=json.dumps({
                        'reply_id': original_reply_id,
                        'user_id': user_id,
                        'error': str(e),
                        'error_code': 'db_error'
                    }),
                    user_id=user_id
                )
            except Exception as audit_error:
                logger.error(
                    f"Failed to log audit event: {str(audit_error)}",
                    exc_info=True
                )

            return {
                'success': False,
                'error': f'Database error: {str(e)}',
                'error_code': 'db_error'
            }

    @staticmethod
    async def get_edit_history(
        conn: asyncpg.Connection,
        reply_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get formatted edit history for display.

        Uses recursive CTE from ReplyDAO.get_reply_history().
        Returns the full edit chain starting from the original reply.

        Args:
            conn: DB connection
            reply_id: Any reply ID in the edit chain (will find original)

        Returns:
            [
                {
                    'id': int,
                    'content': str (truncated to 100 chars),
                    'content_preview': str (first 50 chars),
                    'full_content': str,
                    'created_at': datetime,
                    'is_current': bool,
                    'is_original': bool,
                    'generated_by': str,
                    'confirmed': bool,
                    'posted_at': datetime
                },
                ...
            ]
        Sorted: newest first

        Example:
            >>> history = await ReplyEditorService.get_edit_history(conn, reply_id=123)
            >>> for item in history:
            ...     status = "CURRENT" if item['is_current'] else "ORIGINAL" if item['is_original'] else "EDIT"
            ...     print(f"[{status}] {item['created_at']}: {item['content_preview']}")
        """
        from database.dao.reply_dao import ReplyDAO

        # First, find the original reply (root of the edit chain)
        reply = await ReplyDAO.get_reply_by_id(conn, reply_id)
        if not reply:
            logger.warning(
                f"Reply {reply_id} not found for edit history",
                extra={"reply_id": reply_id}
            )
            return []

        # If this reply has edit_of, trace back to original
        original_reply_id = reply_id
        if reply.get('edit_of'):
            # Walk back to find original
            current = reply
            while current.get('edit_of'):
                original_reply_id = current['edit_of']
                current = await ReplyDAO.get_reply_by_id(conn, original_reply_id)
                if not current:
                    # Broken chain, use what we have
                    logger.warning(
                        f"Broken edit chain at reply {original_reply_id}",
                        extra={"reply_id": reply_id, "broken_at": original_reply_id}
                    )
                    break

        # Get full history from original
        history = await ReplyDAO.get_reply_history(conn, original_reply_id)

        if not history:
            logger.warning(
                f"No edit history found for reply {original_reply_id}",
                extra={"original_reply_id": original_reply_id, "requested_reply_id": reply_id}
            )
            return []

        # Format for display (newest first)
        formatted = []
        for idx, reply_record in enumerate(reversed(history)):
            content = reply_record['content']

            formatted.append({
                'id': reply_record['id'],
                'content': content[:100] + ('...' if len(content) > 100 else ''),
                'content_preview': content[:50] + ('...' if len(content) > 50 else ''),
                'full_content': content,
                'created_at': reply_record['created_at'],
                'is_current': idx == 0,  # First (newest) is current
                'is_original': reply_record['edit_of'] is None,
                'generated_by': reply_record['generated_by'],
                'confirmed': reply_record['confirmed'],
                'posted_at': reply_record.get('posted_at')
            })

        logger.debug(
            f"Retrieved {len(formatted)} versions in edit history for reply {reply_id}",
            extra={
                "reply_id": reply_id,
                "original_reply_id": original_reply_id,
                "version_count": len(formatted)
            }
        )

        return formatted


# Export public API
__all__ = [
    'ReplyEditorService'
]
