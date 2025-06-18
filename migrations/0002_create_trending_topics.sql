-- Create trending_topics table
CREATE TABLE IF NOT EXISTS trending_topics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    interest_score FLOAT NOT NULL,
    sources JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_trending_topics_status ON trending_topics(status);
CREATE INDEX IF NOT EXISTS idx_trending_topics_interest_score ON trending_topics(interest_score DESC);
CREATE INDEX IF NOT EXISTS idx_trending_topics_created_at ON trending_topics(created_at DESC);

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_trending_topics_updated_at
    BEFORE UPDATE ON trending_topics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 