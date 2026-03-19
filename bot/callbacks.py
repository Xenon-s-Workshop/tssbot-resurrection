"""
Callback query and text message handler.
Covers:
- Menu navigation (start screen buttons)
- Mode selection
- Settings editing (quiz_marker, explanation_tag, pdf_mode)
- Add channel / group flow
- Manage / delete channels and groups
- Post flow: header → destination → posting
- Export polls
- All UI disabled after selection (no double-click)
"""

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import config
from database import db

logger = logging.getLogger(__name__)


class CallbackHandlers:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    # ── Dispatcher ────────────────────────────────────────────────────────────

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        try:
            # Menu shortcuts
            if data == "menu_generate":
                await query.edit_message_text(
                    "📄 *Generate Quiz*\n\nSend me a PDF or image and I'll extract/generate MCQs from it.",
                    parse_mode="Markdown",
                )
                return
            if data == "menu_post":
                await query.edit_message_text(
                    "📢 *Post Quiz*\n\nFirst generate a quiz, then tap the *Post Quizzes* button that appears.",
                    parse_mode="Markdown",
                )
                return
            if data == "menu_settings":
                from bot.handlers import BotHandlers
                await self.bot_handlers._send_settings_menu(user_id, query)
                return
            if data == "menu_help":
                await query.edit_message_text(
                    "Use the /help command for the full guide.",
                )
                return

            # Processing mode
            if data.startswith("mode_"):
                await self._handle_mode(query, user_id, data, context)
                return

            # Post flow — start
            if data.startswith("post_"):
                session_id = data[5:]
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.start_post_flow(user_id, session_id, query)
                return

            # Post flow — show destination after header text entered
            if data.startswith("show_dest_"):
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.show_destination_selector(user_id, query, context)
                return

            # Post flow — skip header
            if data.startswith("skip_header_"):
                session_id = data[len("skip_header_"):]
                state = self.bot_handlers.user_states.get(user_id, {})
                state["header_message"] = None
                state["posting_step"] = "destination"
                self.bot_handlers.user_states[user_id] = state
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.show_destination_selector(user_id, query, context)
                return

            # Post flow — channel destination
            if data.startswith("dest_ch_"):
                await self._handle_dest(query, user_id, data, context, is_channel=True)
                return

            # Post flow — group destination
            if data.startswith("dest_g_"):
                await self._handle_dest(query, user_id, data, context, is_channel=False)
                return

            # Settings
            if data == "set_quiz_marker":
                settings = db.get_user_settings(user_id)
                current = settings.get("quiz_marker", config.DEFAULT_QUIZ_MARKER)
                state = self.bot_handlers.user_states.setdefault(user_id, {})
                state["awaiting"] = "quiz_marker"
                await query.edit_message_text(
                    "✏️ *Change Quiz Marker*\n\n"
                    "This text is embedded *before every question* posted to your channels.\n\n"
                    f"Current value: `{current}`\n\n"
                    "Send the new marker text.\n"
                    "_Examples: `[TSS]` · `📚 Daily Quiz` · `🧠 MCQ`_",
                    parse_mode="Markdown",
                )
                return
            if data == "set_explanation_tag":
                settings = db.get_user_settings(user_id)
                current = settings.get("explanation_tag", config.DEFAULT_EXPLANATION_TAG)
                state = self.bot_handlers.user_states.setdefault(user_id, {})
                state["awaiting"] = "explanation_tag"
                await query.edit_message_text(
                    "✏️ *Change Explanation Tag*\n\n"
                    "This text is appended *inside the explanation* of every question, in square brackets.\n\n"
                    f"Current value: `{current}`\n\n"
                    "Send the new tag.\n"
                    "_Examples: `t.me/mychannel` · `@MyChannel` · `Source: NCERT`_",
                    parse_mode="Markdown",
                )
                return
            if data == "set_pdf_inline":
                db.update_user_settings(user_id, "pdf_mode", "inline")
                await self.bot_handlers._send_settings_menu(user_id, query)
                return
            if data == "set_pdf_answer_key":
                db.update_user_settings(user_id, "pdf_mode", "answer_key")
                await self.bot_handlers._send_settings_menu(user_id, query)
                return

            if data == "settings_add_channel":
                state = self.bot_handlers.user_states.setdefault(user_id, {})
                state["awaiting"] = "add_channel"
                await query.edit_message_text(
                    "📺 *Add Channel*\n\n"
                    "1. Add this bot as an *admin* to your channel\n"
                    "2. Forward any message from the channel here, or send the channel ID\n\n"
                    "_Example: `-1001234567890`_",
                    parse_mode="Markdown",
                )
                return
            if data == "settings_add_group":
                state = self.bot_handlers.user_states.setdefault(user_id, {})
                state["awaiting"] = "add_group"
                await query.edit_message_text(
                    "👥 *Add Group*\n\n"
                    "1. Add this bot to your group\n"
                    "2. Use /info inside the group to get the ID\n"
                    "3. Send the group ID here\n\n"
                    "_Example: `-1009876543210`_",
                    parse_mode="Markdown",
                )
                return

            if data == "settings_manage_channels":
                await self._manage_channels(query, user_id)
                return
            if data == "settings_manage_groups":
                await self._manage_groups(query, user_id)
                return
            if data.startswith("del_channel_"):
                doc_id = data[len("del_channel_"):]
                db.delete_channel(doc_id)
                await self._manage_channels(query, user_id)
                return
            if data.startswith("del_group_"):
                doc_id = data[len("del_group_"):]
                db.delete_group(doc_id)
                await self._manage_groups(query, user_id)
                return

            # Export polls
            if data == "export_polls":
                await self._export_polls(query, user_id)
                return

            logger.warning(f"Unhandled callback: {data}")

        except Exception as e:
            logger.error(f"Callback error ({data}): {e}", exc_info=True)
            try:
                await query.edit_message_text(f"❌ An error occurred: {e}")
            except Exception:
                pass

    # ── Text handler (awaiting states) ────────────────────────────────────────

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text or ""
        state = self.bot_handlers.user_states.get(user_id, {})
        awaiting = state.get("awaiting")

        if awaiting == "quiz_marker":
            db.update_user_settings(user_id, "quiz_marker", text.strip())
            state.pop("awaiting", None)
            await update.message.reply_text(
                f"✅ *Quiz Marker updated!*\n\n"
                f"New value: `{text.strip()}`\n\n"
                f"_Preview of how it appears before a question:_\n"
                f"`{text.strip()}`\n\n`What is the capital of France?`",
                parse_mode="Markdown",
            )
            return

        if awaiting == "explanation_tag":
            db.update_user_settings(user_id, "explanation_tag", text.strip())
            state.pop("awaiting", None)
            await update.message.reply_text(
                f"✅ *Explanation Tag updated!*\n\n"
                f"New value: `{text.strip()}`\n\n"
                f"_Preview of how it appears in explanations:_\n"
                f"`Paris is the capital of France. [{text.strip()}]`",
                parse_mode="Markdown",
            )
            return

        if awaiting == "add_channel":
            await self._save_channel_or_group(update, context, user_id, text, "channel")
            state.pop("awaiting", None)
            return

        if awaiting == "add_group":
            await self._save_channel_or_group(update, context, user_id, text, "group")
            state.pop("awaiting", None)
            return

        if state.get("posting_step") == "header":
            state["header_message"] = text.strip()
            state["posting_step"] = "destination"
            session_id = state.get("session_id", "")
            await update.message.reply_text(
                f"✅ Header saved:\n\n_{text[:200]}_\n\nNow select a destination.",
                parse_mode="Markdown",
            )
            # Show destination selector
            keyboard = [[InlineKeyboardButton("➡️ Choose Destination", callback_data=f"show_dest_{session_id}")]]
            await update.message.reply_text(
                "Tap below to choose where to post:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # Unhandled text
        await update.message.reply_text(
            "Send me a PDF, image, or CSV to get started!\nUse /help for the full guide."
        )

    # ── Mode handler ──────────────────────────────────────────────────────────

    async def _handle_mode(self, query, user_id: int, data: str, context):
        mode = data.split("_", 1)[1]
        if user_id not in self.bot_handlers.user_states:
            await query.edit_message_text("❌ Session expired. Please re-send your file.")
            return

        self.bot_handlers.user_states[user_id]["mode"] = mode
        mode_label = "Extraction" if mode == "extraction" else "Generation"

        await query.edit_message_text(
            f"⚙️ *{mode_label} mode selected.*\n\nAdding to processing queue…",
            parse_mode="Markdown",
        )
        await self.bot_handlers.add_to_queue_direct(user_id, None, context)

    # ── Destination handler ───────────────────────────────────────────────────

    async def _handle_dest(self, query, user_id: int, data: str, context, is_channel: bool):
        # Disable the UI immediately
        await query.edit_message_text("⏳ *Preparing to post…*", parse_mode="Markdown")

        try:
            if is_channel:
                # dest_ch_{channel_id}_{session_id}
                parts = data[len("dest_ch_"):].split("_", 1)
                chat_id = int(parts[0])
            else:
                # dest_g_{group_id}_{session_id}
                parts = data[len("dest_g_"):].split("_", 1)
                chat_id = int(parts[0])
        except (ValueError, IndexError) as e:
            await query.edit_message_text(f"❌ Invalid destination data: {e}")
            return

        from bot.content_processor import ContentProcessor
        processor = ContentProcessor(self.bot_handlers)
        await processor.post_quizzes_to_destination(
            user_id, chat_id, None, context, query.message
        )

    # ── Channel / Group management ────────────────────────────────────────────

    async def _save_channel_or_group(self, update, context, user_id, text, kind):
        text = text.strip()
        chat_id = None
        name = None

        # Try to parse as numeric ID
        try:
            chat_id = int(text)
        except ValueError:
            # Try as @username
            try:
                chat = await context.bot.get_chat(text)
                chat_id = chat.id
                name = chat.title or chat.username or text
            except Exception as e:
                await update.message.reply_text(f"❌ Could not find chat: {e}")
                return

        if chat_id and not name:
            try:
                chat = await context.bot.get_chat(chat_id)
                name = chat.title or chat.username or str(chat_id)
            except Exception:
                name = str(chat_id)

        if kind == "channel":
            db.add_channel(user_id, chat_id, name)
            await update.message.reply_text(
                f"✅ Channel *{name}* (`{chat_id}`) added!", parse_mode="Markdown"
            )
        else:
            db.add_group(user_id, chat_id, name)
            await update.message.reply_text(
                f"✅ Group *{name}* (`{chat_id}`) added!", parse_mode="Markdown"
            )

    async def _manage_channels(self, query, user_id: int):
        channels = db.get_user_channels(user_id)
        if not channels:
            await query.edit_message_text("📭 No channels configured. Use /settings → Add Channel.")
            return
        keyboard = []
        for ch in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ {ch['channel_name']}",
                    callback_data=f"del_channel_{ch['_id']}",
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_settings")])
        await query.edit_message_text(
            "📺 *Your Channels*\n\nTap a channel to remove it:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _manage_groups(self, query, user_id: int):
        groups = db.get_user_groups(user_id)
        if not groups:
            await query.edit_message_text("📭 No groups configured. Use /settings → Add Group.")
            return
        keyboard = []
        for g in groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ {g['group_name']}",
                    callback_data=f"del_group_{g['_id']}",
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_settings")])
        await query.edit_message_text(
            "👥 *Your Groups*\n\nTap a group to remove it:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── Poll export ───────────────────────────────────────────────────────────

    async def _export_polls(self, query, user_id: int):
        polls = db.get_user_polls(user_id)
        if not polls:
            await query.edit_message_text("📭 No polls to export.")
            return

        await query.edit_message_text("⏳ *Building exports…*", parse_mode="Markdown")

        from io import BytesIO, StringIO
        import csv as csv_mod
        from datetime import datetime
        from processors.pdf_generator import generate_pdf

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        settings = db.get_user_settings(user_id)
        pdf_mode = settings.get("pdf_mode", "inline")

        # ── Normalise poll records into question dicts ─────────────────────
        # Polls stored by handle_poll_answer contain: poll_id, option_ids
        # We reconstruct best-effort question dicts for export.
        questions = []
        raw_rows = []
        for p in polls:
            data = p.get("data") or {}
            poll_id = p.get("poll_id") or data.get("poll_id") or "unknown"
            option_ids = data.get("option_ids") or []
            chosen = ", ".join(str(o) for o in option_ids) if option_ids else "—"
            raw_rows.append({
                "poll_id": poll_id,
                "user_id": str(data.get("user_id") or ""),
                "chosen_option_ids": chosen,
            })
            # Build a minimal question dict so the PDF renderer works
            questions.append({
                "question_description": f"Poll ID: {poll_id}",
                "options": [f"Option {o}" for o in option_ids] or ["(no answer)"],
                "correct_answer_index": 0,
                "correct_option": "A",
                "explanation": f"User chose option(s): {chosen}",
            })

        errors = []

        # ── 1. JSON ────────────────────────────────────────────────────────
        try:
            json_payload = json.dumps(raw_rows, ensure_ascii=False, indent=2).encode("utf-8")
            json_buf = BytesIO(json_payload)
            await query.message.reply_document(
                json_buf,
                filename=f"polls_{timestamp}.json",
                caption=f"📋 *JSON Export* — {len(raw_rows)} poll records",
                parse_mode="Markdown",
            )
        except Exception as e:
            errors.append(f"JSON: {e}")

        # ── 2. CSV ─────────────────────────────────────────────────────────
        try:
            csv_buf = StringIO()
            writer = csv_mod.DictWriter(
                csv_buf,
                fieldnames=["poll_id", "user_id", "chosen_option_ids"],
            )
            writer.writeheader()
            writer.writerows(raw_rows)
            csv_bytes = BytesIO(csv_buf.getvalue().encode("utf-8"))
            await query.message.reply_document(
                csv_bytes,
                filename=f"polls_{timestamp}.csv",
                caption=f"📊 *CSV Export* — {len(raw_rows)} poll records",
                parse_mode="Markdown",
            )
        except Exception as e:
            errors.append(f"CSV: {e}")

        # ── 3. PDF ─────────────────────────────────────────────────────────
        try:
            pdf_buf = generate_pdf(
                questions,
                mode=pdf_mode,
                engine="reportlab",
                title=f"Poll Report — {timestamp}",
            )
            await query.message.reply_document(
                pdf_buf,
                filename=f"polls_{timestamp}.pdf",
                caption=(
                    f"📄 *PDF Export* — {len(questions)} poll records\n"
                    f"Mode: `{pdf_mode}`"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            errors.append(f"PDF: {e}")

        # ── Summary ────────────────────────────────────────────────────────
        if errors:
            await query.edit_message_text(
                f"⚠️ Export done with errors:\n" + "\n".join(f"• {e}" for e in errors),
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                f"✅ *Export complete!*\n{len(raw_rows)} poll records sent as CSV, JSON, and PDF.",
                parse_mode="Markdown",
            )

