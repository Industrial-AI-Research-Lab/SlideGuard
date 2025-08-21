"""
PDF Report Generator for SlideGuard evaluations.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, blue, red, orange, green
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

from slideguard.schemes import FullEvaluation, Criteria


class SlideGuardReportGenerator:
    """Generate comprehensive PDF reports for SlideGuard evaluations."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report."""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#2E86AB')
        )
        
        # Section header style
        self.section_style = ParagraphStyle(
            'CustomSection',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#A23B72')
        )
        
        # Subsection style
        self.subsection_style = ParagraphStyle(
            'CustomSubsection',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=HexColor('#F18F01')
        )
        
        # Normal text style
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY
        )
        
        # Score style
        self.score_style = ParagraphStyle(
            'CustomScore',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=8,
            alignment=TA_CENTER,
            textColor=HexColor('#2E86AB'),
            fontName='Helvetica-Bold'
        )
    
    def _get_severity_color(self, severity: int) -> str:
        """Get color for severity level."""
        if severity == 1:
            return '#4CAF50'  # Green
        elif severity == 2:
            return '#FF9800'  # Orange
        elif severity == 3:
            return '#F44336'  # Red
        else:
            return '#9E9E9E'  # Gray
    
    def _get_score_color(self, score: float, max_score: float = 5.0) -> str:
        """Get color for score level."""
        percentage = (score / max_score) * 100
        if percentage >= 80:
            return '#4CAF50'  # Green
        elif percentage >= 60:
            return '#FF9800'  # Orange
        elif percentage >= 40:
            return '#FFC107'  # Yellow
        else:
            return '#F44336'  # Red
    
    def _create_header_footer(self, canvas_obj: canvas.Canvas, title: str):
        """Create header and footer for each page."""
        # Header
        canvas_obj.setFont("Helvetica-Bold", 12)
        canvas_obj.setFillColor(HexColor('#2E86AB'))
        canvas_obj.drawString(50, 750, "SlideGuard AI Evaluation Report")
        
        # Footer
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(black)
        canvas_obj.drawString(50, 50, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        canvas_obj.drawRightString(550, 50, f"Page {canvas_obj.getPageNumber()}")
    
    def _add_evaluation_element(self, story: List, element: Any, index: int):
        """Add an evaluation element to the report."""
        # Handle both Pydantic objects and dictionaries
        if hasattr(element, 'severity') and hasattr(element, 'evaluation_element'):
            # Handle Pydantic objects
            severity = element.severity
            evaluation_element = element.evaluation_element
            suggestion = element.evaluation_suggestion
        elif hasattr(element, 'evaluation_element'):
            # Handle Pydantic objects without severity
            severity = 1  # Default to low priority
            evaluation_element = element.evaluation_element
            suggestion = element.evaluation_suggestion
        elif isinstance(element, dict):
            # Handle dictionaries
            severity = element.get('severity', 1)
            evaluation_element = element.get('evaluation_element', 'Unknown Element')
            suggestion = element.get('evaluation_suggestion', 'No suggestion provided')
        else:
            # Fallback for unexpected format
            try:
                # Try to extract from string representation
                element_str = str(element)
                import re
                element_match = re.search(r"evaluation_element='([^']*)'", element_str)
                suggestion_match = re.search(r"evaluation_suggestion='([^']*)'", element_str)
                severity_match = re.search(r"severity=(\d+)", element_str)
                
                evaluation_element = element_match.group(1) if element_match else "Analysis completed"
                suggestion = suggestion_match.group(1) if suggestion_match else "No specific suggestion"
                severity = int(severity_match.group(1)) if severity_match else 1
            except Exception:
                # Final fallback
                evaluation_element = "Unknown evaluation element"
                suggestion = "Unable to parse suggestion"
                severity = 1
        
        # Severity indicator
        severity_color = self._get_severity_color(severity)
        severity_text = {1: "Low", 2: "Medium", 3: "High"}.get(severity, "Info")
        
        # Create severity badge
        severity_style = ParagraphStyle(
            'SeverityBadge',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=white,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        severity_badge = f'<span style="background-color: {severity_color}; color: white; padding: 2px 6px; border-radius: 3px;">{severity_text} Priority (Severity: {severity}/3)</span>'
        
        story.append(Paragraph(f"<b>{index}. {evaluation_element}</b>", self.subsection_style))
        story.append(Paragraph(severity_badge, severity_style))
        story.append(Paragraph(f"<b>Suggestion:</b> {suggestion}", self.normal_style))
        story.append(Spacer(1, 12))
    
    def _add_criteria_evaluation(self, story: List, criteria: Criteria, eval_result: Any):
        """Add a criteria evaluation to the report."""
        criteria_name = criteria.value.replace('_', ' ').title()
        story.append(Paragraph(f"<b>🎯 {criteria_name}</b>", self.section_style))
        
        # Handle both Pydantic objects and dictionaries
        if hasattr(eval_result, 'evaluation_results'):
            # Handle Pydantic objects with evaluation_results (like SlideTitleContentMatch)
            evaluation_results = eval_result.evaluation_results
            for i, element in enumerate(evaluation_results, 1):
                self._add_evaluation_element(story, element, i)
            
            # Calculate and display score
            total_severity = 0
            for elem in evaluation_results:
                if hasattr(elem, 'severity'):
                    total_severity += elem.severity
                elif isinstance(elem, dict):
                    total_severity += elem.get('severity', 1)
                else:
                    # Try to extract severity from string representation
                    try:
                        import re
                        severity_match = re.search(r"severity=(\d+)", str(elem))
                        total_severity += int(severity_match.group(1)) if severity_match else 1
                    except Exception:
                        total_severity += 1
            
            avg_score = total_severity / len(evaluation_results) if evaluation_results else 0
            score_percentage = (avg_score / 3.0) * 100
            
            score_color = self._get_score_color(avg_score, 3.0)
            score_text = f"Final Score: {avg_score:.1f}/3.0 ({score_percentage:.0f}%)"
            
            score_style = ParagraphStyle(
                'ScoreStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=HexColor(score_color),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            story.append(Paragraph(f"<b>{score_text}</b>", score_style))
            
            # Add score from Pydantic object if available
            if hasattr(eval_result, 'score'):
                score = eval_result.score
                score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                score_color = self._get_score_color(score, 5.0)
                
                story.append(Paragraph(f"<b>Overall Score: {score:.1f}/5.0 ({score_percentage:.0f}%)</b>", self.score_style))
                
        elif isinstance(eval_result, dict):
            # Handle dictionary format
            if 'evaluation_results' in eval_result:
                evaluation_results = eval_result['evaluation_results']
                for i, element in enumerate(evaluation_results, 1):
                    self._add_evaluation_element(story, element, i)
                
                # Calculate and display score
                total_severity = 0
                for elem in evaluation_results:
                    if hasattr(elem, 'severity'):
                        total_severity += elem.severity
                    elif isinstance(elem, dict):
                        total_severity += elem.get('severity', 1)
                    else:
                        # Try to extract severity from string representation
                        try:
                            import re
                            severity_match = re.search(r"severity=(\d+)", str(elem))
                            total_severity += int(severity_match.group(1)) if severity_match else 1
                        except Exception:
                            total_severity += 1
                
                avg_score = total_severity / len(evaluation_results) if evaluation_results else 0
                score_percentage = (avg_score / 3.0) * 100
                
                score_color = self._get_score_color(avg_score, 3.0)
                score_text = f"Final Score: {avg_score:.1f}/3.0 ({score_percentage:.0f}%)"
                
                score_style = ParagraphStyle(
                    'ScoreStyle',
                    parent=self.styles['Normal'],
                    fontSize=12,
                    textColor=HexColor(score_color),
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )
                
                story.append(Paragraph(f"<b>{score_text}</b>", score_style))
                
            elif 'score' in eval_result:
                score = eval_result['score']
                score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                score_color = self._get_score_color(score, 5.0)
                
                story.append(Paragraph(f"<b>Score: {score:.1f}/5.0 ({score_percentage:.0f}%)</b>", self.score_style))
                
                if 'comments' in eval_result:
                    story.append(Paragraph(f"<b>Comments:</b> {eval_result['comments']}", self.normal_style))
                if 'recommendations' in eval_result:
                    story.append(Paragraph(f"<b>Recommendations:</b> {eval_result['recommendations']}", self.normal_style))
            else:
                story.append(Paragraph(str(eval_result), self.normal_style))
        else:
            # Fallback for other formats
            story.append(Paragraph(str(eval_result), self.normal_style))
        
        story.append(Spacer(1, 20))
    
    def generate_report(self, evaluation: FullEvaluation, presentation_name: str = "Unknown") -> BytesIO:
        """Generate a comprehensive PDF report for the evaluation."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        story = []
        
        # Title page
        story.append(Paragraph("SlideGuard AI Evaluation Report", self.title_style))
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"<b>Presentation:</b> {presentation_name}", self.normal_style))
        story.append(Paragraph(f"<b>Evaluation Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", self.normal_style))
        story.append(Paragraph(f"<b>Total Slides:</b> {len(evaluation.slide_evaluations)}", self.normal_style))
        
        # Overall score if available
        if evaluation.overall_score:
            overall_percentage = (evaluation.overall_score / 5.0) * 100
            overall_color = self._get_score_color(evaluation.overall_score, 5.0)
            
            overall_style = ParagraphStyle(
                'OverallScore',
                parent=self.styles['Normal'],
                fontSize=16,
                textColor=HexColor(overall_color),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"<b>Overall Score: {evaluation.overall_score:.2f}/5.0 ({overall_percentage:.0f}%)</b>", overall_style))
        
        story.append(PageBreak())
        
        # Executive Summary
        if evaluation.summary:
            story.append(Paragraph("Executive Summary", self.section_style))
            story.append(Paragraph(evaluation.summary, self.normal_style))
            story.append(PageBreak())
        
        # Deck-Level Evaluations
        if evaluation.deck_evaluations and evaluation.deck_evaluations.evaluations:
            story.append(Paragraph("Deck-Level Evaluation Results", self.section_style))
            
            for criteria, eval_result in evaluation.deck_evaluations.evaluations.items():
                self._add_criteria_evaluation(story, criteria, eval_result)
            
            story.append(PageBreak())
        
        # Slide-Level Evaluations
        if evaluation.slide_evaluations:
            story.append(Paragraph("Slide-Level Evaluation Results", self.section_style))
            
            for slide_idx, slide_eval in enumerate(evaluation.slide_evaluations, 1):
                story.append(Paragraph(f"Slide {slide_idx}", self.subsection_style))
                
                if slide_eval.evaluations:
                    for criteria, eval_result in slide_eval.evaluations.items():
                        self._add_criteria_evaluation(story, criteria, eval_result)
                else:
                    story.append(Paragraph("No evaluations available for this slide.", self.normal_style))
                
                story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(story, onFirstPage=lambda canvas, doc: self._create_header_footer(canvas, presentation_name),
                 onLaterPages=lambda canvas, doc: self._create_header_footer(canvas, presentation_name))
        
        buffer.seek(0)
        return buffer
    
    def save_report(self, evaluation: FullEvaluation, output_path: str, presentation_name: str = "Unknown") -> str:
        """Generate and save a PDF report to the specified path."""
        buffer = self.generate_report(evaluation, presentation_name)
        
        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())
        
        return output_path
