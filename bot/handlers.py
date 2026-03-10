"""
Bot Handlers - WITH ENHANCED START and LIVE QUIZ
- Detailed start command with full feature list
- Live quiz integration
- Ghost bug fixed
"""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import config
from database import db
from processors.csv_processor import CSVParser
from processors.poll_collector import poll_collector
from processors.live_quiz import live_quiz_manager
from utils.queue_manager import task_queue
from utils.auth import require_auth, require_sudo

class BotHandlers:
    def __init__(self, pdf_processor):
        self.user_states = {}
        self.pdf_processor = pdf_processor
    
    def get_processor(self, user_id: int):
        """Get AI processor (for future dual-AI support)"""
        return self.pdf_processor
    
    # ==================== ENHANCED START COMMAND ====================
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with detailed help"""
        user_id = update.effective_user.id
        username = update.effective_user.first_name or "User"
        
        if not db.is_authorized(user_id):
            await update.message.reply_text(
                f"🔒 *Access Denied*\n\n"
                f"Contact an administrator for access.",
                parse_mode='Markdown'
            )
            return
        
        is_sudo = db.is_sudo(user_id)
        
        welcome = f"👋 *Welcome to {config.BOT_NAME}!*\n\n"
        welcome += f"Hello {username}! 🎓\n\n"
        
        # Features
        welcome += "✨ *Features:*\n"
        welcome += "📄 Process PDFs/Images with AI\n"
        welcome += "📮 Collect Telegram polls\n"
        welcome += "🎯 Live quiz with leaderboard\n"
        welcome += "📊 Auto-generate CSV/JSON/PDF\n"
        welcome += "📢 Post to channels/groups\n"
        welcome += "🌏 Bengali/Unicode support\n\n"
        
        # Commands - Processing
        welcome += "📋 *Processing Commands:*\n"
        welcome += "`Send PDF/Images` - AI processing\n"
        welcome += "`/collectpolls` - Collect polls\n"
        welcome += "`/queue` - Check queue status\n"
        welcome += "`/cancel` - Cancel current task\n\n"
        
        # Commands - Quiz
        welcome += "🎯 *Quiz Commands:*\n"
        welcome += "`/livequiz` - Start live quiz\n"
        welcome += "Reply to CSV/JSON with options:\n"
        welcome += "  `-m \"message\"` - Custom announcement\n"
        welcome += "  `-t 10` - 10 seconds per question\n"
        welcome += "  `-c -123456` - Post to chat ID\n\n"
        
        # Commands - Settings
        welcome += "⚙️ *Settings:*\n"
        welcome += "`/settings` - Configure bot\n"
        welcome += "`/info` - Get chat/topic info\n"
        welcome += "`/model` - AI model info\n\n"
        
        # Admin commands
        if is_sudo:
            welcome += "🔐 *Admin Commands:*\n"
            welcome += "`/authorize <id>` - Add user\n"
            welcome += "`/revoke <id>` - Remove user\n"
            welcome += "`/users` - List all users\n\n"
        
        # Tips
        welcome += "💡 *Tips:*\n"
        welcome += "• PDF processing auto-generates 3 files\n"
        welcome += "• Poll collection has batch processing\n"
        welcome += "• Live quiz shows real-time leaderboard\n"
        welcome += "• Success counter sent after posting\n\n"
        
        welcome += "🚀 *Ready to start!*"
        
        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    # ==================== BASIC COMMANDS ====================
    
    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick help"""
        await update.message.reply_text(
            f"📚 *Quick Help*\n\n"
            f"Send PDF/Images for AI processing\n"
            f"`/collectpolls` - Collect polls\n"
            f"`/livequiz` - Start live quiz\n"
            f"`/settings` - Configure\n\n"
            f"Use `/start` for detailed help!",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Chat info"""
        chat = update.effective_chat
        t = f"📊 *Chat Info*\n\n"
        t += f"🆔 ID: `{chat.id}`\n"
        t += f"📛 {chat.title or 'Direct Message'}\n"
        t += f"📝 Type: {chat.type}\n"
        
        if update.message.message_thread_id:
            t += f"🧵 Topic ID: `{update.message.message_thread_id}`\n"
        
        await update.message.reply_text(t, parse_mode='Markdown')
    
    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """AI model info"""
        await update.message.reply_text(
            f"🤖 *AI System*\n\n"
            f"Model: `{config.GEMINI_MODEL}`\n"
            f"Workers: {config.MAX_CONCURRENT_IMAGES}\n"
            f"Queue: {task_queue.get_queue_size()}/{config.MAX_QUEUE_SIZE}\n\n"
            f"✅ Bengali/Unicode supported",
            parse_mode='Markdown'
        )
    
    # ==================== POLL COLLECTION ====================
    
    @require_auth
    async def collectpolls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start poll collection"""
        await poll_collector.handle_start_command(update, context)
    
    @require_auth
    async def handle_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle poll message"""
        await poll_collector.handle_poll_message(update, context)
    
    # ==================== LIVE QUIZ ====================
    
    @require_auth
    async def livequiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start live quiz - must reply to CSV/JSON"""
        if not update.message.reply_to_message or not update.message.reply_to_message.document:
            await update.message.reply_text(
                "❌ *Live Quiz*\n\n"
                "Please reply to a CSV or JSON file\n\n"
                "📋 *Usage:*\n"
                "`/livequiz` - Default settings\n"
                "`/livequiz -t 15` - 15s per question\n"
                "`/livequiz -m \"Exam starts!\"` - Custom message\n"
                "`/livequiz -c -123456` - Post to chat ID",
                parse_mode='Markdown'
            )
            return
        
        # Parse arguments
        args = self._parse_quiz_args(update.message.text)
        time_per_q = args.get('t', config.DEFAULT_QUIZ_TIME)
        target_chat = args.get('c', update.effective_chat.id)
        custom_msg = args.get('m', None)
        
        # Validate file
        doc = update.message.reply_to_message.document
        ext = doc.file_name.lower().rsplit('.', 1)[-1]
        
        if ext not in ('csv', 'json'):
            await update.message.reply_text("❌ File must be CSV or JSON")
            return
        
        # Download and load
        msg = await update.message.reply_text("📥 *Loading quiz...*", parse_mode='Markdown')
        
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            file = await context.bot.get_file(doc.file_id)
            await file.download_to_drive(tmp.name)
            
            # Load questions
            if ext == 'csv':
                questions = await self._load_quiz_from_csv(tmp.name)
            else:
                questions = await self._load_quiz_from_json(tmp.name)
        
        import os
        os.unlink(tmp.name)
        
        if not questions:
            await msg.edit_text("❌ *No valid questions found*", parse_mode='Markdown')
            return
        
        # Create session
        session_id = live_quiz_manager.create_session(
            target_chat, questions, time_per_q, custom_msg
        )
        
        await msg.edit_text(
            f"✅ *Live Quiz Started!*\n\n"
            f"📊 Questions: {len(questions)}\n"
            f"⏱️ Time: {time_per_q}s each\n"
            f"🎯 Chat ID: `{target_chat}`\n\n"
            f"Quiz running...",
            parse_mode='Markdown'
        )
        
        # Run quiz
        import asyncio
        asyncio.create_task(live_quiz_manager.run_quiz(session_id, context))
    
    def _parse_quiz_args(self, text: str) -> dict:
        """Parse quiz command arguments"""
        import re
        args = {}
        
        # -m "message"
        m_match = re.search(r'-m\s+"([^"]+)"', text)
        if m_match:
            args['m'] = m_match.group(1)
        
        # -c chat_id
        c_match = re.search(r'-c\s+(-?\d+)', text)
        if c_match:
            args['c'] = int(c_match.group(1))
        
        # -t time
        t_match = re.search(r'-t\s+(\d+)', text)
        if t_match:
            args['t'] = int(t_match.group(1))
        
        return args
    
    async def _load_quiz_from_csv(self, path: str) -> list:
        """Load quiz from CSV"""
        import csv
        questions = []
        
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    q_text = row.get('questions', '').strip()
                    if not q_text:
                        continue
                    
                    options = []
                    for i in range(1, 6):
                        opt = row.get(f'option{i}', '').strip()
                        if opt:
                            options.append(opt)
                    
                    if len(options) < 2:
                        continue
                    
                    try:
                        answer_idx = int(row.get('answer', '1')) - 1
                        if answer_idx < 0 or answer_idx >= len(options):
                            answer_idx = 0
                    except:
                        answer_idx = 0
                    
                    questions.append({
                        'question_description': q_text,
                        'options': options,
                        'correct_option': chr(65 + answer_idx),
                        'explanation': row.get('explanation', '').strip()
                    })
        except Exception as e:
            print(f"❌ CSV load error: {e}")
        
        return questions
    
    async def _load_quiz_from_json(self, path: str) -> list:
        """Load quiz from JSON"""
        import json
        questions = []
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                return questions
            
            for item in data:
                q_text = item.get('question', '').strip()
                opts_dict = item.get('options', {})
                
                if not q_text or not opts_dict:
                    continue
                
                options = []
                for letter in ['A', 'B', 'C', 'D', 'E']:
                    opt = opts_dict.get(letter)
                    if opt:
                        options.append(opt)
                
                if len(options) < 2:
                    continue
                
                correct = item.get('correct_answer', 'A').upper()
                
                questions.append({
                    'question_description': q_text,
                    'options': options,
                    'correct_option': correct,
                    'explanation': item.get('explanation', '').strip()
                })
        except Exception as e:
            print(f"❌ JSON load error: {e}")
        
        return questions
    
    # ==================== ADMIN COMMANDS ====================
    
    @require_sudo
    async def authorize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Authorize user"""
        if not context.args:
            await update.message.reply_text("Usage: `/authorize <user_id>`", parse_mode='Markdown')
            return
        try:
            db.authorize_user(int(context.args[0]), update.effective_user.id)
            await update.message.reply_text(f"✅ User `{context.args[0]}` authorized!", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Invalid user ID.")
    
    @require_sudo
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revoke user"""
        if not context.args:
            await update.message.reply_text("Usage: `/revoke <user_id>`", parse_mode='Markdown')
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
        """List users"""
        users = db.get_authorized_users()
        if not users:
            await update.message.reply_text("No users.")
            return
        t = f"👥 *Authorized ({len(users)}):*\n\n"
        for u in users:
            t += f"{'🔐' if u.get('is_sudo') else '👤'} `{u['user_id']}`\n"
        await update.message.reply_text(t, parse_mode='Markdown')
    
    # ==================== SETTINGS ====================
    
    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Settings menu"""
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
            f"📺 Channels: {len(channels)}\n"
            f"👥 Groups: {len(groups)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ==================== QUEUE MANAGEMENT ====================
    
    @require_auth
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check queue status - GHOST BUG FIXED"""
        user_id = update.effective_user.id
        
        # Check if actually processing (with timeout check)
        if task_queue.is_processing(user_id):
            await update.message.reply_text("⚙️ Your task is being processed...")
        else:
            pos = task_queue.get_position(user_id)
            if pos > 0:
                await update.message.reply_text(f"📋 Queue position: {pos}")
            else:
                await update.message.reply_text("❌ No tasks in queue.")
    
    @require_auth
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel tasks - GHOST BUG FIXED"""
        user_id = update.effective_user.id
        
        # Force clear everything
        task_queue.clear_user(user_id)
        self.user_states.pop(user_id, None)
        
        await update.message.reply_text("✅ All tasks cancelled and cleared!")
    
    # ==================== FILE HANDLERS ====================
    
    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document upload"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        if doc.file_name.endswith('.csv'):
            await self.handle_csv(update, context)
            return
        
        if not doc.file_name.endswith('.pdf'):
            await update.message.reply_text("❌ Send PDF or CSV only.")
            return
        
        if user_id in self.user_states or task_queue.is_processing(user_id):
            await update.message.reply_text("⚠️ Task in progress. Use `/cancel`", parse_mode='Markdown')
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
        """Handle CSV upload"""
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
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")],
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
        """Handle photo upload"""
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
        """Add to processing queue"""
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
