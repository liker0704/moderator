-- Migration: 002_ai_response_variants
-- Description: Add AI response variants table for storing LLM-generated response options
-- Created: 2025-11-18
-- Dependencies: 001_initial_schema (tasks table)

-- =============================================================================
-- Table: ai_response_variants
-- Description: AI-generated response variants for tasks
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_response_variants (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    variant_text TEXT NOT NULL,
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    provider VARCHAR(50), -- 'openai' or 'anthropic'
    model VARCHAR(100), -- 'gpt-4-turbo', 'claude-3-opus', etc.
    tone VARCHAR(50), -- NULL, 'soft', 'formal'
    selected BOOLEAN DEFAULT FALSE, -- Was this variant selected?
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_ai_variants_task ON ai_response_variants(task_id);
CREATE INDEX idx_ai_variants_created ON ai_response_variants(created_at);
CREATE INDEX idx_ai_variants_selected ON ai_response_variants(selected);

-- Composite index for finding selected variants for a task
CREATE INDEX idx_ai_variants_task_selected ON ai_response_variants(task_id, selected);
