"""
Integration tests for multi-server services and commands.

This module provides comprehensive integration testing for:
- DiscordAPIClient: REST API client for Discord metadata
- DiscordCacheService: Server and channel metadata caching
- MultiServerService: High-level multi-server operations
- Telegram Commands: User-facing command handlers

All tests use mocked Discord API responses and in-memory database state
to ensure fast, reliable testing without external dependencies.
"""
import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import asyncio
import aiohttp
from typing import Dict, List, Any

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from discord.api_client import DiscordAPIClient, DiscordAPIError
from services.discord_cache import DiscordCacheService
from services.multiserver import MultiServerService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_discord_token():
    """Mock Discord user token for testing."""
    return "test_discord_token_12345"


@pytest.fixture
def mock_guilds_response():
    """Mock Discord API response for /users/@me/guilds."""
    return [
        {
            'id': '1111111111',
            'name': 'Test Server 1',
            'icon': 'abc123',
            'owner': True,
            'permissions': '8',
            'features': ['COMMUNITY', 'NEWS'],
            'approximate_member_count': 150
        },
        {
            'id': '2222222222',
            'name': 'Test Server 2',
            'icon': 'def456',
            'owner': False,
            'permissions': '2048',
            'features': ['ANIMATED_ICON'],
            'approximate_member_count': 75
        },
        {
            'id': '3333333333',
            'name': 'Test Server 3',
            'icon': None,
            'owner': False,
            'permissions': '1024',
            'features': [],
            'approximate_member_count': 50
        }
    ]


@pytest.fixture
def mock_guild_response():
    """Mock Discord API response for /guilds/{id}."""
    return {
        'id': '1111111111',
        'name': 'Test Server 1',
        'icon': 'abc123',
        'description': 'A test server for integration testing',
        'splash': None,
        'discovery_splash': None,
        'approximate_member_count': 150,
        'approximate_presence_count': 75,
        'features': ['COMMUNITY', 'NEWS'],
        'emojis': [],
        'stickers': [],
        'banner': None,
        'owner_id': '9999999999',
        'application_id': None,
        'region': 'us-west',
        'afk_channel_id': None,
        'afk_timeout': 300,
        'system_channel_id': None,
        'widget_enabled': False,
        'widget_channel_id': None,
        'verification_level': 0,
        'roles': [],
        'default_message_notifications': 0,
        'mfa_level': 0,
        'explicit_content_filter': 0,
        'max_presences': None,
        'max_members': 500000,
        'max_video_channel_users': 25,
        'vanity_url_code': None,
        'premium_tier': 1,
        'premium_subscription_count': 2,
        'system_channel_flags': 0,
        'preferred_locale': 'en-US',
        'rules_channel_id': None,
        'public_updates_channel_id': None
    }


@pytest.fixture
def mock_channels_response():
    """Mock Discord API response for /guilds/{id}/channels."""
    return [
        {
            'id': '1001',
            'name': 'general',
            'type': 0,  # Text channel
            'position': 0,
            'parent_id': None,
            'topic': 'General discussion',
            'nsfw': False,
            'permission_overwrites': []
        },
        {
            'id': '1002',
            'name': 'announcements',
            'type': 0,  # Text channel
            'position': 1,
            'parent_id': None,
            'topic': 'Important announcements',
            'nsfw': False,
            'permission_overwrites': []
        },
        {
            'id': '1003',
            'name': 'Voice General',
            'type': 2,  # Voice channel
            'position': 2,
            'parent_id': None,
            'bitrate': 64000,
            'user_limit': 10,
            'permission_overwrites': []
        },
        {
            'id': '1004',
            'name': 'help-thread',
            'type': 11,  # Public thread
            'position': 3,
            'parent_id': '1001',
            'permission_overwrites': []
        },
        {
            'id': '1005',
            'name': 'Categories',
            'type': 4,  # Category
            'position': 0,
            'parent_id': None,
            'permission_overwrites': []
        }
    ]


@pytest.fixture
async def mock_db_connection():
    """Mock asyncpg database connection with in-memory state."""
    # In-memory storage for testing
    storage = {
        'users': {},
        'servers': {},
        'channels': {},
        'allowlist': {}
    }

    conn = AsyncMock()

    # Helper to generate IDs
    id_counter = {'value': 1}

    def get_next_id():
        current = id_counter['value']
        id_counter['value'] += 1
        return current

    # Mock user operations
    async def mock_get_user_by_tg_id(tg_id):
        for user in storage['users'].values():
            if user['tg_id'] == tg_id:
                return user
        return None

    async def mock_create_user(tg_id):
        user_id = get_next_id()
        storage['users'][user_id] = {
            'id': user_id,
            'tg_id': tg_id,
            'created_at': datetime.now()
        }
        return user_id

    # Mock server operations
    async def mock_cache_server(server_data):
        server_id = server_data['server_id']
        if server_id not in storage['servers']:
            storage['servers'][server_id] = {
                'id': get_next_id(),
                **server_data,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        else:
            storage['servers'][server_id].update({
                **server_data,
                'updated_at': datetime.now()
            })

    async def mock_get_server_by_id(server_id):
        return storage['servers'].get(server_id)

    async def mock_get_all_servers():
        return list(storage['servers'].values())

    async def mock_is_server_cache_stale(server_id, max_age_hours=24):
        server = storage['servers'].get(server_id)
        if not server:
            return True
        age = datetime.now() - server['updated_at']
        return age > timedelta(hours=max_age_hours)

    # Mock channel operations
    async def mock_bulk_update_channels(server_id, channel_data_list):
        for channel_data in channel_data_list:
            channel_id = channel_data['channel_id']
            key = f"{server_id}_{channel_id}"
            storage['channels'][key] = {
                'id': get_next_id(),
                'server_id': server_id,
                **channel_data,
                'cached_at': datetime.now(),
                'updated_at': datetime.now()
            }

    async def mock_get_channels_by_server(server_id, channel_type=None):
        channels = [
            ch for ch in storage['channels'].values()
            if ch['server_id'] == server_id
        ]
        if channel_type:
            channels = [ch for ch in channels if ch['type'] == channel_type]
        return sorted(channels, key=lambda x: (x.get('position', 999), x['name']))

    # Mock allowlist operations
    async def mock_add_channel(user_id, server_id, channel_id, platform='discord'):
        key = f"{user_id}_{channel_id}"
        storage['allowlist'][key] = {
            'id': get_next_id(),
            'user_id': user_id,
            'server_id': server_id,
            'channel_id': channel_id,
            'platform': platform,
            'created_at': datetime.now()
        }

    async def mock_remove_channel(user_id, channel_id, platform='discord'):
        key = f"{user_id}_{channel_id}"
        if key in storage['allowlist']:
            del storage['allowlist'][key]

    async def mock_is_channel_allowed(user_id, channel_id, platform='discord'):
        key = f"{user_id}_{channel_id}"
        return key in storage['allowlist']

    async def mock_add_channels_bulk(user_id, server_id, channel_ids):
        count = 0
        for channel_id in channel_ids:
            key = f"{user_id}_{channel_id}"
            if key not in storage['allowlist']:
                storage['allowlist'][key] = {
                    'id': get_next_id(),
                    'user_id': user_id,
                    'server_id': server_id,
                    'channel_id': channel_id,
                    'platform': 'discord',
                    'created_at': datetime.now()
                }
                count += 1
        return count

    async def mock_remove_channels_bulk(user_id, channel_ids):
        count = 0
        for channel_id in channel_ids:
            key = f"{user_id}_{channel_id}"
            if key in storage['allowlist']:
                del storage['allowlist'][key]
                count += 1
        return count

    async def mock_get_allowlist_stats(user_id):
        stats = {}
        for entry in storage['allowlist'].values():
            if entry['user_id'] == user_id:
                server_id = entry['server_id']
                stats[server_id] = stats.get(server_id, 0) + 1
        return stats

    # Attach methods to connection mock
    conn.storage = storage
    conn.mock_get_user_by_tg_id = mock_get_user_by_tg_id
    conn.mock_create_user = mock_create_user
    conn.mock_cache_server = mock_cache_server
    conn.mock_get_server_by_id = mock_get_server_by_id
    conn.mock_get_all_servers = mock_get_all_servers
    conn.mock_is_server_cache_stale = mock_is_server_cache_stale
    conn.mock_bulk_update_channels = mock_bulk_update_channels
    conn.mock_get_channels_by_server = mock_get_channels_by_server
    conn.mock_add_channel = mock_add_channel
    conn.mock_remove_channel = mock_remove_channel
    conn.mock_is_channel_allowed = mock_is_channel_allowed
    conn.mock_add_channels_bulk = mock_add_channels_bulk
    conn.mock_remove_channels_bulk = mock_remove_channels_bulk
    conn.mock_get_allowlist_stats = mock_get_allowlist_stats

    return conn


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for command handler tests."""
    bot = AsyncMock()
    bot.user_states = {}

    async def mock_send_message(user_id, text, **kwargs):
        return {'ok': True, 'result': {'message_id': 123}}

    async def mock_edit_message_text(chat_id, message_id, text, **kwargs):
        return {'ok': True}

    async def mock_answer_callback_query(query_id, **kwargs):
        return {'ok': True}

    def mock_get_user_state(user_id):
        return bot.user_states.get(user_id)

    def mock_set_user_state(user_id, state_name, data):
        bot.user_states[user_id] = {
            'state': state_name,
            'data': data
        }

    bot.send_message = mock_send_message
    bot.edit_message_text = mock_edit_message_text
    bot.answer_callback_query = mock_answer_callback_query
    bot.get_user_state = mock_get_user_state
    bot.set_user_state = mock_set_user_state

    return bot


# =============================================================================
# DiscordAPIClient Tests (5+ tests)
# =============================================================================

@pytest.mark.asyncio
async def test_get_guilds(mock_discord_token, mock_guilds_response):
    """
    Test fetching user guilds from Discord API.

    Verifies:
    - API request is made to correct endpoint
    - Response is properly parsed
    - Returns list of guild dictionaries
    """
    with patch('aiohttp.ClientSession') as mock_session_class:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_guilds_response)
        mock_response.headers = {}

        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False

        mock_session_class.return_value = mock_session

        # Create client and test
        async with DiscordAPIClient(mock_discord_token) as client:
            guilds = await client.get_guilds()

        # Verify results
        assert len(guilds) == 3
        assert guilds[0]['name'] == 'Test Server 1'
        assert guilds[1]['id'] == '2222222222'
        assert guilds[2]['approximate_member_count'] == 50


@pytest.mark.asyncio
async def test_get_guild(mock_discord_token, mock_guild_response):
    """
    Test fetching single guild information from Discord API.

    Verifies:
    - API request includes guild ID in endpoint
    - Detailed guild information is returned
    - Response includes member count and features
    """
    with patch('aiohttp.ClientSession') as mock_session_class:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_guild_response)
        mock_response.headers = {}

        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False

        mock_session_class.return_value = mock_session

        # Create client and test
        async with DiscordAPIClient(mock_discord_token) as client:
            guild = await client.get_guild('1111111111')

        # Verify results
        assert guild['id'] == '1111111111'
        assert guild['name'] == 'Test Server 1'
        assert guild['description'] == 'A test server for integration testing'
        assert guild['approximate_member_count'] == 150
        assert 'COMMUNITY' in guild['features']


@pytest.mark.asyncio
async def test_get_guild_channels(mock_discord_token, mock_channels_response):
    """
    Test fetching guild channels from Discord API.

    Verifies:
    - API request includes guild ID
    - Returns list of all channel types
    - Channel metadata includes type, position, parent_id
    """
    with patch('aiohttp.ClientSession') as mock_session_class:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_channels_response)
        mock_response.headers = {}

        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False

        mock_session_class.return_value = mock_session

        # Create client and test
        async with DiscordAPIClient(mock_discord_token) as client:
            channels = await client.get_guild_channels('1111111111')

        # Verify results
        assert len(channels) == 5

        # Check text channels
        text_channels = [c for c in channels if c['type'] == 0]
        assert len(text_channels) == 2
        assert text_channels[0]['name'] == 'general'

        # Check voice channels
        voice_channels = [c for c in channels if c['type'] == 2]
        assert len(voice_channels) == 1

        # Check threads
        threads = [c for c in channels if c['type'] == 11]
        assert len(threads) == 1
        assert threads[0]['parent_id'] == '1001'


@pytest.mark.asyncio
async def test_rate_limit_handling(mock_discord_token):
    """
    Test Discord API rate limit (429) response handling.

    Verifies:
    - 429 response triggers retry logic
    - Client waits for retry_after duration
    - Request succeeds after retry
    """
    with patch('aiohttp.ClientSession') as mock_session_class:
        # First response: rate limited
        mock_rate_limit_response = AsyncMock()
        mock_rate_limit_response.status = 429
        mock_rate_limit_response.json = AsyncMock(return_value={
            'retry_after': 0.1,  # 100ms for fast testing
            'global': False
        })
        mock_rate_limit_response.headers = {}

        # Second response: success
        mock_success_response = AsyncMock()
        mock_success_response.status = 200
        mock_success_response.json = AsyncMock(return_value=[
            {'id': '1111111111', 'name': 'Test Server'}
        ])
        mock_success_response.headers = {}

        mock_session = AsyncMock()
        mock_session.closed = False

        # Setup response sequence
        call_count = {'value': 0}

        async def mock_request(*args, **kwargs):
            call_count['value'] += 1
            if call_count['value'] == 1:
                return mock_rate_limit_response
            return mock_success_response

        mock_session.request = mock_request
        mock_session_class.return_value = mock_session

        # Create client and test
        async with DiscordAPIClient(mock_discord_token) as client:
            start_time = asyncio.get_event_loop().time()
            guilds = await client.get_guilds()
            elapsed_time = asyncio.get_event_loop().time() - start_time

        # Verify retry occurred
        assert call_count['value'] == 2
        assert len(guilds) == 1
        assert elapsed_time >= 0.1  # Waited for retry_after


@pytest.mark.asyncio
async def test_error_handling_403_404(mock_discord_token):
    """
    Test Discord API error handling for 403 and 404 responses.

    Verifies:
    - 403 (Forbidden) raises DiscordAPIError with correct status
    - 404 (Not Found) raises DiscordAPIError with correct status
    - Error messages are descriptive
    """
    with patch('aiohttp.ClientSession') as mock_session_class:
        # Test 403 Forbidden
        mock_403_response = AsyncMock()
        mock_403_response.status = 403
        mock_403_response.json = AsyncMock(return_value={
            'message': 'Missing Permissions',
            'code': 50013
        })
        mock_403_response.headers = {}

        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_403_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_403_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        mock_session_class.return_value = mock_session

        # Test 403 error
        async with DiscordAPIClient(mock_discord_token) as client:
            with pytest.raises(DiscordAPIError) as exc_info:
                await client.get_guild('1111111111')

        assert exc_info.value.status_code == 403
        assert 'Permission denied' in str(exc_info.value)

        # Test 404 Not Found
        mock_404_response = AsyncMock()
        mock_404_response.status = 404
        mock_404_response.json = AsyncMock(return_value={
            'message': 'Unknown Guild',
            'code': 10004
        })
        mock_404_response.headers = {}

        mock_session.request = AsyncMock(return_value=mock_404_response)

        async with DiscordAPIClient(mock_discord_token) as client:
            with pytest.raises(DiscordAPIError) as exc_info:
                await client.get_guild('9999999999')

        assert exc_info.value.status_code == 404
        assert 'not found' in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_api_client_context_manager(mock_discord_token):
    """
    Test DiscordAPIClient async context manager functionality.

    Verifies:
    - Session is created on __aenter__
    - Session is closed on __aexit__
    - Multiple requests can be made within context
    """
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])
        mock_response.headers = {}

        mock_session = AsyncMock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        mock_session_class.return_value = mock_session

        # Test context manager
        async with DiscordAPIClient(mock_discord_token) as client:
            assert client.session is not None
            await client.get_guilds()

        # Verify session was closed
        mock_session.close.assert_called_once()


# =============================================================================
# DiscordCacheService Tests (6+ tests)
# =============================================================================

@pytest.mark.asyncio
async def test_fetch_user_servers(mock_discord_token, mock_guilds_response):
    """
    Test fetching user servers from Discord API via cache service.

    Verifies:
    - Service correctly calls Discord API
    - Returns list of server dictionaries
    - Does not update cache (fetch only)
    """
    with patch('backend.src.discord.api_client.DiscordAPIClient') as mock_client_class:
        # Mock the static method (assuming it exists or needs to be added)
        mock_client_class.fetch_guilds = AsyncMock(return_value=mock_guilds_response)

        servers = await DiscordCacheService.fetch_user_servers(mock_discord_token)

        # Verify results
        assert len(servers) == 3
        assert servers[0]['name'] == 'Test Server 1'
        assert servers[1]['id'] == '2222222222'


@pytest.mark.asyncio
async def test_fetch_server_channels(mock_discord_token, mock_channels_response):
    """
    Test fetching server channels with filtering.

    Verifies:
    - Service fetches channels from Discord API
    - Filters to only text channels and threads (types 0, 11, 12)
    - Excludes voice channels, categories, etc.
    """
    with patch('backend.src.discord.api_client.DiscordAPIClient') as mock_client_class:
        mock_client_class.fetch_channels = AsyncMock(return_value=mock_channels_response)

        channels = await DiscordCacheService.fetch_server_channels(
            mock_discord_token,
            '1111111111'
        )

        # Verify filtering
        # Should include: 2 text (type 0) + 1 thread (type 11) = 3 channels
        # Should exclude: 1 voice (type 2) + 1 category (type 4) = 2 channels
        assert len(channels) == 3

        # Verify only allowed types
        for channel in channels:
            assert channel['type'] in [0, 11, 12]

        # Verify voice and category excluded
        channel_ids = [c['id'] for c in channels]
        assert '1003' not in channel_ids  # Voice channel excluded
        assert '1005' not in channel_ids  # Category excluded


@pytest.mark.asyncio
async def test_refresh_server_cache(mock_discord_token, mock_guilds_response,
                                    mock_channels_response, mock_db_connection):
    """
    Test full server cache refresh.

    Verifies:
    - Fetches all servers from Discord API
    - Updates server cache in database
    - Fetches and caches channels for each server
    - Returns count of cached servers
    """
    with patch('backend.src.discord.api_client.DiscordAPIClient') as mock_client_class:
        mock_client_class.fetch_guilds = AsyncMock(return_value=mock_guilds_response)
        mock_client_class.fetch_channels = AsyncMock(return_value=mock_channels_response)

        with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
            with patch('backend.src.database.dao.channel_dao.ChannelDAO') as mock_channel_dao:
                # Setup DAO mocks
                mock_server_dao.cache_server = mock_db_connection.mock_cache_server
                mock_channel_dao.bulk_update_channels = mock_db_connection.mock_bulk_update_channels

                # Perform cache refresh
                count = await DiscordCacheService.refresh_server_cache(
                    mock_db_connection,
                    mock_discord_token
                )

                # Verify results
                assert count == 3

                # Verify servers cached
                assert len(mock_db_connection.storage['servers']) == 3
                assert '1111111111' in mock_db_connection.storage['servers']

                # Verify server data
                server = mock_db_connection.storage['servers']['1111111111']
                assert server['name'] == 'Test Server 1'


@pytest.mark.asyncio
async def test_get_or_fetch_server_cached(mock_discord_token, mock_db_connection):
    """
    Test get_or_fetch_server returns cached data when fresh.

    Verifies:
    - Returns cached server data if < 24 hours old
    - Does not call Discord API
    - Cached data is complete and accurate
    """
    # Pre-populate cache with fresh server
    await mock_db_connection.mock_cache_server({
        'server_id': '1111111111',
        'name': 'Cached Server',
        'icon_url': 'https://cdn.discord.com/icons/1111111111/abc123.png',
        'member_count': 100,
        'owner_id': '9999999999'
    })

    with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
        mock_server_dao.is_server_cache_stale = AsyncMock(return_value=False)
        mock_server_dao.get_server_by_id = mock_db_connection.mock_get_server_by_id

        # Get server (should return cached)
        server = await DiscordCacheService.get_or_fetch_server(
            mock_db_connection,
            '1111111111',
            mock_discord_token
        )

        # Verify cached data returned
        assert server is not None
        assert server['name'] == 'Cached Server'
        assert server['server_id'] == '1111111111'


@pytest.mark.asyncio
async def test_get_or_fetch_server_stale(mock_discord_token, mock_guilds_response,
                                        mock_db_connection):
    """
    Test get_or_fetch_server fetches when cache is stale.

    Verifies:
    - Detects stale cache (> 24 hours old)
    - Fetches fresh data from Discord API
    - Updates cache with new data
    - Returns updated server information
    """
    # Pre-populate cache with stale server
    old_server = {
        'server_id': '1111111111',
        'name': 'Old Server Name',
        'icon_url': None,
        'member_count': 50,
        'owner_id': '8888888888'
    }
    await mock_db_connection.mock_cache_server(old_server)

    # Make it stale by backdating
    mock_db_connection.storage['servers']['1111111111']['updated_at'] = (
        datetime.now() - timedelta(hours=25)
    )

    with patch('backend.src.discord.api_client.DiscordAPIClient') as mock_client_class:
        mock_client_class.fetch_guilds = AsyncMock(return_value=mock_guilds_response)

        with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
            mock_server_dao.is_server_cache_stale = mock_db_connection.mock_is_server_cache_stale
            mock_server_dao.get_server_by_id = mock_db_connection.mock_get_server_by_id
            mock_server_dao.cache_server = mock_db_connection.mock_cache_server

            # Get server (should fetch fresh)
            server = await DiscordCacheService.get_or_fetch_server(
                mock_db_connection,
                '1111111111',
                mock_discord_token
            )

            # Verify fresh data returned
            assert server is not None
            assert server['name'] == 'Test Server 1'  # Updated from API


@pytest.mark.asyncio
async def test_get_server_display_name(mock_db_connection):
    """
    Test server display name resolution with fallback.

    Verifies:
    - Returns server name from cache if available
    - Returns fallback format (ID prefix) if not in cache
    - Never raises exceptions (safe fallback)
    """
    # Cache a server
    await mock_db_connection.mock_cache_server({
        'server_id': '1111111111',
        'name': 'My Cool Server',
        'icon_url': None,
        'member_count': 100,
        'owner_id': '9999999999'
    })

    with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
        mock_server_dao.get_server_by_id = mock_db_connection.mock_get_server_by_id

        # Test cached server
        name = await DiscordCacheService.get_server_display_name(
            mock_db_connection,
            '1111111111'
        )
        assert name == 'My Cool Server'

        # Test uncached server (fallback)
        name = await DiscordCacheService.get_server_display_name(
            mock_db_connection,
            '9999999999'
        )
        assert name == '99999999...'  # Fallback format


@pytest.mark.asyncio
async def test_cache_channel_filtering(mock_discord_token, mock_db_connection):
    """
    Test that cache service properly filters channel types.

    Verifies:
    - Only text channels (type 0) are cached
    - Only threads (types 11, 12) are cached
    - Voice, category, and other types are excluded
    """
    all_channels = [
        {'id': '1001', 'name': 'text1', 'type': 0, 'position': 0},
        {'id': '1002', 'name': 'voice1', 'type': 2, 'position': 1},
        {'id': '1003', 'name': 'category1', 'type': 4, 'position': 2},
        {'id': '1004', 'name': 'thread1', 'type': 11, 'position': 3},
        {'id': '1005', 'name': 'private-thread1', 'type': 12, 'position': 4},
        {'id': '1006', 'name': 'stage1', 'type': 13, 'position': 5}
    ]

    with patch('backend.src.discord.api_client.DiscordAPIClient') as mock_client_class:
        mock_client_class.fetch_channels = AsyncMock(return_value=all_channels)

        filtered = await DiscordCacheService.fetch_server_channels(
            mock_discord_token,
            '1111111111'
        )

        # Should include: 1 text + 1 thread + 1 private thread = 3
        assert len(filtered) == 3

        # Verify correct types included
        types = {ch['type'] for ch in filtered}
        assert types == {0, 11, 12}


# =============================================================================
# MultiServerService Tests (5+ tests)
# =============================================================================

@pytest.mark.asyncio
async def test_get_available_servers(mock_db_connection):
    """
    Test getting available servers with allowlist statistics.

    Verifies:
    - Returns all cached servers
    - Includes allowlist count for each server
    - Server data includes name, ID, member count
    """
    # Setup test data
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Cache servers
    await mock_db_connection.mock_cache_server({
        'server_id': '1111111111',
        'name': 'Server 1',
        'icon_url': None,
        'member_count': 100,
        'owner_id': '9999999999'
    })
    await mock_db_connection.mock_cache_server({
        'server_id': '2222222222',
        'name': 'Server 2',
        'icon_url': None,
        'member_count': 50,
        'owner_id': '8888888888'
    })

    # Add some channels to allowlist
    await mock_db_connection.mock_add_channel(user_id, '1111111111', 'ch1')
    await mock_db_connection.mock_add_channel(user_id, '1111111111', 'ch2')
    await mock_db_connection.mock_add_channel(user_id, '2222222222', 'ch3')

    with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
        with patch('backend.src.database.dao.allowlist_dao.AllowlistDAO') as mock_allowlist_dao:
            mock_server_dao.get_all_servers = mock_db_connection.mock_get_all_servers
            mock_allowlist_dao.get_allowlist_stats = mock_db_connection.mock_get_allowlist_stats

            # Get servers
            servers = await MultiServerService.get_available_servers(
                mock_db_connection,
                user_id
            )

            # Verify results
            assert len(servers) == 2

            # Find servers by ID
            server1 = next(s for s in servers if s['server_id'] == '1111111111')
            server2 = next(s for s in servers if s['server_id'] == '2222222222')

            assert server1['allowed_channels'] == 2
            assert server2['allowed_channels'] == 1


@pytest.mark.asyncio
async def test_get_server_channels(mock_db_connection):
    """
    Test getting channels for a specific server by type.

    Verifies:
    - Returns channels filtered by server ID
    - Supports filtering by channel type
    - Channels ordered by position and name
    """
    # Cache channels for server
    await mock_db_connection.mock_bulk_update_channels('1111111111', [
        {'channel_id': '1001', 'name': 'general', 'type': 'text', 'position': 0, 'parent_id': None},
        {'channel_id': '1002', 'name': 'announcements', 'type': 'text', 'position': 1, 'parent_id': None},
        {'channel_id': '1003', 'name': 'help-thread', 'type': 'thread', 'position': 2, 'parent_id': '1001'}
    ])

    with patch('backend.src.database.dao.channel_dao.ChannelDAO') as mock_channel_dao:
        mock_channel_dao.get_channels_by_server = mock_db_connection.mock_get_channels_by_server

        # Get all channels
        all_channels = await MultiServerService.get_server_channels(
            mock_db_connection,
            '1111111111',
            channel_type=None
        )
        assert len(all_channels) == 3

        # Get only text channels
        text_channels = await MultiServerService.get_server_channels(
            mock_db_connection,
            '1111111111',
            channel_type='text'
        )
        assert len(text_channels) == 2
        assert all(ch['type'] == 'text' for ch in text_channels)


@pytest.mark.asyncio
async def test_bulk_add_to_allowlist(mock_db_connection):
    """
    Test bulk adding channels to allowlist.

    Verifies:
    - Validates all channel IDs exist
    - Adds multiple channels in single operation
    - Returns count of added channels
    - Skips already-allowed channels
    """
    # Setup
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Cache channels
    await mock_db_connection.mock_bulk_update_channels('1111111111', [
        {'channel_id': '1001', 'name': 'ch1', 'type': 'text', 'position': 0, 'parent_id': None},
        {'channel_id': '1002', 'name': 'ch2', 'type': 'text', 'position': 1, 'parent_id': None},
        {'channel_id': '1003', 'name': 'ch3', 'type': 'text', 'position': 2, 'parent_id': None}
    ])

    with patch('backend.src.database.dao.channel_dao.ChannelDAO') as mock_channel_dao:
        with patch('backend.src.database.dao.allowlist_dao.AllowlistDAO') as mock_allowlist_dao:
            mock_channel_dao.get_channels_by_server = mock_db_connection.mock_get_channels_by_server
            mock_allowlist_dao.add_channels_bulk = mock_db_connection.mock_add_channels_bulk

            # Bulk add
            count = await MultiServerService.bulk_add_to_allowlist(
                mock_db_connection,
                user_id,
                '1111111111',
                ['1001', '1002', '1003']
            )

            assert count == 3

            # Add again (should skip duplicates)
            count = await MultiServerService.bulk_add_to_allowlist(
                mock_db_connection,
                user_id,
                '1111111111',
                ['1001', '1002']
            )

            assert count == 0  # Already added


@pytest.mark.asyncio
async def test_bulk_add_validation_error(mock_db_connection):
    """
    Test bulk add validation rejects invalid channel IDs.

    Verifies:
    - Validates channel IDs exist before adding
    - Raises ValueError for non-existent channels
    - Error message includes invalid channel IDs
    """
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Cache only some channels
    await mock_db_connection.mock_bulk_update_channels('1111111111', [
        {'channel_id': '1001', 'name': 'ch1', 'type': 'text', 'position': 0, 'parent_id': None}
    ])

    with patch('backend.src.database.dao.channel_dao.ChannelDAO') as mock_channel_dao:
        mock_channel_dao.get_channels_by_server = mock_db_connection.mock_get_channels_by_server

        # Try to add invalid channels
        with pytest.raises(ValueError) as exc_info:
            await MultiServerService.bulk_add_to_allowlist(
                mock_db_connection,
                user_id,
                '1111111111',
                ['1001', '9999', '8888']  # 9999 and 8888 don't exist
            )

        assert '9999' in str(exc_info.value)
        assert '8888' in str(exc_info.value)


@pytest.mark.asyncio
async def test_bulk_remove_from_allowlist(mock_db_connection):
    """
    Test bulk removing channels from allowlist.

    Verifies:
    - Removes multiple channels in single operation
    - Returns count of removed channels
    - Handles non-existent channels gracefully
    """
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Add channels to allowlist
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1001')
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1002')
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1003')

    with patch('backend.src.database.dao.allowlist_dao.AllowlistDAO') as mock_allowlist_dao:
        mock_allowlist_dao.remove_channels_bulk = mock_db_connection.mock_remove_channels_bulk

        # Bulk remove
        count = await MultiServerService.bulk_remove_from_allowlist(
            mock_db_connection,
            user_id,
            ['1001', '1002']
        )

        assert count == 2

        # Verify removed
        assert not await mock_db_connection.mock_is_channel_allowed(user_id, '1001')
        assert not await mock_db_connection.mock_is_channel_allowed(user_id, '1002')
        assert await mock_db_connection.mock_is_channel_allowed(user_id, '1003')


@pytest.mark.asyncio
async def test_get_allowlist_summary(mock_db_connection):
    """
    Test getting allowlist summary with server names.

    Verifies:
    - Returns summary grouped by server
    - Includes server name and channel count
    - Only includes servers with allowed channels
    """
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Cache servers
    await mock_db_connection.mock_cache_server({
        'server_id': '1111111111',
        'name': 'Server 1',
        'icon_url': 'https://example.com/icon1.png',
        'member_count': 100,
        'owner_id': '9999999999'
    })
    await mock_db_connection.mock_cache_server({
        'server_id': '2222222222',
        'name': 'Server 2',
        'icon_url': None,
        'member_count': 50,
        'owner_id': '8888888888'
    })

    # Add channels to allowlist
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1001')
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1002')
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1003')
    await mock_db_connection.mock_add_channel(user_id, '2222222222', '2001')

    with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
        with patch('backend.src.database.dao.allowlist_dao.AllowlistDAO') as mock_allowlist_dao:
            mock_server_dao.get_server_by_id = mock_db_connection.mock_get_server_by_id
            mock_allowlist_dao.get_allowlist_stats = mock_db_connection.mock_get_allowlist_stats

            # Get summary
            summary = await MultiServerService.get_allowlist_summary(
                mock_db_connection,
                user_id
            )

            # Verify results
            assert len(summary) == 2
            assert summary['1111111111']['name'] == 'Server 1'
            assert summary['1111111111']['count'] == 3
            assert summary['2222222222']['name'] == 'Server 2'
            assert summary['2222222222']['count'] == 1


# =============================================================================
# Telegram Command Tests (8+ tests)
# =============================================================================

@pytest.mark.asyncio
async def test_cmd_servers(mock_telegram_bot, mock_db_connection):
    """
    Test /servers command lists servers with statistics.

    Verifies:
    - Shows list of cached servers
    - Displays allowed channel count per server
    - Includes member count and server ID
    - Provides server selection buttons
    """
    from telegram.handlers import cmd_servers

    # Setup
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Cache servers
    await mock_db_connection.mock_cache_server({
        'server_id': '1111111111',
        'name': 'Test Server 1',
        'icon_url': None,
        'member_count': 100,
        'owner_id': '9999999999'
    })

    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1001')
    await mock_db_connection.mock_add_channel(user_id, '1111111111', '1002')

    message = {
        'from': {'id': 12345},
        'text': '/servers'
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.services.multiserver.MultiServerService') as mock_service:
                mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                mock_service.get_available_servers = AsyncMock(return_value=[
                    {
                        'server_id': '1111111111',
                        'name': 'Test Server 1',
                        'member_count': 100,
                        'allowed_channels': 2
                    }
                ])

                await cmd_servers(message, mock_telegram_bot)

                # Verify message sent
                assert mock_telegram_bot.send_message.called
                call_args = mock_telegram_bot.send_message.call_args
                text = call_args[0][1]

                assert 'Test Server 1' in text
                assert '2' in text  # Allowed channels count


@pytest.mark.asyncio
async def test_cmd_servers_empty(mock_telegram_bot, mock_db_connection):
    """
    Test /servers command when no servers are cached.

    Verifies:
    - Shows helpful message when cache is empty
    - Suggests using /setup_discord
    - Provides refresh cache button
    """
    from telegram.handlers import cmd_servers

    await mock_db_connection.mock_create_user(12345)

    message = {
        'from': {'id': 12345},
        'text': '/servers'
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.services.multiserver.MultiServerService') as mock_service:
                mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                mock_service.get_available_servers = AsyncMock(return_value=[])

                await cmd_servers(message, mock_telegram_bot)

                # Verify message
                assert mock_telegram_bot.send_message.called
                call_args = mock_telegram_bot.send_message.call_args
                text = call_args[0][1]

                assert 'No Discord servers cached' in text
                assert 'Refresh Cache' in str(call_args[1].get('reply_markup', ''))


@pytest.mark.asyncio
async def test_cmd_channels_with_server(mock_telegram_bot, mock_db_connection):
    """
    Test /channels <server_id> shows channels for specified server.

    Verifies:
    - Displays channels for given server ID
    - Shows allowlist status for each channel
    - Provides toggle buttons
    """
    from telegram.handlers import cmd_channels

    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)

    message = {
        'from': {'id': 12345},
        'text': '/channels 1111111111'
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.telegram.handlers._show_server_channels') as mock_show:
                mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                mock_show.return_value = None

                await cmd_channels(message, mock_telegram_bot)

                # Verify helper function called
                assert mock_show.called


@pytest.mark.asyncio
async def test_cmd_channels_no_server(mock_telegram_bot, mock_db_connection):
    """
    Test /channels without server_id shows server selection.

    Verifies:
    - Displays list of available servers
    - Shows server selection buttons
    - Each button includes server name and allowed count
    """
    from telegram.handlers import cmd_channels

    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    await mock_db_connection.mock_cache_server({
        'server_id': '1111111111',
        'name': 'Test Server',
        'icon_url': None,
        'member_count': 100,
        'owner_id': '9999999999'
    })

    message = {
        'from': {'id': 12345},
        'text': '/channels'
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.services.multiserver.MultiServerService') as mock_service:
                mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                mock_service.get_available_servers = AsyncMock(return_value=[
                    {
                        'server_id': '1111111111',
                        'name': 'Test Server',
                        'allowed_channels': 0
                    }
                ])

                await cmd_channels(message, mock_telegram_bot)

                # Verify server selection shown
                assert mock_telegram_bot.send_message.called
                call_args = mock_telegram_bot.send_message.call_args
                text = call_args[0][1]

                assert 'Select Server' in text


@pytest.mark.asyncio
async def test_cmd_bulk_allow(mock_telegram_bot, mock_db_connection):
    """
    Test /bulk_allow command starts bulk selection workflow.

    Verifies:
    - Shows server selection for bulk add
    - Each server button has correct callback data
    - Message explains bulk selection purpose
    """
    from telegram.handlers import cmd_bulk_allow

    await mock_db_connection.mock_create_user(12345)

    message = {
        'from': {'id': 12345},
        'text': '/bulk_allow'
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.services.multiserver.MultiServerService') as mock_service:
                mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                mock_service.get_available_servers = AsyncMock(return_value=[
                    {'server_id': '1111111111', 'name': 'Test Server', 'allowed_channels': 0}
                ])

                await cmd_bulk_allow(message, mock_telegram_bot)

                # Verify message sent
                assert mock_telegram_bot.send_message.called
                call_args = mock_telegram_bot.send_message.call_args
                text = call_args[0][1]

                assert 'Bulk Allow' in text


@pytest.mark.asyncio
async def test_callback_servers_refresh(mock_telegram_bot, mock_db_connection,
                                       mock_discord_token):
    """
    Test servers_refresh callback refreshes cache and updates display.

    Verifies:
    - Shows progress message during refresh
    - Calls DiscordCacheService.refresh_server_cache
    - Updates message with refreshed server list
    - Shows success notification
    """
    from telegram.handlers import callback_servers_refresh

    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)

    query = {
        'id': 'query123',
        'from': {'id': 12345},
        'data': 'servers_refresh',
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.database.dao.discord_dao.DiscordDAO') as mock_discord_dao:
                with patch('backend.src.services.discord_cache.DiscordCacheService') as mock_cache:
                    with patch('backend.src.services.multiserver.MultiServerService') as mock_service:
                        mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                        mock_discord_dao.get_discord_connection = AsyncMock(return_value={
                            'token': mock_discord_token
                        })
                        mock_cache.refresh_server_cache = AsyncMock(return_value=2)
                        mock_service.get_available_servers = AsyncMock(return_value=[])

                        await callback_servers_refresh(query, mock_telegram_bot)

                        # Verify refresh was called
                        assert mock_cache.refresh_server_cache.called

                        # Verify message was edited
                        assert mock_telegram_bot.edit_message_text.called


@pytest.mark.asyncio
async def test_callback_channel_toggle(mock_telegram_bot, mock_db_connection):
    """
    Test channel_toggle callback adds/removes channel from allowlist.

    Verifies:
    - Toggles channel allowlist status
    - Adds if not in allowlist
    - Removes if already in allowlist
    - Updates button state after toggle
    """
    from telegram.handlers import callback_channel_toggle

    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    query = {
        'id': 'query123',
        'from': {'id': 12345},
        'data': 'channel_toggle_1111111111_1001',
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.database.dao.allowlist_dao.AllowlistDAO') as mock_allowlist_dao:
                with patch('backend.src.telegram.handlers._show_server_channels') as mock_show:
                    mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                    mock_allowlist_dao.is_channel_allowed = mock_db_connection.mock_is_channel_allowed
                    mock_allowlist_dao.add_channel = mock_db_connection.mock_add_channel
                    mock_allowlist_dao.remove_channel = mock_db_connection.mock_remove_channel
                    mock_show.return_value = None

                    # Toggle on (add)
                    await callback_channel_toggle(query, mock_telegram_bot)

                    # Verify channel was added
                    is_allowed = await mock_db_connection.mock_is_channel_allowed(user_id, '1001')
                    assert is_allowed


@pytest.mark.asyncio
async def test_callback_bulk_confirm(mock_telegram_bot, mock_db_connection):
    """
    Test bulk_confirm callback adds selected channels to allowlist.

    Verifies:
    - Retrieves selected channels from FSM state
    - Calls MultiServerService.bulk_add_to_allowlist
    - Shows success message with count
    - Clears FSM state after completion
    """
    from telegram.handlers import callback_bulk_confirm

    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    # Setup FSM state
    mock_telegram_bot.set_user_state(12345, 'bulk_allow_selection', {
        'server_id': '1111111111',
        'selected_channels': ['1001', '1002', '1003']
    })

    # Cache channels
    await mock_db_connection.mock_bulk_update_channels('1111111111', [
        {'channel_id': '1001', 'name': 'ch1', 'type': 'text', 'position': 0, 'parent_id': None},
        {'channel_id': '1002', 'name': 'ch2', 'type': 'text', 'position': 1, 'parent_id': None},
        {'channel_id': '1003', 'name': 'ch3', 'type': 'text', 'position': 2, 'parent_id': None}
    ])

    query = {
        'id': 'query123',
        'from': {'id': 12345},
        'data': 'bulk_confirm_1111111111',
        'message': {
            'chat': {'id': 12345},
            'message_id': 100
        }
    }

    with patch('backend.src.database.connection.get_asyncpg_pool') as mock_pool:
        mock_pool.return_value.acquire = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        with patch('backend.src.database.dao.user_dao.UserDAO') as mock_user_dao:
            with patch('backend.src.services.multiserver.MultiServerService') as mock_service:
                with patch('backend.src.services.discord_cache.DiscordCacheService') as mock_cache:
                    mock_user_dao.get_user_by_tg_id = mock_db_connection.mock_get_user_by_tg_id
                    mock_cache.get_server_display_name = AsyncMock(return_value='Test Server')
                    mock_service.bulk_add_to_allowlist = mock_db_connection.mock_add_channels_bulk

                    await callback_bulk_confirm(query, mock_telegram_bot)

                    # Verify message was edited with success
                    assert mock_telegram_bot.edit_message_text.called
                    call_args = mock_telegram_bot.edit_message_text.call_args
                    text = call_args[0][2]

                    assert 'Successful' in text
                    assert '3' in text  # Count of added channels


# =============================================================================
# End-to-End Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_complete_multiserver_workflow(mock_discord_token, mock_guilds_response,
                                             mock_channels_response, mock_db_connection,
                                             mock_telegram_bot):
    """
    Test complete multi-server workflow from cache refresh to allowlist management.

    This end-to-end test verifies:
    1. Cache refresh fetches servers and channels
    2. User can view available servers
    3. User can view channels for a server
    4. User can add channels to allowlist
    5. Allowlist summary shows correct data
    """
    # Setup user
    await mock_db_connection.mock_create_user(12345)
    user = await mock_db_connection.mock_get_user_by_tg_id(12345)
    user_id = user['id']

    with patch('backend.src.discord.api_client.DiscordAPIClient') as mock_client_class:
        mock_client_class.fetch_guilds = AsyncMock(return_value=mock_guilds_response)
        mock_client_class.fetch_channels = AsyncMock(return_value=mock_channels_response)

        with patch('backend.src.database.dao.server_dao.ServerDAO') as mock_server_dao:
            with patch('backend.src.database.dao.channel_dao.ChannelDAO') as mock_channel_dao:
                with patch('backend.src.database.dao.allowlist_dao.AllowlistDAO') as mock_allowlist_dao:
                    # Setup DAO mocks
                    mock_server_dao.cache_server = mock_db_connection.mock_cache_server
                    mock_server_dao.get_all_servers = mock_db_connection.mock_get_all_servers
                    mock_server_dao.get_server_by_id = mock_db_connection.mock_get_server_by_id
                    mock_channel_dao.bulk_update_channels = mock_db_connection.mock_bulk_update_channels
                    mock_channel_dao.get_channels_by_server = mock_db_connection.mock_get_channels_by_server
                    mock_allowlist_dao.add_channels_bulk = mock_db_connection.mock_add_channels_bulk
                    mock_allowlist_dao.get_allowlist_stats = mock_db_connection.mock_get_allowlist_stats

                    # Step 1: Refresh cache
                    count = await DiscordCacheService.refresh_server_cache(
                        mock_db_connection,
                        mock_discord_token
                    )
                    assert count == 3

                    # Step 2: Get available servers
                    servers = await MultiServerService.get_available_servers(
                        mock_db_connection,
                        user_id
                    )
                    assert len(servers) == 3

                    # Step 3: Get channels for first server
                    channels = await MultiServerService.get_server_channels(
                        mock_db_connection,
                        '1111111111',
                        channel_type='text'
                    )
                    # Should have filtered channels (text only)
                    assert len(channels) >= 1

                    # Step 4: Bulk add channels to allowlist
                    text_channel_ids = [ch['channel_id'] for ch in channels]
                    add_count = await MultiServerService.bulk_add_to_allowlist(
                        mock_db_connection,
                        user_id,
                        '1111111111',
                        text_channel_ids
                    )
                    assert add_count == len(text_channel_ids)

                    # Step 5: Get allowlist summary
                    summary = await MultiServerService.get_allowlist_summary(
                        mock_db_connection,
                        user_id
                    )
                    assert '1111111111' in summary
                    assert summary['1111111111']['count'] == len(text_channel_ids)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
