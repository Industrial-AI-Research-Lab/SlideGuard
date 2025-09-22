"""
Agents for slides evaluation and presentation analysis on multiple criteria
"""

import logging
import re
from typing import AsyncIterable, Callable, Dict, List, Any, Tuple, Type, TypeVar, cast, Optional

from jsonschema import ValidationError
from slideguard.crew.controlled_llm import ControlledLLM
from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.criteria.base import CriterionInfo
from slideguard.schemes import AbstractSlideDeck, Criteria, DeckDescription, SlideDeckDescriptions, SlideDeckImages, SlideDescription, SlideDescriptionWithType, SlideType, Criteria
from slideguard.schemes import DeckEvaluationResult
from slideguard.schemes import SlideEvaluationResult
from slideguard.schemes import FullEvaluation
from slideguard.schemes import FinalSummaryOutput, SummaryOutput
from slideguard.crew.summary_processor import SummaryProcessor
from slideguard.utils.base import timer
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager

from textwrap import dedent
from statistics import mean
from collections import Counter, defaultdict
from crewai import Agent, Task, Crew, CrewOutput, TaskOutput
from pydantic import BaseModel
import json
import asyncio
from langfuse import Langfuse


class FallbackResult(BaseModel):
    """Fallback result when evaluation fails."""
    error_message: str = "Evaluation failed - fallback result"
    score: float = 0.0
    comments: str = "This evaluation failed due to technical issues. Please try again."
    recommendations: str = "Consider re-running the evaluation with different settings."


class FallbackSlideType(SlideType):
    """Fallback SlideType when evaluation fails."""
    slide_type: list[str] = ["unknown"]


class FallbackSlideDescription(SlideDescription):
    """Fallback SlideDescription when evaluation fails."""
    title: str = "Evaluation Failed"
    description: str = "This slide evaluation failed due to technical issues. Please try again."
    summary: str = "Unable to analyze this slide due to evaluation errors."


logger = logging.getLogger(__name__)


T = TypeVar('T', bound=BaseModel)
U = TypeVar('U', bound=BaseModel)

# Optional import for search tools
try:
    from duckduckgo_search import DDGS
    DUCKDUCKGO_AVAILABLE = True
except ImportError:
    DUCKDUCKGO_AVAILABLE = False
    DDGS = None


class SlideGuardEvaluator:
    """Crew of agents for comprehensive slide deck evaluation"""
    
    def __init__(self,
                 file_manager: FileManager,
                 cache_manager: CacheManager,
                 llm: ControlledLLM,
                 max_retries: int = 3):
        self.file_manager = file_manager
        self.cache_manager = cache_manager
        self.llm = llm
        self.tools = self._setup_tools()
        self.max_retries = max_retries
        self.summary_processor = SummaryProcessor()

    async def evaluate_presentation(self,
                                    presentation_path: str,
                                    slide_criterias: List[Criteria] = None,
                                    deck_criterias: List[Criteria] = None,
                                    langfuse_client: Langfuse | None = None) -> FullEvaluation:
        
        with timer("evaluate_presentation"):
            try:
                if langfuse_client:
                    with langfuse_client.start_as_current_span(name="slideguard-crewai-trace") as span:
                        evaluation = await self._evaluate_presentation(
                            presentation_path=presentation_path,
                            slide_criterias=slide_criterias,
                            deck_criterias=deck_criterias
                        )

                        span.update_trace(
                            input=presentation_path,
                            output=evaluation.model_dump_json(),
                            tags=["slideguard", "crewai"],
                        )
                    
                    langfuse_client.flush()
                else:
                    evaluation = await self._evaluate_presentation(
                        presentation_path=presentation_path,
                        slide_criterias=slide_criterias,
                        deck_criterias=deck_criterias
                    )
                
                return evaluation
            except AttributeError as e:
                if "function_calling_llm" in str(e):
                    logger.error("LLM configuration error: function_calling_llm is None")
                    raise Exception("LLM configuration error. Please check your API settings and try again.")
                else:
                    raise e
            except Exception as e:
                logger.error(f"Evaluation failed: {e}")
                raise e

    def print_status(self):
        """Print current evaluator status"""
        print("SlideGuard Evaluator Status:")
        print(f"  LLM Available: {'✓ Yes' if self.llm else '✗ No'}")
        print(f"  Cache Directory: {self.cache_dir}")
        print(f"  File Cache Directory: {self.file_cache_dir}")

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
    
    def _make_pydantic_guardrail(self, class_model: Type[BaseModel]) -> Callable[[TaskOutput], Tuple[bool, Any]]:
        def func(result: TaskOutput) -> Tuple[bool, Any]:
            # If CrewAI already parsed it into Pydantic, accept it
            if result.pydantic:
                return True, result.pydantic
            # Fallback: try to coerce raw/JSON into the model yourself
            try:
                data = None
                
                if result.json_dict:
                    data = result.json_dict
                else:
                    raw_content = result.raw
                    if raw_content:
                        json_content = self._extract_md_json(raw_content)
                        data = json.loads(json_content)
                
                if data is None:
                    return False, "No valid data found in result"
                
                cleaned_data = self._clean_evaluation_data(data)
                obj = class_model.model_validate(cleaned_data)
                return True, obj
            except (ValidationError, json.JSONDecodeError) as e:
                return False, f"Invalid output: {e}"
            
        return func
    
    def _extract_md_json(self, text: str) -> str:
        """Extract JSON content from markdown code blocks"""
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return text.strip()
    
    def _clean_evaluation_data(self, data: Any) -> Any:
        """Clean evaluation data to handle potential quotation mark and encoding issues."""
        if isinstance(data, dict):
            return {k: self._clean_evaluation_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_evaluation_data(item) for item in data]
        elif isinstance(data, str):
            # Handle Unicode escape sequences and problematic characters
            try:
                # Handle Unicode escape sequences
                if '\\u' in data:
                    data = data.encode().decode('unicode_escape')
                
                # Remove null bytes and normalize line endings
                data = data.replace('\x00', '').replace('\r', '\n')
                
                # Handle potential quotation mark issues
                data = data.replace('"', '"').replace('"', '"')  # Smart quotes to regular quotes
                data = data.replace(''', "'").replace(''', "'")  # Smart apostrophes to regular apostrophes
                
                return data
            except Exception:
                return data
        else:
            return data
    
    def create_agent(self, criteria: CriterionInfo) -> Agent:
        agent = Agent(
            role='a helpful assistant and expert',
            goal='evaluate the criteria you are responsible for',
            backstory=criteria.agent_prompt,
            # use_system_prompt=True,
            # system_template=criteria.agent_prompt,
            # prompt_template=criteria.agent_prompt,
            tools=self.tools,
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

        return agent
    
    def create_crew(self, criteria: CriterionInfo) -> Crew:
        agent = self.create_agent(criteria)
        task = Task(
            name=criteria.criteria.value,
            description=criteria.task_prompt_template,
            agent=agent,
            # output_json=criteria.pydantic,
            output_pydantic=criteria.pydantic,
            guardrail=self._make_pydantic_guardrail(criteria.pydantic),
            max_retries=self.max_retries,
            expected_output="JSON in the described format."
        )
        
        # Verify LLM is properly configured before creating crew
        if not self.llm or not hasattr(self.llm, 'function_calling_llm') or self.llm.function_calling_llm is None:
            logger.error("LLM is not properly configured - function_calling_llm is None")
            raise ValueError("LLM configuration error: function_calling_llm is not properly set")
        
        return Crew(agents=[agent], tasks=[task], verbose=True, function_calling_llm=self.llm.function_calling_llm)

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
    
    def _get_slide_criterias_info(self, criterias: List[Criteria] | None) -> List[CriterionInfo]:
        if criterias is None:
            return list(SLIDE_CRITERIA_INFO.values())
        
        not_found_criterias = [criteria for criteria in criterias if criteria not in SLIDE_CRITERIA_INFO]
        if not_found_criterias:
            raise ValueError(f"Criteria {not_found_criterias} not found in SLIDE_CRITERIA_INFO")

        return [SLIDE_CRITERIA_INFO[criteria] for criteria in criterias]
    
    def _get_deck_criterias_info(self, criterias: List[Criteria] | None) -> List[CriterionInfo]:
        if criterias is None:
            return list(DECK_CRITERIA_INFO.values())
        
        not_found_criterias = [criteria for criteria in criterias if criteria not in DECK_CRITERIA_INFO]
        if not_found_criterias:
            raise ValueError(f"Criteria {not_found_criterias} not found in DECK_CRITERIA_INFO")

        return [DECK_CRITERIA_INFO[criteria] for criteria in criterias]
    
    
    @staticmethod
    async def _kickoff_for_each_async(crew: Crew, inputs: List[Dict]) -> AsyncIterable[Tuple[int, CrewOutput]]:
        # We add this function, because Crew.kickoff_for_each_async can not provide us with the results as soon as they are available.
        # This is a workaround to get the results as soon as they are available.
        # The implementation is based on the implementation of Crew.kickoff_for_each_async.
        crew_copies = [crew.copy() for _ in inputs]

        async def run_crew(crew, input_data, index):
            result = await crew.kickoff_async(inputs=input_data)
            return index, result

        tasks = [
            asyncio.create_task(run_crew(crew_copies[i], inputs[i], i))
            for i in range(len(inputs))
        ]

        # Process results as they complete, maintaining original order
        for coro in asyncio.as_completed(tasks):
            index, result = await coro
            yield index, result
    
    async def _run_crew(self, 
                        criteria_info: CriterionInfo, 
                        slides: AbstractSlideDeck[T]) -> List[BaseModel]:
        crew = self.create_crew(criteria_info)

        async def compute(inputs: List[Tuple[int, T]]) -> AsyncIterable[Tuple[int, BaseModel]]:
            ins = [in_.model_dump() for _, in_ in inputs]
            try:
                async for i, result in self._kickoff_for_each_async(crew, ins):
                    idx, _ = inputs[i]
                    if result.pydantic is None:
                        # Handle case where pydantic parsing failed
                        logger.warning(f"Pydantic parsing failed for slide {idx}, criteria {criteria_info.criteria.value}")
                        # Create a default/fallback result
                        fallback_result = self._create_fallback_result(criteria_info.pydantic)
                        yield idx, fallback_result
                    else:
                        yield idx, result.pydantic
            except AttributeError as e:
                if "function_calling_llm" in str(e):
                    logger.error(f"LLM configuration error for criteria {criteria_info.criteria.value}: {e}")
                    # Return fallback results for all inputs due to LLM config issue
                    for idx, _ in inputs:
                        fallback_result = self._create_fallback_result(criteria_info.pydantic)
                        yield idx, fallback_result
                else:
                    logger.error(f"Attribute error in crew execution for criteria {criteria_info.criteria.value}: {e}")
                    # Return fallback results for all inputs
                    for idx, _ in inputs:
                        fallback_result = self._create_fallback_result(criteria_info.pydantic)
                        yield idx, fallback_result
            except Exception as e:
                logger.error(f"Error in crew execution for criteria {criteria_info.criteria.value}: {e}")
                # Return fallback results for all inputs
                for idx, _ in inputs:
                    fallback_result = self._create_fallback_result(criteria_info.pydantic)
                    yield idx, fallback_result

        try:
            entities = await self.cache_manager.compute_with_cache(
                deck_name=slides.slide_deck_path,
                criteria_id=criteria_info.criteria.value,
                inputs=slides.slides,
                func=compute
            )
            
            # Ensure we have valid results for all slides
            if not entities or len(entities) != len(slides.slides):
                logger.warning(f"Cache returned incomplete results for {criteria_info.criteria.value}, creating fallbacks")
                entities = [self._create_fallback_result(criteria_info.pydantic) for _ in slides.slides]
            
            return entities
        except Exception as e:
            logger.error(f"Error in cache computation for {criteria_info.criteria.value}: {e}")
            # Return fallback results for all slides
            return [self._create_fallback_result(criteria_info.pydantic) for _ in slides.slides]
    
    def _create_fallback_result(self, pydantic_class: Type[BaseModel]) -> BaseModel:
        """Create a fallback result when parsing fails."""
        try:
            # Try to create a minimal valid instance
            if hasattr(pydantic_class, 'model_validate'):
                # For newer Pydantic versions
                return pydantic_class.model_validate({})
            else:
                # For older Pydantic versions
                return pydantic_class()
        except Exception:
            # Return appropriate fallback based on the expected type
            if pydantic_class.__name__ == 'SlideType':
                return FallbackSlideType()
            elif pydantic_class.__name__ == 'SlideDescription':
                return FallbackSlideDescription()
            else:
                return FallbackResult()

    async def _evaluate_slides(
        self,
        slides: SlideDeckImages,
        criterias: List[Criteria] | None = None
    ) -> List[SlideEvaluationResult]:
        """Evaluate a batch of slides using CrewAI's kickoff_for_each_async.

        Args:
            slides: List of inputs with keys 'slide_id' and 'slide_image_path'.
            slide_criteria: Criteria to apply (defaults to all slide criteria sorted by priority).
            concurrency_limit: Max number of slides to evaluate concurrently (chunked batching).

        Returns:
            List of SlideEvaluationResult matching the input order.
        """

        infos = self._get_slide_criterias_info(criterias)

        running_crews = [self._run_crew(info, slides) for info in infos]
        results = await asyncio.gather(*running_crews)

        crit2result = {info.criteria: result for info, result in zip(infos, results)}

        # what if some computations failed
        slide_evaluation_results = []
        for i, slide in enumerate(slides.slides):
            try:
                # Safely get slide_type and slide_description with null checks
                slide_type = None
                slide_description = None
                
                if Criteria.slide_type in criterias and Criteria.slide_type in crit2result:
                    slide_type_result = crit2result[Criteria.slide_type]
                    if slide_type_result and i < len(slide_type_result) and slide_type_result[i] is not None:
                        slide_type = cast(SlideType, slide_type_result[i])
                    else:
                        # Use fallback if slide_type evaluation failed
                        slide_type = FallbackSlideType()
                
                if Criteria.slide_description in criterias and Criteria.slide_description in crit2result:
                    slide_desc_result = crit2result[Criteria.slide_description]
                    if slide_desc_result and i < len(slide_desc_result) and slide_desc_result[i] is not None:
                        slide_description = cast(SlideDescription, slide_desc_result[i])
                    else:
                        # Use fallback if slide_description evaluation failed
                        slide_description = FallbackSlideDescription()
                
                # Safely build evaluations dictionary
                evaluations = {}
                for info in infos:
                    if not info.criteria.is_service_criteria() and info.criteria in crit2result:
                        result_list = crit2result[info.criteria]
                        if result_list and i < len(result_list) and result_list[i] is not None:
                            evaluations[info.criteria] = result_list[i]
                
                slide_evaluation_results.append(
                    SlideEvaluationResult(
                        slide_deck_path=slides.slide_deck_path,
                        slide_id=slide.slide_id,
                        slide_type=slide_type,
                        slide_description=slide_description,
                        evaluations=evaluations
                    )
                )
            except Exception as e:
                logger.error(f"Error creating slide evaluation result for slide {i}: {e}")
                # Create a fallback slide evaluation result with proper fallback objects
                slide_evaluation_results.append(
                    SlideEvaluationResult(
                        slide_deck_path=slides.slide_deck_path,
                        slide_id=slide.slide_id,
                        slide_type=FallbackSlideType(),
                        slide_description=FallbackSlideDescription(),
                        evaluations={}
                    )
                )

        return slide_evaluation_results

    async def _evaluate_deck(self,
                            slide_descriptions: SlideDeckDescriptions,
                            deck_criterias: List[Criteria] | None = None) -> DeckEvaluationResult:
        """Evaluate the entire deck structure"""
        
        infos = self._get_deck_criterias_info(deck_criterias)

        running_crews = [self._run_crew(info, slide_descriptions) for info in infos]
        results = cast(List[List[BaseModel]], await asyncio.gather(*running_crews))
        
        # Safely build evaluations dictionary with null checks
        evaluations = {}
        for info, result in zip(infos, results):
            if result and len(result) == 1 and result[0] is not None:
                evaluations[info.criteria] = result[0]
            else:
                logger.warning(f"Deck evaluation failed for criteria {info.criteria.value}, using fallback")
                evaluations[info.criteria] = FallbackResult()

        return DeckEvaluationResult(evaluations=evaluations)

    async def _create_final_summary(self, 
                                 slide_evaluations: List[SlideEvaluationResult],
                                 deck_evaluations: Optional[DeckEvaluationResult]) -> FinalSummaryOutput:
        """Create final comprehensive summary"""
        
        summary_agent = self.create_summary_agent()
        summary_payload = self.summary_processor.get_summary_payload(slide_evaluations, deck_evaluations)
        summary_data = summary_payload.model_dump()
        
        summary_task = Task(
            description=dedent(f"""
                Create a comprehensive long-form summary of the presentation evaluation.
                
                Evaluation data:
                {json.dumps(summary_data, indent=2)}
                
                Use the context to formulate the long-form summary.
                Provide:
                - Short overview of the evaluation
                - Main strengths
                - Main problems
                - Prioritized next steps with slide pointers
                
                Return the result strictly as JSON with field: summary.
            """),
            agent=summary_agent,
            expected_output="JSON in the described format.",
            output_pydantic=SummaryOutput,
            guardrail=self._make_pydantic_guardrail(SummaryOutput),
            max_retries=self.max_retries
        )
        
        tldr_task = Task(
            description=dedent(f"""
                Based on the previously generated long-form summary in context, write an actionable TL;DR of 2-4 sentences focusing on key issues and next actions.
                Return the result strictly as JSON with fields: summary, tldr.
                The summary field must contain the exact long-form summary you received in context.
            """),
            agent=summary_agent,
            expected_output="JSON with fields: summary, tldr",
            output_pydantic=FinalSummaryOutput,
            guardrail=self._make_pydantic_guardrail(FinalSummaryOutput),
            max_retries=self.max_retries,
            context=[summary_task]
        )

        crew = Crew(
            agents=[summary_agent],
            tasks=[summary_task, tldr_task],
            verbose=True,
            function_calling_llm=self.llm.function_calling_llm
        )
        final_result = await crew.kickoff_async()
        return final_result.pydantic

    
    
    async def _evaluate_presentation(self,
                                     presentation_path: str,
                                     slide_criterias: List[Criteria] = None,
                                     deck_criterias: List[Criteria] = None) -> FullEvaluation:
        """Main method to evaluate an entire presentation"""

        if deck_criterias:
            slide_criterias = list(set({Criteria.slide_type, Criteria.slide_description, *slide_criterias}))
        
        # Process presentation to get slide images
        slides = self.file_manager.process_presentation(presentation_path)

        slide_evaluations = await self._evaluate_slides(
            slides=slides,
            criterias=slide_criterias
        )

        if deck_criterias:
            slide_descriptions = []
            for slide in slide_evaluations:
                try:
                    if slide.slide_description is not None and slide.slide_type is not None:
                        slide_descriptions.append(
                            SlideDescriptionWithType(
                                **slide.slide_description.model_dump(), 
                                slide_type=slide.slide_type.slide_type
                            )
                        )
                    else:
                        logger.warning(f"Skipping slide {slide.slide_id} due to missing slide_description or slide_type")
                except Exception as e:
                    logger.error(f"Error processing slide {slide.slide_id}: {e}")
                    continue

            if slide_descriptions:
                slide_deck_descriptions = SlideDeckDescriptions(
                    slide_deck_path=presentation_path,
                    slides=[DeckDescription.from_slide_descriptions(slide_descriptions)]
                )

                # Evaluate deck structure
                deck_evaluations = await self._evaluate_deck(
                    slide_deck_descriptions, 
                    deck_criterias
                )
            else:
                logger.warning("No valid slide descriptions available for deck evaluation")
                deck_evaluations = None
        else:
            deck_evaluations = None
        
        # tldr summary
        final_summary = await self._create_final_summary(
            slide_evaluations, 
            deck_evaluations
        )
        
        return FullEvaluation(
            slide_deck_path=presentation_path,
            slide_evaluations=slide_evaluations,
            deck_evaluations=deck_evaluations,
            overall_score=self.summary_processor.calculate_overall_score(slide_evaluations, deck_evaluations),
            summary=final_summary.summary,
            tldr=final_summary.tldr
        )