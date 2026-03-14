"""
Bot Handlers - COMPLETE
All command and file handlers with ghost bug prevention
"""

import asyncio
import csv
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import config
from database import db
from utils.auth import require_auth
from utils.queue_manager import task_queue
from processors.poll_collector import poll_collector

class BotHandlers:
    def __init__(self):
        self.user_states = {}  # {user_id: state_data}
        self.processors = {}  # {user_id: PDFProcessor instance}
        print("✅ Bot Handlers initialized")
    
    def get_processor(self, user_id):
        """Get or create processor for user"""
        if user_id not in self.processors:
            from processors.pdf_processor import PDFProcessor
            from utils.api_rotator import GeminiAPIRotator
            
            api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
            self.processors[user_id] = PDFProcessor(api_rotator)
        
        return self.processors[user_id]
    
    # ==================== COMMAND HANDLERS ====================
    
    @require_auth
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with full feature list"""
        user = update.effective_user
        
        welcome_msg = (
            f"👋 **Welcome {user.first_name}!**\n\n"
            f"🤖 **{config.BOT_NAME}** - Your Quiz Assistant\n\n"
            f"**📚 Features:**\n"
            f"• 📄 PDF/Image → MCQ extraction\n"
            f"• ✨ AI quiz generation\n"
            f"• 📊 CSV/JSON/PDF export\n"
            f"• 📢 Auto-posting to channels\n"
            f"• 🎯 Live quiz with leaderboard\n"
            f"• 📝 Poll collection & export\n\n"
            f"**🎮 Commands:**\n"
            f"• /help - Show all commands\n"
            f"• /settings - Manage channels/groups\n"
            f"• /collectpolls - Collect forwarded polls\n"
            f"• /livequiz - Start live quiz\n"
            f"• /queue - Check queue status\n"
            f"• /cancel - Cancel current task\n\n"
            f"**💡 Quick Start:**\n"
            f"1️⃣ Send PDF or images\n"
            f"2️⃣ Choose extraction/generation\n"
            f"3️⃣ Get CSV, JSON, PDF files\n"
            f"4️⃣ Post to your channel!\n\n"
            f"**🔥 Tips:**\n"
            f"• Clear images = better results\n"
            f"• Use page ranges for large PDFs\n"
            f"• Custom messages get auto-pinned\n"
            f"• Live quiz tracks scores in real-time\n\n"
            f"Ready to create quizzes! 🚀"
        )
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = (
            "📖 **Available Commands:**\n\n"
            "**Basic:**\n"
            "• /start - Welcome message\n"
            "• /help - This message\n"
            "• /info - Bot statistics\n\n"
            "**Quiz Creation:**\n"
            "• Send PDF/images - Process files\n"
            "• /cancel - Cancel current task\n"
            "• /queue - Check queue status\n\n"
            "**Quiz Management:**\n"
            "• /settings - Manage destinations\n"
            "• /collectpolls - Collect polls\n"
            "• /livequiz - Live quiz mode\n\n"
            "**Admin Only:**\n"
            "• /authorize - Add user\n"
            "• /revoke - Remove user\n"
            "• /users - List users\n\n"
            "**💡 Need help?** Just send a file to start!"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Settings command"""
        keyboard = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="settings_add_channel")],
            [InlineKeyboardButton("➕ Add Group", callback_data="settings_add_group")],
            [InlineKeyboardButton("📺 Manage Channels", callback_data="settings_manage_channels")],
            [InlineKeyboardButton("👥 Manage Groups", callback_data="settings_manage_groups")]
        ]
        
        await update.message.reply_text(
            "⚙️ **Settings**\n\nManage your posting destinations:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info command"""
        user_id = update.effective_user.id
        
        # Get user stats
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        settings = db.get_user_settings(user_id)
        
        # Queue status
        queue_pos = task_queue.get_queue_position(user_id)
        is_processing = task_queue.is_processing(user_id)
        
        info_text = (
            f"ℹ️ **Bot Information**\n\n"
            f"**Your Stats:**\n"
            f"• Channels: {len(channels)}\n"
            f"• Groups: {len(groups)}\n"
            f"• Quiz Marker: {settings['quiz_marker']}\n"
            f"• Explanation Tag: {settings['explanation_tag']}\n\n"
            f"**Queue Status:**\n"
            f"• Position: {queue_pos if queue_pos else 'Not in queue'}\n"
            f"• Processing: {'Yes ⚙️' if is_processing else 'No'}\n\n"
            f"**Bot Version:** {config.BOT_VERSION}\n"
            f"**Model:** {config.GEMINI_MODEL}"
        )
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
    
    @require_auth
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Queue status command"""
        user_id = update.effective_user.id
        
        pos = task_queue.get_queue_position(user_id)
        is_proc = task_queue.is_processing(user_id)
        queue_len = task_queue.get_queue_length()
        
        if is_proc:
            status = "⚙️ Your task is being processed"
        elif pos:
            status = f"📋 Position in queue: {pos}"
        else:
            status = "✅ No active tasks"
        
        await update.message.reply_text(
            f"**Queue Status**\n\n"
            f"{status}\n"
            f"Total in queue: {queue_len}",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel tasks - STOPS POSTING TOO"""
        user_id = update.effective_user.id
        
        # Cancel posting if active
        from processors.quiz_poster import quiz_poster
        posting_cancelled = quiz_poster.cancel_posting(user_id)
        
        # Force clear queue
        task_queue.clear_user(user_id)
        self.user_states.pop(user_id, None)
        
        if posting_cancelled:
            await update.message.reply_text("🛑 Posting cancelled! Clearing tasks...")
        else:
            await update.message.reply_text("✅ All tasks cancelled and cleared!")
    
    @require_auth
    async def collectpolls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start poll collection"""
        await poll_collector.start_collection(update, context)
    
    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current model"""
        await update.message.reply_text(
            f"🤖 **Current Model:**\n`{config.GEMINI_MODEL}`",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def livequiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start live quiz from CSV/JSON"""
        user_id = update.effective_user.id
        
        # Check if user has questions
        if user_id not in self.user_states or 'questions' not in self.user_states[user_id]:
            await update.message.reply_text(
                "❌ No questions available!\n\n"
                "Send a CSV or JSON file first."
            )
            return
        
        questions = self.user_states[user_id]['questions']
        
        # Parse arguments for time and message
        args = context.args
        time_per_q = 10  # Default
        custom_msg = None
        
        # Parse flags: -t 15 -m "message"
        i = 0
        while i < len(args):
            if args[i] == '-t' and i + 1 < len(args):
                try:
                    time_per_q = int(args[i + 1])
                    i += 2
                except:
                    i += 1
            elif args[i] == '-m' and i + 1 < len(args):
                custom_msg = ' '.join(args[i + 1:])
                break
            else:
                i += 1
        
        # Store for custom message prompt
        from bot.callbacks import CallbackHandlers
        if hasattr(context.bot_data, 'callback_handlers'):
            callback_handlers = context.bot_data['callback_handlers']
            
            session_id = f"live_{user_id}"
            callback_handlers.custom_message_sessions[user_id] = {
                'session_id': session_id,
                'waiting_for': 'custom_message',
                'questions': questions,
                'quiz_type': 'live'
            }
            
            keyboard = [[InlineKeyboardButton("⏭️ Skip Message", callback_data=f"livequiz_skip_{session_id}")]]
            
            await update.message.reply_text(
                "🎯 **Live Quiz Setup**\n\n"
                "📝 Send a custom announcement message\n"
                "or skip to start immediately.\n\n"
                "💡 Example: \"Final Exam Starting Now!\"",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    # ==================== FILE HANDLERS ====================
    
    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF/document uploads"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        # Ghost bug prevention - check timeout first
        task_queue._check_timeout(user_id)
        
        # Check if already in queue
        if task_queue.is_in_queue(user_id) or task_queue.is_processing(user_id):
            await update.message.reply_text(
                "⚠️ You already have a task running!\n"
                "Use /cancel to stop it first."
            )
            return
        
        # Check file type
        if doc.mime_type == 'application/pdf':
            # Download PDF
            file = await context.bot.get_file(doc.file_id)
            pdf_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(pdf_path)
            
            # Store state
            self.user_states[user_id] = {
                'content_type': 'pdf',
                'content_paths': [pdf_path],
                'waiting_for': None
            }
            
            # Ask for page range
            keyboard = [
                [InlineKeyboardButton("📄 All Pages", callback_data="pages_all")],
                [InlineKeyboardButton("🔢 Custom Range", callback_data="pages_custom")]
            ]
            
            await update.message.reply_text(
                "📄 **PDF Received**\n\nSelect pages to process:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Please send a PDF file.")
    
    @require_auth
    async def handle_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle CSV file uploads"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        # Ghost bug prevention
        task_queue._check_timeout(user_id)
        
        if not doc.file_name.endswith('.csv'):
            await update.message.reply_text("❌ Please send a CSV file.")
            return
        
        try:
            # Download CSV
            file = await context.bot.get_file(doc.file_id)
            csv_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(csv_path)
            
            # Parse CSV
            questions = await self._load_quiz_from_csv(csv_path)
            csv_path.unlink(missing_ok=True)
            
            if not questions:
                await update.message.reply_text("❌ No valid questions found in CSV!")
                return
            
            # Store questions
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"csv_{user_id}_{timestamp}"
            
            self.user_states[user_id] = {
                'questions': questions,
                'session_id': session_id,
                'source': 'csv'
            }
            
            # Show options
            keyboard = [
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")]
            ]
            
            await update.message.reply_text(
                f"✅ **CSV Loaded**\n\n"
                f"📊 Questions: {len(questions)}\n\n"
                f"Choose action:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            print(f"❌ CSV parsing error: {e}")
            await update.message.reply_text(
                f"❌ **CSV Parse Error**\n\n"
                f"Gemini returned invalid JSON.\n\n"
                f"Error: `{str(e)[:100]}`",
                parse_mode='Markdown'
            )
    
    @require_auth
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image uploads"""
        user_id = update.effective_user.id
        
        # Ghost bug prevention
        task_queue._check_timeout(user_id)
        
        # Get highest resolution photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        img_path = config.TEMP_DIR / f"{user_id}_{photo.file_id}.jpg"
        await file.download_to_drive(img_path)
        
        # Add to or create state
        if user_id not in self.user_states or self.user_states[user_id].get('content_type') != 'images':
            self.user_states[user_id] = {
                'content_type': 'images',
                'content_paths': [],
                'waiting_for': None
            }
        
        self.user_states[user_id]['content_paths'].append(img_path)
        
        count = len(self.user_states[user_id]['content_paths'])
        
        # Ask for mode
        keyboard = [
            [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
            [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
        ]
        
        await update.message.reply_text(
            f"📸 **Image {count} received**\n\n"
            f"Send more images or choose mode:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ==================== HELPER METHODS ====================
    
    async def add_to_queue_direct(self, user_id, page_range, context):
        """Add task to queue"""
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        state['page_range'] = page_range
        
        # Add to queue
        task_queue.add_task(user_id, state, context)
        
        pos = task_queue.get_queue_position(user_id)
        
        if pos == 1:
            await context.bot.send_message(
                user_id,
                "⚙️ **Processing started...**",
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                user_id,
                f"✅ **Added to queue!**\n📋 Position: {pos}",
                parse_mode='Markdown'
            )
    
    async def _load_quiz_from_csv(self, csv_path: Path) -> list:
        """Load quiz from CSV file"""
        questions = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse options
                options = []
                for i in range(1, 11):  # Support up to 10 options
                    opt = row.get(f'option{i}', '').strip()
                    if opt:
                        options.append(opt)
                
                if len(options) < 2:
                    continue
                
                # Parse answer (1-based to 0-based index)
                try:
                    answer_idx = int(row.get('answer', '1')) - 1
                    answer_idx = max(0, min(answer_idx, len(options) - 1))
                except:
                    answer_idx = 0
                
                questions.append({
                    'question_description': row.get('questions', '').strip(),
                    'options': options,
                    'correct_answer_index': answer_idx,
                    'correct_option': chr(65 + answer_idx),  # A, B, C...
                    'explanation': row.get('explanation', '').strip()
                })
        
        return questions
    
    async def _load_quiz_from_json(self, json_path: Path) -> list:
        """Load quiz from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = []
        for q in data:
            # Get options as list
            opts_dict = q.get('options', {})
            options = []
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                opt = opts_dict.get(letter)
                if opt:
                    options.append(opt)
            
            if len(options) < 2:
                continue
            
            # Get correct answer
            correct_letter = q.get('correct_answer', 'A').upper()
            correct_idx = ord(correct_letter) - ord('A')
            correct_idx = max(0, min(correct_idx, len(options) - 1))
            
            questions.append({
                'question_description': q.get('question', '').strip(),
                'options': options,
                'correct_answer_index': correct_idx,
                'correct_option': chr(65 + correct_idx),
                'explanation': q.get('explanation', '').strip()
            })
        
        return questions
    
    # ==================== ADMIN COMMANDS ====================
    
    async def authorize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Authorize user (sudo only)"""
        if update.effective_user.id not in config.SUDO_USER_IDS:
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /authorize <user_id>")
            return
        
        try:
            target_id = int(context.args[0])
            db.authorize_user(target_id)
            await update.message.reply_text(f"✅ User {target_id} authorized!")
        except:
            await update.message.reply_text("❌ Invalid user ID")
    
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revoke user (sudo only)"""
        if update.effective_user.id not in config.SUDO_USER_IDS:
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /revoke <user_id>")
            return
        
        try:
            target_id = int(context.args[0])
            db.revoke_user(target_id)
            await update.message.reply_text(f"✅ User {target_id} revoked!")
        except:
            await update.message.reply_text("❌ Invalid user ID")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List authorized users (sudo only)"""
        if update.effective_user.id not in config.SUDO_USER_IDS:
            return
        
        users = db.get_authorized_users()
        if not users:
            await update.message.reply_text("No authorized users.")
            return
        
        user_list = "\n".join([f"• {u['user_id']}" for u in users])
        await update.message.reply_text(f"**Authorized Users:**\n\n{user_list}", parse_mode='Markdown')
