-- Migration: 007_stats_indexes
-- Description: Add database indexes to optimize statistics queries
-- Created: 2025-11-19
-- Dependencies: 001_initial_schema, 003_llm_monitoring

-- =============================================================================
-- Indexes for Response Time Queries
-- =============================================================================

-- Index for calculating average response time from task creation to posting reply
-- Optimizes: get_average_response_time, get_response_time_percentiles
CREATE INDEX IF NOT EXISTS idx_tasks_user_created_answered
ON tasks(assignee_user_id, created_at DESC, answered_at)
WHERE answered_at IS NOT NULL;

-- Index for replies joined with tasks (for response time calculations)
CREATE INDEX IF NOT EXISTS idx_replies_task_posted
ON replies(task_id, posted_at)
WHERE posted_at IS NOT NULL;

-- =============================================================================
-- Indexes for Channel Load Queries
-- =============================================================================

-- Index for message counts by channel and platform
-- Optimizes: get_channel_load
CREATE INDEX IF NOT EXISTS idx_messages_channel_platform_created
ON messages(channel_id, platform, created_at DESC);

-- Composite index for messages joined with tasks
CREATE INDEX IF NOT EXISTS idx_messages_created_platform
ON messages(created_at DESC, platform, channel_id);

-- =============================================================================
-- Indexes for Task Statistics Queries
-- =============================================================================

-- Index for task status counts by user
-- Optimizes: get_task_stats, count_tasks_by_status
CREATE INDEX IF NOT EXISTS idx_tasks_user_status_created
ON tasks(assignee_user_id, status, created_at DESC);

-- Index for finding unclosed tasks by age
-- Optimizes: get_unclosed_tasks
CREATE INDEX IF NOT EXISTS idx_tasks_user_open_created
ON tasks(assignee_user_id, created_at ASC)
WHERE status = 'open';

-- =============================================================================
-- Indexes for LLM Usage Queries
-- =============================================================================

-- Composite index for LLM requests by task and date
-- Optimizes: get_llm_usage_stats (already has idx_llm_requests_created_at)
-- This adds task_id for better join performance
CREATE INDEX IF NOT EXISTS idx_llm_requests_task_created_status
ON llm_requests(task_id, created_at DESC, status);

-- Index for LLM provider/model breakdown
-- Optimizes: get_llm_provider_breakdown
CREATE INDEX IF NOT EXISTS idx_llm_requests_provider_model_cost
ON llm_requests(provider, model, created_at DESC, status)
WHERE status = 'success';

-- =============================================================================
-- Indexes for Hourly Distribution Queries
-- =============================================================================

-- Index for extracting hour from created_at
-- PostgreSQL can use this for queries with EXTRACT(HOUR FROM created_at)
-- Optimizes: get_hourly_distribution
CREATE INDEX IF NOT EXISTS idx_messages_created_hour
ON messages(created_at DESC);

-- =============================================================================
-- Indexes for Daily Task Trend Queries
-- =============================================================================

-- Index for daily task grouping
-- Optimizes: get_daily_task_trend
CREATE INDEX IF NOT EXISTS idx_tasks_created_date_status
ON tasks(created_at DESC, status);

-- =============================================================================
-- Statistics and Maintenance
-- =============================================================================

-- Analyze tables to update query planner statistics
ANALYZE tasks;
ANALYZE messages;
ANALYZE replies;
ANALYZE llm_requests;

-- =============================================================================
-- Comments for Documentation
-- =============================================================================

COMMENT ON INDEX idx_tasks_user_created_answered IS
'Optimizes response time calculations by filtering answered tasks for specific users';

COMMENT ON INDEX idx_replies_task_posted IS
'Optimizes join between tasks and replies for response time metrics';

COMMENT ON INDEX idx_messages_channel_platform_created IS
'Optimizes channel load queries grouping by channel and platform';

COMMENT ON INDEX idx_tasks_user_status_created IS
'Optimizes task statistics queries grouped by status and user';

COMMENT ON INDEX idx_tasks_user_open_created IS
'Optimizes finding old unclosed tasks (partial index for status = open)';

COMMENT ON INDEX idx_llm_requests_task_created_status IS
'Optimizes LLM usage queries joining with tasks table';

COMMENT ON INDEX idx_llm_requests_provider_model_cost IS
'Optimizes LLM provider/model breakdown queries (partial index for successful requests)';
