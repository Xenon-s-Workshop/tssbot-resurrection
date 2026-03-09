"""
Poll Collector - FULLY WORKING
Collects polls when forwarded/sent after /collectpolls command
"""

import re
from typing import List, Dict
from datetime import datetime
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from processors.csv_processor import CSVGenerator
from config import config

class PollCollector:
    def __init__(self):
        self.sessions = {}  # {user_id: {'polls': [], 'status_msg_id': int, 'active': bool}}
        print("✅ Poll Collector initialized")
    
    def is_collecting(self, user_id: int) -> bool:
        """Check if user has active collection session"""
        return user_id in self.sessions and self.sessions[user_id].get('active', False)
    
    def start_collection(self, user_id: int):
        """Start collecting polls for user"""
        self.sessions[user_id] = {
            'polls': [], 
            'active': True, 
            'started_at': datetime.now(),
            'status_msg_id': None
        }
        print(f"📮 Started collection for user {user_id}")
    
    def stop_collection(self, user_id: int):
        """Stop collecting and return count"""
        if user_id in self.sessions:
            count = len(self.sessions[user_id].get('polls', []))
            del self.sessions[user_id]
            print(f"❌ Stopped collection for user {user_id} ({count} polls)")
            return count
        return 0
    
    def add_poll(self, user_id: int, poll: Poll) -> int:
        """Add poll to collection and return total count"""
        if not self.is_collecting(user_id):
            print(f"⚠️ User {user_id} not collecting - ignoring poll")
            return 0
        
        # Extract poll data
        options = [opt.text for opt in poll.options]
        correct_index = poll.correct_option_id if poll.type == 'quiz' and poll.correct_option_id is not None else 0
        
        poll_data = {
            'question': poll.question,
            'options': options,
            'correct_index': correct_index,
            'correct_option': chr(65 + correct_index) if correct_index >= 0 else 'A',
            'explanation': poll.explanation or ''
        }
        
        self.sessions[user_id]['polls'].append(poll_data)
        count = len(self.sessions[user_id]['polls'])
        print(f"✅ User {user_id} collected poll #{count}: {poll.question[:50]}...")
        return count
    
    def get_polls(self, user_id: int) -> List[Dict]:
        """Get all collected polls for user"""
        return self.sessions.get(user_id, {}).get('polls', [])
    
    def clear_polls(self, user_id: int):
        """Clear all collected polls"""
        if user_id in self.sessions:
            self.sessions[user_id]['polls'] = []
            print(f"🗑️ Cleared polls for user {user_id}")
    
    def set_status_message(self, user_id: int, message_id: int):
        """Store status message ID for live updates"""
        if user_id in self.sessions:
            self.sessions[user_id]['status_msg_id'] = message_id
    
    def get_status_message(self, user_id: int) -> int:
        """Get status message ID"""
        return self.sessions.get(user_id, {}).get('status_msg_id')
    
    @staticmethod
    def cleanup_text(text: str) -> str:
        """Remove [tags] and links from text"""
        if not text:
            return text
        # Remove [tags]
        text = re.sub(r'\[[^\]]+\]', '', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        # Clean whitespace
        return re.sub(r'\s+', ' ', text).strip()
    
    def cleanup_polls(self, polls: List[Dict]) -> List[Dict]:
        """Clean all polls in list"""
        cleaned = []
        for p in polls:
            cleaned.append({
                'question_description': self.cleanup_text(p['question']),
                'options': [self.cleanup_text(opt) for opt in p['options']],
                'correct_answer_index': p['correct_index'],
                'correct_option': p['correct_option'],
                'explanation': self.cleanup_text(p['explanation'])
            })
        return cleaned
    
    # ==================== COMMAND HANDLER ====================
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /collectpolls command"""
        user_id = update.effective_user.id
        
        if self.is_collecting(user_id):
            # Already collecting - show status
            count = len(self.get_polls(user_id))
            keyboard = [
                [InlineKeyboardButton("📊 Export CSV", callback_data="poll_export_csv")],
                [InlineKeyboardButton("📄 Export PDF", callback_data="poll_export_pdf")],
                [InlineKeyboardButton("🗑️ Clear All", callback_data="poll_clear")],
                [InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]
            ]
            await update.message.reply_text(
                f"📮 *Poll Collection Active*\n\n"
                f"📊 Collected: *{count}* polls\n\n"
                f"✅ Forward or send polls to me\n"
                f"🗑️ Forwarded polls will auto-delete\n"
                f"📈 Live counter updates automatically",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # Start new collection
            self.start_collection(user_id)
            keyboard = [
                [InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]
            ]
            msg = await update.message.reply_text(
                "📮 *Poll Collection Started!*\n\n"
                "📊 Collected: *0* polls\n\n"
                "✅ Now forward or send polls to me\n"
                "🗑️ Forwarded polls auto-delete\n"
                "📈 Counter updates live\n\n"
                "💡 *Tip:* Just forward polls from any chat!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            self.set_status_message(user_id, msg.message_id)
            print(f"📮 User {user_id} started collection, status msg: {msg.message_id}")
    
    # ==================== POLL MESSAGE HANDLER ====================
    
    async def handle_poll_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming poll messages - THIS GETS CALLED WHEN USER SENDS/FORWARDS A POLL"""
        user_id = update.effective_user.id
        
        # Check if user is collecting
        if not self.is_collecting(user_id):
            print(f"⚠️ User {user_id} sent poll but not collecting - ignoring")
            return
        
        # Get poll from message
        poll = update.message.poll if update.message else update.poll
        if not poll:
            print(f"⚠️ No poll found in update from user {user_id}")
            return
        
        print(f"📥 Received poll from user {user_id}: {poll.question[:50]}...")
        
        # Add poll to collection
        count = self.add_poll(user_id, poll)
        
        # Delete the forwarded message
        try:
            await update.message.delete()
            print(f"🗑️ Deleted poll message for user {user_id}")
        except Exception as e:
            print(f"⚠️ Could not delete poll message: {e}")
        
        # Update status message with new count
        status_msg_id = self.get_status_message(user_id)
        if status_msg_id:
            try:
                keyboard = [
                    [InlineKeyboardButton("📊 Export CSV", callback_data="poll_export_csv")],
                    [InlineKeyboardButton("📄 Export PDF", callback_data="poll_export_pdf")],
                    [InlineKeyboardButton("🗑️ Clear All", callback_data="poll_clear")],
                    [InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]
                ]
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg_id,
                    text=f"📮 *Poll Collection Active!*\n\n"
                         f"📊 Collected: *{count}* polls\n\n"
                         f"✅ Keep forwarding polls\n"
                         f"🗑️ Auto-deleting as you send\n"
                         f"📈 Live counter active\n\n"
                         f"💡 Collection running smoothly!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                print(f"✅ Updated status message for user {user_id} - count: {count}")
            except Exception as e:
                print(f"⚠️ Could not update status message: {e}")
    
    # ==================== CALLBACK HANDLERS ====================
    
    async def handle_export_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export collected polls to CSV"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        polls = self.get_polls(user_id)
        if not polls:
            await query.answer("❌ No polls collected!")
            return
        
        await query.answer("📊 Generating CSV...")
        
        # Clean and convert to questions format
        cleaned = self.cleanup_polls(polls)
        
        # Generate CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = config.OUTPUT_DIR / f"polls_{user_id}_{timestamp}.csv"
        CSVGenerator.questions_to_csv(cleaned, csv_path)
        
        # Send CSV file
        with open(csv_path, 'rb') as f:
            await context.bot.send_document(
                user_id, f,
                filename=f"polls_{timestamp}.csv",
                caption=f"📊 *CSV Export Complete!*\n\n"
                        f"📝 Total polls: *{len(polls)}*\n"
                        f"✨ Text cleaned and formatted\n\n"
                        f"Collection still active!",
                parse_mode='Markdown'
            )
        
        # Cleanup
        csv_path.unlink(missing_ok=True)
        
        await query.edit_message_text(
            f"✅ *CSV Export Complete!*\n\n"
            f"📊 Exported: *{len(polls)}* polls\n\n"
            f"Collection still active.\nUse /collectpolls to manage.",
            parse_mode='Markdown'
        )
    
    async def handle_export_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export collected polls to PDF"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        polls = self.get_polls(user_id)
        if not polls:
            await query.answer("❌ No polls collected!")
            return
        
        await query.answer("📄 Preparing PDF export...")
        
        # Clean and convert to questions format
        cleaned = self.cleanup_polls(polls)
        
        # Import PDF exporter
        from processors.pdf_exporter import pdf_exporter
        
        # Start PDF export flow
        await pdf_exporter.handle_pdf_export_start(update, context, cleaned)
    
    async def handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear all collected polls"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        self.clear_polls(user_id)
        
        keyboard = [
            [InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]
        ]
        
        await query.answer("🗑️ All polls cleared!")
        await query.edit_message_text(
            "🗑️ *All Polls Cleared!*\n\n"
            "📊 Collected: *0* polls\n\n"
            "✅ Ready to collect again\n"
            "💡 Forward polls to start collecting!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop poll collection"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        count = self.stop_collection(user_id)
        
        await query.answer("❌ Collection stopped!")
        await query.edit_message_text(
            f"❌ *Collection Stopped*\n\n"
            f"📊 Final count: *{count}* polls\n\n"
            f"✅ Use /collectpolls to start again\n"
            f"💡 Your polls are saved until export!",
            parse_mode='Markdown'
        )

# Create global instance
poll_collector = PollCollector()
