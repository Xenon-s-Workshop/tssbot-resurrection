"""
Bot Handlers - Enhanced with Better UX
Descriptive commands, proper CSV export, improved workflow
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
    
    # ==================== ENHANCED COMMANDS ====================
    
    @require_auth
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with clear explanation"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("📚 How to Use", callback_data="help_usage")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings_main")],
            [InlineKeyboardButton("ℹ️ About", callback_data="help_about")]
        ]
        
        await update.message.reply_text(
            f"👋 **Welcome, {user.first_name}!**\n\n"
            f"🤖 **{config.BOT_NAME} v{config.BOT_VERSION}**\n"
            f"AI-powered quiz generator for Telegram\n\n"
            f"**What I do:**\n"
            f"• Extract quizzes from PDFs/images\n"
            f"• Generate questions with AI\n"
            f"• Export to CSV, JSON, PDF\n"
            f"• Post quizzes to channels/groups\n"
            f"• Run live quiz sessions\n\n"
            f"**Quick Start:**\n"
            f"1. Send me a PDF or images\n"
            f"2. Choose extraction or generation\n"
            f"3. Get CSV, JSON, PDF files\n"
            f"4. Post quizzes to your channel\n\n"
            f"📖 Use /help for detailed guide",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comprehensive help with step-by-step workflow"""
        help_text = (
            "📖 **Complete Guide**\n\n"
            "**🔹 STEP 1: Generate Quizzes**\n\n"
            "**From PDF:**\n"
            "• Send PDF file\n"
            "• Choose page range or all\n"
            "• Select mode:\n"
            "  - 📤 Extraction: Extract existing quizzes\n"
            "  - ✨ Generation: AI creates new quizzes\n\n"
            "**From Images:**\n"
            "• Send images (one or multiple)\n"
            "• Choose extraction/generation\n\n"
            "**From CSV/JSON:**\n"
            "• Send CSV or JSON file\n"
            "• Questions loaded instantly\n\n"
            "**🔹 STEP 2: Get Outputs**\n\n"
            "You'll receive 3 files:\n"
            "• **CSV**: Spreadsheet format\n"
            "  - Questions, options, answers\n"
            "  - Can edit in Excel/Sheets\n\n"
            "• **JSON**: Structured data\n"
            "  - For developers/automation\n\n"
            "• **PDF**: Beautiful printable format\n"
            "  - 2 modes available in settings\n"
            "  - Mode 1: Answers at end\n"
            "  - Mode 2: Answers inline\n\n"
            "**🔹 STEP 3: Post Quizzes**\n\n"
            "1. Click **Post Quiz** button\n"
            "2. Send header message (or skip)\n"
            "3. Select channel/group\n"
            "4. Watch progress bar\n"
            "5. Get \"?/total\" counter at end\n\n"
            "**🔹 COMMANDS**\n\n"
            "/start - Welcome screen\n"
            "/help - This guide\n"
            "/settings - Manage destinations & preferences\n"
            "/info - Your stats\n"
            "/queue - Check processing queue\n"
            "/cancel - Cancel current task\n"
            "/collectpolls - Collect poll results\n"
            "/livequiz - Start live quiz session\n\n"
            "**🔹 TIPS**\n\n"
            "• Set default channel in /settings\n"
            "• Customize quiz marker & explanation tag\n"
            "• Change PDF mode for your needs\n"
            "• Multiple PDFs queue automatically\n\n"
            "Need help? Contact admin!"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    @require_auth
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Settings menu"""
        keyboard = [
            [InlineKeyboardButton("📺 Manage Channels", callback_data="settings_manage_channels")],
            [InlineKeyboardButton("👥 Manage Groups", callback_data="settings_manage_groups")],
            [InlineKeyboardButton("🎯 Quiz Marker", callback_data="settings_quiz_marker")],
            [InlineKeyboardButton("📝 Explanation Tag", callback_data="settings_exp_tag")],
            [InlineKeyboardButton("📄 PDF Mode", callback_data="settings_pdf_mode")]
        ]
        
        settings = db.get_user_settings(update.effective_user.id)
        
        await update.message.reply_text(
            f"⚙️ **Settings**\n\n"
            f"Current Configuration:\n"
            f"• Quiz Marker: `{settings.get('quiz_marker', '🎯 Quiz')}`\n"
            f"• Explanation Tag: `{settings.get('explanation_tag', 'Exp')}`\n"
            f"• PDF Mode: `{settings.get('pdf_mode', 'mode1')}`\n\n"
            f"Choose setting to modify:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @require_auth
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """User info and stats"""
        user_id = update.effective_user.id
        
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        settings = db.get_user_settings(user_id)
        
        queue_pos = task_queue.get_queue_position(user_id)
        is_processing = task_queue.is_processing(user_id)
        
        default_ch = db.get_default_channel(user_id)
        default_gr = db.get_default_group(user_id)
        
        await update.message.reply_text(
            f"ℹ️ **Your Info**\n\n"
            f"**Destinations:**\n"
            f"• Channels: {len(channels)}\n"
            f"• Groups: {len(groups)}\n"
            f"• Default Channel: {'✓' if default_ch else '✗'}\n"
            f"• Default Group: {'✓' if default_gr else '✗'}\n\n"
            f"**Queue Status:**\n"
            f"• Position: {queue_pos if queue_pos else 'Empty'}\n"
            f"• Processing: {'Yes' if is_processing else 'No'}\n\n"
            f"**Configuration:**\n"
            f"• AI Model: `{config.GEMINI_MODEL}`\n"
            f"• Quiz Marker: `{settings.get('quiz_marker', '🎯 Quiz')}`\n"
            f"• Exp Tag: `{settings.get('explanation_tag', 'Exp')}`\n"
            f"• PDF Mode: `{settings.get('pdf_mode', 'mode1')}`",
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
            status = "⚙️ **Processing your task**"
        elif pos:
            status = f"📋 **Queue Position:** {pos}"
        else:
            status = "✅ **Queue Empty**"
        
        await update.message.reply_text(
            f"**Queue Status**\n\n"
            f"{status}\n"
            f"Total in queue: {queue_len}",
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
            await update.message.reply_text("🛑 **Posting Cancelled**")
        else:
            await update.message.reply_text("✅ **All Tasks Cancelled**")
    
    @require_auth
    async def collectpolls_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start poll collection"""
        await poll_collector.start_collection(update, context)
    
    @require_auth
    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show AI model"""
        await update.message.reply_text(
            f"🤖 **AI Model**\n\n"
            f"Current: `{config.GEMINI_MODEL}`\n"
            f"Provider: Google Gemini",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def livequiz_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start live quiz"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_states or 'questions' not in self.user_states[user_id]:
            await update.message.reply_text(
                "❌ **No Questions Loaded**\n\n"
                "Please send CSV/JSON file first.",
                parse_mode='Markdown'
            )
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
                "🎯 **Live Quiz Setup**\n\n"
                "Send announcement message or skip.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    # ==================== ADMIN ====================
    
    async def authorize_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Authorize user"""
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
                await update.message.reply_text(
                    f"⚠️ User `{target_id}` already authorized",
                    parse_mode='Markdown'
                )
                return
            
            db.authorize_user(target_id)
            await update.message.reply_text(
                f"✅ **Authorized**\n\nUser ID: `{target_id}`",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID (must be number)")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: `{str(e)[:100]}`", parse_mode='Markdown')
    
    async def revoke_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revoke user"""
        user_id = update.effective_user.id
        
        if user_id not in config.SUDO_USER_IDS:
            return
        
        if not context.args:
            await update.message.reply_text("**Usage:** `/revoke <user_id>`", parse_mode='Markdown')
            return
        
        try:
            target_id = int(context.args[0])
            db.revoke_user(target_id)
            await update.message.reply_text(f"✅ **Revoked:** `{target_id}`", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Invalid user ID")
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List authorized users"""
        if update.effective_user.id not in config.SUDO_USER_IDS:
            return
        
        users = db.get_authorized_users()
        if not users:
            await update.message.reply_text("No authorized users")
            return
        
        user_list = "\n".join([f"• `{u['user_id']}`" for u in users])
        await update.message.reply_text(
            f"**Authorized Users:**\n\n{user_list}",
            parse_mode='Markdown'
        )
    
    # ==================== FILE HANDLERS ====================
    
    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF with descriptive messages"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        task_queue._check_timeout(user_id)
        
        if task_queue.is_in_queue(user_id) or task_queue.is_processing(user_id):
            pos = task_queue.get_queue_position(user_id)
            if pos:
                await update.message.reply_text(
                    f"📋 **Already Queued**\n\nPosition: {pos}",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("⚙️ **Already Processing**")
            return
        
        if doc.mime_type == 'application/pdf':
            msg = await update.message.reply_text("📥 **Downloading PDF...**")
            
            file = await context.bot.get_file(doc.file_id)
            pdf_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(pdf_path)
            
            await msg.edit_text("✅ **PDF Downloaded**")
            
            self.user_states[user_id] = {
                'content_type': 'pdf',
                'content_paths': [pdf_path],
                'waiting_for': None
            }
            
            keyboard = [
                [InlineKeyboardButton("📄 All Pages", callback_data="pages_all")],
                [InlineKeyboardButton("🔢 Page Range", callback_data="pages_custom")]
            ]
            
            await update.message.reply_text(
                "📄 **PDF Ready**\n\nSelect pages:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Please send PDF file")
    
    @require_auth
    async def handle_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle CSV with validation"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        task_queue._check_timeout(user_id)
        
        if not doc.file_name.endswith('.csv'):
            await update.message.reply_text("❌ Please send CSV file")
            return
        
        msg = await update.message.reply_text("📊 **Loading CSV...**")
        
        try:
            file = await context.bot.get_file(doc.file_id)
            csv_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(csv_path)
            
            questions = await self._load_quiz_from_csv(csv_path)
            csv_path.unlink(missing_ok=True)
            
            if not questions:
                await msg.edit_text("❌ **No Valid Questions**\n\nCheck CSV format.")
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
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")],
                [InlineKeyboardButton("📄 Export PDF", callback_data=f"export_pdf_{session_id}")]
            ]
            
            await msg.edit_text(
                f"✅ **CSV Loaded**\n\n"
                f"Questions: {len(questions)}\n\n"
                f"Choose action:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await msg.edit_text(
                f"❌ **CSV Error**\n\n`{str(e)[:150]}`",
                parse_mode='Markdown'
            )
    
    @require_auth
    async def handle_json(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle JSON with validation"""
        user_id = update.effective_user.id
        doc = update.message.document
        
        task_queue._check_timeout(user_id)
        
        if not doc.file_name.endswith('.json'):
            await update.message.reply_text("❌ Please send JSON file")
            return
        
        msg = await update.message.reply_text("📋 **Loading JSON...**")
        
        try:
            file = await context.bot.get_file(doc.file_id)
            json_path = config.TEMP_DIR / f"{user_id}_{doc.file_name}"
            await file.download_to_drive(json_path)
            
            questions = await self._load_quiz_from_json(json_path)
            json_path.unlink(missing_ok=True)
            
            if not questions:
                await msg.edit_text("❌ **No Valid Questions**\n\nCheck JSON format.")
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
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")],
                [InlineKeyboardButton("📄 Export PDF", callback_data=f"export_pdf_{session_id}")]
            ]
            
            await msg.edit_text(
                f"✅ **JSON Loaded**\n\n"
                f"Questions: {len(questions)}\n\n"
                f"Choose action:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await msg.edit_text(
                f"❌ **JSON Error**\n\n`{str(e)[:150]}`",
                parse_mode='Markdown'
            )
    
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
            f"📸 **Image {count} Received**\n\n"
            f"Send more images or choose mode:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ==================== HELPERS ====================
    
    async def add_to_queue_direct(self, user_id, page_range, context):
        """Add task to queue"""
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        state['page_range'] = page_range
        
        task_queue.add_task(user_id, state, context)
        
        pos = task_queue.get_queue_position(user_id)
        
        if pos == 1:
            await context.bot.send_message(user_id, "⚙️ **Processing...**")
        else:
            await context.bot.send_message(user_id, f"📋 **Queued**\n\nPosition: {pos}")
    
    async def _load_quiz_from_csv(self, csv_path: Path) -> list:
        """Load and validate CSV"""
        questions = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Get question
                        question = row.get('questions', '').strip()
                        if not question:
                            print(f"⚠️ Row {row_num}: Empty question")
                            continue
                        
                        # Get options
                        options = []
                        for i in range(1, 11):
                            opt = row.get(f'option{i}', '').strip()
                            if opt:
                                options.append(opt)
                        
                        if len(options) < 2:
                            print(f"⚠️ Row {row_num}: Less than 2 options")
                            continue
                        
                        # Get answer
                        try:
                            answer_idx = int(row.get('answer', '1')) - 1
                            answer_idx = max(0, min(answer_idx, len(options) - 1))
                        except:
                            print(f"⚠️ Row {row_num}: Invalid answer, defaulting to 1")
                            answer_idx = 0
                        
                        questions.append({
                            'question_description': question,
                            'options': options,
                            'correct_answer_index': answer_idx,
                            'correct_option': chr(65 + answer_idx),
                            'explanation': row.get('explanation', '').strip()
                        })
                        
                    except Exception as e:
                        print(f"⚠️ Row {row_num} error: {e}")
                        continue
        
        except Exception as e:
            print(f"❌ CSV read error: {e}")
            raise
        
        print(f"✅ Loaded {len(questions)} questions from CSV")
        return questions
    
    async def _load_quiz_from_json(self, json_path: Path) -> list:
        """Load and validate JSON"""
        questions = []
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for idx, q in enumerate(data, 1):
                try:
                    # Get question
                    question = q.get('question', '').strip()
                    if not question:
                        print(f"⚠️ Question {idx}: Empty")
                        continue
                    
                    # Get options
                    opts_dict = q.get('options', {})
                    options = []
                    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                        opt = opts_dict.get(letter)
                        if opt:
                            options.append(opt)
                    
                    if len(options) < 2:
                        print(f"⚠️ Question {idx}: Less than 2 options")
                        continue
                    
                    # Get answer
                    correct_letter = q.get('correct_answer', 'A').upper()
                    correct_idx = ord(correct_letter) - ord('A')
                    correct_idx = max(0, min(correct_idx, len(options) - 1))
                    
                    questions.append({
                        'question_description': question,
                        'options': options,
                        'correct_answer_index': correct_idx,
                        'correct_option': chr(65 + correct_idx),
                        'explanation': q.get('explanation', '').strip()
                    })
                    
                except Exception as e:
                    print(f"⚠️ Question {idx} error: {e}")
                    continue
        
        except Exception as e:
            print(f"❌ JSON read error: {e}")
            raise
        
        print(f"✅ Loaded {len(questions)} questions from JSON")
        return questions
