"""
PDF Exporter - Grid Layout Modes
Mode 1: Grid with answer boxes at bottom
Mode 2: Grid with inline answer boxes
"""

import re
from pathlib import Path
from typing import List, Dict
from config import config

# Try importing WeasyPrint
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
        Generate PDF with grid layout
        mode1: Answer boxes at bottom of each question
        mode2: Answer boxes inline with each question
        """
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint not installed. Run: pip install weasyprint")
        
        if mode == 'mode1':
            html = self._generate_mode1_html(questions, title)
        else:
            html = self._generate_mode2_html(questions, title)
        
        # Generate PDF
        HTML(string=html).write_pdf(str(output_path))
        print(f"✅ PDF {mode} created: {len(questions)} questions")
    
    def _generate_mode1_html(self, questions: List[Dict], title: str) -> str:
        """Mode 1: Grid layout with answer boxes at bottom"""
        
        # Split questions into left and right columns
        mid_point = (len(questions) + 1) // 2
        left_questions = questions[:mid_point]
        right_questions = questions[mid_point:]
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 15mm 12mm;
        }}
        
        body {{
            font-family: 'Noto Sans', 'Noto Sans Bengali', Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.4;
            color: #000;
        }}
        
        .header {{
            text-align: center;
            background: linear-gradient(to right, #ffebee, #ffe0e6);
            border: 2px solid #d32f2f;
            padding: 8px;
            margin-bottom: 12px;
            border-radius: 4px;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 14pt;
            color: #b71c1c;
            font-weight: bold;
        }}
        
        .container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10mm;
        }}
        
        .question-box {{
            break-inside: avoid;
            margin-bottom: 12px;
            page-break-inside: avoid;
        }}
        
        .question-number {{
            font-weight: bold;
            color: #1976d2;
            margin-bottom: 4px;
        }}
        
        .question-text {{
            margin-bottom: 6px;
            line-height: 1.5;
        }}
        
        .options {{
            margin-left: 8px;
        }}
        
        .option {{
            margin: 3px 0;
            display: flex;
            align-items: flex-start;
        }}
        
        .option-letter {{
            min-width: 25px;
            font-weight: 600;
        }}
        
        .option-text {{
            flex: 1;
        }}
        
        .answer-box {{
            background: linear-gradient(to bottom, #ffebee, #fff8f8);
            border-left: 3px solid #e53935;
            padding: 6px 8px;
            margin-top: 6px;
            font-size: 8.5pt;
            border-radius: 2px;
        }}
        
        .answer-label {{
            color: #c62828;
            font-weight: bold;
            margin-bottom: 2px;
        }}
        
        .answer-text {{
            color: #424242;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
    </div>
    
    <div class="container">
        <div class="left-column">
"""
        
        # Left column questions
        for idx, q in enumerate(left_questions, 1):
            question_text = q.get('question_description', '')
            options = q.get('options', [])
            correct_option = q.get('correct_option', 'A')
            explanation = q.get('explanation', '')
            
            if not question_text or not options:
                continue
            
            html += f"""
            <div class="question-box">
                <div class="question-number">{idx:02d}. {question_text}</div>
                <div class="options">
"""
            
            # Options
            for opt_idx, opt in enumerate(options):
                letter = chr(65 + opt_idx)
                html += f"""
                    <div class="option">
                        <span class="option-letter">({letter})</span>
                        <span class="option-text">{opt}</span>
                    </div>
"""
            
            html += """
                </div>
"""
            
            # Answer box
            html += f"""
                <div class="answer-box">
                    <div class="answer-label">উত্তরঃ {correct_option}</div>
"""
            
            if explanation:
                html += f"""
                    <div class="answer-text">{explanation}</div>
"""
            
            html += """
                </div>
            </div>
"""
        
        html += """
        </div>
        <div class="right-column">
"""
        
        # Right column questions
        start_num = mid_point + 1
        for idx, q in enumerate(right_questions, start_num):
            question_text = q.get('question_description', '')
            options = q.get('options', [])
            correct_option = q.get('correct_option', 'A')
            explanation = q.get('explanation', '')
            
            if not question_text or not options:
                continue
            
            html += f"""
            <div class="question-box">
                <div class="question-number">{idx:02d}. {question_text}</div>
                <div class="options">
"""
            
            # Options
            for opt_idx, opt in enumerate(options):
                letter = chr(65 + opt_idx)
                html += f"""
                    <div class="option">
                        <span class="option-letter">({letter})</span>
                        <span class="option-text">{opt}</span>
                    </div>
"""
            
            html += """
                </div>
"""
            
            # Answer box
            html += f"""
                <div class="answer-box">
                    <div class="answer-label">উত্তরঃ {correct_option}</div>
"""
            
            if explanation:
                html += f"""
                    <div class="answer-text">{explanation}</div>
"""
            
            html += """
                </div>
            </div>
"""
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_mode2_html(self, questions: List[Dict], title: str) -> str:
        """Mode 2: Grid layout with compact answer display"""
        
        # Split questions into left and right columns
        mid_point = (len(questions) + 1) // 2
        left_questions = questions[:mid_point]
        right_questions = questions[mid_point:]
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 15mm 12mm;
        }}
        
        body {{
            font-family: 'Noto Sans', 'Noto Sans Bengali', Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.4;
            color: #000;
        }}
        
        .header {{
            text-align: center;
            background: linear-gradient(to right, #e3f2fd, #e1f5fe);
            border: 2px solid #1976d2;
            padding: 8px;
            margin-bottom: 12px;
            border-radius: 4px;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 14pt;
            color: #0d47a1;
            font-weight: bold;
        }}
        
        .container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10mm;
        }}
        
        .question-box {{
            break-inside: avoid;
            margin-bottom: 12px;
            page-break-inside: avoid;
            border: 1px solid #e0e0e0;
            padding: 8px;
            border-radius: 4px;
            background: #fafafa;
        }}
        
        .question-number {{
            font-weight: bold;
            color: #1565c0;
            margin-bottom: 4px;
        }}
        
        .question-text {{
            margin-bottom: 6px;
            line-height: 1.5;
        }}
        
        .options {{
            margin-left: 8px;
            margin-bottom: 6px;
        }}
        
        .option {{
            margin: 3px 0;
            display: flex;
            align-items: flex-start;
        }}
        
        .option-letter {{
            min-width: 25px;
            font-weight: 600;
        }}
        
        .option-text {{
            flex: 1;
        }}
        
        .option-correct {{
            background: #e8f5e9;
            margin: 0 -4px;
            padding: 2px 4px;
            border-radius: 2px;
        }}
        
        .answer-inline {{
            background: linear-gradient(to bottom, #e3f2fd, #f5f9ff);
            border-left: 3px solid #1976d2;
            padding: 5px 8px;
            margin-top: 6px;
            font-size: 8.5pt;
            border-radius: 2px;
        }}
        
        .answer-label {{
            color: #0d47a1;
            font-weight: bold;
            display: inline;
        }}
        
        .answer-value {{
            color: #2e7d32;
            font-weight: bold;
            display: inline;
            margin-left: 4px;
        }}
        
        .explanation {{
            color: #424242;
            margin-top: 3px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
    </div>
    
    <div class="container">
        <div class="left-column">
"""
        
        # Left column questions
        for idx, q in enumerate(left_questions, 1):
            question_text = q.get('question_description', '')
            options = q.get('options', [])
            correct_option = q.get('correct_option', 'A')
            correct_idx = q.get('correct_answer_index', 0)
            explanation = q.get('explanation', '')
            
            if not question_text or not options:
                continue
            
            html += f"""
            <div class="question-box">
                <div class="question-number">{idx:02d}. {question_text}</div>
                <div class="options">
"""
            
            # Options with correct answer highlighted
            for opt_idx, opt in enumerate(options):
                letter = chr(65 + opt_idx)
                is_correct = (opt_idx == correct_idx)
                option_class = 'option-correct' if is_correct else ''
                
                html += f"""
                    <div class="option {option_class}">
                        <span class="option-letter">({letter})</span>
                        <span class="option-text">{opt}</span>
                    </div>
"""
            
            html += """
                </div>
"""
            
            # Inline answer
            html += f"""
                <div class="answer-inline">
                    <span class="answer-label">✓ উত্তরঃ</span>
                    <span class="answer-value">{correct_option}</span>
"""
            
            if explanation:
                html += f"""
                    <div class="explanation">📝 {explanation}</div>
"""
            
            html += """
                </div>
            </div>
"""
        
        html += """
        </div>
        <div class="right-column">
"""
        
        # Right column questions
        start_num = mid_point + 1
        for idx, q in enumerate(right_questions, start_num):
            question_text = q.get('question_description', '')
            options = q.get('options', [])
            correct_option = q.get('correct_option', 'A')
            correct_idx = q.get('correct_answer_index', 0)
            explanation = q.get('explanation', '')
            
            if not question_text or not options:
                continue
            
            html += f"""
            <div class="question-box">
                <div class="question-number">{idx:02d}. {question_text}</div>
                <div class="options">
"""
            
            # Options with correct answer highlighted
            for opt_idx, opt in enumerate(options):
                letter = chr(65 + opt_idx)
                is_correct = (opt_idx == correct_idx)
                option_class = 'option-correct' if is_correct else ''
                
                html += f"""
                    <div class="option {option_class}">
                        <span class="option-letter">({letter})</span>
                        <span class="option-text">{opt}</span>
                    </div>
"""
            
            html += """
                </div>
"""
            
            # Inline answer
            html += f"""
                <div class="answer-inline">
                    <span class="answer-label">✓ উত্তরঃ</span>
                    <span class="answer-value">{correct_option}</span>
"""
            
            if explanation:
                html += f"""
                    <div class="explanation">📝 {explanation}</div>
"""
            
            html += """
                </div>
            </div>
"""
        
        html += """
        </div>
    </div>
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
