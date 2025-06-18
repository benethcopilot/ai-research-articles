import os
from dotenv import load_dotenv
from database import Database
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_connection():
    try:
        # Initialize database using environment variables
        db = Database(
            url=os.getenv('SUPABASE_URL'),
            key=os.getenv('SUPABASE_KEY')
        )
        
        logger.info("Testing database connection...")
        
        # Try to list all articles
        response = db.client.table('articles').select("*").execute()
        articles = response.data
        
        logger.info(f"Found {len(articles)} articles")
        
        print("\nArticle List:")
        print("-" * 50)
        
        for article in articles:
            print(f"ID: {article['id']}")
            print(f"Title: {article['title']}")
            print(f"Status: {article['status']}")
            print(f"Current Agent: {article.get('current_agent', 'None')}")
            print("-" * 25)
            
            # If we find our target article, get its versions
            if article['id'] in ['657e0470-9ddc-4596-99b0-40dc9bdf4fcc', '32771f7c-b476-42b0-9fe5-bb84cb065251']:
                logger.info(f"Found target article {article['id']}, fetching versions...")
                versions = db.get_article_versions(article['id'])
                
                print("\nVersion History:")
                print("-" * 50)
                for version in sorted(versions, key=lambda x: x['created_at']):
                    print(f"Stage: {version['stage']}")
                    print(f"Agent: {version['agent']}")
                    print(f"Created: {version['created_at']}")
                    print(f"Content Length: {len(version['content'])} characters")
                    print("-" * 25)
            
    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}")
        raise

if __name__ == '__main__':
    test_connection() 