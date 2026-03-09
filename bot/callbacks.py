"""Bot Callbacks - CLEAN VERSION"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from processors.poll_collector import poll_collector
from processors.pdf_exporter import pdf_exporter

class CallbackHandlers:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data

        # Poll collection
        if data == "poll_export_csv":
            await poll_collector.handle_export_csv(update, context)
        elif data == "poll_export_pdf":
            await poll_collector.handle_export_pdf(update, context)
        elif data == "poll_clear":
            await poll_collector.handle_clear(update, context)
        elif data == "poll_stop":
            await poll_collector.handle_stop(update, context)
        
        # Page range
        elif data == "pages_all":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            keyboard = [
                [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
            ]
            await query.edit_message_text("📄 *All Pages*\n\nChoose mode:",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data == "pages_custom":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'page_range'
            await query.edit_message_text("🔢 *Enter Page Range*\n\nFormat: `5-15`", parse_mode='Markdown')
        
        # Mode
        elif data.startswith("mode_"):
            mode = data.split("_")[1]
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            self.bot_handlers.user_states[user_id]['mode'] = mode
            await query.edit_message_text(f"✅ Mode: {mode}\n⏳ Adding to queue...")
            page_range = self.bot_handlers.user_states[user_id].get('page_range')
            await self.bot_handlers.add_to_queue_direct(user_id, page_range, context)
        
        # PDF
        elif data.startswith("pdf_format_"):
            fmt = int(data.split("_")[-1])
            await pdf_exporter.handle_format_selection(update, context, fmt)
        
        elif data.startswith("export_pdf_"):
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            questions = self.bot_handlers.user_states[user_id].get('questions', [])
            if not questions:
                await query.answer("❌ No questions!")
                return
            await pdf_exporter.handle_pdf_export_start(update, context, questions)
        
        # Post
        elif data.startswith("post_"):
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            channels = db.get_user_channels(user_id)
            groups = db.get_user_groups(user_id)
            if not channels and not groups:
                await query.edit_message_text("❌ No destinations.")
                return
            keyboard = []
            for ch in channels:
                keyboard.append([InlineKeyboardButton(f"📺 {ch['channel_name']}", callback_data=f"dest_ch_{ch['channel_id']}")])
            for gr in groups:
                keyboard.append([InlineKeyboardButton(f"👥 {gr['group_name']}", callback_data=f"dest_gr_{gr['group_id']}")])
            await query.edit_message_text("📢 *Select:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data.startswith("dest_ch_"):
            channel_id = int(data.split("_")[-1])
            await query.edit_message_text("📺 Posting...")
            from bot.content_processor import ContentProcessor
            processor = ContentProcessor(self.bot_handlers)
            await processor.post_quizzes_to_destination(user_id, channel_id, None, context, query.message)
        
        elif data.startswith("dest_gr_"):
            group_id = int(data.split("_")[-1])
            self.bot_handlers.user_states[user_id]['selected_group'] = group_id
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'topic_id'
            await query.edit_message_text("🔢 Send *Topic ID* (or 0):", parse_mode='Markdown')
        
        # Settings
        elif data == "settings_add_channel":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_channel'}
            await query.edit_message_text("📺 Send: `id name`", parse_mode='Markdown')
        elif data == "settings_add_group":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_group'}
            await query.edit_message_text("👥 Send: `id name`", parse_mode='Markdown')
        elif data == "settings_manage_channels":
            channels = db.get_user_channels(user_id)
            if not channels:
                await query.edit_message_text("❌ No channels.")
                return
            keyboard = [[InlineKeyboardButton(f"❌ {ch['channel_name']}", callback_data=f"del_ch_{ch['_id']}")] for ch in channels]
            await query.edit_message_text("📺 Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        elif data == "settings_manage_groups":
            groups = db.get_user_groups(user_id)
            if not groups:
                await query.edit_message_text("❌ No groups.")
                return
            keyboard = [[InlineKeyboardButton(f"❌ {gr['group_name']}", callback_data=f"del_gr_{gr['_id']}")] for gr in groups]
            await query.edit_message_text("👥 Manage:", reply_markup=InlineKeyboardMarkup(keyboard))
        elif data.startswith("del_ch_"):
            db.delete_channel(data[7:])
            await query.answer("✅ Deleted!")
        elif data.startswith("del_gr_"):
            db.delete_group(data[7:])
            await query.answer("✅ Deleted!")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

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
                start, end = int(parts[0].strip()), int(parts[1].strip())
                if start < 1 or end < start:
                    await update.message.reply_text("❌ Invalid range!")
                    return
                self.bot_handlers.user_states[user_id]['page_range'] = (start, end)
                self.bot_handlers.user_states[user_id]['waiting_for'] = None
                keyboard = [
                    [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                    [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
                ]
                await update.message.reply_text(f"✅ Pages {start}-{end}\n\nChoose mode:",
                    reply_markup=InlineKeyboardMarkup(keyboard))
            except:
                await update.message.reply_text("❌ Format: `5-15`", parse_mode='Markdown')
        
        elif waiting_for == 'add_channel':
            try:
                parts = text.split(" ", 1)
                if len(parts) < 2:
                    await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
                    return
                db.add_channel(user_id, int(parts[0]), parts[1])
                await update.message.reply_text("✅ Added!")
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
                await update.message.reply_text("✅ Added!")
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid ID.")
        
        elif waiting_for == 'topic_id':
            try:
                topic_id = int(text)
                group_id = self.bot_handlers.user_states[user_id]['selected_group']
                thread_id = topic_id if topic_id > 0 else None
                msg = await update.message.reply_text("👥 Posting...")
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.post_quizzes_to_destination(user_id, group_id, thread_id, context, msg)
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid topic ID.")
