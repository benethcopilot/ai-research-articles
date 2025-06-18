import os
import logging
from datetime import datetime, timedelta
import aiohttp
import asyncio
from typing import List, Dict, Any
import json
from database import Database
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TopicResearcher:
    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def research_trending_topics(self) -> List[Dict[str, Any]]:
        """Research trending topics from multiple sources"""
        try:
            # Get topics from different sources concurrently
            hackernews_topics = await self._get_hackernews_topics()
            github_topics = await self._get_github_topics()
            medium_topics = await self._get_medium_topics()
            
            # Combine and deduplicate topics
            all_topics = self._combine_topics(hackernews_topics, github_topics, medium_topics)
            
            # Calculate interest scores
            scored_topics = self._calculate_interest_scores(all_topics)
            
            # Save topics to database
            saved_topics = await self._save_topics(scored_topics)
            
            return saved_topics
            
        except Exception as e:
            self.logger.error(f"Error researching topics: {str(e)}")
            raise
    
    async def _get_hackernews_topics(self) -> List[Dict[str, Any]]:
        """Get trending topics from Hacker News"""
        async with aiohttp.ClientSession() as session:
            # Get top stories
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Hacker News API error: {response.status}")
                    
                story_ids = await response.json()
                story_ids = story_ids[:30]  # Get top 30 stories
                
                topics = []
                for story_id in story_ids:
                    story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    async with session.get(story_url) as story_response:
                        if story_response.status != 200:
                            continue
                            
                        story = await story_response.json()
                        if story.get("title") and story.get("score"):
                            topics.append({
                                "title": story["title"],
                                "description": f"Posted on Hacker News with {story['score']} points",
                                "source": "hackernews",
                                "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                                "published_at": datetime.fromtimestamp(
                                    story.get("time", 0)
                                ).isoformat(),
                                "relevance_score": min(story.get("score", 0) / 1000, 1.0)
                            })
                
                return topics
    
    async def _get_github_topics(self) -> List[Dict[str, Any]]:
        """Get trending topics from GitHub"""
        async with aiohttp.ClientSession() as session:
            # Get trending repositories
            url = "https://github.com/trending"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"GitHub error: {response.status}")
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                topics = []
                for repo in soup.select("article.Box-row"):
                    title_elem = repo.select_one("h2.h3 a")
                    desc_elem = repo.select_one("p")
                    stars_elem = repo.select_one("a[href$='stargazers']")
                    
                    if title_elem and stars_elem:
                        title = title_elem.get_text(strip=True)
                        description = desc_elem.get_text(strip=True) if desc_elem else "No description available"
                        stars = int(stars_elem.get_text(strip=True).replace(",", ""))
                        
                        topics.append({
                            "title": f"GitHub Trending: {title}",
                            "description": description,
                            "source": "github",
                            "url": f"https://github.com{title_elem['href']}",
                            "published_at": datetime.utcnow().isoformat(),
                            "relevance_score": min(stars / 10000, 1.0)
                        })
                
                return topics
    
    async def _get_medium_topics(self) -> List[Dict[str, Any]]:
        """Get trending topics from Medium"""
        async with aiohttp.ClientSession() as session:
            # Get trending articles
            url = "https://medium.com/tag/programming/recommended"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Medium error: {response.status}")
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                topics = []
                for article in soup.select("article"):
                    title_elem = article.select_one("h2")
                    desc_elem = article.select_one("p")
                    link_elem = article.select_one("a[href*='/p/']")
                    
                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        description = desc_elem.get_text(strip=True) if desc_elem else "No description available"
                        
                        topics.append({
                            "title": f"Medium: {title}",
                            "description": description,
                            "source": "medium",
                            "url": f"https://medium.com{link_elem['href']}",
                            "published_at": datetime.utcnow().isoformat(),
                            "relevance_score": 0.8  # Base score for Medium articles
                        })
                
                return topics
    
    def _combine_topics(self, *topic_lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine and deduplicate topics from different sources"""
        combined = {}
        
        for topic_list in topic_lists:
            for topic in topic_list:
                # Use title as key for deduplication
                title = topic["title"].lower()
                
                if title not in combined:
                    combined[title] = topic
                else:
                    # Merge sources and take highest relevance score
                    existing = combined[title]
                    existing["sources"] = existing.get("sources", {})
                    existing["sources"][topic["source"]] = {
                        "url": topic["url"],
                        "published_at": topic["published_at"]
                    }
                    existing["relevance_score"] = max(
                        existing["relevance_score"],
                        topic["relevance_score"]
                    )
        
        return list(combined.values())
    
    def _calculate_interest_scores(self, topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate interest scores for topics"""
        for topic in topics:
            # Base score from relevance
            score = topic["relevance_score"] * 50  # 0-50 points
            
            # Bonus for multiple sources
            source_count = len(topic.get("sources", {}))
            score += min(source_count * 10, 30)  # Up to 30 points for sources
            
            # Bonus for recency
            if "published_at" in topic:
                published = datetime.fromisoformat(topic["published_at"].replace("Z", "+00:00"))
                hours_old = (datetime.utcnow() - published).total_seconds() / 3600
                recency_bonus = max(0, 20 - (hours_old / 24) * 20)  # Up to 20 points for recency
                score += recency_bonus
            
            topic["interest_score"] = min(score, 100)  # Cap at 100
        
        # Sort by interest score
        return sorted(topics, key=lambda x: x["interest_score"], reverse=True)
    
    async def _save_topics(self, topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Save topics to database"""
        # Archive old topics
        self.db.client.table('trending_topics')\
            .update({'status': 'archived'})\
            .eq('status', 'active')\
            .execute()
        
        # Insert new topics
        for topic in topics:
            topic_data = {
                'title': topic['title'],
                'description': topic['description'],
                'interest_score': topic['interest_score'],
                'sources': topic.get('sources', {}),
                'status': 'active',
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.db.client.table('trending_topics')\
                .insert(topic_data)\
                .execute()
        
        return topics 