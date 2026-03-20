"""
Bot Handlers - Complete with All Commands
Includes: start, help, settings, info, queue, cancel, livequiz, authorize, revoke, users, collectpolls, merge, poll handling
"""

import re
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from pathlib import Path
from config import config
from database import db
from utils.auth import require_auth
from utils.api_rotator import GeminiAPIRotator
from utils.queue_manager import task_queue
from processors.pdf_processor import PDFProcessor

class BotHandlers:
    def __init__(self):
        self.user_states = {}
        self.api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
        self.pdf_processors = {}
        print("✅ Bot Handlers initialized")
    
    def get_processor(self, user_id: int):
        """Get or create PDF processor for user"""
        if user_id not in self.pdf_processors:
            self.pdf_processors[user_id] = PDFProcessor(self.api_rotator)
        return self.pdf_processors[user_id]
    
    # ==================== BASIC COMMANDS ====================
    
    @require_auth
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("📚 Help", callback_data="help_usage")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="start_settings")],
            [InlineKeyboardButton("ℹ️ About", callback_data="help_about")]
        ]
        
        welcome_text = (
            f"👋 **Welcome {user.first_name}!**\n\n"
            f"I'm **{config.BOT_NAME}** - Your AI-powered quiz assistant.\n\n"
            f"**What I can do:**\n"
            f"• Extract quizzes from PDFs/images\n"
            f"• Generate new quizzes with AI\n"
            f"• Export to CSV, JSON, PDF formats\n"
            f"• Post quizzes to channels/groups\n"
            f"• Collect and organize polls\n"
            f"• Run live quiz sessions\n\n"
            f"**Quick Start:**\n"
            f"1. Send me a PDF or images\n"
            f"2. Choose extraction or generation\n"
            f"3. Get your quiz files\n"
            f"4. Post or share!\n\n"
            f"Use /help for detailed guide."
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "📚 **Complete Guide**\n\n"
            "**📤 Input Methods:**\n"
            "• PDF files (select page range)\n"
            "• Images (multiple supported)\n"
            "• CSV files (load existing quizzes)\n"
            "• JSON files (structured data)\n\n"
            "**⚙️ Processing Modes:**\n"
            "• **Extraction:** Pull quizzes from images\n"
            "• **Generation:** AI creates new quizzes\n\n"
            "**📦 Output Formats:**\n"
            "• CSV - Data format\n"
            "• JSON - Structured format\n"
            "• PDF Format 1 - Practice sheet\n"
            "• PDF Format 2 - Questions + answers\n\n"
            "**📢 Posting:**\n"
            "1. Click 'Post Quizzes'\n"
            "2. Optional: Send header message\n"
            "3. Select destination\n"
            "4. Watch progress\n\n"
            "**📊 Poll Collection:**\n"
            "• /collectpolls - Start collecting\n"
            "• Forward quiz polls to me\n"
            "• /done - Export to CSV\n"
            "• /merge - Merge multiple files\n\n"
            "**⚙️ Settings:**\n"
            "• Quiz marker (customizable)\n"
            "• Explanation tag (customizable)\n"
            "• Manage channels/groups\n\n"
            "**Commands:**\n"
            "• /start - Welcome screen\n"
            "• /help - This guide\n"
            "• /settings - Preferences\n"
            "• /info - Your stats\n"
            "• /queue - Check queue\n"
            "• /cancel - Cancel current task\n"
            "• /collectpolls - Collect polls\n"
            "• /merge - Merge files\n"
            "• /livequiz - Start live quiz\n\n"
            f"**Model:** {config.GEMINI_MODEL}\n"
            f"**Version:** {config.BOT_VERSION}"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    @require_auth
    async def handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        user_id = update.effective_user.id
        settings = db.get_user_settings(user_id)
        
        keyboard = [
            [InlineKeyboardButton("📺 Manage Channels", callback_data="settings_manage_channels")],
            [InlineKeyboardButton("👥 Manage Groups", callback_data="settings_manage_groups")],
            [InlineKeyboardButton("🎯 Quiz Marker", callback_data="settings_quiz_marker")],
            [InlineKeyboardButton("📝 Explanation Tag", callback_data="settings_exp_tag")],
        ]
        
        settings_text = (
            f"⚙️ **Settings**\n\n"
            f"**Current Configuration:**\n"
            f"• Quiz Marker: `{settings.get('quiz_marker', '🎯 Quiz')}`\n"
            f"• Explanation Tag: `{settings.get('explanation_tag', 'Exp')}`\n\n"
            f"Select setting to modify:"
        )
        
        await update.message.reply_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command"""
        user_id = update.effective_user.id
        
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        settings = db.get_user_settings(user_id)
        
        info_text = (
            f"ℹ️ **Your Information**\n\n"
            f"**User ID:** `{user_id}`\n"
            f"**Channels:** {len(channels)}\n"
            f"**Groups:** {len(groups)}\n\n"
            f"**Settings:**\n"
            f"• Quiz Marker: `{settings.get('quiz_marker', '🎯 Quiz')}`\n"
            f"• Explanation Tag: `{settings.get('explanation_tag', 'Exp')}`\n\n"
            f"**Queue Status:**\n"
            f"• In Queue: {'Yes' if task_queue.is_in_queue(user_id) else 'No'}\n"
            f"• Processing: {'Yes' if task_queue.is_processing(user_id) else 'No'}\n\n"
            f"**Model:** {config.GEMINI_MODEL}"
        )
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
    
    @require_auth
    async def handle_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /queue command"""
        user_id = update.effective_user.id
        
        position = task_queue.get_queue_position(user_id)
        total = task_queue.get_queue_length()
        is_processing = task_queue.is_processing(user_id)
        
        if is_processing:
            status_text = "⚙️ **Queue Status**\n\n✅ Your task is currently processing!"
        elif position:
            status_text = (
                f"📋 **Queue Status**\n\n"
                f"Your position: {position}/{total}\n"
                f"Please wait..."
            )
        else:
            status_text = "📋 **Queue Status**\n\n❌ You have no tasks in queue."
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    @require_auth
    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        user_id = update.effective_user.id
        
        # Clear from queue
        task_queue.clear_user(user_id)
        
        # Clear user state
        if user_id in self.user_states:
            del self.user_states[user_id]
        
        await update.message.reply_text(
            "❌ **Cancelled**\n\nAll tasks cleared.",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_livequiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /livequiz command"""
        await update.message.reply_text(
            "🎯 **Live Quiz**\n\n"
            "Generate quizzes first, then use the 'Live Quiz' button.",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /model command"""
        await update.message.reply_text(
            f"🤖 **Current Model**\n\n"
            f"Model: `{config.GEMINI_MODEL}`\n"
            f"API Keys: {len(config.GEMINI_API_KEYS)} configured",
            parse_mode='Markdown'
        )
    
    # ==================== ADMIN COMMANDS ====================
    
    async def handle_authorize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /authorize command"""
        user_id = update.effective_user.id
        
        # Check if sudo user
        if user_id not in config.SUDO_USER_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        
        # Parse user ID
        try:
            args = update.message.text.split()
            if len(args) < 2:
                await update.message.reply_text("Usage: /authorize <user_id>")
                return
            
            target_user_id = int(args[1])
            db.authorize_user(target_user_id)
            
            await update.message.reply_text(
                f"✅ **User Authorized**\n\nUser ID: `{target_user_id}`",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_revoke(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /revoke command"""
        user_id = update.effective_user.id
        
        # Check if sudo user
        if user_id not in config.SUDO_USER_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        
        # Parse user ID
        try:
            args = update.message.text.split()
            if len(args) < 2:
                await update.message.reply_text("Usage: /revoke <user_id>")
                return
            
            target_user_id = int(args[1])
            db.revoke_user(target_user_id)
            
            await update.message.reply_text(
                f"✅ **User Revoked**\n\nUser ID: `{target_user_id}`",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def handle_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /users command"""
        user_id = update.effective_user.id
        
        # Check if sudo user
        if user_id not in config.SUDO_USER_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        
        users = db.get_authorized_users()
        
        if not users:
            await update.message.reply_text("No authorized users")
            return
        
        user_list = "👥 **Authorized Users**\n\n"
        for u in users:
            user_list += f"• `{u['user_id']}`\n"
        
        await update.message.reply_text(user_list, parse_mode='Markdown')
    
    # ==================== POLL COLLECTION ====================
    
    @require_auth
    async def handle_collectpolls(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /collectpolls command"""
        user_id = update.effective_user.id
        
        from processors.poll_collector import poll_collector
        
        # Check if already collecting
        if poll_collector.is_collecting(user_id):
            count = poll_collector.get_poll_count(user_id)
            await update.message.reply_text(
                f"📊 **Already Collecting Polls**\n\n"
                f"Current: {count} polls\n\n"
                f"Use /done to finish or /cancel to stop.",
                parse_mode='Markdown'
            )
            return
        
        # Parse filename
        filename = poll_collector.parse_filename(update.message.text)
        
        # Start collection
        poll_collector.start_collection(user_id, filename)
        poll_collector.set_chat_id(user_id, update.effective_chat.id)
        
        await update.message.reply_text(
            f"✅ **Poll Collection Started**\n\n"
            f"📁 Filename: `{filename}`\n"
            f"📊 Forward quiz polls to me (max {poll_collector.MAX_POLLS})\n\n"
            f"**Commands:**\n"
            f"• /done - Export CSV\n"
            f"• /status - Check progress\n"
            f"• /cancel - Stop collection\n\n"
            f"Send polls now!",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_poll(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forwarded polls"""
        user_id = update.effective_user.id
        
        from processors.poll_collector import poll_collector
        
        # Check if collecting
        if not poll_collector.is_collecting(user_id):
            return
        
        poll = update.poll
        if not poll or poll.type != 'quiz':
            await update.message.reply_text("❌ Only quiz polls are supported")
            return
        
        # Add poll
        poll_data = {
            'question': poll.question,
            'options': [opt.text for opt in poll.options],
            'correct_option_id': poll.correct_option_id,
            'explanation': poll.explanation or ''
        }
        
        poll_collector.add_poll(user_id, poll_data)
    
    @require_auth
    async def handle_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /done command"""
        user_id = update.effective_user.id
        
        from processors.poll_collector import poll_collector
        
        # Check for merge mode
        if poll_collector.is_merging(user_id):
            await self._handle_merge_done(update, context, user_id)
            return
        
        # Check for collection mode
        if not poll_collector.is_collecting(user_id):
            await update.message.reply_text("❌ Not collecting polls. Use /collectpolls to start.")
            return
        
        user_state = poll_collector.user_states.get(user_id)
        if not user_state:
            await update.message.reply_text("❌ No active session")
            return
        
        # Cancel pending processing
        if user_state.get('processing_task') and not user_state['processing_task'].done():
            user_state['processing_task'].cancel()
        
        polls_count = poll_collector.get_poll_count(user_id)
        
        if polls_count == 0:
            await update.message.reply_text("❌ No polls collected")
            return
        
        # Export polls
        try:
            csv_path, count = poll_collector.export_csv(user_id)
            filename = poll_collector.get_filename(user_id)
            
            # Send CSV
            with open(csv_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=filename,
                    caption=f"📊 **Poll Collection Complete**\n\n✅ {count} polls exported"
                )
            
            # Cleanup
            import os
            os.unlink(csv_path)
            await poll_collector.cleanup_progress_message(
                update.effective_chat.id, user_state, context
            )
            poll_collector.stop_collection(user_id)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Export failed: {str(e)}")
    
    async def _handle_merge_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Handle merge completion"""
        from processors.poll_collector import poll_collector
        
        try:
            progress_msg = await update.message.reply_text("🔄 **Merging files...**")
            
            output_path, file_count = await poll_collector.perform_merge(user_id)
            
            # Send merged file
            with open(output_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=output_path.name,
                    caption=f"✅ **Merge Complete**\n\n📁 Files merged: {file_count}"
                )
            
            # Cleanup
            import os
            os.unlink(output_path)
            poll_collector.cleanup_merge_session(user_id)
            
            await progress_msg.delete()
            
        except Exception as e:
            await update.message.reply_text(f"❌ Merge failed: {str(e)}")
    
    @require_auth
    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        from processors.poll_collector import poll_collector
        
        if poll_collector.is_merging(user_id):
            count = poll_collector.get_merge_file_count(user_id)
            await update.message.reply_text(
                f"📁 **Merge Mode**\n\n"
                f"Files: {count}\n\n"
                f"Use /done to merge",
                parse_mode='Markdown'
            )
            return
        
        if not poll_collector.is_collecting(user_id):
            await update.message.reply_text("❌ Not collecting polls. Use /collectpolls to start.")
            return
        
        count = poll_collector.get_poll_count(user_id)
        filename = poll_collector.get_filename(user_id)
        
        await update.message.reply_text(
            f"📊 **Collection Status**\n\n"
            f"📁 File: `{filename}`\n"
            f"✅ Collected: {count} polls\n\n"
            f"Use /done to export",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_merge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /merge command"""
        user_id = update.effective_user.id
        
        from processors.poll_collector import poll_collector
        
        # Parse filename
        filename_match = re.search(r'"([^"]+)"', update.message.text)
        filename = filename_match.group(1).strip() if filename_match else None
        
        # Start merge session
        poll_collector.start_merge_session(user_id, filename)
        
        await update.message.reply_text(
            "📁 **Merge Mode Started**\n\n"
            "📤 Send files to merge (all CSV or all JSON)\n"
            "✅ Type /done when finished\n"
            "❌ Type /cancel to abort",
            parse_mode='Markdown'
        )
    
    # ==================== FILE HANDLERS ====================
    
    @require_auth
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads"""
        user_id = update.effective_user.id
        document = update.message.document
        
        # Check for merge mode
        from processors.poll_collector import poll_collector
        if poll_collector.is_merging(user_id):
            await self._handle_document_for_merge(update, context, user_id, document)
            return
        
        file_name = document.file_name.lower()
        
        # Handle CSV
        if file_name.endswith('.csv'):
            await self.handle_csv(update, context)
        # Handle JSON
        elif file_name.endswith('.json'):
            await self.handle_json(update, context)
        # Handle PDF
        elif file_name.endswith('.pdf'):
            await self._handle_pdf(update, context, user_id, document)
        else:
            await update.message.reply_text("❌ Unsupported file type")
    
    async def _handle_document_for_merge(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, document):
        """Handle document uploads during merge"""
        from processors.poll_collector import poll_collector
        
        file_name = document.file_name.lower()
        
        # Determine file type
        if file_name.endswith('.csv'):
            file_type = 'csv'
        elif file_name.endswith('.json'):
            file_type = 'json'
        else:
            await update.message.reply_text("❌ Only CSV and JSON files supported")
            return
        
        # Download file
        file = await context.bot.get_file(document.file_id)
        temp_path = config.OUTPUT_DIR / f"merge_{user_id}_{document.file_id}.{file_type}"
        await file.download_to_drive(temp_path)
        
        # Add to merge queue
        success = poll_collector.add_merge_file(user_id, str(temp_path), file_type)
        
        if success:
            count = poll_collector.get_merge_file_count(user_id)
            await update.message.reply_text(
                f"✅ **File Added**\n\n"
                f"Total: {count} {file_type.upper()} files\n\n"
                f"Send more or /done to merge",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Cannot mix CSV and JSON files")
    
    async def _handle_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, document):
        """Handle PDF document"""
        # Download PDF
        file = await context.bot.get_file(document.file_id)
        pdf_path = config.TEMP_DIR / f"pdf_{user_id}_{document.file_id}.pdf"
        await file.download_to_drive(pdf_path)
        
        # Store in user state
        self.user_states[user_id] = {
            'pdf_path': pdf_path,
            'waiting_for': 'page_selection'
        }
        
        keyboard = [
            [InlineKeyboardButton("📄 All Pages", callback_data="pages_all")],
            [InlineKeyboardButton("🔢 Custom Range", callback_data="pages_custom")]
        ]
        
        await update.message.reply_text(
            "📄 **PDF Received**\n\nSelect pages:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle CSV file"""
        user_id = update.effective_user.id
        document = update.message.document
        
        # Download CSV
        file = await context.bot.get_file(document.file_id)
        csv_path = config.TEMP_DIR / f"csv_{user_id}_{document.file_id}.csv"
        await file.download_to_drive(csv_path)
        
        # Load CSV (simplified - implement full CSV loading)
        await update.message.reply_text(
            "📊 **CSV Loaded**\n\nUse /done to process",
            parse_mode='Markdown'
        )
    
    async def handle_json(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle JSON file"""
        user_id = update.effective_user.id
        document = update.message.document
        
        # Download JSON
        file = await context.bot.get_file(document.file_id)
        json_path = config.TEMP_DIR / f"json_{user_id}_{document.file_id}.json"
        await file.download_to_drive(json_path)
        
        # Load JSON (simplified - implement full JSON loading)
        await update.message.reply_text(
            "📋 **JSON Loaded**\n\nUse /done to process",
            parse_mode='Markdown'
        )
    
    @require_auth
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads"""
        user_id = update.effective_user.id
        
        # Get largest photo
        photo = update.message.photo[-1]
        
        # Download photo
        file = await context.bot.get_file(photo.file_id)
        photo_path = config.TEMP_DIR / f"photo_{user_id}_{photo.file_id}.jpg"
        await file.download_to_drive(photo_path)
        
        # Initialize or append to user state
        if user_id not in self.user_states:
            self.user_states[user_id] = {'photos': []}
        
        if 'photos' not in self.user_states[user_id]:
            self.user_states[user_id]['photos'] = []
        
        self.user_states[user_id]['photos'].append(photo_path)
        
        count = len(self.user_states[user_id]['photos'])
        
        keyboard = [
            [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
            [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
        ]
        
        await update.message.reply_text(
            f"📸 **Photo {count} Received**\n\n"
            f"Send more or choose mode:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ==================== QUEUE PROCESSING ====================
    
    async def add_to_queue_direct(self, user_id: int, page_range, context):
        """Add task to queue"""
        state = self.user_states.get(user_id)
        if not state:
            return
        
        task_queue.add_task(user_id, state, context)
        
        position = task_queue.get_queue_position(user_id)
        await context.bot.send_message(
            user_id,
            f"📋 **Task Queued**\n\nPosition: {position}",
            parse_mode='Markdown'
        )
    
    async def process_queued_task(self, user_id: int, state: dict, context):
        """Process queued task"""
        try:
            # Get content paths
            if 'pdf_path' in state:
                content_paths = [state['pdf_path']]
                content_type = 'pdf'
            elif 'photos' in state:
                content_paths = state['photos']
                content_type = 'images'
            else:
                return
            
            page_range = state.get('page_range')
            mode = state.get('mode', 'extraction')
            
            # Process content
            from bot.content_processor import ContentProcessor
            processor = ContentProcessor(self)
            
            await processor.process_content(
                user_id, content_type, content_paths,
                page_range, mode, context
            )
            
        except Exception as e:
            print(f"❌ Task processing error: {e}")
            import traceback
            traceback.print_exc()
