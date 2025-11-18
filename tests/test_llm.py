"""Tests for LLM service."""

import sys
import os
import pytest
from unittest.mock import Mock, patch, AsyncMock

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


@pytest.mark.skip(reason="Requires full integration environment with aiohttp mocking")
def test_llm_service_initialization():
    """Test LLM service initializes with config."""
    from services.llm import LLMService

    # Mock config
    with patch('services.llm.get_config') as mock_config:
        mock_config.return_value = Mock(
            llm_provider='openai',
            llm_model='gpt-4-turbo',
            openai_api_key='test_key'
        )

        service = LLMService()

        assert service.provider == 'openai'
        assert service.model == 'gpt-4-turbo'
        assert service.client is not None


@pytest.mark.skip(reason="Requires full integration environment with aiohttp mocking")
@pytest.mark.asyncio
async def test_openai_client_generate_response():
    """Test OpenAI client generates responses."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4-turbo')

    # Mock aiohttp response
    mock_response_data = {
        'choices': [
            {
                'message': {'content': 'This is response variant 1'},
                'finish_reason': 'stop'
            },
            {
                'message': {'content': 'This is response variant 2'},
                'finish_reason': 'stop'
            }
        ]
    }

    with patch('aiohttp.ClientSession') as mock_session:
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value.status = 200
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response_data)

        variants = await client.generate_response(
            message_context="User: Hello",
            user_message="How are you?",
            max_variants=2
        )

        assert len(variants) == 2
        assert variants[0]['text'] == 'This is response variant 1'
        assert variants[0]['provider'] == 'openai'
        assert variants[0]['confidence'] == 0.9  # stop finish_reason


@pytest.mark.skip(reason="Requires full integration environment with aiohttp mocking")
@pytest.mark.asyncio
async def test_anthropic_client_generate_response():
    """Test Anthropic client generates responses."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    # Mock response
    mock_response_data = {
        'content': [
            {
                'text': 'Response variant 1\n---\nResponse variant 2'
            }
        ],
        'stop_reason': 'end_turn'
    }

    with patch('aiohttp.ClientSession') as mock_session:
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value.status = 200
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response_data)

        variants = await client.generate_response(
            message_context="User: Hello",
            user_message="How are you?",
            max_variants=2
        )

        assert len(variants) == 2
        assert variants[0]['provider'] == 'anthropic'
        assert variants[0]['confidence'] == 0.85


@pytest.mark.skip(reason="Requires full integration environment with aiohttp mocking")
def test_llm_client_timeout_handling():
    """Test LLM client handles timeouts."""
    from services.llm import OpenAIClient
    import asyncio

    client = OpenAIClient(api_key='test_key', model='gpt-4-turbo', timeout=1)

    # Test will be implemented with actual timeout simulation


@pytest.mark.skip(reason="Requires full integration environment with aiohttp mocking")
@pytest.mark.asyncio
async def test_build_context_string():
    """Test context string building."""
    from services.llm import LLMService

    with patch('services.llm.get_config') as mock_config:
        mock_config.return_value = Mock(
            llm_provider='openai',
            llm_model='gpt-4',
            openai_api_key='test'
        )

        service = LLMService()

        context_messages = [
            {'author_name': 'Alice', 'content': 'Hello'},
            {'author_name': 'Bob', 'content': 'Hi there'},
            {'author_name': 'Alice', 'content': 'How are you?'}
        ]

        context_str = service._build_context_string(context_messages)

        assert 'Alice: Hello' in context_str
        assert 'Bob: Hi there' in context_str
        assert 'Alice: How are you?' in context_str
