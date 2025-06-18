import asyncio
import logging
from database import Database
from agent_team import ArticleCreationService, content_team
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_article_creation():
    try:
        # Initialize database and service
        db = Database(
            url=os.getenv('SUPABASE_URL'),
            key=os.getenv('SUPABASE_KEY')
        )
        service = ArticleCreationService(db, content_team)
        
        # Test article parameters
        prompt = "Write about the latest advancements in renewable energy technology"
        target_length = "medium"
        research_scope = "basic"
        
        logger.info(f"Creating article with prompt: {prompt}")
        
        # Create the article
        result = await service.create_article(
            prompt=prompt,
            target_length=target_length,
            research_scope=research_scope
        )
        
        logger.info(f"Article created with ID: {result['id']}")
        
        # Check the article status
        article = db.get_article(result['id'])
        logger.info(f"Article status: {article.status}")
        
        # Get and display versions
        versions = db.get_article_versions(result['id'])
        logger.info("\nVersion History:")
        for version in sorted(versions, key=lambda x: x['created_at']):
            logger.info(f"Stage: {version['stage']}")
            logger.info(f"Agent: {version['agent']}")
            logger.info(f"Created: {version['created_at']}")
            logger.info("-" * 25)
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        raise

if __name__ == '__main__':
    asyncio.run(test_article_creation()) 