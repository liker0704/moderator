-- Migration: 006_search_indexes
-- Description: Add indexes and full-text search support for message search functionality
-- Created: 2025-11-19
-- Tables Modified: messages
-- Features: Search performance optimization with indexes and optional full-text search

-- =============================================================================
-- Performance Indexes for Search
-- =============================================================================

-- Index for author_name searches (case-insensitive partial match)
-- Supports: WHERE author_name ILIKE '%pattern%'
CREATE INDEX IF NOT EXISTS idx_messages_author_name
ON messages USING btree (lower(author_name));

-- Index for created_at for date range searches
-- Note: Already exists in 001_initial_schema.sql but adding IF NOT EXISTS for safety
CREATE INDEX IF NOT EXISTS idx_messages_created_at_desc
ON messages USING btree (created_at DESC);

-- Composite index for common filter combinations
-- Optimizes: platform + created_at queries
CREATE INDEX IF NOT EXISTS idx_messages_platform_created_at
ON messages USING btree (platform, created_at DESC);

-- Composite index for channel searches with date ordering
-- Optimizes: channel_id + created_at queries
CREATE INDEX IF NOT EXISTS idx_messages_channel_created_at
ON messages USING btree (channel_id, created_at DESC);

-- Composite index for server searches (Discord)
-- Optimizes: server_id + created_at queries
CREATE INDEX IF NOT EXISTS idx_messages_server_created_at
ON messages USING btree (server_id, created_at DESC)
WHERE server_id IS NOT NULL;

-- Index for has_image filter
CREATE INDEX IF NOT EXISTS idx_messages_has_image
ON messages USING btree (has_image)
WHERE has_image = true;

-- =============================================================================
-- Full-Text Search Support (Optional, Advanced)
-- =============================================================================

-- Add tsvector column for full-text search
-- This provides more efficient text searching than ILIKE for large datasets
ALTER TABLE messages
ADD COLUMN IF NOT EXISTS content_tsvector tsvector;

-- Create GIN index for full-text search
-- GIN (Generalized Inverted Index) is optimal for full-text search
CREATE INDEX IF NOT EXISTS idx_messages_content_tsvector
ON messages USING gin (content_tsvector);

-- Function to update tsvector column
-- This function converts message content to searchable vector
CREATE OR REPLACE FUNCTION messages_content_tsvector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.content_tsvector := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update tsvector on INSERT/UPDATE
DROP TRIGGER IF EXISTS trigger_messages_content_tsvector_update ON messages;
CREATE TRIGGER trigger_messages_content_tsvector_update
    BEFORE INSERT OR UPDATE OF content
    ON messages
    FOR EACH ROW
    EXECUTE FUNCTION messages_content_tsvector_update();

-- Backfill existing messages with tsvector data
-- This updates all existing rows to populate the content_tsvector column
UPDATE messages
SET content_tsvector = to_tsvector('english', COALESCE(content, ''))
WHERE content_tsvector IS NULL;

-- =============================================================================
-- Performance Notes
-- =============================================================================

-- Index Usage Guide:
--
-- 1. idx_messages_author_name
--    - Used for: author:username searches
--    - Query: WHERE author_name ILIKE '%john%'
--    - Performance: Enables faster author name lookups
--
-- 2. idx_messages_platform_created_at
--    - Used for: platform-specific searches with date ordering
--    - Query: WHERE platform = 'discord' ORDER BY created_at DESC
--    - Performance: Avoids full table scan for platform filters
--
-- 3. idx_messages_channel_created_at
--    - Used for: channel-specific history searches
--    - Query: WHERE channel_id = '123' ORDER BY created_at DESC
--    - Performance: Fast channel message retrieval
--
-- 4. idx_messages_server_created_at
--    - Used for: server-wide searches (Discord)
--    - Query: WHERE server_id = '456' ORDER BY created_at DESC
--    - Performance: Partial index (only for non-NULL server_id)
--
-- 5. idx_messages_content_tsvector
--    - Used for: full-text search queries
--    - Query: WHERE content_tsvector @@ to_tsquery('english', 'search & terms')
--    - Performance: Much faster than ILIKE for large text searches
--    - Features: Supports boolean operators (& | !), stemming, ranking
--
-- Index Maintenance:
-- - Indexes are automatically maintained on INSERT/UPDATE/DELETE
-- - tsvector is automatically updated via trigger
-- - Consider VACUUM ANALYZE messages periodically for optimal performance
--
-- Query Optimization Tips:
-- - Use content_tsvector for complex text searches
-- - Use ILIKE for simple partial matches
-- - Combine filters to leverage composite indexes
-- - Add LIMIT clause to restrict result sets
-- - Use EXPLAIN ANALYZE to verify index usage

-- =============================================================================
-- Verification Queries
-- =============================================================================

-- Verify indexes created successfully
-- Run this to confirm all indexes exist:
--
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'messages'
-- AND indexname LIKE 'idx_messages_%';

-- Test full-text search functionality
-- Run this to verify tsvector is working:
--
-- SELECT id, author_name, content,
--        ts_rank(content_tsvector, to_tsquery('english', 'test')) as rank
-- FROM messages
-- WHERE content_tsvector @@ to_tsquery('english', 'test')
-- ORDER BY rank DESC
-- LIMIT 10;
