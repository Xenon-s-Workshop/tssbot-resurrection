"""
PDF Exporter - BEAUTIFUL DESIGN
Matches the exact style from screenshot:
- Blue headers with question numbers (no "of X")
- Green highlighting for correct answers
- Orange explanation boxes
- Professional color scheme
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from config import config

class PDFExporter:
    def __init__(self):
        self.sessions = {}
        self.font_family = 'Helvetica'
        self._register_bengali_fonts()
    
    def _register_bengali_fonts(self):
        """Register Bengali/Unicode fonts with multiple fallback paths"""
        font_paths = [
            # Linux - Primary
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            # Linux - Alternative
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
            # Mac
            '/System/Library/Fonts/Supplemental/DejaVuSans.ttf',
            '/Library/Fonts/Arial Unicode.ttf',
            # Windows
            'C:\\Windows\\Fonts\\DejaVuSans.ttf',
            'C:\\Windows\\Fonts\\arial.ttf',
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('BengaliFont', path))
                    self.font_family = 'BengaliFont'
                    print(f"✅ Bengali font loaded: {path}")
                    return
                except Exception as e:
                    print(f"⚠️ Failed to load {path}: {e}")
        
        print("⚠️ No Bengali fonts found - using Helvetica")
        print("💡 Install: sudo apt-get install fonts-dejavu-core fonts-noto")
        self.font_family = 'Helvetica'
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML for ReportLab"""
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        return text
    
    @staticmethod
    def cleanup_text(text: str) -> str:
        """Remove tags and links"""
        if not text:
            return text
        text = re.sub(r'\[[^\]]+\]', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        return re.sub(r'\s+', ' ', text).strip()
    
    def cleanup_questions(self, questions: List[Dict]) -> List[Dict]:
        """Clean all questions"""
        cleaned = []
        for q in questions:
            cleaned.append({
                'question_description': self.cleanup_text(q.get('question_description', '')),
                'options': [self.cleanup_text(opt) for opt in q.get('options', []) if opt],
                'correct_answer_index': q.get('correct_answer_index', 0),
                'correct_option': q.get('correct_option', 'A'),
                'explanation': self.cleanup_text(q.get('explanation', ''))
            })
        return cleaned
    
    # ==================== SESSION MANAGEMENT ====================
    
    def start_export(self, user_id: int, questions: List[Dict]):
        self.sessions[user_id] = {
            'questions': questions,
            'waiting_for_name': True
        }
    
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
    
    # ==================== PDF GENERATION - BEAUTIFUL DESIGN ====================
    
    def generate_beautiful_pdf(self, questions: List[Dict], output_path, title: str):
        """
        Generate PDF matching screenshot design:
        - Blue headers: "Question 1", "Question 2" (no "of X")
        - Green background for correct answer
        - Orange explanation boxes
        """
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        
        story = []
        
        # ===== TITLE PAGE =====
        title_style = ParagraphStyle(
            'Title',
            fontName=self.font_family,
            fontSize=22,
            textColor=colors.HexColor('#1565c0'),
            alignment=TA_CENTER,
            spaceAfter=15,
            leading=26
        )
        
        story.append(Spacer(1, 1.5*inch))
        story.append(Paragraph(self.escape_html(title), title_style))
        
        # Subtitle
        subtitle_style = ParagraphStyle(
            'Subtitle',
            fontName=self.font_family,
            fontSize=12,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        date_str = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"মোট {len(questions)}টি প্রশ্ন", subtitle_style))
        story.append(Paragraph(date_str, subtitle_style))
        
        story.append(PageBreak())
        
        # ===== QUESTIONS =====
        for idx, q in enumerate(questions, 1):
            # BLUE HEADER - Just "Question 1" (no "of X")
            header_style = ParagraphStyle(
                'QHeader',
                fontName=self.font_family,
                fontSize=11,
                textColor=colors.white,
                alignment=TA_LEFT,
                leftIndent=12,
                spaceAfter=0,
                leading=14
            )
            
            story.append(Paragraph(
                f'<para backColor="#1565c0" leftIndent="12" rightIndent="12" '
                f'spaceBefore="4" spaceAfter="4">'
                f'<b>Question {idx}</b></para>',
                header_style
            ))
            
            story.append(Spacer(1, 0.08*inch))
            
            # QUESTION TEXT
            q_text = self.escape_html(q['question_description'])
            q_style = ParagraphStyle(
                'Question',
                fontName=self.font_family,
                fontSize=11,
                textColor=colors.HexColor('#212121'),
                alignment=TA_LEFT,
                spaceAfter=10,
                leading=15,
                leftIndent=8
            )
            story.append(Paragraph(q_text, q_style))
            
            # OPTIONS - Green background for correct answer
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)  # A, B, C, D
                is_correct = (i == q['correct_answer_index'])
                opt_text = self.escape_html(opt)
                
                if is_correct:
                    # GREEN BACKGROUND for correct answer
                    opt_style = ParagraphStyle(
                        'OptCorrect',
                        fontName=self.font_family,
                        fontSize=10,
                        textColor=colors.HexColor('#1b5e20'),
                        leftIndent=20,
                        spaceAfter=5,
                        leading=13
                    )
                    story.append(Paragraph(
                        f'<para backColor="#c8e6c9" leftIndent="15" rightIndent="10" '
                        f'spaceBefore="2" spaceAfter="2">'
                        f'<b>✓ {opt_letter}.</b> {opt_text}</para>',
                        opt_style
                    ))
                else:
                    # Regular option
                    opt_style = ParagraphStyle(
                        'OptNormal',
                        fontName=self.font_family,
                        fontSize=10,
                        textColor=colors.HexColor('#424242'),
                        leftIndent=20,
                        spaceAfter=5,
                        leading=13
                    )
                    story.append(Paragraph(
                        f'○ <b>{opt_letter}.</b> {opt_text}',
                        opt_style
                    ))
            
            story.append(Spacer(1, 0.1*inch))
            
            # ORANGE EXPLANATION BOX
            if q.get('explanation'):
                exp_text = self.escape_html(q['explanation'])
                exp_label_style = ParagraphStyle(
                    'ExpLabel',
                    fontName=self.font_family,
                    fontSize=9,
                    textColor=colors.HexColor('#e65100'),
                    leftIndent=15,
                    spaceAfter=0
                )
                exp_text_style = ParagraphStyle(
                    'ExpText',
                    fontName=self.font_family,
                    fontSize=9,
                    textColor=colors.HexColor('#424242'),
                    leftIndent=15,
                    spaceAfter=8,
                    leading=12
                )
                
                story.append(Paragraph(
                    f'<para backColor="#fff3e0" leftIndent="12" rightIndent="10" '
                    f'spaceBefore="3" spaceAfter="2">'
                    f'<b>💡 Explanation:</b></para>',
                    exp_label_style
                ))
                story.append(Paragraph(
                    f'<para backColor="#fff3e0" leftIndent="12" rightIndent="10" '
                    f'spaceBefore="2" spaceAfter="5">'
                    f'{exp_text}</para>',
                    exp_text_style
                ))
            
            story.append(Spacer(1, 0.15*inch))
            
            # Page break every 5 questions
            if idx % 5 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
        print(f"✅ Generated beautiful PDF: {len(questions)} questions")
    
    # ==================== HANDLERS ====================
    
    async def handle_pdf_export_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, questions: List[Dict]):
        """Start PDF export - ask for name"""
        user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
        
        self.start_export(user_id, questions)
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                "📄 **PDF Export**\n\n"
                "Send me a name for your PDF:\n\n"
                "💡 **Examples:**\n"
                "• `Chemistry_Final_2024`\n"
                "• `Biology_MCQ_Set`\n"
                "• `পরীক্ষা_প্রস্তুতি`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "📄 **PDF Export**\n\n"
                "Send me a name for your PDF:\n\n"
                "💡 **Examples:**\n"
                "• `Chemistry_Final_2024`\n"
                "• `Biology_MCQ_Set`\n"
                "• `পরীক্ষা_প্রস্তুতি`",
                parse_mode='Markdown'
            )
    
    async def handle_pdf_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF name input"""
        user_id = update.effective_user.id
        pdf_name = update.message.text.strip()
        
        # Sanitize filename
        pdf_name = re.sub(r'[<>:"/\\|?*]', '', pdf_name)
        if not pdf_name:
            pdf_name = f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if not pdf_name.endswith('.pdf'):
            pdf_name += '.pdf'
        
        self.set_pdf_name(user_id, pdf_name)
        
        # Confirm and generate
        await update.message.reply_text(
            f"✅ PDF Name: `{pdf_name}`\n\n"
            f"🎨 Generating beautiful PDF...\n"
            f"📋 Blue headers\n"
            f"🟢 Green correct answers\n"
            f"🟠 Orange explanations\n"
            f"🌏 Bengali/Unicode supported",
            parse_mode='Markdown'
        )
        
        # Generate PDF
        await self.generate_pdf_file(user_id, context)
    
    async def generate_pdf_file(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Generate and send PDF"""
        session = self.get_session(user_id)
        if not session or 'questions' not in session:
            return
        
        questions = session['questions']
        pdf_name = session.get('pdf_name', f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        # Clean questions
        cleaned = self.cleanup_questions(questions)
        
        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = config.OUTPUT_DIR / f"pdf_{timestamp}.pdf"
        
        try:
            # Get title (filename without .pdf)
            title = pdf_name.replace('.pdf', '')
            
            self.generate_beautiful_pdf(cleaned, pdf_path, title)
            
            # Send PDF
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=pdf_name,
                    caption=f"✅ **PDF Generated!**\n\n"
                            f"📄 {pdf_name}\n"
                            f"📊 Questions: {len(cleaned)}\n"
                            f"🎨 Beautiful design\n"
                            f"🌏 Bengali supported\n\n"
                            f"Enjoy! 🎉",
                    parse_mode='Markdown'
                )
            
            # Cleanup
            pdf_path.unlink(missing_ok=True)
            self.clear_session(user_id)
            
        except Exception as e:
            print(f"❌ PDF generation error: {e}")
            await context.bot.send_message(
                user_id,
                f"❌ **PDF Generation Failed**\n\n"
                f"Error: {str(e)[:100]}\n\n"
                f"Please try again.",
                parse_mode='Markdown'
            )
            self.clear_session(user_id)
    
    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, format_num: int):
        """For backward compatibility - now only one beautiful format"""
        await self.generate_pdf_file(update.callback_query.from_user.id, context)

# Global instance
pdf_exporter = PDFExporter()
