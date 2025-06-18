import asyncio
import logging
from datetime import datetime
from agent_team import content_team, ArticleCreationService
from database import Database
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_article_creation():
    """Test article creation with the agent team"""
    try:
        # Initialize database and service
        db = Database(
            url=os.getenv("SUPABASE_URL"),
            key=os.getenv("SUPABASE_KEY")
        )
        service = ArticleCreationService(db, content_team)
        
        # Test prompt
        prompt = "Write about the latest developments in quantum computing"
        logger.info(f"Starting article creation test with prompt: {prompt}")
        
        # Create article
        article_data = await service.create_article(
            prompt=prompt,
            target_length="medium",
            research_scope="thorough"
        )
        
        # Log success
        logger.info("Article created successfully!")
        logger.info(f"\nGenerated Article:\n{article_data['content']}")
        
        # Get all versions
        versions = db.get_article_versions(article_data['id'])
        logger.info("\nArticle Versions:")
        for version in versions:
            logger.info(f"\nStage: {version['stage']}")
            logger.info(f"Agent: {version['agent']}")
            logger.info(f"Content:\n{version['content']}\n")
            logger.info("-" * 80)
            
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_article_creation()) 