import logging
import re
from typing import List, Dict
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

class TagGenerator:
    """AI-powered tag generation service using Gemini"""
    
    def __init__(self):
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.logger = logging.getLogger(__name__)
    
    def generate_tags(self, title: str, content: str, max_tags: int = 8) -> List[str]:
        """
        Generate relevant tags for an article using AI
        
        Args:
            title: Article title
            content: Article content (markdown)
            max_tags: Maximum number of tags to generate
            
        Returns:
            List of generated tags
        """
        try:
            # Clean content for analysis (remove markdown formatting)
            clean_content = self._clean_content(content)
            
            # Create prompt for tag generation
            prompt = f"""
            Analyze the following article and generate {max_tags} relevant tags that best describe its content, topics, and themes.
            
            Article Title: {title}
            
            Article Content: {clean_content[:2000]}...
            
            Requirements:
            - Generate exactly {max_tags} tags
            - Tags should be 1-3 words each
            - Focus on main topics, technologies, concepts, and themes
            - Use lowercase
            - Avoid generic words like "article", "content", "information"
            - Prioritize specific, searchable terms
            - Include both broad categories and specific technical terms
            
            Return only the tags as a comma-separated list, nothing else.
            Example: artificial intelligence, machine learning, python, data science, neural networks, automation, tech trends, innovation
            """
            
            # Generate tags using Gemini
            response = self.model.generate_content(prompt)
            
            # Parse and clean the response
            tags = self._parse_tags_response(response.text)
            
            # Validate and limit tags
            validated_tags = self._validate_tags(tags, max_tags)
            
            self.logger.info(f"Generated {len(validated_tags)} tags for article: {title}")
            return validated_tags
            
        except Exception as e:
            self.logger.error(f"Error generating tags: {str(e)}")
            # Return fallback tags based on title
            return self._generate_fallback_tags(title)
    
    def _clean_content(self, content: str) -> str:
        """Clean markdown content for analysis"""
        # Remove markdown formatting
        content = re.sub(r'#+\s*', '', content)  # Headers
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*(.*?)\*', r'\1', content)  # Italic
        content = re.sub(r'`(.*?)`', r'\1', content)  # Code
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # Links
        content = re.sub(r'\n+', ' ', content)  # Multiple newlines
        content = re.sub(r'\s+', ' ', content)  # Multiple spaces
        
        return content.strip()
    
    def _parse_tags_response(self, response: str) -> List[str]:
        """Parse AI response to extract tags"""
        # Clean the response
        response = response.strip()
        
        # Split by comma and clean each tag
        tags = []
        for tag in response.split(','):
            tag = tag.strip().lower()
            # Remove quotes and extra characters
            tag = re.sub(r'["\'\(\)\[\]{}]', '', tag)
            tag = re.sub(r'^\d+\.\s*', '', tag)  # Remove numbering
            tag = tag.strip()
            
            if tag and len(tag) > 1:
                tags.append(tag)
        
        return tags
    
    def _validate_tags(self, tags: List[str], max_tags: int) -> List[str]:
        """Validate and filter tags"""
        validated = []
        
        # Common words to avoid
        avoid_words = {
            'article', 'content', 'information', 'data', 'system', 'technology',
            'solution', 'approach', 'method', 'way', 'new', 'modern', 'latest',
            'guide', 'tips', 'how', 'what', 'why', 'when', 'where', 'overview'
        }
        
        for tag in tags:
            # Skip if too short or too long
            if len(tag) < 2 or len(tag) > 30:
                continue
                
            # Skip if contains avoided words
            if any(avoid_word in tag.lower() for avoid_word in avoid_words):
                continue
                
            # Skip if already exists (case insensitive)
            if tag.lower() not in [v.lower() for v in validated]:
                validated.append(tag)
                
            # Stop if we have enough tags
            if len(validated) >= max_tags:
                break
        
        return validated[:max_tags]
    
    def _generate_fallback_tags(self, title: str) -> List[str]:
        """Generate simple fallback tags from title if AI fails"""
        # Extract meaningful words from title
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        
        # Common tech and general tags as fallbacks
        fallback_tags = ['research', 'analysis', 'insights', 'trends']
        
        # Combine title words with fallbacks
        tags = words[:4] + fallback_tags
        
        return tags[:6]  # Return max 6 fallback tags

    def suggest_tags_for_search(self, query: str) -> List[str]:
        """Suggest tags based on search query"""
        try:
            prompt = f"""
            Based on this search query: "{query}"
            
            Suggest 5-8 related tags that someone might use to find similar content.
            Focus on:
            - Related topics and concepts
            - Alternative terminology
            - Broader and narrower categories
            - Technical and non-technical terms
            
            Return only the tags as a comma-separated list.
            """
            
            response = self.model.generate_content(prompt)
            tags = self._parse_tags_response(response.text)
            return self._validate_tags(tags, 8)
            
        except Exception as e:
            self.logger.error(f"Error suggesting tags: {str(e)}")
            # Return simple word-based suggestions
            words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
            return words[:5] 