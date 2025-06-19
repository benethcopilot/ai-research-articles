-- Migration 0003: Add tags, analytics, and moderation features
-- Run this in Supabase SQL Editor

-- Create tags table
CREATE TABLE IF NOT EXISTS tags (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#3b82f6', -- Default blue color
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create article_tags junction table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS article_tags (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(article_id, tag_id)
);

-- Create analytics table for tracking article views and reading time
CREATE TABLE IF NOT EXISTS article_analytics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    session_id VARCHAR(255), -- Simple session tracking
    ip_address INET, -- Track IP for basic analytics
    user_agent TEXT, -- Browser/device info
    page_views INTEGER DEFAULT 1,
    time_spent_seconds INTEGER DEFAULT 0, -- Time spent reading in seconds
    referrer TEXT, -- Where they came from
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create moderation table for content review
CREATE TABLE IF NOT EXISTS content_moderation (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    moderator_notes TEXT,
    moderated_by VARCHAR(100), -- Admin identifier
    moderated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create performance metrics table for tracking article generation
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL, -- planning, research, draft, final
    agent VARCHAR(50) NOT NULL, -- manager, researcher, writer, editor
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER, -- Calculated duration
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    tokens_used INTEGER, -- For tracking AI usage
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_article_tags_article_id ON article_tags(article_id);
CREATE INDEX IF NOT EXISTS idx_article_tags_tag_id ON article_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_article_analytics_article_id ON article_analytics(article_id);
CREATE INDEX IF NOT EXISTS idx_article_analytics_created_at ON article_analytics(created_at);
CREATE INDEX IF NOT EXISTS idx_content_moderation_article_id ON content_moderation(article_id);
CREATE INDEX IF NOT EXISTS idx_content_moderation_status ON content_moderation(status);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_article_id ON performance_metrics(article_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_stage ON performance_metrics(stage);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_agent ON performance_metrics(agent);

-- Add updated_at triggers for tables that need them
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_tags_updated_at BEFORE UPDATE ON tags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_article_analytics_updated_at BEFORE UPDATE ON article_analytics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_moderation_updated_at BEFORE UPDATE ON content_moderation
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS) for better security
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE article_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_moderation ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;

-- Create policies (allow all operations for now, can be refined later)
CREATE POLICY "Allow all operations on tags" ON tags FOR ALL USING (true);
CREATE POLICY "Allow all operations on article_tags" ON article_tags FOR ALL USING (true);
CREATE POLICY "Allow all operations on article_analytics" ON article_analytics FOR ALL USING (true);
CREATE POLICY "Allow all operations on content_moderation" ON content_moderation FOR ALL USING (true);
CREATE POLICY "Allow all operations on performance_metrics" ON performance_metrics FOR ALL USING (true); 