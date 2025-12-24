"""
PDF Report Generator for SlideGuard evaluations.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image, Flowable
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from slideguard.schemes import FullEvaluation, Criteria
from slideguard.ui.translations import Translator


class SlideGuardReportGenerator:
    """Generate comprehensive PDF reports for SlideGuard evaluations."""
    
    def __init__(self, translator: Translator = None):
        self.translator = translator or Translator("en")
        self.styles = getSampleStyleSheet()
        self._register_fonts()
        self._setup_custom_styles()

    def _register_fonts(self):
        try:
            base_dir = str(Path(__file__).resolve().parent.parent)
            # Candidates for fonts that support Unicode (including Cyrillic/Russian)
            regular_candidates = [
                os.path.join(base_dir, "resources", "fonts", "DejaVuSans.ttf"),
                os.path.join(base_dir, "resources", "fonts", "DejaVuSansCondensed.ttf"),
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux (Debian/Ubuntu)
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",  # Linux (Red Hat/Fedora)
                "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",  # macOS
                "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS fallback
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows
                "C:\\Windows\\Fonts\\DejaVuSans.ttf",
            ]
            bold_candidates = [
                os.path.join(base_dir, "resources", "fonts", "DejaVuSans-Bold.ttf"),
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (Debian/Ubuntu)
                "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",  # Linux (Red Hat/Fedora)
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
                "C:\\Windows\\Fonts\\arialbd.ttf",  # Windows
            ]
            
            chosen_regular = None
            chosen_bold = None
            
            for p in regular_candidates:
                if os.path.exists(p):
                    chosen_regular = p
                    break
            
            for p in bold_candidates:
                if os.path.exists(p):
                    chosen_bold = p
                    break
            
            if chosen_regular:
                pdfmetrics.registerFont(TTFont("SGSans", chosen_regular))
                # If no separate bold font found, use regular for bold too
                if chosen_bold:
                    pdfmetrics.registerFont(TTFont("SGSans-Bold", chosen_bold))
                else:
                    pdfmetrics.registerFont(TTFont("SGSans-Bold", chosen_regular))
                self._font_regular = "SGSans"
                self._font_bold = "SGSans-Bold"
            else:
                # Fallback to default fonts (won't work for Russian)
                self._font_regular = "Helvetica"
                self._font_bold = "Helvetica-Bold"
        except Exception:
            # Fallback to default fonts (won't work for Russian)
            self._font_regular = "Helvetica"
            self._font_bold = "Helvetica-Bold"
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report."""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#2E86AB'),
            fontName=self._font_bold
        )
        
        # Section header style
        self.section_style = ParagraphStyle(
            'CustomSection',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#A23B72'),
            fontName=self._font_bold
        )
        
        # Subsection style
        self.subsection_style = ParagraphStyle(
            'CustomSubsection',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=HexColor('#F18F01'),
            fontName=self._font_bold
        )
        
        # Normal text style
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            fontName=self._font_regular
        )
        
        # Score style
        self.score_style = ParagraphStyle(
            'CustomScore',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=8,
            alignment=TA_CENTER,
            textColor=HexColor('#2E86AB'),
            fontName=self._font_bold
        )

    class RoundedPanel(Flowable):
        def __init__(self, inner_flowables: List[Any], bg_color: str, accent_color: str, padding: int = 8, radius: int = 6):
            super().__init__()
            self.children = inner_flowables
            self.child_sizes: List[tuple[int, int]] = []
            self.bg_color = HexColor(bg_color)
            self.accent_color = HexColor(accent_color)
            self.padding = padding
            self.radius = radius
            self._w = 0
            self._h = 0

        def wrap(self, availWidth, availHeight):
            inner_w = max(10, availWidth - 2 * self.padding)
            total_h = 0
            max_w = 0
            sizes: List[tuple[int, int]] = []
            for child in self.children:
                w, h = child.wrap(inner_w, availHeight)
                sizes.append((w, h))
                total_h += h
                if w > max_w:
                    max_w = w
            self.child_sizes = sizes
            self._w = min(availWidth, max_w + 2 * self.padding)
            self._h = total_h + 2 * self.padding
            return self._w, self._h

        def draw(self):
            c = self.canv
            c.saveState()
            c.setFillColor(self.bg_color)
            c.roundRect(0, 0, self._w, self._h, self.radius, stroke=0, fill=1)
            c.setFillColor(self.accent_color)
            c.rect(0, 0, 4, self._h, stroke=0, fill=1)
            c.restoreState()
            y = self._h - self.padding
            x = self.padding
            for (child, (w, h)) in zip(self.children, self.child_sizes):
                y -= h
                child.drawOn(c, x, y)
    
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
    
    def _get_score_color(self, score: float, max_score: float = 5.0, higher_better: bool = True) -> str:
        percentage = (score / max_score) * 100
        if higher_better:
            if percentage >= 80:
                return '#4CAF50'
            elif percentage >= 60:
                return '#FF9800'
            elif percentage >= 40:
                return '#FFC107'
            else:
                return '#F44336'
        else:
            if percentage <= 20:
                return '#4CAF50'
            elif percentage <= 40:
                return '#FF9800'
            elif percentage <= 60:
                return '#FFC107'
            else:
                return '#F44336'
    
    def _create_header(self, canvas_obj: canvas.Canvas):
        canvas_obj.saveState()
        canvas_obj.setFont(self._font_bold, 11)
        canvas_obj.setFillColor(HexColor('#2E86AB'))
        width, height = A4
        canvas_obj.drawString(50, height - 40, self.translator.t('report_title'))
        canvas_obj.restoreState()

    def _create_footer(self, canvas_obj: canvas.Canvas):
        canvas_obj.saveState()
        canvas_obj.setFont(self._font_regular, 8)
        canvas_obj.setFillColor(black)
        width, _ = A4
        canvas_obj.drawString(50, 40, f"{self.translator.t('report_generated')} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        canvas_obj.drawRightString(width - 50, 40, f"{self.translator.t('report_page')} {canvas_obj.getPageNumber()}")
        canvas_obj.restoreState()
    
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
        severity_text = self.translator.get_priority_text(severity)
        
        severity_label = f"{severity_text} ({self.translator.t('severity_label')} {severity}/3)"
        severity_table = Table([[severity_label]])
        severity_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor(severity_color)),
            ('TEXTCOLOR', (0, 0), (-1, -1), white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), self._font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        inner = [
            Paragraph(f"<b>{index}. {evaluation_element}</b>", self.subsection_style),
            Spacer(1, 4),
            severity_table,
            Spacer(1, 6),
            Paragraph(f"<b>{self.translator.t('suggestion_label')}</b> {suggestion}", self.normal_style),
        ]
        story.append(self.RoundedPanel(inner, bg_color="#fff3f3" if severity==3 else ("#fff9e6" if severity==2 else "#eaf6ee"), accent_color=severity_color))
        story.append(Spacer(1, 10))
    
    def _add_criteria_evaluation(self, story: List, criteria: Criteria, eval_result: Any, include_header: bool = True):
        """Add a criteria evaluation to the report."""
        criteria_name = criteria.value.replace('_', ' ').title()
        if include_header:
            story.append(Paragraph(f"<b>{criteria_name}</b>", self.section_style))
        
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
            
            severity_score = total_severity / len(evaluation_results) if evaluation_results else 0
            score_percentage = (severity_score / 3.0) * 100
            
            severity_score_color = self._get_score_color(severity_score, 3.0, False)
            severity_score_text = f"{self.translator.t('total_severity')} {severity_score:.1f}/3.0 ({score_percentage:.0f}%)"
            
            score_style = ParagraphStyle(
                'ScoreStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=HexColor(severity_score_color),
                alignment=TA_CENTER,
                fontName=self._font_bold
            )
            panel_items: List[Any] = [Paragraph(f"<b>{severity_score_text}</b>", score_style)]
            if hasattr(eval_result, 'score'):
                score = eval_result.score
                score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                overall_color = self._get_score_color(score, 5.0)
                overall_style = ParagraphStyle(
                    'ScoreStyleOverall',
                    parent=self.styles['Normal'],
                    fontSize=12,
                    textColor=HexColor(overall_color),
                    alignment=TA_CENTER,
                    fontName=self._font_bold
                )
                panel_items.append(Paragraph(f"<b>Overall Score: {score:.1f}/5.0 ({score_percentage:.0f}%)</b>", overall_style))
            story.append(self.RoundedPanel(panel_items, bg_color="#ffffff", accent_color=severity_score_color))
                
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
                
                severity_score = total_severity / len(evaluation_results) if evaluation_results else 0
                score_percentage = (severity_score / 3.0) * 100
                
                severity_score_color = self._get_score_color(severity_score, 3.0, False)
                severity_score_text = f"Total Severity: {severity_score:.1f}/3.0 ({score_percentage:.0f}%)"
                
                score_style = ParagraphStyle(
                    'ScoreStyle',
                    parent=self.styles['Normal'],
                    fontSize=12,
                    textColor=HexColor(severity_score_color),
                    alignment=TA_CENTER,
                    fontName=self._font_bold
                )
                story.append(self.RoundedPanel([Paragraph(f"<b>{severity_score_text}</b>", score_style)], bg_color="#ffffff", accent_color=severity_score_color))
                
            elif 'score' in eval_result:
                score = eval_result['score']
                score_percentage = (score / 5.0) * 100 if score <= 5 else (score / 10.0) * 100
                score_color = self._get_score_color(score, 5.0)
                
                story.append(self.RoundedPanel([Paragraph(f"<b>{self.translator.t('score_label')} {score:.1f}/5.0 ({score_percentage:.0f}%)</b>", self.score_style)], bg_color="#ffffff", accent_color=score_color))
                
                if 'comments' in eval_result:
                    story.append(Paragraph(f"<b>{self.translator.t('comments')}</b> {eval_result['comments']}", self.normal_style))
                if 'recommendations' in eval_result:
                    story.append(Paragraph(f"<b>{self.translator.t('recommendations')}</b> {eval_result['recommendations']}", self.normal_style))
            else:
                story.append(Paragraph(str(eval_result), self.normal_style))
        else:
            # Fallback for other formats
            story.append(Paragraph(str(eval_result), self.normal_style))
        
        story.append(Spacer(1, 20))
    
    def generate_report(self, evaluation: FullEvaluation, presentation_name: str = "Unknown", slide_images: Optional[List[str]] = None) -> BytesIO:
        """Generate a comprehensive PDF report for the evaluation."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=90,
            bottomMargin=72
        )
        
        story = []
        
        # Title page
        story.append(Paragraph(self.translator.t('report_title'), self.title_style))
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"<b>{self.translator.t('report_presentation')}</b> {presentation_name}", self.normal_style))
        story.append(Paragraph(f"<b>{self.translator.t('report_date')}</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", self.normal_style))
        story.append(Paragraph(f"<b>{self.translator.t('report_total_slides')}</b> {len(evaluation.slide_evaluations)}", self.normal_style))
        
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
                fontName=self._font_bold
            )
            
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"<b>{self.translator.t('overall_score_label')} {evaluation.overall_score:.2f}/5.0 ({overall_percentage:.0f}%)</b>", overall_style))
        
        story.append(PageBreak())
        
        # TL;DR
        if evaluation.tldr:
            story.append(Paragraph(self.translator.t('report_tldr'), self.section_style))
            story.append(self.RoundedPanel([Paragraph(evaluation.tldr, self.normal_style)], bg_color="#fff7e0", accent_color="#ffb300"))
            story.append(Spacer(1, 20))

        # long summary
        if evaluation.summary:
            story.append(Paragraph(self.translator.t('report_summary'), self.section_style))
            story.append(self.RoundedPanel([Paragraph(evaluation.summary, self.normal_style)], bg_color="#fffde7", accent_color="#fbc02d"))
            story.append(PageBreak())
        
        # Deck-Level Evaluations
        if evaluation.deck_evaluations and evaluation.deck_evaluations.evaluations:
            story.append(Paragraph(self.translator.t('report_deck_title'), self.section_style))
            
            for criteria, eval_result in evaluation.deck_evaluations.evaluations.items():
                self._add_criteria_evaluation(story, criteria, eval_result)
            
            story.append(PageBreak())
        
        # Slide-Level Evaluations with images
        if evaluation.slide_evaluations:
            story.append(Paragraph(self.translator.t('report_slide_title'), self.section_style))
            for slide_idx, slide_eval in enumerate(evaluation.slide_evaluations, 1):
                story.append(Paragraph(f"{self.translator.t('report_slide')} {slide_idx}", self.subsection_style))
                # Image below the title
                img_flow = None
                if slide_images and 0 <= slide_idx-1 < len(slide_images) and slide_images[slide_idx-1] and os.path.exists(slide_images[slide_idx-1]):
                    try:
                        img = Image(slide_images[slide_idx-1])
                        img._restrictSize(420, 300)
                        img_flow = img
                    except Exception:
                        img_flow = None
                if img_flow:
                    story.append(img_flow)
                    story.append(Spacer(1, 10))
                # Evaluations stacked below image
                if slide_eval.evaluations:
                    for criteria, eval_result in slide_eval.evaluations.items():
                        self._add_criteria_evaluation(story, criteria, eval_result, include_header=True)
                else:
                    story.append(Paragraph(self.translator.t('report_no_evaluations'), self.normal_style))
                story.append(Spacer(1, 20))
        
        # Build PDF
        def first_page(c: canvas.Canvas, d):
            self._create_footer(c)
        
        def later_pages(c: canvas.Canvas, d):
            self._create_header(c)
            self._create_footer(c)
        
        doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
        
        buffer.seek(0)
        return buffer
    
    def save_report(self, evaluation: FullEvaluation, output_path: str, presentation_name: str = "Unknown", slide_images: Optional[List[str]] = None) -> str:
        """Generate and save a PDF report to the specified path."""
        buffer = self.generate_report(evaluation, presentation_name, slide_images)
        
        with open(output_path, 'wb') as f:
            f.write(buffer.getvalue())
        
        return output_path
