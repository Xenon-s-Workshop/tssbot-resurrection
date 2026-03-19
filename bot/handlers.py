"""
Bot command & message handlers.
Fixes:
- /start with rich description + action buttons
- /help with step-by-step guide
- Settings: quiz_marker, explanation_tag, pdf_mode
- KeyError: 'quiz_marker' — safe .get() with defaults everywhere
- session state guarded per user
- /collectpolls support
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import config
from database import db
from processors.csv_processor import CSVParser
from utils.queue_manager import task_queue
from utils.auth import require_auth

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(self, pdf_processor):
        self.pdf_processor = pdf_processor
        # Per-user session state (in-memory, survives restarts via DB)
        self.user_states: dict = {}

    # ── /start ────────────────────────────────────────────────────────────────

    @require_auth
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        settings = db.get_user_settings(user_id)

        text = (
            f"👋 *Welcome, {user.first_name}!*\n\n"
            "I am your *Telegram Quiz Bot* — I turn PDFs, images, and CSV files "
            "into Telegram quiz polls.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📌 *What I can do*\n"
            "• Extract MCQs from PDFs & images via Gemini AI\n"
            "• Generate MCQs from textbook content\n"
            "• Export quizzes as *CSV*, *JSON*, and *PDF*\n"
            "• Post quizzes to any channel or group\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *Quick Start*\n"
            "1️⃣ Send me a *PDF* or *image*\n"
            "2️⃣ Choose *Extraction* or *Generation* mode\n"
            "3️⃣ Receive CSV + JSON + PDF exports\n"
            "4️⃣ Tap *Post Quiz* to push to your channels\n\n"
            f"⚙️ Current marker: `{settings.get('quiz_marker', config.DEFAULT_QUIZ_MARKER)}`\n"
            f"📄 PDF mode: `{settings.get('pdf_mode', config.DEFAULT_PDF_MODE)}`"
        )

        keyboard = [
            [
                InlineKeyboardButton("📄 Generate Quiz", callback_data="menu_generate"),
                InlineKeyboardButton("📢 Post Quiz", callback_data="menu_post"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
                InlineKeyboardButton("❓ Help", callback_data="menu_help"),
            ],
        ]
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── /help ─────────────────────────────────────────────────────────────────

    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "📚 *Help & Usage Guide*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 *Supported Inputs*\n"
            "• PDF files (single or multi-page)\n"
            "• Images (JPG, PNG — one or multiple)\n"
            "• CSV files (exported from this bot)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔄 *Workflow*\n"
            "1. Send a PDF or image\n"
            "2. Choose a mode:\n"
            "   • *Extraction* — extracts existing MCQs\n"
            "   • *Generation* — generates new MCQs from content\n"
            "3. Wait for processing (progress shown live)\n"
            "4. Receive three export files:\n"
            "   • 📊 CSV — reimportable question list\n"
            "   • 📋 JSON — structured data\n"
            "   • 📄 PDF — printable quiz\n"
            "5. Tap *Post Quiz* → choose destination → done!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📤 *Posting Flow*\n"
            "• Step 1: Optional header message\n"
            "• Step 2: Pick a channel or group\n"
            "• Step 3: Bot posts quizzes with live progress\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 *CSV Format* (for import)\n"
            "`question, option_a, option_b, option_c, option_d,`\n"
            "`correct_answer (A/B/C/D), explanation`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⌨️ *Commands*\n"
            "/start — Main menu\n"
            "/help — This guide\n"
            "/settings — Configure channels, markers, PDF mode\n"
            "/info — Show current chat ID\n"
            "/queue — Check your queue position\n"
            "/cancel — Cancel current task\n"
            "/collectpolls — Export collected poll answers"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    # ── /settings ─────────────────────────────────────────────────────────────

    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._send_settings_menu(update.effective_user.id, update.message)

    async def _send_settings_menu(self, user_id: int, message_or_query):
        settings = db.get_user_settings(user_id)
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        pdf_mode = settings.get("pdf_mode", config.DEFAULT_PDF_MODE)
        marker = settings.get("quiz_marker", config.DEFAULT_QUIZ_MARKER)
        tag = settings.get("explanation_tag", config.DEFAULT_EXPLANATION_TAG)

        text = (
            "⚙️ *Settings*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📢 *Quiz Marker* — shown before every question\n"
            f"Current: `{marker}`\n"
            f"_Preview: \"{marker}\\n\\nWhat is 2+2?\"_\n\n"
            "🏷️ *Explanation Tag* — appended to every explanation\n"
            f"Current: `{tag}`\n"
            f"_Preview: \"Paris is the capital. [{tag}]\"_\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 PDF Mode: `{pdf_mode}`\n"
            f"📺 Channels: {len(channels)} | 👥 Groups: {len(groups)}"
        )
        keyboard = [
            [
                InlineKeyboardButton("✏️ Change Quiz Marker", callback_data="set_quiz_marker"),
            ],
            [
                InlineKeyboardButton("✏️ Change Explanation Tag", callback_data="set_explanation_tag"),
            ],
            [
                InlineKeyboardButton(
                    f"📄 PDF: {'Inline ✅' if pdf_mode == 'inline' else 'Inline'}",
                    callback_data="set_pdf_inline",
                ),
                InlineKeyboardButton(
                    f"📄 PDF: {'Answer Key ✅' if pdf_mode == 'answer_key' else 'Answer Key'}",
                    callback_data="set_pdf_answer_key",
                ),
            ],
            [
                InlineKeyboardButton("➕ Add Channel", callback_data="settings_add_channel"),
                InlineKeyboardButton("➕ Add Group", callback_data="settings_add_group"),
            ],
            [
                InlineKeyboardButton("📺 Manage Channels", callback_data="settings_manage_channels"),
                InlineKeyboardButton("👥 Manage Groups", callback_data="settings_manage_groups"),
            ],
        ]
        markup = InlineKeyboardMarkup(keyboard)

        if hasattr(message_or_query, "reply_text"):
            await message_or_query.reply_text(text, parse_mode="Markdown", reply_markup=markup)
        else:
            await message_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

    # ── /info ─────────────────────────────────────────────────────────────────

    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        await update.message.reply_text(
            f"📊 *Chat Info*\n\nID: `{chat.id}`\nType: `{chat.type}`",
            parse_mode="Markdown",
        )

    # ── /model ────────────────────────────────────────────────────────────────

    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"🤖 *Model Info*\n\n"
            f"Model: `{config.GEMINI_MODEL}`\n"
            f"Workers: `{config.MAX_CONCURRENT_IMAGES}`\n"
            f"Queue: `{task_queue.get_queue_size()}/{config.MAX_QUEUE_SIZE}`",
            parse_mode="Markdown",
        )

    # ── /queue ────────────────────────────────────────────────────────────────

    @require_auth
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if task_queue.is_processing(user_id):
            await update.message.reply_text("⚙️ Your task is currently being processed…")
        else:
            pos = task_queue.get_position(user_id)
            if pos > 0:
                await update.message.reply_text(f"📋 Queue position: *{pos}*", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ You have no active tasks.")

    # ── /cancel ───────────────────────────────────────────────────────────────

    @require_auth
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        task_queue.clear_user(user_id)
        self.user_states.pop(user_id, None)
        await update.message.reply_text("✅ Task cancelled and session cleared.")

    # ── /collectpolls ─────────────────────────────────────────────────────────

    @require_auth
    async def collect_polls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        polls = db.get_user_polls(user_id)
        if not polls:
            await update.message.reply_text("📭 No polls collected yet.")
            return

        lines = [f"📊 *Collected Polls* ({len(polls)} total)\n"]
        for i, p in enumerate(polls[:50], 1):
            data = p.get("data") or {}
            q = data.get("question") or "Unknown"
            lines.append(f"{i}. {q[:80]}")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )

        # Offer export
        keyboard = [[InlineKeyboardButton("📥 Export All (CSV + JSON + PDF)", callback_data="export_polls")]]
        await update.message.reply_text(
            "Tap below to export all collected poll data as *CSV*, *JSON*, and *PDF*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── Document handler ──────────────────────────────────────────────────────

    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        doc = update.message.document
        filename = doc.file_name or ""

        if filename.lower().endswith(".csv"):
            await self._handle_csv(update, context)
            return

        if not filename.lower().endswith(".pdf"):
            await update.message.reply_text("❌ Please send a *PDF* or *CSV* file.", parse_mode="Markdown")
            return

        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ You already have a task in progress. Use /cancel to reset.")
            return

        msg = await update.message.reply_text("📥 Downloading PDF…")
        try:
            file = await context.bot.get_file(doc.file_id)
            path = config.TEMP_DIR / f"{user_id}_{filename}"
            await file.download_to_drive(path)

            self.user_states[user_id] = {"content_type": "pdf", "content_paths": [path]}

            keyboard = [
                [InlineKeyboardButton("📤 Extraction Mode", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation Mode", callback_data="mode_generation")],
            ]
            await msg.edit_text(
                f"📄 *PDF received!* ({filename})\n\nChoose processing mode:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"Document download error: {e}")
            await msg.edit_text(f"❌ Failed to download file: {e}")

    async def _handle_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ Task in progress. Use /cancel first.")
            return

        msg = await update.message.reply_text("📊 Processing CSV file…")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            content = bytes(await file.download_as_bytearray())
            questions = CSVParser.parse_csv_file(content)

            if not questions:
                await msg.edit_text("❌ No valid questions found in CSV. Check format and try again.")
                return

            session_id = f"csv_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.user_states[user_id] = {
                "questions": questions,
                "session_id": session_id,
                "source": "csv",
            }

            keyboard = [[InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")]]
            await msg.edit_text(
                f"✅ CSV loaded! *{len(questions)}* questions ready.\n\nTap below to post them.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"CSV handling error: {e}")
            await msg.edit_text(f"❌ Error processing CSV: {e}")

    # ── Photo handler ─────────────────────────────────────────────────────────

    @require_auth
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ Task in progress. Use /cancel first.")
            return

        msg = await update.message.reply_text("📥 Downloading image…")
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            path = config.TEMP_DIR / f"{user_id}_image.jpg"
            await file.download_to_drive(path)

            self.user_states[user_id] = {"content_type": "images", "content_paths": [path]}

            keyboard = [
                [InlineKeyboardButton("📤 Extraction Mode", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation Mode", callback_data="mode_generation")],
            ]
            await msg.edit_text(
                "🖼️ *Image received!*\n\nChoose processing mode:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"Photo handling error: {e}")
            await msg.edit_text(f"❌ Error: {e}")

    # ── Queue helper ──────────────────────────────────────────────────────────

    async def add_to_queue_direct(self, user_id: int, page_range, context):
        state = self.user_states.get(user_id)
        if not state:
            await context.bot.send_message(user_id, "❌ Session expired. Please re-send your file.")
            return

        task_data = {
            "content_type": state["content_type"],
            "content_paths": state["content_paths"],
            "page_range": page_range,
            "mode": state.get("mode", "extraction"),
            "context": context,
        }
        pos = task_queue.add_task(user_id, task_data)

        if pos == -1:
            msg = "❌ Queue is full. Please try again shortly."
        elif pos == -2:
            msg = "⚠️ You already have a task queued. Use /cancel to reset."
        else:
            msg = f"✅ Added to queue! Position: *{pos}*"

        await context.bot.send_message(user_id, msg, parse_mode="Markdown")

    # ── Auth management (/adduser, /removeuser, /listusers) ──────────────────

    @require_auth
    async def adduser_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Usage: /adduser <user_id> [admin]"""
        caller_id = update.effective_user.id
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: `/adduser <user_id> [admin]`\n"
                "_Example: `/adduser 123456789`_\n"
                "_Example: `/adduser 123456789 admin`_",
                parse_mode="Markdown",
            )
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID — must be a number.")
            return

        role = "admin" if len(args) > 1 and args[1].lower() == "admin" else "user"
        db.add_authorized_user(target_id, added_by=caller_id, role=role)
        await update.message.reply_text(
            f"✅ User `{target_id}` added with role: *{role}*", parse_mode="Markdown"
        )

    @require_auth
    async def removeuser_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Usage: /removeuser <user_id>"""
        import os
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: `/removeuser <user_id>`", parse_mode="Markdown")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
            return

        # Prevent removing owner
        owner_id_str = os.getenv("OWNER_ID", "")
        if owner_id_str:
            try:
                if target_id == int(owner_id_str):
                    await update.message.reply_text("🔒 Cannot remove the bot owner.")
                    return
            except ValueError:
                pass

        removed = db.remove_authorized_user(target_id)
        if removed:
            await update.message.reply_text(f"✅ User `{target_id}` removed.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ User `{target_id}` was not in the auth list.", parse_mode="Markdown")

    @require_auth
    async def listusers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all authorised users."""
        users = db.list_authorized_users()
        if not users:
            await update.message.reply_text("📭 No users in the auth list yet.\nUse `/adduser <id>` to add one.", parse_mode="Markdown")
            return
        lines = ["👥 *Authorised Users*\n"]
        for u in users:
            uid = u.get("user_id")
            role = u.get("role", "user")
            icon = "🔑" if role == "admin" else "👤"
            lines.append(f"{icon} `{uid}` — {role}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    # ── Poll answer listener ──────────────────────────────────────────────────

    async def handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect poll answers when users respond to quiz polls."""
        try:
            answer = update.poll_answer
            if not answer:
                return
            user_id = answer.user.id
            poll_id = answer.poll_id
            db.store_poll(
                user_id,
                poll_id,
                {
                    "poll_id": poll_id,
                    "user_id": user_id,
                    "option_ids": answer.option_ids,
                },
            )
        except Exception as e:
            logger.error(f"Poll answer handler error: {e}")
