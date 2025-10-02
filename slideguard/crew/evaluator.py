"""
Class for slides evaluation and presentation analysis on multiple criteria.
Based on LangGraph + LangChain.
"""

import asyncio
import logging
from textwrap import dedent
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple, Type, cast, Protocol, runtime_checkable

from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langfuse import Langfuse
from slideguard.crew.callbacks import langfuse_callback_cm

from slideguard.crew.controlled_llm import ControlledLLM
from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.criteria.base import CriterionInfo
from slideguard.criteria.slide_abbreviations import (
    SlideAbbreviations,
    SlideAbbreviationsResult,
    ABBREVIATIONS_WHITELIST,
)
from slideguard.schemes import (
    Criteria,
    DeckDescription,
    DeckEvaluationResult,
    FullEvaluation,
    SlideDeckDescriptions,
    SlideDeckImages,
    SlideDescription,
    SlideDescriptionWithType,
    SlideEvaluationResult,
    SlideType,
    SummaryOutput,
    TLDROutput
)
from slideguard.crew.summary_processor import SummaryProcessor, SUMMARY_AGENT_BACKSTORY
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager


logger = logging.getLogger(__name__)

@runtime_checkable
class CriterionResult(Protocol):
    evaluation_results: List[Any]
    score: int

class FallbackMarker:
    __slideguard_fallback__ = True

class FallbackResult(BaseModel, FallbackMarker):
    error_message: str = "Evaluation failed - fallback result"
    score: float = 0.0
    comments: str = "This evaluation failed due to technical issues. Please try again."
    recommendations: str = "Consider re-running the evaluation with different settings."


class FallbackSlideType(SlideType, FallbackMarker):
    slide_type: list[str] = ["unknown"]


class FallbackSlideDescription(SlideDescription, FallbackMarker):
    title: str = "Evaluation Failed"
    description: str = "This slide evaluation failed due to technical issues. Please try again."
    summary: str = "Unable to analyze this slide due to evaluation errors."


class EvaluationState(BaseModel):
    presentation_path: str
    slide_criterias: List[Criteria]
    deck_criterias: Optional[List[Criteria]] = None

    slides: Optional[SlideDeckImages] = None
    slide_service: Optional[Dict[Criteria, List[BaseModel]]] = None
    slide_subsets: Optional[List[Tuple[Criteria, List[int], SlideDeckImages]]] = None
    slide_evaluations: Optional[List[SlideEvaluationResult]] = None

    deck_descriptions: Optional[SlideDeckDescriptions] = None
    deck_evaluations: Optional[DeckEvaluationResult] = None

    summary: Optional[str] = None
    tldr: Optional[str] = None
    overall_score: Optional[int] = None
    errors: List[str] = []


class SlideGuardEvaluator:
    def __init__(
        self,
        file_manager: FileManager,
        cache_manager: CacheManager,
        llm: ControlledLLM,
        max_retries: int = 3,
    ) -> None:
        self.file_manager = file_manager
        self.cache_manager = cache_manager
        self.llm = llm
        self.tools = self._setup_tools()
        self.max_retries = max_retries
        self.summary_processor = SummaryProcessor()

        self.slide_infos: Dict[Criteria, CriterionInfo] = dict(SLIDE_CRITERIA_INFO)
        self.deck_infos: Dict[Criteria, CriterionInfo] = dict(DECK_CRITERIA_INFO)
        self.app = self._setup_app()
        # Bind tools to the LLM if they are set
        if self.tools:
            self.llm = self.llm.with_tools(self.tools)

        self._callbacks: List[Any] = []

    async def evaluate_presentation(
        self,
        presentation_path: str,
        slide_criterias: List[Criteria] | None = None,
        deck_criterias: List[Criteria] | None = None,
        langfuse_client: Langfuse | None = None,
    ) -> FullEvaluation:
        with langfuse_callback_cm(langfuse_client) as cbs:
            self._callbacks = cbs
        if deck_criterias:
            if slide_criterias is None:
                slide_criterias = [Criteria.slide_type, Criteria.slide_description] # add service criteria
            else:
                sc = {*slide_criterias, Criteria.slide_type, Criteria.slide_description}
                slide_criterias = list(sc)

        initial = EvaluationState(
            presentation_path=presentation_path,
            slide_criterias=slide_criterias or list(self.slide_infos.keys()),
            deck_criterias=deck_criterias,
        )

        # Run graph; attach callbacks to capture LangGraph + LCEL traces
        if self._callbacks:
            result = await self.app.ainvoke(initial, config={"callbacks": self._callbacks, "configurable": {"thread_id": "1"}})
        else:
            result = await self.app.ainvoke(initial, config={"configurable": {"thread_id": "1"}})
        final_state: EvaluationState = EvaluationState.model_validate(result) if isinstance(result, dict) else cast(EvaluationState, result)
            
        full_evaluation = FullEvaluation(
            slide_deck_path=presentation_path,
            slide_evaluations=final_state.slide_evaluations or [],
            deck_evaluations=final_state.deck_evaluations,
            overall_score=final_state.overall_score,
            summary=final_state.summary,
            tldr=final_state.tldr,
        )

        return full_evaluation

    def _setup_app(self) -> StateGraph:
        graph = StateGraph(EvaluationState)
        graph.add_node("process_presentation", self._node_process_presentation)
        graph.add_node("evaluate_service", self._node_evaluate_service)
        graph.add_node("plan_subsets", self._node_plan_subsets)
        graph.add_node("evaluate_slide_criteria", self._node_evaluate_slide_criteria)
        graph.add_node("build_deck_descriptions", self._node_build_deck_descriptions)
        graph.add_node("evaluate_deck_criteria", self._node_evaluate_deck_criteria)
        graph.add_node("build_summary", self._node_build_summary)
        graph.add_node("build_tldr", self._node_build_tldr)
        graph.add_node("compute_overall", self._node_compute_overall)

        graph.set_entry_point("process_presentation")
        graph.add_edge("process_presentation", "evaluate_service")
        graph.add_edge("evaluate_service", "plan_subsets")
        graph.add_edge("plan_subsets", "evaluate_slide_criteria")

        def _branch_after_slides(state: EvaluationState) -> str:
            return "build_deck_descriptions" if state.deck_criterias else "build_summary"

        graph.add_conditional_edges(
            "evaluate_slide_criteria",
            _branch_after_slides,
            {
                "build_deck_descriptions": "build_deck_descriptions",
                "build_summary": "build_summary",
            },
        )
        graph.add_edge("build_deck_descriptions", "evaluate_deck_criteria")
        graph.add_edge("evaluate_deck_criteria", "build_summary")
        graph.add_edge("build_summary", "build_tldr")
        graph.add_edge("build_tldr", "compute_overall")

        return graph.compile(checkpointer=MemorySaver()) # checkpointer could be used in the future to resume a partially completed evaluation (retry)

    async def _node_process_presentation(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        slides = self.file_manager.process_presentation(state.presentation_path)
        if not slides:
            raise ValueError(f"Failed to process presentation: {state.presentation_path}")
        return {"slides": slides}

    async def _node_evaluate_service(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        requested = [c for c in state.slide_criterias if c.is_service_criteria()]
        results: Dict[Criteria, List[BaseModel]] = {}
        for c in requested: # can be batched instead?
            info = self.slide_infos[c]
            chain = info.to_runnable(self.llm)
            entities = await self._eval_criterion_with_cache(
                info=info,
                deck=state.slides,
                chain=chain,
                config=config,
            )
            results[c] = entities

        return {"slide_service": results}

    async def _node_plan_subsets(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slides:
            return {}

        infos: List[CriterionInfo] = [SLIDE_CRITERIA_INFO[c] for c in state.slide_criterias]
        other_infos = sorted(
            [i for i in infos if not i.criteria.is_service_criteria()],
            key=lambda x: getattr(x, "priority", 100),
        )

        slide_types_per_idx: List[List[str]] = []
        for i in range(len(state.slides.slides)):
            if state.slide_service and Criteria.slide_type in state.slide_service and i < len(state.slide_service[Criteria.slide_type]):
                st_obj = cast(SlideType, state.slide_service[Criteria.slide_type][i])
                slide_types_per_idx.append(list(getattr(st_obj, "slide_type", []) or []))
            else:
                slide_types_per_idx.append([])

        subsets: List[Tuple[Criteria, List[int], SlideDeckImages]] = []
        for info in other_infos:
            if getattr(info, "applicable_slide_types", None) or getattr(info, "requires_slide_type", False):
                eligible = [idx for idx, types in enumerate(slide_types_per_idx) if self._criterion_applies(info, types)]
                if not eligible:
                    continue
                subset = SlideDeckImages(
                    slide_deck_path=state.slides.slide_deck_path,
                    png_dir=state.slides.png_dir,
                    slides=[state.slides.slides[i] for i in eligible],
                )
                subsets.append((info.criteria, eligible, subset))
            else:
                eligible = list(range(len(state.slides.slides)))
                subsets.append((info.criteria, eligible, state.slides))

        return {"slide_subsets": subsets}

    async def _node_evaluate_slide_criteria(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slides:
            return {}

        crit2result: Dict[Criteria, List[BaseModel]] = {}
        subsets = state.slide_subsets or []

        if subsets:
            tasks: List[Tuple[Criteria, List[int], List[BaseModel]]] = []
            for crit, eligible, subset in subsets:
                info = SLIDE_CRITERIA_INFO[crit]
                chain = info.to_runnable(self.llm)
                entities = await self._eval_criterion_with_cache(
                    info=info,
                    deck=subset,
                    chain=chain,
                    config=config,
                )
                tasks.append((crit, eligible, entities))

            for crit, eligible, subset_results in tasks:
                if len(eligible) == len(state.slides.slides):
                    crit2result[crit] = [self._postprocess_result(crit, r) for r in subset_results]
                else:
                    merged: List[BaseModel] = [None] * len(state.slides.slides)
                    for j, idx in enumerate(eligible):
                        merged[idx] = self._postprocess_result(crit, subset_results[j])
                    crit2result[crit] = merged

        infos = [SLIDE_CRITERIA_INFO[c] for c in state.slide_criterias]
        service_infos = [i for i in infos if i.criteria.is_service_criteria()]
        all_infos = service_infos + [i for i in infos if not i.criteria.is_service_criteria()]

        slide_evaluation_results: List[SlideEvaluationResult] = []

        def _get_result(crit: Criteria, idx: int) -> Optional[BaseModel]:
            lst = crit2result.get(crit) or (state.slide_service or {}).get(crit)
            if not lst or idx >= len(lst):
                return None
            return lst[idx]

        for i, slide in enumerate(state.slides.slides):
            try:
                slide_type_obj = None
                slide_desc_obj = None
                if Criteria.slide_type in state.slide_criterias:
                    st = _get_result(Criteria.slide_type, i)
                    slide_type_obj = cast(SlideType, st) if st else FallbackSlideType()
                if Criteria.slide_description in state.slide_criterias:
                    sd = _get_result(Criteria.slide_description, i)
                    slide_desc_obj = cast(SlideDescription, sd) if sd else FallbackSlideDescription()

                evaluations: Dict[Criteria, Any] = {}
                for info in all_infos:
                    if info.criteria.is_service_criteria():
                        continue
                    val = _get_result(info.criteria, i)
                    if val is not None:
                        evaluations[info.criteria] = val

                slide_evaluation_results.append(
                    SlideEvaluationResult(
                        slide_deck_path=state.slides.slide_deck_path,
                        slide_id=slide.slide_id,
                        slide_type=slide_type_obj,
                        slide_description=slide_desc_obj,
                        evaluations=evaluations,
                    )
                )
            except Exception as e:
                logger.error(f"Error creating slide evaluation result for slide {i}: {e}")
                slide_evaluation_results.append(
                    SlideEvaluationResult(
                        slide_deck_path=state.slides.slide_deck_path,
                        slide_id=slide.slide_id,
                        slide_type=FallbackSlideType(),
                        slide_description=FallbackSlideDescription(),
                        evaluations={},
                    )
                )
        return {"slide_evaluations": slide_evaluation_results}

    async def _node_build_deck_descriptions(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slide_evaluations:
            logger.error("No slide evaluations found. Returning fallback deck descriptions.")
            return {"deck_descriptions": None}
        slide_descriptions: List[SlideDescriptionWithType] = []
        for slide in state.slide_evaluations:
            try:
                if slide.slide_description is not None and slide.slide_type is not None:
                    slide_descriptions.append(
                        SlideDescriptionWithType(
                            **slide.slide_description.model_dump(),
                            slide_type=slide.slide_type.slide_type,
                        )
                    )
            except Exception as e:
                logger.error(f"Error processing slide {slide.slide_id}: {e}")
                continue

        if not slide_descriptions:
            logger.error("No slide descriptions found. Returning fallback deck descriptions.")
            return {"deck_descriptions": None}

        slide_deck_descriptions = SlideDeckDescriptions(
            slide_deck_path=state.presentation_path,
            slides=[DeckDescription.from_slide_descriptions(slide_descriptions)],
        )
        return {"deck_descriptions": slide_deck_descriptions}

    async def _node_evaluate_deck_criteria(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.deck_criterias or not state.deck_descriptions:
            logger.error("No deck criteria or deck descriptions found. Returning fallback deck evaluations.")
            # TODO: return fallback deck evaluations
            return {"deck_evaluations": None}

        evaluations: Dict[Criteria, Any] = {}
        for c in state.deck_criterias:
            info = self.deck_infos[c]
            chain = info.to_runnable(self.llm)
            try:
                res_list = await self._eval_criterion_with_cache(info, state.deck_descriptions, chain, config)
                if res_list and res_list[0] is not None:
                    evaluations[c] = self._postprocess_result(c, res_list[0])
                else:
                    evaluations[c] = FallbackResult()
            except Exception as e:
                logger.warning(f"Failed to evaluate deck criterion {c}: {e}. Returning fallback result.", exc_info=True)
                evaluations[c] = FallbackResult()

        return {"deck_evaluations": DeckEvaluationResult(evaluations=evaluations)}

    async def _node_build_summary(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        payload = self.summary_processor.get_summary_payload(state.slide_evaluations or [], state.deck_evaluations)
        data = payload.model_dump()
        summary_prompt_text = dedent(
            """\
            Create a comprehensive long-form summary of the presentation evaluation.

            Evaluation data:
            {data}

            Use the context to formulate the long-form summary.
            Provide:
            - Short overview of the evaluation
            - Main strengths
            - Main problems
            - Prioritized next steps with slide pointers
            """
        )
        summary_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                SUMMARY_AGENT_BACKSTORY,
            ),
            (
                "user",
                summary_prompt_text,
            ),
        ])
        summary_chain = summary_prompt | self.llm.with_structured_output_retry(SummaryOutput)

        out = await summary_chain.ainvoke({"data": data}, config)
        p = cast(BaseModel, out.pydantic) if hasattr(out, "pydantic") else out
        summary_obj = cast(SummaryOutput, p)
        return {"summary": summary_obj.summary}

    async def _node_build_tldr(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.summary:
            logger.error("No summary found. Returning None for TL;DR.")
            return {"tldr": None}

        tldr_prompt_text = dedent("""
        Based on the previously generated long-form summary in context, write an actionable TL;DR of 2-4 sentences focusing on key issues and next actions.
        Long-form summary:
        {summary}
        """)
        tldr_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                SUMMARY_AGENT_BACKSTORY,
            ),
            (
                "user",
                tldr_prompt_text,
            ),
        ])
        tldr_chain = tldr_prompt | self.llm.with_structured_output_retry(TLDROutput)

        out = await tldr_chain.ainvoke({"summary": state.summary}, config)
        p = cast(BaseModel, out.pydantic) if hasattr(out, "pydantic") else out
        final = cast(TLDROutput, p)
        return {"tldr": final.tldr}

    async def _node_compute_overall(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slide_evaluations or not state.deck_evaluations:
            logger.error("No slide evaluations or deck evaluations found. Returning None for overall score.")
            return {"overall_score": None}
        score = self.summary_processor.calculate_overall_score(state.slide_evaluations or [], state.deck_evaluations)
        return {"overall_score": score}

    def _criterion_applies(self, info: CriterionInfo, slide_types: List[str] | None) -> bool:
        targets = getattr(info, "applicable_slide_types", None)
        if not targets:
            return True
        target_values = set(targets)
        for st in (slide_types or []):
            if st in target_values:
                return True
        return False

    def _filter_sort_by_severity(self, obj: CriterionResult) -> CriterionResult:
        def _severity_value(v: Any) -> int:
            return int(getattr(v, 'severity', 0))
        try:
            items = sorted(getattr(obj, 'evaluation_results', []), key=_severity_value, reverse=True)
            items = [item for item in items if item.severity > 0] # exclude 0 sev items (no issues found)
            setattr(obj, 'evaluation_results', items)
            if not items:
                setattr(obj, 'score', 5) # sanity check
        except Exception as e:
            logger.warning(f"Failed to filter and sort by severity: {e}", exc_info=True)
            pass
        return obj

    def _postprocess_result(self, criteria: Criteria, obj: BaseModel) -> BaseModel:
        try:
            if criteria == Criteria.slide_abbreviations and isinstance(obj, SlideAbbreviations):
                filtered: List[SlideAbbreviationsResult] = []
                wl = ABBREVIATIONS_WHITELIST
                for item in obj.evaluation_results:
                    try:
                        token = str(getattr(item, "evaluation_element", "")).strip().lower().replace(".", "")
                        if token and token not in wl:
                            filtered.append(item)
                    except Exception as e:
                        logger.warning(f"Failed to filter abbreviations: {e}", exc_info=True)
                        filtered.append(item)
                obj.evaluation_results = filtered
            
            if isinstance(obj, CriterionResult):
                obj = cast(CriterionResult, obj)
                obj = self._filter_sort_by_severity(obj)
        except Exception as e:
            logger.warning(f"Failed to postprocess result: {e}", exc_info=True)
            pass
        return obj

    def _create_fallback(self, model_cls: Type[BaseModel]) -> BaseModel:
        try:
            return model_cls.model_validate({})
        except Exception :
            if model_cls.__name__ == "SlideType":
                return FallbackSlideType()
            if model_cls.__name__ == "SlideDescription":
                return FallbackSlideDescription()
            return FallbackResult()

    def _setup_tools(self) -> List:
        """Setup tools for agents"""
        tools = []
        # Note: Search tools temporarily disabled for vLLM compatibility
        # The core evaluation functionality works without external search
        return tools

    async def _eval_criterion_with_cache(
        self,
        info: CriterionInfo,
        deck: Any,
        chain: Runnable,
        config: RunnableConfig,
    ) -> List[BaseModel]:
        async def compute(inputs: List[Tuple[int, Any]]) -> AsyncIterable[Tuple[int, BaseModel]]:
            async def _ainvoke_one(idx: int, payload: Dict[str, Any]) -> Tuple[int, BaseModel]:
                try:
                    out = await chain.ainvoke(payload, config)
                    p = cast(BaseModel, getattr(out, "pydantic", None)) or None
                    if p is None and hasattr(out, "json") and out.json is not None:
                        try:
                            p = info.pydantic.model_validate(out.json)
                        except Exception:
                            p = None
                    if p is None:
                        logger.warning(f"Failed to parse output for {info.criteria.value} idx={idx}. Creating fallback.")
                        p = self._create_fallback(info.pydantic)
                    return idx, p
                except Exception:
                    logger.warning(f"Exception in cache computation for {info.criteria.value} idx={idx}. Creating fallback.")
                    return idx, self._create_fallback(info.pydantic)

            payloads: List[Tuple[int, Dict[str, Any]]] = []
            for i, in_ in inputs:
                data: Dict[str, Any] = {}
                if info.criteria.is_slide_criteria():
                    data = {"slide_image_path": in_.slide_image_path, "slide_id": in_.slide_id}
                else:
                    data = {"deck_description": getattr(in_, "deck_description", "")}
                payloads.append((i, data))

            coros = [_ainvoke_one(i, d) for i, d in payloads]
            for coro in asyncio.as_completed(coros):
                yield await coro

        try:
            entities = await self.cache_manager.compute_with_cache(
                deck_name=deck.slide_deck_path,
                criteria_id=info.criteria.value,
                inputs=deck.slides,
                func=compute,
            )
            if not entities or len(entities) != len(deck.slides):
                entities = [self._create_fallback(info.pydantic) for _ in deck.slides]
            return entities
        except Exception as e:
            logger.error(f"Error in cache computation for {info.criteria.value}: {e}")
            return [self._create_fallback(info.pydantic) for _ in deck.slides]