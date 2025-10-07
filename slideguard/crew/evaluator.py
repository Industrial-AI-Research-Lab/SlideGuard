"""
Class for slides evaluation and presentation analysis on multiple criteria.
Based on LangGraph + LangChain.
"""

import os
import shutil
import subprocess
import asyncio
import logging
from textwrap import dedent
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple, Type, cast, Protocol, runtime_checkable, Literal
from typing_extensions import Annotated

from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
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


class NotApplicableResult(BaseModel, FallbackMarker):
    __slideguard_not_applicable__: bool = True
    reason: str = "Criterion not applicable to this slide"


def _merge_dicts(left: Optional[Dict[Any, Any]], right: Optional[Dict[Any, Any]]) -> Dict[Any, Any]:
    l = dict(left or {})
    for k, v in (right or {}).items():
        l[k] = v
    return l

def _merge_lists(a: Optional[List[Any]], b: Optional[List[Any]]) -> List[Any]:
    return list(set(a or []) | set(b or []))

def _take_any(a: Optional[Any], b: Optional[Any]) -> Optional[Any]:
    return a or b

class EvaluationState(BaseModel):
    presentation_path: Annotated[str, _take_any]
    slide_criterias: Annotated[List[Criteria], _merge_lists]
    deck_criterias: Annotated[Optional[List[Criteria]], _merge_lists] = None

    slides: Annotated[Optional[SlideDeckImages], _take_any] = None
    slide_service: Annotated[Dict[Criteria, List[BaseModel]], _merge_dicts] = {}
    slide_subsets: Optional[List[Tuple[Criteria, List[int], SlideDeckImages]]] = None
    slide_results: Annotated[Dict[Criteria, List[BaseModel]], _merge_dicts] = {}
    slide_evaluations: Optional[List[SlideEvaluationResult]] = None

    deck_descriptions: Optional[SlideDeckDescriptions] = None
    deck_results: Annotated[Dict[Criteria, BaseModel], _merge_dicts] = {}
    deck_evaluations: Optional[DeckEvaluationResult] = None

    summary: Optional[str] = None
    tldr: Optional[str] = None
    overall_score: Optional[int] = None
    errors: Annotated[List[str], _merge_lists] = []


class SlideGuardEvaluator:
    def __init__(
        self,
        file_manager: FileManager,
        cache_manager: CacheManager,
        llm: ControlledLLM,
        max_concurrency: Optional[int] = None,
        max_retries: int = 3,
        debug: bool = False,
    ) -> None:
        self.file_manager = file_manager
        self.cache_manager = cache_manager
        self.llm = llm
        self.tools = self._setup_tools()
        self.max_retries = max_retries
        self.summary_processor = SummaryProcessor()
        self._compiled_subgraphs: Dict[str, Any] = {}
        self._debug: bool = debug # if true, save graph images (for now)
        self._max_concurrency: Optional[int] = max_concurrency
        
        self.slide_infos: Dict[Criteria, CriterionInfo] = dict(SLIDE_CRITERIA_INFO)
        self.deck_infos: Dict[Criteria, CriterionInfo] = dict(DECK_CRITERIA_INFO)
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
            slide_criterias = list({*(slide_criterias or []), Criteria.slide_type, Criteria.slide_description})
        elif slide_criterias:
            if any(not c.is_service_criteria() for c in slide_criterias) and Criteria.slide_type not in slide_criterias:
                slide_criterias = list({*slide_criterias, Criteria.slide_type})

        initial = EvaluationState(
            presentation_path=presentation_path,
            slide_criterias=slide_criterias,
            deck_criterias=deck_criterias,
        )
        
        app = self._setup_app(initial.slide_criterias, initial.deck_criterias)
        if self._debug:
            try:
                self._save_graph_images(app)
            except Exception as e:
                logger.warning(f"Failed to export graph: {e}", exc_info=True)

        # Build base config and inject max_concurrency if set
        base_config: Dict[str, Any] = {"configurable": {"thread_id": "1"}}
        if self._callbacks:
            base_config["callbacks"] = self._callbacks
        if self._max_concurrency is not None:
            base_config["max_concurrency"] = self._max_concurrency

        result = await app.ainvoke(initial, config=base_config)
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

    def _setup_tools(self) -> List:
        """Setup tools for agents"""
        tools = []
        # Note: Search tools temporarily disabled for vLLM compatibility
        # The core evaluation functionality works without external search
        return tools

    def _setup_app(self, used_slide: List[Criteria], used_deck: Optional[List[Criteria]] = None) -> StateGraph:
        service_slide = [c for c in used_slide if c.is_service_criteria()]
        non_service_slide = [c for c in used_slide if not c.is_service_criteria()]

        def _get_deck_flow():
            graph = StateGraph(EvaluationState)
            graph.add_node("build_deck_descriptions", self._node_build_deck_descriptions)
            for c in used_deck:
                graph.add_node(c.value, self._make_deck_criterion_node(c))
                graph.add_edge("build_deck_descriptions", c.value) # run in parallel
            graph.add_node("gather_deck_results", self._node_gather_deck_results)
            graph.add_edge([c.value for c in used_deck], "gather_deck_results") # wait for all deck criteria to finish
            graph.set_entry_point("build_deck_descriptions")
            return graph.compile()

        def _get_slide_flow():
            graph = StateGraph(EvaluationState)
            graph.add_node("slide_entry", lambda s: {}) # dummy node for cleaner code
            for c in non_service_slide:
                graph.add_node(c.value, self._make_slide_criterion_node(c))
            graph.add_node("gather_slide_results", self._node_gather_slide_results)
            for c in non_service_slide:
                graph.add_edge("slide_entry", c.value) # run in parallel
            graph.add_edge([c.value for c in non_service_slide], "gather_slide_results") # wait for all slide criteria to finish
            if not non_service_slide:
                graph.add_edge("slide_entry", "gather_slide_results")
            graph.set_entry_point("slide_entry")
            return graph.compile()

        def _get_summary_flow():
            graph = StateGraph(EvaluationState)
            graph.add_node("build_summary", self._node_build_summary)
            graph.add_node("build_tldr", self._node_build_tldr)
            graph.add_node("compute_overall", self._node_compute_overall)
            graph.add_edge("build_summary", "build_tldr")
            graph.add_edge("build_tldr", "compute_overall")
            graph.set_entry_point("build_summary")
            return graph.compile()

        main = StateGraph(EvaluationState)
        # Add service nodes
        main.add_node("process_presentation", self._node_process_presentation)
        for c in service_slide:
            main.add_node(c.value, self._make_service_criterion_node(c))

        slide_requires = [Criteria.slide_type.value] # define requirements for slide flow
        deck_requires = [Criteria.slide_type.value, Criteria.slide_description.value] # define requirements for deck flow

        # Add subgraphs
        slide_app = _get_slide_flow()
        deck_app = _get_deck_flow() if used_deck else None
        summary_app = _get_summary_flow()

        main.add_node("slide_flow", slide_app)
        if deck_app:
            main.add_node("deck_flow", deck_app)
        main.add_node("summary_flow", summary_app)

        # Entry
        main.set_entry_point("process_presentation")

        # Add service edges
        for c in service_slide:
            main.add_edge("process_presentation", c.value)

        # Main flows (slide + deck)
        main.add_edge([c.value for c in service_slide if c in slide_requires], "slide_flow")
        if deck_app:
            main.add_edge([c.value for c in service_slide if c in deck_requires], "deck_flow")

        # Summary flow
        if deck_app:
            main.add_edge(["slide_flow", "deck_flow"], "summary_flow") # wait for slide and deck subgraphs to finish
        else:
            main.add_edge("slide_flow", "summary_flow")
            
        app = main.compile(checkpointer=MemorySaver())

        if self._debug:
            try:
                subs: Dict[str, Any] = {"summary_flow": summary_app}
                if deck_app:
                    subs["deck_flow"] = deck_app
                if not non_service_slide:
                    subs["slide_flow"] = slide_app
                self._compiled_subgraphs = subs
            except Exception as e:
                logger.warning(f"Failed to compile subgraphs: {e}")
                self._compiled_subgraphs = {}

        return app

    async def _node_process_presentation(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        slides = self.file_manager.process_presentation(state.presentation_path)
        if not slides.slides:
            raise ValueError(f"Failed to process presentation: {state.presentation_path}")
        return {"slides": slides}

    def _make_service_criterion_node(self, crit: Criteria):
        async def _run(state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
            if not state.slides or crit not in state.slide_criterias:
                return {}
            info = self.slide_infos[crit]
            chain = info.to_runnable(self.llm)
            entities = await self._eval_criterion_with_cache(
                info=info,
                deck=state.slides,
                chain=chain,
                config=config,
            )
            if not entities:
                logger.error(f"No entities found for {crit}.")
            return {"slide_service": {crit: entities}}
        return _run

    def _make_slide_criterion_node(self, crit: Criteria):
        async def _run(state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
            if not state.slides or crit not in state.slide_criterias:
                return {}
            info = SLIDE_CRITERIA_INFO[crit]
            chain = info.to_runnable(self.llm)
            total = len(state.slides.slides)
            applicable = info.applicable_slide_types
            requires_type = info.requires_slide_type

            eligible = list(range(total))
            if applicable or requires_type:
                st_service = (state.slide_service or {}).get(Criteria.slide_type)
                if st_service and len(st_service) == total:
                    slide_types_per_slide: List[List[str]] = [cast(SlideType, st_service[i]).slide_type for i in range(total)]
                    eligible = [i for i, types in enumerate(slide_types_per_slide) if self._criterion_applies(info, types)]
                else:
                    eligible = list(range(total))

            if not eligible:
                logger.warning(f"No eligible slides for {crit}. Running for all slides.")
                eligible = list(range(total))

            if len(eligible) == total:
                entities = await self._eval_criterion_with_cache(info=info, deck=state.slides, chain=chain, config=config)
                processed = [self._postprocess_result(crit, r) for r in entities]
                return {"slide_results": {crit: processed}}

            subset = SlideDeckImages(
                slide_deck_path=state.slides.slide_deck_path,
                png_dir=state.slides.png_dir,
                slides=[state.slides.slides[i] for i in eligible],
            )
            subset_entities = await self._eval_criterion_with_cache(info=info, deck=subset, chain=chain, config=config)
            merged: List[BaseModel] = [cast(BaseModel, NotApplicableResult()) for _ in range(total)]
            for j, idx in enumerate(eligible):
                merged[idx] = self._postprocess_result(crit, subset_entities[j])
            return {"slide_results": {crit: merged}}
        return _run

    async def _node_gather_slide_results(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slides:
            return {}
        def _is_not_applicable(v: Optional[BaseModel]) -> bool:
            try:
                return bool(getattr(v, "__slideguard_not_applicable__", False)) if v is not None else False
            except Exception:
                return False

        service = state.slide_service or {}
        results = state.slide_results or {}
        non_service_criteria = [c for c in (state.slide_criterias or []) if not c.is_service_criteria()]

        out: List[SlideEvaluationResult] = []
        for i, slide in enumerate(state.slides.slides):
            try:
                st = self._safe_get(service, Criteria.slide_type, i) if Criteria.slide_type in (state.slide_criterias or []) else None
                sd = self._safe_get(service, Criteria.slide_description, i) if Criteria.slide_description in (state.slide_criterias or []) else None
                slide_type_obj = cast(SlideType, st) if st else FallbackSlideType()
                slide_desc_obj = cast(SlideDescription, sd) if sd else FallbackSlideDescription()

                evaluations: Dict[Criteria, Any] = {
                    c: val for c in non_service_criteria
                    if (val := self._safe_get(results, c, i)) is not None and not _is_not_applicable(val)
                }

                out.append(
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
                out.append(
                    SlideEvaluationResult(
                        slide_deck_path=state.slides.slide_deck_path,
                        slide_id=slide.slide_id,
                        slide_type=FallbackSlideType(),
                        slide_description=FallbackSlideDescription(),
                        evaluations={},
                    )
                )
        return {"slide_evaluations": out}

    async def _node_build_deck_descriptions(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slides:
            return {}
        types = (state.slide_service or {}).get(Criteria.slide_type) or []
        descs = (state.slide_service or {}).get(Criteria.slide_description) or []
        if len(descs) != len(state.slides.slides) or len(types) != len(state.slides.slides):
            return {}
        slide_descriptions: List[SlideDescriptionWithType] = []
        for i in range(len(state.slides.slides)):
            try:
                st = cast(SlideType, self._safe_get(types, i))
                sd = cast(SlideDescription, self._safe_get(descs, i))
                if sd is None: # allow for slide_type fails
                    continue
                slide_descriptions.append(
                    SlideDescriptionWithType(
                        **sd.model_dump(),
                        slide_type=st.slide_type if st else [],
                    )
                )
            except Exception as e:
                logger.error(f"Error processing slide {i} for deck descriptions: {e}")
                continue
        if not slide_descriptions:
            logger.warning("No slide descriptions found.")
            return {}
        slide_deck_descriptions = SlideDeckDescriptions(
            slide_deck_path=state.presentation_path,
            slides=[DeckDescription.from_slide_descriptions(slide_descriptions)],
        )
        return {"deck_descriptions": slide_deck_descriptions}

    def _make_deck_criterion_node(self, crit: Criteria):
        async def _run(state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
            if not state.deck_criterias or not state.deck_descriptions or crit not in state.deck_criterias:
                return {}
            info = self.deck_infos[crit]
            chain = info.to_runnable(self.llm)
            try:
                res_list = await self._eval_criterion_with_cache(info, state.deck_descriptions, chain, config)
                if res_list and res_list[0] is not None:
                    val = self._postprocess_result(crit, res_list[0])
                else:
                    val = FallbackResult()
            except Exception as e:
                logger.warning(f"Failed to evaluate deck criterion {crit}: {e}. Returning fallback result.", exc_info=True)
                val = FallbackResult()
            return {"deck_results": {crit: val}}
        return _run

    async def _node_gather_deck_results(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.deck_criterias:
            return {"deck_evaluations": None}
        try:
            evaluations: Dict[Criteria, Any] = {
                c: ((state.deck_results or {}).get(c) or FallbackResult())
                for c in state.deck_criterias
            }
            return {"deck_evaluations": DeckEvaluationResult(evaluations=evaluations)}
        except Exception as e:
            logger.warning(f"Failed to gather deck results: {e}", exc_info=True)
            return {"deck_evaluations": DeckEvaluationResult(evaluations={})}

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
        targets = info.applicable_slide_types
        if not targets:
            return True
        target_values = set(targets)
        return any(st in target_values for st in (slide_types or []))

    def _filter_sort_by_severity(self, obj: CriterionResult) -> CriterionResult:
        try:
            items = sorted(obj.evaluation_results, key=lambda v: v.severity, reverse=True)
            items = [item for item in items if item.severity > 0] # exclude 0 sev items (no issues found)
            obj.evaluation_results = items
            if not items:
                obj.score = 5 # sanity check
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
                        token = str(item.evaluation_element).strip().lower().replace(".", "")
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

    def _safe_get(self, container: Any, key_or_idx: Any, idx: Optional[int] = None) -> Optional[BaseModel]:
        try:
            if isinstance(container, dict):
                lst = container.get(key_or_idx)
                i = 0 if idx is None else idx
            else:
                lst = container
                i = key_or_idx if isinstance(key_or_idx, int) else 0
            return lst[i] if lst and i < len(lst) else None
        except Exception:
            return None

    def _save_graph_images(self, app: CompiledStateGraph) -> None:
        base_name = "slideguard_graph"
        try:
            out_dir = os.path.join(os.getcwd(), ".graph_images")
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                pass
            png_path = os.path.join(out_dir, f"{base_name}.png")
            graph = app.get_graph()
            if not graph:
                return
            try:
                data = graph.draw_mermaid_png()
            except Exception as e:
                logger.error(f"draw_mermaid_png failed: {e}")
                return
            try:
                with open(png_path, "wb") as f:
                    f.write(data)
            except Exception as e:
                logger.error(f"PNG write failed: {e}")
            try:
                full_graph = app.get_graph(xray=True)
                full_png = os.path.join(out_dir, f"{base_name}_full.png")
                full_data = full_graph.draw_mermaid_png()
                with open(full_png, "wb") as f:
                    f.write(full_data)
            except Exception as e:
                logger.error(f"Full workflow export failed: {e}")
            try:
                for name, sub in (self._compiled_subgraphs or {}).items():
                    try:
                        sub_graph = sub.get_graph()
                        if not sub_graph:
                            continue
                        sub_png = os.path.join(out_dir, f"{base_name}_{name}.png")
                        sub_data = sub_graph.draw_mermaid_png()
                        with open(sub_png, "wb") as f:
                            f.write(sub_data)
                    except Exception as e:
                        logger.error(f"Subgraph '{name}' export failed: {e}")
            except Exception as e:
                logger.error(f"Subgraphs export failed: {e}")
        except Exception:
            logger.exception("Graph export failed")

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

            payloads: List[Tuple[int, Dict[str, Any]]] = [
                (
                    i,
                    ({"slide_image_path": in_.slide_image_path, "slide_id": in_.slide_id}
                     if info.criteria.is_slide_criteria()
                     else {"deck_description": getattr(in_, "deck_description", "")})
                )
                for i, in_ in inputs
            ]

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