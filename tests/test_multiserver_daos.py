"""
Comprehensive unit tests for multi-server DAOs.

Tests ServerDAO, ChannelDAO, and AllowlistDAO enhancements for multi-server support.
Uses pytest-asyncio for async testing and mocked asyncpg connections.
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from database.dao.server_dao import ServerDAO
from database.dao.channel_dao import ChannelDAO
from database.dao.allowlist_dao import AllowlistDAO


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_conn():
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    return conn


@pytest.fixture
def sample_server_data():
    """Sample server data for testing."""
    return {
        'server_id': '1111111111',
        'name': 'Test Server',
        'icon_url': 'https://cdn.discordapp.com/icons/111/abc123.png',
        'member_count': 150,
        'owner_id': '9999999999'
    }


@pytest.fixture
def sample_server_data_minimal():
    """Minimal server data (only required fields)."""
    return {
        'server_id': '2222222222',
        'name': 'Minimal Server'
    }


@pytest.fixture
def sample_channel_data():
    """Sample channel data for testing."""
    return {
        'server_id': '1111111111',
        'channel_id': '3333333333',
        'name': 'general',
        'type': 'text',
        'position': 0,
        'parent_id': None
    }


@pytest.fixture
def sample_channels_list():
    """Sample list of channels for bulk operations."""
    return [
        {
            'channel_id': '3333333333',
            'name': 'general',
            'type': 'text',
            'position': 0,
            'parent_id': None
        },
        {
            'channel_id': '4444444444',
            'name': 'announcements',
            'type': 'text',
            'position': 1,
            'parent_id': None
        },
        {
            'channel_id': '5555555555',
            'name': 'voice-chat',
            'type': 'voice',
            'position': 2,
            'parent_id': None
        }
    ]


# =============================================================================
# ServerDAO Tests
# =============================================================================

@pytest.mark.asyncio
async def test_cache_server_insert(mock_conn, sample_server_data):
    """Test inserting a new server into the cache."""
    # Mock the database response for a new insert
    mock_conn.fetchrow.return_value = {'id': 1}

    result = await ServerDAO.cache_server(mock_conn, sample_server_data)

    # Verify result
    assert result == 1

    # Verify the query was called with correct parameters
    mock_conn.fetchrow.assert_called_once()
    call_args = mock_conn.fetchrow.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query contains INSERT and ON CONFLICT
    assert 'INSERT INTO discord_servers' in query
    assert 'ON CONFLICT' in query

    # Check parameters
    assert params[0] == sample_server_data['server_id']
    assert params[1] == sample_server_data['name']
    assert params[2] == sample_server_data['icon_url']
    assert params[3] == sample_server_data['member_count']
    assert params[4] == sample_server_data['owner_id']
    assert isinstance(params[5], datetime)  # created_at
    assert isinstance(params[6], datetime)  # updated_at


@pytest.mark.asyncio
async def test_cache_server_update(mock_conn, sample_server_data):
    """Test updating an existing server (upsert behavior)."""
    # Mock the database response for an update (same ID returned)
    mock_conn.fetchrow.return_value = {'id': 5}

    # Modify the server data (simulating an update)
    updated_data = sample_server_data.copy()
    updated_data['member_count'] = 200
    updated_data['name'] = 'Updated Test Server'

    result = await ServerDAO.cache_server(mock_conn, updated_data)

    # Verify result
    assert result == 5

    # Verify the query was called
    mock_conn.fetchrow.assert_called_once()
    call_args = mock_conn.fetchrow.call_args
    params = call_args[0][1:]

    # Check updated parameters
    assert params[1] == 'Updated Test Server'
    assert params[3] == 200


@pytest.mark.asyncio
async def test_cache_server_missing_required_fields(mock_conn):
    """Test that cache_server raises KeyError when required fields are missing."""
    # Missing 'name' field
    invalid_data = {'server_id': '1111111111'}

    with pytest.raises(KeyError, match="server_data must contain 'server_id' and 'name'"):
        await ServerDAO.cache_server(mock_conn, invalid_data)

    # Missing 'server_id' field
    invalid_data = {'name': 'Test Server'}

    with pytest.raises(KeyError, match="server_data must contain 'server_id' and 'name'"):
        await ServerDAO.cache_server(mock_conn, invalid_data)


@pytest.mark.asyncio
async def test_get_server_by_id_found(mock_conn, sample_server_data):
    """Test retrieving a server that exists in the cache."""
    # Mock the database response
    mock_row = {
        'id': 1,
        'server_id': sample_server_data['server_id'],
        'name': sample_server_data['name'],
        'icon_url': sample_server_data['icon_url'],
        'member_count': sample_server_data['member_count'],
        'owner_id': sample_server_data['owner_id'],
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    mock_conn.fetchrow.return_value = mock_row

    result = await ServerDAO.get_server_by_id(mock_conn, sample_server_data['server_id'])

    # Verify result
    assert result is not None
    assert result['server_id'] == sample_server_data['server_id']
    assert result['name'] == sample_server_data['name']
    assert result['member_count'] == sample_server_data['member_count']

    # Verify query was called with correct parameter
    mock_conn.fetchrow.assert_called_once()
    call_args = mock_conn.fetchrow.call_args
    assert call_args[0][1] == sample_server_data['server_id']


@pytest.mark.asyncio
async def test_get_server_by_id_not_found(mock_conn):
    """Test retrieving a server that doesn't exist in the cache."""
    # Mock the database response for not found
    mock_conn.fetchrow.return_value = None

    result = await ServerDAO.get_server_by_id(mock_conn, 'nonexistent_server_id')

    # Verify result is None
    assert result is None

    # Verify query was called
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_servers(mock_conn):
    """Test retrieving all servers from the cache."""
    # Mock the database response with multiple servers
    mock_rows = [
        {
            'id': 1,
            'server_id': '1111111111',
            'name': 'Alpha Server',
            'icon_url': 'https://example.com/icon1.png',
            'member_count': 100,
            'owner_id': '9999999991',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        },
        {
            'id': 2,
            'server_id': '2222222222',
            'name': 'Beta Server',
            'icon_url': 'https://example.com/icon2.png',
            'member_count': 200,
            'owner_id': '9999999992',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        },
        {
            'id': 3,
            'server_id': '3333333333',
            'name': 'Gamma Server',
            'icon_url': None,
            'member_count': 50,
            'owner_id': '9999999993',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
    ]
    mock_conn.fetch.return_value = mock_rows

    result = await ServerDAO.get_all_servers(mock_conn)

    # Verify result
    assert len(result) == 3
    assert result[0]['name'] == 'Alpha Server'
    assert result[1]['name'] == 'Beta Server'
    assert result[2]['name'] == 'Gamma Server'

    # Verify query was called
    mock_conn.fetch.assert_called_once()
    call_args = mock_conn.fetch.call_args
    query = call_args[0][0]
    assert 'ORDER BY name ASC' in query


@pytest.mark.asyncio
async def test_get_all_servers_empty(mock_conn):
    """Test retrieving all servers when database is empty."""
    # Mock empty response
    mock_conn.fetch.return_value = []

    result = await ServerDAO.get_all_servers(mock_conn)

    # Verify result is empty list
    assert result == []

    # Verify query was called
    mock_conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_update_server_info(mock_conn):
    """Test updating specific fields of a server."""
    # Mock successful update (1 row affected)
    mock_conn.execute.return_value = 'UPDATE 1'

    updates = {
        'name': 'New Server Name',
        'member_count': 250
    }

    result = await ServerDAO.update_server_info(
        mock_conn,
        server_id='1111111111',
        updates=updates
    )

    # Verify result
    assert result is True

    # Verify query was called
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query structure
    assert 'UPDATE discord_servers' in query
    assert 'SET' in query
    assert 'WHERE server_id = $1' in query

    # Check parameters (server_id, field values, updated_at)
    assert params[0] == '1111111111'
    assert 'New Server Name' in params
    assert 250 in params


@pytest.mark.asyncio
async def test_update_server_info_not_found(mock_conn):
    """Test updating a server that doesn't exist."""
    # Mock no rows affected
    mock_conn.execute.return_value = 'UPDATE 0'

    updates = {'member_count': 300}

    result = await ServerDAO.update_server_info(
        mock_conn,
        server_id='nonexistent_id',
        updates=updates
    )

    # Verify result is False
    assert result is False


@pytest.mark.asyncio
async def test_update_server_info_no_valid_fields(mock_conn):
    """Test updating with no valid fields returns False."""
    # Invalid fields that should be ignored
    updates = {'invalid_field': 'value', 'another_invalid': 123}

    result = await ServerDAO.update_server_info(
        mock_conn,
        server_id='1111111111',
        updates=updates
    )

    # Verify result is False and no query was executed
    assert result is False
    mock_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_is_server_cache_stale_fresh(mock_conn):
    """Test that recently cached server is not stale."""
    # Mock server that was updated 1 hour ago
    recent_time = datetime.utcnow() - timedelta(hours=1)
    mock_conn.fetchrow.return_value = {'updated_at': recent_time}

    result = await ServerDAO.is_server_cache_stale(
        mock_conn,
        server_id='1111111111',
        max_age_hours=24
    )

    # Verify result is False (not stale)
    assert result is False

    # Verify query was called
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_is_server_cache_stale_old(mock_conn):
    """Test that old cached server is stale."""
    # Mock server that was updated 48 hours ago
    old_time = datetime.utcnow() - timedelta(hours=48)
    mock_conn.fetchrow.return_value = {'updated_at': old_time}

    result = await ServerDAO.is_server_cache_stale(
        mock_conn,
        server_id='1111111111',
        max_age_hours=24
    )

    # Verify result is True (stale)
    assert result is True


@pytest.mark.asyncio
async def test_is_server_cache_stale_missing(mock_conn):
    """Test that missing server is considered stale."""
    # Mock server not found
    mock_conn.fetchrow.return_value = None

    result = await ServerDAO.is_server_cache_stale(
        mock_conn,
        server_id='nonexistent_id',
        max_age_hours=24
    )

    # Verify result is True (stale because missing)
    assert result is True


# =============================================================================
# ChannelDAO Tests
# =============================================================================

@pytest.mark.asyncio
async def test_cache_channel_insert(mock_conn, sample_channel_data):
    """Test inserting a new channel into the cache."""
    # Mock the database response for a new insert
    mock_conn.fetchrow.return_value = {'id': 10}

    result = await ChannelDAO.cache_channel(mock_conn, sample_channel_data)

    # Verify result
    assert result == 10

    # Verify the query was called with correct parameters
    mock_conn.fetchrow.assert_called_once()
    call_args = mock_conn.fetchrow.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query contains INSERT and ON CONFLICT
    assert 'INSERT INTO discord_channels' in query
    assert 'ON CONFLICT' in query

    # Check parameters
    assert params[0] == sample_channel_data['server_id']
    assert params[1] == sample_channel_data['channel_id']
    assert params[2] == sample_channel_data['name']
    assert params[3] == sample_channel_data['type']
    assert params[4] == sample_channel_data['position']
    assert params[5] == sample_channel_data['parent_id']
    assert isinstance(params[6], datetime)  # cached_at
    assert isinstance(params[7], datetime)  # updated_at


@pytest.mark.asyncio
async def test_cache_channel_update(mock_conn, sample_channel_data):
    """Test updating an existing channel (upsert behavior)."""
    # Mock the database response for an update
    mock_conn.fetchrow.return_value = {'id': 15}

    # Modify channel data (simulating an update)
    updated_data = sample_channel_data.copy()
    updated_data['name'] = 'general-chat'
    updated_data['position'] = 5

    result = await ChannelDAO.cache_channel(mock_conn, updated_data)

    # Verify result
    assert result == 15

    # Verify updated values were used
    call_args = mock_conn.fetchrow.call_args
    params = call_args[0][1:]
    assert params[2] == 'general-chat'
    assert params[4] == 5


@pytest.mark.asyncio
async def test_get_channels_by_server(mock_conn):
    """Test retrieving all channels for a specific server."""
    # Mock the database response with multiple channels
    mock_rows = [
        {
            'id': 1,
            'server_id': '1111111111',
            'channel_id': '3333333333',
            'name': 'general',
            'type': 'text',
            'position': 0,
            'parent_id': None,
            'cached_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        },
        {
            'id': 2,
            'server_id': '1111111111',
            'channel_id': '4444444444',
            'name': 'announcements',
            'type': 'text',
            'position': 1,
            'parent_id': None,
            'cached_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
    ]
    mock_conn.fetch.return_value = mock_rows

    result = await ChannelDAO.get_channels_by_server(mock_conn, '1111111111')

    # Verify result
    assert len(result) == 2
    assert result[0]['name'] == 'general'
    assert result[1]['name'] == 'announcements'
    assert all(ch['server_id'] == '1111111111' for ch in result)

    # Verify query was called with server_id
    mock_conn.fetch.assert_called_once()
    call_args = mock_conn.fetch.call_args
    assert call_args[0][1] == '1111111111'


@pytest.mark.asyncio
async def test_get_channels_by_server_filtered(mock_conn):
    """Test retrieving channels filtered by type."""
    # Mock the database response with only text channels
    mock_rows = [
        {
            'id': 1,
            'server_id': '1111111111',
            'channel_id': '3333333333',
            'name': 'general',
            'type': 'text',
            'position': 0,
            'parent_id': None,
            'cached_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
    ]
    mock_conn.fetch.return_value = mock_rows

    result = await ChannelDAO.get_channels_by_server(
        mock_conn,
        '1111111111',
        channel_type='text'
    )

    # Verify result
    assert len(result) == 1
    assert result[0]['type'] == 'text'

    # Verify query was called with server_id and channel_type
    mock_conn.fetch.assert_called_once()
    call_args = mock_conn.fetch.call_args
    assert call_args[0][1] == '1111111111'
    assert call_args[0][2] == 'text'
    query = call_args[0][0]
    assert 'type = $2' in query


@pytest.mark.asyncio
async def test_get_channels_by_server_empty(mock_conn):
    """Test retrieving channels for a server with no channels."""
    # Mock empty response
    mock_conn.fetch.return_value = []

    result = await ChannelDAO.get_channels_by_server(mock_conn, '9999999999')

    # Verify result is empty list
    assert result == []

    # Verify query was called
    mock_conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_get_channel_by_id_found(mock_conn, sample_channel_data):
    """Test retrieving a channel that exists in the cache."""
    # Mock the database response
    mock_row = {
        'id': 20,
        'server_id': sample_channel_data['server_id'],
        'channel_id': sample_channel_data['channel_id'],
        'name': sample_channel_data['name'],
        'type': sample_channel_data['type'],
        'position': sample_channel_data['position'],
        'parent_id': sample_channel_data['parent_id'],
        'cached_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    mock_conn.fetchrow.return_value = mock_row

    result = await ChannelDAO.get_channel_by_id(mock_conn, sample_channel_data['channel_id'])

    # Verify result
    assert result is not None
    assert result['channel_id'] == sample_channel_data['channel_id']
    assert result['name'] == sample_channel_data['name']
    assert result['type'] == sample_channel_data['type']

    # Verify query was called with correct parameter
    mock_conn.fetchrow.assert_called_once()
    call_args = mock_conn.fetchrow.call_args
    assert call_args[0][1] == sample_channel_data['channel_id']


@pytest.mark.asyncio
async def test_get_channel_by_id_not_found(mock_conn):
    """Test retrieving a channel that doesn't exist in the cache."""
    # Mock the database response for not found
    mock_conn.fetchrow.return_value = None

    result = await ChannelDAO.get_channel_by_id(mock_conn, 'nonexistent_channel_id')

    # Verify result is None
    assert result is None

    # Verify query was called
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_update_channels_insert(mock_conn, sample_channels_list):
    """Test bulk inserting new channels."""
    # Mock execute to simulate successful operations
    mock_conn.execute.return_value = 'DELETE 0'  # No existing channels to delete

    result = await ChannelDAO.bulk_update_channels(
        mock_conn,
        server_id='1111111111',
        channels=sample_channels_list
    )

    # Verify result (number of channels inserted)
    assert result == 3

    # Verify delete query was called once
    delete_call = mock_conn.execute.call_args_list[0]
    assert 'DELETE FROM discord_channels' in delete_call[0][0]

    # Verify insert queries were called (3 times for 3 channels)
    assert mock_conn.execute.call_count == 4  # 1 delete + 3 inserts


@pytest.mark.asyncio
async def test_bulk_update_channels_delete(mock_conn):
    """Test bulk update that deletes removed channels."""
    # Mock execute to simulate deleting 2 channels
    mock_conn.execute.return_value = 'DELETE 2'

    # Provide only 1 channel (implying 2 were removed)
    channels = [
        {
            'channel_id': '3333333333',
            'name': 'general',
            'type': 'text',
            'position': 0,
            'parent_id': None
        }
    ]

    result = await ChannelDAO.bulk_update_channels(
        mock_conn,
        server_id='1111111111',
        channels=channels
    )

    # Verify result
    assert result == 1

    # Verify delete query was called
    delete_call = mock_conn.execute.call_args_list[0]
    delete_query = delete_call[0][0]
    assert 'DELETE FROM discord_channels' in delete_query
    assert 'WHERE server_id = $1' in delete_query


@pytest.mark.asyncio
async def test_bulk_update_channels_mixed(mock_conn, sample_channels_list):
    """Test bulk update with inserts, updates, and deletes."""
    # Mock execute to simulate 1 channel deleted
    mock_conn.execute.return_value = 'DELETE 1'

    result = await ChannelDAO.bulk_update_channels(
        mock_conn,
        server_id='1111111111',
        channels=sample_channels_list
    )

    # Verify result (3 channels upserted)
    assert result == 3

    # Verify both delete and insert operations occurred
    assert mock_conn.execute.call_count == 4  # 1 delete + 3 inserts


@pytest.mark.asyncio
async def test_bulk_update_channels_empty(mock_conn):
    """Test bulk update with empty list deletes all channels."""
    # Mock execute to simulate deleting all channels
    mock_conn.execute.return_value = 'DELETE 5'

    result = await ChannelDAO.bulk_update_channels(
        mock_conn,
        server_id='1111111111',
        channels=[]
    )

    # Verify result (0 channels inserted)
    assert result == 0

    # Verify delete query was called to delete all channels for the server
    mock_conn.execute.assert_called_once()
    delete_call = mock_conn.execute.call_args
    delete_query = delete_call[0][0]
    assert 'DELETE FROM discord_channels' in delete_query
    assert 'WHERE server_id = $1' in delete_query
    # Should NOT have the channel_id filter when list is empty
    assert 'channel_id' not in delete_query


# =============================================================================
# AllowlistDAO Enhancement Tests
# =============================================================================

@pytest.mark.asyncio
async def test_add_channels_bulk(mock_conn):
    """Test adding multiple channels to the allowlist."""
    # Mock the database response
    mock_conn.fetchrow.return_value = {'count': 3}

    channel_ids = ['111111111', '222222222', '333333333']

    result = await AllowlistDAO.add_channels_bulk(
        conn=mock_conn,
        user_id=1,
        server_id='9999999999',
        channel_ids=channel_ids
    )

    # Verify result
    assert result == 3

    # Verify query was called
    mock_conn.fetchrow.assert_called_once()
    call_args = mock_conn.fetchrow.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query structure
    assert 'INSERT INTO channels_allowlist' in query
    assert 'ON CONFLICT' in query
    assert 'DO NOTHING' in query

    # Check parameters
    assert params[0] == 1  # user_id
    assert params[1] == 'discord'  # platform
    assert params[2] == '9999999999'  # server_id
    assert params[3] == channel_ids


@pytest.mark.asyncio
async def test_add_channels_bulk_skip_duplicates(mock_conn):
    """Test that bulk add skips existing channels."""
    # Mock the database response (only 1 new channel added, 2 were duplicates)
    mock_conn.fetchrow.return_value = {'count': 1}

    channel_ids = ['111111111', '222222222', '333333333']

    result = await AllowlistDAO.add_channels_bulk(
        conn=mock_conn,
        user_id=1,
        server_id='9999999999',
        channel_ids=channel_ids
    )

    # Verify result (only 1 was actually inserted)
    assert result == 1

    # Verify ON CONFLICT DO NOTHING was used
    call_args = mock_conn.fetchrow.call_args
    query = call_args[0][0]
    assert 'ON CONFLICT' in query
    assert 'DO NOTHING' in query


@pytest.mark.asyncio
async def test_add_channels_bulk_empty(mock_conn):
    """Test that empty list returns 0 without database call."""
    result = await AllowlistDAO.add_channels_bulk(
        conn=mock_conn,
        user_id=1,
        server_id='9999999999',
        channel_ids=[]
    )

    # Verify result is 0
    assert result == 0

    # Verify no database query was made
    mock_conn.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_add_channels_bulk_invalid_server_id(mock_conn):
    """Test that invalid server_id returns 0."""
    result = await AllowlistDAO.add_channels_bulk(
        conn=mock_conn,
        user_id=1,
        server_id='',
        channel_ids=['111111111']
    )

    # Verify result is 0
    assert result == 0

    # Verify no database query was made
    mock_conn.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_remove_channels_bulk(mock_conn):
    """Test removing multiple channels from the allowlist."""
    # Mock the database response (3 channels removed)
    mock_conn.execute.return_value = 'DELETE 3'

    channel_ids = ['111111111', '222222222', '333333333']

    result = await AllowlistDAO.remove_channels_bulk(
        conn=mock_conn,
        user_id=1,
        channel_ids=channel_ids
    )

    # Verify result
    assert result == 3

    # Verify query was called
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query structure
    assert 'DELETE FROM channels_allowlist' in query
    assert 'WHERE user_id = $1' in query
    assert 'channel_id = ANY($2::text[])' in query

    # Check parameters
    assert params[0] == 1  # user_id
    assert params[1] == channel_ids


@pytest.mark.asyncio
async def test_remove_channels_bulk_partial(mock_conn):
    """Test removing channels when some don't exist."""
    # Mock the database response (only 1 channel existed and was removed)
    mock_conn.execute.return_value = 'DELETE 1'

    channel_ids = ['111111111', '222222222', '333333333']

    result = await AllowlistDAO.remove_channels_bulk(
        conn=mock_conn,
        user_id=1,
        channel_ids=channel_ids
    )

    # Verify result (only 1 was removed)
    assert result == 1


@pytest.mark.asyncio
async def test_remove_channels_bulk_empty(mock_conn):
    """Test that empty list returns 0 without database call."""
    result = await AllowlistDAO.remove_channels_bulk(
        conn=mock_conn,
        user_id=1,
        channel_ids=[]
    )

    # Verify result is 0
    assert result == 0

    # Verify no database query was made
    mock_conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_allowlist_get_channels_by_server(mock_conn):
    """Test retrieving allowlist entries filtered by server_id."""
    # Mock the database response
    mock_rows = [
        {
            'id': 1,
            'user_id': 1,
            'platform': 'discord',
            'server_id': '9999999999',
            'channel_id': '111111111',
            'thread_filter_json': None,
            'enabled': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        },
        {
            'id': 2,
            'user_id': 1,
            'platform': 'discord',
            'server_id': '9999999999',
            'channel_id': '222222222',
            'thread_filter_json': None,
            'enabled': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
    ]
    mock_conn.fetch.return_value = mock_rows

    result = await AllowlistDAO.get_channels_by_server(
        conn=mock_conn,
        user_id=1,
        server_id='9999999999'
    )

    # Verify result
    assert len(result) == 2
    assert all(ch['server_id'] == '9999999999' for ch in result)
    assert all(ch['user_id'] == 1 for ch in result)

    # Verify query was called
    mock_conn.fetch.assert_called_once()
    call_args = mock_conn.fetch.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query structure
    assert 'WHERE user_id = $1' in query
    assert 'AND server_id = $2' in query

    # Check parameters
    assert params[0] == 1
    assert params[1] == '9999999999'


@pytest.mark.asyncio
async def test_allowlist_get_channels_by_server_empty_server_id(mock_conn):
    """Test that empty server_id returns empty list."""
    result = await AllowlistDAO.get_channels_by_server(
        conn=mock_conn,
        user_id=1,
        server_id=''
    )

    # Verify result is empty list
    assert result == []

    # Verify no database query was made
    mock_conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_get_allowlist_stats(mock_conn):
    """Test retrieving allowlist statistics grouped by server."""
    # Mock the database response
    mock_rows = [
        {'server_id': '9999999999', 'count': 5},
        {'server_id': '8888888888', 'count': 3},
        {'server_id': '7777777777', 'count': 1}
    ]
    mock_conn.fetch.return_value = mock_rows

    result = await AllowlistDAO.get_allowlist_stats(
        conn=mock_conn,
        user_id=1
    )

    # Verify result
    assert isinstance(result, dict)
    assert result['9999999999'] == 5
    assert result['8888888888'] == 3
    assert result['7777777777'] == 1
    assert len(result) == 3

    # Verify query was called
    mock_conn.fetch.assert_called_once()
    call_args = mock_conn.fetch.call_args
    query = call_args[0][0]
    params = call_args[0][1:]

    # Check query structure
    assert 'GROUP BY server_id' in query
    assert 'WHERE user_id = $1' in query
    assert 'enabled = TRUE' in query

    # Check parameters
    assert params[0] == 1


@pytest.mark.asyncio
async def test_get_allowlist_stats_empty(mock_conn):
    """Test retrieving stats when user has no allowlist entries."""
    # Mock empty response
    mock_conn.fetch.return_value = []

    result = await AllowlistDAO.get_allowlist_stats(
        conn=mock_conn,
        user_id=999
    )

    # Verify result is empty dict
    assert result == {}

    # Verify query was called
    mock_conn.fetch.assert_called_once()
