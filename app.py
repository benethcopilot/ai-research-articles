from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from database import Database
import markdown2
import os
from dotenv import load_dotenv
from datetime import datetime
import asyncio
from agent_team import content_team, ArticleCreationService
from topic_researcher import TopicResearcher
import logging

# Load environment variables
load_dotenv()

# Get required environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing required environment variables SUPABASE_URL and/or SUPABASE_KEY")

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev')  # Set a secret key for flash messages

# Initialize database and article service
db = Database(url=SUPABASE_URL, key=SUPABASE_KEY)
article_service = ArticleCreationService(db, content_team)
topic_researcher = TopicResearcher(db)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def format_article_dates(article):
    """Format dates in article data for display"""
    if isinstance(article.get('created_at'), str):
        article['created_at'] = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
    if isinstance(article.get('updated_at'), str):
        article['updated_at'] = datetime.fromisoformat(article['updated_at'].replace('Z', '+00:00'))
    return article

async def process_article(article_data):
    """Process a single article using the article service"""
    try:
        await article_service.create_article(
            prompt=article_data['prompt'],
            target_length=article_data['target_length'],
            research_scope=article_data['research_scope']
        )
    except Exception as e:
        app.logger.error(f"Error processing article: {str(e)}")
        raise

@app.route('/')
def index():
    """Show list of all completed articles"""
    try:
        # Get all completed articles from Supabase
        response = db.client.table('articles')\
            .select('*')\
            .eq('status', 'completed')\
            .order('created_at', desc=True)\
            .execute()
        
        # Format dates for each article
        articles = []
        for article_data in response.data:
            # Get all versions for this article
            versions = db.get_article_versions(article_data['id'])
            
            # Validate article has gone through all required stages
            has_all_stages = all(
                any(v['stage'] == stage and v['agent'] == agent 
                    for v in versions)
                for stage, agent in [
                    ('planning', 'manager'),
                    ('research', 'researcher'),
                    ('draft', 'writer'),
                    ('final', 'editor')
                ]
            )
            
            # Only include properly completed articles
            if has_all_stages:
                articles.append(format_article_dates(article_data))
                
        return render_template('index.html', articles=articles)
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        return f"Error loading articles: {str(e)}", 500

@app.route('/article/<article_id>')
def article(article_id):
    """Show a specific article"""
    try:
        # Get article details
        article = db.get_article(article_id)
        if not article:
            return "Article not found", 404

        # Get all versions
        versions = db.get_article_versions(article_id)
        if not versions:
            return "No content found", 404
            
        # Validate article has gone through all required stages
        has_all_stages = all(
            any(v['stage'] == stage and v['agent'] == agent 
                for v in versions)
            for stage, agent in [
                ('planning', 'manager'),
                ('research', 'researcher'),
                ('draft', 'writer'),
                ('final', 'editor')
            ]
        )
        
        if not has_all_stages:
            flash('This article is not yet ready for viewing', 'warning')
            return redirect(url_for('index'))
        
        # Find the final version from the editor
        final_version = None
        for version in versions:
            if version['stage'] == 'final' and version['agent'] == 'editor':
                final_version = version
                break
                
        if not final_version:
            flash('Final version not found', 'warning')
            return redirect(url_for('index'))
        
        # Format article dates
        article_data = {
            'id': article.id,
            'title': article.title,
            'prompt': article.prompt,
            'research_scope': article.research_scope,
            'target_length': article.target_length,
            'status': article.status,
            'created_at': article.created_at,
            'updated_at': article.updated_at
        }
        article_data = format_article_dates(article_data)
        
        # Convert markdown content to HTML
        html_content = markdown2.markdown(final_version['content'])
        
        return render_template('article.html', 
                             article=article_data, 
                             content=html_content)
    except Exception as e:
        app.logger.error(f"Error in article route: {str(e)}")
        return f"Error loading article: {str(e)}", 500

@app.route('/prompts')
def prompts():
    """Show list of all prompts"""
    try:
        # Get all articles (prompts) ordered by creation date
        response = db.client.table('articles')\
            .select('*')\
            .order('created_at', desc=True)\
            .execute()
        
        # Format dates for each prompt
        prompts = [format_article_dates(prompt) for prompt in response.data]
        return render_template('prompts.html', prompts=prompts)
    except Exception as e:
        app.logger.error(f"Error in prompts route: {str(e)}")
        flash(f"Error loading prompts: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/submit-prompt', methods=['GET', 'POST'])
def submit_prompt():
    """Handle prompt submission"""
    if request.method == 'POST':
        try:
            # Create new article with submitted data
            article_data = {
                'title': request.form['title'],
                'prompt': request.form['prompt'],
                'research_scope': request.form['research_scope'],
                'target_length': request.form['target_length'],
                'status': 'pending'
            }
            
            # Start processing the article asynchronously
            asyncio.run(process_article(article_data))
            
            return jsonify({'success': True})
        except Exception as e:
            app.logger.error(f"Error submitting prompt: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('submit_prompt.html')

@app.route('/prompt/<prompt_id>/pause', methods=['POST'])
def pause_prompt(prompt_id):
    """Pause article generation"""
    try:
        db.update_article_status(prompt_id, 'paused')
        flash('Prompt paused successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Error pausing prompt: {str(e)}")
        flash(f"Error pausing prompt: {str(e)}", 'danger')
    return redirect(url_for('prompts'))

@app.route('/prompt/<prompt_id>/resume', methods=['POST'])
def resume_prompt(prompt_id):
    """Resume article generation"""
    try:
        # Get the article data
        article = db.get_article(prompt_id)
        if not article:
            flash('Article not found', 'danger')
            return redirect(url_for('prompts'))
            
        # Update status to pending
        db.update_article_status(prompt_id, 'pending')
        
        # Start processing the article asynchronously
        article_data = {
            'title': article.title,
            'prompt': article.prompt,
            'research_scope': article.research_scope,
            'target_length': article.target_length,
            'status': 'pending'
        }
        asyncio.run(process_article(article_data))
        
        flash('Prompt resumed successfully and processing has started!', 'success')
    except Exception as e:
        app.logger.error(f"Error resuming prompt: {str(e)}")
        flash(f"Error resuming prompt: {str(e)}", 'danger')
    return redirect(url_for('prompts'))

@app.route('/prompt/<prompt_id>/delete', methods=['POST'])
def delete_prompt(prompt_id):
    """Delete an article prompt"""
    try:
        # Delete the article and its versions (cascade delete is handled by the database)
        db.client.table('articles').delete().eq('id', prompt_id).execute()
        flash('Prompt deleted successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Error deleting prompt: {str(e)}")
        flash(f"Error deleting prompt: {str(e)}", 'danger')
    return redirect(url_for('prompts'))

# Trending Topics Routes
@app.route('/trending-topics')
def trending_topics():
    """Show trending topics page"""
    try:
        # Get active trending topics
        response = db.client.table('trending_topics')\
            .select('*')\
            .eq('status', 'active')\
            .order('interest_score', desc=True)\
            .execute()
        
        topics = [format_article_dates(topic) for topic in response.data]
        return render_template('trending_topics.html', topics=topics)
    except Exception as e:
        app.logger.error(f"Error loading trending topics: {str(e)}")
        flash(f"Error loading trending topics: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/api/refresh-topics', methods=['POST'])
def refresh_topics():
    """Refresh trending topics"""
    try:
        # Run the async research_trending_topics function
        topics = asyncio.run(topic_researcher.research_trending_topics())
        return jsonify({'success': True, 'count': len(topics)})
    except Exception as e:
        app.logger.error(f"Error refreshing topics: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/create-article', methods=['POST'])
def create_article_from_topic():
    """Create an article from a trending topic"""
    try:
        topic_id = request.form.get('topic_id')
        if not topic_id:
            return jsonify({'success': False, 'error': 'No topic ID provided'}), 400
            
        # Get topic details
        response = db.client.table('trending_topics')\
            .select('*')\
            .eq('id', topic_id)\
            .single()\
            .execute()
            
        if not response.data:
            return jsonify({'success': False, 'error': 'Topic not found'}), 404
            
        topic = response.data
        
        # Create article data
        article_data = {
            'title': f"Article about: {topic['title']}",
            'prompt': f"{topic['title']}\n\n{topic['description']}",
            'research_scope': request.form.get('research_scope', 'thorough'),
            'target_length': request.form.get('target_length', 'medium'),
            'status': 'pending'
        }
        
        # Start processing the article
        asyncio.run(process_article(article_data))
        
        # Update topic status
        db.client.table('trending_topics')\
            .update({'status': 'selected'})\
            .eq('id', topic_id)\
            .execute()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error creating article from topic: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 