"""
PDF Exporter - Selenium-based with 2 HTML Formats
Format 1: Practice sheet with inline answers
Format 2: Questions only, then answers table
"""

import re
import os
import base64
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import List, Dict
from jinja2 import Template
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.print_page_options import PrintOptions
from webdriver_manager.chrome import ChromeDriverManager
from config import config

logger = logging.getLogger(__name__)

class PDFExporter:
    def __init__(self):
        self.waiting_for_name = {}
        self.driver = None
        self.answer_circles = {'A': 'Ⓐ', 'B': 'Ⓑ', 'C': 'Ⓒ', 'D': 'Ⓓ', 'E': 'Ⓔ'}
        print("✅ PDF Exporter initialized")
    
    def initialize_browser(self):
        """Initialize headless Chrome browser"""
        if self.driver:
            return
        
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-software-rasterizer')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("✅ Chrome browser initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize browser: {e}")
            raise
    
    def cleanup_browser(self):
        """Cleanup browser"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("✅ Browser cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up browser: {e}")
    
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
    
    def check_short_option(self, options: Dict) -> bool:
        """Check if options are short enough for table format"""
        total_length = sum(len(str(opt)) for opt in options.values())
        return total_length < 120
    
    def prepare_questions(self, questions_data):
        """Prepare questions with format detection"""
        prepared_questions = []
        
        for q in questions_data:
            question_text = q.get('question_description', '')
            
            # Convert options list to dict
            options_list = q.get('options', [])
            options = {}
            for i, opt in enumerate(options_list[:4]):
                letter = chr(65 + i)  # A, B, C, D
                options[letter] = opt
            
            explanation = q.get('explanation', '')
            correct_answer = q.get('correct_option', 'A').strip().upper()
            
            is_short_option = self.check_short_option(options)
            answer_circle = self.answer_circles.get(correct_answer, correct_answer)
            
            prepared_questions.append({
                'question': question_text,
                'options': options,
                'explanation': explanation,
                'correct_answer': correct_answer,
                'answer_circle': answer_circle,
                'is_short_option': is_short_option
            })
        
        return prepared_questions
    
    def create_format1_html(self, questions, title):
        """Format 1: Practice sheet with inline answers"""
        
        template_str = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@200;300&display=swap" rel="stylesheet">
    
    <style>
        @page {
            size: A4 portrait;
            margin: 10mm;
        }
        
        body {
            font-family: 'SolaimanLipi', Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.2;
            color: #000;
            margin: 0;
            padding: 10px;
            width: 210mm;
        }
        
        .exam-header {
            text-align: center;
            border: 2px solid #4169E1;
            background-color: #F0F8FF;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 15px;
        }
        
        .exam-header h1 {
            color: #191970;
            margin: 0;
            font-size: 15pt;
            font-weight: bold;
        }
        
        .content-columns {
            column-count: 2;
            column-gap: 15px;
            column-fill: balance;
            column-rule: 1px solid #ddd;
        }
        
        .question {
            margin-bottom: 7px;
            break-inside: avoid;
            page-break-inside: avoid;
        }
        
        .question-header {
            margin-bottom: 4px;
            display: flex;
            align-items: flex-start;
        }
        
        .question-num {
            font-weight: bold;
            color: #1E64B7;
            font-size: 12pt;
            margin-right: 5px;
            white-space: nowrap;
            flex-shrink: 0;
        }
        
        .question-text {
            flex: 1;
            line-height: 1.4;
            font-size: 13pt;
        }
        
        .options-table-short {
            width: 100%;
            border-collapse: collapse;
            margin: 4px 0 4px 8px;
        }
        
        .options-table-short td {
            border: none;
            padding: 2px 8px 2px 0;
            vertical-align: top;
            font-size: 13pt;
        }
        
        .option-col {
            width: 40%;
        }
        
        .answer-col {
            text-align: center;
            vertical-align: middle;
            font-family: 'Poppins', sans-serif;
            font-weight: 300;
            font-size: 12pt;
        }
        
        .options-list {
            margin: 4px 0 4px 8px;
            padding: 0;
            list-style: none;
        }
        
        .options-list li {
            margin: 1px 0;
            font-size: 13pt;
        }
        
        .option-with-answer {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }
        
        .answer-circle {
            font-family: 'Poppins', sans-serif;
            font-weight: 300;
            font-size: 12pt;
        }
        
        .explanation {
            margin: 4px 0 2px 8px;
            padding: 4px;
            background-color: rgba(66, 153, 225, 0.1);
            border-left: 3px solid #4299e1;
            font-size: 12pt;
            font-style: italic;
            break-inside: avoid;
        }
        
        .explanation-label {
            font-weight: bold;
            color: #2c5282;
        }
        
        @media print {
            body {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
</head>
<body>
    <div class="exam-header">
        <h1>{{ title }}</h1>
    </div>
    
    <div class="content-columns">
        {% for question in questions %}
        <div class="question">
            <div class="question-header">
                <span class="question-num">{{ "{:02d}".format(loop.index) }}.</span>
                <div class="question-text">{{ question.question }}</div>
            </div>
            
            {% if question.is_short_option %}
            <table class="options-table-short">
                <tr>
                    <td class="option-col">(A) {{ question.options.A }}</td>
                    <td class="option-col">(B) {{ question.options.B }}</td>
                    <td rowspan="2" class="answer-col">
                        <span class="answer-circle">{{ question.answer_circle }}</span>
                    </td>
                </tr>
                <tr>
                    <td class="option-col">(C) {{ question.options.C }}</td>
                    <td class="option-col">(D) {{ question.options.D }}</td>
                </tr>
            </table>
            {% else %}
            <ul class="options-list">
                <li>(A) {{ question.options.A }}</li>
                <li>(B) {{ question.options.B }}</li>
                <li>(C) {{ question.options.C }}</li>
                <li class="option-with-answer">
                    <span>(D) {{ question.options.D }}</span>
                    <span class="answer-circle">{{ question.answer_circle }}</span>
                </li>
            </ul>
            {% endif %}
            
            {% if question.explanation %}
            <div class="explanation">
                <span class="explanation-label">ব্যাখ্যা:</span> {{ question.explanation }}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''
        
        template = Template(template_str)
        return template.render(questions=questions, title=title)
    
    def create_format2_html(self, questions, title):
        """Format 2: Questions only, then answers table"""
        
        template_str = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    
    <style>
        @page {
            size: A4 portrait;
            margin: 10mm;
        }
        
        body {
            font-family: 'SolaimanLipi', Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.2;
            color: #333;
            margin: 0;
            padding: 10px;
            width: 210mm;
        }
        
        .exam-header {
            text-align: center;
            border: 2px solid #4169E1;
            background-color: #F0F8FF;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 15px;
        }
        
        .exam-header h1 {
            color: #191970;
            margin: 0;
            font-size: 15pt;
            font-weight: bold;
        }
        
        .questions-section {
            column-count: 2;
            column-gap: 15px;
            column-fill: balance;
            column-rule: 1px solid #ddd;
        }
        
        .question {
            margin-bottom: 8px;
            break-inside: avoid;
            page-break-inside: avoid;
        }
        
        .question-header {
            margin-bottom: 4px;
            display: flex;
            align-items: flex-start;
        }
        
        .question-num {
            font-weight: bold;
            color: #1E64B7;
            font-size: 12pt;
            margin-right: 5px;
            white-space: nowrap;
            flex-shrink: 0;
        }
        
        .question-text {
            flex: 1;
            line-height: 1.4;
            font-size: 13pt;
        }
        
        .options-table-short {
            width: 100%;
            border-collapse: collapse;
            margin: 4px 0 4px 8px;
        }
        
        .options-table-short td {
            border: none;
            padding: 1px 4px 1px 0;
            font-size: 12pt;
            width: 50%;
        }
        
        .options-list {
            margin: 4px 0 4px 8px;
            padding: 0;
            list-style: none;
        }
        
        .options-list li {
            margin: 1px 0;
            font-size: 12pt;
        }
        
        .page-break {
            page-break-before: always;
            break-before: page;
        }
        
        .answers-section {
            column-count: 1;
        }
        
        .answer-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            border: 1px solid #333;
        }
        
        .answer-table th, .answer-table td {
            border: 1px solid #333;
            padding: 6px;
            text-align: left;
            vertical-align: top;
        }
        
        .answer-table th {
            background-color: #f5f5f5;
            font-weight: bold;
            text-align: center;
            font-size: 13pt;
        }
        
        .qno-col { width: 8%; text-align: center; }
        .ans-col { width: 8%; text-align: center; font-weight: bold; font-size: 14pt; }
        .exp-col { width: 84%; font-size: 12pt; }
        
        @media print {
            body {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            
            .answer-table thead {
                display: table-header-group;
            }
            
            .answer-table {
                page-break-inside: auto;
            }
            
            .answer-table tr {
                page-break-inside: avoid;
                page-break-after: auto;
            }
        }
    </style>
</head>
<body>
    <div class="exam-header">
        <h1>{{ title }} - Questions</h1>
    </div>
    
    <div class="questions-section">
        {% for question in questions %}
        <div class="question">
            <div class="question-header">
                <span class="question-num">{{ "{:02d}".format(loop.index) }}.</span>
                <div class="question-text">{{ question.question }}</div>
            </div>
            
            {% if question.is_short_option %}
            <table class="options-table-short">
                <tr>
                    <td>(A) {{ question.options.A }}</td>
                    <td>(B) {{ question.options.B }}</td>
                </tr>
                <tr>
                    <td>(C) {{ question.options.C }}</td>
                    <td>(D) {{ question.options.D }}</td>
                </tr>
            </table>
            {% else %}
            <ul class="options-list">
                <li>(A) {{ question.options.A }}</li>
                <li>(B) {{ question.options.B }}</li>
                <li>(C) {{ question.options.C }}</li>
                <li>(D) {{ question.options.D }}</li>
            </ul>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    
    <div class="page-break"></div>
    
    <div class="answers-section">
        <table class="answer-table">
            <thead>
                <tr>
                    <th class="qno-col">Q.No.</th>
                    <th class="ans-col">Ans</th>
                    <th class="exp-col">Explanation</th>
                </tr>
            </thead>
            <tbody>
                {% for question in questions %}
                <tr>
                    <td class="qno-col">{{ loop.index }}</td>
                    <td class="ans-col">{{ question.correct_answer }}</td>
                    <td class="exp-col">{{ question.explanation if question.explanation else '' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
'''
        
        template = Template(template_str)
        return template.render(questions=questions, title=title)
    
    def wait_for_page_load(self, driver, timeout=3):
        """Wait for page to fully load"""
        import time
        time.sleep(timeout)
    
    async def html_to_pdf(self, html_content, output_path):
        """Convert HTML to PDF using Selenium"""
        
        if not self.driver:
            self.initialize_browser()
        
        temp_html_path = None
        try:
            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(html_content)
                temp_html_path = temp_file.name
            
            # Load HTML in browser
            file_url = f"file://{os.path.abspath(temp_html_path)}"
            self.driver.get(file_url)
            
            # Wait for page load
            self.wait_for_page_load(self.driver)
            
            # Generate PDF with A4 settings
            print_options = PrintOptions()
            print_options.page_width = 8.27  # A4 width in inches
            print_options.page_height = 11.69  # A4 height in inches
            print_options.margin_top = 0.39
            print_options.margin_bottom = 0.39
            print_options.margin_left = 0.39
            print_options.margin_right = 0.39
            print_options.scale = 1.0
            print_options.background = True
            print_options.shrink_to_fit = True
            
            # Generate PDF
            pdf_data = self.driver.print_page(print_options)
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(base64.b64decode(pdf_data))
            
            logger.info(f"✅ PDF generated: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error converting HTML to PDF: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            
        finally:
            # Clean up temp HTML file
            if temp_html_path and os.path.exists(temp_html_path):
                try:
                    os.unlink(temp_html_path)
                except:
                    pass
    
    async def generate_both_pdfs(self, questions: List[Dict], output_dir: Path, title: str):
        """Generate both PDF formats"""
        try:
            # Initialize browser once
            self.initialize_browser()
            
            # Clean and prepare questions
            cleaned = self.cleanup_questions(questions)
            prepared = self.prepare_questions(cleaned)
            
            # Generate Format 1
            logger.info("Generating Format 1 PDF...")
            html1 = self.create_format1_html(prepared, title)
            pdf1_path = output_dir / f"{title}_format1.pdf"
            await self.html_to_pdf(html1, pdf1_path)
            
            # Generate Format 2
            logger.info("Generating Format 2 PDF...")
            html2 = self.create_format2_html(prepared, title)
            pdf2_path = output_dir / f"{title}_format2.pdf"
            await self.html_to_pdf(html2, pdf2_path)
            
            return pdf1_path, pdf2_path
            
        finally:
            # Cleanup browser
            self.cleanup_browser()
    
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
        
        try:
            pdf1_path, pdf2_path = await self.generate_both_pdfs(
                questions, config.OUTPUT_DIR, pdf_name
            )
            
            # Send both PDFs
            with open(pdf1_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"{pdf_name}_PracticeSheet.pdf",
                    caption=f"📄 **Format 1** • Practice Sheet • {len(questions)}Q"
                )
            
            with open(pdf2_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"{pdf_name}_QuestionsAnswers.pdf",
                    caption=f"📄 **Format 2** • Q&A Separate • {len(questions)}Q"
                )
            
            # Cleanup
            pdf1_path.unlink(missing_ok=True)
            pdf2_path.unlink(missing_ok=True)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ **PDF Generation Failed**\n\n`{str(e)[:200]}`",
                parse_mode='Markdown'
            )

# Global instance
pdf_exporter = PDFExporter()
