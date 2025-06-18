-- Enable UUID generation
create extension if not exists "uuid-ossp";

-- Article status enum
create type article_status as enum (
  'pending',
  'researching',
  'writing',
  'editing',
  'completed',
  'paused',
  'error'
);

-- Articles table
create table articles (
  id uuid default uuid_generate_v4() primary key,
  title text not null,
  prompt text not null,
  status article_status default 'pending',
  target_length text not null check (target_length in ('short', 'medium', 'long')),
  research_scope text not null check (research_scope in ('basic', 'thorough', 'comprehensive')),
  current_agent text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Article versions table
create table article_versions (
  id uuid default uuid_generate_v4() primary key,
  article_id uuid not null references articles(id) on delete cascade,
  content text not null,
  agent text not null,
  stage text not null,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Trending topics table
create table trending_topics (
  id uuid default uuid_generate_v4() primary key,
  title text not null,
  description text not null,
  interest_score float not null check (interest_score >= 0 and interest_score <= 100),
  sources jsonb not null, -- Stores data from different sources (Google Trends, News, Social Media)
  status text not null check (status in ('active', 'selected', 'archived')) default 'active',
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Function to update updated_at timestamp
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = timezone('utc'::text, now());
  return new;
end;
$$ language plpgsql;

-- Trigger to update updated_at on articles
create trigger update_articles_updated_at
  before update on articles
  for each row
  execute function update_updated_at_column();

-- Trigger to update updated_at on trending_topics
create trigger update_trending_topics_updated_at
  before update on trending_topics
  for each row
  execute function update_updated_at_column(); 