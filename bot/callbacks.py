“””
Bot Callbacks - FIXED Posting Flow
Complete redesign with proper session management and settings UI
“””

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from processors.poll_collector import poll_collector
from processors.pdf_exporter import pdf_exporter
from processors.live_quiz import live_quiz_manager
from config import config

class CallbackHandlers:
def **init**(self, bot_handlers):
self.bot_handlers = bot_handlers
self.custom_message_sessions = {}
self.posting_sessions = {}  # Track active posting sessions

async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback router"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    print(f"🔘 Callback: {data} from user {user_id}")
    
    # Poll collection callbacks
    if data == "poll_export_csv":
        await poll_collector.handle_export_csv(update, context)
    elif data == "poll_export_pdf":
        await poll_collector.handle_export_pdf(update, context)
    elif data == "poll_clear":
        await poll_collector.handle_clear(update, context)
    elif data == "poll_stop":
        await poll_collector.handle_stop(update, context)
    
    # Page selection
    elif data == "pages_all":
        await self._handle_pages_all(update, context, user_id, query)
    elif data == "pages_custom":
        await self._handle_pages_custom(update, context, user_id, query)
    
    # Mode selection
    elif data.startswith("mode_"):
        await self._handle_mode_selection(update, context, user_id, query, data)
    
    # PDF export
    elif data.startswith("export_pdf_"):
        await self._handle_pdf_export(update, context, user_id, query, data)
    
    # Live quiz
    elif data.startswith("livequiz_"):
        await self._handle_livequiz(update, context, user_id, query, data)
    
    # POSTING FLOW - REDESIGNED
    elif data.startswith("post_"):
        await self._handle_post_start(update, context, user_id, query, data)
    
    # Settings
    elif data.startswith("settings_") or data == "start_settings":
        await self._handle_settings(update, context, user_id, query, data)
    
    # PDF mode selection
    elif data.startswith("pdf_mode"):
        await self._handle_pdf_mode(update, context, user_id, query, data)
    
    # Destination selection
    elif data.startswith("dest_"):
        await self._handle_destination(update, context, user_id, query, data)
    
    # Help callbacks
    elif data == "help_usage":
        await self._handle_help_usage(update, context, query)
    elif data == "help_about":
        await self._handle_help_about(update, context, query)

async def _handle_post_start(self, update, context, user_id, query, data):
    """Step 1: Ask for header message"""
    session_id = data.split("_", 1)[1]
    
    if user_id not in self.bot_handlers.user_states:
        await query.edit_message_text("❌ Session expired")
        return
    
    # Check if already posting
    if user_id in self.posting_sessions:
        await query.answer("⚠️ Already posting!")
        return
    
    # Initialize posting session
    self.posting_sessions[user_id] = {
        'session_id': session_id,
        'step': 'header',
        'custom_message': None,
        'destination': None
    }
    
    keyboard = [[InlineKeyboardButton("⏭️ Skip Header", callback_data=f"post_skip_{session_id}")]]
    
    # Delete old message
    try:
        await query.message.delete()
    except:
        pass
    
    # Send fresh message for header
    await context.bot.send_message(
        user_id,
        "📢 **Step 1/3: Header Message**\n\n"
        "Send your announcement message\n"
        "or click Skip to proceed.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def _handle_destination(self, update, context, user_id, query, data):
    """Step 3: Post to selected destination"""
    # Get session
    if user_id not in self.posting_sessions:
        await query.answer("❌ Session expired")
        return
    
    session = self.posting_sessions[user_id]
    custom_msg = session.get('custom_message')
    
    # Parse destination
    if data.startswith("dest_ch_"):
        chat_id = int(data.split("_")[-1])
        thread_id = None
        
        # Delete selection message IMMEDIATELY
        try:
            await query.message.delete()
        except:
            pass
        
        # Clear session to prevent re-click
        del self.posting_sessions[user_id]
        
        # Start posting
        msg = await context.bot.send_message(user_id, "📢 **Step 3/3: Posting...**")
        
        from bot.content_processor import ContentProcessor
        processor = ContentProcessor(self.bot_handlers)
        await processor.post_quizzes_to_destination(
            user_id, chat_id, thread_id, context, msg, custom_msg
        )
        
    elif data.startswith("dest_gr_"):
        group_id = int(data.split("_")[-1])
        # For groups, ask for topic ID
        session['selected_group'] = group_id
        session['step'] = 'topic_id'
        
        await query.edit_message_text(
            "🔢 **Step 3/3: Topic ID**\n\n"
            "Send topic ID or send 0 for main chat.",
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Invalid destination")

async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Check if waiting for header message
    if user_id in self.posting_sessions:
        session = self.posting_sessions[user_id]
        
        if session['step'] == 'header':
            # Save header message
            session['custom_message'] = text
            session['step'] = 'destination'
            
            await update.message.reply_text("✅ Header saved")
            await self._send_destination_selection(user_id, context)
            return
        
        elif session['step'] == 'topic_id':
            # Handle topic ID
            try:
                topic_id = int(text)
                group_id = session['selected_group']
                custom_msg = session.get('custom_message')
                thread_id = topic_id if topic_id > 0 else None
                
                # Clear session
                del self.posting_sessions[user_id]
                
                msg = await update.message.reply_text("📢 **Posting...**")
                
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.post_quizzes_to_destination(
                    user_id, group_id, thread_id, context, msg, custom_msg
                )
                return
            except:
                await update.message.reply_text("❌ Invalid topic ID")
                return
    
    # PDF name input
    if pdf_exporter.is_waiting_for_name(user_id):
        await pdf_exporter.handle_pdf_name_input(update, context)
        return
    
    # Settings text input
    if user_id in self.bot_handlers.user_states:
        waiting_for = self.bot_handlers.user_states[user_id].get('waiting_for')
        
        if waiting_for in ['quiz_marker', 'explanation_tag']:
            await self._handle_settings_text_input(update, context, user_id, text, waiting_for)
            return
    
    # Other text handlers (page range, channel/group addition, etc.)
    if user_id not in self.bot_handlers.user_states:
        return
    
    waiting_for = self.bot_handlers.user_states[user_id].get('waiting_for')
    
    if waiting_for == 'page_range':
        await self._handle_page_range_input(update, context, user_id, text)
    elif waiting_for == 'add_channel':
        await self._handle_add_channel_input(update, context, user_id, text)
    elif waiting_for == 'add_group':
        await self._handle_add_group_input(update, context, user_id, text)

async def _send_destination_selection(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send destination selection menu"""
    channels = db.get_user_channels(user_id)
    groups = db.get_user_groups(user_id)
    
    if not channels and not groups:
        await context.bot.send_message(
            user_id,
            "❌ **No Destinations**\n\nUse /settings to add channels/groups.",
            parse_mode='Markdown'
        )
        if user_id in self.posting_sessions:
            del self.posting_sessions[user_id]
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
    
    await context.bot.send_message(
        user_id,
        "📢 **Step 2/3: Select Destination**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== PAGE HANDLERS ====================

async def _handle_pages_all(self, update, context, user_id, query):
    if user_id not in self.bot_handlers.user_states:
        await query.edit_message_text("❌ Session expired")
        return
    
    keyboard = [
        [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
        [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
    ]
    await query.edit_message_text(
        "📄 **All Pages Selected**\n\nChoose processing mode:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def _handle_pages_custom(self, update, context, user_id, query):
    if user_id not in self.bot_handlers.user_states:
        await query.edit_message_text("❌ Session expired")
        return
    
    self.bot_handlers.user_states[user_id]['waiting_for'] = 'page_range'
    await query.edit_message_text(
        "🔢 **Page Range**\n\n"
        "Send page range (e.g., `5-15`)",
        parse_mode='Markdown'
    )

async def _handle_mode_selection(self, update, context, user_id, query, data):
    mode = data.split("_")[1]
    if user_id not in self.bot_handlers.user_states:
        await query.edit_message_text("❌ Session expired")
        return
    
    self.bot_handlers.user_states[user_id]['mode'] = mode
    await query.edit_message_text("⏳ **Queuing task...**")
    
    page_range = self.bot_handlers.user_states[user_id].get('page_range')
    await self.bot_handlers.add_to_queue_direct(user_id, page_range, context)

# ==================== PDF EXPORT ====================

async def _handle_pdf_export(self, update, context, user_id, query, data):
    session_id = data.split("_", 2)[2]
    
    if user_id not in self.bot_handlers.user_states:
        await query.edit_message_text("❌ Session expired")
        return
    
    questions = self.bot_handlers.user_states[user_id].get('questions', [])
    if not questions:
        await query.answer("❌ No questions")
        return
    
    await query.edit_message_text("📄 **Generating PDF...**")
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_title = f"Quiz_{timestamp}"
    pdf_path = config.OUTPUT_DIR / f"{pdf_title}.pdf"
    
    try:
        settings = db.get_user_settings(user_id)
        pdf_mode = settings.get('pdf_mode', 'mode1')
        
        cleaned = pdf_exporter.cleanup_questions(questions)
        pdf_exporter.generate_beautiful_pdf(cleaned, pdf_path, pdf_title, mode=pdf_mode)
        
        with open(pdf_path, 'rb') as f:
            await context.bot.send_document(
                user_id, f,
                filename=f"{pdf_title}.pdf",
                caption=f"📄 PDF • {len(questions)}Q • {pdf_mode}"
            )
        
        await query.message.delete()
        pdf_path.unlink(missing_ok=True)
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ **PDF Failed**\n\n`{str(e)[:150]}`",
            parse_mode='Markdown'
        )

# ==================== LIVE QUIZ ====================

async def _handle_livequiz(self, update, context, user_id, query, data):
    session_id = data.split("_", 1)[1]
    
    if "skip" in data:
        # Skip custom message
        if user_id in self.custom_message_sessions:
            session_data = self.custom_message_sessions.pop(user_id)
            questions = session_data['questions']
            
            try:
                await query.message.delete()
            except:
                pass
            
            quiz_session_id = live_quiz_manager.create_session(
                update.effective_chat.id,
                questions,
                10,
                None
            )
            
            await context.bot.send_message(
                user_id,
                f"✅ **Live Quiz**\n\n{len(questions)}Q • 10s each",
                parse_mode='Markdown'
            )
            
            asyncio.create_task(live_quiz_manager.run_quiz(quiz_session_id, context))
    else:
        # Start live quiz flow
        if user_id not in self.bot_handlers.user_states:
            await query.edit_message_text("❌ Session expired")
            return
        
        questions = self.bot_handlers.user_states[user_id].get('questions', [])
        if not questions:
            await query.answer("❌ No questions")
            return
        
        self.custom_message_sessions[user_id] = {
            'session_id': session_id,
            'waiting_for': 'custom_message',
            'questions': questions,
            'quiz_type': 'live'
        }
        
        keyboard = [[InlineKeyboardButton("⏭️ Skip", callback_data=f"livequiz_skip_{session_id}")]]
        
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            user_id,
            "🎯 **Live Quiz**\n\nSend announcement or skip.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ==================== SETTINGS HANDLERS ====================

async def _handle_settings(self, update, context, user_id, query, data):
    """Settings callback handler"""
    
    if data == "settings_main" or data == "start_settings" or data == "settings_manage_channels" or data == "settings_manage_groups":
        if data == "settings_main" or data == "start_settings":
            await self._show_settings_menu(update, context, user_id, query)
        elif data == "settings_manage_channels":
            channels = db.get_user_channels(user_id)
            if not channels:
                await query.edit_message_text(
                    "❌ **No Channels**\n\nAdd channels using /settings → Add Channel",
                    parse_mode='Markdown'
                )
                return
            
            keyboard = []
            for ch in channels:
                keyboard.append([InlineKeyboardButton(
                    f"📺 {ch['channel_name']}", 
                    callback_data=f"ch_view_{ch['_id']}"
                )])
            keyboard.append([InlineKeyboardButton("➕ Add Channel", callback_data="settings_add_channel")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_main")])
            
            await query.edit_message_text(
                "📺 **Your Channels**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        elif data == "settings_manage_groups":
            groups = db.get_user_groups(user_id)
            if not groups:
                await query.edit_message_text(
                    "❌ **No Groups**\n\nAdd groups using /settings → Add Group",
                    parse_mode='Markdown'
                )
                return
            
            keyboard = []
            for gr in groups:
                keyboard.append([InlineKeyboardButton(
                    f"👥 {gr['group_name']}", 
                    callback_data=f"gr_view_{gr['_id']}"
                )])
            keyboard.append([InlineKeyboardButton("➕ Add Group", callback_data="settings_add_group")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_main")])
            
            await query.edit_message_text(
                "👥 **Your Groups**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif data == "settings_quiz_marker":
        current_marker = db.get_user_settings(user_id).get('quiz_marker', '🎯 Quiz')
        self.bot_handlers.user_states[user_id] = {'waiting_for': 'quiz_marker'}
        await query.edit_message_text(
            f"🎯 **Quiz Marker**\n\n"
            f"Current: `{current_marker}`\n\n"
            f"Send new quiz marker text:",
            parse_mode='Markdown'
        )
    
    elif data == "settings_exp_tag":
        current_tag = db.get_user_settings(user_id).get('explanation_tag', 'Exp')
        self.bot_handlers.user_states[user_id] = {'waiting_for': 'explanation_tag'}
        await query.edit_message_text(
            f"📝 **Explanation Tag**\n\n"
            f"Current: `{current_tag}`\n\n"
            f"Send new explanation tag:",
            parse_mode='Markdown'
        )
    
    elif data == "settings_pdf_mode":
        keyboard = [
            [InlineKeyboardButton("📄 Mode 1: Answers at End", callback_data="pdf_mode1")],
            [InlineKeyboardButton("📝 Mode 2: Inline Answers", callback_data="pdf_mode2")],
            [InlineKeyboardButton("🔙 Back", callback_data="settings_main")]
        ]
        
        current_mode = db.get_user_settings(user_id).get('pdf_mode', 'mode1')
        
        await query.edit_message_text(
            f"📄 **PDF Mode**\n\n"
            f"Current: `{current_mode}`\n\n"
            f"**Mode 1:** Questions only, answers at end\n"
            f"**Mode 2:** Each question with inline answer\n\n"
            f"Select mode:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == "settings_add_channel":
        self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_channel'}
        await query.edit_message_text(
            "📺 **Add Channel**\n\n"
            "Format: `channel_id channel_name`\n"
            "Example: `-1001234567890 My Channel`",
            parse_mode='Markdown'
        )
    
    elif data == "settings_add_group":
        self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_group'}
        await query.edit_message_text(
            "👥 **Add Group**\n\n"
            "Format: `group_id group_name`\n"
            "Example: `-1001234567890 My Group`",
            parse_mode='Markdown'
        )

async def _handle_pdf_mode(self, update, context, user_id, query, data):
    """Handle PDF mode selection"""
    mode = "mode1" if data == "pdf_mode1" else "mode2"
    db.set_pdf_mode(user_id, mode)
    await query.answer(f"✅ PDF Mode set to {mode}")
    await self._show_settings_menu(update, context, user_id, query)

async def _show_settings_menu(self, update, context, user_id, query):
    """Show main settings menu"""
    settings = db.get_user_settings(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📺 Manage Channels", callback_data="settings_manage_channels")],
        [InlineKeyboardButton("👥 Manage Groups", callback_data="settings_manage_groups")],
        [InlineKeyboardButton("🎯 Quiz Marker", callback_data="settings_quiz_marker")],
        [InlineKeyboardButton("📝 Explanation Tag", callback_data="settings_exp_tag")],
        [InlineKeyboardButton("📄 PDF Mode", callback_data="settings_pdf_mode")],
    ]
    
    await query.edit_message_text(
        f"⚙️ **Settings**\n\n"
        f"**Current Configuration:**\n"
        f"• Quiz Marker: `{settings.get('quiz_marker', '🎯 Quiz')}`\n"
        f"• Explanation Tag: `{settings.get('explanation_tag', 'Exp')}`\n"
        f"• PDF Mode: `{settings.get('pdf_mode', 'mode1')}`\n\n"
        f"Select setting to modify:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== TEXT INPUT HANDLERS ====================

async def _handle_settings_text_input(self, update, context, user_id, text, waiting_for):
    """Handle settings text input"""
    
    if waiting_for == 'quiz_marker':
        db.set_quiz_marker(user_id, text)
        await update.message.reply_text(
            f"✅ **Quiz Marker Updated**\n\nNew: `{text}`",
            parse_mode='Markdown'
        )
        del self.bot_handlers.user_states[user_id]
    
    elif waiting_for == 'explanation_tag':
        db.set_explanation_tag(user_id, text)
        await update.message.reply_text(
            f"✅ **Explanation Tag Updated**\n\nNew: `{text}`",
            parse_mode='Markdown'
        )
        del self.bot_handlers.user_states[user_id]

async def _handle_page_range_input(self, update, context, user_id, text):
    try:
        if '-' not in text:
            await update.message.reply_text("❌ Format: `5-15`", parse_mode='Markdown')
            return
        
        parts = text.split('-')
        start, end = int(parts[0].strip()), int(parts[1].strip())
        
        if start < 1 or end < start:
            await update.message.reply_text("❌ Invalid range")
            return
        
        self.bot_handlers.user_states[user_id]['page_range'] = (start, end)
        self.bot_handlers.user_states[user_id]['waiting_for'] = None
        
        keyboard = [
            [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
            [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
        ]
        await update.message.reply_text(
            f"✅ **Pages {start}-{end}**\n\nChoose mode:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ Invalid format. Use: `5-15`", parse_mode='Markdown')

async def _handle_add_channel_input(self, update, context, user_id, text):
    try:
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
            return
        
        db.add_channel(user_id, int(parts[0]), parts[1])
        await update.message.reply_text("✅ **Channel Added**")
        del self.bot_handlers.user_states[user_id]
    except:
        await update.message.reply_text("❌ Invalid channel ID")

async def _handle_add_group_input(self, update, context, user_id, text):
    try:
        parts = text.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
            return
        
        db.add_group(user_id, int(parts[0]), parts[1])
        await update.message.reply_text("✅ **Group Added**")
        del self.bot_handlers.user_states[user_id]
    except:
        await update.message.reply_text("❌ Invalid group ID")

# ==================== HELP HANDLERS ====================

async def _handle_help_usage(self, update, context, query):
    """Show usage guide"""
    help_text = (
        "📚 **How to Use**\n\n"
        "1. Send PDF or images\n"
        "2. Choose extraction/generation\n"
        "3. Get CSV, JSON, PDF files\n"
        "4. Post to channel/group\n\n"
        "Use /help for full guide"
    )
    await query.edit_message_text(help_text, parse_mode='Markdown')

async def _handle_help_about(self, update, context, query):
    """Show about info"""
    about_text = (
        f"ℹ️ **About**\n\n"
        f"**{config.BOT_NAME}** v{config.BOT_VERSION}\n"
        f"AI-powered quiz generator\n\n"
        f"Model: {config.GEMINI_MODEL}\n\n"
        f"Features:\n"
        f"• Quiz extraction/generation\n"
        f"• Multiple export formats\n"
        f"• Channel/group posting\n"
        f"• Live quiz sessions\n"
        f"• Bengali support"
    )
    await query.edit_message_text(about_text, parse_mode='Markdown')
