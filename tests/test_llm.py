"""Tests for LLM service."""

import sys
import os
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))


# ============================================================================
# FIXTURES AND HELPERS
# ============================================================================

@pytest.fixture
def mock_config_openai():
    """Mock configuration for OpenAI."""
    config = Mock()
    config.llm = Mock(
        provider='openai',
        model='gpt-4-turbo',
        openai_api_key='test_openai_key',
        anthropic_api_key=None
    )
    return config


@pytest.fixture
def mock_config_anthropic():
    """Mock configuration for Anthropic."""
    config = Mock()
    config.llm = Mock(
        provider='anthropic',
        model='claude-3-sonnet-20240229',
        openai_api_key=None,
        anthropic_api_key='test_anthropic_key'
    )
    return config


def create_mock_aiohttp_session(mock_response):
    """
    Helper to create properly configured aiohttp.ClientSession mock.

    Args:
        mock_response: The response object to return

    Returns:
        Configured mock session class
    """
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(return_value=mock_response),
        __aexit__=AsyncMock(return_value=None)
    ))

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_session
    return mock_session_cls


# ============================================================================
# EXISTING TESTS (RE-ENABLED)
# ============================================================================

def test_llm_service_initialization(mock_config_openai):
    """Test LLM service initializes with config."""
    from services.llm import LLMService, OpenAIClient

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()

        assert service.provider == 'openai'
        assert service.model == 'gpt-4-turbo'
        assert service.client is not None
        assert isinstance(service.client, OpenAIClient)


@pytest.mark.asyncio
async def test_openai_client_generate_response():
    """Test OpenAI client generates responses."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4-turbo')

    # Mock aiohttp response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [
            {
                'message': {'content': 'This is response variant 1'},
                'finish_reason': 'stop'
            },
            {
                'message': {'content': 'This is response variant 2'},
                'finish_reason': 'stop'
            }
        ],
        'usage': {
            'prompt_tokens': 50,
            'completion_tokens': 20,
            'total_tokens': 70
        }
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="User: Hello",
                user_message="How are you?",
                max_variants=2
            )

            assert len(variants) == 2
            assert variants[0]['text'] == 'This is response variant 1'
            assert variants[0]['provider'] == 'openai'
            assert variants[0]['confidence'] == 0.9  # stop finish_reason


@pytest.mark.asyncio
async def test_anthropic_client_generate_response():
    """Test Anthropic client generates responses."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    # Mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [
            {
                'text': 'Response variant 1\n---\nResponse variant 2'
            }
        ],
        'stop_reason': 'end_turn',
        'usage': {
            'input_tokens': 100,
            'output_tokens': 50
        }
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="User: Hello",
                user_message="How are you?",
                max_variants=2
            )

            assert len(variants) == 2
            assert variants[0]['provider'] == 'anthropic'
            assert variants[0]['confidence'] == 0.9


@pytest.mark.asyncio
async def test_llm_client_timeout_handling():
    """Test LLM client handles timeouts."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4-turbo', timeout=1)

    # Create session that raises timeout
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_session

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []
            # Verify timeout was tracked
            mock_track.assert_called()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['status'] == 'timeout'


@pytest.mark.asyncio
async def test_build_context_string(mock_config_openai):
    """Test context string building."""
    from services.llm import LLMService

    with patch('services.llm.get_config', return_value=mock_config_openai):
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


# ============================================================================
# NEW OPENAI CLIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_openai_request_formatting():
    """Test that OpenAI API requests are formatted correctly."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4-turbo')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [{'message': {'content': 'Response'}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
    })

    mock_session_cls = create_mock_aiohttp_session(mock_response)

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()):
            await client.generate_response(
                message_context="Context",
                user_message="Test message",
                tone="soft",
                max_variants=3
            )

            # Verify POST was called with correct parameters
            mock_session = mock_session_cls.return_value
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args

            # Check URL
            assert call_args[0][0] == 'https://api.openai.com/v1/chat/completions'

            # Check payload
            payload = call_args[1]['json']
            assert payload['model'] == 'gpt-4-turbo'
            assert payload['n'] == 3
            assert payload['temperature'] == 0.7
            assert payload['max_tokens'] == 500
            assert 'messages' in payload
            assert len(payload['messages']) == 2  # system + user

            # Check headers
            headers = call_args[1]['headers']
            assert 'Authorization' in headers
            assert headers['Authorization'] == 'Bearer test_key'


@pytest.mark.asyncio
async def test_openai_response_parsing():
    """Test parsing OpenAI API responses into variants."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-3.5-turbo')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [
            {'message': {'content': 'First variant'}, 'finish_reason': 'stop'},
            {'message': {'content': 'Second variant'}, 'finish_reason': 'length'},
            {'message': {'content': 'Third variant'}, 'finish_reason': 'stop'},
        ],
        'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'total_tokens': 50}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=3
            )

            assert len(variants) == 3
            assert variants[0]['text'] == 'First variant'
            assert variants[1]['text'] == 'Second variant'
            assert variants[2]['text'] == 'Third variant'
            assert all(v['provider'] == 'openai' for v in variants)
            assert all(v['model'] == 'gpt-3.5-turbo' for v in variants)


@pytest.mark.asyncio
async def test_openai_token_extraction():
    """Test extracting token counts from OpenAI usage field."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [{'message': {'content': 'Response'}, 'finish_reason': 'stop'}],
        'usage': {
            'prompt_tokens': 150,
            'completion_tokens': 75,
            'total_tokens': 225
        }
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            # Verify token counts were tracked
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['prompt_tokens'] == 150
            assert call_kwargs['completion_tokens'] == 75
            assert call_kwargs['status'] == 'success'


@pytest.mark.asyncio
async def test_openai_error_handling_timeout():
    """Test OpenAI client handles timeout errors."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4', timeout=5)

    # Create session that raises timeout
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_session

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['status'] == 'timeout'
            assert 'timed out' in call_kwargs['error_message']


@pytest.mark.asyncio
async def test_openai_error_handling_api_error():
    """Test OpenAI client handles API errors (4xx, 5xx)."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    # Test 429 Rate Limit
    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.text = AsyncMock(return_value='Rate limit exceeded')

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['status'] == 'error'
            assert 'HTTP 429' in call_kwargs['error_message']


@pytest.mark.asyncio
async def test_openai_error_handling_network_error():
    """Test OpenAI client handles network errors."""
    from services.llm import OpenAIClient
    import aiohttp

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    # Create session that raises network error
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_session

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['status'] == 'error'
            assert 'Network error' in call_kwargs['error_message']


@pytest.mark.asyncio
async def test_openai_confidence_scoring_stop():
    """Test confidence scoring for finish_reason='stop'."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [
            {'message': {'content': 'Complete response'}, 'finish_reason': 'stop'}
        ],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert len(variants) == 1
            assert variants[0]['confidence'] == 0.9


@pytest.mark.asyncio
async def test_openai_confidence_scoring_length():
    """Test confidence scoring for finish_reason='length'."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [
            {'message': {'content': 'Truncated...'}, 'finish_reason': 'length'}
        ],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 500, 'total_tokens': 510}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert len(variants) == 1
            assert variants[0]['confidence'] == 0.7


@pytest.mark.asyncio
async def test_openai_max_variants():
    """Test max_variants parameter limits response count."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    # API returns 5 choices, but we only request 3
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [
            {'message': {'content': f'Variant {i}'}, 'finish_reason': 'stop'}
            for i in range(1, 6)
        ],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 50, 'total_tokens': 60}
    })

    mock_session_cls = create_mock_aiohttp_session(mock_response)

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=3
            )

            # Should get all 5 choices (API returns them)
            assert len(variants) == 5

            # But verify that n=3 was requested in the API call
            mock_session = mock_session_cls.return_value
            call_args = mock_session.post.call_args
            payload = call_args[1]['json']
            assert payload['n'] == 3


@pytest.mark.asyncio
async def test_openai_tone_adjustment():
    """Test tone parameter affects prompt."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [{'message': {'content': 'Gentle response'}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}
    })

    mock_session_cls = create_mock_aiohttp_session(mock_response)

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()):
            await client.generate_response(
                message_context="Context",
                user_message="Message",
                tone="soft",
                max_variants=1
            )

            # Verify system message includes soft tone
            mock_session = mock_session_cls.return_value
            call_args = mock_session.post.call_args
            payload = call_args[1]['json']
            system_message = payload['messages'][0]['content']
            assert 'gentle' in system_message.lower() or 'empathetic' in system_message.lower()


# ============================================================================
# NEW ANTHROPIC CLIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_anthropic_request_formatting():
    """Test Anthropic API request structure."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_anthropic_key', model='claude-3-opus-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [{'text': 'Response'}],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 10, 'output_tokens': 5}
    })

    mock_session_cls = create_mock_aiohttp_session(mock_response)

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()):
            await client.generate_response(
                message_context="Context",
                user_message="Test message",
                max_variants=2
            )

            # Verify POST was called with correct parameters
            mock_session = mock_session_cls.return_value
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args

            # Check URL
            assert call_args[0][0] == 'https://api.anthropic.com/v1/messages'

            # Check headers
            headers = call_args[1]['headers']
            assert headers['x-api-key'] == 'test_anthropic_key'
            assert 'anthropic-version' in headers

            # Check payload
            payload = call_args[1]['json']
            assert payload['model'] == 'claude-3-opus-20240229'
            assert 'system' in payload
            assert 'messages' in payload
            assert payload['max_tokens'] == 1000
            assert payload['temperature'] == 0.7


@pytest.mark.asyncio
async def test_anthropic_response_parsing():
    """Test parsing Anthropic responses."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [
            {'text': 'This is the response text'}
        ],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 50, 'output_tokens': 25}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert len(variants) == 1
            assert variants[0]['text'] == 'This is the response text'
            assert variants[0]['provider'] == 'anthropic'
            assert variants[0]['model'] == 'claude-3-sonnet-20240229'


@pytest.mark.asyncio
async def test_anthropic_variant_splitting():
    """Test splitting response into variants using '---' delimiter."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [
            {'text': 'Variant 1\n---\nVariant 2\n---\nVariant 3'}
        ],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 50, 'output_tokens': 60}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=3
            )

            assert len(variants) == 3
            assert variants[0]['text'] == 'Variant 1'
            assert variants[1]['text'] == 'Variant 2'
            assert variants[2]['text'] == 'Variant 3'


@pytest.mark.asyncio
async def test_anthropic_single_variant():
    """Test handling response without variant delimiters."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [
            {'text': 'Single variant without delimiters'}
        ],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 50, 'output_tokens': 30}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=2
            )

            # Should get 1 variant (no delimiter found)
            assert len(variants) == 1
            assert variants[0]['text'] == 'Single variant without delimiters'


@pytest.mark.asyncio
async def test_anthropic_confidence_end_turn():
    """Test confidence for stop_reason='end_turn'."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [{'text': 'Complete response'}],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 50, 'output_tokens': 25}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert len(variants) == 1
            assert variants[0]['confidence'] == 0.9


@pytest.mark.asyncio
async def test_anthropic_confidence_max_tokens():
    """Test confidence for stop_reason='max_tokens'."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [{'text': 'Truncated response...'}],
        'stop_reason': 'max_tokens',
        'usage': {'input_tokens': 50, 'output_tokens': 1000}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert len(variants) == 1
            assert variants[0]['confidence'] == 0.7


@pytest.mark.asyncio
async def test_anthropic_error_handling():
    """Test Anthropic-specific error handling."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    # Test 500 Server Error
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value='Internal server error')

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['status'] == 'error'
            assert 'HTTP 500' in call_kwargs['error_message']


@pytest.mark.asyncio
async def test_anthropic_token_counting():
    """Test token usage extraction from Anthropic response."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [{'text': 'Response'}],
        'stop_reason': 'end_turn',
        'usage': {
            'input_tokens': 125,
            'output_tokens': 89
        }
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            # Verify token counts were tracked
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['prompt_tokens'] == 125
            assert call_kwargs['completion_tokens'] == 89
            assert call_kwargs['status'] == 'success'


@pytest.mark.asyncio
async def test_anthropic_timeout():
    """Test timeout handling for Anthropic client."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229', timeout=3)

    # Create session that raises timeout
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = mock_session

    with patch('aiohttp.ClientSession', mock_session_cls):
        with patch.object(client, '_track_request', new=AsyncMock()) as mock_track:
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []
            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs['status'] == 'timeout'


@pytest.mark.asyncio
async def test_anthropic_model_variants():
    """Test different Claude model variants."""
    from services.llm import AnthropicClient

    models = [
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307'
    ]

    for model in models:
        client = AnthropicClient(api_key='test_key', model=model)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'content': [{'text': f'Response from {model}'}],
            'stop_reason': 'end_turn',
            'usage': {'input_tokens': 10, 'output_tokens': 5}
        })

        with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
            with patch.object(client, '_track_request', new=AsyncMock()):
                variants = await client.generate_response(
                    message_context="Context",
                    user_message="Message",
                    max_variants=1
                )

                assert len(variants) == 1
                assert variants[0]['model'] == model


# ============================================================================
# NEW LLM SERVICE INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_llm_service_provider_switching():
    """Test switching between OpenAI and Anthropic providers."""
    from services.llm import LLMService, OpenAIClient, AnthropicClient

    # Test OpenAI
    mock_config_openai = Mock()
    mock_config_openai.llm = Mock(
        provider='openai',
        model='gpt-4',
        openai_api_key='test_openai_key',
        anthropic_api_key=None
    )

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()
        assert service.provider == 'openai'
        assert isinstance(service.client, OpenAIClient)

    # Test Anthropic
    mock_config_anthropic = Mock()
    mock_config_anthropic.llm = Mock(
        provider='anthropic',
        model='claude-3-sonnet-20240229',
        openai_api_key=None,
        anthropic_api_key='test_anthropic_key'
    )

    with patch('services.llm.get_config', return_value=mock_config_anthropic):
        service = LLMService()
        assert service.provider == 'anthropic'
        assert isinstance(service.client, AnthropicClient)


@pytest.mark.asyncio
async def test_llm_service_tracking_integration(mock_config_openai):
    """Test LLM monitoring integration."""
    from services.llm import LLMService

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'choices': [{'message': {'content': 'Response'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}
        })

        with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
            with patch('services.llm.get_asyncpg_pool') as mock_pool:
                mock_conn = AsyncMock()
                mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

                with patch('services.llm.track_llm_request') as mock_track_func:
                    await service.generate_response_variants(
                        message={'content': 'Test message', 'author_name': 'User'},
                        context_messages=[],
                        num_variants=1
                    )

                    # Verify tracking was called
                    mock_track_func.assert_called_once()
                    call_kwargs = mock_track_func.call_args[1]
                    assert call_kwargs['provider'] == 'openai'
                    assert call_kwargs['prompt_tokens'] == 100
                    assert call_kwargs['completion_tokens'] == 50


@pytest.mark.asyncio
async def test_llm_service_soften_tone(mock_config_openai):
    """Test soften tone functionality."""
    from services.llm import LLMService

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'choices': [{'message': {'content': 'Gentle response'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 50, 'completion_tokens': 25, 'total_tokens': 75}
        })

        mock_session_cls = create_mock_aiohttp_session(mock_response)

        with patch('aiohttp.ClientSession', mock_session_cls):
            with patch.object(service.client, '_track_request', new=AsyncMock()):
                variants = await service.generate_response_variants(
                    message={'content': 'Test message', 'author_name': 'User'},
                    context_messages=[],
                    num_variants=1,
                    tone='soft'
                )

                # Verify tone was passed to client
                assert len(variants) == 1

                # Check that the system message includes soft tone
                mock_session = mock_session_cls.return_value
                call_args = mock_session.post.call_args
                payload = call_args[1]['json']
                system_message = payload['messages'][0]['content']
                assert 'gentle' in system_message.lower() or 'empathetic' in system_message.lower()


@pytest.mark.asyncio
async def test_llm_service_context_building(mock_config_openai):
    """Test context string building from message list."""
    from services.llm import LLMService

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()

        # Test with multiple messages
        messages = [
            {'author_name': 'Alice', 'content': 'First message'},
            {'author_name': 'Bob', 'content': 'Second message'},
            {'author_name': 'Charlie', 'content': 'Third message'}
        ]

        context = service._build_context_string(messages)

        assert 'Alice: First message' in context
        assert 'Bob: Second message' in context
        assert 'Charlie: Third message' in context

        # Test with empty messages
        empty_context = service._build_context_string([])
        assert empty_context == "(No previous context)"

        # Test with messages without content
        empty_content_messages = [
            {'author_name': 'User', 'content': ''}
        ]
        no_content_context = service._build_context_string(empty_content_messages)
        assert no_content_context == "(No previous context)"

        # Test with many messages (should limit to last 10)
        many_messages = [
            {'author_name': f'User{i}', 'content': f'Message {i}'}
            for i in range(20)
        ]
        limited_context = service._build_context_string(many_messages)

        # Should only include last 10
        assert 'Message 10' in limited_context
        assert 'Message 19' in limited_context
        assert 'Message 0' not in limited_context
        assert 'Message 9' not in limited_context


@pytest.mark.asyncio
async def test_llm_service_error_propagation(mock_config_openai):
    """Test errors from clients propagate correctly."""
    from services.llm import LLMService

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()

        # Create session that raises error
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(side_effect=Exception("Unexpected error"))

        mock_session_cls = MagicMock()
        mock_session_cls.return_value = mock_session

        with patch('aiohttp.ClientSession', mock_session_cls):
            with patch.object(service.client, '_track_request', new=AsyncMock()):
                variants = await service.generate_response_variants(
                    message={'content': 'Test message', 'author_name': 'User'},
                    context_messages=[],
                    num_variants=1
                )

                # Service should handle error gracefully and return empty list
                assert variants == []


# ============================================================================
# ADDITIONAL EDGE CASE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_openai_empty_choices():
    """Test handling of empty choices in OpenAI response."""
    from services.llm import OpenAIClient

    client = OpenAIClient(api_key='test_key', model='gpt-4')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'choices': [],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 0, 'total_tokens': 10}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []


@pytest.mark.asyncio
async def test_anthropic_empty_content():
    """Test handling of empty content in Anthropic response."""
    from services.llm import AnthropicClient

    client = AnthropicClient(api_key='test_key', model='claude-3-sonnet-20240229')

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'content': [],
        'stop_reason': 'end_turn',
        'usage': {'input_tokens': 10, 'output_tokens': 0}
    })

    with patch('aiohttp.ClientSession', create_mock_aiohttp_session(mock_response)):
        with patch.object(client, '_track_request', new=AsyncMock()):
            variants = await client.generate_response(
                message_context="Context",
                user_message="Message",
                max_variants=1
            )

            assert variants == []


@pytest.mark.asyncio
async def test_llm_service_empty_message(mock_config_openai):
    """Test handling empty message in LLM service."""
    from services.llm import LLMService

    with patch('services.llm.get_config', return_value=mock_config_openai):
        service = LLMService()

        variants = await service.generate_response_variants(
            message={'content': '', 'author_name': 'User'},
            context_messages=[],
            num_variants=1
        )

        # Should return empty list without making API call
        assert variants == []


def test_llm_service_missing_config():
    """Test LLM service initialization with missing config."""
    from services.llm import LLMService

    mock_config = Mock()
    mock_config.llm = None

    with patch('services.llm.get_config', return_value=mock_config):
        with pytest.raises(ValueError, match="LLM configuration not found"):
            LLMService()


def test_llm_service_invalid_provider(mock_config_openai):
    """Test LLM service initialization with invalid provider."""
    from services.llm import LLMService

    mock_config_openai.llm.provider = 'invalid_provider'

    with patch('services.llm.get_config', return_value=mock_config_openai):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMService()


def test_llm_service_missing_openai_key():
    """Test LLM service initialization with missing OpenAI key."""
    from services.llm import LLMService

    mock_config = Mock()
    mock_config.llm = Mock(
        provider='openai',
        model='gpt-4',
        openai_api_key=None
    )

    with patch('services.llm.get_config', return_value=mock_config):
        with pytest.raises(ValueError, match="OPENAI_API_KEY not configured"):
            LLMService()


def test_llm_service_missing_anthropic_key():
    """Test LLM service initialization with missing Anthropic key."""
    from services.llm import LLMService

    mock_config = Mock()
    mock_config.llm = Mock(
        provider='anthropic',
        model='claude-3-sonnet-20240229',
        anthropic_api_key=None
    )

    with patch('services.llm.get_config', return_value=mock_config):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not configured"):
            LLMService()
