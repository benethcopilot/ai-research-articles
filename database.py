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