"""Bot Handlers - CLEAN VERSION"""
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import config
from database import db
from processors.csv_processor import CSVParser
from processors.poll_collector import poll_collector
from utils.queue_manager import task_queue
from utils.auth import require_auth, require_sudo

class BotHandlers:
    def __init__(self, pdf_processor):
        self.user_states = {}
        self.pdf_processor = pdf_processor

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        if not db.is_authorized(user_id):
            await update.message.reply_text(
                f"🔒 *Access Denied*\n\nContact an administrator.",
                parse_mode='Markdown'
            )
            return
        await update.message.reply_text(
            f"👋 *Welcome to {config.BOT_NAME}!*\n\nHello {username}! 🎓\n\n"
            f"📋 /help /settings /collectpolls /info\n" +
            ("🔐 /authorize /revoke /users\n" if db.is_sudo(user_id) else ""),
            parse_mode='Markdown'
        )

    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"📚 *{config.BOT_NAME} - Help*\n\n"
            f"🎯 Send PDF → select pages → choose mode → get CSV\n"
            f"📮 /collectpolls - Collect Telegram polls\n"
            f"✨ Progress bars, cleanup, Bengali support",
            parse_mode='Markdown'
        )

    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        t = f"📊 *Chat Info*\n\n🆔 ID: `{chat.id}`\n📛 {chat.title or 'N/A'}\n📝 {chat.type}\n"
        if update.message.message_thread_id:
            t += f"🧵 Topic ID: `{update.message.message_thread_id}`\n"
        await update.message.reply_text(t, parse_mode='Markdown')

    @require_auth
    async def collectpolls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await poll_collector.handle_start_command(update, context)

    @require_auth
    async def handle_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await poll_collector.handle_poll_message(update, context)

    @require_sudo
    async def authorize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /authorize <user_id>")
            return
        try:
            db.authorize_user(int(context.args[0]), update.effective_user.id)
            await update.message.reply_text(f"✅ User {context.args[0]} authorized!")
        except:
            await update.message.reply_text("❌ Invalid user ID.")

    @require_sudo
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Usage: /revoke <user_id>")
            return
        try:
            uid = int(context.args[0])
            if db.is_sudo(uid):
                await update.message.reply_text("❌ Cannot revoke sudo!")
                return
            db.revoke_user(uid)
            await update.message.reply_text(f"✅ Revoked!")
        except:
            await update.message.reply_text("❌ Invalid user ID.")

    @require_sudo
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        users = db.get_authorized_users()
        if not users:
            await update.message.reply_text("No users.")
            return
        t = f"👥 *Authorized ({len(users)}):*\n\n"
        for u in users:
            t += f"{'🔐' if u.get('is_sudo') else '👤'} `{u['user_id']}`\n"
        await update.message.reply_text(t, parse_mode='Markdown')

    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        settings = db.get_user_settings(user_id)
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        
        keyboard = [
            [InlineKeyboardButton("➕ Channel", callback_data="settings_add_channel"),
             InlineKeyboardButton("➕ Group", callback_data="settings_add_group")],
            [InlineKeyboardButton("📺 Channels", callback_data="settings_manage_channels"),
             InlineKeyboardButton("👥 Groups", callback_data="settings_manage_groups")],
        ]
        
        await update.message.reply_text(
            f"⚙️ *Settings*\n\n"
            f"📢 Marker: `{settings['quiz_marker']}`\n"
            f"🔗 Tag: `{settings['explanation_tag']}`\n\n"
            f"📺 Channels: {len(channels)} | 👥 Groups: {len(groups)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            f"🤖 *System Info*\n\n"
            f"Model: `{config.GEMINI_MODEL}`\n"
            f"Workers: {config.MAX_CONCURRENT_IMAGES}\n"
            f"Queue: {task_queue.get_queue_size()}/{config.MAX_QUEUE_SIZE}",
            parse_mode='Markdown'
        )

    @require_auth
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if task_queue.is_processing(user_id):
            await update.message.reply_text("⚙️ Processing...")
        else:
            pos = task_queue.get_position(user_id)
            await update.message.reply_text(f"📋 Position: {pos}" if pos > 0 else "❌ No tasks.")

    @require_auth
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        task_queue.clear_user(user_id)
        self.user_states.pop(user_id, None)
        await update.message.reply_text("✅ Cancelled!")

    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        doc = update.message.document
        
        if doc.file_name.endswith('.csv'):
            await self.handle_csv(update, context)
            return
        
        if not doc.file_name.endswith('.pdf'):
            await update.message.reply_text("❌ Send PDF or CSV only.")
            return
        
        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ Task in progress. Use /cancel")
            return
        
        msg = await update.message.reply_text("📥 Downloading PDF...")
        try:
            file = await context.bot.get_file(doc.file_id)
            path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(path)
            
            keyboard = [
                [InlineKeyboardButton("📄 All Pages", callback_data="pages_all")],
                [InlineKeyboardButton("🔢 Select Range", callback_data="pages_custom")]
            ]
            self.user_states[user_id] = {'content_type': 'pdf', 'content_paths': [path]}
            await msg.edit_text(
                "📄 *PDF Received!*\n\nSelect pages:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}")

    @require_auth
    async def handle_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ Task in progress.")
            return
        
        msg = await update.message.reply_text("📊 Processing CSV...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            content = await file.download_as_bytearray()
            questions = CSVParser.parse_csv_file(bytes(content))
            
            if not questions:
                await msg.edit_text("❌ No valid questions.")
                return
            
            session_id = f"csv_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.user_states[user_id] = {'questions': questions, 'session_id': session_id}
            
            keyboard = [
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("📄 Export PDF", callback_data=f"export_pdf_{session_id}")]
            ]
            await msg.edit_text(
                f"✅ *CSV Processed!*\n📊 Questions: {len(questions)}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}")

    @require_auth
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ Task in progress.")
            return
        
        msg = await update.message.reply_text("📥 Downloading...")
        try:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            path = config.TEMP_DIR / f"{user_id}_image.jpg"
            await file.download_to_drive(path)
            
            keyboard = [
                [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
            ]
            self.user_states[user_id] = {'content_type': 'images', 'content_paths': [path]}
            await msg.edit_text("🖼️ Choose mode:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}")

    async def add_to_queue_direct(self, user_id, page_range, context):
        if user_id not in self.user_states:
            return
        
        mode = self.user_states[user_id].get('mode', 'extraction')
        task_data = {
            'content_type': self.user_states[user_id]['content_type'],
            'content_paths': self.user_states[user_id]['content_paths'],
            'page_range': page_range,
            'mode': mode,
            'context': context
        }
        
        pos = task_queue.add_task(user_id, task_data)
        msg = "❌ Queue full." if pos == -1 else "⚠️ Already queued." if pos == -2 else f"✅ Queued! Position: {pos}"
        await context.bot.send_message(user_id, msg)
