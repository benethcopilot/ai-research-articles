import asyncio
import logging
from datetime import datetime
from database import Database
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_article_stages(versions):
    """Check if article has all required stages in correct order"""
    required_stages = [
        ('planning', 'manager'),
        ('research', 'researcher'),
        ('draft', 'writer'),
        ('final', 'editor')
    ]
    
    # Check each required stage
    missing_stages = []
    for stage, agent in required_stages:
        if not any(v['stage'] == stage and v['agent'] == agent for v in versions):
            missing_stages.append(f"{stage} by {agent}")
            
    return missing_stages

async def cleanup_articles():
    """Find and fix articles in inconsistent states"""
    try:
        # Initialize database
        db = Database(
            url=os.getenv('SUPABASE_URL'),
            key=os.getenv('SUPABASE_KEY')
        )
        
        # Get all completed articles
        response = db.client.table('articles')\
            .select('*')\
            .eq('status', 'completed')\
            .execute()
            
        completed_articles = response.data
        logger.info(f"Found {len(completed_articles)} articles marked as completed")
        
        fixed_count = 0
        for article in completed_articles:
            article_id = article['id']
            
            # Get all versions for this article
            versions = db.get_article_versions(article_id)
            
            # Check for missing stages
            missing_stages = check_article_stages(versions)
            
            if missing_stages:
                # Article is in inconsistent state
                error_msg = f"Missing stages: {', '.join(missing_stages)}"
                logger.warning(f"Article {article_id} ({article['title']}) is incomplete: {error_msg}")
                
                try:
                    # Update article status to error
                    db.update_article_status(article_id, "error", f"Incomplete article: {error_msg}")
                    fixed_count += 1
                    logger.info(f"Updated article {article_id} status to error")
                except Exception as e:
                    logger.error(f"Failed to update article {article_id}: {str(e)}")
                    continue
        
        logger.info(f"Cleanup complete. Fixed {fixed_count} articles.")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise

if __name__ == '__main__':
    logger.info("Starting article cleanup")
    asyncio.run(cleanup_articles()) 