"""
Comprehensive unit tests for search functionality.

This module provides extensive testing for:
- SearchDAO: Database access layer for message searches with advanced filtering
- SearchService: Query parsing, search execution, and result formatting
- Integration: Command handlers and callback handlers for search UI

All tests use mocked database connections and follow pytest best practices.
"""
import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, date, timedelta
from typing import Dict, List, Any

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from database.dao.search_dao import SearchDAO
from services.search import SearchService, SearchQuery


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_conn():
    """Mock asyncpg database connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def sample_messages():
    """Sample message records for testing."""
    return [
        {
            'id': 1,
            'platform': 'discord',
            'ext_message_id': '123456789',
            'server_id': '111111111',
            'channel_id': '222222222',
            'thread_id': None,
            'author_id': '333333333',
            'author_name': 'JohnDoe',
            'content': 'Hello world, this is a test message',
            'has_image': False,
            'context_ref': None,
            'created_at': datetime(2025, 11, 15, 10, 0, 0),
            'platform_created_at': datetime(2025, 11, 15, 10, 0, 0),
        },
        {
            'id': 2,
            'platform': 'discord',
            'ext_message_id': '123456790',
            'server_id': '111111111',
            'channel_id': '222222222',
            'thread_id': None,
            'author_id': '444444444',
            'author_name': 'AliceSmith',
            'content': 'Hello everyone, welcome to the channel!',
            'has_image': True,
            'context_ref': None,
            'created_at': datetime(2025, 11, 16, 12, 30, 0),
            'platform_created_at': datetime(2025, 11, 16, 12, 30, 0),
        },
        {
            'id': 3,
            'platform': 'telegram',
            'ext_message_id': '987654321',
            'server_id': None,
            'channel_id': '555555555',
            'thread_id': None,
            'author_id': '666666666',
            'author_name': 'BobJones',
            'content': 'Important announcement about the project',
            'has_image': False,
            'context_ref': None,
            'created_at': datetime(2025, 11, 10, 8, 15, 0),
            'platform_created_at': datetime(2025, 11, 10, 8, 15, 0),
        },
    ]


@pytest.fixture
def sample_user():
    """Sample user record for testing."""
    return {
        'id': 1,
        'telegram_user_id': 123456,
        'username': 'testuser',
        'created_at': datetime(2025, 11, 1, 0, 0, 0),
    }


# =============================================================================
# SearchDAO Tests
# =============================================================================

class TestSearchDAO:
    """Test suite for SearchDAO database operations."""

    @pytest.mark.asyncio
    async def test_search_messages_text_filter(self, mock_conn, sample_messages):
        """Test basic text search with ILIKE pattern matching."""
        # Arrange
        filters = {'text_query': 'hello'}
        mock_conn.fetch.return_value = [
            Mock(**msg) for msg in sample_messages[:2]
        ]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'content ILIKE' in query
        assert '%hello%' in params
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_messages_author_filter(self, mock_conn, sample_messages):
        """Test search by author username with partial match."""
        # Arrange
        filters = {'author_username': 'john'}
        mock_conn.fetch.return_value = [Mock(**sample_messages[0])]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'author_name ILIKE' in query
        assert '%john%' in params
        assert len(result) == 1
        assert result[0]['author_name'] == 'JohnDoe'

    @pytest.mark.asyncio
    async def test_search_messages_channel_filter(self, mock_conn, sample_messages):
        """Test filtering by specific channel ID."""
        # Arrange
        filters = {'channel_id': '222222222'}
        mock_conn.fetch.return_value = [
            Mock(**msg) for msg in sample_messages[:2]
        ]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'channel_id =' in query
        assert '222222222' in params
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_messages_server_filter(self, mock_conn, sample_messages):
        """Test filtering by Discord server ID."""
        # Arrange
        filters = {'server_id': '111111111'}
        mock_conn.fetch.return_value = [
            Mock(**msg) for msg in sample_messages[:2]
        ]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'server_id =' in query
        assert '111111111' in params
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_messages_platform_filter(self, mock_conn, sample_messages):
        """Test filtering by platform (discord/telegram)."""
        # Arrange
        filters = {'platform': 'discord'}
        mock_conn.fetch.return_value = [
            Mock(**msg) for msg in sample_messages[:2]
        ]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'platform =' in query
        assert 'discord' in params
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_messages_date_from(self, mock_conn, sample_messages):
        """Test filtering messages after a specific date."""
        # Arrange
        filters = {'date_from': date(2025, 11, 15)}
        mock_conn.fetch.return_value = [
            Mock(**msg) for msg in sample_messages[:2]
        ]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'created_at >=' in query
        assert date(2025, 11, 15) in params
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_messages_date_to(self, mock_conn, sample_messages):
        """Test filtering messages before a specific date."""
        # Arrange
        filters = {'date_to': date(2025, 11, 10)}
        mock_conn.fetch.return_value = [Mock(**sample_messages[2])]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'created_at <' in query
        assert date(2025, 11, 10) in params
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_messages_date_range(self, mock_conn, sample_messages):
        """Test filtering with both from and to dates."""
        # Arrange
        filters = {
            'date_from': date(2025, 11, 14),
            'date_to': date(2025, 11, 16)
        }
        mock_conn.fetch.return_value = [
            Mock(**msg) for msg in sample_messages[:2]
        ]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'created_at >=' in query
        assert 'created_at <' in query
        assert date(2025, 11, 14) in params
        assert date(2025, 11, 16) in params
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_messages_has_image(self, mock_conn, sample_messages):
        """Test filtering messages that contain images."""
        # Arrange
        filters = {'has_image': True}
        mock_conn.fetch.return_value = [Mock(**sample_messages[1])]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'has_image =' in query
        assert True in params
        assert len(result) == 1
        assert result[0]['has_image'] is True

    @pytest.mark.asyncio
    async def test_search_messages_pagination(self, mock_conn, sample_messages):
        """Test pagination with limit and offset."""
        # Arrange
        filters = {}
        mock_conn.fetch.return_value = [Mock(**sample_messages[1])]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=1, offset=1
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'LIMIT' in query
        assert 'OFFSET' in query
        assert 1 in params  # limit
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_messages_no_results(self, mock_conn):
        """Test search returning empty result set."""
        # Arrange
        filters = {'text_query': 'nonexistent'}
        mock_conn.fetch.return_value = []

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_count_search_results(self, mock_conn):
        """Test counting total matching messages."""
        # Arrange
        filters = {'text_query': 'hello'}
        mock_conn.fetchrow.return_value = {'count': 42}

        # Act
        count = await SearchDAO.count_search_results(
            mock_conn, user_id=1, filters=filters
        )

        # Assert
        assert mock_conn.fetchrow.called
        call_args = mock_conn.fetchrow.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'COUNT(*)' in query
        assert 'content ILIKE' in query
        assert '%hello%' in params
        assert count == 42

    @pytest.mark.asyncio
    async def test_search_messages_fulltext(self, mock_conn, sample_messages):
        """Test full-text search using PostgreSQL tsvector."""
        # Arrange
        search_query = 'hello & world'
        filters = {'channel_id': '222222222'}
        mock_conn.fetch.return_value = [Mock(**sample_messages[0])]

        # Act
        result = await SearchDAO.search_messages_fulltext(
            mock_conn, user_id=1, search_query=search_query,
            filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'content_tsvector' in query
        assert 'to_tsquery' in query
        assert 'ts_rank' in query
        assert search_query in params
        assert '222222222' in params
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_messages_combined_filters(self, mock_conn, sample_messages):
        """Test searching with multiple combined filters."""
        # Arrange
        filters = {
            'text_query': 'hello',
            'author_username': 'alice',
            'platform': 'discord',
            'date_from': date(2025, 11, 1),
            'has_image': True
        }
        mock_conn.fetch.return_value = [Mock(**sample_messages[1])]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        # Verify all filters are in the query
        assert 'content ILIKE' in query
        assert 'author_name ILIKE' in query
        assert 'platform =' in query
        assert 'created_at >=' in query
        assert 'has_image =' in query
        assert ' AND ' in query
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_messages_author_id_filter(self, mock_conn, sample_messages):
        """Test filtering by exact author ID."""
        # Arrange
        filters = {'author_id': '333333333'}
        mock_conn.fetch.return_value = [Mock(**sample_messages[0])]

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert 'author_id =' in query
        assert '333333333' in params
        assert len(result) == 1


# =============================================================================
# SearchService Tests
# =============================================================================

class TestSearchService:
    """Test suite for SearchService query parsing and formatting."""

    def test_parse_search_query_simple(self):
        """Test parsing plain text query without filters."""
        # Act
        filters = SearchService.parse_search_query("hello world")

        # Assert
        assert filters == {'text_query': 'hello world'}

    def test_parse_search_query_author(self):
        """Test parsing author filter from query string."""
        # Act
        filters = SearchService.parse_search_query("author:john hello")

        # Assert
        assert filters['author_username'] == 'john'
        assert filters['text_query'] == 'hello'

    def test_parse_search_query_channel(self):
        """Test parsing channel filter from query string."""
        # Act
        filters = SearchService.parse_search_query("channel:123456 test")

        # Assert
        assert filters['channel_id'] == '123456'
        assert filters['text_query'] == 'test'

    def test_parse_search_query_server(self):
        """Test parsing server filter from query string."""
        # Act
        filters = SearchService.parse_search_query("server:987654 message")

        # Assert
        assert filters['server_id'] == '987654'
        assert filters['text_query'] == 'message'

    def test_parse_search_query_platform(self):
        """Test parsing platform filter (discord/telegram)."""
        # Act - Discord
        filters_discord = SearchService.parse_search_query("platform:discord test")
        assert filters_discord['platform'] == 'discord'
        assert filters_discord['text_query'] == 'test'

        # Act - Telegram
        filters_telegram = SearchService.parse_search_query("platform:telegram test")
        assert filters_telegram['platform'] == 'telegram'
        assert filters_telegram['text_query'] == 'test'

    def test_parse_search_query_dates(self):
        """Test parsing from and to date filters."""
        # Act
        filters = SearchService.parse_search_query(
            "from:2025-11-01 to:2025-11-15 important"
        )

        # Assert
        assert filters['date_from'] == date(2025, 11, 1)
        assert filters['date_to'] == date(2025, 11, 15)
        assert filters['text_query'] == 'important'

    def test_parse_search_query_has_image(self):
        """Test parsing has:image filter."""
        # Act
        filters = SearchService.parse_search_query("has:image from:alice")

        # Assert
        assert filters['has_image'] is True
        assert filters['text_query'] == 'from:alice'  # 'from' without date format

    def test_parse_search_query_complex(self):
        """Test parsing query with multiple combined filters."""
        # Act
        filters = SearchService.parse_search_query(
            "hello world author:john platform:discord from:2025-11-01 has:image"
        )

        # Assert
        assert filters['text_query'] == 'hello world'
        assert filters['author_username'] == 'john'
        assert filters['platform'] == 'discord'
        assert filters['date_from'] == date(2025, 11, 1)
        assert filters['has_image'] is True

    @pytest.mark.asyncio
    async def test_execute_search(self, mock_conn, sample_messages):
        """Test executing search with pagination."""
        # Arrange
        query_string = "hello author:john"

        with patch('services.search.SearchDAO') as mock_dao:
            mock_dao.search_messages = AsyncMock(return_value=sample_messages[:1])
            mock_dao.count_search_results = AsyncMock(return_value=1)

            # Act
            result = await SearchService.execute_search(
                mock_conn, user_id=1, query_string=query_string,
                page=1, results_per_page=10
            )

            # Assert
            assert result['results'] == sample_messages[:1]
            assert result['total_count'] == 1
            assert result['page'] == 1
            assert result['total_pages'] == 1
            assert result['has_next'] is False
            assert result['has_prev'] is False
            assert result['filters']['text_query'] == 'hello'
            assert result['filters']['author_username'] == 'john'
            assert result['query_string'] == query_string

    @pytest.mark.asyncio
    async def test_execute_search_pagination_multiple_pages(self, mock_conn):
        """Test execute search with multiple pages."""
        # Arrange
        query_string = "test"

        with patch('services.search.SearchDAO') as mock_dao:
            mock_dao.search_messages = AsyncMock(return_value=[])
            mock_dao.count_search_results = AsyncMock(return_value=25)

            # Act - Page 2 of 3 (10 results per page)
            result = await SearchService.execute_search(
                mock_conn, user_id=1, query_string=query_string,
                page=2, results_per_page=10
            )

            # Assert
            assert result['page'] == 2
            assert result['total_pages'] == 3
            assert result['has_next'] is True
            assert result['has_prev'] is True

    def test_format_filters_summary(self):
        """Test formatting filters into human-readable summary."""
        # Arrange
        filters = {
            'text_query': 'hello',
            'author_username': 'john',
            'date_from': date(2025, 11, 1),
            'date_to': date(2025, 11, 15),
            'platform': 'discord',
            'has_image': True
        }

        # Act
        summary = SearchService.format_filters_summary(filters)

        # Assert
        assert 'Text: "hello"' in summary
        assert 'Author: john' in summary
        assert 'From: 2025-11-01' in summary
        assert 'To: 2025-11-15' in summary
        assert 'Platform: Discord' in summary
        assert 'With images only' in summary

    def test_format_filters_summary_empty(self):
        """Test formatting empty filters dictionary."""
        # Act
        summary = SearchService.format_filters_summary({})

        # Assert
        assert summary == "No filters applied"

    def test_highlight_text(self):
        """Test highlighting search terms in content."""
        # Arrange
        content = "Hello world, this is a test message with hello again"
        search_query = "hello"

        # Act
        result = SearchService.highlight_text(content, search_query, max_length=100)

        # Assert
        assert '*hello*' in result.lower()
        assert len(result) <= 100

    def test_highlight_text_truncate_long_content(self):
        """Test truncating long content around search term."""
        # Arrange
        content = "A" * 100 + "SEARCH_TERM" + "B" * 100
        search_query = "SEARCH_TERM"

        # Act
        result = SearchService.highlight_text(content, search_query, max_length=50)

        # Assert
        assert 'SEARCH_TERM' in result
        assert len(result) <= 60  # Accounting for ellipsis
        assert '...' in result

    def test_highlight_text_no_query(self):
        """Test highlighting with no search query provided."""
        # Arrange
        content = "This is a test message"

        # Act
        result = SearchService.highlight_text(content, None, max_length=50)

        # Assert
        assert result == content

    def test_get_search_help_text(self):
        """Test generating search help text."""
        # Act
        help_text = SearchService.get_search_help_text()

        # Assert
        assert 'Search Syntax Help' in help_text
        assert 'author:' in help_text
        assert 'channel:' in help_text
        assert 'from:' in help_text
        assert 'to:' in help_text
        assert 'has:image' in help_text
        assert 'Examples:' in help_text

    def test_parse_search_query_invalid_date_format(self):
        """Test handling invalid date format gracefully."""
        # Act
        filters = SearchService.parse_search_query("from:invalid-date test")

        # Assert
        # Invalid date should be treated as text
        assert 'date_from' not in filters
        assert 'from:invalid-date test' in filters.get('text_query', '')

    def test_parse_search_query_empty(self):
        """Test parsing empty query string."""
        # Act
        filters = SearchService.parse_search_query("")

        # Assert
        assert filters == {}

    def test_parse_search_query_whitespace_only(self):
        """Test parsing query with only whitespace."""
        # Act
        filters = SearchService.parse_search_query("   \t\n  ")

        # Assert
        assert filters == {}


# =============================================================================
# Integration Tests
# =============================================================================

class TestSearchIntegration:
    """Integration tests for search command handlers and callbacks."""

    @pytest.mark.asyncio
    async def test_cmd_search_no_query(self):
        """Test /search command with no query shows help."""
        # Arrange
        from telegram.handlers import cmd_search

        message = {
            'from': {'id': 123456},
            'text': '/search'
        }
        bot = AsyncMock()
        bot.send_message = AsyncMock()

        # Act
        await cmd_search(message, bot)

        # Assert
        bot.send_message.assert_called_once()
        call_args = bot.send_message.call_args
        assert call_args[0][0] == 123456  # user_id
        assert 'Search Syntax Help' in call_args[0][1] or 'search' in call_args[0][1].lower()
        assert 'reply_markup' in call_args[1]

    @pytest.mark.asyncio
    async def test_cmd_search_with_results(self, sample_messages, sample_user):
        """Test /search command displaying search results."""
        # Arrange
        from telegram.handlers import cmd_search

        message = {
            'from': {'id': 123456},
            'text': '/search hello'
        }
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        bot.set_search_state = Mock()

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
            with patch('telegram.handlers.UserDAO') as mock_user_dao:
                with patch('telegram.handlers.SearchService') as mock_search_service:
                    mock_user_dao.get_user_by_tg_id = AsyncMock(return_value=sample_user)
                    mock_search_service.execute_search = AsyncMock(return_value={
                        'results': sample_messages,
                        'total_count': 3,
                        'page': 1,
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False,
                        'filters': {'text_query': 'hello'},
                        'query_string': 'hello'
                    })

                    # Act
                    await cmd_search(message, bot)

                    # Assert
                    bot.send_message.assert_called_once()
                    bot.set_search_state.assert_called_once_with(
                        123456,
                        {'query_string': 'hello', 'current_page': 1}
                    )

    @pytest.mark.asyncio
    async def test_cmd_search_empty_results(self, sample_user):
        """Test /search command with no matching results."""
        # Arrange
        from telegram.handlers import cmd_search

        message = {
            'from': {'id': 123456},
            'text': '/search nonexistent'
        }
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        bot.set_search_state = Mock()

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
            with patch('telegram.handlers.UserDAO') as mock_user_dao:
                with patch('telegram.handlers.SearchService') as mock_search_service:
                    mock_user_dao.get_user_by_tg_id = AsyncMock(return_value=sample_user)
                    mock_search_service.execute_search = AsyncMock(return_value={
                        'results': [],
                        'total_count': 0,
                        'page': 1,
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False,
                        'filters': {'text_query': 'nonexistent'},
                        'query_string': 'nonexistent'
                    })

                    # Act
                    await cmd_search(message, bot)

                    # Assert
                    bot.send_message.assert_called_once()
                    call_args = bot.send_message.call_args
                    # Should still send results (even if empty)
                    assert call_args[0][0] == 123456

    @pytest.mark.asyncio
    async def test_cmd_search_pagination(self, sample_user):
        """Test /search command with paginated results."""
        # Arrange
        from telegram.handlers import cmd_search

        message = {
            'from': {'id': 123456},
            'text': '/search test'
        }
        bot = AsyncMock()
        bot.send_message = AsyncMock()
        bot.set_search_state = Mock()

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
            with patch('telegram.handlers.UserDAO') as mock_user_dao:
                with patch('telegram.handlers.SearchService') as mock_search_service:
                    mock_user_dao.get_user_by_tg_id = AsyncMock(return_value=sample_user)
                    mock_search_service.execute_search = AsyncMock(return_value={
                        'results': [],
                        'total_count': 25,
                        'page': 1,
                        'total_pages': 3,
                        'has_next': True,
                        'has_prev': False,
                        'filters': {'text_query': 'test'},
                        'query_string': 'test'
                    })

                    # Act
                    await cmd_search(message, bot)

                    # Assert
                    bot.send_message.assert_called_once()
                    # Keyboard should include next page button
                    call_args = bot.send_message.call_args
                    assert 'reply_markup' in call_args[1]

    @pytest.mark.asyncio
    async def test_callback_search_page(self, sample_messages, sample_user):
        """Test navigating to different search result pages."""
        # Arrange
        from telegram.handlers import callback_search_page

        query = {
            'from': {'id': 123456},
            'message': {
                'chat': {'id': 123456},
                'message_id': 789
            },
            'data': 'search_page_2',
            'id': 'callback_123'
        }
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock()
        bot.answer_callback_query = AsyncMock()
        bot.get_search_state = Mock(return_value={
            'query_string': 'hello',
            'current_page': 1
        })
        bot.set_search_state = Mock()

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
            with patch('telegram.handlers.UserDAO') as mock_user_dao:
                with patch('telegram.handlers.SearchService') as mock_search_service:
                    mock_user_dao.get_user_by_tg_id = AsyncMock(return_value=sample_user)
                    mock_search_service.execute_search = AsyncMock(return_value={
                        'results': sample_messages,
                        'total_count': 20,
                        'page': 2,
                        'total_pages': 2,
                        'has_next': False,
                        'has_prev': True,
                        'filters': {'text_query': 'hello'},
                        'query_string': 'hello'
                    })

                    # Act
                    await callback_search_page(query, bot)

                    # Assert
                    bot.edit_message_text.assert_called_once()
                    bot.answer_callback_query.assert_called_once()
                    bot.set_search_state.assert_called_once_with(
                        123456,
                        {'query_string': 'hello', 'current_page': 2}
                    )

    @pytest.mark.asyncio
    async def test_callback_search_new(self):
        """Test starting a new search from search results."""
        # Arrange
        from telegram.handlers import callback_search_new

        query = {
            'from': {'id': 123456},
            'message': {
                'chat': {'id': 123456},
                'message_id': 789
            },
            'id': 'callback_123'
        }
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock()
        bot.answer_callback_query = AsyncMock()

        # Act
        await callback_search_new(query, bot)

        # Assert
        bot.edit_message_text.assert_called_once()
        call_args = bot.edit_message_text.call_args
        assert 'search' in call_args[0][2].lower()
        bot.answer_callback_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_search_help(self):
        """Test showing search help from search results."""
        # Arrange
        from telegram.handlers import callback_search_help

        query = {
            'from': {'id': 123456},
            'message': {
                'chat': {'id': 123456},
                'message_id': 789
            },
            'id': 'callback_123'
        }
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock()
        bot.answer_callback_query = AsyncMock()

        # Act
        await callback_search_help(query, bot)

        # Assert
        bot.edit_message_text.assert_called_once()
        call_args = bot.edit_message_text.call_args
        assert 'Search Syntax Help' in call_args[0][2] or 'search' in call_args[0][2].lower()
        bot.answer_callback_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_search_example(self, sample_user):
        """Test running an example search."""
        # Arrange
        from telegram.handlers import callback_search_example

        query = {
            'from': {'id': 123456},
            'message': {
                'chat': {'id': 123456},
                'message_id': 789
            },
            'id': 'callback_123'
        }
        bot = AsyncMock()
        bot.edit_message_text = AsyncMock()
        bot.answer_callback_query = AsyncMock()
        bot.set_search_state = Mock()

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
            with patch('telegram.handlers.UserDAO') as mock_user_dao:
                with patch('telegram.handlers.SearchService') as mock_search_service:
                    mock_user_dao.get_user_by_tg_id = AsyncMock(return_value=sample_user)
                    mock_search_service.execute_search = AsyncMock(return_value={
                        'results': [],
                        'total_count': 0,
                        'page': 1,
                        'total_pages': 1,
                        'has_next': False,
                        'has_prev': False,
                        'filters': {},
                        'query_string': 'from:2025-10-20'
                    })

                    # Act
                    await callback_search_example(query, bot)

                    # Assert
                    bot.edit_message_text.assert_called_once()
                    # Should execute a search with example query
                    mock_search_service.execute_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_search_page_expired_session(self):
        """Test handling expired search session."""
        # Arrange
        from telegram.handlers import callback_search_page

        query = {
            'from': {'id': 123456},
            'message': {
                'chat': {'id': 123456},
                'message_id': 789
            },
            'data': 'search_page_2',
            'id': 'callback_123'
        }
        bot = AsyncMock()
        bot.answer_callback_query = AsyncMock()
        bot.get_search_state = Mock(return_value=None)  # Expired session

        # Act
        await callback_search_page(query, bot)

        # Assert
        bot.answer_callback_query.assert_called_once()
        call_args = bot.answer_callback_query.call_args
        assert 'expired' in call_args[0][1].lower() or 'new search' in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_cmd_search_user_not_found(self):
        """Test /search command when user is not in database."""
        # Arrange
        from telegram.handlers import cmd_search

        message = {
            'from': {'id': 123456},
            'text': '/search hello'
        }
        bot = AsyncMock()
        bot.send_message = AsyncMock()

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch('telegram.handlers.get_asyncpg_pool', return_value=mock_pool):
            with patch('telegram.handlers.UserDAO') as mock_user_dao:
                mock_user_dao.get_user_by_tg_id = AsyncMock(return_value=None)

                # Act
                await cmd_search(message, bot)

                # Assert
                bot.send_message.assert_called_once()
                call_args = bot.send_message.call_args
                assert 'not found' in call_args[0][1].lower() or '/start' in call_args[0][1].lower()


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestSearchEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_search_messages_with_datetime_filter(self, mock_conn):
        """Test date filter with datetime instead of date object."""
        # Arrange
        filters = {'date_from': datetime(2025, 11, 15, 10, 0, 0)}
        mock_conn.fetch.return_value = []

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_search_messages_with_string_date_filter(self, mock_conn):
        """Test date filter with string date format."""
        # Arrange
        filters = {
            'date_from': '2025-11-15',
            'date_to': '2025-11-20'
        }
        mock_conn.fetch.return_value = []

        # Act
        result = await SearchDAO.search_messages(
            mock_conn, user_id=1, filters=filters, limit=10, offset=0
        )

        # Assert
        assert mock_conn.fetch.called
        call_args = mock_conn.fetch.call_args
        query = call_args[0][0]
        assert '::timestamp' in query  # String dates should be cast

    @pytest.mark.asyncio
    async def test_count_search_results_all_filters(self, mock_conn):
        """Test count with all possible filters."""
        # Arrange
        filters = {
            'text_query': 'test',
            'author_username': 'john',
            'author_id': '123',
            'channel_id': '456',
            'server_id': '789',
            'platform': 'discord',
            'has_image': True,
            'date_from': date(2025, 11, 1),
            'date_to': date(2025, 11, 30)
        }
        mock_conn.fetchrow.return_value = {'count': 5}

        # Act
        count = await SearchDAO.count_search_results(
            mock_conn, user_id=1, filters=filters
        )

        # Assert
        assert mock_conn.fetchrow.called
        assert count == 5

    def test_parse_search_query_unknown_filter(self):
        """Test that unknown filters are treated as text."""
        # Act
        filters = SearchService.parse_search_query("unknown:value test")

        # Assert
        assert 'unknown' not in filters
        assert filters.get('text_query') == 'unknown:value test'

    def test_highlight_text_empty_content(self):
        """Test highlighting with empty content."""
        # Act
        result = SearchService.highlight_text("", "test")

        # Assert
        assert result == "[No content]"

    @pytest.mark.asyncio
    async def test_execute_search_invalid_page_number(self, mock_conn):
        """Test execute search with invalid page number (< 1)."""
        # Arrange
        with patch('services.search.SearchDAO') as mock_dao:
            mock_dao.search_messages = AsyncMock(return_value=[])
            mock_dao.count_search_results = AsyncMock(return_value=0)

            # Act - Page 0 should be normalized to page 1
            result = await SearchService.execute_search(
                mock_conn, user_id=1, query_string="test",
                page=0, results_per_page=10
            )

            # Assert
            assert result['page'] == 1

    @pytest.mark.asyncio
    async def test_execute_search_page_beyond_total(self, mock_conn):
        """Test execute search requesting page beyond total pages."""
        # Arrange
        with patch('services.search.SearchDAO') as mock_dao:
            mock_dao.search_messages = AsyncMock(return_value=[])
            mock_dao.count_search_results = AsyncMock(return_value=5)

            # Act - Request page 5 when only 1 page exists
            result = await SearchService.execute_search(
                mock_conn, user_id=1, query_string="test",
                page=5, results_per_page=10
            )

            # Assert
            # Should return last valid page
            assert result['page'] == 1
            assert result['total_pages'] == 1
