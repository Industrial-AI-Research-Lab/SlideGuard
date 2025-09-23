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
from typing import Dict, List, Optional, Tuple
import gradio as gr
from PIL import Image
import fitz  # PyMuPDF

from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.schemes import Criteria, FullEvaluation, UIEvaluationResult
from slideguard.utils.config import SlideGuardConfig, load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.utils.cache_manager import CacheManager
from slideguard.utils.file_manager import FileManager
from slideguard.utils.config import load_langfuse_client
from slideguard.ui.report_generator import SlideGuardReportGenerator
from slideguard.ui.auth import verify_user_db, get_role, register_user, Role, list_users, update_user_password, update_user_role, delete_user


class SlideGuardUI:
    """Main UI class for SlideGuard application."""
    
    def __init__(self):
        self.evaluator = None
        self.current_evaluation = None
        self.slide_images = []
        self.current_slide_index = 0
        self.temp_files = []  # Track temporary files for cleanup
        self.current_presentation_name = "Unknown"
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = load_config()
        self.langfuse_client = load_langfuse_client(False)
        
        # Initialize evaluator and report generator
        self._initialize_evaluator()
        self.report_generator = SlideGuardReportGenerator()
    
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
                llm=llm
            )
            self.logger.info("Evaluator initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize evaluator: {e}")
    
    def _clear_ui_state(self) -> Tuple[str, str, str, str]:
        msg = "🔄 Processing evaluation... Please wait."
        return (msg, "", "", msg)
    
    def _clear_slide_evaluation_display(self) -> str:
        """Clear slide evaluation display during processing."""
        if self.slide_images:
            return "🔄 Processing evaluation... Please wait."
        else:
            return "Upload a presentation to see slide evaluations."
    
    def _clear_slide_navigation_state(self, pdf_input) -> Tuple[str, Optional[str], str]:
        if not pdf_input:
            # Keep existing state if no PDF provided
            slide_idx = str(self.current_slide_index + 1) if self.slide_images else "1"
            current_image = self.slide_images[self.current_slide_index] if self.slide_images else None
            return (slide_idx, current_image, "Upload a presentation to launch evaluation.")
        
        self.current_presentation_name = Path(pdf_input.name).stem
        self.slide_images = self._extract_slide_images(pdf_input.name)
        self.current_slide_index = 0
        first_image = self.slide_images[0] if self.slide_images else None
        msg = "🔄 Processing evaluation... Please wait." if self.slide_images else "Failed to extract slides."
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
    
    def _load_criteria(self, criteria_names: List[str]) -> Tuple[List[Criteria], List[Criteria]]:
        """Load slide and deck criteria based on input criteria list."""
        if criteria_names:
            criterias = [Criteria(c) for c in criteria_names]
            slide_criterias = [c for c in criterias if c.is_slide_criteria()]
            deck_criterias = [c for c in criterias if c.is_deck_criteria()]
        else:
            slide_criterias = list(SLIDE_CRITERIA_INFO.keys())
            deck_criterias = list(DECK_CRITERIA_INFO.keys())
        
        return slide_criterias, deck_criterias
    
    async def evaluate_presentation(self, pdf_file, selected_criteria) -> UIEvaluationResult:
        """Evaluate a presentation and return results."""
        if not pdf_file:
            return UIEvaluationResult.error("Please upload a PDF file to start evaluation.")
        
        if not self.evaluator:
            return UIEvaluationResult.error("Evaluator not initialized. Please check your configuration.")
        
        try:
            self.current_evaluation = None
            
            # Load criteria
            slide_criterias, deck_criterias = self._load_criteria(selected_criteria)
            
            # Run evaluation
            self.logger.info(f"Starting evaluation with {len(slide_criterias)} slide criteria and {len(deck_criterias)} deck criteria")
            
            evaluation = await self.evaluator.evaluate_presentation(
                presentation_path=pdf_file.name,
                slide_criterias=slide_criterias,
                deck_criterias=deck_criterias,
                langfuse_client=self.langfuse_client
            )
            
            self.current_evaluation = evaluation
            self.current_slide_index = 0
            
            # Format results
            deck_summary = self._format_deck_results(evaluation)
            tldr_text = evaluation.tldr or ""
            tldr_html = (
                f"<div style='background-color: #fffde7; padding: 8px; border-radius: 8px; margin: 4px 0 4px 0; border-left: 4px solid #fbc02d; color: #333333;'>"
                f"<h3 style='color: #333333; margin-top: 0; margin-bottom: 4px;'>⚡ <strong>TL;DR</strong></h3>"
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
                    f"{icon} Overall Score: {s}/5"
                    f"</span>"
                    f"</div>"
                )
            
            # Return the first slide image if available, otherwise None
            first_slide_image = self.slide_images[0] if self.slide_images else None
            status_msg = f"✅ Evaluation completed successfully! Processed {len(self.slide_images)} slides with {len(slide_criterias)} slide criteria and {len(deck_criterias)} deck criteria."
            return UIEvaluationResult(deck_summary=deck_summary, first_slide_image=first_slide_image, tldr_html=tldr_html, score_html=score_html, status_msg=status_msg)
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}")
            return UIEvaluationResult.error(f"Evaluation failed: {str(e)}")
    
    def _format_deck_results(self, evaluation: FullEvaluation) -> str:
        """Format deck-level evaluation results."""
        if not evaluation or not evaluation.deck_evaluations:
            return "No deck-level evaluations available."
        
        result = "<h2 style='color: #333333;'>📋 Deck-Level Evaluation Results</h2>\n\n"
        
        for criteria, eval_result in evaluation.deck_evaluations.evaluations.items():
            criteria_name = criteria.value.replace('_', ' ').title()
            result += f"<div style='background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #2196f3; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: #333333;'>\n"
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
                        score_text = "Excellent"
                        score_color = "#4caf50"
                    elif score_percentage >= 60:
                        score_icon = "🟡"
                        score_text = "Good"
                        score_color = "#ff9800"
                    elif score_percentage >= 40:
                        score_icon = "🟠"
                        score_text = "Fair"
                        score_color = "#ff9800"
                    else:
                        score_icon = "🔴"
                        score_text = "Needs Improvement"
                        score_color = "#f44336"
                    
                    result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid {score_color}; color: #333333;'>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>📊 Score: {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>Assessment:</strong> {score_text}</p>\n"
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
                        score_text = "Excellent"
                        score_color = "#4caf50"
                    elif score_percentage >= 60:
                        score_icon = "🟡"
                        score_text = "Good"
                        score_color = "#ff9800"
                    elif score_percentage >= 40:
                        score_icon = "🟠"
                        score_text = "Fair"
                        score_color = "#ff9800"
                    else:
                        score_icon = "🔴"
                        score_text = "Needs Improvement"
                        score_color = "#f44336"
                    
                    result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid {score_color}; color: #333333;'>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>📊 Score: {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                    result += f"<p style='color: #333333; margin: 8px 0;'><strong>Assessment:</strong> {score_text}</p>\n"
                    
                    if 'comments' in eval_result:
                        result += f"<p style='color: #333333; margin: 8px 0;'><strong>💬 Comments:</strong><br>{eval_result['comments']}</p>\n"
                    if 'recommendations' in eval_result:
                        result += f"<p style='color: #333333; margin: 8px 0;'><strong>💡 Recommendations:</strong><br>{eval_result['recommendations']}</p>\n"
                    result += "</div>\n"
                else:
                    result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                    result += f"{eval_result}\n"
                    result += "</div>\n"
            else:
                # Fallback for other formats
                result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                result += f"{eval_result}\n"
                result += "</div>\n"
            
            result += "</div>\n\n"
        
        if evaluation.overall_score:
            overall_percentage = (evaluation.overall_score / 5.0) * 100
            if overall_percentage >= 80:
                overall_icon = "🟢"
                overall_text = "Excellent"
            elif overall_percentage >= 60:
                overall_icon = "🟡"
                overall_text = "Good"
            elif overall_percentage >= 40:
                overall_icon = "🟠"
                overall_text = "Fair"
            else:
                overall_icon = "🔴"
                overall_text = "Needs Improvement"
            
            result += f"<div style='background-color: #e3f2fd; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #2196f3; color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'>🏆 <strong>Overall Score: {overall_icon} {evaluation.overall_score:.2f}/5.0 ({overall_percentage:.0f}%)</strong></h3>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>Overall Assessment:</strong> {overall_text}</p>\n"
            result += "</div>\n\n"
        
        if evaluation.summary:
            result += f"<div style='background-color: #f3e5f5; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #9c27b0; color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'>📝 <strong>Summary</strong></h3>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'>{evaluation.summary}</p>\n"
            result += "</div>\n\n"
        
        return result
    
    def _format_slide_results(self, evaluation: FullEvaluation) -> str:
        """Format slide-level evaluation results."""
        if not evaluation or not evaluation.slide_evaluations:
            return "No slide-level evaluations available."
        
        result = "<h2 style='color: #333333;'>📄 Slide-Level Evaluation Results</h2>\n\n"
        
        for slide_eval in evaluation.slide_evaluations:
            result += f"<h3 style='color: #333333;'>📊 Slide {slide_eval.slide_id + 1}</h3>\n"
            
            if slide_eval.evaluations:
                for criteria, eval_result in slide_eval.evaluations.items():
                    result += f"<h4 style='color: #333333;'>🎯 {criteria.value.replace('_', ' ').title()}</h4>\n"
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
            return "No slide evaluation available."
        
        if slide_index < 0:
            return "Invalid slide index."
        
        if slide_index >= len(self.current_evaluation.slide_evaluations):
            return "Slide index out of range."
        
        slide_eval = self.current_evaluation.slide_evaluations[slide_index]
        result = f"<h2 style='color: #333333;'>📊 Slide {slide_index + 1} Evaluation</h2>\n\n"
        
        if slide_eval.evaluations:
            for criteria, eval_result in slide_eval.evaluations.items():
                criteria_name = criteria.value.replace('_', ' ').title()
                result += f"<div style='background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #2196f3; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>\n"
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
                            score_text = "Excellent"
                        elif score_percentage >= 60:
                            score_icon = "🟡"
                            score_text = "Good"
                        elif score_percentage >= 40:
                            score_icon = "🟠"
                            score_text = "Fair"
                        else:
                            score_icon = "🔴"
                            score_text = "Needs Improvement"
                        
                        result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                        result += f"<p><strong>📊 Score: {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                        result += f"<p><strong>Assessment:</strong> {score_text}</p>\n"
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
                            score_text = "Excellent"
                        elif score_percentage >= 60:
                            score_icon = "🟡"
                            score_text = "Good"
                        elif score_percentage >= 40:
                            score_icon = "🟠"
                            score_text = "Fair"
                        else:
                            score_icon = "🔴"
                            score_text = "Needs Improvement"
                        
                        result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                        result += f"<p><strong>📊 Score: {score_icon} {score:.1f}/5.0 ({score_percentage:.0f}%)</strong></p>\n"
                        result += f"<p><strong>Assessment:</strong> {score_text}</p>\n"
                        
                        if 'comments' in eval_result:
                            result += f"<p><strong>💬 Comments:</strong><br>{eval_result['comments']}</p>\n"
                        if 'recommendations' in eval_result:
                            result += f"<p><strong>💡 Recommendations:</strong><br>{eval_result['recommendations']}</p>\n"
                        result += "</div>\n"
                    else:
                        result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                        result += f"{eval_result}\n"
                        result += "</div>\n"
                else:
                    # Fallback for other formats
                    result += f"<div style='background-color: #ffffff; padding: 12px; border-radius: 6px; margin: 8px 0;'>\n"
                    result += f"{eval_result}\n"
                    result += "</div>\n"
                
                result += "</div>\n\n"
        else:
            result += "<div style='background-color: #fff3e0; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #ff9800; color: #333333;'>\n"
            result += "<p style='color: #333333;'><strong>⚠️ No evaluations available for this slide.</strong></p>\n"
            result += "</div>\n\n"
        
        return result
    
    def _format_structured_evaluation(self, evaluation_results) -> str:
        """Format structured evaluation results with severity indicators."""
        if not evaluation_results:
            return "No detailed evaluation results available.\n\n"
        
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
                        result += f"<div style='background-color: #f5f5f5; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #666;'>\n"
                        result += f"### ⚠️ **Unexpected Result Format**\n"
                        result += f"**Raw Data:** {str(eval_item)[:200]}...\n"
                        result += "</div>\n\n"
                        continue
                except Exception as e:
                    # Final fallback
                    result += f"<div style='background-color: #f5f5f5; padding: 12px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #666;'>\n"
                    result += f"### ⚠️ **Error Processing Result**\n"
                    result += f"**Error:** {str(e)}\n"
                    result += f"**Raw Data:** {str(eval_item)[:200]}...\n"
                    result += "</div>\n\n"
                    continue
            
            # Update max severity and score
            total_severity += severity
            
            # Severity indicator with better styling and dark theme compatibility
            if severity == 1:
                severity_icon = "🟢"
                severity_text = "Low Priority"
                severity_color = "#4caf50"
                bg_color = "#e8f5e8"
                border_color = "#4caf50"
            elif severity == 2:
                severity_icon = "🟡"
                severity_text = "Medium Priority"
                severity_color = "#ff9800"
                bg_color = "#fff3e0"
                border_color = "#ff9800"
            elif severity == 3:
                severity_icon = "🔴"
                severity_text = "High Priority"
                severity_color = "#f44336"
                bg_color = "#ffebee"
                border_color = "#f44336"
            else:
                severity_icon = "⚪"
                severity_text = "Info"
                severity_color = "#9e9e9e"
                bg_color = "#f5f5f5"
                border_color = "#9e9e9e"
            
            result += f"<div style='background-color: {bg_color}; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid {border_color}; color: #333333;'>\n"
            result += f"<h3 style='color: #333333; margin-top: 0;'>{severity_icon} <strong>Analysis</strong></h3>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>Priority:</strong> {severity_text} (Severity: {severity}/3)</p>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>📝 Evaluation:</strong> {element}</p>\n"
            result += f"<p style='color: #333333; margin: 8px 0;'><strong>💡 Suggestion:</strong> {suggestion}</p>\n"
            result += "</div>\n\n"
        
        severity_score = total_severity / len(items) if items else 0
        severity_percentage = (severity_score / 3.0) * 100

        if severity_percentage >= 80:
            score_icon = "🔴"
            score_text = "Needs Improvement"
            score_color = "#f44336"
        elif severity_percentage >= 60:
            score_icon = "🟠"
            score_text = "Fair"
            score_color = "#ff9800"
        elif severity_percentage >= 40:
            score_icon = "🟡"
            score_text = "Good"
            score_color = "#ffeb3b"
        else:
            score_icon = "🟢"
            score_text = "Excellent"
            score_color = "#4caf50"

        result += f"<div style='background-color: #ffffff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid {score_color}; box-shadow: 0 2px 4px rgba(0,0,0,0.1); color: #333333;'>\n"
        result += f"<h3 style='color: #333333; margin-top: 0;'>📊 <strong>Total Severity: {score_icon} {severity_score:.1f}/3.0 ({severity_percentage:.0f}%)</strong></h3>\n"
        result += f"<p style='color: #333333; margin: 8px 0;'><strong>Overall Assessment:</strong> {score_text}</p>\n"
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
            return None, "❌ No evaluation available. Please run an evaluation first."
        
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
            return pdf_path, "✅ PDF report generated successfully! Click the download button to save it."
            
        except Exception as e:
            return None, f"❌ Failed to generate PDF report: {str(e)}"

    def render_profile_widget(self, username: str) -> str:
        u = username or "Guest"
        initial = (u[:1] or "?").upper()
        safe_name = escape(u)
        html = dedent("""
                <div id='sgProfileContainer' style='position:fixed;top:12px;right:12px;z-index:2147483647;'>
                <div id='sgProfileIcon' style='width:36px;height:36px;border-radius:50%;background:#1f6feb;color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:600;' onclick="event.stopPropagation();var d=document.getElementById('sgProfileDropdown');if(d){d.style.display=(d.style.display==='block')?'none':'block';}">__INITIAL__</div>
                <div id='sgProfileDropdown' style='display:none;position:absolute;right:0;top:44px;background:#fff;border:1px solid #e0e0e0;border-radius:8px;min-width:200px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:2147483647;max-height:none;overflow:visible;'>
                    <div style='padding:12px 16px;font-weight:600;border-bottom:1px solid #eee;' id='sgProfileName'>__SAFE_NAME__</div>
                    <a href='/logout' id='sgLogoutLink' style='padding:10px 16px;display:block;text-decoration:none;color:#333;' onclick="(function(){var p=new URLSearchParams(window.location.search);var t=p.get('__theme')||localStorage.getItem('sg_theme')||'';if(t){localStorage.setItem('sg_theme',t);}fetch('/logout',{method:'GET',credentials:'include'}).finally(function(){window.top.location.href='/?__theme='+encodeURIComponent(t);});return false;})()">Logout</a>
                </div>
                </div>""")
        return html.replace("__INITIAL__", initial).replace("__SAFE_NAME__", safe_name)
    
    def create_ui(self):
        """Create the Gradio interface."""
        # Available criteria (exclude internal helper criteria)
        slide_criteria = [c for c in SLIDE_CRITERIA_INFO.keys() if not c.is_service_criteria()]
        deck_criteria = list(DECK_CRITERIA_INFO.keys())
        all_criteria = slide_criteria + deck_criteria
        criteria_choices = [c.value for c in all_criteria]
        
        with gr.Blocks(title="SlideGuard - Presentation Evaluation", theme=gr.themes.Default()) as interface:
            gr.Markdown("# 🎯 SlideGuard - AI-Powered Presentation Evaluation")
            gr.Markdown("Upload your presentation PDF, select evaluation criteria, and get detailed feedback on your slides.")
            gr.Markdown("---")
            profile_html = gr.HTML(value="")
            
            with gr.Row():
                with gr.Column(scale=1):
                    # Upload section
                    gr.Markdown("## 📁 Upload Presentation")
                    pdf_input = gr.File(
                        label="Upload PDF Presentation",
                        file_types=[".pdf"],
                        type="filepath",
                        height=100
                    )
                    
                    # Criteria selection
                    gr.Markdown("## 🎯 Select Evaluation Criteria")
                    criteria_input = gr.CheckboxGroup(
                        choices=criteria_choices,
                        label="Choose criteria to evaluate",
                        value=criteria_choices,  # Select all by default
                        interactive=True
                    )
                    
                    # Evaluate button
                    evaluate_btn = gr.Button(
                        "🚀 Start Evaluation",
                        variant="primary",
                        scale=1
                    )
                
                with gr.Column(scale=2):
                    # Results section
                    gr.Markdown("## 📊 Evaluation Results")
                    
                    # Status display (moved here for better visibility during processing)
                    status_output = gr.Textbox(
                        label="Status",
                        interactive=False,
                        lines=2,
                        max_lines=5
                    )
                    tldr_output = gr.HTML("")
                    overall_score_output = gr.HTML("")
                    result_state = gr.State()
                    
                    # Report generation section
                    with gr.Row():
                        generate_report_btn = gr.Button(
                            "📄 Generate PDF Report",
                            variant="secondary",
                            scale=1
                        )
                        download_report_btn = gr.File(
                            label="Download PDF Report",
                            visible=False,
                            scale=1
                        )
                    
                    with gr.Tabs():
                        with gr.TabItem("🖼️ Interactive Presentation Viewer"):
                            with gr.Row():
                                with gr.Column(scale=1):
                                    slide_nav_btn = gr.Button("◀️ Previous", scale=1)
                                    slide_number = gr.Textbox(
                                        label="Current Slide",
                                        value="1",
                                        interactive=False
                                    )
                                    slide_nav_btn_next = gr.Button("Next ▶️", scale=1)
                                
                                with gr.Column(scale=3):
                                    slide_image = gr.Image(
                                        label="Slide Preview",
                                        interactive=False,
                                        height=400
                                    )
                            
                            slide_evaluation = gr.HTML("Upload a presentation to see slide evaluations.")
                        
                        with gr.TabItem("📋 Deck-Level Results"):
                            deck_results = gr.HTML("Upload a presentation and select criteria to see deck-level evaluation results.")

                        with gr.TabItem("🔒 Admin Panel", visible=False) as admin_tab:
                            admin_panel = gr.Group()
                            with admin_panel:
                                with gr.Tabs():
                                    with gr.TabItem("Users"):
                                        with gr.Row():
                                            with gr.Column(scale=1):
                                                users_table = gr.Dataframe(headers=["Username", "Role"], interactive=False)
                                                with gr.Row():
                                                    refresh_users_btn = gr.Button(value="Refresh", variant="secondary")
                                    with gr.TabItem("Create User"):
                                        with gr.Column():
                                            username_input = gr.Textbox(label="Username")
                                            password_input = gr.Textbox(label="Password", type="password")
                                            role_input = gr.Dropdown(choices=[r.value for r in Role], label="Role")
                                            register_btn = gr.Button(value="Register User", variant="primary")
                                            register_status = gr.Textbox(label="Status", interactive=False)
                                    with gr.TabItem("Manage User"):
                                        with gr.Column():
                                            user_select = gr.Dropdown(choices=[], label="Select User")
                                            new_role_input = gr.Dropdown(choices=[r.value for r in Role], label="New Role")
                                            update_role_btn = gr.Button(value="Update Role", variant="primary")
                                            new_password_input = gr.Textbox(label="New Password", type="password")
                                            update_password_btn = gr.Button(value="Update Password", variant="primary")
                                            delete_confirm = gr.Checkbox(label="Confirm Delete")
                                            delete_btn = gr.Button(value="Delete User", variant="stop")
                                            admin_action_status = gr.Textbox(label="Action Status", interactive=False)

                            def on_load(req: gr.Request):
                                u = req.username if req and req.username else "Guest"
                                is_admin = (get_role(u) == Role.ADMIN) if u and u != "Guest" else False
                                return self.render_profile_widget(u), gr.update(visible=is_admin)

                            def admin_register(u, p, r, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return "Not authorized"
                                if not (u and u.strip() and p and p.strip()):
                                    return "Username and password are required"
                                ok = register_user(u, p, Role(r))
                                return "User registered successfully" if ok else "User already exists"

                            def admin_list(req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return [], gr.update(choices=[])
                                data = list_users()
                                data = [(u, role) for u, role in data if u and u.strip()]
                                choices = [u for u, _ in data if u != req.username]
                                return data, gr.update(choices=choices)

                            def admin_update_role(u, r, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return "Not authorized"
                                if not u or not r:
                                    return "Select user and role"
                                if u == req.username:
                                    return "Cannot change own role"
                                ok = update_user_role(u, Role(r))
                                return "Role updated" if ok else "User not found"

                            def admin_update_password(u, p, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return "Not authorized"
                                if not u or not p:
                                    return "Select user and set password"
                                if not p or not p.strip():
                                    return "Password cannot be empty"
                                ok = update_user_password(u, p)
                                return "Password updated" if ok else "User not found"

                            def admin_delete_user(u, confirm, req: gr.Request):
                                if get_role(req.username) != Role.ADMIN:
                                    return "Not authorized"
                                if not u:
                                    return "Select user"
                                if not confirm:
                                    return "Confirm delete"
                                if u == req.username:
                                    return "Cannot delete self"
                                ok = delete_user(u)
                                return "User deleted" if ok else "User not found"

                            interface.load(on_load, outputs=[profile_html, admin_tab])
                            register_btn.click(admin_register, inputs=[username_input, password_input, role_input], outputs=[register_status])
                            interface.load(admin_list, outputs=[users_table, user_select])
                            refresh_users_btn.click(admin_list, outputs=[users_table, user_select])
                            update_role_btn.click(admin_update_role, inputs=[user_select, new_role_input], outputs=[admin_action_status]).then(admin_list, outputs=[users_table, user_select])
                            update_password_btn.click(admin_update_password, inputs=[user_select, new_password_input], outputs=[admin_action_status]).then(fn=lambda: "", outputs=[new_password_input])
                            delete_btn.click(admin_delete_user, inputs=[user_select, delete_confirm], outputs=[admin_action_status]).then(admin_list, outputs=[users_table, user_select]).then(fn=lambda: False, outputs=[delete_confirm])

            
            # Event handlers
            evaluate_btn.click(
                fn=self._clear_slide_navigation_state,
                inputs=[pdf_input],
                outputs=[slide_number, slide_image, slide_evaluation]
            ).then(
                fn=self._clear_ui_state,
                outputs=[deck_results, tldr_output, overall_score_output, status_output]
            ).then(
                fn=lambda: gr.update(interactive=False, value="⏳ Evaluating..."),
                outputs=[evaluate_btn]
            ).then(
                fn=self._clear_slide_evaluation_display,
                outputs=[slide_evaluation]
            ).then(
                fn=self.evaluate_presentation,
                inputs=[pdf_input, criteria_input],
                outputs=[result_state]
            ).then(
                fn=lambda r: tuple(r),
                inputs=[result_state],
                outputs=[deck_results, slide_image, tldr_output, overall_score_output, status_output]
            ).then(
                fn=lambda: gr.update(interactive=True, value="🚀 Start Evaluation"),
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


def create_app(auth:bool = True):
    """Create and return the Gradio app."""
    if auth:
        from slideguard.ui.auth import init_db
        init_db()

    ui = SlideGuardUI()
    return ui.create_ui()


if __name__ == "__main__":
    app = create_app()
    app.launch(
        share=False, 
        debug=True,
        auth=verify_user_db
    )
