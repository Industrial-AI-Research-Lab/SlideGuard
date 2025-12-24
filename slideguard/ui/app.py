"""
Gradio UI for SlideGuard - Interactive presentation evaluation interface.
"""
import logging
import os
import tempfile
import re
import io
from pathlib import Path
from html import escape
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple
import gradio as gr
from PIL import Image
import fitz  # PyMuPDF

from slideguard.criteria import get_registry_provider
from slideguard.schemes import Criteria, FullEvaluation, UIEvaluationResult
from slideguard.criteria.types import PresentationType, DEFAULT_PRESENTATION_TYPE
from slideguard.utils.config import load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.utils.cache_manager import CacheManager
from slideguard.utils.file_manager import FileManager
from slideguard.utils.config import load_langfuse_client
from slideguard.ui.report_generator import SlideGuardReportGenerator
from slideguard.ui.auth import verify_user_db, get_role, register_user, Role, list_users, update_user_password, update_user_role, delete_user
from slideguard.ui.translations import Translator

BILINGUAL_TABS = {
    "viewer": "🖼️ Viewer / Просмотр",
    "deck": "📋 Deck Results / Результаты",
    "admin": "🔒 Admin Panel / Панель администратора",
}

CRITERIA_LABELS: Dict[Criteria, Tuple[str, str]] = {
    Criteria.slide_visual_arrangement: ("Visual arrangement", "Визуальное оформление"),
    Criteria.slide_abbreviations: ("Abbreviations", "Проверка аббревиатур"),
    Criteria.slide_fact_link_availability: ("Fact link availability", "Корректность ссылок на источники"),
    Criteria.slide_graphic_content_match: ("Graphic and content match", "Соответствие графических материалов содержанию слайда"),
    Criteria.slide_orphography_correctness: ("Orphography correctness", "Качество орфографии"),
    Criteria.slide_title_content_match: ("Title content match", "Соответствие заголовка содержанию слайда"),
    Criteria.slide_title_slide_quality: ("Slide title quality", "Качество титульного слайда"),
    Criteria.slide_track_justification_scientific: ("Scientific track justification", "Обоснование выбора научного трека"),
    Criteria.slide_track_justification_collaborative: ("Collaborative track justification", "Обоснование выбора коллаборативного трека"),
    Criteria.slide_track_justification_industrial: ("Industrial track justification", "Обоснование выбора индустриального трека"),
    Criteria.slide_track_justification_technological: ("Technological track justification", "Обоснование выбора технологического трека"),
    Criteria.slide_related_works_review_scientific: ("Related works review", "Обзор существующих работ"),
    Criteria.slide_related_works_review_technological: ("Related works review", "Обзор существующих работ"),
    Criteria.slide_related_works_review_collaborative: ("Related works review", "Обзор существующих работ"),
    Criteria.slide_related_works_review_industrial: ("Related works review", "Обзор существующих работ"),
    Criteria.deck_storytelling: ("Storytelling quality", "Связность рассказа"),
    Criteria.deck_structure_analysis: ("Structure analysis", "Анализ структуры"),
    Criteria.deck_research_quality: ("Research quality", "Качество исследования"),
}

SERVICE_CRITERIA: Tuple[Criteria, ...] = (Criteria.slide_type, Criteria.slide_description)
PRESENTATION_TYPES = [p.value for p in PresentationType]


class SlideGuardUI:
    """Main UI class for SlideGuard application."""
    
    def __init__(self, use_langfuse: bool = False, eval_debug: bool = False):
        self.evaluator = None
        self.current_evaluation = None
        self.slide_images = []
        self.current_slide_index = 0
        self.temp_files = []  # Track temporary files for cleanup
        self.current_presentation_name = "Unknown"
        self.current_language = "en"
        self.current_presentation_type = DEFAULT_PRESENTATION_TYPE
        self.current_user = "Guest"
        self.translator = Translator(self.current_language)
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = load_config()
        self.langfuse_client = load_langfuse_client(use_langfuse)
        self.eval_debug = eval_debug
        
        # Initialize registry provider
        self.registry_provider = get_registry_provider()
        
        # Initialize evaluator and report generator
        self._initialize_evaluator()
        self.report_generator = SlideGuardReportGenerator(self.translator)
    
    def _initialize_evaluator(self):
        """Initialize the SlideGuard evaluator."""
        try:
            llm = create_llm_from_config(self.config)
            if llm is None:
                self.logger.error("Failed to initialize LLM. Please check your configuration.")
                return
            
            self.evaluator = SlideGuardEvaluator(
                file_manager=FileManager(self.config.file_cache_dir),
                cache_manager=CacheManager(self.config.evaluations_cache_dir),
                llm=llm,
                max_concurrency=self.config.max_concurrency,
                debug=self.eval_debug,
                registry_provider=self.registry_provider
            )
            self.logger.info("Evaluator initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize evaluator: {e}")
    
    def _clear_ui_state(self) -> Tuple[str, str, str, str]:
        msg = self.translator.t("processing")
        return (msg, "", "", msg)
    
    def _clear_slide_evaluation_display(self) -> str:
        """Clear slide evaluation display during processing."""
        if self.slide_images:
            return self.translator.t("processing")
        else:
            return self.translator.t("upload_prompt_slides")
    
    def _clear_slide_navigation_state(self, pdf_input) -> Tuple[str, Optional[str], str]:
        if not pdf_input:
            # Keep existing state if no PDF provided
            slide_idx = str(self.current_slide_index + 1) if self.slide_images else "1"
            current_image = self.slide_images[self.current_slide_index] if self.slide_images else None
            return (slide_idx, current_image, self.translator.t("upload_prompt"))
        
        self.current_presentation_name = Path(pdf_input.name).stem
        self.slide_images = self._extract_slide_images(pdf_input.name)
        self.current_slide_index = 0
        first_image = self.slide_images[0] if self.slide_images else None
        msg = self.translator.t("processing") if self.slide_images else self.translator.t("failed_extract")
        return ("1", first_image, msg)
    
    def _extract_slide_images(self, pdf_path: str) -> List[str]:
        """Extract slide images from PDF for display."""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Render page to image
                mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image and save to temp file
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                    img.save(tmp_file.name, "PNG")
                    images.append(tmp_file.name)
                    self.temp_files.append(tmp_file.name)
            
            doc.close()
            self.logger.info(f"Successfully extracted {len(images)} slide images")
            return images
        except Exception as e:
            self.logger.error(f"Failed to extract slide images: {e}")
            return []
    
    def _refresh_criteria_lists(self) -> None:
        """Refresh available criteria based on current presentation type."""
        registry = self.registry_provider.get_for_user()
        pt = PresentationType.from_string(self.current_presentation_type) if self.current_presentation_type else None
        slide_all = registry.get_slide_ids(include_service=True, presentation_type=pt)
        self._service_slide_criteria = [c for c in slide_all if c.is_service_criteria()]
        self._slide_criteria_list = [c for c in slide_all if not c.is_service_criteria()]
        self._deck_criteria_list = registry.get_deck_ids(presentation_type=pt)

    def _load_criteria(self, criteria_names: List[str], presentation_type: Optional[str]) -> Tuple[List[Criteria], List[Criteria]]:
        """Load slide and deck criteria based on input criteria list."""
        if criteria_names:
            criterias = [Criteria(c) for c in criteria_names]
            slide_criterias = [c for c in criterias if c.is_slide_criteria()]
            deck_criterias = [c for c in criterias if c.is_deck_criteria()]
        else:
            registry = self.registry_provider.get_for_user()
            pt = PresentationType.from_string(presentation_type) if presentation_type else None
            slide_criterias = registry.get_slide_ids(presentation_type=pt)
            deck_criterias = registry.get_deck_ids(presentation_type=pt)
        
        return slide_criterias, deck_criterias

    def _set_language(self, lang: str):
        """Set current language and update translator."""
        lang = lang if lang in ("en", "ru") else "en"
        self.current_language = lang
        self.translator.set_language(lang)
        # Update report generator with new translator language
        if hasattr(self, 'report_generator') and self.report_generator:
            self.report_generator.translator = self.translator
        try:
            if self.evaluator and self.evaluator.llm:
                self.evaluator.llm.set_language(lang)
        except Exception:
            self.logger.warning("Failed to set evaluator LLM language to %s", lang, exc_info=True)

    def _get_criteria_display_name(self, criteria: Criteria) -> str:
        labels = CRITERIA_LABELS.get(criteria)
        if labels:
            return labels[0] if self.current_language == "en" else labels[1]
        return criteria.value.replace("_", " ").title()

    def _get_criteria_choices(self, criteria_list: List[Criteria]) -> List[str]:
        return [self._get_criteria_display_name(c) for c in criteria_list]

    def _get_presentation_type_display(self, presentation_type: str) -> str:
        key = f"presentation_type_{presentation_type}"
        return self.translator.t(key)

    def _get_presentation_type_choices(self) -> List[str]:
        return [self._get_presentation_type_display(pt) for pt in PRESENTATION_TYPES]

    def _decode_presentation_type(self, selected: Optional[str]) -> Optional[str]:
        if not selected:
            return None
        mapping: Dict[str, str] = {}
        for pt in PRESENTATION_TYPES:
            mapping[pt] = pt
            mapping[self._get_presentation_type_display(pt)] = pt
        return mapping.get(selected)

    def _decode_criteria_selection(self, selected: Optional[List[str]], criteria_list: List[Criteria]) -> List[Criteria]:
        mapping: Dict[str, Criteria] = {}
        for crit in criteria_list:
            mapping[crit.value] = crit
            mapping[crit.name] = crit
            labels = CRITERIA_LABELS.get(crit)
            if labels:
                mapping[labels[0]] = crit
                mapping[labels[1]] = crit
            mapping[self._get_criteria_display_name(crit)] = crit
        decoded: List[Criteria] = []
        for item in selected or []:
            crit = mapping.get(item)
            if crit is None:
                try:
                    crit = Criteria(item)
                except Exception:
                    continue
            decoded.append(crit)
        return decoded

    def _get_ui_texts(self) -> Dict[str, Any]:
        """Return all language-dependent UI strings."""
        t = self.translator.t
        texts = {
            "lang_button": self.current_language.upper(),
            "title_md": f"# 🎯 {t('app_title')}",
            "description_md": t('app_description'),
            "upload_md": f"## {t('upload_section')}",
            "upload_label": t('upload_label'),
            "presentation_type_md": f"## {t('presentation_type_md')}",
            "presentation_type_label": t('presentation_type_label'),
            "presentation_type_scientific": t('presentation_type_scientific'),
            "presentation_type_industrial": t('presentation_type_industrial'),
            "presentation_type_collaborative": t('presentation_type_collaborative'),
            "presentation_type_technological": t('presentation_type_technological'),
            "criteria_md": f"## {t('criteria_section')}",
            "slide_criteria_label": t('slide_criteria_label'),
            "deck_criteria_label": t('deck_criteria_label'),
            "evaluate_btn": t('start_evaluation'),
            "results_md": f"## {t('results_section')}",
            "status_label": t('status_label'),
            "generate_report": t('generate_report'),
            "download_report": t('download_report'),
            "slide_nav_prev": t('previous_slide'),
            "slide_nav_next": t('next_slide'),
            "slide_number_label": t('current_slide_label'),
            "slide_image_label": t('slide_preview_label'),
            "slide_evaluation_placeholder": t('upload_prompt_slides'),
            "deck_results_placeholder": t('upload_prompt'),
            "admin_users_headers": [t('admin_username'), t('admin_role')],
            "refresh_btn": t('refresh'),
            "username_label": t('admin_username'),
            "password_label": t('admin_password'),
            "role_label": t('admin_role'),
            "register_btn": t('admin_register'),
            "register_status_label": t('admin_status'),
            "user_select_label": t('admin_select_user'),
            "new_role_label": t('admin_new_role'),
            "update_role_btn": t('admin_update_role'),
            "new_password_label": t('admin_new_password'),
            "update_password_btn": t('admin_update_password'),
            "delete_confirm_label": t('admin_confirm_delete'),
            "delete_btn": t('admin_delete_user'),
            "admin_action_status_label": t('admin_action_status'),
        }
        return texts

    def _language_updates(
        self,
        selected_slide: Optional[List[Criteria]] = None,
        selected_deck: Optional[List[Criteria]] = None,
    ) -> Tuple[Any, ...]:
        """Build component updates for the current language."""
        texts = self._get_ui_texts()
        is_admin = (
            self.current_user != "Guest" and get_role(self.current_user) == Role.ADMIN
        )

        slide_selected = selected_slide or getattr(self, "_selected_slide_criteria", self._slide_criteria_list)
        deck_selected = selected_deck or getattr(self, "_selected_deck_criteria", self._deck_criteria_list)

        slide_selected = [c for c in slide_selected if c in self._slide_criteria_list]
        deck_selected = [c for c in deck_selected if c in self._deck_criteria_list]

        if not slide_selected:
            slide_selected = self._slide_criteria_list
        if not deck_selected:
            deck_selected = self._deck_criteria_list

        self._selected_slide_criteria = slide_selected
        self._selected_deck_criteria = deck_selected

        slide_choices = self._get_criteria_choices(self._slide_criteria_list)
        deck_choices = self._get_criteria_choices(self._deck_criteria_list)
        presentation_choices = self._get_presentation_type_choices()
        presentation_selected = self._get_presentation_type_display(self.current_presentation_type)

        slide_selected_display = [self._get_criteria_display_name(c) for c in slide_selected if c in self._slide_criteria_list]
        deck_selected_display = [self._get_criteria_display_name(c) for c in deck_selected if c in self._deck_criteria_list]

        slide_update = gr.update()
        deck_update = gr.update()
        if not self.current_evaluation:
            slide_update = gr.update(value=texts["slide_evaluation_placeholder"])
            deck_update = gr.update(value=texts["deck_results_placeholder"])

        updates = (
            self.render_profile_widget(self.current_user),
            gr.update(visible=is_admin),
            gr.update(value=texts["lang_button"]),
            texts["title_md"],
            texts["description_md"],
            texts["upload_md"],
            gr.update(label=texts["upload_label"]),
            texts["presentation_type_md"],
            gr.update(
                label=texts["presentation_type_label"],
                choices=[
                    (texts["presentation_type_scientific"], PresentationType.SCIENTIFIC.value),
                    (texts["presentation_type_industrial"], PresentationType.INDUSTRIAL.value),
                    (texts["presentation_type_collaborative"], PresentationType.COLLABORATIVE.value),
                    (texts["presentation_type_technological"], PresentationType.TECHNOLOGICAL.value),
                ],
            ),
            texts["criteria_md"],
            gr.update(label=texts["presentation_type_label"], choices=presentation_choices, value=presentation_selected),
            gr.update(label=texts["slide_criteria_label"], choices=slide_choices, value=slide_selected_display),
            gr.update(label=texts["deck_criteria_label"], choices=deck_choices, value=deck_selected_display),
            gr.update(value=texts["evaluate_btn"]),
            texts["results_md"],
            gr.update(label=texts["status_label"]),
            gr.update(value=texts["generate_report"]),
            gr.update(label=texts["download_report"]),
            gr.update(value=texts["slide_nav_prev"]),
            gr.update(label=texts["slide_number_label"]),
            gr.update(value=texts["slide_nav_next"]),
            gr.update(label=texts["slide_image_label"]),
            slide_update,
            deck_update,
            gr.update(headers=texts["admin_users_headers"]),
            gr.update(value=texts["refresh_btn"]),
            gr.update(label=texts["username_label"]),
            gr.update(label=texts["password_label"]),
            gr.update(label=texts["role_label"]),
            gr.update(value=texts["register_btn"]),
            gr.update(label=texts["register_status_label"]),
            gr.update(label=texts["user_select_label"]),
            gr.update(label=texts["new_role_label"]),
            gr.update(value=texts["update_role_btn"]),
            gr.update(label=texts["new_password_label"]),
            gr.update(value=texts["update_password_btn"]),
            gr.update(label=texts["delete_confirm_label"]),
            gr.update(value=texts["delete_btn"]),
            gr.update(label=texts["admin_action_status_label"]),
        )
        return updates
    
    async def evaluate_presentation(self, pdf_file, slide_selected, deck_selected, presentation_type_value: Optional[str] = None, user_id: Optional[str] = None) -> UIEvaluationResult:
        """Evaluate a presentation and return results."""
        if not pdf_file:
            return UIEvaluationResult.error(self.translator.t("no_pdf"))
        
        if not presentation_type_value:
            return UIEvaluationResult.error(self.translator.t("presentation_type_required"))
        
        if not self.evaluator:
            return UIEvaluationResult.error(self.translator.t("evaluator_not_initialized"))
        
        try:
            self.current_evaluation = None
            
            # Parse presentation type
            presentation_type = PresentationType.from_string(presentation_type_value)
            if not presentation_type:
                return UIEvaluationResult.error(self.translator.t("invalid_presentation_type"))
            
            # Load criteria
            slide_selected_list = self._decode_criteria_selection(slide_selected, self._slide_criteria_list + self._service_slide_criteria)
            deck_selected_list = self._decode_criteria_selection(deck_selected, self._deck_criteria_list)

            service_needed: List[Criteria] = [
                serv for serv in self._service_slide_criteria if serv not in slide_selected_list
            ]

            self._selected_slide_criteria = slide_selected_list
            self._selected_deck_criteria = deck_selected_list

            selected_values = [c.value for c in slide_selected_list + service_needed + deck_selected_list]
            slide_criterias, deck_criterias = self._load_criteria(selected_values, self.current_presentation_type)
	    
            # Get registry for user
            registry = self.registry_provider.get_for_user(user_id)	            
            
            # Run evaluation
            self.logger.info(f"Starting evaluation with {len(slide_criterias)} slide criteria and {len(deck_criterias)} deck criteria for presentation type {presentation_type.value}")
            
            evaluation = await self.evaluator.evaluate_presentation(
                presentation_path=pdf_file.name,
                slide_criterias=slide_criterias,
                deck_criterias=deck_criterias,
                langfuse_client=self.langfuse_client,
                registry=registry,
                user_id=user_id,
                presentation_type=presentation_type
            )
            
            self.current_evaluation = evaluation
            self.current_slide_index = 0
            
            # Format results
            deck_summary = self._format_deck_results(evaluation)
            tldr_text = evaluation.tldr or ""
            tldr_html = (
                f"<div style='background-color: #fffde7; padding: 8px; border-radius: 8px; margin: 4px 0 4px 0; border-left: 4px solid #fbc02d; color: #333333;'>"
                f"<h3 style='color: #333333; margin-top: 0; margin-bottom: 4px;'><strong>{self.translator.t('tldr')}</strong></h3>"
                f"<p style='color: #333333; margin: 4px 0;'>{escape(tldr_text)}</p>"
                f"</div>"
            ) if tldr_text else ""

            score_html = ""
            if evaluation.overall_score is not None:
                s = evaluation.overall_score
                if s >= 4:
                    icon, bg, brd, col = "🟢", "#e8f5e8", "#4caf50", "#2e7d32"
                elif s >= 3:
                    icon, bg, brd, col = "🟡", "#fffde7", "#fbc02d", "#8d6e63"
                elif s >= 2:
                    icon, bg, brd, col = "🟠", "#fff3e0", "#ff9800", "#e65100"
                else:
                    icon, bg, brd, col = "🔴", "#ffebee", "#f44336", "#b71c1c"
                score_html = (
                    f"<div style='margin: 2px 0 2px 0;'>"
                    f"<span style='display:inline-block;padding:5px 10px;border-radius:14px;background:{bg};border:1px solid {brd};color:{col};font-weight:600;'>"
                    f"{icon} {self.translator.t('overall_score_label')} {s}/5"
                    f"</span>"
                    f"</div>"
                )
            
            # Return the first slide image if available, otherwise None
            first_slide_image = self.slide_images[0] if self.slide_images else None
            status_msg = self.translator.t("evaluation_success", slides=len(self.slide_images), slide_criteria=len(slide_criterias), deck_criteria=len(deck_criterias))
            return UIEvaluationResult(deck_summary=deck_summary, first_slide_image=first_slide_image, tldr_html=tldr_html, score_html=score_html, status_msg=status_msg)
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}")
            return UIEvaluationResult.error(self.translator.t("evaluation_failed", error=str(e)))
    
    def _format_deck_results(self, evaluation: FullEvaluation) -> str:
        """Format deck-level evaluation results."""
        if not evaluation or not evaluation.deck_evaluations:
            return self.translator.t("no_deck_evaluations")
        
        result = f"<h2 style='color: #333333;'>{self.translator.t('deck_results_title')}</h2>\n\n"
        
        for criteria, eval_result in evaluation.deck_evaluations.evaluations.items():
            criteria_name = self._get_criteria_display_name(criteria)
            result += "<div style='background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #2196f3; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'>🎯 {criteria_name}</h3>\n"
            
            # Handle both Pydantic objects and dictionaries
            if hasattr(eval_result, 'evaluation_results'):
                # Handle Pydantic objects with evaluation_results (like SlideTitleContentMatch)
                result += self._format_structured_evaluation(eval_result.evaluation_results)
                if hasattr(eval_result, 'score'):
                    score = eval_result.score
                    score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                    
                    # Score indicator
                    if score_percentage >= 80:
                        score_icon = "🟢"
                        score_text = self.translator.t("excellent")
                        score_color = "#4caf50"
                    elif score_percentage >= 60:
                        score_icon = "🟡"
                        score_text = self.translator.t("good")
                        score_color = "#ff9800"
                    elif score_percentage >= 40:
                        score_icon = "🟠"
                        score_text = self.translator.t("fair")
                        score_color = "#ff9800"
                    else:
                        score_icon = "🔴"
                        score_text = self.translator.t("needs_improvement")
                        score_color = "#f44336"
                    
                    result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid {score_color}; color: #333333;'>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('score_label')} {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('assessment_label')}</strong> {score_text}</p>\n"
                    result += "</div>\n"
            elif isinstance(eval_result, dict):
                # Handle dictionary format
                if 'evaluation_results' in eval_result:
                    result += self._format_structured_evaluation(eval_result['evaluation_results'])
                elif 'score' in eval_result:
                    score = eval_result['score']
                    score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                    
                    # Score indicator
                    if score_percentage >= 80:
                        score_icon = "🟢"
                        score_text = self.translator.t("excellent")
                        score_color = "#4caf50"
                    elif score_percentage >= 60:
                        score_icon = "🟡"
                        score_text = self.translator.t("good")
                        score_color = "#ff9800"
                    elif score_percentage >= 40:
                        score_icon = "🟠"
                        score_text = self.translator.t("fair")
                        score_color = "#ff9800"
                    else:
                        score_icon = "🔴"
                        score_text = self.translator.t("needs_improvement")
                        score_color = "#f44336"
                    
                    result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid {score_color}; color: #333333;'>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('score_label')} {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('assessment_label')}</strong> {score_text}</p>\n"
                    
                    if 'comments' in eval_result:
                        result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('comments')}</strong><br>{eval_result['comments']}</p>\n"
                    if 'recommendations' in eval_result:
                        result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('recommendations')}</strong><br>{eval_result['recommendations']}</p>\n"
                    result += "</div>\n"
                else:
                    result += "<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                    result += f"{eval_result}\n"
                    result += "</div>\n"
            else:
                # Fallback for other formats
                result += "<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                result += f"{eval_result}\n"
                result += "</div>\n"
            
            result += "</div>\n\n"
        
        if evaluation.overall_score:
            overall_percentage = (evaluation.overall_score / 5.0) * 100
            if overall_percentage >= 80:
                overall_icon = "🟢"
                overall_text = self.translator.t("excellent")
            elif overall_percentage >= 60:
                overall_icon = "🟡"
                overall_text = self.translator.t("good")
            elif overall_percentage >= 40:
                overall_icon = "🟠"
                overall_text = self.translator.t("fair")
            else:
                overall_icon = "🔴"
                overall_text = self.translator.t("needs_improvement")
            
            result += "<div style='background-color: #e3f2fd; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #2196f3; color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'><strong>{self.translator.t('overall_score_label')} {overall_icon} {evaluation.overall_score:.2f}/5.0 ({overall_percentage:.0f}%)</strong></h3>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('overall_assessment')}</strong> {overall_text}</p>\n"
            result += "</div>\n\n"
        
        if evaluation.summary:
            result += "<div style='background-color: #f3e5f5; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #9c27b0; color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'><strong>{self.translator.t('summary')}</strong></h3>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'>{evaluation.summary}</p>\n"
            result += "</div>\n\n"
        
        return result
    
    def _format_slide_results(self, evaluation: FullEvaluation) -> str:
        """Format slide-level evaluation results."""
        if not evaluation or not evaluation.slide_evaluations:
            return self.translator.t("no_slide_evaluations")
        
        result = f"<h2 style='color: #333333;'>{self.translator.t('slide_results_title')}</h2>\n\n"
        
        for slide_eval in evaluation.slide_evaluations:
            result += f"<h3 style='color: #333333;'>📊 Slide {slide_eval.slide_id + 1}</h3>\n"
            
            if slide_eval.evaluations:
                for criteria, eval_result in slide_eval.evaluations.items():
                    result += f"<h4 style='color: #333333;'>🎯 {self._get_criteria_display_name(criteria)}</h4>\n"
                    # Handle both Pydantic objects and dictionaries
                    if hasattr(eval_result, 'evaluation_results'):
                        # Handle Pydantic objects with evaluation_results (like SlideTitleContentMatch)
                        result += self._format_structured_evaluation(eval_result.evaluation_results)
                        if hasattr(eval_result, 'score'):
                            result += f"<p style='color: #333333;'><strong>Score:</strong> {eval_result.score}</p>\n\n"
                    elif isinstance(eval_result, dict):
                        # Handle dictionary format
                        if 'evaluation_results' in eval_result:
                            result += self._format_structured_evaluation(eval_result['evaluation_results'])
                        elif 'score' in eval_result:
                            result += f"<p style='color: #333333;'><strong>Score:</strong> {eval_result['score']}</p>\n\n"
                            if 'comments' in eval_result:
                                result += f"<p style='color: #333333;'><strong>Comments:</strong> {eval_result['comments']}</p>\n\n"
                            if 'recommendations' in eval_result:
                                result += f"<p style='color: #333333;'><strong>Recommendations:</strong> {eval_result['recommendations']}</p>\n\n"
                        else:
                            result += f"{eval_result}\n\n"
                    else:
                        result += f"{eval_result}\n\n"
            
            result += "<hr/>\n\n"
        
        return result
    
    def get_slide_evaluation(self, slide_index: int) -> str:
        """Get evaluation results for a specific slide."""
        if not self.current_evaluation or not self.current_evaluation.slide_evaluations:
            return self.translator.t("upload_prompt_slides")
        
        if slide_index < 0:
            return self.translator.t("upload_prompt_slides")
        
        if slide_index >= len(self.current_evaluation.slide_evaluations):
            return self.translator.t("upload_prompt_slides")
        
        slide_eval = self.current_evaluation.slide_evaluations[slide_index]
        result = f"<h2 style='color: #333333;'>{self.translator.t('slide_evaluation_title', number=slide_index + 1)}</h2>\n\n"
        
        if slide_eval.evaluations:
            for criteria, eval_result in slide_eval.evaluations.items():
                criteria_name = self._get_criteria_display_name(criteria)
                result += "<div style='background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #2196f3; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>\n"
                result += f"<h3 style='color: #333333; margin-top: 0;'>🎯 {criteria_name}</h3>\n"
                
                # Handle both Pydantic objects and dictionaries
                if hasattr(eval_result, 'evaluation_results'):
                    # Handle Pydantic objects with evaluation_results (like SlideTitleContentMatch)
                    result += self._format_structured_evaluation(eval_result.evaluation_results)
                    if hasattr(eval_result, 'score'):
                        score = eval_result.score
                        score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                        
                        # Score indicator
                        if score_percentage >= 80:
                            score_icon = "🟢"
                            score_text = self.translator.t("excellent")
                        elif score_percentage >= 60:
                            score_icon = "🟡"
                            score_text = self.translator.t("good")
                        elif score_percentage >= 40:
                            score_icon = "🟠"
                            score_text = self.translator.t("fair")
                        else:
                            score_icon = "🔴"
                            score_text = self.translator.t("needs_improvement")
                        
                        result += "<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                        result += f"<p><strong>{self.translator.t('score_label')} {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                        result += f"<p><strong>{self.translator.t('assessment_label')}</strong> {score_text}</p>\n"
                        result += "</div>\n"
                elif isinstance(eval_result, dict):
                    # Handle dictionary format
                    if 'evaluation_results' in eval_result:
                        result += self._format_structured_evaluation(eval_result['evaluation_results'])
                    elif 'score' in eval_result:
                        score = eval_result['score']
                        score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                        
                        # Score indicator
                        if score_percentage >= 80:
                            score_icon = "🟢"
                            score_text = self.translator.t("excellent")
                        elif score_percentage >= 60:
                            score_icon = "🟡"
                            score_text = self.translator.t("good")
                        elif score_percentage >= 40:
                            score_icon = "🟠"
                            score_text = self.translator.t("fair")
                        else:
                            score_icon = "🔴"
                            score_text = self.translator.t("needs_improvement")
                        
                        result += "<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                        result += f"<p><strong>{self.translator.t('score_label')} {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                        result += f"<p><strong>{self.translator.t('assessment_label')}</strong> {score_text}</p>\n"
                        
                        if 'comments' in eval_result:
                            result += f"<p><strong>{self.translator.t('comments')}</strong><br>{eval_result['comments']}</p>\n"
                        if 'recommendations' in eval_result:
                            result += f"<p><strong>{self.translator.t('recommendations')}</strong><br>{eval_result['recommendations']}</p>\n"
                        result += "</div>\n"
                    else:
                        result += "<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                        result += f"{eval_result}\n"
                        result += "</div>\n"
                else:
                    # Fallback for other formats
                    result += "<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                    result += f"{eval_result}\n"
                    result += "</div>\n"
                
                result += "</div>\n\n"
        else:
            result += "<div style='background-color: #fff3e0; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #ff9800; color: #333333;'>\n"
            result += f"<p style='color: #333333;'><strong>{self.translator.t('no_slide_evaluation_single')}</strong></p>\n"
            result += "</div>\n\n"
        
        return result
    
    def _format_structured_evaluation(self, evaluation_results) -> str:
        """Format structured evaluation results with severity indicators."""
        if not evaluation_results:
            return self.translator.t("no_detailed_results")
        
        result = ""
        total_severity = 0
        
        # Handle both list of dicts and list of Pydantic objects
        if hasattr(evaluation_results, '__iter__') and not isinstance(evaluation_results, str):
            items = list(evaluation_results)
        else:
            return f"Unexpected evaluation results format: {type(evaluation_results)}\n\n"
        
        for i, eval_item in enumerate(items, 1):
            # Handle both dict and Pydantic object
            if hasattr(eval_item, 'severity') and hasattr(eval_item, 'evaluation_element'):
                # Handle Pydantic objects with severity (most criteria results)
                severity = eval_item.severity
                element = eval_item.evaluation_element
                suggestion = eval_item.evaluation_suggestion
            elif hasattr(eval_item, 'evaluation_element'):
                # Handle Pydantic objects without severity (fallback)
                severity = 1  # Default to low priority for items without explicit severity
                element = eval_item.evaluation_element
                suggestion = eval_item.evaluation_suggestion
            elif isinstance(eval_item, dict):
                severity = eval_item.get('severity', 1)
                element = eval_item.get('evaluation_element', 'Unknown Element')
                suggestion = eval_item.get('evaluation_suggestion', 'No suggestion provided')
            else:
                # Fallback for unexpected format - try to extract useful information
                try:
                    # Try to convert to string and extract meaningful parts
                    item_str = str(eval_item)
                    if "evaluation_element" in item_str and "evaluation_suggestion" in item_str:
                        # Try to parse the string representation
                        import re
                        element_match = re.search(r"evaluation_element='([^']*)'", item_str)
                        suggestion_match = re.search(r"evaluation_suggestion='([^']*)'", item_str)
                        severity_match = re.search(r"severity=(\d+)", item_str)
                        
                        element = element_match.group(1) if element_match else "Analysis completed"
                        suggestion = suggestion_match.group(1) if suggestion_match else "No specific suggestion"
                        severity = int(severity_match.group(1)) if severity_match else 1
                    else:
                        # Fallback for completely unexpected format
                        result += "<div style='background-color: #f5f5f5; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #666;'>\n"
                        result += "### ⚠️ **Unexpected Result Format**\n"
                        result += f"**Raw Data:** {str(eval_item)[:200]}...\n"
                        result += "</div>\n\n"
                        continue
                except Exception as e:
                    # Final fallback
                    result += "<div style='background-color: #f5f5f5; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #666;'>\n"
                    result += "### ⚠️ **Error Processing Result**\n"
                    result += f"**Error:** {str(e)}\n"
                    result += f"**Raw Data:** {str(eval_item)[:200]}...\n"
                    result += "</div>\n\n"
                    continue
            
            # Update max severity and score
            total_severity += severity
            
            # Severity indicator with better styling and dark theme compatibility
            if severity == 1:
                severity_icon = "🟢"
                severity_text = self.translator.t("low_priority")
                bg_color = "#e8f5e8"
                border_color = "#4caf50"
            elif severity == 2:
                severity_icon = "🟡"
                severity_text = self.translator.t("medium_priority")
                bg_color = "#fff3e0"
                border_color = "#ff9800"
            elif severity == 3:
                severity_icon = "🔴"
                severity_text = self.translator.t("high_priority")
                bg_color = "#ffebee"
                border_color = "#f44336"
            else:
                severity_icon = "⚪"
                severity_text = self.translator.t("info")
                bg_color = "#f5f5f5"
                border_color = "#9e9e9e"
            
            result += f"<div style='background-color: {bg_color}; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid {border_color}; color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'>{severity_icon} <strong>{self.translator.t('analysis')}</strong></h3>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('priority_label')}</strong> {severity_text} ({self.translator.t('severity_label')} {severity}/3)</p>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('evaluation_label')}</strong> {element}</p>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('suggestion_label')}</strong> {suggestion}</p>\n"
            result += "</div>\n\n"
        
        severity_score = total_severity / len(items) if items else 0
        severity_percentage = (severity_score / 3.0) * 100

        if severity_percentage >= 80:
            score_icon = "🔴"
            score_text = self.translator.t("needs_improvement")
            score_color = "#f44336"
        elif severity_percentage >= 60:
            score_icon = "🟠"
            score_text = self.translator.t("fair")
            score_color = "#ff9800"
        elif severity_percentage >= 40:
            score_icon = "🟡"
            score_text = self.translator.t("good")
            score_color = "#ffeb3b"
        else:
            score_icon = "🟢"
            score_text = self.translator.t("excellent")
            score_color = "#4caf50"

        result += f"<div style='background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid {score_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: #333333;'>\n"
        result += f"<h3 style='color: #333333; margin-top: 0;'><strong>{self.translator.t('total_severity')} {score_icon} {severity_score:.1f}/3.0 ({severity_percentage:.0f}%)</strong></h3>\n"
        result += f"<p style='color: #333333; margin: 8px 0;'><strong>{self.translator.t('overall_assessment')}</strong> {score_text}</p>\n"
        result += "</div>\n\n"
        
        return result
    
    def cleanup_temp_files(self):
        """Clean up temporary image files."""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    self.logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
        self.temp_files.clear()
    
    def generate_pdf_report(self) -> Tuple[Optional[str], str]:
        """Generate a PDF report for the current evaluation."""
        if not self.current_evaluation:
            return None, self.translator.t("no_evaluation")
        
        try:
            base = self.current_presentation_name or "presentation"
            # sanitize filename for Windows
            safe = re.sub(r'[<>:"/\\|?*]+', '_', base).strip() or "presentation"
            filename = f"{safe}_report.pdf"
            temp_dir = tempfile.gettempdir()
            pdf_path = os.path.join(temp_dir, filename)
            if os.path.exists(pdf_path):
                pdf_path = os.path.join(temp_dir, f"{safe}_report.pdf")
            
            # Generate the report
            self.report_generator.save_report(
                evaluation=self.current_evaluation,
                output_path=pdf_path,
                presentation_name=self.current_presentation_name,
                slide_images=self.slide_images
            )
            
            # Add to temp files for cleanup
            self.temp_files.append(pdf_path)
            return pdf_path, self.translator.t("report_success")
            
        except Exception as e:
            return None, self.translator.t("report_failed", error=str(e))

    def render_profile_widget(self, username: str) -> str:
        u = username or "Guest"
        initial = (u[:1] or "?").upper()
        safe_name = escape(u)
        logout_text = self.translator.t("logout")
        html = dedent("""
                <div id='sgProfileContainer' style='position:fixed;top:12px;right:12px;z-index:2147483647;'>
                <div id='sgProfileIcon' style='width:36px;height:36px;border-radius:50%;background:#1f6feb;color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:600;' onclick="event.stopPropagation();var d=document.getElementById('sgProfileDropdown');if(d){d.style.display=(d.style.display==='block')?'none':'block';}">__INITIAL__</div>
                <div id='sgProfileDropdown' style='display:none;position:absolute;right:0;top:44px;background:#fff;border:1px solid #e0e0e0;border-radius:8px;min-width:200px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:2147483647;max-height:none;overflow:visible;'>
                    <div style='padding:12px 16px;font-weight:600;border-bottom:1px solid #eee;' id='sgProfileName'>__SAFE_NAME__</div>
                    <a href='/logout' id='sgLogoutLink' style='padding:10px 16px;display:block;text-decoration:none;color:#333;' onclick="(function(){var p=new URLSearchParams(window.location.search);var t=p.get('__theme')||localStorage.getItem('sg_theme')||'';if(t){localStorage.setItem('sg_theme',t);}fetch('/logout',{method:'GET',credentials:'include'}).finally(function(){window.top.location.href='/?__theme='+encodeURIComponent(t);});return false;})()">__LOGOUT_TEXT__</a>
                </div>
                </div>""")
        return html.replace("__INITIAL__", initial).replace("__SAFE_NAME__", safe_name).replace("__LOGOUT_TEXT__", logout_text)
    
    def create_ui(self):
        """Create the Gradio interface."""
        self._set_language(self.current_language)
        texts = self._get_ui_texts()

        # Available criteria (exclude internal helper criteria)
        self._refresh_criteria_lists()
        self._selected_slide_criteria = self._slide_criteria_list.copy()
        self._selected_deck_criteria = self._deck_criteria_list.copy()
        slide_choices_display = self._get_criteria_choices(self._slide_criteria_list)
        deck_choices_display = self._get_criteria_choices(self._deck_criteria_list)
        presentation_type_choices = self._get_presentation_type_choices()
        presentation_type_display = self._get_presentation_type_display(self.current_presentation_type)

        with gr.Blocks(
            title="SlideGuard - Presentation Evaluation",
            theme=gr.themes.Default(),
            css="""
            #sgLangButton {
                position: fixed;
                top: 12px;
                right: 60px;
                z-index: 2147483646;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 2px 9px;
                border-radius: 14px;
                font-size: 11px;
                line-height: 1.1;
                min-height: 24px;
                min-width: 42px;
                width: auto !important;
                max-width: fit-content;
                background-color: #1f6feb;
                color: #ffffff;
                border: 1px solid #1f6feb;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
                cursor: pointer;
            }
            #sgLangButton:hover {
                background-color: #1554b0;
                border-color: #1554b0;
            }
            #sgLangButton:focus-visible {
                outline: 2px solid rgba(21, 84, 176, 0.6);
                outline-offset: 2px;
            }
            """,
        ) as interface:
            title_md = gr.Markdown(texts["title_md"])
            description_md = gr.Markdown(texts["description_md"])
            gr.Markdown("---")
            lang_button = gr.Button(value=texts["lang_button"], elem_id="sgLangButton")
            lang_state = gr.State(self.current_language)
            profile_html = gr.HTML(value="")

            with gr.Row():
                with gr.Column(scale=1):
                    upload_md = gr.Markdown(texts["upload_md"])
                    pdf_input = gr.File(
                        label=texts["upload_label"],
                        file_types=[".pdf"],
                        type="filepath",
                        height=100,
                    )

                    presentation_type_md = gr.Markdown(texts["presentation_type_md"])
                    presentation_type_dropdown = gr.Dropdown(
                        choices=[
                            (texts["presentation_type_scientific"], PresentationType.SCIENTIFIC.value),
                            (texts["presentation_type_industrial"], PresentationType.INDUSTRIAL.value),
                            (texts["presentation_type_collaborative"], PresentationType.COLLABORATIVE.value),
                            (texts["presentation_type_technological"], PresentationType.TECHNOLOGICAL.value),
                        ],
                        label=texts["presentation_type_label"],
                        value=None,
                        interactive=True,
                        allow_custom_value=False,
                    )

                    criteria_md = gr.Markdown(texts["criteria_md"])
                    presentation_type_input = gr.Dropdown(
                        choices=presentation_type_choices,
                        value=presentation_type_display,
                        label=texts["presentation_type_label"],
                        interactive=True,
                    )
                    slide_criteria_input = gr.CheckboxGroup(
                        choices=slide_choices_display,
                        label=texts["slide_criteria_label"],
                        value=slide_choices_display,
                        interactive=True,
                    )
                    deck_criteria_input = gr.CheckboxGroup(
                        choices=deck_choices_display,
                        label=texts["deck_criteria_label"],
                        value=deck_choices_display,
                        interactive=True,
                    )

                    evaluate_btn = gr.Button(
                        texts["evaluate_btn"],
                        variant="primary",
                        scale=1,
                    )

                with gr.Column(scale=2):
                    results_md = gr.Markdown(texts["results_md"])

                    status_output = gr.Textbox(
                        label=texts["status_label"],
                        interactive=False,
                        lines=2,
                        max_lines=5,
                    )
                    tldr_output = gr.HTML("")
                    overall_score_output = gr.HTML("")
                    result_state = gr.State()

                    with gr.Row():
                        generate_report_btn = gr.Button(
                            texts["generate_report"],
                            variant="secondary",
                            scale=1,
                        )
                        download_report_btn = gr.File(
                            label=texts["download_report"],
                            visible=False,
                            scale=1,
                        )

                    with gr.Tabs():
                        with gr.TabItem(BILINGUAL_TABS["viewer"]):
                            with gr.Row():
                                with gr.Column(scale=1):
                                    slide_nav_btn = gr.Button(texts["slide_nav_prev"], scale=1)
                                    slide_number = gr.Textbox(
                                        label=texts["slide_number_label"],
                                        value="1",
                                        interactive=False,
                                    )
                                    slide_nav_btn_next = gr.Button(texts["slide_nav_next"], scale=1)

                                with gr.Column(scale=3):
                                    slide_image = gr.Image(
                                        label=texts["slide_image_label"],
                                        interactive=False,
                                        height=400,
                                    )

                            slide_evaluation = gr.HTML(texts["slide_evaluation_placeholder"])

                        with gr.TabItem(BILINGUAL_TABS["deck"]):
                            deck_results = gr.HTML(texts["deck_results_placeholder"])

                        with gr.TabItem(BILINGUAL_TABS["admin"], visible=False) as admin_tab:
                            admin_panel = gr.Group()
                            with admin_panel:
                                with gr.Tabs():
                                    with gr.TabItem("👥 Users / Пользователи"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                users_table = gr.Dataframe(
                                                    headers=texts["admin_users_headers"],
                                                    interactive=False,
                                                )
                                                with gr.Row():
                                                    refresh_users_btn = gr.Button(
                                                        value=texts["refresh_btn"],
                                                        variant="secondary",
                                                    )
                                    with gr.TabItem("➕ Create / Создать"):
                                        with gr.Column():
                                            username_input = gr.Textbox(label=texts["username_label"])
                                            password_input = gr.Textbox(
                                                label=texts["password_label"],
                                                type="password",
                                            )
                                            role_input = gr.Dropdown(
                                                choices=[r.value for r in Role],
                                                label=texts["role_label"],
                                            )
                                            register_btn = gr.Button(
                                                value=texts["register_btn"],
                                                variant="primary",
                                            )
                                            register_status = gr.Textbox(
                                                label=texts["register_status_label"],
                                                interactive=False,
                                            )
                                    with gr.TabItem("🛠 Manage / Управление"):
                                        with gr.Column():
                                            user_select = gr.Dropdown(
                                                choices=[],
                                                label=texts["user_select_label"],
                                            )
                                            new_role_input = gr.Dropdown(
                                                choices=[r.value for r in Role],
                                                label=texts["new_role_label"],
                                            )
                                            update_role_btn = gr.Button(
                                                value=texts["update_role_btn"],
                                                variant="primary",
                                            )
                                            new_password_input = gr.Textbox(
                                                label=texts["new_password_label"],
                                                type="password",
                                            )
                                            update_password_btn = gr.Button(
                                                value=texts["update_password_btn"],
                                                variant="primary",
                                            )
                                            delete_confirm = gr.Checkbox(
                                                label=texts["delete_confirm_label"]
                                            )
                                            delete_btn = gr.Button(
                                                value=texts["delete_btn"],
                                                variant="stop",
                                            )
                                            admin_action_status = gr.Textbox(
                                                label=texts["admin_action_status_label"],
                                                interactive=False,
                                            )

                            def on_load(req: gr.Request):
                                lang = (
                                    req.query_params.get("lang", self.current_language)
                                    if req
                                    else self.current_language
                                )
                                if lang not in ("en", "ru"):
                                    lang = "en"
                                self._set_language(lang)
                                self.current_user = req.username if req and req.username else "Guest"
                                updates = self._language_updates()
                                return (*updates, lang)

                            def toggle_language(current_lang: str, slide_selected_values: List[str], deck_selected_values: List[str]):
                                lang = current_lang if current_lang in ("en", "ru") else "en"
                                new_lang = "ru" if lang == "en" else "en"
                                self._set_language(new_lang)
                                slide_selected_criteria = self._decode_criteria_selection(slide_selected_values, self._slide_criteria_list)
                                deck_selected_criteria = self._decode_criteria_selection(deck_selected_values, self._deck_criteria_list)
                                updates = self._language_updates(slide_selected_criteria, deck_selected_criteria)
                                return (*updates, new_lang)

                            def on_presentation_type_change(selected_label, slide_selected_values: List[str], deck_selected_values: List[str]):
                                new_pt = self._decode_presentation_type(selected_label) or self.current_presentation_type
                                
                                # Decode current selections BEFORE refreshing criteria lists
                                old_slide_selected = self._decode_criteria_selection(slide_selected_values, self._slide_criteria_list)
                                
                                # Check which presentation-type-specific criteria were selected
                                had_track_justification = any(
                                    "track_justification" in c.value for c in old_slide_selected
                                )
                                had_related_works = any(
                                    "related_works_review" in c.value for c in old_slide_selected
                                )
                                
                                # Now update presentation type and refresh criteria lists
                                self.current_presentation_type = new_pt
                                self._refresh_criteria_lists()
                                
                                # Decode selections against NEW criteria list (keeps criteria that exist in both)
                                slide_selected_criteria = self._decode_criteria_selection(slide_selected_values, self._slide_criteria_list)
                                deck_selected_criteria = self._decode_criteria_selection(deck_selected_values, self._deck_criteria_list)

                                # Auto-select presentation-type-specific criteria if they were selected before
                                if had_track_justification:
                                    track_justification_criteria = [
                                        c for c in self._slide_criteria_list 
                                        if "track_justification" in c.value and new_pt in c.value
                                    ]
                                    for crit in track_justification_criteria:
                                        if crit not in slide_selected_criteria:
                                            slide_selected_criteria.append(crit)
                                
                                if had_related_works:
                                    related_works_criteria = [
                                        c for c in self._slide_criteria_list 
                                        if "related_works_review" in c.value and new_pt in c.value
                                    ]
                                    for crit in related_works_criteria:
                                        if crit not in slide_selected_criteria:
                                            slide_selected_criteria.append(crit)

                                # If no criteria selected, select all by default
                                if not slide_selected_criteria:
                                    slide_selected_criteria = self._slide_criteria_list.copy()
                                if not deck_selected_criteria:
                                    deck_selected_criteria = self._deck_criteria_list.copy()

                                self._selected_slide_criteria = slide_selected_criteria
                                self._selected_deck_criteria = deck_selected_criteria

                                slide_choices = self._get_criteria_choices(self._slide_criteria_list)
                                deck_choices = self._get_criteria_choices(self._deck_criteria_list)

                                return (
                                    gr.update(choices=slide_choices, value=[self._get_criteria_display_name(c) for c in slide_selected_criteria]),
                                    gr.update(choices=deck_choices, value=[self._get_criteria_display_name(c) for c in deck_selected_criteria]),
                                    gr.update(interactive=bool(slide_selected_criteria or deck_selected_criteria)),
                                    gr.update(value=self._get_presentation_type_display(self.current_presentation_type)),
                                )

                            def admin_register(u, p, r, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return self.translator.t("admin_not_authorized")
                                if not (u and u.strip() and p and p.strip()):
                                    return self.translator.t("admin_fields_required")
                                ok = register_user(u, p, Role(r))
                                return self.translator.t("admin_user_registered") if ok else self.translator.t("admin_user_exists")

                            def admin_list(req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return [], gr.update(choices=[])
                                data = list_users()
                                data = [(u, role) for u, role in data if u and u.strip()]
                                choices = [u for u, _ in data if u != req.username]
                                return data, gr.update(choices=choices)

                            def admin_update_role(u, r, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return self.translator.t("admin_not_authorized")
                                if not u or not r:
                                    return self.translator.t("admin_select_user_role")
                                if u == req.username:
                                    return self.translator.t("admin_cannot_change_own")
                                ok = update_user_role(u, Role(r))
                                return self.translator.t("admin_role_updated") if ok else self.translator.t("admin_user_not_found")

                            def admin_update_password(u, p, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return self.translator.t("admin_not_authorized")
                                if not u or not p:
                                    return self.translator.t("admin_set_password")
                                if not p or not p.strip():
                                    return self.translator.t("admin_password_empty")
                                ok = update_user_password(u, p)
                                return self.translator.t("admin_password_updated") if ok else self.translator.t("admin_user_not_found")

                            def admin_delete_user(u, confirm, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return self.translator.t("admin_not_authorized")
                                if not u:
                                    return self.translator.t("admin_select_user_delete")
                                if not confirm:
                                    return self.translator.t("admin_confirm_delete_msg")
                                if u == req.username:
                                    return self.translator.t("admin_cannot_delete_self")
                                ok = delete_user(u)
                                return self.translator.t("admin_user_deleted") if ok else self.translator.t("admin_user_not_found")

                            interface.load(
                                on_load,
                                outputs=[
                                    profile_html,
                                    admin_tab,
                                    lang_button,
                                    title_md,
                                    description_md,
                                    upload_md,
                                    pdf_input,
                                    presentation_type_md,
                                    presentation_type_dropdown,
                                    criteria_md,
                                    presentation_type_input,
                                    slide_criteria_input,
                                    deck_criteria_input,
                                    evaluate_btn,
                                    results_md,
                                    status_output,
                                    generate_report_btn,
                                    download_report_btn,
                                    slide_nav_btn,
                                    slide_number,
                                    slide_nav_btn_next,
                                    slide_image,
                                    slide_evaluation,
                                    deck_results,
                                    users_table,
                                    refresh_users_btn,
                                    username_input,
                                    password_input,
                                    role_input,
                                    register_btn,
                                    register_status,
                                    user_select,
                                    new_role_input,
                                    update_role_btn,
                                    new_password_input,
                                    update_password_btn,
                                    delete_confirm,
                                    delete_btn,
                                    admin_action_status,
                                    lang_state,
                                ],
                            )
                            lang_button.click(
                                toggle_language,
                                inputs=[lang_state, slide_criteria_input, deck_criteria_input],
                                outputs=[
                                    profile_html,
                                    admin_tab,
                                    lang_button,
                                    title_md,
                                    description_md,
                                    upload_md,
                                    pdf_input,
                                    presentation_type_md,
                                    presentation_type_dropdown,
                                    criteria_md,
                                    presentation_type_input,
                                    slide_criteria_input,
                                    deck_criteria_input,
                                    evaluate_btn,
                                    results_md,
                                    status_output,
                                    generate_report_btn,
                                    download_report_btn,
                                    slide_nav_btn,
                                    slide_number,
                                    slide_nav_btn_next,
                                    slide_image,
                                    slide_evaluation,
                                    deck_results,
                                    users_table,
                                    refresh_users_btn,
                                    username_input,
                                    password_input,
                                    role_input,
                                    register_btn,
                                    register_status,
                                    user_select,
                                    new_role_input,
                                    update_role_btn,
                                    new_password_input,
                                    update_password_btn,
                                    delete_confirm,
                                    delete_btn,
                                    admin_action_status,
                                    lang_state,
                                ],
                            )
                            presentation_type_input.change(
                                on_presentation_type_change,
                                inputs=[presentation_type_input, slide_criteria_input, deck_criteria_input],
                                outputs=[slide_criteria_input, deck_criteria_input, evaluate_btn, presentation_type_input],
                            )
                            register_btn.click(admin_register, inputs=[username_input, password_input, role_input], outputs=[register_status])
                            interface.load(admin_list, outputs=[users_table, user_select])
                            refresh_users_btn.click(admin_list, outputs=[users_table, user_select])
                            update_role_btn.click(admin_update_role, inputs=[user_select, new_role_input], outputs=[admin_action_status]).then(admin_list, outputs=[users_table, user_select])
                            update_password_btn.click(admin_update_password, inputs=[user_select, new_password_input], outputs=[admin_action_status]).then(fn=lambda: "", outputs=[new_password_input])
                            delete_btn.click(admin_delete_user, inputs=[user_select, delete_confirm], outputs=[admin_action_status]).then(admin_list, outputs=[users_table, user_select]).then(fn=lambda: False, outputs=[delete_confirm])

            
            # Event handlers
            def _validate_criteria(s, d, pt):
                if not pt:
                    raise gr.Error(self.translator.t("presentation_type_required"))
                if not (s or d):
                    raise gr.Error(self.translator.t("criteria_validation_error"))

            def _toggle_evaluate_btn(s, d):
                return gr.update(interactive=bool(s or d))

            slide_criteria_input.change(
                fn=_toggle_evaluate_btn,
                inputs=[slide_criteria_input, deck_criteria_input],
                outputs=[evaluate_btn]
            )
            deck_criteria_input.change(
                fn=_toggle_evaluate_btn,
                inputs=[slide_criteria_input, deck_criteria_input],
                outputs=[evaluate_btn]
            )

            evaluate_btn.click(
                fn=_validate_criteria,
                inputs=[slide_criteria_input, deck_criteria_input, presentation_type_dropdown],
                outputs=[]
            ).then(
                fn=self._clear_slide_navigation_state,
                inputs=[pdf_input],
                outputs=[slide_number, slide_image, slide_evaluation]
            ).then(
                fn=self._clear_ui_state,
                outputs=[deck_results, tldr_output, overall_score_output, status_output]
            ).then(
                fn=lambda: gr.update(interactive=False, value=self.translator.t("evaluating")),
                outputs=[evaluate_btn]
            ).then(
                fn=self._clear_slide_evaluation_display,
                outputs=[slide_evaluation]
            ).then(
                fn=self.evaluate_presentation,
                inputs=[pdf_input, slide_criteria_input, deck_criteria_input, presentation_type_dropdown],
                outputs=[result_state]
            ).then(
                fn=lambda r: tuple(r),
                inputs=[result_state],
                outputs=[deck_results, slide_image, tldr_output, overall_score_output, status_output]
            ).then(
                fn=lambda: self.get_slide_evaluation(self.current_slide_index),
                outputs=[slide_evaluation]
            ).then(
                fn=lambda: gr.update(interactive=True, value=self.translator.t("start_evaluation")),
                outputs=[evaluate_btn]
            )
            
            # Report generation handlers
            generate_report_btn.click(
                fn=self.generate_pdf_report,
                outputs=[download_report_btn, status_output]
            ).then(
                fn=lambda x: gr.update(visible=True) if x else gr.update(visible=False),
                inputs=[download_report_btn],
                outputs=[download_report_btn]
            )
            
            # Hide download component after file is downloaded/cleared
            download_report_btn.change(
                fn=lambda x: gr.update(visible=False) if not x else gr.update(),
                inputs=[download_report_btn],
                outputs=[download_report_btn]
            )
            
            def next_slide():
                if self.slide_images and self.current_slide_index < len(self.slide_images) - 1:
                    self.current_slide_index += 1
                    slide_num = self.current_slide_index + 1
                    slide_eval = self.get_slide_evaluation(self.current_slide_index)
                    return (
                        str(slide_num),
                        self.slide_images[self.current_slide_index],
                        slide_eval
                    )
                return gr.update(), gr.update(), gr.update()
            
            def prev_slide():
                if self.slide_images and self.current_slide_index > 0:
                    self.current_slide_index -= 1
                    slide_num = self.current_slide_index + 1
                    slide_eval = self.get_slide_evaluation(self.current_slide_index)
                    return (
                        str(slide_num),
                        self.slide_images[self.current_slide_index],
                        slide_eval
                    )
                return gr.update(), gr.update(), gr.update()
            
            slide_nav_btn_next.click(
                fn=next_slide,
                outputs=[slide_number, slide_image, slide_evaluation]
            )
            
            slide_nav_btn.click(
                fn=prev_slide,
                outputs=[slide_number, slide_image, slide_evaluation]
            )
            
            # Update slide evaluation when slide image changes
            slide_image.change(
                fn=lambda: self.get_slide_evaluation(self.current_slide_index),
                outputs=[slide_evaluation]
            )
        
        return interface


def create_app(auth:bool = True, use_langfuse: bool = False, eval_debug: bool = False, lang: str = 'en'):
    """Create and return the Gradio app with specified language."""
    if auth:
        from slideguard.ui.auth import init_db
        init_db()

    ui = SlideGuardUI(use_langfuse=use_langfuse, eval_debug=eval_debug)
    # Set language before creating UI
    ui.translator.set_language(lang)
    interface = ui.create_ui()
    
    # Add middleware to handle language switching via URL reload
    def language_middleware(request):
        # Get language from query parameter
        import urllib.parse
        query = urllib.parse.parse_qs(urllib.parse.urlparse(str(request.url)).query)
        requested_lang = query.get('lang', ['en'])[0]
        if requested_lang != lang and requested_lang in ['en', 'ru']:
            # Need to recreate app with new language
            # This is handled by the JavaScript redirect
            pass
        return request
    
    return interface


if __name__ == "__main__":
    app = create_app()
    app.launch(
        share=False, 
        debug=True,
        auth=verify_user_db
    )
