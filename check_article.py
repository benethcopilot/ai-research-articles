import logging
from database import Database
import os
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def format_timestamp(ts):
    """Format timestamp for display"""
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    return ts.strftime('%Y-%m-%d %H:%M:%S')

def check_article(article_id: str):
    """Check the state of an article and its versions"""
    try:
        # Initialize database
        db = Database(
            url=os.getenv('SUPABASE_URL'),
            key=os.getenv('SUPABASE_KEY')
        )
        
        # Get article details
        article = db.get_article(article_id)
        if not article:
            logger.error(f"Article {article_id} not found")
            return
            
        # Print article info
        print("\nArticle Information:")
        print("-" * 50)
        print(f"ID: {article.id}")
        print(f"Title: {article.title}")
        print(f"Status: {article.status}")
        print(f"Current Agent: {article.current_agent or 'None'}")
        print(f"Created: {format_timestamp(article.created_at)}")
        print(f"Updated: {format_timestamp(article.updated_at)}")
        print(f"Target Length: {article.target_length}")
        print(f"Research Scope: {article.research_scope}")
        
        # Get all versions
        versions = db.get_article_versions(article_id)
        
        # Check required stages
        required_stages = [
            ('planning', 'manager'),
            ('research', 'researcher'),
            ('draft', 'writer'),
            ('final', 'editor')
        ]
        
        print("\nStage Completion Status:")
        print("-" * 50)
        for stage, agent in required_stages:
            matching_versions = [
                v for v in versions 
                if v['stage'] == stage and v['agent'] == agent
            ]
            status = "✓" if matching_versions else "✗"
            timestamp = format_timestamp(matching_versions[0]['created_at']) if matching_versions else "Not completed"
            print(f"{status} {stage.title()} by {agent}: {timestamp}")
        
        # Print version history
        print("\nVersion History:")
        print("-" * 50)
        for version in sorted(versions, key=lambda x: x['created_at']):
            print(f"Stage: {version['stage']}")
            print(f"Agent: {version['agent']}")
            print(f"Created: {format_timestamp(version['created_at'])}")
            print(f"Content Length: {len(version['content'])} characters")
            print("-" * 25)
        
        # Analyze potential issues
        print("\nDiagnostic Information:")
        print("-" * 50)
        
        # Check stage sequence
        if versions:
            stages_in_order = []
            for v in sorted(versions, key=lambda x: x['created_at']):
                stages_in_order.append((v['stage'], v['agent']))
            
            expected_order = [s[0] for s in required_stages]
            actual_order = [s[0] for s in stages_in_order]
            
            if actual_order != expected_order[:len(actual_order)]:
                print("⚠️ Warning: Stages not completed in expected order")
                print(f"Expected: {' -> '.join(expected_order)}")
                print(f"Actual: {' -> '.join(actual_order)}")
        
        # Check for missing stages
        missing_stages = []
        for stage, agent in required_stages:
            if not any(v['stage'] == stage and v['agent'] == agent for v in versions):
                missing_stages.append(f"{stage} by {agent}")
        
        if missing_stages:
            print("\n⚠️ Missing Stages:")
            for stage in missing_stages:
                print(f"- {stage}")
        
        # Check status consistency
        if article.status == 'completed' and missing_stages:
            print("\n⚠️ Inconsistency: Article marked as completed but missing required stages")
        
        if article.status == 'error':
            print("\n⚠️ Article is in error state")
            print(f"Current Agent: {article.current_agent}")
            
    except Exception as e:
        logger.error(f"Error checking article: {str(e)}")
        raise

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print("Usage: python check_article.py <article_id>")
        sys.exit(1)
    
    article_id = sys.argv[1]
    check_article(article_id) 