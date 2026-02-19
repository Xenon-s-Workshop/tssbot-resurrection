"""
Content Processor - WITH DUAL AI SUPPORT + PROGRESS BARS
Routes to Gemini or DeepSeek based on per-user setting
"""

import asyncio
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
        try:
            # Pick processor based on user's chosen AI provider
            processor = self.bot_handlers.get_processor(user_id)
            settings = db.get_user_settings(user_id)
            provider = settings.get('ai_provider', 'gemini')
            provider_label = "🟢 Gemini" if provider == 'gemini' else f"🔵 DeepSeek ({settings.get('deepseek_model','')})"

            if content_type == 'pdf':
                msg = await context.bot.send_message(
                    user_id,
                    f"🔄 Processing PDF...\n"
                    f"📄 Pages: {'All' if not page_range else f'{page_range[0]}-{page_range[1]}'}\n"
                    f"🤖 AI: {provider_label}"
                )
                images = await PDFProcessor.pdf_to_images(content_paths[0], page_range)
            else:
                msg = await context.bot.send_message(
                    user_id,
                    f"🔄 Processing images...\n🤖 AI: {provider_label}"
                )
                images = [await ImageProcessor.load_image(p) for p in content_paths]

            total = len(images)

            async def progress(current, total_pages):
                try:
                    pct = int((current / total_pages) * 100)
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    await msg.edit_text(
                        f"🔍 *Processing...*\n\n"
                        f"`[{bar}]` {pct}%\n"
                        f"Page {current} of {total_pages}\n"
                        f"🤖 AI: {provider_label}\n"
                        f"Mode: {mode}",
                        parse_mode='Markdown'
                    )
                except:
                    pass

            questions = await processor.process_images_parallel(images, mode, progress)

            if not questions:
                await msg.edit_text("❌ No questions found. Try switching AI provider in /settings")
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"gen_{user_id}_{timestamp}"
            csv_path = config.OUTPUT_DIR / f"questions_{session_id}.csv"
            CSVGenerator.questions_to_csv(questions, csv_path)

            self.bot_handlers.user_states[user_id] = {
                'questions': questions,
                'session_id': session_id,
                'csv_path': csv_path,
                'source': 'generated'
            }

            keyboard = [
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("📄 Export PDF", callback_data=f"export_pdf_{session_id}")]
            ]

            with open(csv_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"mcq_{timestamp}.csv",
                    caption=f"✅ *Complete!*\n\n"
                            f"📊 Questions: {len(questions)}\n"
                            f"🤖 AI: {provider_label}\n\n"
                            f"Choose action:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )

            await msg.edit_text(
                f"✅ Done! {len(questions)} questions\n🤖 {provider_label}"
            )

            for p in content_paths:
                if p.exists():
                    p.unlink(missing_ok=True)

        except Exception as e:
            await context.bot.send_message(user_id, f"❌ Error: {e}")
            raise

    async def post_quizzes_to_destination(self, user_id, chat_id, thread_id, context, status_msg):
        if user_id not in self.bot_handlers.user_states:
            return

        questions = self.bot_handlers.user_states[user_id]['questions']
        settings = db.get_user_settings(user_id)

        await status_msg.edit_text(f"📢 Starting: {len(questions)} quizzes...")

        async def progress(current, total, success, failed):
            try:
                pct = int((current / total) * 100)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                await status_msg.edit_text(
                    f"📊 *Posting Quizzes...*\n\n"
                    f"`[{bar}]` {pct}%\n"
                    f"Quiz {current} of {total}\n"
                    f"✅ Success: {success}  ❌ Failed: {failed}",
                    parse_mode='Markdown'
                )
            except:
                pass

        result = await QuizPoster.post_quizzes_batch(
            context, chat_id, questions,
            settings['quiz_marker'], settings['explanation_tag'],
            thread_id, progress
        )

        await status_msg.edit_text(
            f"✅ *Posting Complete!*\n\n"
            f"📊 Total: {result['total']}\n"
            f"✅ Success: {result['success']}\n"
            f"❌ Failed: {result['failed']}\n"
            f"⏭️ Skipped: {result['skipped']}",
            parse_mode='Markdown'
        )

        self.bot_handlers.user_states.pop(user_id, None)
