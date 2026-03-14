"""
Content Processor - WITH AUTO FILE GENERATION & ERROR REPORTING
After processing completes, automatically generates and sends:
1. CSV file
2. JSON file
3. PDF file (beautiful format)

NOW WITH: User error messages sent to Telegram
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
from processors.quiz_poster import QuizPoster
from processors.pdf_processor import PDFProcessor

class ContentProcessor:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    async def process_content(self, user_id, content_type, content_paths, page_range, mode, context):
        """Process content and AUTO-GENERATE 3 files - WITH ERROR REPORTING"""
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

            await context.bot.send_message(
                user_id,
                f"✅ *Extracted {total} images*\n"
                f"🤖 Starting AI processing...",
                parse_mode='Markdown'
            )

            # Progress callback
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

            # Get processor based on user settings
            processor = self.bot_handlers.get_processor(user_id)
            
            # Process images - WITH ERROR REPORTING
            try:
                questions = await processor.process_images_parallel(
                    images, 
                    mode, 
                    progress,
                    user_id=user_id,    # ← PASS USER ID FOR ERROR REPORTING
                    context=context      # ← PASS CONTEXT FOR ERROR REPORTING
                )
            except Exception as e:
                await context.bot.send_message(
                    user_id,
                    f"❌ *AI Processing Failed*\n\n"
                    f"Error: `{str(e)[:200]}`\n\n"
                    f"💡 Check if your API keys are valid:\n"
                    f"https://aistudio.google.com/apikey",
                    parse_mode='Markdown'
                )
                raise

            if not questions:
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
                f"📦 Generating files..."
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
            
            await context.bot.send_message(
                user_id,
                f"❌ *Processing Error*\n\n"
                f"`{str(e)[:200]}`",
                parse_mode='Markdown'
            )
            raise

    async def auto_generate_files(self, user_id: int, questions: List, timestamp: str, context, progress_msg):
        """AUTO-GENERATE and send CSV, JSON, and PDF"""
        
        try:
            # Update progress
            await progress_msg.edit_text(
                f"✅ Processing complete!\n\n"
                f"📊 Questions: {len(questions)}\n\n"
                f"📦 Generating files:\n"
                f"⏳ CSV...",
                parse_mode='Markdown'
            )
            
            # ===== 1. GENERATE CSV =====
            csv_path = config.OUTPUT_DIR / f"questions_{timestamp}.csv"
            CSVGenerator.questions_to_csv(questions, csv_path)
            
            await progress_msg.edit_text(
                f"✅ Processing complete!\n\n"
                f"📊 Questions: {len(questions)}\n\n"
                f"📦 Generating files:\n"
                f"✅ CSV\n"
                f"⏳ JSON...",
                parse_mode='Markdown'
            )
            
            # ===== 2. GENERATE JSON =====
            json_questions = []
            for q in questions:
                json_q = {
                    'question': q.get('question_description', ''),
                    'options': {},
                    'correct_answer': q.get('correct_option', 'A'),
                    'explanation': q.get('explanation', '')
                }
                
                # Add options
                opts = q.get('options', [])
                for i, opt in enumerate(opts):
                    if opt:
                        json_q['options'][chr(65 + i)] = opt
                
                json_questions.append(json_q)
            
            json_path = config.OUTPUT_DIR / f"questions_{timestamp}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_questions, f, ensure_ascii=False, indent=2)
            
            await progress_msg.edit_text(
                f"✅ Processing complete!\n\n"
                f"📊 Questions: {len(questions)}\n\n"
                f"📦 Generating files:\n"
                f"✅ CSV\n"
                f"✅ JSON\n"
                f"⏳ PDF (beautiful format)...",
                parse_mode='Markdown'
            )
            
            # ===== 3. GENERATE PDF =====
            from processors.pdf_exporter import pdf_exporter
            
            pdf_title = f"MCQ_Questions_{timestamp}"
            pdf_path = config.OUTPUT_DIR / f"questions_{timestamp}.pdf"
            
            # Clean questions for PDF
            cleaned = pdf_exporter.cleanup_questions(questions)
            
            # Generate beautiful PDF
            pdf_exporter.generate_beautiful_pdf(cleaned, pdf_path, pdf_title)
            
            await progress_msg.edit_text(
                f"✅ Processing complete!\n\n"
                f"📊 Questions: {len(questions)}\n\n"
                f"📦 Files generated:\n"
                f"✅ CSV\n"
                f"✅ JSON\n"
                f"✅ PDF\n\n"
                f"📤 Sending files...",
                parse_mode='Markdown'
            )
            
            # ===== SEND ALL 3 FILES =====
            
            # Send CSV
            with open(csv_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.csv",
                    caption="📊 **CSV Format**\nImport to spreadsheets",
                    parse_mode='Markdown'
                )
            
            # Send JSON
            with open(json_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.json",
                    caption="📋 **JSON Format**\nFor quiz systems",
                    parse_mode='Markdown'
                )
            
            # Send PDF with action buttons
            session_id = self.bot_handlers.user_states[user_id]['session_id']
            
            keyboard = [
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")]
            ]
            
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.pdf",
                    caption=f"📄 **PDF Format (Beautiful)**\n"
                            f"🎨 Blue headers, green answers\n"
                            f"🌏 Bengali/Unicode supported\n\n"
                            f"📊 Total: {len(questions)} questions\n\n"
                            f"Choose action:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            
            # Cleanup files
            csv_path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)
            pdf_path.unlink(missing_ok=True)
            
            # Final message
            await progress_msg.edit_text(
                f"✅ **All Done!**\n\n"
                f"📊 Questions: {len(questions)}\n"
                f"📦 Files sent: CSV, JSON, PDF\n\n"
                f"Ready to post quizzes! 🎉",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            print(f"❌ Error generating files: {e}")
            import traceback
            traceback.print_exc()
            
            await progress_msg.edit_text(
                f"⚠️ **Files Generated with Errors**\n\n"
                f"Some files may be missing.\n"
                f"Error: {str(e)[:100]}",
                parse_mode='Markdown'
            )

    async def post_quizzes_to_destination(self, user_id, chat_id, thread_id, context, status_msg, custom_message=None):
        """Post quizzes with custom message and success counter"""
        if user_id not in self.bot_handlers.user_states:
            return

        questions = self.bot_handlers.user_states[user_id]['questions']
        settings = db.get_user_settings(user_id)

        await status_msg.edit_text(f"📢 Starting: {len(questions)} quizzes...")

        # Progress callback
        async def progress(current, total, success, failed):
            try:
                pct = int((current / total) * 100)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                await status_msg.edit_text(
                    f"📊 *Posting Quizzes...*\n\n"
                    f"`[{bar}]` {pct}%\n"
                    f"Quiz {current}/{total}\n"
                    f"✅ {success}  ❌ {failed}",
                    parse_mode='Markdown'
                )
            except:
                pass

        # Post with custom message
        result = await QuizPoster.post_quizzes_batch(
            context, chat_id, questions,
            settings['quiz_marker'], settings['explanation_tag'],
            thread_id, progress, custom_message
        )

        # Final summary
        await status_msg.edit_text(
            f"✅ *Posting Complete!*\n\n"
            f"📊 Total: {result['total']}\n"
            f"✅ Success: {result['success']}\n"
            f"❌ Failed: {result['failed']}\n"
            f"⏭️ Skipped: {result['skipped']}\n\n"
            f"📤 Success counter sent to destination!",
            parse_mode='Markdown'
        )

        # Cleanup
        self.bot_handlers.user_states.pop(user_id, None)
