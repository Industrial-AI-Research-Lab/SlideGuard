"""
Agents for slides evaluation and presentation analysis on multiple criteria
"""

from typing import List, Dict, Any, Optional
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager
from slideguard.criteria import (
    get_slide_criteria, 
    get_deck_criteria, 
    get_criteria_for_slide_types,
    get_criteria_sorted_by_priority,
    CriterionInfo,
    slide_helper_type
)

from textwrap import dedent
from crewai import Agent, Task, Crew
from pydantic import BaseModel
import json
import asyncio

# Optional import for search tools
try:
    from duckduckgo_search import DDGS
    DUCKDUCKGO_AVAILABLE = True
except ImportError:
    DUCKDUCKGO_AVAILABLE = False
    DDGS = None

class EvaluationResult(BaseModel):
    """Result of a single criterion evaluation"""
    criterion_name: str
    criterion_type: str
    slide_id: Optional[str] = None
    result: Dict[str, Any]
    score: Optional[int] = None
    suggestions: List[str] = []

class SlideEvaluationResult(BaseModel):
    """Result of slide-level evaluation"""
    slide_id: str
    slide_type: List[str]
    slide_description: str
    evaluations: List[EvaluationResult]

class DeckEvaluationResult(BaseModel):
    """Result of deck-level evaluation"""
    deck_name: str
    slide_evaluations: List[SlideEvaluationResult]
    deck_evaluations: List[EvaluationResult]
    overall_score: float
    summary: str

class SlideGuardAgents:
    """Crew of agents for comprehensive slide deck evaluation"""
    
    def __init__(self,
                 file_manager: FileManager,
                 cache_manager: CacheManager,
                 llm=None):
        self.file_manager = file_manager
        self.cache_manager = cache_manager
        self.llm = llm
        self.tools = self._setup_tools()

    def _create_duckduckgo_search_tool(self):
        """Create a DuckDuckGo search tool for CrewAI"""
        if not DUCKDUCKGO_AVAILABLE:
            return None
            
        # Create a tool dictionary that CrewAI can understand
        tool_dict = {
            "name": "duckduckgo_search",
            "description": "Search DuckDuckGo for information related to a query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    }
                },
                "required": ["query"]
            },
            "function": self._duckduckgo_search_function
        }
        
        return tool_dict
        
    def _duckduckgo_search_function(self, query: str) -> str:
        """
        Internal function to perform DuckDuckGo search.
        
        Args:
            query: The search query string
            
        Returns:
            String containing search results
        """
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                
            if not results:
                return "No search results found."
            
            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                body = result.get('body', 'No description')
                url = result.get('href', 'No URL')
                formatted_results.append(f"{i}. {title}\n   {body}\n   URL: {url}\n")
            
            return "\n".join(formatted_results)
            
        except Exception as e:
            return f"Search failed: {str(e)}"

    def _setup_tools(self) -> List:
        """Setup tools for agents"""
        tools = []
        # Note: Search tools temporarily disabled for vLLM compatibility
        # The core evaluation functionality works without external search
        print("Info: Using core evaluation tools only (search tools disabled for vLLM compatibility)")
        
        return tools

    def create_slide_type_agent(self) -> Agent:
        """Agent responsible for determining slide types"""
        return Agent(
            role="Slide Type Classifier",
            goal="Accurately classify each slide into appropriate types based on content and structure",
            backstory=dedent("""
                You are an expert presentation analyst with deep understanding of slide types and structures.
                You can quickly identify whether a slide is a title slide, motivation slide, goals slide, 
                tasks slide, current state slide, proposed solution slide, experiment settings slide, 
                experimental results slide, conclusion slide, or separator slide.
                Your classifications help other agents understand the context and purpose of each slide.
            """),
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def create_slide_description_agent(self) -> Agent:
        """Agent responsible for creating detailed slide descriptions"""
        return Agent(
            role="Slide Description Specialist",
            goal="Create comprehensive, detailed descriptions of slide content for analysis",
            backstory=dedent("""
                You are a meticulous slide content analyst who excels at extracting and describing
                all visual elements, text content, charts, tables, and layout information from slides.
                Your descriptions are used by other agents to perform various evaluations and analyses.
                You never make assumptions about content not visible in the slide.
            """),
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def create_visual_arrangement_agent(self) -> Agent:
        """Agent responsible for evaluating visual arrangement and readability"""
        return Agent(
            role="Visual Design Evaluator",
            goal="Evaluate slide visual design, readability, and user experience",
            backstory=dedent("""
                You are a UI/UX expert specializing in presentation design and visual communication.
                You evaluate color schemes, typography, layout, spacing, and overall visual hierarchy.
                You identify issues that could impact readability or audience engagement and provide
                specific, actionable recommendations for improvement.
            """),
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def create_deck_structure_agent(self) -> Agent:
        """Agent responsible for evaluating overall deck structure and completeness"""
        return Agent(
            role="Presentation Structure Analyst",
            goal="Evaluate the completeness and logical flow of the entire presentation",
            backstory=dedent("""
                You are a presentation strategy expert who understands the essential elements
                of effective presentations. You evaluate whether presentations contain all necessary
                components like title slides, motivation, goals, tasks, current state, proposed solutions,
                experimental results, and conclusions. You assess the logical flow and completeness
                of the presentation structure.
            """),
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def create_summary_agent(self) -> Agent:
        """Agent responsible for creating final evaluation summary"""
        return Agent(
            role="Evaluation Summary Coordinator",
            goal="Synthesize all evaluation results into a comprehensive, actionable summary",
            backstory=dedent("""
                You are an expert at synthesizing complex evaluation data into clear, actionable insights.
                You take results from multiple specialized agents and create a coherent summary that
                highlights key findings, identifies priority areas for improvement, and provides
                an overall assessment score. Your summaries help presenters understand exactly
                what needs to be improved and why.
            """),
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def create_custom_criterion_agent(self, criterion: CriterionInfo) -> Agent:
        """Create an agent for a specific custom criterion"""
        return Agent(
            role=f"{criterion.criterion_name} Specialist",
            goal=f"Evaluate slides based on the {criterion.criterion_name} criterion",
            backstory=dedent(f"""
                You are a specialized evaluator focused on {criterion.criterion_name}.
                {criterion.criterion_description}
                You provide detailed, objective assessments based on this specific criterion.
            """),
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    async def evaluate_slide(self, 
                           slide_image_path: str, 
                           slide_id: str,
                           slide_criteria: List[CriterionInfo] = None,
                           slide_types: List[str] = None) -> SlideEvaluationResult:
        """Evaluate a single slide using multiple criteria"""
        
        if slide_criteria is None:
            if slide_types:
                # Filter criteria based on slide types
                slide_criteria = get_criteria_for_slide_types(slide_types)
            else:
                slide_criteria = get_slide_criteria()
        
        # Sort criteria by priority
        slide_criteria = get_criteria_sorted_by_priority("slide")

        # Create agents for this evaluation
        type_agent = self.create_slide_type_agent()
        desc_agent = self.create_slide_description_agent()
        visual_agent = self.create_visual_arrangement_agent()
        
        # Create tasks
        tasks = []
        
        # Task 1: Determine slide type
        from slideguard.criteria.slide_helper_type import get_slide_helper_type_prompt
        
        type_task = Task(
            description=dedent(f"""
                Analyze the slide image at {slide_image_path} and determine its type(s).
                
                {get_slide_helper_type_prompt(
                    schema_format=slide_helper_type.criterion_schema.model_json_schema(),
                    description="Analyze the provided slide image"
                )}
            """),
            agent=type_agent,
            expected_output="JSON with slide_type field containing list of applicable slide types"
        )
        tasks.append(type_task)
        
        # Task 2: Create detailed description
        desc_task = Task(
            description=dedent(f"""
                Create a detailed description of the slide at {slide_image_path}.
                Use the slide_helper_description criterion to provide comprehensive analysis.
                Return the result in JSON format with title, description, and summary fields.
            """),
            agent=desc_agent,
            expected_output="JSON with title, description, and summary fields"
        )
        tasks.append(desc_task)
        
        # Task 3: Evaluate visual arrangement
        visual_task = Task(
            description=dedent(f"""
                Evaluate the visual arrangement and readability of the slide at {slide_image_path}.
                Use the slide_visual_arrangement criterion to assess design quality.
                Return the result in JSON format with evaluation_results and score fields.
            """),
            agent=visual_agent,
            expected_output="JSON with evaluation_results and score fields"
        )
        tasks.append(visual_task)
        
        # Create custom criterion tasks
        custom_agents = []
        for criterion in slide_criteria:
            if criterion.criterion_name not in ["Slide Type", "Slide Description", "Slide Visual Arrangement"]:
                # Check if criterion requires slide type and we have it
                if criterion.requires_slide_type and slide_types:
                    # Add slide type context to the prompt
                    slide_type_context = f"Slide types: {', '.join(slide_types)}"
                    enhanced_prompt = f"{criterion.criterion_prompt}\n\nContext: {slide_type_context}"
                else:
                    enhanced_prompt = criterion.criterion_prompt
                
                agent = self.create_custom_criterion_agent(criterion)
                custom_agents.append(agent)
                
                task = Task(
                    description=dedent(f"""
                        Evaluate the slide at {slide_image_path} using the {criterion.criterion_name} criterion.
                        {enhanced_prompt}
                        Return the result in the specified JSON format.
                    """),
                    agent=agent,
                    expected_output=f"JSON result for {criterion.criterion_name} evaluation"
                )
                tasks.append(task)
        
        # Execute tasks
        crew = Crew(
            agents=[type_agent, desc_agent, visual_agent] + custom_agents,
            tasks=tasks,
            verbose=True
        )
        
        result = await crew.kickoff()
        
        # Parse results and create SlideEvaluationResult
        evaluations = []
        slide_type = []
        slide_description = ""
        
        # Parse the crew result to extract individual task results
        # This is a simplified parsing - in practice you'd need more robust parsing
        try:
            # Extract slide type
            type_result = self._extract_json_from_result(result, "slide_type")
            if type_result and "slide_type" in type_result:
                slide_type = type_result["slide_type"]
            else:
                slide_type = []
            
            # Extract description
            desc_result = self._extract_json_from_result(result, "description")
            if desc_result and "description" in desc_result:
                slide_description = desc_result["description"]
            
            # Extract visual arrangement evaluation
            visual_result = self._extract_json_from_result(result, "evaluation_results")
            if visual_result:
                evaluations.append(EvaluationResult(
                    criterion_name="Slide Visual Arrangement",
                    criterion_type="slide",
                    slide_id=slide_id,
                    result=visual_result,
                    score=visual_result.get("score"),
                    suggestions=self._extract_suggestions(visual_result)
                ))
                
        except Exception as e:
            print(f"Error parsing slide evaluation results: {e}")
        
        return SlideEvaluationResult(
            slide_id=slide_id,
            slide_type=slide_type,
            slide_description=slide_description,
            evaluations=evaluations
        )

    async def evaluate_deck(self, 
                          presentation_path: str,
                          slide_descriptions: List[str],
                          deck_criteria: List[CriterionInfo] = None) -> List[EvaluationResult]:
        """Evaluate the entire deck structure"""
        
        if deck_criteria is None:
            deck_criteria = get_deck_criteria()
        
        deck_agent = self.create_deck_structure_agent()
        
        # Combine all slide descriptions
        combined_descriptions = "\n\n".join([
            f"Slide {i+1}:\n{desc}" for i, desc in enumerate(slide_descriptions)
        ])
        
        tasks = []
        for criterion in deck_criteria:
            task = Task(
                description=dedent(f"""
                    Evaluate the entire presentation structure using the {criterion.criterion_name} criterion.
                    
                    Presentation slides:
                    {combined_descriptions}
                    
                    {criterion.criterion_prompt}
                    
                    Return the result in the specified JSON format.
                """),
                agent=deck_agent,
                expected_output=f"JSON result for {criterion.criterion_name} evaluation"
            )
            tasks.append(task)
        
        crew = Crew(
            agents=[deck_agent],
            tasks=tasks,
            verbose=True
        )
        
        result = await crew.kickoff()
        
        # Parse results
        evaluations = []
        try:
            for criterion in deck_criteria:
                criterion_result = self._extract_json_from_result(result, criterion.criterion_name)
                if criterion_result:
                    evaluations.append(EvaluationResult(
                        criterion_name=criterion.criterion_name,
                        criterion_type="deck",
                        result=criterion_result,
                        score=criterion_result.get("score"),
                        suggestions=self._extract_suggestions(criterion_result)
                    ))
        except Exception as e:
            print(f"Error parsing deck evaluation results: {e}")
        
        return evaluations

    async def create_final_summary(self, 
                                 slide_evaluations: List[SlideEvaluationResult],
                                 deck_evaluations: List[EvaluationResult]) -> DeckEvaluationResult:
        """Create final comprehensive summary"""
        
        summary_agent = self.create_summary_agent()
        
        # Prepare summary data
        summary_data = {
            "slide_evaluations": [eval.dict() for eval in slide_evaluations],
            "deck_evaluations": [eval.dict() for eval in deck_evaluations]
        }
        
        task = Task(
            description=dedent(f"""
                Create a comprehensive summary of the presentation evaluation.
                
                Evaluation data:
                {json.dumps(summary_data, indent=2)}
                
                Provide:
                1. Overall assessment score (1-5)
                2. Key strengths and weaknesses
                3. Priority areas for improvement
                4. Specific actionable recommendations
                5. Summary of findings by slide type
                
                Return the result in JSON format with overall_score and summary fields.
            """),
            agent=summary_agent,
            expected_output="JSON with overall_score and summary fields"
        )
        
        crew = Crew(
            agents=[summary_agent],
            tasks=[task],
            verbose=True
        )
        
        result = await crew.kickoff()
        
        # Parse summary result
        try:
            summary_result = self._extract_json_from_result(result, "summary")
            overall_score = summary_result.get("overall_score", 3.0) if summary_result else 3.0
            summary_text = summary_result.get("summary", "Evaluation summary not available") if summary_result else "Evaluation summary not available"
        except Exception as e:
            print(f"Error parsing summary result: {e}")
            overall_score = 3.0
            summary_text = "Error generating summary"
        
        return DeckEvaluationResult(
            deck_name="Presentation",
            slide_evaluations=slide_evaluations,
            deck_evaluations=deck_evaluations,
            overall_score=overall_score,
            summary=summary_text
        )

    def _extract_json_from_result(self, result: str, search_term: str) -> Optional[Dict]:
        """Extract JSON from crew result string"""
        try:
            # Simple JSON extraction - in practice you'd need more robust parsing
            if "{" in result and "}" in result:
                start = result.find("{")
                end = result.rfind("}") + 1
                json_str = result[start:end]
                return json.loads(json_str)
        except Exception as e:
            print(f"Error extracting JSON for {search_term}: {e}")
        return None

    def _extract_suggestions(self, result: Dict) -> List[str]:
        """Extract suggestions from evaluation result"""
        suggestions = []
        if "evaluation_results" in result:
            for eval_result in result["evaluation_results"]:
                if isinstance(eval_result, dict) and "evaluation_suggestion" in eval_result:
                    suggestions.append(eval_result["evaluation_suggestion"])
        return suggestions

    async def evaluate_presentation(self, 
                                  presentation_path: str,
                                  slide_criteria: List[CriterionInfo] = None,
                                  deck_criteria: List[CriterionInfo] = None) -> DeckEvaluationResult:
        """Main method to evaluate an entire presentation"""
        
        # Process presentation to get slide images
        png_dir, uploaded_files = self.file_manager.process_presentation(
            self.llm, presentation_path
        )
        
        # Get slide descriptions
        slide_descriptions = self.file_manager.get_slides_descriptions(presentation_path)
        
        # Evaluate each slide
        slide_evaluations = []
        for i, uploaded_file in enumerate(uploaded_files):
            slide_id = f"slide_{i+1}"
            slide_image_path = uploaded_file.get('image_file')
            
            if slide_image_path:
                slide_eval = await self.evaluate_slide(
                    slide_image_path, 
                    slide_id, 
                    slide_criteria
                )
                slide_evaluations.append(slide_eval)
        
        # Evaluate deck structure
        deck_evaluations = await self.evaluate_deck(
            presentation_path, 
            slide_descriptions, 
            deck_criteria
        )
        
        # Create final summary
        final_result = await self.create_final_summary(
            slide_evaluations, 
            deck_evaluations
        )
        
        return final_result