"""
Bot Handlers - COMPLETE WITH ALL FIXES
- Fixed authorize command
- Debloated messages
- Export PDF button
- Better error handling
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
        self.user_states = {}
        self.processors = {}
        print("✅ Bot Handlers initialized")
    
    def get_processor(self, user_id):
        """Get or create processor for user"""
        if user_id not in self.processors:
            from processors.pdf_processor import PDFProcessor
            from utils.api_rotator import GeminiAPIRotator
            
            api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
            self.processors[user_id] = PDFProcessor(api_rotator)
        
        return self.processors[user_id]
    
    # ==================== COMMANDS ====================
    
    @require_auth
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user = update.effective_user
        
        await update.message.reply_text(
            f"👋 **{user.first_name}**\n\n"
            f"🤖 {config.BOT_NAME}\n"
            f"Quiz bot with Gemini AI\n\n"
            f"**Commands:**\n"
            f"• /help - Commands\n"
            f"• /settings - Destinations\n"
            f"• /queue - Queue status\n"
            f"• /cancel - Cancel task\n\n"
            f"Send PDF/CSV to start.",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        await update.message.reply_text(
            "**Commands:**\n\n"
            "/start - Welcome\n"
            "/help - This message\n"
            "/info - Bot stats\n"
            "/settings - Manage destinations\n"
            "/queue - Queue status\n"
            "/cancel - Cancel task\n"
            "/collectpolls - Collect polls\n"
            "/livequiz - Live quiz\n\n"
            "**Admin:**\n"
            "/authorize - Add user\n"
            "/revoke - Remove user\n"
            "/users - List users",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Settings command"""
        keyboard = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="settings_add_channel")],
            [InlineKeyboardButton("➕ Add Group", callback_data="settings_add_group")],
            [InlineKeyboardButton("📺 Channels", callback_data="settings_manage_channels")],
            [InlineKeyboardButton("👥 Groups", callback_data="settings_manage_groups")]
        ]
        
        await update.message.reply_text(
            "⚙️ **Settings**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info command"""
        user_id = update.effective_user.id
        
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        settings = db.get_user_settings(user_id)
        
        queue_pos = task_queue.get_queue_position(user_id)
        is_processing = task_queue.is_processing(user_id)
        
        default_ch = db.get_default_channel(user_id)
        default_gr = db.get_default_group(user_id)
        
        await update.message.reply_text(
            f"ℹ️ **Info**\n\n"
            f"Channels: {len(channels)}\n"
            f"Groups: {len(groups)}\n"
            f"Default CH: {'✓' if default_ch else '✗'}\n"
            f"Default GR: {'✓' if default_gr else '✗'}\n\n"
            f"Queue: {queue_pos or 'Empty'}\n"
            f"Processing: {'Yes' if is_processing else 'No'}\n\n"
            f"Model: `{config.GEMINI_MODEL}`",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Queue status"""
        user_id = update.effective_user.id
        
        pos = task_queue.get_queue_position(user_id)
        is_proc = task_queue.is_processing(user_id)
        queue_len = task_queue.get_queue_length()
        
        if is_proc:
            status = "⚙️ Processing"
        elif pos:
            status = f"📋 Position: {pos}"
        else:
            status = "✅ Empty"
        
        await update.message.reply_text(
            f"**Queue**\n\n{status}\nTotal: {queue_len}",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel tasks"""
        user_id = update.effective_user.id
        
        from processors.quiz_poster import quiz_poster
        posting_cancelled = quiz_poster.cancel_posting(user_id)
        
        task_queue.clear_user(user_id)
        self.user_states.pop(user_id, None)
        
        if posting_cancelled:
            await update.message.reply_text("🛑 Posting cancelled")
        else:
            await update.message.reply_text("✅ Cancelled")
    
    @require_auth
    async def collectpolls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start poll collection"""
        await poll_collector.start_collection(update, context)
    
    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show model"""
        await update.message.reply_text(
            f"🤖 Model: `{config.GEMINI_MODEL}`",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def livequiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Live quiz"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states or 'questions' not in self.user_states[user_id]:
            await update.message.reply_text("❌ No questions. Send CSV/JSON first.")
            return
        
        questions = self.user_states[user_id]['questions']
        
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
            
            keyboard = [[InlineKeyboardButton("⏭️ Skip", callback_data=f"livequiz_skip_{session_id}")]]
            
            await update.message.reply_text(
                "🎯 **Live Quiz**\n\nSend announcement or skip.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    # ==================== ADMIN ====================
    
    async def authorize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Authorize user (sudo only)"""
        user_id = update.effective_user.id
        
        if user_id not in config.SUDO_USER_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        
        if not context.args:
            await update.message.reply_text(
                "**Usage:**\n`/authorize <user_id>`\n\n"
                "Example:\n`/authorize 1234567890`",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_id = int(context.args[0])
            
            if db.is_user_authorized(target_id):
                await update.message.reply_text(f"⚠️ User `{target_id}` already authorized", parse_mode='Markdown')
                return
            
            db.authorize_user(target_id)
            await update.message.reply_text(f"✅ Authorized: `{target_id}`", parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text("❌ Invalid ID (must be number)")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: `{str(e)[:100]}`", parse_mode='Markdown')
    
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revoke user"""
        user_id = update.effective_user.id
        
        if user_id not in config.SUDO_USER_IDS:
            return
        
        if not context.args:
            await update.message.reply_text("Usage: `/revoke <user_id>`", parse_mode='Markdown')
            return
        
        try:
            target_id = int(context.args[0])
            db.revoke_user(target_id)
            await update.message.reply_text(f"✅ Revoked: `{target_id}`", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Invalid ID")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List users"""
        if update.effective_user.id not in config.SUDO_USER_IDS:
            return
        
        users = db.get_authorized_users()
        if not users:
            await update.message.reply_text("No users")
            return
        
        user_list = "\n".join([f"• `{u['user_id']}`" for u in users])
        await update.message.reply_text(f"**Users:**\n\n{user_list}", parse_mode='Markdown')
    
    # ==================== FILE HANDLERS ====================
    
    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        task_queue._check_timeout(user_id)
        
        if task_queue.is_in_queue(user_id) or task_queue.is_processing(user_id):
            pos = task_queue.get_queue_position(user_id)
            if pos:
                await update.message.reply_text(f"📋 Already queued (Position: {pos})")
            else:
                await update.message.reply_text("⚙️ Already processing")
            return
        
        if doc.mime_type == 'application/pdf':
            file = await context.bot.get_file(doc.file_id)
            pdf_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(pdf_path)
            
            self.user_states[user_id] = {
                'content_type': 'pdf',
                'content_paths': [pdf_path],
                'waiting_for': None
            }
            
            keyboard = [
                [InlineKeyboardButton("📄 All Pages", callback_data="pages_all")],
                [InlineKeyboardButton("🔢 Range", callback_data="pages_custom")]
            ]
            
            await update.message.reply_text(
                "📄 PDF received\n\nSelect pages:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Send PDF only")
    
    @require_auth
    async def handle_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle CSV"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        task_queue._check_timeout(user_id)
        
        if not doc.file_name.endswith('.csv'):
            await update.message.reply_text("❌ Send CSV file")
            return
        
        try:
            file = await context.bot.get_file(doc.file_id)
            csv_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(csv_path)
            
            questions = await self._load_quiz_from_csv(csv_path)
            csv_path.unlink(missing_ok=True)
            
            if not questions:
                await update.message.reply_text("❌ No questions in CSV")
                return
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"csv_{user_id}_{timestamp}"
            
            self.user_states[user_id] = {
                'questions': questions,
                'session_id': session_id,
                'source': 'csv'
            }
            
            keyboard = [
                [InlineKeyboardButton("📢 Post", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")],
                [InlineKeyboardButton("📄 Export PDF", callback_data=f"export_pdf_{session_id}")]
            ]
            
            await update.message.reply_text(
                f"✅ CSV • {len(questions)}Q",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Parse error: `{str(e)[:100]}`", parse_mode='Markdown')
    
    @require_auth
    async def handle_json(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle JSON"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        task_queue._check_timeout(user_id)
        
        if not doc.file_name.endswith('.json'):
            await update.message.reply_text("❌ Send JSON file")
            return
        
        try:
            file = await context.bot.get_file(doc.file_id)
            json_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(json_path)
            
            questions = await self._load_quiz_from_json(json_path)
            json_path.unlink(missing_ok=True)
            
            if not questions:
                await update.message.reply_text("❌ No questions in JSON")
                return
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"json_{user_id}_{timestamp}"
            
            self.user_states[user_id] = {
                'questions': questions,
                'session_id': session_id,
                'source': 'json'
            }
            
            keyboard = [
                [InlineKeyboardButton("📢 Post", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")],
                [InlineKeyboardButton("📄 Export PDF", callback_data=f"export_pdf_{session_id}")]
            ]
            
            await update.message.reply_text(
                f"✅ JSON • {len(questions)}Q",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Parse error: `{str(e)[:100]}`", parse_mode='Markdown')
    
    @require_auth
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle images"""
        user_id = update.effective_user.id
        
        task_queue._check_timeout(user_id)
        
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        img_path = config.TEMP_DIR / f"{user_id}_{photo.file_id}.jpg"
        await file.download_to_drive(img_path)
        
        if user_id not in self.user_states or self.user_states[user_id].get('content_type') != 'images':
            self.user_states[user_id] = {
                'content_type': 'images',
                'content_paths': [],
                'waiting_for': None
            }
        
        self.user_states[user_id]['content_paths'].append(img_path)
        
        count = len(self.user_states[user_id]['content_paths'])
        
        keyboard = [
            [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
            [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
        ]
        
        await update.message.reply_text(
            f"📸 Image {count}\n\nSend more or choose mode:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ==================== HELPERS ====================
    
    async def add_to_queue_direct(self, user_id, page_range, context):
        """Add to queue"""
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        state['page_range'] = page_range
        
        task_queue.add_task(user_id, state, context)
        
        pos = task_queue.get_queue_position(user_id)
        
        if pos == 1:
            await context.bot.send_message(user_id, "⚙️ Processing...")
        else:
            await context.bot.send_message(user_id, f"📋 Queued • Position {pos}")
    
    async def _load_quiz_from_csv(self, csv_path: Path) -> list:
        """Load from CSV"""
        questions = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                options = []
                for i in range(1, 11):
                    opt = row.get(f'option{i}', '').strip()
                    if opt:
                        options.append(opt)
                
                if len(options) < 2:
                    continue
                
                try:
                    answer_idx = int(row.get('answer', '1')) - 1
                    answer_idx = max(0, min(answer_idx, len(options) - 1))
                except:
                    answer_idx = 0
                
                questions.append({
                    'question_description': row.get('questions', '').strip(),
                    'options': options,
                    'correct_answer_index': answer_idx,
                    'correct_option': chr(65 + answer_idx),
                    'explanation': row.get('explanation', '').strip()
                })
        
        return questions
    
    async def _load_quiz_from_json(self, json_path: Path) -> list:
        """Load from JSON"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = []
        for q in data:
            opts_dict = q.get('options', {})
            options = []
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                opt = opts_dict.get(letter)
                if opt:
                    options.append(opt)
            
            if len(options) < 2:
                continue
            
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
