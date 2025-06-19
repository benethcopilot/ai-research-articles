from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from database import Database
import markdown2
import os
from dotenv import load_dotenv
from datetime import datetime
import asyncio
from agent_team import content_team, ArticleCreationService
from topic_researcher import TopicResearcher
from tag_generator import TagGenerator
import logging
import hashlib
import uuid

# Load environment variables
load_dotenv()

# Get required environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')  # Simple admin password

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing required environment variables SUPABASE_URL and/or SUPABASE_KEY")

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev')  # Set a secret key for flash messages

# Initialize database and services
db = Database(url=SUPABASE_URL, key=SUPABASE_KEY)
article_service = ArticleCreationService(db, content_team)
topic_researcher = TopicResearcher(db)
tag_generator = TagGenerator()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_session_id():
    """Get or create a session ID for analytics"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def get_client_ip():
    """Get client IP address"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
    else:
        return request.environ.get('REMOTE_ADDR')

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

# ===== SEARCH ROUTES =====

@app.route('/search')
def search():
    """Search articles with filters"""
    try:
        query = request.args.get('q', '').strip()
        tags = request.args.getlist('tags')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        target_length = request.args.get('target_length')
        
        # Search articles
        articles = db.search_articles(
            query=query,
            tags=tags if tags else None,
            date_from=date_from,
            date_to=date_to,
            target_length=target_length
        )
        
        # Format dates and add tags for each article
        formatted_articles = []
        for article in articles:
            article = format_article_dates(article)
            article['tags'] = db.get_article_tags(article['id'])
            formatted_articles.append(article)
        
        # Get suggested tags if there's a query
        suggested_tags = []
        if query:
            suggested_tags = tag_generator.suggest_tags_for_search(query)
        
        return render_template('search.html', 
                             articles=formatted_articles,
                             query=query,
                             tags=tags,
                             date_from=date_from,
                             date_to=date_to,
                             target_length=target_length,
                             suggested_tags=suggested_tags)
    except Exception as e:
        app.logger.error(f"Error in search route: {str(e)}")
        flash(f"Error searching articles: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/api/search-suggestions')
def search_suggestions():
    """Get search suggestions based on query"""
    try:
        query = request.args.get('q', '').strip()
        if not query or len(query) < 2:
            return jsonify([])
        
        # Get articles that match the query for autocomplete
        articles = db.search_articles(query=query)
        suggestions = []
        
        # Extract unique titles and add to suggestions
        for article in articles[:10]:  # Limit to 10 suggestions
            if article['title'] not in suggestions:
                suggestions.append(article['title'])
        
        return jsonify(suggestions)
    except Exception as e:
        app.logger.error(f"Error getting search suggestions: {str(e)}")
        return jsonify([])

# ===== ANALYTICS ROUTES =====

@app.route('/api/track-view', methods=['POST'])
def track_view():
    """Track article view for analytics"""
    try:
        data = request.get_json()
        article_id = data.get('article_id')
        
        if not article_id:
            return jsonify({'error': 'Missing article_id'}), 400
        
        # Track the view
        db.track_article_view(
            article_id=article_id,
            session_id=get_session_id(),
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
            referrer=request.referrer
        )
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error tracking view: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/track-reading-time', methods=['POST'])
def track_reading_time():
    """Track reading time for analytics"""
    try:
        data = request.get_json()
        article_id = data.get('article_id')
        time_spent = data.get('time_spent_seconds', 0)
        
        if not article_id:
            return jsonify({'error': 'Missing article_id'}), 400
        
        # Track reading time
        db.track_reading_time(
            article_id=article_id,
            session_id=get_session_id(),
            time_spent_seconds=int(time_spent)
        )
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error tracking reading time: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ===== ADMIN ROUTES =====

@app.route('/admin')
def admin_login():
    """Admin login page"""
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_authenticate():
    """Authenticate admin user"""
    password = request.form.get('password')
    if password == ADMIN_PASSWORD:
        session['admin_authenticated'] = True
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Invalid password', 'danger')
        return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if not session.get('admin_authenticated'):
        return redirect(url_for('admin_login'))
    
    try:
        # Get popular articles
        popular_articles = db.get_popular_articles(limit=10)
        
        # Format dates for popular articles
        for article in popular_articles:
            if isinstance(article.get('created_at'), str):
                try:
                    article['created_at'] = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
                except:
                    article['created_at'] = None
        
        # Get performance metrics
        performance_metrics = db.get_performance_metrics()
        
        # Format dates for performance metrics
        for metric in performance_metrics:
            if isinstance(metric.get('created_at'), str):
                try:
                    metric['created_at'] = datetime.fromisoformat(metric['created_at'].replace('Z', '+00:00'))
                except:
                    metric['created_at'] = None
        
        # Get articles for moderation
        pending_moderation = db.get_articles_for_moderation(status='pending')
        
        # Format dates for moderation records
        for moderation in pending_moderation:
            if isinstance(moderation.get('created_at'), str):
                try:
                    moderation['created_at'] = datetime.fromisoformat(moderation['created_at'].replace('Z', '+00:00'))
                except:
                    moderation['created_at'] = None
        
        return render_template('admin_dashboard.html',
                             popular_articles=popular_articles,
                             performance_metrics=performance_metrics[:20],  # Last 20 metrics
                             pending_moderation=pending_moderation)
    except Exception as e:
        app.logger.error(f"Error in admin dashboard: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", 'danger')
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
def admin_logout():
    """Logout admin user"""
    session.pop('admin_authenticated', None)
    return redirect(url_for('index'))

@app.route('/admin/moderate/<article_id>', methods=['POST'])
def moderate_article(article_id):
    """Moderate an article (approve/reject)"""
    if not session.get('admin_authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        status = data.get('status')
        moderator_notes = data.get('moderator_notes', '')
        
        if status not in ['approved', 'rejected']:
            return jsonify({'error': 'Invalid status'}), 400
        
        # Update moderation status
        db.update_moderation_status(
            article_id=article_id,
            status=status,
            moderator_notes=moderator_notes,
            moderated_by='admin'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error moderating article: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ===== EXISTING ROUTES (UPDATED) =====

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
        
        # Format dates and add tags for each article
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
                article_data = format_article_dates(article_data)
                article_data['tags'] = db.get_article_tags(article_data['id'])
                articles.append(article_data)
                
        return render_template('index.html', articles=articles)
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        return f"Error loading articles: {str(e)}", 500

@app.route('/article/<article_id>')
def article(article_id):
    """Show a specific article"""
    try:
        # Track article view
        db.track_article_view(
            article_id=article_id,
            session_id=get_session_id(),
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
            referrer=request.referrer
        )
        
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
        
        # Get article tags
        article_data['tags'] = db.get_article_tags(article_id)
        
        # Get article analytics
        article_data['analytics'] = db.get_article_analytics(article_id)
        
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