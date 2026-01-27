from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langfuse import Langfuse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field

from slideguard.criteria.factory import CriteriaRegistry
from slideguard.crew.controlled_llm import AppLanguage, ControlledLLM
from slideguard.metrics.observability import metrics_trace
from slideguard.metrics.schemas import (
    AtomicIssue,
    FeedbackEntry,
    FeedbackIssue,
    NormalizedIssue,
    UnmappedFeedback,
)


logger = logging.getLogger(__name__)


class FeedbackGraphState(BaseModel):
    feedback_text: str
    presentation_path: str
    user_id: Optional[str]
    persist: bool
    feedback_hash: str
    language: Optional[str] = None
    presentation_text: Optional[str] = None
    atoms: List[AtomicIssue] = Field(default_factory=list)
    normalized: List[FeedbackIssue] = Field(default_factory=list)
    low_confidence: List[AtomicIssue] = Field(default_factory=list)


class AtomicIssuesList(BaseModel):
    issues: List[AtomicIssue] = Field(default_factory=list, description="List of extracted atomic issues from feedback")


class LanguageDetectionResult(BaseModel):
    language: str = Field(description="Detected language code: 'en' or 'ru'")


class FeedbackHandler:
    def __init__(
        self,
        llm: ControlledLLM,
        criteria_registry: CriteriaRegistry,
        feedback_log_dir: Path = Path("resources/feedback_logs"),
        unmapped_dir: Path = Path("resources/unmapped_feedback"),
        min_confidence: float = 0.5,
    ) -> None:
        self.llm = llm
        self.registry = criteria_registry
        self.feedback_log_dir = feedback_log_dir
        self.unmapped_dir = unmapped_dir
        self.min_confidence = min_confidence
        self.feedback_log_dir.mkdir(parents=True, exist_ok=True)
        self.unmapped_dir.mkdir(parents=True, exist_ok=True)
        self._graph = self._build_graph()

    async def process_presentation_feedback(
        self,
        feedback_text: str,
        presentation_path: str,
        user_id: Optional[str] = None,
        persist: bool = True,
        langfuse_client: Optional[Langfuse] = None,
        language: Optional[AppLanguage | str] = None,
        presentation_text: Optional[str] = None,
    ) -> List[FeedbackIssue]:
        feedback_hash = self._compute_hash(feedback_text, presentation_path)
        if self._is_duplicate(feedback_hash):
            return []
        lang_value: Optional[str] = None
        if language:
            try:
                lang_value = AppLanguage(str(language).lower()).value
            except Exception:
                lang_value = None
        state = FeedbackGraphState(
            feedback_text=feedback_text,
            presentation_path=presentation_path,
            user_id=user_id,
            persist=persist,
            feedback_hash=feedback_hash,
            language=lang_value,
            presentation_text=presentation_text,
        )
        metadata = {"presentation_path": presentation_path}
        with metrics_trace(feedback_hash[:12], "feedback_processing", metadata, langfuse_client) as trace:
            final_state = await self._graph.ainvoke(state)
            issues = final_state.normalized
            if trace:
                try:
                    trace.update(
                        output={
                            "presentation_path": presentation_path,
                            "issues": [issue.issue.issue for issue in issues],
                            "count": len(issues),
                        }
                    )
                except Exception as exc:
                    logger.warning("Failed to update Langfuse trace: %s", exc, exc_info=True)
            return issues

    def _build_graph(self):
        graph = StateGraph(FeedbackGraphState)
        graph.add_node("detect_language", self._node_detect_language)
        graph.add_node("chunk_feedback", self._node_chunk_feedback)
        graph.add_node("normalize", self._node_normalize)
        graph.add_node("finalize", self._node_finalize)
        graph.add_edge("detect_language", "chunk_feedback")
        graph.add_edge("chunk_feedback", "normalize")
        graph.add_edge("normalize", "finalize")
        graph.set_entry_point("detect_language")
        return graph.compile(checkpointer=MemorySaver())

    async def _node_detect_language(self, state: FeedbackGraphState, config) -> dict:
        if state.language:
            return {"language": state.language}
        language = await self._detect_language_robust(state.feedback_text, state.presentation_path, state.presentation_text)
        return {"language": language}

    async def _node_chunk_feedback(self, state: FeedbackGraphState, config) -> dict:
        language = state.language or "en"
        atoms = await self._chunk_feedback(state.feedback_text, language)
        return {"atoms": atoms}

    def _node_normalize(self, state: FeedbackGraphState, config) -> dict:
        normalized: List[FeedbackIssue] = []
        low_conf: List[AtomicIssue] = []
        for atomic in state.atoms:
            if atomic.criterion.is_service_criteria():
                continue
            normalized_issue = NormalizedIssue(issue=atomic.issue_text.strip(), severity=2, suggestion=None)
            if atomic.confidence < self.min_confidence or atomic.needs_review:
                low_conf.append(atomic)
                continue
            normalized.append(
                FeedbackIssue(
                    presentation_path=state.presentation_path,
                    criterion=atomic.criterion,
                    slide_ids=atomic.slide_ids,
                    issue=normalized_issue,
                )
            )
        return {"normalized": normalized, "low_confidence": low_conf}

    def _node_finalize(self, state: FeedbackGraphState, config) -> dict:
        if not state.persist:
            return {}
        if state.normalized:
            for issue in state.normalized:
                entry = FeedbackEntry(
                    feedback_id=uuid.uuid4().hex,
                    feedback_text=state.feedback_text,
                    presentation_path=state.presentation_path,
                    slide_id=issue.slide_ids[0] if issue.slide_ids else None,
                    criterion=issue.criterion,
                    agreement=None,
                    comment=None,
                    source="cli",
                    needs_review=False,
                    user_id=state.user_id,
                    feedback_hash=state.feedback_hash,
                )
                self._append_jsonl(self._current_log_path(), entry.model_dump(mode="json"))
        else:
            entry = FeedbackEntry(
                feedback_id=uuid.uuid4().hex,
                feedback_text=state.feedback_text,
                presentation_path=state.presentation_path,
                slide_id=None,
                criterion=None,
                agreement=None,
                comment=None,
                source="cli",
                needs_review=True,
                user_id=state.user_id,
                feedback_hash=state.feedback_hash,
            )
            self._append_jsonl(self._current_log_path(), entry.model_dump(mode="json"))
        for atomic in state.low_confidence:
            record = UnmappedFeedback(
                feedback_id=uuid.uuid4().hex,
                presentation_path=state.presentation_path,
                issue_text=atomic.issue_text,
                reason="low_confidence",
            )
            self._append_jsonl(self._unmapped_path(), record.model_dump(mode="json"))
        return {}

    async def _chunk_feedback(self, feedback_text: str, language: str) -> List[AtomicIssue]:
        criteria_context = self._build_criteria_context()
        prompt = self._build_prompt(feedback_text, language, criteria_context)
        
        llm_with_lang = self.llm
        try:
            lang_enum = AppLanguage(language.lower())
            llm_with_lang = ControlledLLM(
                chat_model=self.llm.chat_model,
                max_retries=self.llm.max_retries,
                retry_temperature=self.llm.retry_temperature,
                preprocessors=self.llm.preprocessors,
                language=lang_enum,
            )
        except Exception:
            pass
        
        chain = prompt | llm_with_lang.with_structured_output_retry(AtomicIssuesList)
        result = await chain.ainvoke({})
        
        if result.pydantic is None:
            logger.error("Failed to parse feedback response as structured output")
            return []
        
        return result.pydantic.issues

    def _build_prompt(self, feedback_text: str, language: str, criteria_context: str) -> ChatPromptTemplate:
        lang_name = "Russian" if language == "ru" else "English"
        
        system_message = f"""You are an expert at analyzing presentation feedback and extracting actionable, atomic issues.

Your task is to:
1. Break down the feedback into individual, atomic issues
2. Map each issue to the most appropriate evaluation criterion
3. Identify which slides (if any) the issue applies to
4. Assess your confidence in the mapping
5. Flag issues that need human review

Guidelines:
- Each atomic issue should be a single, specific problem or suggestion
- If feedback mentions multiple issues, extract them separately
- Slide IDs should be 0-indexed (first slide is 0)
- Use empty slide_ids list for deck-level issues
- Confidence should reflect how certain you are about the criterion mapping
- Set needs_review=True if the issue is ambiguous or doesn't clearly map to any criterion

Language: All extracted issue_text fields must be in {lang_name} (the same language as the feedback).

Available criteria:
{criteria_context}

Return a list of atomic issues, each with:
- criterion: The criterion enum name this issue relates to
- slide_ids: List of slide indices (0-indexed) this applies to, or empty for deck-level
- issue_text: The specific issue description in {lang_name}
- confidence: Your confidence (0.0-1.0) in this mapping
- needs_review: Whether this needs human review"""

        user_message = f"""Feedback to analyze:
{feedback_text}"""

        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", user_message),
        ])

    def _build_criteria_context(self) -> str:
        parts: List[str] = []
        for criterion in sorted(self.registry.get_slide_ids(), key=lambda c: c.value):
            if criterion.is_service_criteria():
                continue
            info = self.registry.get_info(criterion)
            parts.append(f"{criterion.value}: {info.description or ''}".strip())
        for criterion in sorted(self.registry.get_deck_ids(), key=lambda c: c.value):
            info = self.registry.get_info(criterion)
            parts.append(f"{criterion.value}: {info.description or ''}".strip())
        return "\n".join(parts)

    async def _detect_language_robust(self, feedback_text: str, presentation_path: str, presentation_text: Optional[str]) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a language detection expert. Determine the primary language of the given text. Respond with 'en' for English or 'ru' for Russian."),
            ("user", f"Text to analyze:\n{feedback_text[:500]}\n\nAdditional presentation context:\n{(presentation_text or '')[:500]}\n\nPresentation path: {presentation_path}"),
        ])
        
        chain = prompt | self.llm.with_structured_output_retry(LanguageDetectionResult)
        try:
            result = await chain.ainvoke({})
            if result.pydantic and result.pydantic.language in ("en", "ru"):
                return result.pydantic.language
        except Exception as exc:
            logger.warning(f"Language detection failed, falling back to simple detection: {exc}")
        
        combined = (feedback_text or "") + " " + (presentation_text or "")
        cyrillic = sum(1 for c in combined if ord(c) >= 0x0400 and ord(c) <= 0x04FF)
        latin = sum(1 for c in combined if "a" <= c.lower() <= "z")
        if cyrillic > latin:
            return "ru"
        return "en"

    def _compute_hash(self, feedback_text: str, presentation_path: str) -> str:
        payload = f"{presentation_path}:{feedback_text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _is_duplicate(self, feedback_hash: str) -> bool:
        for path in sorted(self.feedback_log_dir.glob("feedback_*.jsonl")):
            try:
                with path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("feedback_hash") == feedback_hash:
                            return True
            except Exception:
                continue
        return False

    def _append_jsonl(self, path: Path, payload: dict) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _current_log_path(self) -> Path:
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return self.feedback_log_dir / f"feedback_{date_str}.jsonl"

    def _unmapped_path(self) -> Path:
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return self.unmapped_dir / f"unmapped_{date_str}.jsonl"

