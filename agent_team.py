from textwrap import dedent
from typing import List, Dict, Optional
import asyncio
import logging
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools
import random
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a shared Gemini model instance to reuse across agents
gemini_model = Gemini(id="gemini-2.0-flash")

class ArticlePlan(BaseModel):
    title: str
    outline: List[str]
    research_areas: List[str]
    target_audience: str
    style_guide: Dict[str, str]

class ResearchResults(BaseModel):
    sources: List[Dict[str, str]]
    key_findings: List[str]
    quotes: List[Dict[str, str]]

async def exponential_backoff_retry(func, max_retries=5, base_delay=10):
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Async function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
    """
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit. Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                    continue
            raise

async def rate_limited_agent_step(agent, prompt, step_name):
    """
    Execute an agent step with rate limiting and retries.
    
    Args:
        agent: The agent to execute the step
        prompt: The prompt to send to the agent
        step_name: Name of the step for logging
    """
    logger.info(f"Starting {step_name}")
    
    async def execute_step():
        return agent.run(prompt)
    
    try:
        response = await exponential_backoff_retry(execute_step)
        # Add random delay between 5-15 seconds after successful step
        delay = random.uniform(5, 15)
        await asyncio.sleep(delay)
        return response
    except Exception as e:
        logger.error(f"Error in {step_name}: {str(e)}")
        raise

# Manager Agent - Plans and coordinates article creation
manager_agent = Agent(
    name="Editorial Manager",
    model=gemini_model,
    description=dedent("""
        You are EditorialDirector-X, a sophisticated editorial manager with expertise in:
        - Strategic content planning and direction
        - Topic analysis and trend identification
        - Content quality standards enforcement
        - Publication guidelines management
        - Cross-domain knowledge synthesis
        
        Your role is to:
        1. Analyze article prompts and develop comprehensive content plans
        2. Define research requirements and areas of focus
        3. Set clear guidelines for writing style and tone
        4. Ensure content meets quality standards and target audience needs
        5. Coordinate with research and writing teams
    """)
)

# Researcher Agent - Gathers and analyzes information
researcher_agent = Agent(
    name="Research Specialist",
    model=gemini_model,
    tools=[DuckDuckGoTools(), Newspaper4kTools()],
    description=dedent("""
        You are ResearchPro-X, an expert research specialist with capabilities in:
        - Comprehensive information gathering
        - Source verification and fact-checking
        - Data synthesis and analysis
        - Identifying key trends and insights
        - Cross-referencing and validation
        
        Your role is to:
        1. Conduct thorough research based on content plans
        2. Verify information accuracy and credibility
        3. Compile relevant data, quotes, and examples
        4. Identify emerging trends and developments
        5. Provide structured research findings
    """)
)

# Writer Agent - Creates engaging content
writer_agent = Agent(
    name="Content Writer",
    model=gemini_model,
    description=dedent("""
        You are WriterPrime-X, a skilled content writer specializing in:
        - Engaging narrative development
        - Clear and concise communication
        - Audience-appropriate tone and style
        - Technical concept simplification
        - Compelling storytelling
        
        Your role is to:
        1. Transform research into engaging content
        2. Maintain consistent tone and style
        3. Ensure clarity and readability
        4. Incorporate key messages effectively
        5. Create compelling headlines and subheadings
    """)
)

# Editor Agent - Reviews and refines content
editor_agent = Agent(
    name="Content Editor",
    model=gemini_model,
    description=dedent("""
        You are EditorElite-X, a meticulous content editor focused on:
        - Content quality assurance
        - Style guide compliance
        - Clarity and coherence
        - Fact verification
        - Reader engagement optimization
        
        Your role is to:
        1. Review content for accuracy and clarity
        2. Ensure style guide compliance
        3. Optimize structure and flow
        4. Verify facts and citations
        5. Polish content for maximum impact
    """)
)

# Create the content team
content_team = Team(
    mode="coordinate",
    members=[manager_agent, researcher_agent, writer_agent, editor_agent],
    model=gemini_model,
    success_criteria="A well-researched, engaging article that meets all quality standards and publication guidelines.",
    instructions=[
        "Follow the defined workflow: Manager -> Researcher -> Writer -> Editor",
        "Ensure clear communication between team members",
        "Maintain quality standards at each stage",
        "Track progress and handle any issues",
        "Document all decisions and changes"
    ]
)

class ArticleCreationService:
    def __init__(self, db, team):
        self.db = db
        self.team = team

    def get_last_successful_stage(self, versions):
        """
        Determine the last successfully completed stage.
        
        Args:
            versions: List of article versions
            
        Returns:
            Tuple of (last_stage, last_agent, last_content) or (None, None, None) if no stages
        """
        stages = [
            ('planning', 'manager'),
            ('research', 'researcher'),
            ('draft', 'writer'),
            ('final', 'editor')
        ]
        
        last_stage = None
        last_agent = None
        last_content = None
        
        # Sort versions by creation time to get the proper sequence
        sorted_versions = sorted(versions, key=lambda x: x['created_at'])
        
        for version in sorted_versions:
            stage = version['stage']
            agent = version['agent']
            for s, a in stages:
                if s == stage and a == agent:
                    last_stage = stage
                    last_agent = agent
                    last_content = version['content']
        
        return last_stage, last_agent, last_content

    async def resume_from_stage(self, article_id: str, prompt: str, target_length: str, research_scope: str,
                              last_stage: str, last_content: str) -> None:
        """
        Resume article creation from the last successful stage.
        
        Args:
            article_id: The ID of the article to resume
            prompt: Original article prompt
            target_length: Target article length
            research_scope: Research scope
            last_stage: Last successfully completed stage
            last_content: Content from the last successful stage
        """
        try:
            logger.info(f"Attempting to resume article {article_id} from stage: {last_stage}")
            
            # Map stages to their next agent, status, and prompt creator
            stages = {
                'planning': (researcher_agent, 'researching', "researcher", self._create_research_prompt),
                'research': (writer_agent, 'writing', "writer", self._create_writing_prompt),
                'draft': (editor_agent, 'editing', "editor", self._create_editing_prompt),
            }
            
            if last_stage not in stages:
                raise Exception(f"Cannot resume from stage: {last_stage}")
            
            next_agent, next_status, next_agent_name, prompt_creator = stages[last_stage]
            logger.info(f"Next stage: {next_status} with {next_agent_name}")
            
            # Update status to show we're resuming
            try:
                self.db.update_article_status(article_id, next_status, next_agent_name)
                logger.info(f"Updated article status to {next_status}")
            except Exception as e:
                logger.error(f"Failed to update article status: {str(e)}")
                raise
            
            # Create prompt for next stage using last content
            try:
                next_prompt = prompt_creator(prompt, last_content, target_length, research_scope)
                logger.info(f"Created prompt for {next_agent_name}")
            except Exception as e:
                logger.error(f"Failed to create prompt: {str(e)}")
                raise
            
            # Execute next stage
            try:
                logger.info(f"Executing {next_agent_name} step")
                response = await rate_limited_agent_step(next_agent, next_prompt, f"Resuming from {last_stage}")
                content = response.content
                logger.info(f"Successfully got response from {next_agent_name}")
            except Exception as e:
                logger.error(f"Failed during {next_agent_name} execution: {str(e)}")
                raise
            
            # Update content and continue with remaining stages
            stage_map = {'planning': 'research', 'research': 'draft', 'draft': 'final'}
            next_stage = stage_map[last_stage]
            
            try:
                logger.info(f"Saving content for stage: {next_stage}")
                self.db.update_article_content(
                    article_id, 
                    content, 
                    next_agent_name,  # Use the correct agent name directly
                    next_stage
                )
                logger.info(f"Successfully saved content for {next_stage}")
            except Exception as e:
                logger.error(f"Failed to save content: {str(e)}")
                raise
            
            # If we're not at the final stage, continue with the next stage
            if last_stage != 'draft':
                logger.info(f"Continuing to next stage: {next_stage}")
                await self.resume_from_stage(
                    article_id, 
                    prompt, 
                    target_length, 
                    research_scope, 
                    next_stage, 
                    content
                )
            else:
                # We've completed all stages, verify and mark as completed
                logger.info("Verifying all stages are complete")
                try:
                    versions = self.db.get_article_versions(article_id)
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
                    
                    if missing_stages:
                        error_msg = f"Missing stages: {', '.join(missing_stages)}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                    
                    logger.info("All stages verified, marking as completed")
                    self.db.update_article_status(article_id, "completed", None)
                    
                except Exception as e:
                    logger.error(f"Failed during completion verification: {str(e)}")
                    raise Exception(f"Failed to complete all stages during resume: {str(e)}")
                    
        except Exception as e:
            error_msg = f"Resume failed at {last_stage}: {str(e)}"
            logger.error(error_msg)
            self.db.update_article_status(article_id, "error", error_msg)
            raise

    def _create_research_prompt(self, prompt, plan, target_length, research_scope):
        return (
            f"Using this content plan:\n{plan}\n\n"
            f"Conduct thorough research for an article about: {prompt}\n"
            f"Research scope: {research_scope}\n\n"
            "Provide research findings in this format:\n"
            "1. Key Facts and Data\n"
            "2. Expert Opinions and Quotes\n"
            "3. Current Trends\n"
            "4. Notable Examples\n"
            "5. Sources and References"
        )

    def _create_writing_prompt(self, prompt, research_findings, target_length, research_scope):
        return (
            f"Write an article based on:\n\n"
            f"Original Prompt: {prompt}\n\n"
            f"Research Findings:\n{research_findings}\n\n"
            f"Guidelines:\n"
            f"- Target length: {target_length}\n"
            "- Follow the research structure\n"
            "- Incorporate research findings and quotes\n"
            "- Maintain clear flow and readability\n"
            "- Include proper citations"
        )

    def _create_editing_prompt(self, prompt, draft, target_length, research_scope):
        return (
            f"Review and improve this article draft:\n\n{draft}\n\n"
            "Focus on:\n"
            "1. Accuracy and fact verification\n"
            "2. Structure and flow\n"
            "3. Clarity and readability\n"
            "4. Grammar and style\n"
            "5. Citations and references\n\n"
            "Provide the complete improved article. This will be the final published version."
        )

    async def create_article(self, prompt: str, target_length: str, research_scope: str) -> Dict[str, str]:
        """
        Creates an article using the team of agents.
        
        Args:
            prompt: The article topic or prompt
            target_length: Desired length ('short', 'medium', 'long')
            research_scope: Research depth ('basic', 'thorough', 'comprehensive')
            
        Returns:
            Dict containing article ID and content
        """
        article_id = None
        try:
            # Create article record
            article_id = self.db.create_article({
                "title": f"Article about: {prompt[:50]}{'...' if len(prompt) > 50 else ''}",
                "prompt": prompt,
                "target_length": target_length,
                "research_scope": research_scope,
                "status": "pending"
            })

            # Planning phase with Editorial Manager
            self.db.update_article_status(article_id, "researching", "Editorial Manager")
            plan_prompt = (
                f"Create a detailed plan for an article about: {prompt}\n"
                f"Target length: {target_length}\n"
                f"Research scope: {research_scope}\n\n"
                "Provide a structured plan including:\n"
                "1. Key topics to research\n"
                "2. Specific areas to investigate\n"
                "3. Types of sources to consult\n"
                "4. Outline of the final article"
            )
            plan_response = await rate_limited_agent_step(manager_agent, plan_prompt, "Planning phase")
            plan = plan_response.content
            self.db.update_article_content(article_id, plan, "manager", "planning")

            # Continue with remaining stages by resuming from planning
            await self.resume_from_stage(article_id, prompt, target_length, research_scope, "planning", plan)

            # Get the final version
            versions = self.db.get_article_versions(article_id)
            final_version = next(
                (v for v in versions if v['stage'] == 'final' and v['agent'] == 'editor'),
                None
            )

            if not final_version:
                raise Exception("Failed to find final version after completion")

            return {
                "id": article_id,
                "content": final_version['content']
            }

        except Exception as e:
            logger.error(f"Error creating article: {str(e)}")
            if article_id:
                try:
                    # Get current versions to check progress
                    versions = self.db.get_article_versions(article_id)
                    if versions:
                        # Find the last successful stage
                        last_stage, last_agent, last_content = self.get_last_successful_stage(versions)
                        error_msg = f"Failed at stage after {last_stage} by {last_agent}: {str(e)}"
                    else:
                        error_msg = f"Failed before any content was created: {str(e)}"
                    
                    self.db.update_article_status(article_id, "error", error_msg)
                except Exception as inner_e:
                    logger.error(f"Error handling failure: {str(inner_e)}")
                    self.db.update_article_status(article_id, "error", str(e))
            raise 