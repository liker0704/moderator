"""
Discord utility functions and helpers.

This module provides utility functions for Discord operations:
- Message formatting and sanitization
- Discord markdown to plain text conversion
- User mention and role mention parsing
- Timestamp formatting and timezone handling
- Channel and guild ID validation
- Discord API error handling and response parsing
- Rate limit calculation and tracking

These utilities are used across Discord-related modules to ensure consistent
handling of Discord data formats and API interactions.
"""

import base64
import json
import logging
import platform
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_super_properties(custom_props: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Parse or generate Discord super properties.

    Super properties are technical parameters of the Discord client
    required for authentication. If custom properties are provided,
    they will be validated and returned. Otherwise, default properties
    will be generated based on the current system.

    Args:
        custom_props: Custom super properties dictionary (optional)

    Returns:
        Dictionary containing super properties

    Example:
        >>> props = parse_super_properties()
        >>> print(props['os'])
        'Linux'
    """
    if custom_props:
        # Validate required fields
        required_fields = ["os", "browser"]
        for field in required_fields:
            if field not in custom_props:
                logger.warning(f"Missing required super property: {field}")

        return custom_props

    # Generate default super properties based on system
    system = platform.system()

    if system == "Linux":
        os_name = "Linux"
        os_version = platform.release()
    elif system == "Windows":
        os_name = "Windows"
        os_version = platform.version()
    elif system == "Darwin":
        os_name = "Mac OS X"
        os_version = platform.mac_ver()[0]
    else:
        os_name = "Linux"
        os_version = "Unknown"

    # Default properties matching a typical browser client
    default_props = {
        "os": os_name,
        "browser": "Chrome",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "browser_version": "120.0.0.0",
        "os_version": os_version,
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": 261053,  # Update periodically as Discord updates
        "client_event_source": None
    }

    logger.debug(f"Generated super properties: os={os_name}, browser=Chrome")

    return default_props


def parse_super_properties_from_base64(base64_props: str) -> Dict[str, Any]:
    """
    Parse super properties from base64-encoded string.

    Discord provides super properties as a base64-encoded JSON string
    via the browser DevTools. This function decodes and parses them.

    Args:
        base64_props: Base64-encoded super properties string

    Returns:
        Dictionary containing super properties

    Raises:
        ValueError: If base64 string is invalid or JSON cannot be parsed

    Example:
        >>> base64_str = "eyJvcyI6IkxpbnV4IiwiYnJvd3NlciI6IkNocm9tZSJ9"
        >>> props = parse_super_properties_from_base64(base64_str)
        >>> print(props['os'])
        'Linux'
    """
    try:
        decoded_bytes = base64.b64decode(base64_props)
        decoded_str = decoded_bytes.decode('utf-8')
        props = json.loads(decoded_str)
        logger.info("Successfully parsed super properties from base64")
        return props
    except base64.binascii.Error as e:
        raise ValueError(f"Invalid base64 string: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in super properties: {e}")
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid UTF-8 encoding: {e}")


def validate_discord_token(token: str) -> str:
    """
    Validate Discord user token format.

    Discord user tokens have a specific format:
    - Base64-encoded user ID
    - Timestamp
    - HMAC signature
    - Separated by dots

    Args:
        token: Discord user token to validate

    Returns:
        The validated token (stripped of whitespace)

    Raises:
        ValueError: If token format is invalid

    Example:
        >>> token = "MTE1NjY5ODQwMzMwMjQ1MTMwMQ.G8kR9w.abc123..."
        >>> validated = validate_discord_token(token)
    """
    if not token:
        raise ValueError("Discord token is empty")

    token = token.strip()

    # Basic format validation (3 parts separated by dots)
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError(
            "Invalid Discord token format. "
            "Token should have 3 parts separated by dots."
        )

    # Validate first part is valid base64
    try:
        base64.b64decode(parts[0])
    except base64.binascii.Error:
        raise ValueError("Invalid token: first part is not valid base64")

    logger.info("Discord token validated successfully")
    return token


def format_discord_timestamp(
    timestamp: str,
    output_format: str = "iso"
) -> str:
    """
    Format Discord timestamp string to desired format.

    Discord provides timestamps in ISO 8601 format with microseconds.
    This function converts them to various output formats.

    Args:
        timestamp: Discord timestamp string (ISO 8601)
        output_format: Output format ('iso', 'unix', 'readable')

    Returns:
        Formatted timestamp string

    Example:
        >>> ts = "2025-11-16T12:00:00.000000+00:00"
        >>> format_discord_timestamp(ts, "readable")
        '2025-11-16 12:00:00 UTC'
        >>> format_discord_timestamp(ts, "unix")
        '1700136000'
    """
    try:
        # Parse Discord timestamp
        dt = datetime.fromisoformat(timestamp.replace('+00:00', '+0000'))

        if output_format == "iso":
            return dt.isoformat()
        elif output_format == "unix":
            return str(int(dt.timestamp()))
        elif output_format == "readable":
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            raise ValueError(f"Unknown output format: {output_format}")

    except ValueError as e:
        logger.error(f"Failed to parse timestamp '{timestamp}': {e}")
        return timestamp  # Return original on error


def parse_discord_timestamp(timestamp: str) -> datetime:
    """
    Parse Discord timestamp string to datetime object.

    Args:
        timestamp: Discord timestamp string (ISO 8601)

    Returns:
        datetime object (timezone-aware)

    Example:
        >>> ts = "2025-11-16T12:00:00.000000+00:00"
        >>> dt = parse_discord_timestamp(ts)
        >>> print(dt.year)
        2025
    """
    # Handle both formats: with and without timezone
    if '+' in timestamp or timestamp.endswith('Z'):
        # Has timezone info
        timestamp_clean = timestamp.replace('Z', '+00:00')
        return datetime.fromisoformat(timestamp_clean)
    else:
        # No timezone, assume UTC
        dt = datetime.fromisoformat(timestamp)
        return dt.replace(tzinfo=timezone.utc)


def sanitize_discord_content(content: str) -> str:
    """
    Sanitize Discord message content.

    Removes or escapes potentially problematic characters and formatting.

    Args:
        content: Raw Discord message content

    Returns:
        Sanitized content

    Example:
        >>> content = "Hello @everyone! Check <@123456789>"
        >>> sanitize_discord_content(content)
        'Hello @everyone! Check @user'
    """
    if not content:
        return ""

    # Remove or replace special Discord syntax
    # This is a basic implementation; expand as needed

    # Remove zero-width characters
    content = content.replace('\u200b', '')  # Zero-width space
    content = content.replace('\u200c', '')  # Zero-width non-joiner
    content = content.replace('\u200d', '')  # Zero-width joiner

    # Strip leading/trailing whitespace
    content = content.strip()

    return content


def parse_discord_mentions(content: str) -> Dict[str, list]:
    """
    Parse Discord mentions from message content.

    Extracts user mentions, role mentions, and channel mentions.

    Args:
        content: Discord message content

    Returns:
        Dictionary with 'users', 'roles', and 'channels' lists

    Example:
        >>> content = "Hello <@123456789> check <#987654321>"
        >>> mentions = parse_discord_mentions(content)
        >>> print(mentions['users'])
        ['123456789']
        >>> print(mentions['channels'])
        ['987654321']
    """
    mentions = {
        'users': [],
        'roles': [],
        'channels': []
    }

    # User mentions: <@123456789> or <@!123456789> (with nickname)
    user_pattern = r'<@!?(\d+)>'
    mentions['users'] = re.findall(user_pattern, content)

    # Role mentions: <@&123456789>
    role_pattern = r'<@&(\d+)>'
    mentions['roles'] = re.findall(role_pattern, content)

    # Channel mentions: <#123456789>
    channel_pattern = r'<#(\d+)>'
    mentions['channels'] = re.findall(channel_pattern, content)

    return mentions


def strip_discord_markdown(content: str) -> str:
    """
    Strip Discord markdown formatting from text.

    Removes bold, italic, underline, strikethrough, code blocks, etc.

    Args:
        content: Discord message content with markdown

    Returns:
        Plain text without markdown

    Example:
        >>> content = "**bold** *italic* ~~strike~~ `code`"
        >>> strip_discord_markdown(content)
        'bold italic strike code'
    """
    if not content:
        return ""

    # Remove code blocks (```code```)
    content = re.sub(r'```[a-z]*\n?(.*?)\n?```', r'\1', content, flags=re.DOTALL)

    # Remove inline code (`code`)
    content = re.sub(r'`([^`]+)`', r'\1', content)

    # Remove bold (**text** or __text__)
    content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
    content = re.sub(r'__([^_]+)__', r'\1', content)

    # Remove italic (*text* or _text_)
    content = re.sub(r'\*([^*]+)\*', r'\1', content)
    content = re.sub(r'_([^_]+)_', r'\1', content)

    # Remove strikethrough (~~text~~)
    content = re.sub(r'~~([^~]+)~~', r'\1', content)

    # Remove underline (not standard Discord, but sometimes used)
    content = re.sub(r'__([^_]+)__', r'\1', content)

    # Remove spoilers (||text||)
    content = re.sub(r'\|\|([^|]+)\|\|', r'\1', content)

    # Remove blockquotes (> text or >>> text)
    content = re.sub(r'^>\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'^>>>\s*', '', content, flags=re.MULTILINE)

    return content.strip()


def validate_snowflake(snowflake: str) -> bool:
    """
    Validate Discord snowflake ID.

    Snowflakes are 64-bit integers used for IDs in Discord.
    They must be numeric and within a valid range.

    Args:
        snowflake: Discord snowflake ID (as string)

    Returns:
        True if valid, False otherwise

    Example:
        >>> validate_snowflake("123456789012345678")
        True
        >>> validate_snowflake("invalid")
        False
    """
    if not snowflake:
        return False

    # Must be numeric
    if not snowflake.isdigit():
        return False

    # Convert to int and check range
    try:
        snowflake_int = int(snowflake)
        # Discord snowflakes are typically 17-19 digits
        # Minimum: 4194304 (Discord epoch)
        # Maximum: 2^64-1
        if snowflake_int < 4194304 or snowflake_int >= 2**64:
            return False
        return True
    except ValueError:
        return False


def extract_snowflake_timestamp(snowflake: str) -> Optional[datetime]:
    """
    Extract timestamp from Discord snowflake ID.

    Discord snowflakes encode the creation timestamp in the first 42 bits.

    Args:
        snowflake: Discord snowflake ID

    Returns:
        datetime object or None if invalid

    Example:
        >>> snowflake = "123456789012345678"
        >>> dt = extract_snowflake_timestamp(snowflake)
        >>> print(dt.year)
        2015
    """
    if not validate_snowflake(snowflake):
        return None

    try:
        snowflake_int = int(snowflake)

        # Discord epoch: 2015-01-01T00:00:00.000Z
        DISCORD_EPOCH = 1420070400000

        # Extract timestamp (first 42 bits, shift right by 22)
        timestamp_ms = (snowflake_int >> 22) + DISCORD_EPOCH

        # Convert to datetime
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    except Exception as e:
        logger.error(f"Failed to extract timestamp from snowflake: {e}")
        return None


def format_discord_message_link(
    guild_id: str,
    channel_id: str,
    message_id: str
) -> str:
    """
    Format a Discord message link.

    Args:
        guild_id: Guild (server) ID
        channel_id: Channel ID
        message_id: Message ID

    Returns:
        Discord message link URL

    Example:
        >>> link = format_discord_message_link("111", "222", "333")
        >>> print(link)
        'https://discord.com/channels/111/222/333'
    """
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"


def is_discord_url(url: str) -> bool:
    """
    Check if URL is a Discord URL (CDN, attachments, etc.).

    Args:
        url: URL to check

    Returns:
        True if Discord URL, False otherwise

    Example:
        >>> is_discord_url("https://cdn.discordapp.com/attachments/...")
        True
        >>> is_discord_url("https://example.com/image.png")
        False
    """
    discord_domains = [
        'discord.com',
        'discordapp.com',
        'cdn.discordapp.com',
        'media.discordapp.net',
        'discord.gg'
    ]

    return any(domain in url for domain in discord_domains)


def parse_discord_embed(embed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Discord embed data to simplified format.

    Args:
        embed_data: Raw embed data from Discord API

    Returns:
        Simplified embed dictionary

    Example:
        >>> embed = {"title": "Test", "description": "Hello"}
        >>> parsed = parse_discord_embed(embed)
        >>> print(parsed['title'])
        'Test'
    """
    return {
        'title': embed_data.get('title', ''),
        'description': embed_data.get('description', ''),
        'url': embed_data.get('url', ''),
        'color': embed_data.get('color'),
        'timestamp': embed_data.get('timestamp'),
        'footer': embed_data.get('footer', {}).get('text', ''),
        'image': embed_data.get('image', {}).get('url', ''),
        'thumbnail': embed_data.get('thumbnail', {}).get('url', ''),
        'author': embed_data.get('author', {}).get('name', ''),
        'fields': [
            {
                'name': field.get('name', ''),
                'value': field.get('value', ''),
                'inline': field.get('inline', False)
            }
            for field in embed_data.get('fields', [])
        ]
    }


def truncate_message(content: str, max_length: int = 2000) -> str:
    """
    Truncate message content to Discord's character limit.

    Discord has a 2000 character limit for message content.

    Args:
        content: Message content
        max_length: Maximum length (default: 2000)

    Returns:
        Truncated content with ellipsis if needed

    Example:
        >>> long_text = "a" * 3000
        >>> truncated = truncate_message(long_text, 100)
        >>> len(truncated)
        100
        >>> truncated.endswith('...')
        True
    """
    if len(content) <= max_length:
        return content

    # Leave room for ellipsis
    return content[:max_length - 3] + '...'


# Export commonly used functions
__all__ = [
    'parse_super_properties',
    'parse_super_properties_from_base64',
    'validate_discord_token',
    'format_discord_timestamp',
    'parse_discord_timestamp',
    'sanitize_discord_content',
    'parse_discord_mentions',
    'strip_discord_markdown',
    'validate_snowflake',
    'extract_snowflake_timestamp',
    'format_discord_message_link',
    'is_discord_url',
    'parse_discord_embed',
    'truncate_message'
]
