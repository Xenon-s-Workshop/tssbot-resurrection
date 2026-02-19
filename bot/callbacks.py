"""
Bot Callbacks - WITH AI PROVIDER SWITCHING
All poll, page range, PDF, and AI settings routing
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from processors.poll_collector import poll_collector
from processors.pdf_exporter import pdf_exporter
from processors.deepseek_processor import DEEPSEEK_MODELS

class CallbackHandlers:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        # ==================== AI PROVIDER SWITCHING ====================
        if data == "ai_switch_gemini":
            db.set_ai_provider(user_id, 'gemini')
            await query.edit_message_text(
                "✅ *Switched to Gemini AI*\n\n"
                "🟢 Gemini is now active for question processing.\n"
                "Fast, parallel, supports vision.\n\n"
                "Use /settings to switch back.",
                parse_mode='Markdown'
            )

        elif data == "ai_switch_deepseek":
            db.set_ai_provider(user_id, 'deepseek')
            settings = db.get_user_settings(user_id)
            model = settings.get('deepseek_model', DEEPSEEK_MODELS[7])
            await query.edit_message_text(
                f"✅ *Switched to DeepSeek AI*\n\n"
                f"🔵 DeepSeek is now active for question processing.\n"
                f"Current model: `{model}`\n\n"
                f"Use /settings to change model or switch back.",
                parse_mode='Markdown'
            )

        elif data == "ai_select_model":
            # Show paginated model list (18 models in rows of 2)
            keyboard = []
            for i in range(0, len(DEEPSEEK_MODELS), 2):
                row = []
                row.append(InlineKeyboardButton(DEEPSEEK_MODELS[i], callback_data=f"ai_model_{i}"))
                if i + 1 < len(DEEPSEEK_MODELS):
                    row.append(InlineKeyboardButton(DEEPSEEK_MODELS[i+1], callback_data=f"ai_model_{i+1}"))
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("↩️ Back", callback_data="ai_select_model_back")])

            settings = db.get_user_settings(user_id)
            current = settings.get('deepseek_model', DEEPSEEK_MODELS[7])
            await query.edit_message_text(
                f"🤖 *Select DeepSeek Model*\n\n"
                f"Current: `{current}`\n\n"
                f"Choose from 18 models below:\n"
                f"_(R1 recommended for reasoning)_",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif data.startswith("ai_model_"):
            idx = int(data.split("_")[-1])
            model = DEEPSEEK_MODELS[idx]
            db.set_deepseek_model(user_id, model)
            # Also activate DeepSeek if not already
            settings = db.get_user_settings(user_id)
            if settings.get('ai_provider') != 'deepseek':
                db.set_ai_provider(user_id, 'deepseek')

            await query.edit_message_text(
                f"✅ *DeepSeek Model Set*\n\n"
                f"🔵 Model: `{model}`\n"
                f"AI Provider: DeepSeek (now active)\n\n"
                f"Use /settings to manage or switch to Gemini.",
                parse_mode='Markdown'
            )

        elif data == "ai_select_model_back":
            settings = db.get_user_settings(user_id)
            provider = settings.get('ai_provider', 'gemini')
            if provider == 'gemini':
                ai_btn = InlineKeyboardButton("🔵 Switch to DeepSeek", callback_data="ai_switch_deepseek")
            else:
                ai_btn = InlineKeyboardButton("🟢 Switch to Gemini", callback_data="ai_switch_gemini")
            keyboard = [
                [ai_btn],
                [InlineKeyboardButton("🤖 Select DeepSeek Model", callback_data="ai_select_model")],
            ]
            pe = "🟢" if provider == 'gemini' else "🔵"
            await query.edit_message_text(
                f"⚙️ *Settings*\n\n"
                f"🤖 AI Provider: {pe} {provider.title()}\n\n"
                f"Use /settings for full settings.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        # ==================== POLL COLLECTION ====================
        elif data == "poll_export_csv":
            await poll_collector.handle_export_csv(update, context)

        elif data == "poll_export_pdf":
            await poll_collector.handle_export_pdf(update, context)

        elif data == "poll_clear":
            await poll_collector.handle_clear(update, context)

        elif data == "poll_stop":
            await poll_collector.handle_stop(update, context)

        # ==================== PAGE RANGE ====================
        elif data == "pages_all":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            keyboard = [
                [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
            ]
            await query.edit_message_text(
                "📄 *All Pages Selected*\n\nChoose processing mode:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif data == "pages_custom":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'page_range'
            await query.edit_message_text(
                "🔢 *Enter Page Range*\n\n"
                "Format: `start-end`\n"
                "Example: `1-10` or `5-20`",
                parse_mode='Markdown'
            )

        # ==================== MODE SELECTION ====================
        elif data.startswith("mode_"):
            mode = data.split("_")[1]
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return

            settings = db.get_user_settings(user_id)
            provider = settings.get('ai_provider', 'gemini')
            pe = "🟢 Gemini" if provider == 'gemini' else f"🔵 DeepSeek ({settings.get('deepseek_model','')})"

            self.bot_handlers.user_states[user_id]['mode'] = mode
            await query.edit_message_text(
                f"✅ Mode: {mode}\n🤖 AI: {pe}\n\n⏳ Adding to queue..."
            )
            page_range = self.bot_handlers.user_states[user_id].get('page_range')
            await self.bot_handlers.add_to_queue_direct(user_id, page_range, context)

        # ==================== PDF FORMAT ====================
        elif data.startswith("pdf_format_"):
            fmt = int(data.split("_")[-1])
            await pdf_exporter.handle_format_selection(update, context, fmt)

        # ==================== PDF EXPORT ====================
        elif data.startswith("export_pdf_"):
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            questions = self.bot_handlers.user_states[user_id].get('questions', [])
            if not questions:
                await query.answer("❌ No questions!")
                return
            await pdf_exporter.handle_pdf_export_start(update, context, questions)

        # ==================== POST QUIZZES ====================
        elif data.startswith("post_"):
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            channels = db.get_user_channels(user_id)
            groups = db.get_user_groups(user_id)
            if not channels and not groups:
                await query.edit_message_text("❌ No destinations. Use /settings")
                return
            keyboard = []
            for ch in channels:
                keyboard.append([InlineKeyboardButton(
                    f"📺 {ch['channel_name']}",
                    callback_data=f"dest_ch_{ch['channel_id']}"
                )])
            for gr in groups:
                keyboard.append([InlineKeyboardButton(
                    f"👥 {gr['group_name']}",
                    callback_data=f"dest_gr_{gr['group_id']}"
                )])
            await query.edit_message_text(
                "📢 *Select Destination:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif data.startswith("dest_ch_"):
            channel_id = int(data.split("_")[-1])
            await query.edit_message_text("📺 Posting to channel...")
            from bot.content_processor import ContentProcessor
            processor = ContentProcessor(self.bot_handlers)
            await processor.post_quizzes_to_destination(user_id, channel_id, None, context, query.message)

        elif data.startswith("dest_gr_"):
            group_id = int(data.split("_")[-1])
            self.bot_handlers.user_states[user_id]['selected_group'] = group_id
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'topic_id'
            await query.edit_message_text("🔢 Send *Topic ID* (or 0 for none):", parse_mode='Markdown')

        # ==================== SETTINGS ====================
        elif data == "settings_add_channel":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_channel'}
            await query.edit_message_text("📺 Send: `channel_id channel_name`", parse_mode='Markdown')

        elif data == "settings_add_group":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_group'}
            await query.edit_message_text("👥 Send: `group_id group_name`", parse_mode='Markdown')

        elif data == "settings_manage_channels":
            channels = db.get_user_channels(user_id)
            if not channels:
                await query.edit_message_text("❌ No channels.")
                return
            keyboard = [[InlineKeyboardButton(f"❌ {ch['channel_name']}", callback_data=f"del_ch_{ch['_id']}")] for ch in channels]
            await query.edit_message_text("📺 Manage channels:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "settings_manage_groups":
            groups = db.get_user_groups(user_id)
            if not groups:
                await query.edit_message_text("❌ No groups.")
                return
            keyboard = [[InlineKeyboardButton(f"❌ {gr['group_name']}", callback_data=f"del_gr_{gr['_id']}")] for gr in groups]
            await query.edit_message_text("👥 Manage groups:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("del_ch_"):
            db.delete_channel(data[7:])
            await query.answer("✅ Channel deleted!")

        elif data.startswith("del_gr_"):
            db.delete_group(data[7:])
            await query.answer("✅ Group deleted!")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # PDF name input
        if pdf_exporter.is_waiting_for_name(user_id):
            await pdf_exporter.handle_pdf_name_input(update, context)
            return

        if user_id not in self.bot_handlers.user_states:
            return

        waiting_for = self.bot_handlers.user_states[user_id].get('waiting_for')
        text = update.message.text.strip()

        if waiting_for == 'page_range':
            try:
                if '-' not in text:
                    await update.message.reply_text("❌ Format: `5-15`", parse_mode='Markdown')
                    return
                parts = text.split('-')
                start_page, end_page = int(parts[0].strip()), int(parts[1].strip())
                if start_page < 1 or end_page < start_page:
                    await update.message.reply_text("❌ Invalid range!")
                    return
                self.bot_handlers.user_states[user_id]['page_range'] = (start_page, end_page)
                self.bot_handlers.user_states[user_id]['waiting_for'] = None
                keyboard = [
                    [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                    [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
                ]
                await update.message.reply_text(
                    f"✅ Pages {start_page}-{end_page} selected\n\nChoose mode:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text("❌ Format: `5-15`", parse_mode='Markdown')

        elif waiting_for == 'add_channel':
            try:
                parts = text.split(" ", 1)
                if len(parts) < 2:
                    await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
                    return
                db.add_channel(user_id, int(parts[0]), parts[1])
                await update.message.reply_text("✅ Channel added!")
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid ID.")

        elif waiting_for == 'add_group':
            try:
                parts = text.split(" ", 1)
                if len(parts) < 2:
                    await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
                    return
                db.add_group(user_id, int(parts[0]), parts[1])
                await update.message.reply_text("✅ Group added!")
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid ID.")

        elif waiting_for == 'topic_id':
            try:
                topic_id = int(text)
                group_id = self.bot_handlers.user_states[user_id]['selected_group']
                thread_id = topic_id if topic_id > 0 else None
                msg = await update.message.reply_text("👥 Posting to group...")
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.post_quizzes_to_destination(user_id, group_id, thread_id, context, msg)
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid topic ID.")
