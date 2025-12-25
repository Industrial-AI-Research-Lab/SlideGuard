"""
Class for slides evaluation and presentation analysis on multiple criteria.
Based on LangGraph + LangChain.
"""

import os
import asyncio
import logging
import random
from textwrap import dedent
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple, Type
from itertools import chain
from typing_extensions import Annotated

from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from langfuse import Langfuse
from slideguard.crew.callbacks import langfuse_callback_cm

from slideguard.crew.controlled_llm import ControlledLLM
from slideguard.criteria.base import CriterionInfo
from slideguard.criteria.factory import CriteriaRegistry, CriteriaRegistryProvider
from slideguard.criteria.types import CriterionResult, PostProcessorContext
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

class FallbackMarker:
    __slideguard_fallback__ = True

class FallbackResult(BaseModel, FallbackMarker):
    error_message: str = "Evaluation failed - fallback result"
    score: float = 0.0
    comments: str = "This evaluation failed due to technical issues. Please try again."
    recommendations: str = "Consider re-running the evaluation with different settings."

class FallbackSlideType(SlideType, FallbackMarker): # NOTE: can be replaced with pydantic fallback values
    slide_type: list[str] = ["unknown"]
    contains_infographics: bool = False

class FallbackSlideDescription(SlideDescription, FallbackMarker): # NOTE: can be replaced with pydantic fallback values
    title: str = "Evaluation Failed"
    description: str = "This slide evaluation failed due to technical issues. Please try again."
    summary: str = "Unable to analyze this slide due to evaluation errors."

class NotApplicableResult(BaseModel, FallbackMarker):
    __slideguard_not_applicable__: bool = True
    reason: str = "Criterion not applicable to this slide"


def _merge_dicts(left: Optional[Dict[Any, Any]], right: Optional[Dict[Any, Any]]) -> Dict[Any, Any]:
    return dict(chain((left or {}).items(), (right or {}).items()))

def _merge_lists(a: Optional[List[Any]], b: Optional[List[Any]]) -> List[Any]:
    return list(set(chain(a or [], b or [])))

def _take_any(a: Optional[Any], b: Optional[Any]) -> Optional[Any]:
    return a or b

class EvaluationState(BaseModel):
    presentation_path: Annotated[str, _take_any]
    slide_criterias: Annotated[List[Criteria], _merge_lists]
    deck_criterias: Annotated[Optional[List[Criteria]], _merge_lists] = None

    slides: Annotated[Optional[SlideDeckImages], _take_any] = None
    slide_service: Annotated[Dict[Criteria, List[BaseModel]], _merge_dicts] = Field(default_factory=dict)
    slide_subsets: Optional[List[Tuple[Criteria, List[int], SlideDeckImages]]] = None
    slide_results: Annotated[Dict[Criteria, List[BaseModel]], _merge_dicts] = Field(default_factory=dict)
    slide_evaluations: Optional[List[SlideEvaluationResult]] = None

    deck_descriptions: Optional[SlideDeckDescriptions] = None
    deck_results: Annotated[Dict[Criteria, BaseModel], _merge_dicts] = Field(default_factory=dict)
    deck_evaluations: Optional[DeckEvaluationResult] = None

    summary: Optional[str] = None
    tldr: Optional[str] = None
    overall_score: Optional[int] = None
    errors: Annotated[List[str], _merge_lists] = Field(default_factory=list)


class SlideGuardEvaluator:
    def __init__(
        self,
        file_manager: FileManager,
        cache_manager: CacheManager,
        llm: ControlledLLM,
        max_concurrency: Optional[int] = None,
        max_retries: int = 3,
        debug: bool = False,
        registry_provider: Optional[CriteriaRegistryProvider] = None,
        max_context_tokens: int = 32000,
        deck_reserved_tokens: int = 8000,
        deck_chars_per_token: float = 2.5,
        deck_max_slides: int = 30, #условно потолок по слайдам
        deck_context_strategy: str = "slide_size", #стратегия обрезки (slide - режем только количество слайдов, size - режем длину слайдов, slide_size - сначала слайды потом объем)
        random_slide_select: bool = False, #если слайдов много - выбираем рандомно чтобы не обрезать повествовательность
        random_slide_seed: Optional[int] = None,
        same_slide: bool = False, #если на обработку не хватает контекста, обрезаем слайды не хронологически, а все пропорционально (если True)
        deck_text_source: str = "summary", #выбираем откуда берем контекст для deck
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
        self._max_context_tokens: int = max_context_tokens
        self._deck_reserved_tokens: int = deck_reserved_tokens
        self._deck_chars_per_token: float = deck_chars_per_token
        self._deck_max_slides: int = deck_max_slides
        self._deck_context_strategy: str = deck_context_strategy
        self._random_slide_select: bool = random_slide_select
        self._random_slide_seed: Optional[int] = random_slide_seed
        self._same_slide: bool = same_slide
        self._deck_text_source: str = deck_text_source

        self.registry_provider = registry_provider
        self._registry: Optional[CriteriaRegistry] = None
        
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
        registry: Optional[CriteriaRegistry] = None,
        user_id: Optional[str] = None,
    ) -> FullEvaluation:
        with langfuse_callback_cm(langfuse_client) as cbs:
            self._callbacks = cbs
        
        if registry:
            self._registry = registry
        elif self.registry_provider:
            self._registry = self.registry_provider.get_for_user(user_id)
        else:
            raise ValueError("Criteria registry is not configured. Provide a registry or registry_provider.")
        
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
        if isinstance(result, dict):
            final_state = EvaluationState.model_validate(result)
        else:
            final_state = result
            
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

    def _get_deck_flow(self, used_deck: List[Criteria]) -> CompiledStateGraph:
        graph = StateGraph(EvaluationState)
        graph.add_node("build_deck_descriptions", self._node_build_deck_descriptions)
        for c in used_deck:
            graph.add_node(c.value, self._make_deck_criterion_node(c))
            graph.add_edge("build_deck_descriptions", c.value) # run in parallel
        graph.add_node("gather_deck_results", self._node_gather_deck_results)
        graph.add_edge([c.value for c in used_deck], "gather_deck_results") # wait for all deck criteria to finish
        graph.set_entry_point("build_deck_descriptions")
        return graph.compile()

    def _get_slide_flow(self, non_service_slide: List[Criteria]) -> CompiledStateGraph:
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

    def _get_summary_flow(self) -> CompiledStateGraph:
        graph = StateGraph(EvaluationState)
        graph.add_node("build_summary", self._node_build_summary)
        graph.add_node("build_tldr", self._node_build_tldr)
        graph.add_node("compute_overall", self._node_compute_overall)
        graph.add_edge("build_summary", "build_tldr")
        graph.add_edge("build_tldr", "compute_overall")
        graph.set_entry_point("build_summary")
        return graph.compile()

    def _setup_app(self, used_slide: List[Criteria], used_deck: Optional[List[Criteria]] = None) -> StateGraph:
        service_slide = [c for c in used_slide if c.is_service_criteria()]
        non_service_slide = [c for c in used_slide if not c.is_service_criteria()]

        main = StateGraph(EvaluationState)
        # Add service nodes
        main.add_node("process_presentation", self._node_process_presentation)
        for c in service_slide:
            main.add_node(c.value, self._make_service_criterion_node(c))

        slide_requires = [Criteria.slide_type] # define requirements for slide flow
        deck_requires = [Criteria.slide_type, Criteria.slide_description] # define requirements for deck flow

        # Add subgraphs
        slide_app = self._get_slide_flow(non_service_slide)
        deck_app = self._get_deck_flow(used_deck) if used_deck else None
        summary_app = self._get_summary_flow()

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
            registry = self._registry
            info = registry.get_info(crit)
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
            registry = self._registry
            info = registry.get_info(crit)
            chain = info.to_runnable(self.llm)
            total = len(state.slides.slides)
            needs_filtering = (
                info.applicable_slide_types or 
                info.exclude_slide_types or
                info.requires_infographics
            )

            eligible = list(range(total))
            if needs_filtering:
                st_service = (state.slide_service or {}).get(Criteria.slide_type)
                if st_service and len(st_service) == total:
                    slide_types_per_slide: List[List[str]] = [st_service[i].slide_type for i in range(total)]
                    eligible = [i for i, types in enumerate(slide_types_per_slide) if self._criterion_applies(info, types, st_service[i].contains_infographics)]
                else:
                    eligible = list(range(total))

            if not eligible:
                logger.info(f"No eligible slides for {crit}. Returning NotApplicableResult for all slides.")
                return {"slide_results": {crit: [NotApplicableResult() for _ in range(total)]}}

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
            merged: List[BaseModel] = [NotApplicableResult() for _ in range(total)]
            for j, idx in enumerate(eligible):
                merged[idx] = self._postprocess_result(crit, subset_entities[j])
            return {"slide_results": {crit: merged}}
        return _run

    async def _node_gather_slide_results(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slides:
            return {}

        service = state.slide_service or {}
        results = state.slide_results or {}
        non_service_criteria = [c for c in (state.slide_criterias or []) if not c.is_service_criteria()]

        out: List[SlideEvaluationResult] = []
        for i, slide in enumerate(state.slides.slides):
            try:
                st = self._safe_get(service, Criteria.slide_type, i) if Criteria.slide_type in (state.slide_criterias or []) else None
                sd = self._safe_get(service, Criteria.slide_description, i) if Criteria.slide_description in (state.slide_criterias or []) else None
                slide_type_obj = st if st else FallbackSlideType()
                slide_desc_obj = sd if sd else FallbackSlideDescription()

                evaluations: Dict[Criteria, Any] = {
                    c: val for c in non_service_criteria
                    if (val := self._safe_get(results, c, i)) is not None and self._is_applicable_result(val)
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


    def _estimate_tokens_from_chars(self, n_chars: int) -> int:
        if self._deck_chars_per_token <= 0:
            return 0
        return int(n_chars / self._deck_chars_per_token)

    def _deck_description_char_budget(self) -> int:
        budget_tokens = max(0, int(self._max_context_tokens) - int(self._deck_reserved_tokens))
        return int(budget_tokens * float(self._deck_chars_per_token))

    def _truncate_text_soft(self, text: str, max_chars: int) -> str:
        if not text or max_chars <= 0:
            return ""
        if len(text) <= max_chars:
            return text
        cut = text[:max_chars]
        window_start = int(max_chars * 0.85)
        for sep in ["\n\n", "\n", ". ", "; ", ", "]:
            j = cut.rfind(sep, window_start)
            if j != -1:
                return cut[: j + len(sep)].rstrip()
        return cut.rstrip()


    def _slide_text_field_name(self, sd: SlideDescriptionWithType) -> Optional[str]:
        if getattr(self, "_deck_text_source", "description") == "summary":
            names = ("summary", "slide_summary", "description", "slide_description", "text")
        else:
            names = ("description", "slide_description", "summary", "slide_summary", "text")
        for name in names:
            if hasattr(sd, name):
                v = getattr(sd, name)
                if isinstance(v, str):
                    return name
        return None

    def _prepare_deck_slide_descriptions(self, slide_descriptions: List[SlideDescriptionWithType]) -> List[SlideDescriptionWithType]:
        if getattr(self, "_deck_text_source", "description") != "summary":
            return slide_descriptions
        out: List[SlideDescriptionWithType] = []
        for sd in slide_descriptions:
            txt = getattr(sd, "summary", None)
            if not isinstance(txt, str) or not txt:
                txt = getattr(sd, "description", "")
                if not isinstance(txt, str):
                    txt = str(txt)
            update = {"description": txt, "summary": txt}
            if hasattr(sd, "model_copy"):
                out.append(sd.model_copy(update=update))
            else:
                out.append(sd.copy(update=update))
        return out

    def _limit_slide_descriptions_proportional(
        self,
        slide_descriptions: List[SlideDescriptionWithType],
    ) -> Tuple[List[SlideDescriptionWithType], Optional[str]]:
        max_chars = self._deck_description_char_budget()
        if not slide_descriptions or max_chars <= 0:
            if max_chars <= 0:
                return slide_descriptions, "deck_description truncated: budget is 0 chars (same_slide=True)"
            return slide_descriptions, None

        field_names: List[Optional[str]] = []
        texts: List[str] = []
        lengths: List[int] = []
        for sd in slide_descriptions:
            fname = self._slide_text_field_name(sd)
            field_names.append(fname)
            if fname is None:
                texts.append("")
                lengths.append(0)
                continue
            t = getattr(sd, fname) or ""
            if not isinstance(t, str):
                t = str(t)
            texts.append(t)
            lengths.append(len(t))

        total_len = sum(lengths)
        if total_len <= max_chars:
            return slide_descriptions, None

        n = len(slide_descriptions)
        alloc = [0] * n
        remaining = {i for i in range(n) if lengths[i] > 0}
        budget_remaining = int(max_chars)

        # Saturating proportional allocation:
        # - slides that are shorter than their share keep full text
        # - remaining budget is redistributed proportionally among the rest
        while remaining and budget_remaining > 0:
            total_remaining = sum(lengths[i] for i in remaining)
            if total_remaining <= 0:
                break

            saturated = []
            for i in remaining:
                share = budget_remaining * (lengths[i] / float(total_remaining))
                a = int(share)
                if a >= lengths[i]:
                    alloc[i] = lengths[i]
                    saturated.append(i)

            if saturated:
                for i in saturated:
                    budget_remaining -= alloc[i]
                    remaining.remove(i)
                continue

            # Final proportional allocation with rounding + exact sum fixup
            rem = list(remaining)
            total_remaining = sum(lengths[i] for i in rem)
            for i in rem:
                alloc[i] = min(lengths[i], int(round(budget_remaining * lengths[i] / float(total_remaining))))

            s = sum(alloc[i] for i in rem)
            diff = budget_remaining - s

            if diff != 0:
                if diff > 0:
                    order = sorted(rem, key=lambda i: (lengths[i] - alloc[i]), reverse=True)
                    for i in order:
                        if diff <= 0:
                            break
                        cap = lengths[i] - alloc[i]
                        if cap <= 0:
                            continue
                        add = min(cap, diff)
                        alloc[i] += add
                        diff -= add
                else:
                    diff = -diff
                    order = sorted(rem, key=lambda i: alloc[i], reverse=True)
                    for i in order:
                        if diff <= 0:
                            break
                        if alloc[i] <= 0:
                            continue
                        sub = min(alloc[i], diff)
                        alloc[i] -= sub
                        diff -= sub

            budget_remaining = 0
            break

        did_truncate = False
        new_sds: List[SlideDescriptionWithType] = []
        for i, sd in enumerate(slide_descriptions):
            fname = field_names[i]
            if fname is None:
                new_sds.append(sd)
                continue
            orig = texts[i]
            lim = int(alloc[i]) if lengths[i] > 0 else 0
            new_text = self._truncate_text_soft(orig, lim) if lim > 0 else ""
            if new_text != orig:
                did_truncate = True
                if hasattr(sd, "model_copy"):
                    sd = sd.model_copy(update={fname: new_text})
                else:
                    sd = sd.copy(update={fname: new_text})
            new_sds.append(sd)

        if did_truncate:
            tok_est = self._estimate_tokens_from_chars(max_chars)
            return new_sds, f"deck_description truncated: proportional per-slide limit applied (same_slide=True), budget≈{tok_est} tokens (~{max_chars} chars)"
        return new_sds, None

    def _select_deck_slides(self, slide_descriptions: List[SlideDescriptionWithType]) -> List[SlideDescriptionWithType]:
        n = len(slide_descriptions)
        k = int(self._deck_max_slides) if self._deck_max_slides is not None else n
        if k <= 0 or n <= k:
            return slide_descriptions

        # Always preserve conclusion/intro when we are forced to cut slides.
        # For narrative-oriented deck criteria, losing the last slide is usually worse than losing a random middle slide.
        if k == 1:
            return [slide_descriptions[n - 1]]

        idxs = {0, n - 1}

        if k > 2:
            if self._random_slide_select:
                rng = random.Random(self._random_slide_seed)
                candidates = list(range(1, n - 1))
                need = min(k - 2, len(candidates))
                if need > 0:
                    idxs.update(rng.sample(candidates, k=need))
            else:
                step = (n - 1) / float(k - 1)
                for i in range(k):
                    idxs.add(int(round(i * step)))

        return [slide_descriptions[i] for i in sorted(idxs)[:k]]
    def _limit_deck_description_text(self, deck_text: str) -> Tuple[str, Optional[str]]:
        max_chars = self._deck_description_char_budget()
        if max_chars <= 0:
            return "", "deck_description budget is 0"
        if deck_text is None:
            return "", None
        if len(deck_text) <= max_chars:
            return deck_text, None
        limited = self._truncate_text_soft(deck_text, max_chars=max_chars)
        msg = f"deck_description truncated: chars={len(deck_text)} -> {len(limited)} (~{self._estimate_tokens_from_chars(len(limited))} tokens est)"
        return limited, msg


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
                st = self._safe_get(types, i)
                sd = self._safe_get(descs, i)
                if sd is None: # allow for slide_type fails
                    continue
                slide_descriptions.append(
                    SlideDescriptionWithType(
                        **sd.model_dump(),
                        slide_type=st.slide_type if st else [],
                        contains_infographics=st.contains_infographics if st else False, # NOTE: can be replaced with pydantic fallback values
                    )
                )
            except Exception as e:
                logger.error(f"Error processing slide {i} for deck descriptions: {e}")
                continue
        if not slide_descriptions:
            logger.warning("No slide descriptions found.")
            return {}
        slide_descriptions = self._prepare_deck_slide_descriptions(slide_descriptions)
        if self._deck_context_strategy in ("sample", "sample_truncate"):
            slide_descriptions = self._select_deck_slides(slide_descriptions)

        errors: List[str] = []

        if self._deck_context_strategy in ("truncate", "sample_truncate") and getattr(self, "_same_slide", False):
            slide_descriptions, per_err = self._limit_slide_descriptions_proportional(slide_descriptions)
            if per_err:
                errors.append(per_err)

        deck_desc = DeckDescription.from_slide_descriptions(slide_descriptions)

        if self._deck_context_strategy in ("truncate", "sample_truncate"):
            limited_text, tail_err = self._limit_deck_description_text(getattr(deck_desc, "deck_description", "") or "")
            if limited_text != getattr(deck_desc, "deck_description", ""):
                if hasattr(deck_desc, "model_copy"):
                    deck_desc = deck_desc.model_copy(update={"deck_description": limited_text})
                else:
                    deck_desc = deck_desc.copy(update={"deck_description": limited_text})
            if tail_err:
                errors.append(tail_err)

        slide_deck_descriptions = SlideDeckDescriptions(
            slide_deck_path=state.presentation_path,
            slides=[deck_desc],
        )
        if errors:
            return {"deck_descriptions": slide_deck_descriptions, "errors": errors}
        return {"deck_descriptions": slide_deck_descriptions}

    def _make_deck_criterion_node(self, crit: Criteria):
        async def _run(state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
            if not state.deck_criterias or not state.deck_descriptions or crit not in state.deck_criterias:
                return {}
            registry = self._registry
            info = registry.get_info(crit)
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
        payload = self.summary_processor.get_summary_payload(
            state.slide_evaluations or [],
            state.deck_evaluations,
            registry=self._registry,
        )
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
        summary_obj = out.pydantic
        if summary_obj is None:
            logger.error("Failed to parse summary output. Returning None.")
            return {"summary": None}
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
        final = out.pydantic
        if final is None:
            logger.error("Failed to parse TLDR output. Returning None.")
            return {"tldr": None}
        return {"tldr": final.tldr}

    async def _node_compute_overall(self, state: EvaluationState, config: RunnableConfig) -> Dict[str, Any]:
        if not state.slide_evaluations or not state.deck_evaluations:
            logger.error("No slide evaluations or deck evaluations found. Returning None for overall score.")
            return {"overall_score": None}
        score = self.summary_processor.calculate_overall_score(state.slide_evaluations or [], state.deck_evaluations)
        return {"overall_score": score}

    def _criterion_applies(self, info: CriterionInfo, slide_types: List[str], contains_infographics: bool) -> bool:
        ts, xs, ri = info.applicable_slide_types, info.exclude_slide_types, info.requires_infographics
        # Check exclusions first
        if xs:
            # Ensure xs contains strings (not enum objects)
            xs_str = [str(x) for x in xs]
            if any(st in xs_str for st in slide_types):
                return False
        # Check applicable types
        if ts:
            # Ensure ts contains strings (not enum objects)
            ts_str = [str(t) for t in ts]
            if not any(st in ts_str for st in slide_types):
                return False
        # Check infographics requirement
        if ri and not contains_infographics:
            return False
            return True

    def _is_applicable_result(self, v: Optional[BaseModel]) -> bool:
        if v is None:
            return False
        return not isinstance(v, NotApplicableResult)


    def _postprocess_result(self, criteria: Criteria, obj: BaseModel) -> BaseModel:
        try:
            if isinstance(obj, CriterionResult):
                info = self._registry.get_info(criteria)
                ctx = PostProcessorContext(criteria_id=criteria.value)
                result = obj
                for postprocessor_func in info.postprocessors:
                    result = postprocessor_func(result, ctx)
                return result
        except Exception as e:
            logger.warning(f"Postprocessing skipped for {criteria}: {e}")
        return obj

    def _create_fallback(self, model_cls: Type[BaseModel]) -> BaseModel:
        try:
            return model_cls()
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
            os.makedirs(out_dir, exist_ok=True)
            
            # Save main graph
            graph = app.get_graph()
            if graph:
                png_path = os.path.join(out_dir, f"{base_name}.png")
                data = graph.draw_mermaid_png()
                with open(png_path, "wb") as f:
                    f.write(data)
            
            # Save full graph
            full_graph = app.get_graph(xray=True)
            if full_graph:
                full_png = os.path.join(out_dir, f"{base_name}_full.png")
                full_data = full_graph.draw_mermaid_png()
                with open(full_png, "wb") as f:
                    f.write(full_data)
            
            # Save subgraphs
            for name, sub in (self._compiled_subgraphs or {}).items():
                sub_graph = sub.get_graph()
                if sub_graph:
                    sub_png = os.path.join(out_dir, f"{base_name}_{name}.png")
                    sub_data = sub_graph.draw_mermaid_png()
                    with open(sub_png, "wb") as f:
                        f.write(sub_data)
        except Exception as e:
            logger.warning(f"Failed to export graph images: {e}")

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
                    p = out.pydantic
                    if p is None and out.json is not None:
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
                     else {"deck_description": in_.deck_description if info.criteria.is_deck_criteria() else ""})
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
