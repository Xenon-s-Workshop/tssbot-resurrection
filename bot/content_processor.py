"""
Content Processor - COMPLETE & FIXED
- Auto-generates 3 files
- Single edited message (no spam)
- Correct question format
- Error reporting
"""

import json
import asyncio
from typing import List, Dict
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import config
from database import db
from processors.csv_processor import CSVGenerator
from processors.image_processor import ImageProcessor
from processors.quiz_poster import quiz_poster
from processors.pdf_processor import PDFProcessor

class ContentProcessor:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    async def process_content(self, user_id, content_type, content_paths, page_range, mode, context):
        """Process content and AUTO-GENERATE 3 files - WITH ERROR REPORTING"""
        msg = None
        
        try:
            # Convert to images
            if content_type == 'pdf':
                msg = await context.bot.send_message(
                    user_id,
                    f"🔄 *Processing PDF...*\n📄 Pages: {'All' if not page_range else f'{page_range[0]}-{page_range[1]}'}\n\n"
                    f"Using model: `{config.GEMINI_MODEL}`",
                    parse_mode='Markdown'
                )
                
                try:
                    images = await PDFProcessor.pdf_to_images(content_paths[0], page_range)
                except Exception as e:
                    await msg.edit_text(
                        f"❌ *PDF Conversion Failed*\n\n"
                        f"Could not convert PDF to images.\n"
                        f"Error: `{str(e)[:200]}`",
                        parse_mode='Markdown'
                    )
                    return
            else:
                msg = await context.bot.send_message(user_id, "🔄 Processing images...")
                images = [await ImageProcessor.load_image(p) for p in content_paths]

            total = len(images)
            
            if total == 0:
                await msg.edit_text(
                    "❌ *No Images Found*\n\n"
                    "Could not extract any images from the PDF.",
                    parse_mode='Markdown'
                )
                return

            await msg.edit_text(
                f"✅ *Extracted {total} images*\n"
                f"🤖 Starting AI processing...",
                parse_mode='Markdown'
            )

            # Progress callback - EDIT SINGLE MESSAGE
            async def progress(current, total_pages):
                try:
                    pct = int((current / total_pages) * 100)
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    await msg.edit_text(
                        f"🔍 *Processing...*\n\n"
                        f"`[{bar}]` {pct}%\n"
                        f"Page {current}/{total_pages}\n"
                        f"Mode: {mode}",
                        parse_mode='Markdown'
                    )
                except:
                    pass

            # Get processor
            processor = self.bot_handlers.get_processor(user_id)
            
            # Process images - WITH ERROR REPORTING
            try:
                raw_questions = await processor.process_images_parallel(
                    images, 
                    mode, 
                    progress,
                    user_id=user_id,
                    context=context
                )
            except Exception as e:
                await msg.edit_text(
                    f"❌ *AI Processing Failed*\n\n"
                    f"Error: `{str(e)[:200]}`\n\n"
                    f"💡 Check if your API keys are valid:\n"
                    f"https://aistudio.google.com/apikey",
                    parse_mode='Markdown'
                )
                raise

            if not raw_questions:
                await msg.edit_text(
                    "❌ *No Questions Found*\n\n"
                    "The AI couldn't extract any questions.\n\n"
                    "💡 *Possible reasons:*\n"
                    "• Image quality too low\n"
                    "• No questions in the image\n"
                    "• API key issue\n\n"
                    "Check messages above for details.",
                    parse_mode='Markdown'
                )
                return

            # ===== FIX QUESTION FORMAT FOR POSTING =====
            questions = self._normalize_questions(raw_questions)

            # Store in session
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"gen_{user_id}_{timestamp}"
            
            self.bot_handlers.user_states[user_id] = {
                'questions': questions,
                'session_id': session_id,
                'source': 'generated'
            }

            await msg.edit_text(
                f"✅ *Processing complete!*\n\n"
                f"📊 Questions: {len(questions)}\n"
                f"📦 Generating files...",
                parse_mode='Markdown'
            )

            # ===== AUTO-GENERATE 3 FILES =====
            await self.auto_generate_files(user_id, questions, timestamp, context, msg)

            # Cleanup
            for p in content_paths:
                if p.exists():
                    p.unlink(missing_ok=True)

        except Exception as e:
            print(f"❌ Error processing: {e}")
            import traceback
            traceback.print_exc()
            
            if msg:
                await msg.edit_text(
                    f"❌ *Processing Error*\n\n"
                    f"`{str(e)[:200]}`",
                    parse_mode='Markdown'
                )
            raise

    def _normalize_questions(self, raw_questions: List[Dict]) -> List[Dict]:
        """
        Normalize questions to format expected by quiz_poster
        
        Input format (from Gemini):
        {
            'question': str,
            'options': {'A': str, 'B': str, ...},
            'correct_answer': 'A',
            'explanation': str
        }
        
        Output format (for posting):
        {
            'question_description': str,
            'options': [str, str, ...],
            'correct_answer_index': int,
            'correct_option': str,
            'explanation': str
        }
        """
        normalized = []
        
        for q in raw_questions:
            # Get options as list
            opts_dict = q.get('options', {})
            options = []
            for letter in ['A', 'B', 'C', 'D', 'E']:
                opt = opts_dict.get(letter)
                if opt:
                    options.append(opt)
            
            # Get correct answer index
            correct_letter = q.get('correct_answer', 'A').upper()
            correct_idx = ord(correct_letter) - ord('A')
            
            # Ensure index is valid
            if correct_idx < 0 or correct_idx >= len(options):
                correct_idx = 0
                correct_letter = 'A'
            
            normalized.append({
                'question_description': q.get('question', ''),
                'options': options,
                'correct_answer_index': correct_idx,
                'correct_option': correct_letter,
                'explanation': q.get('explanation', '')
            })
        
        return normalized

    async def auto_generate_files(self, user_id: int, questions: List, timestamp: str, context, progress_msg):
        """AUTO-GENERATE and send CSV, JSON, and PDF - EDIT SINGLE MESSAGE"""
        
        try:
            # ===== 1. GENERATE CSV =====
            await progress_msg.edit_text(
                f"📦 *Generating files...*\n\n"
                f"⏳ CSV...",
                parse_mode='Markdown'
            )
            
            csv_path = config.OUTPUT_DIR / f"questions_{timestamp}.csv"
            
            # Convert to CSV format
            csv_questions = []
            for q in questions:
                csv_q = {
                    'questions': q.get('question_description', ''),
                    'option1': q['options'][0] if len(q['options']) > 0 else '',
                    'option2': q['options'][1] if len(q['options']) > 1 else '',
                    'option3': q['options'][2] if len(q['options']) > 2 else '',
                    'option4': q['options'][3] if len(q['options']) > 3 else '',
                    'option5': q['options'][4] if len(q['options']) > 4 else '',
                    'answer': str(q.get('correct_answer_index', 0) + 1),
                    'explanation': q.get('explanation', ''),
                    'type': '1',
                    'section': '1'
                }
                csv_questions.append(csv_q)
            
            CSVGenerator.questions_to_csv(csv_questions, csv_path)
            
            # ===== 2. GENERATE JSON =====
            await progress_msg.edit_text(
                f"📦 *Generating files...*\n\n"
                f"✅ CSV\n"
                f"⏳ JSON...",
                parse_mode='Markdown'
            )
            
            json_questions = []
            for q in questions:
                json_q = {
                    'question': q.get('question_description', ''),
                    'options': {},
                    'correct_answer': q.get('correct_option', 'A'),
                    'explanation': q.get('explanation', '')
                }
                
                for i, opt in enumerate(q['options']):
                    if opt:
                        json_q['options'][chr(65 + i)] = opt
                
                json_questions.append(json_q)
            
            json_path = config.OUTPUT_DIR / f"questions_{timestamp}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_questions, f, ensure_ascii=False, indent=2)
            
            # ===== 3. GENERATE PDF =====
            await progress_msg.edit_text(
                f"📦 *Generating files...*\n\n"
                f"✅ CSV\n"
                f"✅ JSON\n"
                f"⏳ PDF...",
                parse_mode='Markdown'
            )
            
            from processors.pdf_exporter import pdf_exporter
            
            pdf_title = f"MCQ_Questions_{timestamp}"
            pdf_path = config.OUTPUT_DIR / f"questions_{timestamp}.pdf"
            
            cleaned = pdf_exporter.cleanup_questions(questions)
            pdf_exporter.generate_beautiful_pdf(cleaned, pdf_path, pdf_title)
            
            # ===== SEND ALL 3 FILES =====
            await progress_msg.edit_text(
                f"📦 *Files generated!*\n\n"
                f"✅ CSV\n"
                f"✅ JSON\n"
                f"✅ PDF\n\n"
                f"📤 Sending...",
                parse_mode='Markdown'
            )
            
            # Send CSV
            with open(csv_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.csv",
                    caption="📊 **CSV Format**",
                    parse_mode='Markdown'
                )
            
            # Send JSON
            with open(json_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.json",
                    caption="📋 **JSON Format**",
                    parse_mode='Markdown'
                )
            
            # Send PDF with buttons
            session_id = self.bot_handlers.user_states[user_id]['session_id']
            
            keyboard = [
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")]
            ]
            
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.pdf",
                    caption=f"📄 **PDF Format**\n"
                            f"🎨 Beautiful design\n\n"
                            f"📊 **{len(questions)} questions**\n\n"
                            f"Ready to post! 🎉",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            
            # Cleanup files
            csv_path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)
            pdf_path.unlink(missing_ok=True)
            
            # Final message - DELETE instead of edit
            await progress_msg.delete()
            
        except Exception as e:
            print(f"❌ Error generating files: {e}")
            import traceback
            traceback.print_exc()
            
            await progress_msg.edit_text(
                f"⚠️ **Error**\n\n{str(e)[:100]}",
                parse_mode='Markdown'
            )

    async def post_quizzes_to_destination(self, user_id, chat_id, thread_id, context, status_msg, custom_message=None):
        """Post quizzes with custom message and pin - EDIT SINGLE MESSAGE"""
        if user_id not in self.bot_handlers.user_states:
            return

        questions = self.bot_handlers.user_states[user_id]['questions']
        settings = db.get_user_settings(user_id)

        await status_msg.edit_text(
            f"📢 *Starting...*\n\n"
            f"📊 Total: {len(questions)} quizzes",
            parse_mode='Markdown'
        )

        # Pin custom message if provided
        pinned_msg_id = None
        if custom_message:
            try:
                pin_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=custom_message,
                    message_thread_id=thread_id
                )
                # Try to pin
                try:
                    await context.bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=pin_msg.message_id,
                        disable_notification=True
                    )
                    pinned_msg_id = pin_msg.message_id
                except:
                    pass  # Might not have permission
            except Exception as e:
                print(f"⚠️ Could not send/pin message: {e}")

        # Progress callback - EDIT SINGLE MESSAGE
        async def progress(current, total, success, failed):
            try:
                pct = int((current / total) * 100)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                await status_msg.edit_text(
                    f"📊 *Posting...*\n\n"
                    f"`[{bar}]` {pct}%\n"
                    f"{current}/{total}\n"
                    f"✅ {success}  ❌ {failed}",
                    parse_mode='Markdown'
                )
            except:
                pass

        # Post with custom message
        result = await quiz_poster.post_quizzes_batch(
            context, chat_id, questions,
            settings['quiz_marker'], settings['explanation_tag'],
            thread_id, progress, None,  # Don't send custom message again
            user_id=user_id
        )

        # Final summary
        await status_msg.edit_text(
            f"✅ *Complete!*\n\n"
            f"📊 Total: {result['total']}\n"
            f"✅ Success: {result['success']}\n"
            f"❌ Failed: {result['failed']}\n"
            f"⏭️ Skipped: {result['skipped']}\n\n"
            f"📤 Counter sent!",
            parse_mode='Markdown'
        )

        # Cleanup
        self.bot_handlers.user_states.pop(user_id, None)
