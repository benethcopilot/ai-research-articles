from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from supabase import create_client, Client

class ArticleBase(BaseModel):
    title: str
    prompt: str
    target_length: str  # 'short', 'medium', 'long'
    research_scope: str  # 'basic', 'thorough', 'comprehensive'

class Article(ArticleBase):
    id: str
    status: str
    current_agent: Optional[str]
    created_at: datetime
    updated_at: datetime

class ArticleVersion(BaseModel):
    id: str
    article_id: str
    content: str
    agent: str
    stage: str
    created_at: datetime

class Tag(BaseModel):
    id: str
    name: str
    color: str
    created_at: datetime
    updated_at: datetime

class Database:
    # Valid article statuses from the enum
    VALID_STATUSES = {
        'pending',
        'researching',
        'writing',
        'editing',
        'completed',
        'paused',
        'error'
    }

    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)

    def validate_status(self, status: str) -> None:
        """Validates that a status is allowed by the enum"""
        if status not in self.VALID_STATUSES:
            valid_statuses = "', '".join(sorted(self.VALID_STATUSES))
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: '{valid_statuses}'"
            )

    def create_article(self, article_data: dict) -> str:
        """Creates a new article record"""
        try:
            response = self.client.table('articles').insert(article_data).execute()
            return response.data[0]['id']
        except Exception as e:
            raise Exception(f"Error creating article: {str(e)}")

    def update_article_status(self, article_id: str, status: str, current_agent: Optional[str] = None) -> None:
        """Updates article status and current agent"""
        try:
            # Validate status before attempting update
            self.validate_status(status)
            
            update_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
            if current_agent is not None:
                update_data["current_agent"] = current_agent
            
            self.client.table('articles').update(update_data).eq('id', article_id).execute()
        except ValueError as e:
            # Re-raise validation errors with the original message
            raise
        except Exception as e:
            raise Exception(f"Error updating article status: {str(e)}")

    def update_article_content(self, article_id: str, content: str, agent: str = "editor", stage: str = "final") -> None:
        """
        Updates the article content by creating a new version.
        
        Args:
            article_id: The ID of the article
            content: The article content
            agent: The agent that created this version
            stage: The stage of the article creation process
        """
        try:
            self.client.table('article_versions').insert({
                'article_id': article_id,
                'content': content,
                'agent': agent,
                'stage': stage
            }).execute()
        except Exception as e:
            raise Exception(f"Error updating article content: {str(e)}")

    def get_article(self, article_id: str) -> Optional[Article]:
        """Retrieves an article by ID"""
        try:
            response = self.client.table('articles').select("*").eq('id', article_id).execute()
            if response.data:
                return Article(**response.data[0])
            return None
        except Exception as e:
            raise Exception(f"Error getting article: {str(e)}")

    def get_article_versions(self, article_id: str) -> List[Dict]:
        """
        Gets all versions of an article.
        
        Args:
            article_id: The ID of the article
            
        Returns:
            List of article versions
        """
        try:
            response = self.client.table('article_versions')\
                .select('*')\
                .eq('article_id', article_id)\
                .order('created_at')\
                .execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error getting article versions: {str(e)}")

    def create_article_version(self, article_id: str, content: str, agent: str, stage: str) -> None:
        """Creates a new version of an article"""
        try:
            self.client.table('article_versions').insert({
                "article_id": article_id,
                "content": content,
                "agent": agent,
                "stage": stage,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            raise Exception(f"Error creating article version: {str(e)}")

    # ===== TAG MANAGEMENT =====
    
    def create_tag(self, name: str, color: str = '#3b82f6') -> str:
        """Creates a new tag"""
        try:
            response = self.client.table('tags').insert({
                'name': name.lower().strip(),
                'color': color
            }).execute()
            return response.data[0]['id']
        except Exception as e:
            raise Exception(f"Error creating tag: {str(e)}")

    def get_or_create_tag(self, name: str, color: str = '#3b82f6') -> str:
        """Gets existing tag or creates a new one"""
        try:
            # Try to get existing tag
            response = self.client.table('tags').select('id').eq('name', name.lower().strip()).execute()
            if response.data:
                return response.data[0]['id']
            # Create new tag if not found
            return self.create_tag(name, color)
        except Exception as e:
            raise Exception(f"Error getting or creating tag: {str(e)}")

    def add_tags_to_article(self, article_id: str, tag_names: List[str]) -> None:
        """Adds tags to an article"""
        try:
            for tag_name in tag_names:
                tag_id = self.get_or_create_tag(tag_name)
                # Insert article-tag relationship, ignore if already exists
                try:
                    self.client.table('article_tags').insert({
                        'article_id': article_id,
                        'tag_id': tag_id
                    }).execute()
                except:
                    # Tag already exists for this article, skip
                    pass
        except Exception as e:
            raise Exception(f"Error adding tags to article: {str(e)}")

    def get_article_tags(self, article_id: str) -> List[Dict]:
        """Gets all tags for an article"""
        try:
            response = self.client.table('article_tags')\
                .select('tags(id, name, color)')\
                .eq('article_id', article_id)\
                .execute()
            return [item['tags'] for item in response.data]
        except Exception as e:
            raise Exception(f"Error getting article tags: {str(e)}")

    def search_articles(self, query: str = '', tags: Optional[List[str]] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, target_length: Optional[str] = None) -> List[Dict]:
        """Search articles with various filters"""
        try:
            # Start with base query
            query_builder = self.client.table('articles').select('*, article_tags(tags(name, color))')
            
            # Add text search if query provided
            if query:
                query_builder = query_builder.or_(f'title.ilike.%{query}%,prompt.ilike.%{query}%')
            
            # Add date filters
            if date_from:
                query_builder = query_builder.gte('created_at', date_from)
            if date_to:
                query_builder = query_builder.lte('created_at', date_to)
            
            # Add target length filter
            if target_length:
                query_builder = query_builder.eq('target_length', target_length)
            
            # Only show completed articles
            query_builder = query_builder.eq('status', 'completed')
            
            # Order by creation date
            query_builder = query_builder.order('created_at', desc=True)
            
            response = query_builder.execute()
            
            # Filter by tags if provided (post-processing since Supabase doesn't handle this well)
            if tags:
                filtered_articles = []
                for article in response.data:
                    article_tag_names = [tag_rel['tags']['name'] for tag_rel in article.get('article_tags', [])]
                    if any(tag.lower() in article_tag_names for tag in tags):
                        filtered_articles.append(article)
                return filtered_articles
            
            return response.data
        except Exception as e:
            raise Exception(f"Error searching articles: {str(e)}")

    # ===== ANALYTICS =====
    
    def track_article_view(self, article_id: str, session_id: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None, referrer: Optional[str] = None) -> None:
        """Track an article view"""
        try:
            # Check if this session already viewed this article
            response = self.client.table('article_analytics')\
                .select('id, page_views')\
                .eq('article_id', article_id)\
                .eq('session_id', session_id)\
                .execute()
            
            if response.data:
                # Update existing record
                existing_record = response.data[0]
                self.client.table('article_analytics')\
                    .update({'page_views': existing_record['page_views'] + 1})\
                    .eq('id', existing_record['id'])\
                    .execute()
            else:
                # Create new record
                self.client.table('article_analytics').insert({
                    'article_id': article_id,
                    'session_id': session_id,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'referrer': referrer,
                    'page_views': 1
                }).execute()
        except Exception as e:
            raise Exception(f"Error tracking article view: {str(e)}")

    def track_reading_time(self, article_id: str, session_id: str, time_spent_seconds: int) -> None:
        """Track time spent reading an article"""
        try:
            # Find existing analytics record for this session and article
            response = self.client.table('article_analytics')\
                .select('id, time_spent_seconds')\
                .eq('article_id', article_id)\
                .eq('session_id', session_id)\
                .execute()
            
            if response.data:
                # Update existing record
                existing_record = response.data[0]
                new_time = existing_record['time_spent_seconds'] + time_spent_seconds
                self.client.table('article_analytics')\
                    .update({'time_spent_seconds': new_time})\
                    .eq('id', existing_record['id'])\
                    .execute()
        except Exception as e:
            raise Exception(f"Error tracking reading time: {str(e)}")

    def get_article_analytics(self, article_id: str) -> Dict:
        """Get analytics for a specific article"""
        try:
            response = self.client.table('article_analytics')\
                .select('*')\
                .eq('article_id', article_id)\
                .execute()
            
            if not response.data:
                return {'total_views': 0, 'unique_sessions': 0, 'total_reading_time': 0, 'avg_reading_time': 0}
            
            total_views = sum(record['page_views'] for record in response.data)
            unique_sessions = len(response.data)
            total_reading_time = sum(record['time_spent_seconds'] for record in response.data)
            avg_reading_time = total_reading_time / unique_sessions if unique_sessions > 0 else 0
            
            return {
                'total_views': total_views,
                'unique_sessions': unique_sessions,
                'total_reading_time': total_reading_time,
                'avg_reading_time': round(avg_reading_time, 2)
            }
        except Exception as e:
            raise Exception(f"Error getting article analytics: {str(e)}")

    def get_popular_articles(self, limit: int = 10) -> List[Dict]:
        """Get most popular articles by view count"""
        try:
            # Get articles with their analytics
            response = self.client.rpc('get_popular_articles', {'limit_count': limit}).execute()
            return response.data
        except Exception as e:
            # Fallback to simple query if RPC doesn't exist
            try:
                articles_response = self.client.table('articles')\
                    .select('*, article_analytics(page_views)')\
                    .eq('status', 'completed')\
                    .execute()
                
                # Calculate total views for each article
                articles_with_views = []
                for article in articles_response.data:
                    total_views = sum(analytics['page_views'] for analytics in article.get('article_analytics', []))
                    article['total_views'] = total_views
                    articles_with_views.append(article)
                
                # Sort by total views and return top articles
                articles_with_views.sort(key=lambda x: x['total_views'], reverse=True)
                return articles_with_views[:limit]
            except Exception as fallback_error:
                raise Exception(f"Error getting popular articles: {str(fallback_error)}")

    # ===== PERFORMANCE METRICS =====
    
    def track_performance_start(self, article_id: str, stage: str, agent: str) -> str:
        """Track the start of a performance metric"""
        try:
            response = self.client.table('performance_metrics').insert({
                'article_id': article_id,
                'stage': stage,
                'agent': agent,
                'start_time': datetime.utcnow().isoformat()
            }).execute()
            return response.data[0]['id']
        except Exception as e:
            raise Exception(f"Error tracking performance start: {str(e)}")

    def track_performance_end(self, metric_id: str, success: bool = True, error_message: Optional[str] = None, tokens_used: Optional[int] = None) -> None:
        """Track the end of a performance metric"""
        try:
            end_time = datetime.utcnow()
            
            # Get the start time to calculate duration
            response = self.client.table('performance_metrics')\
                .select('start_time')\
                .eq('id', metric_id)\
                .execute()
            
            if response.data:
                start_time = datetime.fromisoformat(response.data[0]['start_time'].replace('Z', '+00:00'))
                duration_seconds = int((end_time - start_time).total_seconds())
                
                self.client.table('performance_metrics')\
                    .update({
                        'end_time': end_time.isoformat(),
                        'duration_seconds': duration_seconds,
                        'success': success,
                        'error_message': error_message,
                        'tokens_used': tokens_used
                    })\
                    .eq('id', metric_id)\
                    .execute()
        except Exception as e:
            raise Exception(f"Error tracking performance end: {str(e)}")

    def get_performance_metrics(self, article_id: str = None) -> List[Dict]:
        """Get performance metrics, optionally filtered by article"""
        try:
            query_builder = self.client.table('performance_metrics').select('*')
            
            if article_id:
                query_builder = query_builder.eq('article_id', article_id)
            
            response = query_builder.order('created_at', desc=True).execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error getting performance metrics: {str(e)}")

    # ===== CONTENT MODERATION =====
    
    def create_moderation_record(self, article_id: str, status: str = 'pending') -> str:
        """Create a moderation record for an article"""
        try:
            response = self.client.table('content_moderation').insert({
                'article_id': article_id,
                'status': status
            }).execute()
            return response.data[0]['id']
        except Exception as e:
            raise Exception(f"Error creating moderation record: {str(e)}")

    def update_moderation_status(self, article_id: str, status: str, moderator_notes: str = None, moderated_by: str = None) -> None:
        """Update moderation status for an article"""
        try:
            update_data = {
                'status': status,
                'moderated_at': datetime.utcnow().isoformat()
            }
            if moderator_notes:
                update_data['moderator_notes'] = moderator_notes
            if moderated_by:
                update_data['moderated_by'] = moderated_by
            
            self.client.table('content_moderation')\
                .update(update_data)\
                .eq('article_id', article_id)\
                .execute()
        except Exception as e:
            raise Exception(f"Error updating moderation status: {str(e)}")

    def get_articles_for_moderation(self, status: str = 'pending') -> List[Dict]:
        """Get articles that need moderation"""
        try:
            response = self.client.table('content_moderation')\
                .select('*, articles(*)')\
                .eq('status', status)\
                .order('created_at')\
                .execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error getting articles for moderation: {str(e)}") 