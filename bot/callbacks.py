"""
Bot Callbacks - COMPLETE HANDLER
Handles all button callbacks including live quiz, poll collection, settings
"""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from processors.poll_collector import poll_collector
from processors.pdf_exporter import pdf_exporter
from processors.live_quiz import live_quiz_manager

class CallbackHandlers:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers
        self.custom_message_sessions = {}  # {user_id: {session_id, waiting, custom_message}}
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main callback router"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data
        
        print(f"🔘 Callback from user {user_id}: {data}")
        
        # ==================== POLL COLLECTION ====================
        if data == "poll_export_csv":
            await poll_collector.handle_export_csv(update, context)
        
        elif data == "poll_export_pdf":
            await poll_collector.handle_export_pdf(update, context)
        
        elif data == "poll_clear":
            await poll_collector.handle_clear(update, context)
        
        elif data == "poll_stop":
            await poll_collector.handle_stop(update, context)
        
        # ==================== PAGE RANGE SELECTION ====================
        elif data == "pages_all":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            
            keyboard = [
                [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
            ]
            await query.edit_message_text(
                "📄 *All Pages Selected*\n\nChoose mode:",
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
                "Format: `5-15`\n"
                "Example: `1-10`",
                parse_mode='Markdown'
            )
        
        # ==================== MODE SELECTION ====================
        elif data.startswith("mode_"):
            mode = data.split("_")[1]
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            
            self.bot_handlers.user_states[user_id]['mode'] = mode
            await query.edit_message_text(f"✅ Mode: {mode}\n⏳ Adding to queue...")
            
            page_range = self.bot_handlers.user_states[user_id].get('page_range')
            await self.bot_handlers.add_to_queue_direct(user_id, page_range, context)
        
        # ==================== PDF EXPORT ====================
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
        
        # ==================== LIVE QUIZ ====================
        elif data.startswith("livequiz_"):
            session_id = data.split("_", 1)[1]
            
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            
            questions = self.bot_handlers.user_states[user_id].get('questions', [])
            if not questions:
                await query.answer("❌ No questions!")
                return
            
            # Store session for custom message
            self.custom_message_sessions[user_id] = {
                'session_id': session_id,
                'waiting_for': 'custom_message',
                'questions': questions,
                'quiz_type': 'live'
            }
            
            keyboard = [[InlineKeyboardButton("⏭️ Skip Message", callback_data=f"livequiz_skip_{session_id}")]]
            
            # Delete old message and send new one
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                user_id,
                "🎯 *Live Quiz Setup*\n\n"
                "📝 Send a custom announcement message\n"
                "or skip to start immediately.\n\n"
                "💡 Example: \"Chemistry Final Exam Starting!\"",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("livequiz_skip_"):
            # Start live quiz without custom message
            if user_id not in self.custom_message_sessions:
                await query.answer("❌ Session expired!")
                return
            
            session_data = self.custom_message_sessions.pop(user_id)
            questions = session_data['questions']
            
            # Delete old message
            try:
                await query.message.delete()
            except:
                pass
            
            # Create and run quiz
            quiz_session_id = live_quiz_manager.create_session(
                update.effective_chat.id,
                questions,
                10,  # Default time
                None  # No custom message
            )
            
            await context.bot.send_message(
                user_id,
                f"✅ *Live Quiz Started!*\n\n"
                f"📊 Questions: {len(questions)}\n"
                f"⏱️ Time: 10s each\n\n"
                f"Watch the chat for questions!",
                parse_mode='Markdown'
            )
            
            # Run quiz
            asyncio.create_task(live_quiz_manager.run_quiz(quiz_session_id, context))
        
        # ==================== QUIZ POSTING ====================
        elif data.startswith("post_"):
            session_id = data.split("_", 1)[1]
            
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired.")
                return
            
            channels = db.get_user_channels(user_id)
            groups = db.get_user_groups(user_id)
            
            if not channels and not groups:
                await query.edit_message_text("❌ No destinations. Use /settings")
                return
            
            # Store session for custom message
            self.custom_message_sessions[user_id] = {
                'session_id': session_id,
                'waiting_for': 'custom_message',
                'quiz_type': 'post'
            }
            
            keyboard = [[InlineKeyboardButton("⏭️ Skip Message", callback_data=f"post_skip_{session_id}")]]
            
            # Delete old message and send new one
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                user_id,
                "📢 *Quiz Posting Setup*\n\n"
                "📝 Send a custom announcement message\n"
                "or skip to post without message.\n\n"
                "💡 Example: \"Daily Practice Quiz!\"",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("post_skip_"):
            # Show destination selection without custom message
            session_id = data.split("_", 2)[2]
            
            if user_id in self.custom_message_sessions:
                self.custom_message_sessions[user_id]['custom_message'] = None
            
            # Delete old message
            try:
                await query.message.delete()
            except:
                pass
            
            # Send fresh destination selection
            await self._send_destination_selection(user_id, context)
        
        elif data.startswith("dest_ch_"):
            channel_id = int(data.split("_")[-1])
            
            # Get custom message if exists
            custom_msg = None
            if user_id in self.custom_message_sessions:
                custom_msg = self.custom_message_sessions.pop(user_id).get('custom_message')
            
            # Send posting status
            msg = await context.bot.send_message(user_id, "📺 Posting to channel...")
            
            from bot.content_processor import ContentProcessor
            processor = ContentProcessor(self.bot_handlers)
            await processor.post_quizzes_to_destination(
                user_id, channel_id, None, context, msg, custom_msg
            )
        
        elif data.startswith("dest_gr_"):
            group_id = int(data.split("_")[-1])
            
            # Store for topic ID input
            self.bot_handlers.user_states[user_id]['selected_group'] = group_id
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'topic_id'
            
            # Store custom message
            if user_id in self.custom_message_sessions:
                session_data = self.custom_message_sessions.pop(user_id)
                self.bot_handlers.user_states[user_id]['custom_message'] = session_data.get('custom_message')
            
            await context.bot.send_message(
                user_id,
                "🔢 *Topic ID*\n\n"
                "Send topic ID or 0 for none:",
                parse_mode='Markdown'
            )
        
        # ==================== SETTINGS ====================
        elif data == "settings_add_channel":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_channel'}
            await query.edit_message_text(
                "📺 *Add Channel*\n\n"
                "Send: `channel_id channel_name`\n\n"
                "Example: `-1001234567890 My Channel`",
                parse_mode='Markdown'
            )
        
        elif data == "settings_add_group":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_group'}
            await query.edit_message_text(
                "👥 *Add Group*\n\n"
                "Send: `group_id group_name`\n\n"
                "Example: `-1001234567890 My Group`",
                parse_mode='Markdown'
            )
        
        elif data == "settings_manage_channels":
            channels = db.get_user_channels(user_id)
            if not channels:
                await query.edit_message_text("❌ No channels.")
                return
            
            keyboard = [
                [InlineKeyboardButton(f"❌ {ch['channel_name']}", callback_data=f"del_ch_{ch['_id']}")]
                for ch in channels
            ]
            await query.edit_message_text(
                "📺 *Manage Channels*",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "settings_manage_groups":
            groups = db.get_user_groups(user_id)
            if not groups:
                await query.edit_message_text("❌ No groups.")
                return
            
            keyboard = [
                [InlineKeyboardButton(f"❌ {gr['group_name']}", callback_data=f"del_gr_{gr['_id']}")]
                for gr in groups
            ]
            await query.edit_message_text(
                "👥 *Manage Groups*",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data.startswith("del_ch_"):
            db.delete_channel(data[7:])
            await query.answer("✅ Channel deleted!")
            await query.message.delete()
        
        elif data.startswith("del_gr_"):
            db.delete_group(data[7:])
            await query.answer("✅ Group deleted!")
            await query.message.delete()
    
    # ==================== TEXT INPUT HANDLER ====================
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for various waiting states"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        print(f"📝 Text received from user {user_id}: {text[:50]}...")
        
        # ==================== CUSTOM MESSAGE FOR QUIZ/LIVE QUIZ ====================
        if user_id in self.custom_message_sessions:
            session_data = self.custom_message_sessions[user_id]
            
            print(f"📋 Session data: waiting_for={session_data.get('waiting_for')}, type={session_data.get('quiz_type')}")
            
            if session_data.get('waiting_for') == 'custom_message':
                # Store custom message
                session_data['custom_message'] = text
                session_data['waiting_for'] = None
                
                print(f"✅ Stored custom message: {text[:50]}...")
                
                if session_data['quiz_type'] == 'live':
                    # Start live quiz with custom message
                    questions = session_data['questions']
                    
                    quiz_session_id = live_quiz_manager.create_session(
                        update.effective_chat.id,
                        questions,
                        10,  # Default time
                        text  # Custom message
                    )
                    
                    self.custom_message_sessions.pop(user_id)
                    
                    await update.message.reply_text(
                        f"✅ *Live Quiz Started!*\n\n"
                        f"📊 Questions: {len(questions)}\n"
                        f"⏱️ Time: 10s each\n"
                        f"📝 Message: \"{text[:50]}{'...' if len(text) > 50 else ''}\"\n\n"
                        f"Watch the chat!",
                        parse_mode='Markdown'
                    )
                    
                    # Run quiz
                    asyncio.create_task(live_quiz_manager.run_quiz(quiz_session_id, context))
                
                else:  # Regular post
                    print(f"📢 Showing destination selection for regular post...")
                    
                    await update.message.reply_text(
                        f"✅ *Custom message set:*\n\n"
                        f"\"{text[:100]}{'...' if len(text) > 100 else ''}\"\n\n"
                        f"Selecting destination...",
                        parse_mode='Markdown'
                    )
                    
                    # Show destination selection
                    await self._send_destination_selection(user_id, context)
                
                return
        
        # ==================== PDF NAME INPUT ====================
        if pdf_exporter.is_waiting_for_name(user_id):
            print(f"📄 PDF name input from user {user_id}")
            await pdf_exporter.handle_pdf_name_input(update, context)
            return
        
        # ==================== REGULAR STATE HANDLING ====================
        if user_id not in self.bot_handlers.user_states:
            print(f"⚠️ No state for user {user_id}, ignoring text")
            return
        
        waiting_for = self.bot_handlers.user_states[user_id].get('waiting_for')
        print(f"📋 User state waiting_for: {waiting_for}")
        
        # ==================== PAGE RANGE INPUT ====================
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
                await update.message.reply_text(
                    f"✅ Pages {start}-{end}\n\nChoose mode:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                print(f"❌ Page range error: {e}")
                await update.message.reply_text("❌ Format: `5-15`", parse_mode='Markdown')
        
        # ==================== SETTINGS INPUT ====================
        elif waiting_for == 'add_channel':
            try:
                parts = text.split(" ", 1)
                if len(parts) < 2:
                    await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
                    return
                
                db.add_channel(user_id, int(parts[0]), parts[1])
                await update.message.reply_text("✅ Channel added!")
                del self.bot_handlers.user_states[user_id]
            except Exception as e:
                print(f"❌ Add channel error: {e}")
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
            except Exception as e:
                print(f"❌ Add group error: {e}")
                await update.message.reply_text("❌ Invalid ID.")
        
        # ==================== TOPIC ID INPUT ====================
        elif waiting_for == 'topic_id':
            try:
                topic_id = int(text)
                group_id = self.bot_handlers.user_states[user_id]['selected_group']
                custom_msg = self.bot_handlers.user_states[user_id].get('custom_message')
                thread_id = topic_id if topic_id > 0 else None
                
                msg = await update.message.reply_text("👥 Posting to group...")
                
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.post_quizzes_to_destination(
                    user_id, group_id, thread_id, context, msg, custom_msg
                )
                
                del self.bot_handlers.user_states[user_id]
            except Exception as e:
                print(f"❌ Topic ID error: {e}")
                await update.message.reply_text("❌ Invalid topic ID.")
        
        else:
            print(f"⚠️ Unknown waiting_for state: {waiting_for}")
    
    # ==================== HELPER METHODS ====================
    
    async def _send_destination_selection(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Send destination selection menu (fresh message)"""
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        
        if not channels and not groups:
            await context.bot.send_message(
                user_id,
                "❌ No destinations configured.\nUse /settings to add channels or groups."
            )
            self.custom_message_sessions.pop(user_id, None)
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
            "📢 *Select Destination:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
