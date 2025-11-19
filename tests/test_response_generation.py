"""Tests for response generation service."""

import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


@pytest.mark.skip(reason="Requires full integration environment with database mocking")
@pytest.mark.asyncio
async def test_generate_variants_for_task(mock_db_connection):
    """Test generating variants for a task."""
    from services.response_generation import ResponseGenerationService

    # Mock LLM service
    mock_variants = [
        {
            'text': 'AI generated response 1',
            'confidence': 0.9,
            'provider': 'openai',
            'model': 'gpt-4'
        },
        {
            'text': 'AI generated response 2',
            'confidence': 0.85,
            'provider': 'openai',
            'model': 'gpt-4'
        }
    ]

    with patch('services.response_generation.get_llm_service') as mock_llm:
        mock_llm.return_value.generate_response_variants = AsyncMock(return_value=mock_variants)

        with patch('services.response_generation.get_asyncpg_pool') as mock_pool:
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_db_connection

            # Mock database returns
            mock_db_connection.fetchval.return_value = 1  # variant_id

            variants = await ResponseGenerationService.generate_variants_for_task(
                task_id=1,
                message_id=1,
                num_variants=2
            )

            assert len(variants) == 2
            assert variants[0]['variant_text'] == 'AI generated response 1'


@pytest.mark.skip(reason="Requires full integration environment with database mocking")
@pytest.mark.asyncio
async def test_soften_response(mock_db_connection):
    """Test softening response (regenerate with soft tone)."""
    from services.response_generation import ResponseGenerationService

    with patch('services.response_generation.ResponseGenerationService.generate_variants_for_task') as mock_gen:
        mock_gen.return_value = [
            {'variant_text': 'Gentle response', 'confidence_score': 0.9}
        ]

        variants = await ResponseGenerationService.soften_response(
            task_id=1,
            message_id=1
        )

        # Verify it called with tone='soft' and force_regenerate=True
        mock_gen.assert_called_once_with(
            task_id=1,
            message_id=1,
            num_variants=2,
            tone='soft',
            force_regenerate=True
        )


@pytest.mark.skip(reason="Requires full integration environment with database mocking")
@pytest.mark.asyncio
async def test_caching_prevents_duplicate_generation(mock_db_connection):
    """Test that existing variants are returned without regeneration."""
    from services.response_generation import ResponseGenerationService

    # Mock existing variants in database
    existing_variants = [
        {'id': 1, 'variant_text': 'Existing variant', 'confidence_score': 0.9}
    ]

    mock_db_connection.fetch.return_value = [Mock(**v) for v in existing_variants]

    with patch('services.response_generation.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_db_connection

        with patch('services.response_generation.get_llm_service') as mock_llm:
            # LLM should NOT be called if variants exist
            variants = await ResponseGenerationService.generate_variants_for_task(
                task_id=1,
                message_id=1,
                force_regenerate=False
            )

            mock_llm.assert_not_called()
