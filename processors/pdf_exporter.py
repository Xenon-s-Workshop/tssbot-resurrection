"""
PDF Exporter - BEAUTIFUL DESIGN with FULL BENGALI SUPPORT
Professional layouts with colors, headers, and proper formatting
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
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from config import config

class PDFExporter:
    def __init__(self):
        self.sessions = {}
        self.font_family = 'Helvetica'
        self._register_fonts()
    
    def _register_fonts(self):
        """Register Bengali/Unicode fonts - tries multiple paths"""
        font_paths = [
            # Linux
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
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
                    pdfmetrics.registerFont(TTFont('UniFont', path))
                    self.font_family = 'UniFont'
                    print(f"✅ Bengali/Unicode font loaded: {path}")
                    return
                except Exception as e:
                    print(f"⚠️ Failed to load {path}: {e}")
                    continue
        
        print("⚠️ No Unicode fonts found - Bengali text may not display correctly")
        print("💡 Install fonts: sudo apt-get install fonts-dejavu-core")
        self.font_family = 'Helvetica'
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters for ReportLab"""
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
        """Remove [tags], links, and extra whitespace"""
        if not text:
            return text
        # Remove [tags]
        text = re.sub(r'\[[^\]]+\]', '', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        # Clean whitespace
        return re.sub(r'\s+', ' ', text).strip()
    
    def cleanup_questions(self, questions: List[Dict]) -> List[Dict]:
        """Clean all questions in list"""
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
    
    # ==================== SESSION MANAGEMENT ====================
    
    def start_export(self, user_id: int, questions: List[Dict]):
        """Start PDF export session"""
        self.sessions[user_id] = {
            'questions': questions,
            'waiting_for_name': True
        }
    
    def is_waiting_for_name(self, user_id: int) -> bool:
        """Check if waiting for PDF name input"""
        return self.sessions.get(user_id, {}).get('waiting_for_name', False)
    
    def set_pdf_name(self, user_id: int, name: str):
        """Set PDF name for session"""
        if user_id in self.sessions:
            self.sessions[user_id]['pdf_name'] = name
            self.sessions[user_id]['waiting_for_name'] = False
    
    def get_session(self, user_id: int) -> Dict:
        """Get user session data"""
        return self.sessions.get(user_id, {})
    
    def clear_session(self, user_id: int):
        """Clear user session"""
        self.sessions.pop(user_id, None)
    
    # ==================== FORMAT 1: STANDARD (Beautiful & Compact) ====================
    
    def generate_standard_format(self, questions: List[Dict], output_path, title: str):
        """Format 1: Beautiful Standard - Colorful compact layout"""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # ===== HEADER =====
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontName=self.font_family,
            fontSize=20,
            textColor=colors.HexColor('#1a237e'),
            alignment=TA_CENTER,
            spaceAfter=10,
            spaceBefore=0,
            leading=24
        )
        
        story.append(Paragraph(self.escape_html(title), header_style))
        
        # Subtitle with date
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontName=self.font_family,
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        date_str = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(f"{len(questions)} Questions • {date_str}", subtitle_style))
        
        # Separator line
        story.append(Spacer(1, 0.1*inch))
        
        # ===== QUESTIONS =====
        for idx, q in enumerate(questions, 1):
            # Question number box
            q_num_style = ParagraphStyle(
                'QNum',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=11,
                textColor=colors.white,
                alignment=TA_LEFT,
                leftIndent=8,
                rightIndent=8,
                spaceAfter=0
            )
            
            # Question text
            q_text = self.escape_html(q['question_description'])
            q_style = ParagraphStyle(
                'Question',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=11,
                textColor=colors.HexColor('#212121'),
                alignment=TA_JUSTIFY,
                spaceAfter=8,
                leading=14
            )
            
            # Question with number in colored box
            story.append(Paragraph(
                f'<para backColor="#1a237e" leftIndent="8" rightIndent="8">'
                f'<font color="white"><b>Q{idx}</b></font></para>',
                q_num_style
            ))
            story.append(Spacer(1, 0.05*inch))
            story.append(Paragraph(f"<b>{q_text}</b>", q_style))
            
            # Options in table format for better layout
            option_data = []
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)
                is_correct = (i == q['correct_answer_index'])
                
                # Checkmark for correct answer
                marker = "✓" if is_correct else "○"
                marker_color = "#2e7d32" if is_correct else "#757575"
                
                opt_text = self.escape_html(opt)
                
                option_data.append([
                    Paragraph(f'<font color="{marker_color}"><b>{marker}</b></font>', styles['Normal']),
                    Paragraph(f'<font color="{marker_color}"><b>{opt_letter}.</b></font>', styles['Normal']),
                    Paragraph(f'<font color="#212121">{opt_text}</font>', styles['Normal'])
                ])
            
            # Options table
            opt_table = Table(option_data, colWidths=[0.3*inch, 0.3*inch, 5.5*inch])
            opt_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), self.font_family),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(opt_table)
            story.append(Spacer(1, 0.1*inch))
            
            # Answer box
            ans_style = ParagraphStyle(
                'Answer',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=9,
                textColor=colors.HexColor('#2e7d32'),
                alignment=TA_LEFT,
                leftIndent=15,
                spaceAfter=15
            )
            story.append(Paragraph(
                f'<para backColor="#e8f5e9" leftIndent="10" rightIndent="10">'
                f'<b>✓ Answer: {q["correct_option"]}</b></para>',
                ans_style
            ))
            
            story.append(Spacer(1, 0.15*inch))
            
            # Page break every 8 questions
            if idx % 8 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
        print(f"✅ Generated Standard PDF: {len(questions)} questions")
    
    # ==================== FORMAT 2: DETAILED (Premium with Explanations) ====================
    
    def generate_detailed_format(self, questions: List[Dict], output_path, title: str):
        """Format 2: Premium Detailed - Full explanations with beautiful design"""
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # ===== COVER PAGE =====
        cover_title = ParagraphStyle(
            'CoverTitle',
            parent=styles['Heading1'],
            fontName=self.font_family,
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            alignment=TA_CENTER,
            spaceAfter=20,
            leading=30
        )
        
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph(self.escape_html(title), cover_title))
        
        # Cover subtitle
        cover_sub = ParagraphStyle(
            'CoverSub',
            parent=styles['Normal'],
            fontName=self.font_family,
            fontSize=14,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceAfter=10
        )
        story.append(Paragraph(f"Complete Study Guide", cover_sub))
        story.append(Paragraph(f"{len(questions)} Questions with Detailed Explanations", cover_sub))
        
        date_str = datetime.now().strftime("%B %d, %Y")
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(date_str, cover_sub))
        
        story.append(PageBreak())
        
        # ===== QUESTIONS =====
        for idx, q in enumerate(questions, 1):
            # Question header with colored background
            q_header_style = ParagraphStyle(
                'QHeader',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=12,
                textColor=colors.white,
                alignment=TA_LEFT,
                leftIndent=15,
                spaceAfter=10,
                leading=16
            )
            
            story.append(Paragraph(
                f'<para backColor="#1565c0" leftIndent="15" rightIndent="15" spaceBefore="5" spaceAfter="5">'
                f'<b>Question {idx} of {len(questions)}</b></para>',
                q_header_style
            ))
            
            # Question text
            q_text = self.escape_html(q['question_description'])
            q_style = ParagraphStyle(
                'QText',
                parent=styles['Normal'],
                fontName=self.font_family,
                fontSize=12,
                textColor=colors.HexColor('#212121'),
                alignment=TA_JUSTIFY,
                spaceAfter=12,
                leading=16,
                leftIndent=10
            )
            story.append(Paragraph(f"<b>{q_text}</b>", q_style))
            
            # Options with highlighting
            for i, opt in enumerate(q['options']):
                opt_letter = chr(65 + i)
                is_correct = (i == q['correct_answer_index'])
                opt_text = self.escape_html(opt)
                
                if is_correct:
                    # Correct answer - green background
                    opt_style = ParagraphStyle(
                        'OptCorrect',
                        parent=styles['Normal'],
                        fontName=self.font_family,
                        fontSize=11,
                        textColor=colors.HexColor('#1b5e20'),
                        leftIndent=25,
                        spaceAfter=6,
                        leading=14
                    )
                    story.append(Paragraph(
                        f'<para backColor="#c8e6c9" leftIndent="20" rightIndent="10" spaceBefore="3" spaceAfter="3">'
                        f'<b>✓ {opt_letter}.</b> {opt_text}</para>',
                        opt_style
                    ))
                else:
                    # Other options
                    opt_style = ParagraphStyle(
                        'OptNormal',
                        parent=styles['Normal'],
                        fontName=self.font_family,
                        fontSize=11,
                        textColor=colors.HexColor('#424242'),
                        leftIndent=25,
                        spaceAfter=6,
                        leading=14
                    )
                    story.append(Paragraph(f"○ <b>{opt_letter}.</b> {opt_text}", opt_style))
            
            story.append(Spacer(1, 0.15*inch))
            
            # Explanation box (if exists)
            if q.get('explanation'):
                exp_text = self.escape_html(q['explanation'])
                exp_style = ParagraphStyle(
                    'Explanation',
                    parent=styles['Normal'],
                    fontName=self.font_family,
                    fontSize=10,
                    textColor=colors.HexColor('#424242'),
                    alignment=TA_JUSTIFY,
                    leftIndent=20,
                    rightIndent=15,
                    spaceAfter=10,
                    leading=13
                )
                
                story.append(Paragraph(
                    f'<para backColor="#fff3e0" leftIndent="15" rightIndent="15" spaceBefore="5" spaceAfter="5">'
                    f'<b><font color="#e65100">💡 Explanation:</font></b></para>',
                    exp_style
                ))
                story.append(Paragraph(
                    f'<para backColor="#fff3e0" leftIndent="15" rightIndent="15" spaceBefore="5" spaceAfter="8">'
                    f'{exp_text}</para>',
                    exp_style
                ))
            
            story.append(Spacer(1, 0.2*inch))
            
            # Page break every 5 questions
            if idx % 5 == 0 and idx < len(questions):
                story.append(PageBreak())
        
        doc.build(story)
        print(f"✅ Generated Detailed PDF: {len(questions)} questions with explanations")
    
    # ==================== HANDLERS ====================
    
    async def handle_pdf_export_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, questions: List[Dict]):
        """Start PDF export - ask for name"""
        user_id = update.effective_user.id if hasattr(update, 'effective_user') else update.callback_query.from_user.id
        
        self.start_export(user_id, questions)
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                "📄 *PDF Export*\n\n"
                "Send me a name for your PDF (without .pdf extension):\n\n"
                "💡 *Examples:*\n"
                "• `Chemistry_Final_2024`\n"
                "• `Biology_Practice_Set`\n"
                "• `Math_MCQ_Collection`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "📄 *PDF Export*\n\n"
                "Send me a name for your PDF (without .pdf extension):\n\n"
                "💡 *Examples:*\n"
                "• `Chemistry_Final_2024`\n"
                "• `Biology_Practice_Set`\n"
                "• `Math_MCQ_Collection`",
                parse_mode='Markdown'
            )
    
    async def handle_pdf_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF name input from user"""
        user_id = update.effective_user.id
        pdf_name = update.message.text.strip()
        
        # Sanitize filename
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
            f"📋 *Standard* - Beautiful & compact\n"
            f"   • Colorful design\n"
            f"   • ~8 questions per page\n"
            f"   • Quick review format\n\n"
            f"📝 *Detailed* - Premium with explanations\n"
            f"   • Cover page included\n"
            f"   • Full explanations shown\n"
            f"   • ~5 questions per page\n\n"
            f"Select format below:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, format_num: int):
        """Generate PDF with selected format"""
        query = update.callback_query
        user_id = query.from_user.id
        
        session = self.get_session(user_id)
        if not session or 'questions' not in session:
            await query.answer("❌ Session expired! Please start over.")
            return
        
        questions = session['questions']
        pdf_name = session.get('pdf_name', f"MCQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Progress message
        progress_msg = await query.edit_message_text(
            f"⏳ Generating beautiful PDF...\n\n"
            f"📄 Format: {'Standard' if format_num == 1 else 'Detailed'}\n"
            f"📊 Questions: {len(questions)}\n\n"
            f"Please wait..."
        )
        
        # Clean questions
        cleaned = self.cleanup_questions(questions)
        
        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{pdf_name}_{timestamp}.pdf"
        pdf_path = config.OUTPUT_DIR / filename
        
        try:
            if format_num == 1:
                self.generate_standard_format(cleaned, pdf_path, pdf_name)
            else:
                self.generate_detailed_format(cleaned, pdf_path, pdf_name)
            
            # Send PDF
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=filename,
                    caption=f"✅ *PDF Generated Successfully!*\n\n"
                            f"📄 {pdf_name}\n"
                            f"📊 Questions: {len(cleaned)}\n"
                            f"🎨 Format: {'Standard (Colorful)' if format_num == 1 else 'Detailed (Premium)'}\n"
                            f"🌏 Bengali/Unicode supported\n\n"
                            f"Enjoy your beautiful PDF! 🎉",
                    parse_mode='Markdown'
                )
            
            # Cleanup
            pdf_path.unlink(missing_ok=True)
            self.clear_session(user_id)
            
            await query.answer("✅ PDF sent!")
            await progress_msg.edit_text(
                f"✅ *PDF Export Complete!*\n\n"
                f"Check your messages for the beautiful PDF! 📄"
            )
            
        except Exception as e:
            print(f"❌ PDF generation error: {e}")
            await query.answer("❌ Error generating PDF!")
            await progress_msg.edit_text(
                f"❌ *PDF Generation Failed*\n\n"
                f"Error: {str(e)[:100]}\n\n"
                f"Please try again or contact support."
            )
            self.clear_session(user_id)

# Create global instance
pdf_exporter = PDFExporter()
