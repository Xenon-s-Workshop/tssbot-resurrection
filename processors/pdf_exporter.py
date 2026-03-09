"""
PDF Exporter - FIXED with HTML escaping
No paraparser errors, Bengali support, 2 formats
"""

import re
import os
from typing import List, Dict
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
from config import config

class PDFExporter:
    def __init__(self):
        self.sessions = {}
        self._register_fonts()
    
    def _register_fonts(self):
        """Register Bengali fonts"""
        try:
            dejavu_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Supplemental/DejaVuSans.ttf',
                'C:\\Windows\\Fonts\\DejaVuSans.ttf'
            ]
            for path in dejavu_paths:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont('DejaVu', path))
                    self.font_family = 'DejaVu'
                    print("✅ Bengali font support enabled")
                    return
        except:
            pass
        self.font_family = 'Helvetica'
        print("⚠️ Using Helvetica (no Bengali support)")
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters to prevent paraparser errors"""
        if not text:
            return ""
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        return text
    
    @staticmethod
    def cleanup_text(text: str) -> str:
        """Remove [tags] and links"""
        if not text:
            return text
        text = re.sub(r'\[[^\]]+\]', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        return re.sub(r'\s+', ' ', text).strip()
    
    def cleanup_questions(self, questions: List[Dict]) -> List[Dict]:
        return [{
            'question_description': self.cleanup_text(q.get('question_description', '')),
            'options': [self.cleanup_text(opt) for opt in q.get('options', [])],
            'correct_answer_index': q.get('correct_answer_index', 0),
            'correct_option': q.get('correct_option', 'A'),
            'explanation': self.cleanup_text(q.get('explanation', ''))
        } for q in questions]
    
    def start_export(self, user_id: int, questions: List[Dict]):
        self.sessions[user_id] = {'questions': questions, 'waiting_for_name': True}
    
    def is_waiting_for_name(self, user_id: int) -> bool:
        return self.sessions.get(user_id, {}).get('waiting_for_name', False)
    
    def set_pdf_name(self, user_id: int, name: str):
        if user_id in self.sessions:
            self.sessions[user_id]['pdf_name'] = name
            self.sessions[user_id]['waiting_for_name'] = False
    
    def get_session(self, user_id: int) -> Dict:
        return self.sessions.get(user_id, {})
    
    def clear_session(self, user_id: int):
        self.sessions.pop(user_id, None)
    
    # ==================== FORMAT 1: STANDARD ====================
    
    def generate_standard_format(self, questions: List[Dict], output_path, title: str):
        """Format 1: Standard - Compact layout"""
        doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                     fontName=self.font_family, fontSize=16,
                                     alignment=TA_LEFT, spaceAfter=20)
        story.append(Paragraph(self.escape_html(title), title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Questions
        for idx, q in enumerate(questions, 1):
            q_text = self.escape_html(q['question_description'])
            q_style = ParagraphStyle('Q', parent=styles['Normal'],
                                    fontName=self.font_family, fontSize=11, spaceAfter=6)
            story.append(Paragraph(f"<b>{idx}.</b> {q_text}", q_style))
            
            # Options
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)
                is_correct = (i == q['correct_answer_index'])
                marker = "✓" if is_correct else "○"
                opt_text = self.escape_html(opt)
                opt_style = ParagraphStyle('O', parent=styles['Normal'],
                                          fontName=self.font_family, fontSize=10,
                                          leftIndent=20, spaceAfter=3)
                story.append(Paragraph(f"{marker} <b>{opt_letter}.</b> {opt_text}", opt_style))
            
            # Answer
            ans_style = ParagraphStyle('A', parent=styles['Normal'],
                                      fontName=self.font_family, fontSize=9,
                                      leftIndent=20, spaceAfter=12,
                                      textColor=colors.HexColor('#006400'))
            story.append(Paragraph(f"<b>Answer: {q['correct_option']}</b>", ans_style))
            
            if idx % 10 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
    
    # ==================== FORMAT 2: DETAILED ====================
    
    def generate_detailed_format(self, questions: List[Dict], output_path, title: str):
        """Format 2: Detailed - With explanations"""
        doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)
        
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                     fontName=self.font_family, fontSize=16,
                                     alignment=TA_LEFT, spaceAfter=20)
        story.append(Paragraph(self.escape_html(title), title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Questions
        for idx, q in enumerate(questions, 1):
            q_text = self.escape_html(q['question_description'])
            q_style = ParagraphStyle('Q', parent=styles['Normal'],
                                    fontName=self.font_family, fontSize=12, spaceAfter=10)
            story.append(Paragraph(f"<b>{idx}. {q_text}</b>", q_style))
            
            # Options
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)
                is_correct = (i == q['correct_answer_index'])
                marker = "✓" if is_correct else "○"
                opt_text = self.escape_html(opt)
                opt_style = ParagraphStyle('O', parent=styles['Normal'],
                                          fontName=self.font_family, fontSize=11,
                                          leftIndent=25, spaceAfter=5,
                                          textColor=colors.HexColor('#006400') if is_correct else colors.black)
                story.append(Paragraph(f"{marker} <b>{opt_letter}.</b> {opt_text}", opt_style))
            
            # Explanation
            if q.get('explanation'):
                exp_text = self.escape_html(q['explanation'])
                exp_style = ParagraphStyle('E', parent=styles['Normal'],
                                          fontName=self.font_family, fontSize=10,
                                          leftIndent=25, spaceAfter=15,
                                          textColor=colors.HexColor('#555555'))
                story.append(Paragraph(f"<i>💡 {exp_text}</i>", exp_style))
            else:
                story.append(Spacer(1, 0.1*inch))
            
            story.append(Spacer(1, 0.05*inch))
            
            if idx % 6 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
    
    # ==================== HANDLERS ====================
    
    async def handle_pdf_export_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, questions: List[Dict]):
        user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
        
        self.start_export(user_id, questions)
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                "📄 *PDF Export*\n\nSend PDF name (without .pdf):\n\nExample: `Biology_Quiz_2024`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "📄 *PDF Export*\n\nSend PDF name (without .pdf):\n\nExample: `Biology_Quiz_2024`",
                parse_mode='Markdown'
            )
    
    async def handle_pdf_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        pdf_name = update.message.text.strip()
        pdf_name = re.sub(r'[<>:"/\\|?*]', '', pdf_name) or f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.set_pdf_name(user_id, pdf_name)
        
        keyboard = [
            [InlineKeyboardButton("📋 Standard", callback_data="pdf_format_1")],
            [InlineKeyboardButton("📝 Detailed", callback_data="pdf_format_2")]
        ]
        
        await update.message.reply_text(
            f"✅ PDF Name: `{pdf_name}.pdf`\n\n"
            f"📄 *Choose Format:*\n\n"
            f"📋 *Standard* - Compact (~10 Q/page)\n"
            f"📝 *Detailed* - With explanations (~6 Q/page)\n\n"
            f"Select below:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, format_num: int):
        query = update.callback_query
        user_id = query.from_user.id
        
        session = self.get_session(user_id)
        if not session or 'questions' not in session:
            await query.answer("❌ Session expired!")
            return
        
        questions = session['questions']
        pdf_name = session.get('pdf_name', f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        progress_msg = await query.edit_message_text("⏳ Generating PDF... 0%")
        
        cleaned = self.cleanup_questions(questions)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{pdf_name}_{timestamp}.pdf"
        pdf_path = config.OUTPUT_DIR / filename
        
        try:
            await progress_msg.edit_text("⏳ Generating PDF... 50%")
            
            if format_num == 1:
                self.generate_standard_format(cleaned, pdf_path, pdf_name)
            else:
                self.generate_detailed_format(cleaned, pdf_path, pdf_name)
            
            await progress_msg.edit_text("⏳ Generating PDF... 100%")
            
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f, filename=filename,
                    caption=f"✅ *PDF Generated!*\n\n"
                            f"📄 {pdf_name}\n"
                            f"📊 Questions: {len(cleaned)}\n"
                            f"🎨 {'Standard' if format_num == 1 else 'Detailed'}",
                    parse_mode='Markdown'
                )
            
            pdf_path.unlink(missing_ok=True)
            self.clear_session(user_id)
            
            await query.answer("✅ PDF sent!")
            await progress_msg.edit_text("✅ PDF export complete!")
            
        except Exception as e:
            await query.answer("❌ Error!")
            await progress_msg.edit_text(f"❌ Error: {e}")
            self.clear_session(user_id)

pdf_exporter = PDFExporter()
