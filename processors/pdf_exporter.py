"""
PDF Exporter - USING WEASYPRINT FOR PERFECT BENGALI SUPPORT
WeasyPrint handles Unicode/Bengali fonts automatically
Generates beautiful PDFs with HTML/CSS
"""

from pathlib import Path
from typing import List, Dict
import re
from weasyprint import HTML, CSS
from config import config

class PDFExporter:
    def __init__(self):
        self.waiting_for_name = {}  # {user_id: questions}
        print("✅ PDF Exporter initialized (WeasyPrint)")
    
    def cleanup_questions(self, questions: List[Dict]) -> List[Dict]:
        """Remove tags and URLs from questions"""
        cleaned = []
        
        for q in questions:
            cleaned_q = q.copy()
            
            # Clean question text
            text = q.get('question_description', '')
            text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
            text = re.sub(r'http\S+', '', text)  # Remove URLs
            text = text.strip()
            cleaned_q['question_description'] = text
            
            # Clean options
            cleaned_opts = []
            for opt in q.get('options', []):
                opt = re.sub(r'<[^>]+>', '', opt)
                opt = re.sub(r'http\S+', '', opt)
                cleaned_opts.append(opt.strip())
            cleaned_q['options'] = cleaned_opts
            
            # Clean explanation
            expl = q.get('explanation', '')
            expl = re.sub(r'<[^>]+>', '', expl)
            expl = re.sub(r'http\S+', '', expl)
            cleaned_q['explanation'] = expl.strip()
            
            cleaned.append(cleaned_q)
        
        return cleaned
    
    def generate_beautiful_pdf(self, questions: List[Dict], output_path: Path, title: str = "MCQ Questions"):
        """
        Generate beautiful PDF using WeasyPrint
        Perfect Bengali/Unicode support with Google Fonts
        """
        html_content = self._generate_html(questions, title)
        
        # Generate PDF
        HTML(string=html_content).write_pdf(output_path)
        
        print(f"✅ PDF generated: {output_path} ({len(questions)} questions)")
    
    def _generate_html(self, questions: List[Dict], title: str) -> str:
        """Generate HTML with embedded CSS"""
        
        # Build questions HTML
        questions_html = ""
        for idx, q in enumerate(questions, 1):
            question_text = self._escape_html(q.get('question_description', ''))
            explanation = self._escape_html(q.get('explanation', ''))
            correct_idx = q.get('correct_answer_index', 0)
            
            # Options HTML
            options_html = ""
            for opt_idx, opt in enumerate(q.get('options', [])):
                if opt:
                    opt_text = self._escape_html(opt)
                    letter = chr(65 + opt_idx)  # A, B, C, D...
                    
                    if opt_idx == correct_idx:
                        # Correct answer - green background
                        options_html += f"""
                        <div class="option correct-option">
                            <span class="option-letter">{letter}.</span>
                            <span class="option-text">{opt_text}</span>
                        </div>
                        """
                    else:
                        # Regular option
                        options_html += f"""
                        <div class="option">
                            <span class="option-letter">{letter}.</span>
                            <span class="option-text">{opt_text}</span>
                        </div>
                        """
            
            # Explanation box
            explanation_html = ""
            if explanation:
                explanation_html = f"""
                <div class="explanation">
                    <div class="explanation-title">📝 Explanation:</div>
                    <div class="explanation-text">{explanation}</div>
                </div>
                """
            
            # Question block
            questions_html += f"""
            <div class="question-block">
                <div class="question-header">Question {idx}</div>
                <div class="question-text">{question_text}</div>
                {options_html}
                {explanation_html}
            </div>
            """
        
        # Complete HTML document
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+Bengali:wght@400;600;700&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Noto Sans', 'Noto Sans Bengali', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #4A90E2;
        }}
        
        .header h1 {{
            font-size: 24pt;
            color: #4A90E2;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .header .subtitle {{
            font-size: 12pt;
            color: #666;
        }}
        
        .question-block {{
            margin-bottom: 25px;
            page-break-inside: avoid;
        }}
        
        .question-header {{
            background: #4A90E2;
            color: white;
            padding: 8px 12px;
            font-weight: 600;
            font-size: 13pt;
            border-radius: 5px 5px 0 0;
        }}
        
        .question-text {{
            background: #f8f9fa;
            padding: 12px;
            font-size: 11pt;
            border-left: 3px solid #4A90E2;
            margin-bottom: 10px;
        }}
        
        .option {{
            padding: 8px 12px;
            margin: 5px 0;
            border-left: 3px solid #ddd;
            background: white;
        }}
        
        .correct-option {{
            background: #d4edda !important;
            border-left: 3px solid #28a745 !important;
            font-weight: 600;
        }}
        
        .option-letter {{
            font-weight: 700;
            color: #4A90E2;
            margin-right: 8px;
        }}
        
        .correct-option .option-letter {{
            color: #28a745;
        }}
        
        .explanation {{
            background: #fff3cd;
            border-left: 3px solid #ffc107;
            padding: 10px 12px;
            margin-top: 10px;
        }}
        
        .explanation-title {{
            font-weight: 600;
            color: #856404;
            margin-bottom: 5px;
        }}
        
        .explanation-text {{
            color: #333;
            font-size: 10pt;
        }}
        
        @page {{
            margin: 2cm;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{self._escape_html(title)}</h1>
        <div class="subtitle">Total Questions: {len(questions)}</div>
    </div>
    
    {questions_html}
</body>
</html>
"""
        return html
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters"""
        if not text:
            return ""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))
    
    # ===== INTERACTIVE PDF NAME INPUT =====
    
    def is_waiting_for_name(self, user_id: int) -> bool:
        """Check if waiting for PDF name from user"""
        return user_id in self.waiting_for_name
    
    async def handle_pdf_export_start(self, update, context, questions):
        """Start PDF export process"""
        user_id = update.effective_user.id
        query = update.callback_query
        
        self.waiting_for_name[user_id] = questions
        
        await query.edit_message_text(
            "📝 *PDF Export*\n\n"
            "Send me a name for the PDF file.\n\n"
            "Example: `Anatomy_Quiz_2024`",
            parse_mode='Markdown'
        )
    
    async def handle_pdf_name_input(self, update, context):
        """Handle PDF name input from user"""
        user_id = update.effective_user.id
        
        if user_id not in self.waiting_for_name:
            return
        
        questions = self.waiting_for_name.pop(user_id)
        pdf_name = update.message.text.strip()
        
        # Sanitize filename
        pdf_name = re.sub(r'[^\w\s-]', '', pdf_name)
        pdf_name = re.sub(r'[-\s]+', '_', pdf_name)
        
        if not pdf_name:
            pdf_name = "quiz"
        
        # Generate PDF
        msg = await update.message.reply_text("📄 Generating beautiful PDF...")
        
        try:
            pdf_path = config.OUTPUT_DIR / f"{pdf_name}.pdf"
            
            cleaned = self.cleanup_questions(questions)
            self.generate_beautiful_pdf(cleaned, pdf_path, pdf_name)
            
            # Send PDF
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"{pdf_name}.pdf",
                    caption=f"📄 **{pdf_name}**\n\n"
                            f"📊 Questions: {len(questions)}\n"
                            f"🎨 Beautiful format with Bengali support!",
                    parse_mode='Markdown'
                )
            
            await msg.delete()
            pdf_path.unlink(missing_ok=True)
            
        except Exception as e:
            print(f"❌ PDF generation error: {e}")
            import traceback
            traceback.print_exc()
            
            await msg.edit_text(
                f"❌ PDF generation failed:\n`{str(e)[:200]}`",
                parse_mode='Markdown'
            )
    
    async def handle_format_selection(self, update, context, format_type):
        """Handle PDF format selection"""
        # Format selection removed - only one beautiful format now
        pass

# Global instance
pdf_exporter = PDFExporter()
