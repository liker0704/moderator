"""
AI Response Variant Data Access Object.

Provides async database operations for ai_response_variants table using asyncpg.
Handles creation, retrieval, selection, and deletion of AI-generated response variants.
"""

import logging
from typing import List, Dict, Optional, Any
import asyncpg

logger = logging.getLogger(__name__)


class AIVariantDAO:
    """
    Data Access Object for AI response variants table.

    All methods are async and use asyncpg connections for high-performance
    database operations.
    """

    @staticmethod
    async def create_variant(
        conn: asyncpg.Connection,
        task_id: int,
        variant_text: str,
        confidence_score: float,
        provider: str,
        model: str,
        tone: Optional[str] = None
    ) -> int:
        """
        Create AI response variant.

        Args:
            conn: AsyncPG database connection
            task_id: ID of the task this variant belongs to
            variant_text: Generated response text
            confidence_score: Confidence score (0.0 - 1.0)
            provider: LLM provider ('openai' or 'anthropic')
            model: Model identifier (e.g., 'gpt-4-turbo', 'claude-3-opus')
            tone: Optional tone modifier ('soft', 'formal', None)

        Returns:
            int: ID of the created variant

        Raises:
            asyncpg.PostgresError: On database errors

        Example:
            >>> variant_id = await AIVariantDAO.create_variant(
            ...     conn=conn,
            ...     task_id=123,
            ...     variant_text="Thanks for reaching out!",
            ...     confidence_score=0.9,
            ...     provider="openai",
            ...     model="gpt-4-turbo",
            ...     tone=None
            ... )
        """
        query = """
            INSERT INTO ai_response_variants
            (task_id, variant_text, confidence_score, provider, model, tone)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        row = await conn.fetchrow(
            query, task_id, variant_text, confidence_score, provider, model, tone
        )

        variant_id = row['id']
        logger.debug(
            f"Created AI variant {variant_id} for task {task_id}",
            extra={"task_id": task_id, "variant_id": variant_id, "provider": provider}
        )
        return variant_id

    @staticmethod
    async def get_variants_for_task(
        conn: asyncpg.Connection,
        task_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all AI variants for a task.

        Variants are ordered by confidence score (descending), then by creation time (ascending).

        Args:
            conn: AsyncPG database connection
            task_id: ID of the task

        Returns:
            List of variant dictionaries

        Example:
            >>> variants = await AIVariantDAO.get_variants_for_task(conn, 123)
            >>> for variant in variants:
            ...     print(f"Variant {variant['id']}: {variant['variant_text'][:50]}...")
        """
        query = """
            SELECT
                id, task_id, variant_text, confidence_score,
                provider, model, tone, selected, created_at
            FROM ai_response_variants
            WHERE task_id = $1
            ORDER BY confidence_score DESC, created_at ASC
        """

        rows = await conn.fetch(query, task_id)
        variants = [dict(row) for row in rows]

        logger.debug(
            f"Retrieved {len(variants)} AI variants for task {task_id}",
            extra={"task_id": task_id, "count": len(variants)}
        )

        return variants

    @staticmethod
    async def get_variant_by_id(
        conn: asyncpg.Connection,
        variant_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific AI variant by ID.

        Args:
            conn: AsyncPG database connection
            variant_id: ID of the variant

        Returns:
            Variant dictionary or None if not found

        Example:
            >>> variant = await AIVariantDAO.get_variant_by_id(conn, 456)
            >>> if variant:
            ...     print(f"Confidence: {variant['confidence_score']}")
        """
        query = """
            SELECT
                id, task_id, variant_text, confidence_score,
                provider, model, tone, selected, created_at
            FROM ai_response_variants
            WHERE id = $1
        """

        row = await conn.fetchrow(query, variant_id)
        return dict(row) if row else None

    @staticmethod
    async def mark_variant_selected(
        conn: asyncpg.Connection,
        variant_id: int
    ) -> bool:
        """
        Mark a variant as selected.

        This sets the 'selected' flag to TRUE for the specified variant.

        Args:
            conn: AsyncPG database connection
            variant_id: ID of the variant to mark as selected

        Returns:
            bool: True if the update succeeded, False otherwise

        Example:
            >>> success = await AIVariantDAO.mark_variant_selected(conn, 456)
            >>> if success:
            ...     print("Variant marked as selected")
        """
        query = """
            UPDATE ai_response_variants
            SET selected = TRUE
            WHERE id = $1
        """

        result = await conn.execute(query, variant_id)
        success = result == "UPDATE 1"

        if success:
            logger.debug(
                f"Marked AI variant {variant_id} as selected",
                extra={"variant_id": variant_id}
            )

        return success

    @staticmethod
    async def unmark_all_selected_for_task(
        conn: asyncpg.Connection,
        task_id: int
    ) -> int:
        """
        Unmark all selected variants for a task.

        This sets the 'selected' flag to FALSE for all variants of the task.
        Useful when regenerating variants or allowing re-selection.

        Args:
            conn: AsyncPG database connection
            task_id: ID of the task

        Returns:
            int: Number of variants unmarked

        Example:
            >>> count = await AIVariantDAO.unmark_all_selected_for_task(conn, 123)
            >>> print(f"Unmarked {count} variants")
        """
        query = """
            UPDATE ai_response_variants
            SET selected = FALSE
            WHERE task_id = $1 AND selected = TRUE
        """

        result = await conn.execute(query, task_id)

        # Extract count from result string "UPDATE N"
        count = int(result.split()[-1]) if result and ' ' in result else 0

        logger.debug(
            f"Unmarked {count} selected AI variants for task {task_id}",
            extra={"task_id": task_id, "count": count}
        )

        return count

    @staticmethod
    async def get_selected_variant_for_task(
        conn: asyncpg.Connection,
        task_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the selected variant for a task.

        Args:
            conn: AsyncPG database connection
            task_id: ID of the task

        Returns:
            Selected variant dictionary or None if no variant is selected

        Example:
            >>> variant = await AIVariantDAO.get_selected_variant_for_task(conn, 123)
            >>> if variant:
            ...     print(f"Selected: {variant['variant_text']}")
        """
        query = """
            SELECT
                id, task_id, variant_text, confidence_score,
                provider, model, tone, selected, created_at
            FROM ai_response_variants
            WHERE task_id = $1 AND selected = TRUE
            LIMIT 1
        """

        row = await conn.fetchrow(query, task_id)
        return dict(row) if row else None

    @staticmethod
    async def delete_variants_for_task(
        conn: asyncpg.Connection,
        task_id: int
    ) -> int:
        """
        Delete all variants for a task.

        This is useful when regenerating variants or cleaning up.

        Args:
            conn: AsyncPG database connection
            task_id: ID of the task

        Returns:
            int: Number of variants deleted

        Example:
            >>> count = await AIVariantDAO.delete_variants_for_task(conn, 123)
            >>> print(f"Deleted {count} variants")
        """
        query = "DELETE FROM ai_response_variants WHERE task_id = $1"
        result = await conn.execute(query, task_id)

        # Extract count from result string "DELETE N"
        count = int(result.split()[-1]) if result and ' ' in result else 0

        logger.debug(
            f"Deleted {count} AI variants for task {task_id}",
            extra={"task_id": task_id, "count": count}
        )

        return count

    @staticmethod
    async def delete_variant(
        conn: asyncpg.Connection,
        variant_id: int
    ) -> bool:
        """
        Delete a specific variant.

        Args:
            conn: AsyncPG database connection
            variant_id: ID of the variant to delete

        Returns:
            bool: True if deletion succeeded, False otherwise

        Example:
            >>> success = await AIVariantDAO.delete_variant(conn, 456)
            >>> if success:
            ...     print("Variant deleted")
        """
        query = "DELETE FROM ai_response_variants WHERE id = $1"
        result = await conn.execute(query, variant_id)
        success = result == "DELETE 1"

        if success:
            logger.debug(
                f"Deleted AI variant {variant_id}",
                extra={"variant_id": variant_id}
            )

        return success

    @staticmethod
    async def count_variants_for_task(
        conn: asyncpg.Connection,
        task_id: int
    ) -> int:
        """
        Count the number of variants for a task.

        Args:
            conn: AsyncPG database connection
            task_id: ID of the task

        Returns:
            int: Number of variants for the task

        Example:
            >>> count = await AIVariantDAO.count_variants_for_task(conn, 123)
            >>> print(f"Task has {count} variants")
        """
        query = """
            SELECT COUNT(*) as count
            FROM ai_response_variants
            WHERE task_id = $1
        """

        row = await conn.fetchrow(query, task_id)
        return row['count'] if row else 0
