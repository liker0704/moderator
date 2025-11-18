"""
Response Generation Service.

Service for generating and managing AI response variants.
Integrates LLM service with the existing message workflow to provide:
- Automatic response variant generation when tasks are created
- Caching of variants to avoid duplicate API calls
- "Soften" functionality to regenerate with gentle tone
- Variant selection and management
"""

import logging
from typing import List, Dict, Optional, Any

from database.connection import get_asyncpg_pool
from database.dao.ai_variant_dao import AIVariantDAO
from database.dao.message_dao import MessageDAO
from services.llm import get_llm_service
from services.context import get_context_by_channel

logger = logging.getLogger(__name__)


class ResponseGenerationService:
    """
    Service for AI response generation and management.

    This service integrates the LLM service with the message workflow
    to provide automated response variant generation for moderator tasks.
    """

    @staticmethod
    async def generate_variants_for_task(
        task_id: int,
        message_id: int,
        num_variants: int = 2,
        tone: Optional[str] = None,
        force_regenerate: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate AI response variants for a task.

        This method will:
        1. Check if variants already exist (unless force_regenerate=True)
        2. Get message and context from database
        3. Generate variants using LLM service
        4. Store variants in database
        5. Return the stored variants

        Args:
            task_id: ID of the task
            message_id: ID of the source message
            num_variants: Number of variants to generate (default: 2)
            tone: Optional tone ('soft', 'formal', None for default)
            force_regenerate: Force regeneration even if variants exist (default: False)

        Returns:
            List of variant dicts with keys:
                - id: Variant database ID
                - task_id: Task ID
                - variant_text: Generated response text
                - confidence_score: Confidence score (0.0 - 1.0)
                - provider: LLM provider ('openai' or 'anthropic')
                - model: Model identifier
                - tone: Tone modifier
                - selected: Whether this variant is selected
                - created_at: Creation timestamp

        Example:
            >>> variants = await ResponseGenerationService.generate_variants_for_task(
            ...     task_id=123,
            ...     message_id=456,
            ...     num_variants=2,
            ...     tone=None
            ... )
            >>> for variant in variants:
            ...     print(f"Option {variant['id']}: {variant['variant_text'][:50]}...")
        """
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            # Check if variants already exist (caching logic)
            if not force_regenerate:
                existing_variants = await AIVariantDAO.get_variants_for_task(conn, task_id)
                if existing_variants:
                    logger.info(
                        f"Returning {len(existing_variants)} cached variants for task {task_id}",
                        extra={"task_id": task_id, "count": len(existing_variants)}
                    )
                    return existing_variants

            # Delete old variants if regenerating
            if force_regenerate:
                deleted_count = await AIVariantDAO.delete_variants_for_task(conn, task_id)
                logger.info(
                    f"Deleted {deleted_count} old variants for task {task_id} (regenerating)",
                    extra={"task_id": task_id, "deleted_count": deleted_count}
                )

            # Get message and context
            message = await MessageDAO.get_message_by_id(conn, message_id)
            if not message:
                logger.error(
                    f"Message {message_id} not found",
                    extra={"message_id": message_id, "task_id": task_id}
                )
                return []

            message_dict = dict(message)

            # Get context messages
            try:
                context_messages = await get_context_by_channel(
                    conn,
                    platform=message_dict['platform'],
                    channel_id=message_dict['channel_id'],
                    server_id=message_dict.get('server_id'),
                    thread_id=message_dict.get('thread_id'),
                    before_message_id=message_id,
                    limit=10
                )

                # Convert Message objects to dicts
                context_dicts = []
                for ctx_msg in context_messages:
                    if hasattr(ctx_msg, '__dict__'):
                        context_dicts.append(vars(ctx_msg))
                    else:
                        context_dicts.append(dict(ctx_msg))

                logger.debug(
                    f"Retrieved {len(context_dicts)} context messages for task {task_id}",
                    extra={"task_id": task_id, "context_count": len(context_dicts)}
                )

            except Exception as e:
                logger.warning(
                    f"Failed to retrieve context for task {task_id}: {e}",
                    extra={"task_id": task_id},
                    exc_info=True
                )
                context_dicts = []

            # Generate variants using LLM
            try:
                llm_service = get_llm_service()
                variants = await llm_service.generate_response_variants(
                    message=message_dict,
                    context_messages=context_dicts,
                    num_variants=num_variants,
                    tone=tone
                )

                if not variants:
                    logger.warning(
                        f"LLM service returned no variants for task {task_id}",
                        extra={"task_id": task_id}
                    )
                    return []

                # Store variants in database
                stored_variants = []
                for variant in variants:
                    variant_id = await AIVariantDAO.create_variant(
                        conn,
                        task_id=task_id,
                        variant_text=variant['text'],
                        confidence_score=variant['confidence'],
                        provider=variant['provider'],
                        model=variant['model'],
                        tone=tone
                    )

                    stored_variants.append({
                        'id': variant_id,
                        'task_id': task_id,
                        'variant_text': variant['text'],
                        'confidence_score': variant['confidence'],
                        'provider': variant['provider'],
                        'model': variant['model'],
                        'tone': tone,
                        'selected': False,
                        'created_at': None  # Will be set by database
                    })

                logger.info(
                    f"Generated and stored {len(stored_variants)} variants for task {task_id}",
                    extra={
                        "task_id": task_id,
                        "count": len(stored_variants),
                        "provider": variants[0]['provider'] if variants else None,
                        "tone": tone
                    }
                )

                return stored_variants

            except Exception as e:
                logger.error(
                    f"Failed to generate variants for task {task_id}: {e}",
                    extra={"task_id": task_id},
                    exc_info=True
                )
                return []

    @staticmethod
    async def soften_response(task_id: int, message_id: int) -> List[Dict[str, Any]]:
        """
        Regenerate response variants with 'soft' tone.

        This is a convenience function for the "Soften" button in the UI.
        It forces regeneration of variants with a gentle, empathetic tone.

        Args:
            task_id: ID of the task
            message_id: ID of the source message

        Returns:
            List of new variant dicts with soft tone

        Example:
            >>> soft_variants = await ResponseGenerationService.soften_response(
            ...     task_id=123,
            ...     message_id=456
            ... )
            >>> # Returns 2 new variants with gentle tone
        """
        logger.info(
            f"Softening response for task {task_id}",
            extra={"task_id": task_id, "action": "soften"}
        )

        return await ResponseGenerationService.generate_variants_for_task(
            task_id=task_id,
            message_id=message_id,
            num_variants=2,
            tone='soft',
            force_regenerate=True
        )

    @staticmethod
    async def regenerate_response(
        task_id: int,
        message_id: int,
        num_variants: int = 2,
        tone: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Regenerate response variants.

        Similar to generate_variants_for_task with force_regenerate=True,
        but provides a clearer API for explicit regeneration requests.

        Args:
            task_id: ID of the task
            message_id: ID of the source message
            num_variants: Number of variants to generate (default: 2)
            tone: Optional tone ('soft', 'formal', None)

        Returns:
            List of new variant dicts

        Example:
            >>> new_variants = await ResponseGenerationService.regenerate_response(
            ...     task_id=123,
            ...     message_id=456,
            ...     num_variants=3,
            ...     tone='formal'
            ... )
        """
        logger.info(
            f"Regenerating response for task {task_id}",
            extra={"task_id": task_id, "num_variants": num_variants, "tone": tone}
        )

        return await ResponseGenerationService.generate_variants_for_task(
            task_id=task_id,
            message_id=message_id,
            num_variants=num_variants,
            tone=tone,
            force_regenerate=True
        )

    @staticmethod
    async def get_variants(task_id: int) -> List[Dict[str, Any]]:
        """
        Get all variants for a task.

        Retrieves cached variants from the database without generating new ones.

        Args:
            task_id: ID of the task

        Returns:
            List of variant dicts

        Example:
            >>> variants = await ResponseGenerationService.get_variants(task_id=123)
            >>> if variants:
            ...     print(f"Found {len(variants)} cached variants")
        """
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            variants = await AIVariantDAO.get_variants_for_task(conn, task_id)

            logger.debug(
                f"Retrieved {len(variants)} variants for task {task_id}",
                extra={"task_id": task_id, "count": len(variants)}
            )

            return variants

    @staticmethod
    async def select_variant(variant_id: int) -> bool:
        """
        Mark a variant as selected.

        Args:
            variant_id: ID of the variant to select

        Returns:
            bool: True if selection succeeded, False otherwise

        Example:
            >>> success = await ResponseGenerationService.select_variant(variant_id=789)
            >>> if success:
            ...     print("Variant selected successfully")
        """
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            success = await AIVariantDAO.mark_variant_selected(conn, variant_id)

            if success:
                logger.info(
                    f"Selected variant {variant_id}",
                    extra={"variant_id": variant_id}
                )
            else:
                logger.warning(
                    f"Failed to select variant {variant_id}",
                    extra={"variant_id": variant_id}
                )

            return success

    @staticmethod
    async def get_selected_variant(task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the selected variant for a task.

        Args:
            task_id: ID of the task

        Returns:
            Selected variant dict or None if no variant is selected

        Example:
            >>> variant = await ResponseGenerationService.get_selected_variant(task_id=123)
            >>> if variant:
            ...     print(f"Selected: {variant['variant_text']}")
        """
        db_pool = get_asyncpg_pool()

        async with db_pool.acquire() as conn:
            variant = await AIVariantDAO.get_selected_variant_for_task(conn, task_id)

            if variant:
                logger.debug(
                    f"Found selected variant {variant['id']} for task {task_id}",
                    extra={"task_id": task_id, "variant_id": variant['id']}
                )

            return variant


# Singleton
_response_gen_service: Optional[ResponseGenerationService] = None


def get_response_generation_service() -> ResponseGenerationService:
    """
    Get response generation service singleton.

    Returns:
        ResponseGenerationService: Singleton instance

    Example:
        >>> service = get_response_generation_service()
        >>> variants = await service.generate_variants_for_task(task_id=123, message_id=456)
    """
    global _response_gen_service
    if _response_gen_service is None:
        _response_gen_service = ResponseGenerationService()
    return _response_gen_service


def reset_response_generation_service() -> None:
    """
    Reset the response generation service singleton.

    Useful for testing or configuration changes.
    """
    global _response_gen_service
    _response_gen_service = None


# Export public API
__all__ = [
    "ResponseGenerationService",
    "get_response_generation_service",
    "reset_response_generation_service"
]
