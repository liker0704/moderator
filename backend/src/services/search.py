"""
Search service for parsing and executing message searches.

This module provides search functionality:
- Parses search query strings with filter syntax
- Executes searches with pagination
- Formats search results for display
- Handles search state for pagination
"""

import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchQuery:
    """
    Represents a parsed search query with filters.

    Attributes:
        text_query: Free text search query
        author_username: Filter by author username
        author_id: Filter by author ID
        channel_id: Filter by channel ID
        server_id: Filter by server ID
        platform: Filter by platform
        date_from: Start date for date range
        date_to: End date for date range
        has_image: Filter messages with images
    """
    text_query: Optional[str] = None
    author_username: Optional[str] = None
    author_id: Optional[str] = None
    channel_id: Optional[str] = None
    server_id: Optional[str] = None
    platform: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    has_image: Optional[bool] = None


class SearchService:
    """
    Service for handling message search operations.

    Provides query parsing, search execution, and result formatting.
    """

    @staticmethod
    def parse_search_query(query_string: str) -> Dict[str, Any]:
        """
        Parse search query string into filter dictionary.

        Supports filter syntax:
        - `author:username` - filter by author (partial match)
        - `author_id:123456` - filter by exact author ID
        - `channel:channel_id` - filter by channel
        - `server:server_id` - filter by server
        - `platform:discord` or `platform:telegram` - filter by platform
        - `from:YYYY-MM-DD` - messages from date (inclusive)
        - `to:YYYY-MM-DD` - messages until date (inclusive)
        - `has:image` - messages with images
        - Free text for content search (everything not matching filters)

        Args:
            query_string: Raw search query from user

        Returns:
            Dictionary of filters compatible with SearchDAO

        Example:
            >>> filters = SearchService.parse_search_query(
            ...     "hello author:john from:2025-11-01 to:2025-11-15"
            ... )
            >>> print(filters)
            {
                'text_query': 'hello',
                'author_username': 'john',
                'date_from': date(2025, 11, 1),
                'date_to': date(2025, 11, 15)
            }
        """
        if not query_string or not query_string.strip():
            return {}

        filters = {}
        remaining_text = []

        # Split query into tokens
        tokens = query_string.split()

        for token in tokens:
            # Check for filter patterns
            if ':' in token:
                filter_type, value = token.split(':', 1)
                filter_type = filter_type.lower()

                # Author username filter
                if filter_type == 'author':
                    filters['author_username'] = value

                # Author ID filter
                elif filter_type == 'author_id':
                    filters['author_id'] = value

                # Channel filter
                elif filter_type == 'channel':
                    filters['channel_id'] = value

                # Server filter
                elif filter_type == 'server':
                    filters['server_id'] = value

                # Platform filter
                elif filter_type == 'platform':
                    if value.lower() in ['discord', 'telegram']:
                        filters['platform'] = value.lower()
                    else:
                        logger.warning(f"Invalid platform value: {value}")
                        remaining_text.append(token)

                # Date from filter
                elif filter_type == 'from':
                    try:
                        filters['date_from'] = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        logger.warning(f"Invalid date format for 'from': {value}")
                        remaining_text.append(token)

                # Date to filter
                elif filter_type == 'to':
                    try:
                        filters['date_to'] = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        logger.warning(f"Invalid date format for 'to': {value}")
                        remaining_text.append(token)

                # Has filter (currently only supports 'image')
                elif filter_type == 'has':
                    if value.lower() == 'image':
                        filters['has_image'] = True
                    else:
                        logger.warning(f"Unknown 'has' filter value: {value}")
                        remaining_text.append(token)

                # Unknown filter - treat as text
                else:
                    remaining_text.append(token)
            else:
                # Not a filter, add to text query
                remaining_text.append(token)

        # Combine remaining tokens as text query
        if remaining_text:
            filters['text_query'] = ' '.join(remaining_text)

        logger.debug(f"Parsed search query: {filters}")
        return filters

    @staticmethod
    async def execute_search(
        conn,
        user_id: int,
        query_string: str,
        page: int = 1,
        results_per_page: int = 10,
    ) -> Dict[str, Any]:
        """
        Execute search and return formatted results with pagination info.

        Args:
            conn: Database connection
            user_id: User ID executing the search
            query_string: Raw search query string
            page: Page number (1-indexed)
            results_per_page: Number of results per page (default: 10)

        Returns:
            Dictionary with:
                - results: List of message dictionaries
                - total_count: Total number of matching messages
                - page: Current page number
                - total_pages: Total number of pages
                - has_next: Whether there's a next page
                - has_prev: Whether there's a previous page
                - filters: Parsed filters dictionary
                - query_string: Original query string

        Example:
            >>> result = await SearchService.execute_search(
            ...     conn, user_id=1, query_string="hello author:john", page=1
            ... )
            >>> print(f"Found {result['total_count']} messages")
            >>> for msg in result['results']:
            ...     print(f"{msg['author_name']}: {msg['content']}")
        """
        from ..database.dao.search_dao import SearchDAO

        # Parse query
        filters = SearchService.parse_search_query(query_string)

        # Validate page number
        if page < 1:
            page = 1

        # Calculate offset
        offset = (page - 1) * results_per_page

        # Get total count
        total_count = await SearchDAO.count_search_results(conn, user_id, filters)

        # Calculate pagination info
        total_pages = (total_count + results_per_page - 1) // results_per_page
        if total_pages == 0:
            total_pages = 1

        # Ensure page is within bounds
        if page > total_pages:
            page = total_pages
            offset = (page - 1) * results_per_page

        # Execute search
        results = await SearchDAO.search_messages(
            conn,
            user_id,
            filters,
            limit=results_per_page,
            offset=offset,
        )

        return {
            'results': results,
            'total_count': total_count,
            'page': page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
            'filters': filters,
            'query_string': query_string,
        }

    @staticmethod
    def format_filters_summary(filters: Dict[str, Any]) -> str:
        """
        Format filters dictionary into human-readable summary.

        Args:
            filters: Dictionary of search filters

        Returns:
            Formatted summary string

        Example:
            >>> filters = {
            ...     'text_query': 'hello',
            ...     'author_username': 'john',
            ...     'date_from': date(2025, 11, 1)
            ... }
            >>> summary = SearchService.format_filters_summary(filters)
            >>> print(summary)
            Text: "hello"
            Author: john
            From: 2025-11-01
        """
        if not filters:
            return "No filters applied"

        lines = []

        if filters.get('text_query'):
            lines.append(f'Text: "{filters["text_query"]}"')

        if filters.get('author_username'):
            lines.append(f"Author: {filters['author_username']}")

        if filters.get('author_id'):
            lines.append(f"Author ID: {filters['author_id']}")

        if filters.get('channel_id'):
            channel_short = str(filters['channel_id'])[:12]
            lines.append(f"Channel: {channel_short}...")

        if filters.get('server_id'):
            server_short = str(filters['server_id'])[:12]
            lines.append(f"Server: {server_short}...")

        if filters.get('platform'):
            lines.append(f"Platform: {filters['platform'].title()}")

        if filters.get('date_from'):
            date_str = filters['date_from']
            if isinstance(date_str, (date, datetime)):
                date_str = date_str.strftime('%Y-%m-%d')
            lines.append(f"From: {date_str}")

        if filters.get('date_to'):
            date_str = filters['date_to']
            if isinstance(date_str, (date, datetime)):
                date_str = date_str.strftime('%Y-%m-%d')
            lines.append(f"To: {date_str}")

        if filters.get('has_image'):
            lines.append("With images only")

        return '\n'.join(lines) if lines else "No filters applied"

    @staticmethod
    def highlight_text(content: str, search_query: Optional[str], max_length: int = 150) -> str:
        """
        Highlight search terms in content and truncate if needed.

        Args:
            content: Message content
            search_query: Search query to highlight
            max_length: Maximum length of returned text

        Returns:
            Truncated content with search terms highlighted (using *)

        Example:
            >>> text = SearchService.highlight_text(
            ...     "Hello world, this is a test message",
            ...     "world",
            ...     max_length=30
            ... )
            >>> print(text)
            Hello *world*, this is a...
        """
        if not content:
            return "[No content]"

        # Truncate long content
        if len(content) > max_length:
            # Try to find search query in content and center around it
            if search_query:
                # Find first occurrence of any search term
                terms = search_query.lower().split()
                for term in terms:
                    pos = content.lower().find(term)
                    if pos != -1:
                        # Center around the found term
                        start = max(0, pos - max_length // 2)
                        end = min(len(content), start + max_length)

                        # Adjust start if we're at the end
                        if end - start < max_length:
                            start = max(0, end - max_length)

                        excerpt = content[start:end]
                        if start > 0:
                            excerpt = "..." + excerpt
                        if end < len(content):
                            excerpt = excerpt + "..."

                        content = excerpt
                        break
                else:
                    # No match found, just truncate from start
                    content = content[:max_length] + "..."
            else:
                content = content[:max_length] + "..."

        # Highlight search terms (simple version without regex)
        if search_query:
            terms = search_query.split()
            for term in terms:
                # Case-insensitive replace
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                content = pattern.sub(f"*{term}*", content)

        return content

    @staticmethod
    def get_search_help_text() -> str:
        """
        Get help text for search command syntax.

        Returns:
            Formatted help text string
        """
        return """🔍 Search Syntax Help

**Filter Options:**
• `author:username` - Filter by author (partial match)
• `author_id:123456` - Filter by exact author ID
• `channel:channel_id` - Filter by channel
• `server:server_id` - Filter by server (Discord)
• `platform:discord` or `platform:telegram` - Filter by platform
• `from:YYYY-MM-DD` - Messages from date
• `to:YYYY-MM-DD` - Messages until date
• `has:image` - Only messages with images

**Text Search:**
Any text without a filter prefix will search message content.

**Examples:**
• `/search hello` - Search for "hello" in all messages
• `/search author:john hello` - Search "hello" from user john
• `/search from:2025-11-01 to:2025-11-15` - Messages in date range
• `/search platform:discord server:123456 important` - Search "important" in specific Discord server
• `/search author:alice has:image` - Images from user alice

**Tips:**
• Combine multiple filters for precise results
• Dates use YYYY-MM-DD format
• Text search is case-insensitive
• Use pagination buttons to navigate results"""
