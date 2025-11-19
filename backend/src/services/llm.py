"""
LLM integration service for response generation.

Supports:
- OpenAI GPT-4 / GPT-3.5
- Anthropic Claude 3 (Opus, Sonnet, Haiku)

Features:
- Response variant generation
- Tone adjustment ("soft", "formal")
- Confidence scoring
- Timeout handling
- Error handling with retries
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime
import aiohttp

from config import get_config
from database.connection import get_asyncpg_pool
from services.llm_monitoring import track_llm_request

logger = logging.getLogger(__name__)

# Provider types
LLMProvider = Literal["openai", "anthropic"]


class LLMClient:
    """Base class for LLM clients."""

    def __init__(self, api_key: str, model: str, timeout: int = 30):
        """
        Initialize LLM client.

        Args:
            api_key: API key for the provider
            model: Model identifier (e.g., "gpt-4-turbo", "claude-3-opus-20240229")
            timeout: Request timeout in seconds (default 30)
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def _track_request(
        self,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        status: str = "success",
        error_message: Optional[str] = None,
        task_id: Optional[int] = None,
        request_type: str = "generation"
    ) -> None:
        """
        Track LLM request in monitoring system.

        Args:
            provider: LLM provider ('openai' or 'anthropic')
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            duration_ms: Request duration in milliseconds
            status: Request status ('success', 'error', 'timeout')
            error_message: Error details if applicable
            task_id: Associated task ID if applicable
            request_type: Type of request ('generation', 'soften', etc.)
        """
        try:
            pool = get_asyncpg_pool()
            async with pool.acquire() as conn:
                await track_llm_request(
                    conn=conn,
                    provider=provider,
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    duration_ms=duration_ms,
                    status=status,
                    error_message=error_message,
                    task_id=task_id,
                    request_type=request_type
                )
        except Exception as e:
            # Don't let tracking errors break the main flow
            logger.warning(f"Failed to track LLM request: {e}")

        # Track metrics if available
        try:
            from api.metrics import increment_llm_requests, observe_response_time, increment_errors
            increment_llm_requests(provider, status)
            observe_response_time('llm_request', duration_ms / 1000.0)  # Convert to seconds
            if status == 'error':
                increment_errors('llm')
        except ImportError:
            # Metrics not available
            pass
        except Exception as e:
            logger.warning(f"Failed to track LLM metrics: {e}")

    async def generate_response(
        self,
        message_context: str,
        user_message: str,
        tone: Optional[str] = None,
        max_variants: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate response variants.

        Args:
            message_context: Context from previous messages
            user_message: The user's message to respond to
            tone: Optional tone modifier ("soft", "formal", None)
            max_variants: Number of response variants to generate

        Returns:
            List of variant dicts with keys: text, confidence, provider, model
        """
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """OpenAI API client for GPT models."""

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    async def generate_response(
        self,
        message_context: str,
        user_message: str,
        tone: Optional[str] = None,
        max_variants: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate response variants using OpenAI.

        Args:
            message_context: Context from previous messages
            user_message: The user's message to respond to
            tone: Optional tone modifier ("soft", "formal", None)
            max_variants: Number of response variants to generate

        Returns:
            List of variant dicts with keys: text, confidence, provider, model
        """
        # Start timing
        start_time = time.time()

        # Build system prompt
        system_prompt = self._build_system_prompt(tone)

        # Build user prompt
        user_prompt = f"""Context (previous messages):
{message_context}

User's message:
{user_message}

Generate {max_variants} different response options."""

        # Prepare request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "n": max_variants,
            "temperature": 0.7,
            "max_tokens": 500
        }

        # Make request with timeout
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    # Calculate duration
                    duration_ms = int((time.time() - start_time) * 1000)

                    if response.status == 200:
                        data = await response.json()

                        # Extract token usage
                        usage = data.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)

                        # Track successful request
                        await self._track_request(
                            provider="openai",
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            duration_ms=duration_ms,
                            status="success"
                        )

                        return self._parse_openai_response(data)
                    else:
                        error = await response.text()
                        logger.error(f"OpenAI API error {response.status}: {error}")

                        # Track failed request
                        await self._track_request(
                            provider="openai",
                            prompt_tokens=0,
                            completion_tokens=0,
                            duration_ms=duration_ms,
                            status="error",
                            error_message=f"HTTP {response.status}: {error[:200]}"
                        )

                        return []
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"OpenAI request timed out after {self.timeout}s")

            # Track timeout
            await self._track_request(
                provider="openai",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="timeout",
                error_message=f"Request timed out after {self.timeout}s"
            )

            return []
        except aiohttp.ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"OpenAI network error: {e}", exc_info=True)

            # Track network error
            await self._track_request(
                provider="openai",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="error",
                error_message=f"Network error: {str(e)[:200]}"
            )

            return []
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"OpenAI request failed: {e}", exc_info=True)

            # Track general error
            await self._track_request(
                provider="openai",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="error",
                error_message=f"Unexpected error: {str(e)[:200]}"
            )

            return []

    def _build_system_prompt(self, tone: Optional[str]) -> str:
        """
        Build system prompt based on tone.

        Args:
            tone: Optional tone modifier ("soft", "formal", None)

        Returns:
            System prompt string
        """
        base = (
            "You are a helpful community moderator assistant. "
            "Generate professional, friendly responses."
        )

        if tone == "soft":
            return base + " Use a gentle, empathetic tone. Avoid harsh language."
        elif tone == "formal":
            return base + " Use formal, professional language."
        else:
            return base

    def _parse_openai_response(self, data: Dict) -> List[Dict[str, Any]]:
        """
        Parse OpenAI API response.

        Args:
            data: Raw API response data

        Returns:
            List of parsed variant dicts
        """
        variants = []

        for choice in data.get("choices", []):
            content = choice.get("message", {}).get("content", "").strip()
            if content:
                variants.append({
                    "text": content,
                    "confidence": self._calculate_confidence(choice),
                    "provider": "openai",
                    "model": self.model
                })

        return variants

    def _calculate_confidence(self, choice: Dict) -> float:
        """
        Calculate confidence score (0.0 - 1.0).

        Args:
            choice: Choice object from OpenAI response

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Use finish_reason as confidence indicator
        finish_reason = choice.get("finish_reason", "")
        if finish_reason == "stop":
            return 0.9
        elif finish_reason == "length":
            return 0.7
        else:
            return 0.5


class AnthropicClient(LLMClient):
    """Anthropic Claude API client."""

    BASE_URL = "https://api.anthropic.com/v1/messages"

    async def generate_response(
        self,
        message_context: str,
        user_message: str,
        tone: Optional[str] = None,
        max_variants: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate response variants using Anthropic Claude.

        Args:
            message_context: Context from previous messages
            user_message: The user's message to respond to
            tone: Optional tone modifier ("soft", "formal", None)
            max_variants: Number of response variants to generate

        Returns:
            List of variant dicts with keys: text, confidence, provider, model
        """
        # Start timing
        start_time = time.time()

        # Build system prompt
        system_prompt = self._build_system_prompt(tone)

        # Build user prompt
        user_prompt = f"""Context (previous messages):
{message_context}

User's message:
{user_message}

Generate {max_variants} different response options, separated by '---'."""

        # Prepare request
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }

        # Make request with timeout
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    # Calculate duration
                    duration_ms = int((time.time() - start_time) * 1000)

                    if response.status == 200:
                        data = await response.json()

                        # Extract token usage
                        usage = data.get("usage", {})
                        prompt_tokens = usage.get("input_tokens", 0)
                        completion_tokens = usage.get("output_tokens", 0)

                        # Track successful request
                        await self._track_request(
                            provider="anthropic",
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            duration_ms=duration_ms,
                            status="success"
                        )

                        return self._parse_anthropic_response(data, max_variants)
                    else:
                        error = await response.text()
                        logger.error(f"Anthropic API error {response.status}: {error}")

                        # Track failed request
                        await self._track_request(
                            provider="anthropic",
                            prompt_tokens=0,
                            completion_tokens=0,
                            duration_ms=duration_ms,
                            status="error",
                            error_message=f"HTTP {response.status}: {error[:200]}"
                        )

                        return []
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Anthropic request timed out after {self.timeout}s")

            # Track timeout
            await self._track_request(
                provider="anthropic",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="timeout",
                error_message=f"Request timed out after {self.timeout}s"
            )

            return []
        except aiohttp.ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Anthropic network error: {e}", exc_info=True)

            # Track network error
            await self._track_request(
                provider="anthropic",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="error",
                error_message=f"Network error: {str(e)[:200]}"
            )

            return []
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Anthropic request failed: {e}", exc_info=True)

            # Track general error
            await self._track_request(
                provider="anthropic",
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                status="error",
                error_message=f"Unexpected error: {str(e)[:200]}"
            )

            return []

    def _build_system_prompt(self, tone: Optional[str]) -> str:
        """
        Build system prompt based on tone.

        Args:
            tone: Optional tone modifier ("soft", "formal", None)

        Returns:
            System prompt string
        """
        base = (
            "You are a helpful community moderator assistant. "
            "Generate professional, friendly responses."
        )

        if tone == "soft":
            return base + " Use a gentle, empathetic tone. Avoid harsh language."
        elif tone == "formal":
            return base + " Use formal, professional language."
        else:
            return base

    def _parse_anthropic_response(
        self,
        data: Dict,
        max_variants: int
    ) -> List[Dict[str, Any]]:
        """
        Parse Anthropic API response.

        Args:
            data: Raw API response data
            max_variants: Maximum number of variants to return

        Returns:
            List of parsed variant dicts
        """
        content = data.get("content", [])
        if not content:
            return []

        # Extract text
        text = content[0].get("text", "").strip()
        if not text:
            return []

        # Calculate base confidence from stop reason
        base_confidence = self._calculate_confidence(data)

        # Split by separator
        variants_text = text.split("---")
        variants = []

        for variant_text in variants_text[:max_variants]:
            variant_text = variant_text.strip()
            if variant_text:
                variants.append({
                    "text": variant_text,
                    "confidence": base_confidence,
                    "provider": "anthropic",
                    "model": self.model
                })

        return variants

    def _calculate_confidence(self, data: Dict) -> float:
        """
        Calculate confidence score (0.0 - 1.0).

        Args:
            data: Full API response data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        stop_reason = data.get("stop_reason", "")
        if stop_reason == "end_turn":
            return 0.9
        elif stop_reason == "max_tokens":
            return 0.7
        else:
            return 0.6


class LLMService:
    """Unified LLM service with provider selection."""

    def __init__(self):
        """
        Initialize LLM service with configuration.

        Raises:
            ValueError: If LLM configuration is missing or invalid
        """
        config = get_config()

        # Check if LLM is configured
        if not config.llm:
            raise ValueError(
                "LLM configuration not found. Please set LLM_PROVIDER and "
                "appropriate API keys in your environment."
            )

        self.provider = config.llm.provider
        self.model = config.llm.model

        # Initialize client based on provider
        if self.provider == "openai":
            if not config.llm.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self.client = OpenAIClient(config.llm.openai_api_key, self.model)

        elif self.provider == "anthropic":
            if not config.llm.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self.client = AnthropicClient(config.llm.anthropic_api_key, self.model)

        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

        logger.info(
            f"LLM Service initialized with provider={self.provider}, model={self.model}"
        )

    async def generate_response_variants(
        self,
        message: Dict[str, Any],
        context_messages: List[Dict[str, Any]],
        num_variants: int = 2,
        tone: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate response variants for a message.

        Args:
            message: The message to respond to (dict with 'content', 'author_name')
            context_messages: List of previous messages for context
            num_variants: Number of variants to generate (default 2)
            tone: Optional tone ("soft", "formal", None for default)

        Returns:
            List of variant dicts with keys: text, confidence, provider, model
        """
        # Build context string
        context_str = self._build_context_string(context_messages)

        # Get user message
        user_message = message.get("content", "")
        author_name = message.get("author_name", "User")

        # Handle empty message
        if not user_message:
            logger.warning("Cannot generate response for empty message")
            return []

        # Generate variants
        try:
            variants = await self.client.generate_response(
                message_context=context_str,
                user_message=f"{author_name}: {user_message}",
                tone=tone,
                max_variants=num_variants
            )

            logger.info(
                f"Generated {len(variants)} response variants using {self.provider}"
            )

            return variants
        except Exception as e:
            logger.error(f"Failed to generate response variants: {e}", exc_info=True)
            return []

    def _build_context_string(self, context_messages: List[Dict[str, Any]]) -> str:
        """
        Build context string from messages.

        Args:
            context_messages: List of message dicts with 'author_name' and 'content'

        Returns:
            Formatted context string
        """
        if not context_messages:
            return "(No previous context)"

        context_lines = []

        # Use last 10 messages for context window
        for msg in context_messages[-10:]:
            author = msg.get("author_name", "Unknown")
            content = msg.get("content", "")
            if content:  # Only include messages with content
                context_lines.append(f"{author}: {content}")

        if not context_lines:
            return "(No previous context)"

        return "\n".join(context_lines)


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get or create LLM service singleton.

    Returns:
        LLMService: Singleton instance of the LLM service

    Raises:
        ValueError: If LLM configuration is missing or invalid
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def reset_llm_service() -> None:
    """
    Reset the LLM service singleton.

    Useful for testing or configuration changes.
    """
    global _llm_service
    _llm_service = None


# Export public API
__all__ = [
    "LLMClient",
    "OpenAIClient",
    "AnthropicClient",
    "LLMService",
    "get_llm_service",
    "reset_llm_service",
    "LLMProvider"
]
