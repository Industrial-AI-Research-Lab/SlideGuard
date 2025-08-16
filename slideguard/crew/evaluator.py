"""
Agents for slides evaluation and presentation analysis on multiple criteria
"""

from typing import AsyncIterable, Callable, List, Any, Tuple, Type, TypeVar, cast

from jsonschema import ValidationError
from slideguard.crew.controlled_llm import create_llm_from_env
from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.criteria.base import CriterionInfo
from slideguard.criteria.deck_storytelling import DECK_STORYTELLING
from slideguard.criteria.deck_structure_analysis import DECK_STRUCTURE_ANALYSIS
from slideguard.criteria.slide_helper_description import SLIDE_HELPER_DESCRIPTION
from slideguard.criteria.slide_helper_type import SLIDE_HELPER_TYPE
from slideguard.criteria.slide_visual_arrangement import SLIDE_VISUAL_ARRANGEMENT
from slideguard.schemes import AbstractSlideDeck, Criteria, DeckDescription, SlideDeckDescriptions, SlideDeckImages, SlideDescription, SlideDescriptionWithType, SlideType
from slideguard.schemes import EvaluationResult
from slideguard.schemes import SlideEvaluationResult
from slideguard.schemes import DeckEvaluationResult
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager
from slideguard.config import config

from textwrap import dedent
from crewai import LLM, Agent, Task, Crew, TaskOutput
from pydantic import BaseModel
import json
import asyncio
from langfuse import Langfuse


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
                 file_manager: FileManager | None = None,
                 cache_manager: CacheManager | None = None,
                 llm: LLM | None = None,
                 max_retries: int = 3):
        self.file_manager = file_manager or FileManager()
        self.cache_manager = cache_manager or CacheManager()
        self.llm = llm or create_llm_from_env()
        self.tools = self._setup_tools()
        self.max_retries = max_retries

    async def evaluate_presentation(self,
                                    presentation_path: str,
                                    slide_criterias: List[Criteria] = None,
                                    deck_criterias: List[Criteria] = None,
                                    langfuse_client: Langfuse | None = None) -> DeckEvaluationResult:
        
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

    def print_status(self):
        """Print current evaluator status"""
        print("SlideGuard Evaluator Status:")
        print(f"  LLM Available: {'✓ Yes' if self.llm else '✗ No'}")
        print(f"  Cache Directory: {self.cache_dir}")
        print(f"  File Cache Directory: {self.file_cache_dir}")
        
        if self.llm is None:
            config.print_config_status()

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
                data = result.json_dict or json.loads(result.raw)
                obj = class_model.model_validate(data)
                return True, obj
            except (ValidationError, json.JSONDecodeError) as e:
                return False, f"Invalid output: {e}"
            
        return func
    
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
            description=criteria.task_prompt,
            agent=agent,
            output_pydantic=criteria.pydantic,
            guardrail=self._make_pydantic_guardrail(criteria.pydantic),
            max_retries=self.max_retries,
            expected_output="JSON in the described format."
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

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
    
    async def _run_crew(self, 
                        criteria_info: CriterionInfo, 
                        slides: AbstractSlideDeck[T]) -> List[BaseModel]:
        crew = self.create_crew(criteria_info)

        async def compute(inputs: List[Tuple[int, T]]) -> AsyncIterable[Tuple[int, BaseModel]]:
            ins = [in_.model_dump() for _, in_ in inputs]
            results = await crew.kickoff_for_each_async(ins)
            for (i, _), result in zip(inputs, results):
                yield (i, result.pydantic)

        entities = await self.cache_manager.compute_with_cache(
            deck_name=slides.slide_deck_path,
            criteria_id=criteria_info.criteria.value,
            inputs=slides.slides,
            func=compute
        )
        
        return entities

    async def _evaluate_slides(
        self,
        slides: SlideDeckImages,
        criterias: List[Criteria] | None = None,
        langfuse_client: Langfuse | None = None,
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
        slide_evaluation_results = [
            SlideEvaluationResult(
                slide_deck_path=slides.slide_deck_path,
                slide_id=slide.slide_id,
                slide_type=cast(SlideType, crit2result[Criteria.slide_type][i]),
                slide_description=cast(SlideDescription, crit2result[Criteria.slide_description][i]),
                evaluations=[
                    cast(EvaluationResult, crit2result[info.criteria][i]) 
                    for info in infos
                    if not info.criteria.is_service_criteria()
                ]
            )
            for i, slide in enumerate(slides.slides)
        ]

        return slide_evaluation_results

    async def _evaluate_slide(
        self,
        slide_image_path: str,
        slide_id: str,
        slide_criteria: List[CriterionInfo] | None = None,
        slide_types: List[str] | None = None,
    ) -> SlideEvaluationResult:
        """Backward-compatible wrapper to evaluate a single slide using the batch engine."""
        results = await self._evaluate_slides(
            slides=[{"slide_id": slide_id, "slide_image_path": slide_image_path}],
            criterias=slide_criteria,
            concurrency_limit=1,
        )

    async def _evaluate_deck(self,
                            slide_descriptions: SlideDeckDescriptions,
                            deck_criterias: List[Criteria] | None = None) -> List[EvaluationResult]:
        """Evaluate the entire deck structure"""
        
        infos = self._get_deck_criterias_info(deck_criterias)

        running_crews = [self._run_crew(info, slide_descriptions) for info in infos]
        results = cast(List[List[EvaluationResult]], await asyncio.gather(*running_crews))
        
        for result in results:
            assert len(result) == 1

        results = [result[0] for result in results]

        return results

    async def _create_final_summary(self, 
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
        
        result = await crew.kickoff_async()

        return result.pydantic
    
    
    async def _evaluate_presentation(self,
                                     presentation_path: str,
                                     slide_criterias: List[Criteria] = None,
                                     deck_criterias: List[Criteria] = None) -> DeckEvaluationResult:
        """Main method to evaluate an entire presentation"""
        
        # Process presentation to get slide images
        slides = self.file_manager.process_presentation(presentation_path)

        slide_evaluations = await self._evaluate_slides(
            slides=slides,
            criterias=slide_criterias
        )
        

        slide_descriptions = [
            SlideDescriptionWithType(
                **slide.slide_description.model_dump(), 
                slide_type=slide.slide_type.slide_type
            ) 
            for slide in slide_evaluations
        ]

        slide_deck_descriptions = SlideDeckDescriptions(
            slide_deck_path=presentation_path,
            slides=[DeckDescription.from_slide_descriptions(slide_descriptions)]
        )

        # Evaluate deck structure
        deck_evaluations = await self._evaluate_deck(
            slide_deck_descriptions, 
            deck_criterias
        )
        
        # # Create final summary
        # final_result = await self.create_final_summary(
        #     slide_evaluations, 
        #     deck_evaluations
        # )
        
        return DeckEvaluationResult(
            deck_name=presentation_path,
            slide_evaluations=slide_evaluations,
            deck_evaluations=deck_evaluations,
            overall_score=-1.0,
            summary="Evaluation summary not available"
        )
