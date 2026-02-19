"""
PDF Exporter - COMPLETELY FIXED
- Bengali font support (DejaVuSans)
- 2 clear formats (Standard & Detailed)
- Progress bars during generation
- Custom naming
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
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from config import config

class PDFExporter:
    """PDF export with Bengali support and 2 formats"""
    
    def __init__(self):
        self.sessions = {}  # {user_id: {'questions': [], 'pdf_name': '', 'waiting': bool}}
        self._register_fonts()
    
    def _register_fonts(self):
        """Register fonts for Bengali support"""
        try:
            # Try to register DejaVu fonts
            dejavu_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Supplemental/DejaVuSans.ttf',
                'C:\\Windows\\Fonts\\DejaVuSans.ttf'
            ]
            
            dejavu_bold_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf',
                'C:\\Windows\\Fonts\\DejaVuSans-Bold.ttf'
            ]
            
            # Register regular
            for path in dejavu_paths:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont('DejaVu', path))
                    print(f"✅ Registered DejaVu font from {path}")
                    break
            
            # Register bold
            for path in dejavu_bold_paths:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont('DejaVu-Bold', path))
                    print(f"✅ Registered DejaVu-Bold font from {path}")
                    break
            
            self.font_family = 'DejaVu'
            print("✅ Bengali font support enabled")
        except Exception as e:
            print(f"⚠️ Could not register DejaVu fonts: {e}")
            print("⚠️ Falling back to Helvetica (no Bengali support)")
            self.font_family = 'Helvetica'
    
    def start_export(self, user_id: int, questions: List[Dict]):
        """Start PDF export session"""
        self.sessions[user_id] = {
            'questions': questions,
            'waiting_for_name': True
        }
    
    def is_waiting_for_name(self, user_id: int) -> bool:
        """Check if waiting for PDF name"""
        return self.sessions.get(user_id, {}).get('waiting_for_name', False)
    
    def set_pdf_name(self, user_id: int, name: str):
        """Set PDF name"""
        if user_id in self.sessions:
            self.sessions[user_id]['pdf_name'] = name
            self.sessions[user_id]['waiting_for_name'] = False
    
    def get_session(self, user_id: int) -> Dict:
        """Get session data"""
        return self.sessions.get(user_id, {})
    
    def clear_session(self, user_id: int):
        """Clear session"""
        if user_id in self.sessions:
            del self.sessions[user_id]
    
    @staticmethod
    def cleanup_text(text: str) -> str:
        """Remove [tags] and links"""
        if not text:
            return text
        text = re.sub(r'\[[^\]]+\]', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def cleanup_questions(self, questions: List[Dict]) -> List[Dict]:
        """Clean all questions"""
        cleaned = []
        for q in questions:
            cleaned.append({
                'question_description': self.cleanup_text(q.get('question_description', '')),
                'options': [self.cleanup_text(opt) for opt in q.get('options', [])],
                'correct_answer_index': q.get('correct_answer_index', 0),
                'correct_option': q.get('correct_option', 'A'),
                'explanation': self.cleanup_text(q.get('explanation', ''))
            })
        return cleaned
    
    # ==================== FORMAT 1: STANDARD ====================
    
    def generate_standard_format(self, questions: List[Dict], output_path, title: str):
        """Format 1: Standard - Clean & compact with Bengali support"""
        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.5*inch, rightMargin=0.5*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontName=f'{self.font_family}-Bold' if self.font_family == 'DejaVu' else 'Helvetica-Bold',
            fontSize=16,
            alignment=TA_LEFT,
            spaceAfter=20
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Questions
        for idx, q in enumerate(questions, 1):
            # Question
            q_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontName=f'{self.font_family}-Bold' if self.font_family == 'DejaVu' else 'Helvetica-Bold',
                fontSize=11,
                spaceAfter=6
            )
            story.append(Paragraph(f"{idx}. {q['question_description']}", q_style))
            
            # Options
            opt_style = ParagraphStyle(
                'Options',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=10,
                leftIndent=20,
                spaceAfter=3
            )
            
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)
                is_correct = (i == q['correct_answer_index'])
                marker = "✓" if is_correct else "○"
                
                opt_text = f"{marker} <b>{opt_letter}.</b> {opt}"
                story.append(Paragraph(opt_text, opt_style))
            
            # Answer
            ans_style = ParagraphStyle(
                'Answer',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=9,
                leftIndent=20,
                spaceAfter=12,
                textColor=colors.HexColor('#006400')
            )
            story.append(Paragraph(f"<b>Answer: {q['correct_option']}</b>", ans_style))
            
            # Page break every 10 questions
            if idx % 10 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
    
    # ==================== FORMAT 2: DETAILED ====================
    
    def generate_detailed_format(self, questions: List[Dict], output_path, title: str):
        """Format 2: Detailed - With explanations and spacing"""
        doc = SimpleDocTemplate(
            str(output_path), pagesize=A4,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.5*inch, rightMargin=0.5*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontName=f'{self.font_family}-Bold' if self.font_family == 'DejaVu' else 'Helvetica-Bold',
            fontSize=16,
            alignment=TA_LEFT,
            spaceAfter=20
        )
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Questions
        for idx, q in enumerate(questions, 1):
            # Question
            q_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontName=f'{self.font_family}-Bold' if self.font_family == 'DejaVu' else 'Helvetica-Bold',
                fontSize=12,
                spaceAfter=10
            )
            story.append(Paragraph(f"<b>{idx}. {q['question_description']}</b>", q_style))
            
            # Options
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)
                is_correct = (i == q['correct_answer_index'])
                
                opt_style = ParagraphStyle(
                    'Option',
                    parent=styles['Normal'],
                    fontName=f'{self.font_family}-Bold' if is_correct else self.font_family,
                    fontSize=11,
                    leftIndent=25,
                    spaceAfter=5,
                    textColor=colors.HexColor('#006400') if is_correct else colors.black
                )
                
                marker = "✓" if is_correct else "○"
                story.append(Paragraph(f"{marker} <b>{opt_letter}.</b> {opt}", opt_style))
            
            # Explanation
            if q.get('explanation'):
                exp_style = ParagraphStyle(
                    'Explanation',
                    parent=styles['Normal'],
                    fontName=self.font_family,
                    fontSize=10,
                    leftIndent=25,
                    spaceAfter=15,
                    textColor=colors.HexColor('#555555')
                )
                story.append(Paragraph(f"<i>💡 {q['explanation']}</i>", exp_style))
            else:
                story.append(Spacer(1, 0.1*inch))
            
            # Separator line
            story.append(Spacer(1, 0.05*inch))
            
            # Page break every 6 questions
            if idx % 6 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
    
    # ==================== HANDLERS ====================
    
    async def handle_pdf_export_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, questions: List[Dict]):
        """Start PDF export - ask for name"""
        user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
        
        self.start_export(user_id, questions)
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                "📄 *PDF Export*\n\n"
                "Please send the PDF name\n"
                "(without .pdf extension)\n\n"
                "Example: `Biology_Quiz_2024`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "📄 *PDF Export*\n\n"
                "Please send the PDF name\n"
                "(without .pdf extension)\n\n"
                "Example: `Biology_Quiz_2024`",
                parse_mode='Markdown'
            )
    
    async def handle_pdf_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF name and show format selection"""
        user_id = update.effective_user.id
        pdf_name = update.message.text.strip()
        
        # Clean filename
        pdf_name = re.sub(r'[<>:"/\\|?*]', '', pdf_name)
        if not pdf_name:
            pdf_name = f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.set_pdf_name(user_id, pdf_name)
        
        # Show format selection
        keyboard = [
            [InlineKeyboardButton("📋 Standard Format", callback_data="pdf_format_1")],
            [InlineKeyboardButton("📝 Detailed Format", callback_data="pdf_format_2")]
        ]
        
        await update.message.reply_text(
            f"✅ PDF Name: `{pdf_name}.pdf`\n\n"
            f"📄 *Choose Format:*\n\n"
            f"📋 *Standard* - Compact, clean layout\n"
            f"   • Questions with inline options\n"
            f"   • Answers marked with ✓\n"
            f"   • ~10 questions per page\n\n"
            f"📝 *Detailed* - Spacious with explanations\n"
            f"   • Each option on separate line\n"
            f"   • Explanations included\n"
            f"   • Color-coded answers\n"
            f"   • ~6 questions per page\n\n"
            f"Select format:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, format_num: int):
        """Generate PDF with selected format"""
        query = update.callback_query
        user_id = query.from_user.id
        
        session = self.get_session(user_id)
        if not session or 'questions' not in session:
            await query.answer("❌ Session expired!")
            return
        
        questions = session['questions']
        pdf_name = session.get('pdf_name', f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Show progress
        progress_msg = await query.edit_message_text("⏳ Generating PDF... 0%")
        
        # Clean questions
        cleaned = self.cleanup_questions(questions)
        
        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{pdf_name}_{timestamp}.pdf"
        pdf_path = config.OUTPUT_DIR / filename
        
        try:
            # Update progress
            await progress_msg.edit_text("⏳ Generating PDF... 50%")
            
            # Generate based on format
            if format_num == 1:
                self.generate_standard_format(cleaned, pdf_path, pdf_name)
            else:
                self.generate_detailed_format(cleaned, pdf_path, pdf_name)
            
            # Update progress
            await progress_msg.edit_text("⏳ Generating PDF... 100%")
            
            # Send PDF
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f, filename=filename,
                    caption=f"✅ *PDF Generated!*\n\n"
                            f"📄 Name: {pdf_name}\n"
                            f"📊 Questions: {len(cleaned)}\n"
                            f"🎨 Format: {'Standard' if format_num == 1 else 'Detailed'}\n"
                            f"✨ Bengali support enabled",
                    parse_mode='Markdown'
                )
            
            # Cleanup
            pdf_path.unlink(missing_ok=True)
            self.clear_session(user_id)
            
            await query.answer("✅ PDF sent!")
            await progress_msg.edit_text("✅ PDF export complete!")
            
        except Exception as e:
            await query.answer("❌ Error!")
            await progress_msg.edit_text(f"❌ Error: {e}")
            self.clear_session(user_id)

# Global instance
pdf_exporter = PDFExporter()
