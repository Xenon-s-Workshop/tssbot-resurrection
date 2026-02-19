"""
Bot Handlers - WITH AI PROVIDER TOGGLE
"""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import config
from database import db
from processors.csv_processor import CSVParser
from processors.poll_collector import poll_collector
from processors.deepseek_processor import DEEPSEEK_MODELS
from utils.queue_manager import task_queue
from utils.auth import require_auth, require_sudo

class BotHandlers:
    def __init__(self, gemini_processor, deepseek_processor):
        self.user_states = {}
        self.pdf_processor = gemini_processor
        self.deepseek_processor = deepseek_processor

    def get_processor(self, user_id: int):
        """Return correct AI processor based on user setting"""
        settings = db.get_user_settings(user_id)
        if settings.get('ai_provider') == 'deepseek':
            model = settings.get('deepseek_model', DEEPSEEK_MODELS[7])
            self.deepseek_processor.set_model(model)
            return self.deepseek_processor
        return self.pdf_processor

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        if not db.is_authorized(user_id):
            await update.message.reply_text(
                f"🔒 *Access Denied*\n\nHello {username}!\n\nYou are not authorized.\nContact an administrator.",
                parse_mode='Markdown'
            )
            return
        settings = db.get_user_settings(user_id)
        provider = settings.get('ai_provider', 'gemini')
        pe = "🟢" if provider == 'gemini' else "🔵"
        pname = "Gemini" if provider == 'gemini' else f"DeepSeek ({settings.get('deepseek_model','')})"
        welcome = f"👋 *Welcome to {config.BOT_NAME}!*\n\nHello {username}! 🎓\n\n"
        welcome += f"🤖 *AI Provider:* {pe} {pname}\n\n"
        welcome += "📋 /help /settings /collectpolls /info\n"
        if db.is_sudo(user_id):
            welcome += "🔐 /authorize /revoke /users\n"
        await update.message.reply_text(welcome, parse_mode='Markdown')

    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        t = f"📚 *{config.BOT_NAME} - Help*\n\n"
        t += "🎯 *Generate from PDF/Images:*\n"
        t += "Send PDF → select page range → choose mode → get CSV\n\n"
        t += "🤖 *AI Providers (toggle in /settings):*\n"
        t += "🟢 *Gemini* - Fast, parallel, vision AI\n"
        t += "🔵 *DeepSeek* - 18 models, secondary AI\n\n"
        t += "📮 *Collect Polls:* /collectpolls\n"
        t += "✨ All exports: progress bars + cleanup\n"
        await update.message.reply_text(t, parse_mode='Markdown')

    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        message = update.message
        t = f"📊 *Chat Info*\n\n🆔 ID: `{chat.id}`\n📛 Title: {chat.title or 'N/A'}\n📝 Type: {chat.type}\n"
        if message.message_thread_id:
            t += f"🧵 Topic ID: `{message.message_thread_id}`\n"
        try:
            if chat.type in ['supergroup', 'group']:
                cf = await context.bot.get_chat(chat.id)
                is_forum = getattr(cf, 'is_forum', False)
                t += f"📑 Topics: {'Yes' if is_forum else 'No'}\n"
                if is_forum and not message.message_thread_id:
                    t += "\n💡 Send /info inside a topic to get its ID!\n"
        except:
            pass
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
            await update.message.reply_text(f"✅ Revoked {uid}!")
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
            badge = "🔐" if u.get('is_sudo') else "👤"
            t += f"{badge} `{u['user_id']}`\n"
        await update.message.reply_text(t, parse_mode='Markdown')

    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        settings = db.get_user_settings(user_id)
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        provider = settings.get('ai_provider', 'gemini')
        ds_model = settings.get('deepseek_model', DEEPSEEK_MODELS[7])
        pe = "🟢" if provider == 'gemini' else "🔵"

        if provider == 'gemini':
            ai_btn = InlineKeyboardButton("🔵 Switch to DeepSeek", callback_data="ai_switch_deepseek")
        else:
            ai_btn = InlineKeyboardButton("🟢 Switch to Gemini", callback_data="ai_switch_gemini")

        keyboard = [
            [ai_btn],
            [InlineKeyboardButton("🤖 Select DeepSeek Model", callback_data="ai_select_model")],
            [InlineKeyboardButton("➕ Channel", callback_data="settings_add_channel"),
             InlineKeyboardButton("➕ Group", callback_data="settings_add_group")],
            [InlineKeyboardButton("📺 Channels", callback_data="settings_manage_channels"),
             InlineKeyboardButton("👥 Groups", callback_data="settings_manage_groups")],
        ]

        ds_line = f"\n🔵 Model: `{ds_model}`" if provider == 'deepseek' else ""
        await update.message.reply_text(
            f"⚙️ *Settings*\n\n"
            f"🤖 *AI Provider:* {pe} {provider.title()}{ds_line}\n\n"
            f"📢 Marker: `{settings['quiz_marker']}`\n"
            f"🔗 Tag: `{settings['explanation_tag']}`\n\n"
            f"📺 Channels: {len(channels)} | 👥 Groups: {len(groups)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        settings = db.get_user_settings(user_id)
        provider = settings.get('ai_provider', 'gemini')
        ds_model = settings.get('deepseek_model', DEEPSEEK_MODELS[7])
        model_str = f"`{config.GEMINI_MODEL}`" if provider == 'gemini' else f"`{ds_model}`"
        await update.message.reply_text(
            f"🤖 *AI Info*\n\n"
            f"Provider: {'🟢 Gemini' if provider == 'gemini' else '🔵 DeepSeek'}\n"
            f"Model: {model_str}\n"
            f"Workers: {config.MAX_CONCURRENT_IMAGES}\n"
            f"Queue: {task_queue.get_queue_size()}/{config.MAX_QUEUE_SIZE}",
            parse_mode='Markdown'
        )

    @require_auth
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if task_queue.is_processing(user_id):
            await update.message.reply_text("⚙️ Your task is being processed...")
        else:
            pos = task_queue.get_position(user_id)
            await update.message.reply_text(f"📋 Position: {pos}" if pos > 0 else "❌ No tasks in queue.")

    @require_auth
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        task_queue.clear_user(user_id)
        self.user_states.pop(user_id, None)
        await update.message.reply_text("✅ All tasks cancelled and cleared!")

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
                "📄 *PDF Received!*\n\nSelect pages to process:",
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
                f"✅ *CSV Processed!*\n📊 Questions: {len(questions)}\n\nChoose action:",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
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
        if pos == -1:
            msg = "❌ Queue full. Try later."
        elif pos == -2:
            msg = "⚠️ Already queued. Use /cancel to clear."
        else:
            msg = f"✅ Queued! Position: {pos}"
        await context.bot.send_message(user_id, msg)
