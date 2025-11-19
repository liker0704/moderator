-- Migration: 005_multiserver_support
-- Description: Add multi-server support with discord_servers and discord_channels tables
-- Created: 2025-11-19
-- Dependencies: 001_initial_schema (settings table)
-- Tables: discord_servers, discord_channels
-- Alterations: settings (add server_filter_json column)

-- =============================================================================
-- Table: discord_servers
-- Description: Information about Discord servers (guilds) being monitored
-- =============================================================================

CREATE TABLE IF NOT EXISTS discord_servers (
    id BIGSERIAL PRIMARY KEY,
    server_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    icon_url TEXT,
    member_count INT,
    owner_id VARCHAR(255),
    cached_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE discord_servers IS
  'Stores Discord server metadata for multi-server support';

COMMENT ON COLUMN discord_servers.server_id IS
  'Discord guild ID - unique identifier for the server';

COMMENT ON COLUMN discord_servers.name IS
  'Server name as it appears in Discord';

COMMENT ON COLUMN discord_servers.icon_url IS
  'URL to the server icon image';

COMMENT ON COLUMN discord_servers.member_count IS
  'Cached member count from last cache update';

COMMENT ON COLUMN discord_servers.owner_id IS
  'Discord user ID of the server owner';

COMMENT ON COLUMN discord_servers.cached_at IS
  'Timestamp when server metadata was last cached';

-- Indexes for discord_servers table
CREATE INDEX IF NOT EXISTS idx_discord_servers_server_id
ON discord_servers(server_id);

CREATE INDEX IF NOT EXISTS idx_discord_servers_cached_at
ON discord_servers(cached_at DESC);

-- =============================================================================
-- Table: discord_channels
-- Description: Information about Discord channels within monitored servers
-- =============================================================================

CREATE TABLE IF NOT EXISTS discord_channels (
    id BIGSERIAL PRIMARY KEY,
    server_id VARCHAR(255) NOT NULL,
    channel_id VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'text' | 'voice' | 'category' | 'thread' | 'forum'
    position INT,
    parent_id VARCHAR(255),
    cached_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (server_id) REFERENCES discord_servers(server_id) ON DELETE CASCADE
);

COMMENT ON TABLE discord_channels IS
  'Stores Discord channel metadata for each monitored server';

COMMENT ON COLUMN discord_channels.server_id IS
  'Discord guild ID (foreign key reference to discord_servers)';

COMMENT ON COLUMN discord_channels.channel_id IS
  'Discord channel ID - unique identifier for the channel';

COMMENT ON COLUMN discord_channels.name IS
  'Channel name as it appears in Discord';

COMMENT ON COLUMN discord_channels.type IS
  'Channel type: text, voice, category, thread, or forum';

COMMENT ON COLUMN discord_channels.position IS
  'Position of the channel in the channel list (for sorting)';

COMMENT ON COLUMN discord_channels.parent_id IS
  'Parent category ID (NULL if not in a category)';

COMMENT ON COLUMN discord_channels.cached_at IS
  'Timestamp when channel metadata was last cached';

-- Indexes for discord_channels table
CREATE INDEX IF NOT EXISTS idx_discord_channels_server_id
ON discord_channels(server_id);

CREATE INDEX IF NOT EXISTS idx_discord_channels_channel_id
ON discord_channels(channel_id);

CREATE INDEX IF NOT EXISTS idx_discord_channels_type
ON discord_channels(type);

-- Composite index for efficient channel lookup by server and type
CREATE INDEX IF NOT EXISTS idx_discord_channels_server_type
ON discord_channels(server_id, type);

-- =============================================================================
-- Alterations to Existing Tables
-- =============================================================================

-- Add server_filter_json column to settings table for multi-server filtering
ALTER TABLE settings ADD COLUMN IF NOT EXISTS server_filter_json TEXT;

COMMENT ON COLUMN settings.server_filter_json IS
  'JSON configuration for server filtering. Format: {"enabled_servers": ["123", "456"], "show_all": true}';

-- =============================================================================
-- Index Maintenance Comments
-- =============================================================================

COMMENT ON INDEX idx_discord_servers_server_id IS
  'Optimizes lookups of servers by server_id and ensures uniqueness';

COMMENT ON INDEX idx_discord_servers_cached_at IS
  'Optimizes cache freshness queries and ordered retrieval by cache time';

COMMENT ON INDEX idx_discord_channels_server_id IS
  'Optimizes lookups of all channels within a specific server';

COMMENT ON INDEX idx_discord_channels_channel_id IS
  'Optimizes direct channel lookups and ensures uniqueness';

COMMENT ON INDEX idx_discord_channels_type IS
  'Optimizes filtering channels by type (text, voice, category, thread)';

COMMENT ON INDEX idx_discord_channels_server_type IS
  'Optimizes combined server and type filtering for efficient channel queries';
