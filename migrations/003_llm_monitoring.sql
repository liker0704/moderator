-- Migration: 003_llm_monitoring
-- Description: LLM monitoring and cost tracking infrastructure
-- Created: 2025-11-18
-- Dependencies: 001_initial_schema (tasks table)

-- =============================================================================
-- Table: llm_requests
-- Description: Detailed tracking of all LLM API requests for monitoring and cost analysis
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_requests (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES tasks(id) ON DELETE SET NULL, -- NULL allowed for non-task requests
    provider VARCHAR(50) NOT NULL, -- 'openai' or 'anthropic'
    model VARCHAR(100) NOT NULL, -- 'gpt-4-turbo', 'claude-3-sonnet-20240229', etc.
    request_type VARCHAR(50) DEFAULT 'generation', -- 'generation', 'soften', 'other'
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost DECIMAL(10,6) NOT NULL DEFAULT 0.0, -- Cost in USD (up to $9999.999999)
    duration_ms INTEGER, -- Request duration in milliseconds
    status VARCHAR(50) NOT NULL DEFAULT 'success', -- 'success' | 'error' | 'timeout'
    error_message TEXT, -- Error details if status != 'success'
    metadata_json TEXT, -- Additional metadata (JSON): temperature, max_tokens, etc.
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for performance optimization
CREATE INDEX idx_llm_requests_task_id ON llm_requests(task_id);
CREATE INDEX idx_llm_requests_provider ON llm_requests(provider);
CREATE INDEX idx_llm_requests_model ON llm_requests(model);
CREATE INDEX idx_llm_requests_status ON llm_requests(status);
CREATE INDEX idx_llm_requests_created_at ON llm_requests(created_at DESC);

-- Composite index for cost analysis by date and provider
CREATE INDEX idx_llm_requests_created_provider ON llm_requests(created_at DESC, provider);

-- Composite index for successful requests analytics
CREATE INDEX idx_llm_requests_status_created ON llm_requests(status, created_at DESC);

-- =============================================================================
-- Table: llm_usage_budgets
-- Description: Budget tracking and alerts for LLM usage
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_usage_budgets (
    id BIGSERIAL PRIMARY KEY,
    period VARCHAR(50) NOT NULL, -- 'daily' | 'weekly' | 'monthly'
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    budget_limit DECIMAL(10,2) NOT NULL, -- Budget limit in USD
    current_usage DECIMAL(10,6) NOT NULL DEFAULT 0.0, -- Current usage in USD
    alert_threshold DECIMAL(3,2) DEFAULT 0.80, -- Alert when usage exceeds this % (0.0 - 1.0)
    alert_triggered BOOLEAN DEFAULT FALSE, -- Has alert been triggered for this period?
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(period, period_start)
);

-- Indexes for budget tracking
CREATE INDEX idx_llm_budgets_period ON llm_usage_budgets(period);
CREATE INDEX idx_llm_budgets_period_dates ON llm_usage_budgets(period_start, period_end);
CREATE INDEX idx_llm_budgets_alert ON llm_usage_budgets(alert_triggered);

-- =============================================================================
-- View: llm_usage_summary
-- Description: Aggregated statistics for LLM usage and costs
-- =============================================================================

CREATE OR REPLACE VIEW llm_usage_summary AS
SELECT
    provider,
    model,
    DATE(created_at) as usage_date,
    COUNT(*) as request_count,
    COUNT(*) FILTER (WHERE status = 'success') as successful_requests,
    COUNT(*) FILTER (WHERE status = 'error') as failed_requests,
    COUNT(*) FILTER (WHERE status = 'timeout') as timeout_requests,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(completion_tokens) as total_completion_tokens,
    SUM(total_tokens) as total_tokens,
    SUM(cost) as total_cost,
    AVG(cost) as avg_cost_per_request,
    AVG(duration_ms) as avg_duration_ms,
    MAX(cost) as max_cost,
    MIN(cost) FILTER (WHERE cost > 0) as min_cost
FROM llm_requests
GROUP BY provider, model, DATE(created_at)
ORDER BY usage_date DESC, total_cost DESC;

-- =============================================================================
-- View: llm_daily_totals
-- Description: Daily aggregated totals across all providers and models
-- =============================================================================

CREATE OR REPLACE VIEW llm_daily_totals AS
SELECT
    DATE(created_at) as usage_date,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE status = 'success') as successful_requests,
    COUNT(*) FILTER (WHERE status = 'error') as failed_requests,
    SUM(total_tokens) as total_tokens,
    SUM(cost) as total_cost,
    AVG(duration_ms) as avg_duration_ms
FROM llm_requests
GROUP BY DATE(created_at)
ORDER BY usage_date DESC;

-- =============================================================================
-- View: llm_provider_comparison
-- Description: Compare usage and costs across different LLM providers
-- =============================================================================

CREATE OR REPLACE VIEW llm_provider_comparison AS
SELECT
    provider,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE status = 'success') as successful_requests,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'success') / NULLIF(COUNT(*), 0), 2) as success_rate_pct,
    SUM(total_tokens) as total_tokens,
    SUM(cost) as total_cost,
    AVG(cost) as avg_cost_per_request,
    AVG(duration_ms) as avg_duration_ms
FROM llm_requests
GROUP BY provider
ORDER BY total_cost DESC;
