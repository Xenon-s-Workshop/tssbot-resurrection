"""
Bot Callbacks - COMPLETE WITH ALL FIXES
- Export PDF button handler
- Default destination support
- Debloated messages
- Settings management
"""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from processors.poll_collector import poll_collector
from processors.pdf_exporter import pdf_exporter
from processors.live_quiz import live_quiz_manager
from config import config

class CallbackHandlers:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers
        self.custom_message_sessions = {}
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main callback router"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data
        
        print(f"🔘 Callback: {data}")
        
        # ==================== POLL COLLECTION ====================
        if data == "poll_export_csv":
            await poll_collector.handle_export_csv(update, context)
        
        elif data == "poll_export_pdf":
            await poll_collector.handle_export_pdf(update, context)
        
        elif data == "poll_clear":
            await poll_collector.handle_clear(update, context)
        
        elif data == "poll_stop":
            await poll_collector.handle_stop(update, context)
        
        # ==================== PAGE RANGE ====================
        elif data == "pages_all":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired")
                return
            
            keyboard = [
                [InlineKeyboardButton("📤 Extraction", callback_data="mode_extraction")],
                [InlineKeyboardButton("✨ Generation", callback_data="mode_generation")]
            ]
            await query.edit_message_text(
                "📄 All pages\n\nChoose mode:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "pages_custom":
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired")
                return
            
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'page_range'
            await query.edit_message_text(
                "🔢 **Page Range**\n\n"
                "Format: `5-15`",
                parse_mode='Markdown'
            )
        
        # ==================== MODE SELECTION ====================
        elif data.startswith("mode_"):
            mode = data.split("_")[1]
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired")
                return
            
            self.bot_handlers.user_states[user_id]['mode'] = mode
            await query.edit_message_text("⏳ Queuing...")
            
            page_range = self.bot_handlers.user_states[user_id].get('page_range')
            await self.bot_handlers.add_to_queue_direct(user_id, page_range, context)
        
        # ==================== PDF EXPORT ====================
        elif data.startswith("export_pdf_"):
            session_id = data.split("_", 2)[2]
            
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired")
                return
            
            questions = self.bot_handlers.user_states[user_id].get('questions', [])
            if not questions:
                await query.answer("❌ No questions")
                return
            
            await query.edit_message_text("📄 Generating PDF...")
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_title = f"Quiz_{timestamp}"
            pdf_path = config.OUTPUT_DIR / f"{pdf_title}.pdf"
            
            try:
                cleaned = pdf_exporter.cleanup_questions(questions)
                pdf_exporter.generate_beautiful_pdf(cleaned, pdf_path, pdf_title)
                
                with open(pdf_path, 'rb') as f:
                    await context.bot.send_document(
                        user_id, f,
                        filename=f"{pdf_title}.pdf",
                        caption=f"📄 PDF • {len(questions)}Q"
                    )
                
                await query.message.delete()
                pdf_path.unlink(missing_ok=True)
                
            except Exception as e:
                await query.edit_message_text(f"❌ PDF failed: `{str(e)[:150]}`", parse_mode='Markdown')
        
        # ==================== LIVE QUIZ ====================
        elif data.startswith("livequiz_"):
            session_id = data.split("_", 1)[1]
            
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
        
        elif data.startswith("livequiz_skip_"):
            if user_id not in self.custom_message_sessions:
                await query.answer("❌ Expired")
                return
            
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
        
        # ==================== QUIZ POSTING ====================
        elif data.startswith("post_"):
            session_id = data.split("_", 1)[1]
            
            if user_id not in self.bot_handlers.user_states:
                await query.edit_message_text("❌ Session expired")
                return
            
            channels = db.get_user_channels(user_id)
            groups = db.get_user_groups(user_id)
            
            if not channels and not groups:
                await query.edit_message_text("❌ No destinations. Use /settings")
                return
            
            self.custom_message_sessions[user_id] = {
                'session_id': session_id,
                'waiting_for': 'custom_message',
                'quiz_type': 'post'
            }
            
            keyboard = [[InlineKeyboardButton("⏭️ Skip", callback_data=f"post_skip_{session_id}")]]
            
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                user_id,
                "📢 **Post Setup**\n\nSend announcement or skip.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("post_skip_"):
            session_id = data.split("_", 2)[2]
            
            if user_id in self.custom_message_sessions:
                self.custom_message_sessions[user_id]['custom_message'] = None
            
            try:
                await query.message.delete()
            except:
                pass
            
            await self._send_destination_selection(user_id, context)
        
        elif data.startswith("dest_ch_"):
            channel_id = int(data.split("_")[-1])
            
            custom_msg = None
            if user_id in self.custom_message_sessions:
                custom_msg = self.custom_message_sessions.pop(user_id).get('custom_message')
            
            msg = await context.bot.send_message(user_id, "📺 Posting...")
            
            from bot.content_processor import ContentProcessor
            processor = ContentProcessor(self.bot_handlers)
            await processor.post_quizzes_to_destination(
                user_id, channel_id, None, context, msg, custom_msg
            )
        
        elif data.startswith("dest_gr_"):
            group_id = int(data.split("_")[-1])
            
            self.bot_handlers.user_states[user_id]['selected_group'] = group_id
            self.bot_handlers.user_states[user_id]['waiting_for'] = 'topic_id'
            
            if user_id in self.custom_message_sessions:
                session_data = self.custom_message_sessions.pop(user_id)
                self.bot_handlers.user_states[user_id]['custom_message'] = session_data.get('custom_message')
            
            await context.bot.send_message(
                user_id,
                "🔢 **Topic ID**\n\nSend topic ID or 0:",
                parse_mode='Markdown'
            )
        
        # ==================== SETTINGS ====================
        elif data == "settings_add_channel":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_channel'}
            await query.edit_message_text(
                "📺 **Add Channel**\n\n"
                "Format: `id name`\n"
                "Example: `-1001234567890 My Channel`",
                parse_mode='Markdown'
            )
        
        elif data == "settings_add_group":
            self.bot_handlers.user_states[user_id] = {'waiting_for': 'add_group'}
            await query.edit_message_text(
                "👥 **Add Group**\n\n"
                "Format: `id name`\n"
                "Example: `-1001234567890 My Group`",
                parse_mode='Markdown'
            )
        
        elif data == "settings_manage_channels":
            channels = db.get_user_channels(user_id)
            default_ch = db.get_default_channel(user_id)
            
            if not channels:
                await query.edit_message_text("❌ No channels")
                return
            
            keyboard = []
            for ch in channels:
                prefix = "⭐ " if ch['channel_id'] == default_ch else ""
                keyboard.append([
                    InlineKeyboardButton(
                        f"{prefix}{ch['channel_name']}", 
                        callback_data=f"ch_menu_{ch['_id']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
            
            await query.edit_message_text(
                "📺 **Channels**\n⭐ = Default",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "settings_manage_groups":
            groups = db.get_user_groups(user_id)
            default_gr = db.get_default_group(user_id)
            
            if not groups:
                await query.edit_message_text("❌ No groups")
                return
            
            keyboard = []
            for gr in groups:
                prefix = "⭐ " if gr['group_id'] == default_gr else ""
                keyboard.append([
                    InlineKeyboardButton(
                        f"{prefix}{gr['group_name']}", 
                        callback_data=f"gr_menu_{gr['_id']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_back")])
            
            await query.edit_message_text(
                "👥 **Groups**\n⭐ = Default",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("ch_menu_"):
            from bson.objectid import ObjectId
            ch_id = data.split("_")[-1]
            channel = db.db.channels.find_one({'_id': ObjectId(ch_id)})
            
            if not channel:
                await query.answer("❌ Not found")
                return
            
            default_ch = db.get_default_channel(user_id)
            is_default = (channel['channel_id'] == default_ch)
            
            keyboard = []
            if not is_default:
                keyboard.append([InlineKeyboardButton("⭐ Set Default", callback_data=f"ch_default_{ch_id}")])
            else:
                keyboard.append([InlineKeyboardButton("✖️ Clear Default", callback_data=f"ch_undefault_{ch_id}")])
            keyboard.append([InlineKeyboardButton("❌ Delete", callback_data=f"del_ch_{ch_id}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_manage_channels")])
            
            await query.edit_message_text(
                f"📺 **{channel['channel_name']}**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("ch_default_"):
            from bson.objectid import ObjectId
            ch_id = data.split("_")[-1]
            channel = db.db.channels.find_one({'_id': ObjectId(ch_id)})
            
            db.set_default_channel(user_id, channel['channel_id'])
            await query.answer("⭐ Set as default")
            await query.edit_message_text(f"⭐ **{channel['channel_name']}** is default", parse_mode='Markdown')
        
        elif data.startswith("ch_undefault_"):
            db.clear_default_channel(user_id)
            await query.answer("✖️ Default cleared")
            await query.edit_message_text("✖️ Default cleared")
        
        elif data.startswith("gr_menu_"):
            from bson.objectid import ObjectId
            gr_id = data.split("_")[-1]
            group = db.db.groups.find_one({'_id': ObjectId(gr_id)})
            
            if not group:
                await query.answer("❌ Not found")
                return
            
            default_gr = db.get_default_group(user_id)
            is_default = (group['group_id'] == default_gr)
            
            keyboard = []
            if not is_default:
                keyboard.append([InlineKeyboardButton("⭐ Set Default", callback_data=f"gr_default_{gr_id}")])
            else:
                keyboard.append([InlineKeyboardButton("✖️ Clear Default", callback_data=f"gr_undefault_{gr_id}")])
            keyboard.append([InlineKeyboardButton("❌ Delete", callback_data=f"del_gr_{gr_id}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="settings_manage_groups")])
            
            await query.edit_message_text(
                f"👥 **{group['group_name']}**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("gr_default_"):
            from bson.objectid import ObjectId
            gr_id = data.split("_")[-1]
            group = db.db.groups.find_one({'_id': ObjectId(gr_id)})
            
            db.set_default_group(user_id, group['group_id'])
            await query.answer("⭐ Set as default")
            await query.edit_message_text(f"⭐ **{group['group_name']}** is default", parse_mode='Markdown')
        
        elif data.startswith("gr_undefault_"):
            db.clear_default_group(user_id)
            await query.answer("✖️ Default cleared")
            await query.edit_message_text("✖️ Default cleared")
        
        elif data.startswith("del_ch_"):
            db.delete_channel(data[7:])
            await query.answer("✅ Deleted")
            await query.message.delete()
        
        elif data.startswith("del_gr_"):
            db.delete_group(data[7:])
            await query.answer("✅ Deleted")
            await query.message.delete()
        
        elif data == "settings_back":
            keyboard = [
                [InlineKeyboardButton("➕ Add Channel", callback_data="settings_add_channel")],
                [InlineKeyboardButton("➕ Add Group", callback_data="settings_add_group")],
                [InlineKeyboardButton("📺 Channels", callback_data="settings_manage_channels")],
                [InlineKeyboardButton("👥 Groups", callback_data="settings_manage_groups")]
            ]
            await query.edit_message_text("⚙️ **Settings**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    # ==================== TEXT HANDLER ====================
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        print(f"📝 Text: {text[:50]}...")
        
        # Custom message
        if user_id in self.custom_message_sessions:
            session_data = self.custom_message_sessions[user_id]
            
            if session_data.get('waiting_for') == 'custom_message':
                session_data['custom_message'] = text
                session_data['waiting_for'] = None
                
                if session_data['quiz_type'] == 'live':
                    questions = session_data['questions']
                    
                    quiz_session_id = live_quiz_manager.create_session(
                        update.effective_chat.id,
                        questions,
                        10,
                        text
                    )
                    
                    self.custom_message_sessions.pop(user_id)
                    
                    await update.message.reply_text(
                        f"✅ **Live Quiz**\n\n{len(questions)}Q • 10s each",
                        parse_mode='Markdown'
                    )
                    
                    asyncio.create_task(live_quiz_manager.run_quiz(quiz_session_id, context))
                
                else:
                    await update.message.reply_text("✅ Message set")
                    await self._send_destination_selection(user_id, context)
                
                return
        
        # PDF name
        if pdf_exporter.is_waiting_for_name(user_id):
            await pdf_exporter.handle_pdf_name_input(update, context)
            return
        
        if user_id not in self.bot_handlers.user_states:
            return
        
        waiting_for = self.bot_handlers.user_states[user_id].get('waiting_for')
        
        # Page range
        if waiting_for == 'page_range':
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
                    f"✅ Pages {start}-{end}\n\nMode:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text("❌ Format: `5-15`", parse_mode='Markdown')
        
        # Settings
        elif waiting_for == 'add_channel':
            try:
                parts = text.split(" ", 1)
                if len(parts) < 2:
                    await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
                    return
                
                db.add_channel(user_id, int(parts[0]), parts[1])
                await update.message.reply_text("✅ Channel added")
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid ID")
        
        elif waiting_for == 'add_group':
            try:
                parts = text.split(" ", 1)
                if len(parts) < 2:
                    await update.message.reply_text("❌ Format: `id name`", parse_mode='Markdown')
                    return
                
                db.add_group(user_id, int(parts[0]), parts[1])
                await update.message.reply_text("✅ Group added")
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid ID")
        
        # Topic ID
        elif waiting_for == 'topic_id':
            try:
                topic_id = int(text)
                group_id = self.bot_handlers.user_states[user_id]['selected_group']
                custom_msg = self.bot_handlers.user_states[user_id].get('custom_message')
                thread_id = topic_id if topic_id > 0 else None
                
                msg = await update.message.reply_text("👥 Posting...")
                
                from bot.content_processor import ContentProcessor
                processor = ContentProcessor(self.bot_handlers)
                await processor.post_quizzes_to_destination(
                    user_id, group_id, thread_id, context, msg, custom_msg
                )
                
                del self.bot_handlers.user_states[user_id]
            except:
                await update.message.reply_text("❌ Invalid topic ID")
    
    async def _send_destination_selection(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Send destination menu"""
        channels = db.get_user_channels(user_id)
        groups = db.get_user_groups(user_id)
        
        if not channels and not groups:
            await context.bot.send_message(user_id, "❌ No destinations. Use /settings")
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
            "📢 **Destination:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
