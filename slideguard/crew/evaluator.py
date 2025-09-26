"""
Agents for slides evaluation and presentation analysis on multiple criteria
"""

import logging
import re
from typing import AsyncIterable, Callable, Dict, List, Any, Tuple, Type, TypeVar, cast, Optional, Protocol, runtime_checkable

from jsonschema import ValidationError
from slideguard.crew.controlled_llm import ControlledLLM
from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.criteria.slide_abbreviations import SlideAbbreviations, SlideAbbreviationsResult, ABBREVIATIONS_WHITELIST
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
from crewai import Agent, Task, Crew, CrewOutput, TaskOutput
from pydantic import BaseModel
import json
import asyncio
from langfuse import Langfuse


@runtime_checkable
class HasEvaluationResults(Protocol):
    evaluation_results: List[Any]


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
                coerced = self._coerce_task_output(result, class_model)
                if coerced is not None:
                    return True, coerced
                return False, "No valid data found in result"
            except Exception as e:
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
                # normalize quotes
                data = data.replace('\u201c', '"').replace('\u201d', '"')
                data = data.replace('\u2018', "'").replace('\u2019', "'")
                # normalize backslashes
                data = re.sub(r"\\+\(", "(", data)
                data = re.sub(r"\\+\)", ")", data)
                data = re.sub(r"\\+\[", "[", data)
                data = re.sub(r"\\+\]", "]", data)
                # remove stray backslashes not forming valid JSON escapes
                data = re.sub(r"\\(?![\"\\/bfnrtu])", "", data)
                return data
            except Exception:
                return data
        else:
            return data

    def _coerce_task_output(self, result: TaskOutput, class_model: Type[BaseModel]) -> Optional[BaseModel]:
        try:
            if result.json_dict:
                obj = class_model.model_validate(self._clean_evaluation_data(result.json_dict))
                return obj

            raw = (result.raw or "").strip()
            if not raw:
                return None

            text = self._extract_md_json(raw)
            candidates: List[str] = [text]
            first, last = text.find('{'), text.rfind('}')
            if 0 <= first < last:
                candidates.append(text[first:last + 1])

            for cand in candidates:
                cleaned_str = cast(str, self._clean_evaluation_data(cand))
                for attempt in (cleaned_str, cleaned_str.replace('\n', ' ')):
                    try:
                        data_obj = json.loads(attempt)
                        obj = class_model.model_validate(self._clean_evaluation_data(data_obj))
                        return obj
                    except Exception:
                        pass
        except Exception:
            return None
        return None
    
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
            llm=self.llm,
            max_retry_limit=1
        )

        return agent
    
    def _criterion_applies(self, info: CriterionInfo, slide_types: List[str] | None) -> bool:
        targets = getattr(info, 'applicable_slide_types', None)
        if not targets:
            return True
        target_values = set(targets)
        for st in (slide_types or []):
            if st in target_values:
                return True
        return False

    def _sort_by_severity(self, obj: HasEvaluationResults) -> HasEvaluationResults:
        def _severity_value(v: Any) -> int:
            return int(getattr(v, 'severity', 1))
        try:
            items = sorted(getattr(obj, 'evaluation_results', []), key=_severity_value, reverse=True)
            setattr(obj, 'evaluation_results', items)
        except Exception:
            pass
        return obj

    def _postprocess_result(self, criteria: Criteria, obj: BaseModel) -> BaseModel:
        try:
            if criteria == Criteria.slide_abbreviations and isinstance(obj, SlideAbbreviations):
                filtered: List[SlideAbbreviationsResult] = []
                wl = ABBREVIATIONS_WHITELIST
                for item in obj.evaluation_results:
                    try:
                        token = str(getattr(item, 'evaluation_element', '')).strip().lower().replace('.', '')
                        if token and token not in wl:
                            filtered.append(item)
                    except Exception:
                        filtered.append(item)
                obj.evaluation_results = filtered
            if isinstance(obj, HasEvaluationResults):
                obj = cast(HasEvaluationResults, obj)
                obj = self._sort_by_severity(obj)
        except Exception:
            pass
        return obj

    def create_crew(self, criteria: CriterionInfo) -> Crew:
        agent = self.create_agent(criteria)
        task = Task(
            name=criteria.criteria.value,
            description=criteria.task_prompt_template,
            agent=agent,
            # output_json=criteria.pydantic,
            output_pydantic=criteria.pydantic,
            guardrail=self._make_pydantic_guardrail(criteria.pydantic),
            max_retries=1,
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
            try:
                result = await crew.kickoff_async(inputs=input_data)
                return index, result
            except Exception as e:
                return index, e

        tasks = [
            asyncio.create_task(run_crew(crew_copies[i], inputs[i], i))
            for i in range(len(inputs))
        ]

        # Process results as they complete, maintaining original order
        for coro in asyncio.as_completed(tasks):
            try:
                index, result = await coro
            except Exception as e:
                # Should not happen due to try in run_crew, but guard anyway
                index = 0
                result = e
            yield index, result
    
    async def _run_crew(self, 
                        criteria_info: CriterionInfo, 
                        slides: AbstractSlideDeck[T]) -> List[BaseModel]:
        crew = self.create_crew(criteria_info)

        async def compute(inputs: List[Tuple[int, T]]) -> AsyncIterable[Tuple[int, BaseModel]]:
            ins = [in_.model_dump() for _, in_ in inputs]
            async for i, result in self._kickoff_for_each_async(crew, ins):
                idx, _ = inputs[i]
                try:
                    if isinstance(result, Exception) or result is None:
                        yield idx, self._create_fallback_result(criteria_info.pydantic)
                        continue
                    if result.pydantic is not None:
                        yield idx, result.pydantic
                        continue
                    coerced = self._coerce_task_output(result, criteria_info.pydantic)
                    if coerced is not None:
                        yield idx, coerced
                    else:
                        yield idx, self._create_fallback_result(criteria_info.pydantic)
                except Exception:
                    yield idx, self._create_fallback_result(criteria_info.pydantic)

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
        service_infos = [i for i in infos if i.criteria.is_service_criteria()]
        other_infos = sorted((i for i in infos if not i.criteria.is_service_criteria()), key=lambda x: getattr(x, 'priority', 100))

        crit2result: Dict[Criteria, List[BaseModel]] = {}

        if service_infos:
            service_runs = [self._run_crew(i, slides) for i in service_infos]
            service_res = await asyncio.gather(*service_runs)
            for info, res in zip(service_infos, service_res):
                crit2result[info.criteria] = res

        slide_types_per_idx: List[List[str]] = []
        for i in range(len(slides.slides)):
            if Criteria.slide_type in crit2result and i < len(crit2result[Criteria.slide_type]):
                st_obj = cast(SlideType, crit2result[Criteria.slide_type][i])
                slide_types_per_idx.append(list(getattr(st_obj, 'slide_type', []) or []))
            else:
                slide_types_per_idx.append([])

        subsets: List[Tuple[CriterionInfo, List[int], SlideDeckImages]] = []
        for info in other_infos:
            if getattr(info, 'applicable_slide_types', None) or getattr(info, 'requires_slide_type', False):
                eligible = [idx for idx, types in enumerate(slide_types_per_idx) if self._criterion_applies(info, types)]
                if not eligible:
                    continue
                subset = SlideDeckImages(
                    slide_deck_path=slides.slide_deck_path,
                    png_dir=slides.png_dir,
                    slides=[slides.slides[i] for i in eligible]
                )
                subsets.append((info, eligible, subset))
            else:
                eligible = list(range(len(slides.slides)))
                subsets.append((info, eligible, slides))

        if subsets:
            runs = [self._run_crew(info, subset) for info, _, subset in subsets]
            results = await asyncio.gather(*runs)
            for (info, eligible, _), subset_results in zip(subsets, results):
                if len(eligible) == len(slides.slides):
                    crit2result[info.criteria] = [self._postprocess_result(info.criteria, r) for r in subset_results]
                else:
                    merged: List[BaseModel] = [None] * len(slides.slides)
                    for j, idx in enumerate(eligible):
                        merged[idx] = self._postprocess_result(info.criteria, subset_results[j])
                    crit2result[info.criteria] = merged

        # what if some computations failed
        slide_evaluation_results = []
        all_infos = service_infos + other_infos

        def get_result(crit: Criteria, idx: int) -> Optional[BaseModel]:
            lst = crit2result.get(crit)
            if not lst or idx >= len(lst):
                return None
            return lst[idx]

        for i, slide in enumerate(slides.slides):
            try:
                # Safely get slide_type and slide_description with null checks
                slide_type = None
                slide_description = None
                
                if Criteria.slide_type in criterias:
                    st = get_result(Criteria.slide_type, i)
                    slide_type = cast(SlideType, st) if st else FallbackSlideType()
                
                if Criteria.slide_description in criterias:
                    sd = get_result(Criteria.slide_description, i)
                    slide_description = cast(SlideDescription, sd) if sd else FallbackSlideDescription()
                
                # Safely build evaluations dictionary
                evaluations = {}
                for info in all_infos:
                    if info.criteria.is_service_criteria():
                        continue
                    val = get_result(info.criteria, i)
                    if val is not None:
                        evaluations[info.criteria] = val
                
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
                evaluations[info.criteria] = self._postprocess_result(info.criteria, result[0])
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