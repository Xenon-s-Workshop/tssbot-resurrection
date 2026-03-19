"""
ContentProcessor orchestrates the full pipeline:
  PDF/Image → Gemini → questions → CSV + JSON + PDF → Post button

Post flow:
  Step 1: Header (optional, skippable)
  Step 2: Destination select (disable UI after click)
  Step 3: Post with progress bar
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import config
from database import db
from processors.csv_processor import CSVGenerator
from processors.image_processor import ImageProcessor
from processors.quiz_poster import QuizPoster
from processors.pdf_processor import PDFProcessor
from processors.pdf_generator import generate_pdf

logger = logging.getLogger(__name__)


class ContentProcessor:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    # ── Main processing pipeline ──────────────────────────────────────────────

    async def process_content(
        self,
        user_id: int,
        content_type: str,
        content_paths: list,
        page_range,
        mode: str,
        context,
    ):
        try:
            # ── Step 1: Convert to images ─────────────────────────────────
            if content_type == "pdf":
                msg = await context.bot.send_message(
                    user_id, "🔄 *Converting PDF to images…*", parse_mode="Markdown"
                )
                images = await PDFProcessor.pdf_to_images(content_paths[0], page_range)
            else:
                msg = await context.bot.send_message(
                    user_id, "🔄 *Loading images…*", parse_mode="Markdown"
                )
                images = [await ImageProcessor.load_image(p) for p in content_paths]

            total_pages = len(images)
            await msg.edit_text(
                f"🤖 *Processing {total_pages} page(s) with Gemini AI…*",
                parse_mode="Markdown",
            )

            # ── Step 2: Extract questions ─────────────────────────────────
            async def progress(current, total):
                try:
                    bar = _progress_bar(current, total)
                    await msg.edit_text(
                        f"🔍 *Analysing pages…*\n{bar}\n`{current}/{total}` pages done",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

            questions = await self.bot_handlers.pdf_processor.process_images_parallel(
                images, mode, progress
            )

            if not questions:
                await msg.edit_text("❌ No questions could be extracted. Try a different mode or file.")
                return

            await msg.edit_text(
                f"✅ *Extracted {len(questions)} questions!*\n\n📦 Building exports…",
                parse_mode="Markdown",
            )

            # ── Step 3: Build exports ─────────────────────────────────────
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"gen_{user_id}_{timestamp}"

            csv_path = config.OUTPUT_DIR / f"quiz_{session_id}.csv"
            json_path = config.OUTPUT_DIR / f"quiz_{session_id}.json"
            pdf_path = config.OUTPUT_DIR / f"quiz_{session_id}.pdf"

            settings = db.get_user_settings(user_id)
            pdf_mode = settings.get("pdf_mode", config.DEFAULT_PDF_MODE)

            # Write CSV
            CSVGenerator.questions_to_csv(questions, csv_path)

            # Write JSON
            CSVGenerator.questions_to_json(questions, json_path)

            # Write PDF
            try:
                await msg.edit_text(
                    f"✅ *{len(questions)} questions extracted!*\n\n📄 Generating PDF…",
                    parse_mode="Markdown",
                )
                generate_pdf(
                    questions,
                    mode=pdf_mode,
                    engine="reportlab",
                    title=f"Quiz — {timestamp}",
                    output_path=pdf_path,
                )
                pdf_ok = True
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")
                pdf_ok = False

            # ── Step 4: Save session state ────────────────────────────────
            self.bot_handlers.user_states[user_id] = {
                "questions": questions,
                "session_id": session_id,
                "csv_path": csv_path,
                "json_path": json_path,
                "pdf_path": pdf_path if pdf_ok else None,
                "source": "generated",
            }

            # ── Step 5: Send exports to user ──────────────────────────────
            await msg.edit_text(
                f"✅ *Done! {len(questions)} questions ready.*\n\n📤 Sending export files…",
                parse_mode="Markdown",
            )

            post_button = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")]]
            )

            # Send CSV
            if csv_path.exists():
                with open(csv_path, "rb") as f:
                    await context.bot.send_document(
                        user_id,
                        f,
                        filename=f"quiz_{timestamp}.csv",
                        caption="📊 *CSV Export* — import back into this bot anytime",
                        parse_mode="Markdown",
                    )

            # Send JSON
            if json_path.exists():
                with open(json_path, "rb") as f:
                    await context.bot.send_document(
                        user_id,
                        f,
                        filename=f"quiz_{timestamp}.json",
                        caption="📋 *JSON Export* — structured question data",
                        parse_mode="Markdown",
                    )

            # Send PDF
            if pdf_ok and pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    await context.bot.send_document(
                        user_id,
                        f,
                        filename=f"quiz_{timestamp}.pdf",
                        caption=(
                            f"📄 *PDF Export* — mode: `{pdf_mode}`\n"
                            "Ready to print or share!"
                        ),
                        parse_mode="Markdown",
                        reply_markup=post_button,
                    )
            else:
                await context.bot.send_message(
                    user_id,
                    f"✅ *{len(questions)} questions ready!*\nTap below to post them as Telegram quizzes.",
                    parse_mode="Markdown",
                    reply_markup=post_button,
                )

            await msg.edit_text(
                f"🎉 *All done!* {len(questions)} questions extracted and exported.\n"
                "Use the *Post Quizzes* button to send them to your channels."
            )

            # Cleanup temp files
            for p in content_paths:
                try:
                    if Path(p).exists():
                        Path(p).unlink()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"process_content error for user {user_id}: {e}", exc_info=True)
            try:
                await context.bot.send_message(
                    user_id,
                    f"❌ *Processing failed:* {e}\n\nPlease try again or use /cancel to reset.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    # ── Posting pipeline ──────────────────────────────────────────────────────

    async def start_post_flow(self, user_id: int, session_id: str, query):
        """Step 1: Ask for optional header message."""
        state = self.bot_handlers.user_states.get(user_id)
        if not state or state.get("session_id") != session_id:
            await query.edit_message_text("❌ Session expired. Please re-process your file.")
            return

        state["posting_step"] = "header"
        state["session_id"] = session_id

        keyboard = [
            [InlineKeyboardButton("⏭️ Skip Header", callback_data=f"skip_header_{session_id}")]
        ]
        await query.edit_message_text(
            "📝 *Step 1/3 — Header Message*\n\n"
            "Send a message to appear before the quizzes, or tap *Skip*.\n"
            "_Example: 📚 Today's Biology Quiz — Good luck!_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def show_destination_selector(self, user_id: int, query, context):
        """Step 2: Select channel or group."""
        state = self.bot_handlers.user_states.get(user_id)
        if not state:
            await query.edit_message_text("❌ Session expired.")
            return

        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)

        if not channels and not groups:
            await query.edit_message_text(
                "❌ *No destinations configured.*\n\nUse /settings to add a channel or group first.",
                parse_mode="Markdown",
            )
            return

        session_id = state.get("session_id", "")
        keyboard = []

        for ch in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"📺 {ch['channel_name']}",
                    callback_data=f"dest_ch_{ch['channel_id']}_{session_id}",
                )
            ])
        for g in groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"👥 {g['group_name']}",
                    callback_data=f"dest_g_{g['group_id']}_{session_id}",
                )
            ])

        n = len(state.get("questions") or [])
        await query.edit_message_text(
            f"📡 *Step 2/3 — Choose Destination*\n\n"
            f"*{n}* quizzes will be posted to the selected destination.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        state["posting_step"] = "destination"

    async def post_quizzes_to_destination(
        self,
        user_id: int,
        chat_id: int,
        thread_id,
        context,
        status_msg,
    ):
        """Step 3: Post all quizzes with live progress."""
        state = self.bot_handlers.user_states.get(user_id)
        if not state:
            await status_msg.edit_text("❌ Session expired.")
            return

        questions = state.get("questions") or []
        settings = db.get_user_settings(user_id)
        quiz_marker = settings.get("quiz_marker", config.DEFAULT_QUIZ_MARKER)
        explanation_tag = settings.get("explanation_tag", config.DEFAULT_EXPLANATION_TAG)
        header = state.get("header_message")

        total = len(questions)
        await status_msg.edit_text(
            f"📢 *Step 3/3 — Posting {total} quizzes…*\n\n⏳ Starting…",
            parse_mode="Markdown",
        )

        async def progress(current, total):
            try:
                bar = _progress_bar(current, total)
                await status_msg.edit_text(
                    f"📢 *Posting quizzes…*\n{bar}\n`{current}/{total}` sent",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        result = await QuizPoster.post_quizzes_batch(
            context,
            chat_id,
            questions,
            quiz_marker,
            explanation_tag,
            thread_id,
            progress,
            header,
        )

        # Build result summary
        lines = [
            f"🎉 *Posting Complete!*\n",
            f"✅ Success: {result['success']}/{result['total']}",
        ]
        if result["failed"]:
            lines.append(f"❌ Failed: {result['failed']}")
        if result["skipped"]:
            lines.append(f"⏭️ Skipped: {result['skipped']}")
        if result.get("failures"):
            lines.append("\n*Failure details:*")
            for f in result["failures"][:5]:
                lines.append(f"`{f}`")
            if len(result["failures"]) > 5:
                lines.append(f"…and {len(result['failures'])-5} more")

        await status_msg.edit_text("\n".join(lines), parse_mode="Markdown")

        # Clear session
        self.bot_handlers.user_states.pop(user_id, None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _progress_bar(current: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "▱" * width
    filled = int(width * current / total)
    return "▰" * filled + "▱" * (width - filled)
