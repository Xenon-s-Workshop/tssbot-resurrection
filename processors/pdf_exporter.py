"""
PDF Exporter - TWO MODES with Bengali Support
Mode 1: Answer key at end (ReportLab)
Mode 2: Inline answers (WeasyPrint)
"""

import re
from pathlib import Path
from typing import List, Dict
from config import config

# Try importing both libraries
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ ReportLab not available")

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    print("⚠️ WeasyPrint not available")

class PDFExporter:
    def __init__(self):
        self.waiting_for_name = {}
        print("✅ PDF Exporter initialized")
    
    def cleanup_questions(self, questions: List[Dict]) -> List[Dict]:
        """Clean HTML tags and URLs from questions"""
        cleaned = []
        
        for q in questions:
            cleaned_q = q.copy()
            
            # Clean question text
            if 'question_description' in cleaned_q:
                text = cleaned_q['question_description']
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'http[s]?://\S+', '[URL]', text)
                cleaned_q['question_description'] = text.strip()
            
            # Clean options
            if 'options' in cleaned_q:
                cleaned_opts = []
                for opt in cleaned_q['options']:
                    opt = re.sub(r'<[^>]+>', '', str(opt))
                    opt = re.sub(r'http[s]?://\S+', '[URL]', opt)
                    cleaned_opts.append(opt.strip())
                cleaned_q['options'] = cleaned_opts
            
            # Clean explanation
            if 'explanation' in cleaned_q:
                exp = cleaned_q['explanation']
                exp = re.sub(r'<[^>]+>', '', str(exp))
                exp = re.sub(r'http[s]?://\S+', '[URL]', exp)
                cleaned_q['explanation'] = exp.strip()
            
            cleaned.append(cleaned_q)
        
        return cleaned
    
    def generate_beautiful_pdf(self, questions: List[Dict], output_path: Path, title: str, mode: str = 'mode1'):
        """
        Generate PDF with selected mode
        mode1: Answer key at end (ReportLab)
        mode2: Inline answers (WeasyPrint)
        """
        if mode == 'mode1':
            return self._generate_mode1_reportlab(questions, output_path, title)
        else:
            return self._generate_mode2_weasyprint(questions, output_path, title)
    
    def _generate_mode1_reportlab(self, questions: List[Dict], output_path: Path, title: str):
        """Mode 1: Answer key at end using ReportLab"""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab not installed. Run: pip install reportlab")
        
        # Create PDF
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor='#2C3E50',
            spaceAfter=20,
            alignment=TA_LEFT
        )
        
        question_style = ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=8
        )
        
        option_style = ParagraphStyle(
            'Option',
            parent=styles['Normal'],
            fontSize=10,
            leading=13,
            leftIndent=10,
            spaceAfter=4
        )
        
        answer_style = ParagraphStyle(
            'Answer',
            parent=styles['Normal'],
            fontSize=10,
            leading=13,
            spaceAfter=6
        )
        
        # Build content
        story = []
        
        # Title
        story.append(Paragraph(f"<b>{title}</b>", title_style))
        story.append(Spacer(1, 10*mm))
        
        # Questions section
        story.append(Paragraph("<b>Questions:</b>", title_style))
        story.append(Spacer(1, 5*mm))
        
        question_count = 0
        for idx, q in enumerate(questions, 1):
            question_text = q.get('question_description', '')
            options = q.get('options', [])
            
            if not question_text or not options:
                continue
            
            question_count += 1
            
            # Question
            story.append(Paragraph(f"<b>Q{idx}.</b> {question_text}", question_style))
            
            # Options
            for opt_idx, opt in enumerate(options):
                letter = chr(65 + opt_idx)
                story.append(Paragraph(f"   {letter}) {opt}", option_style))
            
            story.append(Spacer(1, 5*mm))
            
            # Page break after ~6 questions
            if idx % 6 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        # Answer section on new page
        story.append(PageBreak())
        story.append(Paragraph("<b>Answer Key:</b>", title_style))
        story.append(Spacer(1, 5*mm))
        
        for idx, q in enumerate(questions, 1):
            correct_option = q.get('correct_option', 'A')
            explanation = q.get('explanation', '')
            
            answer_text = f"<b>{idx})</b> Answer: <b>{correct_option}</b>"
            if explanation:
                answer_text += f" - {explanation}"
            
            story.append(Paragraph(answer_text, answer_style))
            story.append(Spacer(1, 3*mm))
        
        # Build PDF
        doc.build(story)
        print(f"✅ PDF Mode 1 created: {question_count} questions")
    
    def _generate_mode2_weasyprint(self, questions: List[Dict], output_path: Path, title: str):
        """Mode 2: Inline answers using WeasyPrint"""
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint not installed. Run: pip install weasyprint")
        
        html = self._generate_html_mode2(questions, title)
        
        # Generate PDF
        HTML(string=html).write_pdf(str(output_path))
        print(f"✅ PDF Mode 2 created: {len(questions)} questions")
    
    def _generate_html_mode2(self, questions: List[Dict], title: str) -> str:
        """Generate HTML for mode 2"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 20mm;
        }}
        
        body {{
            font-family: 'Noto Sans', 'Noto Sans Bengali', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }}
        
        h1 {{
            color: #2C3E50;
            font-size: 20pt;
            margin-bottom: 20px;
            border-bottom: 2px solid #3498DB;
            padding-bottom: 10px;
        }}
        
        .question {{
            margin-bottom: 25px;
            page-break-inside: avoid;
        }}
        
        .question-header {{
            font-weight: bold;
            color: #2980B9;
            margin-bottom: 8px;
            font-size: 12pt;
        }}
        
        .options {{
            margin: 10px 0 10px 15px;
        }}
        
        .option {{
            margin: 5px 0;
        }}
        
        .answer-box {{
            background-color: #E8F8F5;
            border-left: 4px solid #27AE60;
            padding: 10px;
            margin-top: 10px;
        }}
        
        .answer {{
            color: #27AE60;
            font-weight: bold;
        }}
        
        .explanation {{
            color: #555;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
"""
        
        for idx, q in enumerate(questions, 1):
            question_text = q.get('question_description', '')
            options = q.get('options', [])
            correct_option = q.get('correct_option', 'A')
            explanation = q.get('explanation', '')
            
            if not question_text or not options:
                continue
            
            html += f"""
    <div class="question">
        <div class="question-header">Q{idx}. {question_text}</div>
        <div class="options">
"""
            
            for opt_idx, opt in enumerate(options):
                letter = chr(65 + opt_idx)
                html += f'            <div class="option">{letter}) {opt}</div>\n'
            
            html += """        </div>
        <div class="answer-box">
"""
            html += f'            <div class="answer">✓ Answer: {correct_option}</div>\n'
            
            if explanation:
                html += f'            <div class="explanation">📝 Explanation: {explanation}</div>\n'
            
            html += """        </div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html
    
    def is_waiting_for_name(self, user_id: int) -> bool:
        """Check if waiting for PDF name"""
        return user_id in self.waiting_for_name
    
    async def handle_pdf_name_input(self, update, context):
        """Handle PDF name input"""
        user_id = update.effective_user.id
        
        if user_id not in self.waiting_for_name:
            return
        
        pdf_name = update.message.text.strip()
        data = self.waiting_for_name.pop(user_id)
        
        questions = data['questions']
        
        # Generate PDF
        pdf_path = config.OUTPUT_DIR / f"{pdf_name}.pdf"
        
        settings = data.get('settings', {})
        pdf_mode = settings.get('pdf_mode', 'mode1')
        
        try:
            cleaned = self.cleanup_questions(questions)
            self.generate_beautiful_pdf(cleaned, pdf_path, pdf_name, mode=pdf_mode)
            
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"{pdf_name}.pdf",
                    caption=f"📄 PDF • {len(questions)}Q • {pdf_mode}"
                )
            
            pdf_path.unlink(missing_ok=True)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ **PDF Generation Failed**\n\n`{str(e)[:200]}`",
                parse_mode='Markdown'
            )

# Global instance
pdf_exporter = PDFExporter()
