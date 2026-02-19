"""
Poll Collector - COMPLETELY FIXED
- Proper state management with sessions dict
- Auto-delete of forwarded polls works
- Live counter updates correctly
- Clean export to CSV/PDF
"""

import re
from typing import List, Dict
from datetime import datetime
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from processors.csv_processor import CSVGenerator
from config import config

class PollCollector:
    """Fixed poll collection with proper state management"""
    
    def __init__(self):
        # Session structure: {user_id: {'polls': [], 'status_msg_id': int, 'active': bool}}
        self.sessions = {}
        print("✅ Poll Collector initialized")
    
    def is_collecting(self, user_id: int) -> bool:
        """Check if user has active collection"""
        return user_id in self.sessions and self.sessions[user_id].get('active', False)
    
    def start_collection(self, user_id: int):
        """Start new collection session"""
        self.sessions[user_id] = {
            'polls': [],
            'active': True,
            'started_at': datetime.now()
        }
        print(f"📮 Started collection for user {user_id}")
    
    def stop_collection(self, user_id: int):
        """Stop collection and cleanup"""
        if user_id in self.sessions:
            count = len(self.sessions[user_id].get('polls', []))
            del self.sessions[user_id]
            print(f"❌ Stopped collection for user {user_id} (collected: {count})")
            return count
        return 0
    
    def add_poll(self, user_id: int, poll: Poll) -> int:
        """Add poll to collection, return total count"""
        if not self.is_collecting(user_id):
            return 0
        
        # Extract poll data
        options = [opt.text for opt in poll.options]
        correct_index = -1
        
        if poll.type == 'quiz' and poll.correct_option_id is not None:
            correct_index = poll.correct_option_id
        
        poll_data = {
            'question': poll.question,
            'options': options,
            'correct_index': correct_index,
            'explanation': poll.explanation or ''
        }
        
        self.sessions[user_id]['polls'].append(poll_data)
        count = len(self.sessions[user_id]['polls'])
        print(f"📊 User {user_id} collected poll #{count}")
        return count
    
    def get_count(self, user_id: int) -> int:
        """Get poll count"""
        return len(self.sessions.get(user_id, {}).get('polls', []))
    
    def get_polls(self, user_id: int) -> List[Dict]:
        """Get all collected polls"""
        return self.sessions.get(user_id, {}).get('polls', [])
    
    def clear_polls(self, user_id: int):
        """Clear polls but keep session active"""
        if user_id in self.sessions:
            self.sessions[user_id]['polls'] = []
            print(f"🗑️ Cleared polls for user {user_id}")
    
    def set_status_message(self, user_id: int, message_id: int):
        """Save status message ID for updates"""
        if user_id in self.sessions:
            self.sessions[user_id]['status_msg_id'] = message_id
    
    def get_status_message(self, user_id: int) -> int:
        """Get status message ID"""
        return self.sessions.get(user_id, {}).get('status_msg_id')
    
    @staticmethod
    def cleanup_text(text: str) -> str:
        """Remove [tags] and links"""
        if not text:
            return text
        # Remove [anything]
        text = re.sub(r'\[[^\]]+\]', '', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        # Clean spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def cleanup_polls(self, polls: List[Dict]) -> List[Dict]:
        """Clean all polls"""
        cleaned = []
        for p in polls:
            cleaned.append({
                'question': self.cleanup_text(p.get('question', '')),
                'options': [self.cleanup_text(opt) for opt in p.get('options', [])],
                'correct_index': p.get('correct_index', -1),
                'explanation': self.cleanup_text(p.get('explanation', ''))
            })
        return cleaned
    
    # ==================== HANDLERS ====================
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /collectpolls command"""
        user_id = update.effective_user.id
        
        if self.is_collecting(user_id):
            # Already active - show status
            count = self.get_count(user_id)
            keyboard = [
                [InlineKeyboardButton("📊 Export CSV", callback_data="poll_export_csv")],
                [InlineKeyboardButton("📄 Export PDF", callback_data="poll_export_pdf")],
                [InlineKeyboardButton("🗑️ Clear", callback_data="poll_clear")],
                [InlineKeyboardButton("❌ Stop", callback_data="poll_stop")]
            ]
            await update.message.reply_text(
                f"📮 *Poll Collection Active*\n\n"
                f"📊 Collected: {count} polls\n\n"
                f"✅ Forward or send polls\n"
                f"🗑️ Forwarded polls auto-deleted\n\n"
                f"Use buttons to manage:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # Start new collection
            self.start_collection(user_id)
            keyboard = [[InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]]
            msg = await update.message.reply_text(
                f"📮 *Poll Collection Started!*\n\n"
                f"📊 Collected: 0 polls\n\n"
                f"✅ Forward or send polls to me\n"
                f"🗑️ Polls will be auto-deleted\n"
                f"📈 Counter updates live\n\n"
                f"Keep forwarding polls!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            self.set_status_message(user_id, msg.message_id)
    
    async def handle_poll_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming poll - FIXED with proper delete"""
        user_id = update.effective_user.id
        
        # Check if collecting
        if not self.is_collecting(user_id):
            return
        
        # Get poll
        poll = update.message.poll if update.message else update.poll
        if not poll:
            return
        
        # Add to collection
        count = self.add_poll(user_id, poll)
        
        # DELETE THE FORWARDED MESSAGE - CRITICAL FIX
        try:
            await update.message.delete()
            print(f"🗑️ Deleted poll message for user {user_id}")
        except Exception as e:
            print(f"⚠️ Could not delete message for user {user_id}: {e}")
        
        # UPDATE STATUS MESSAGE
        status_msg_id = self.get_status_message(user_id)
        if status_msg_id:
            try:
                keyboard = [
                    [InlineKeyboardButton("📊 Export CSV", callback_data="poll_export_csv")],
                    [InlineKeyboardButton("📄 Export PDF", callback_data="poll_export_pdf")],
                    [InlineKeyboardButton("🗑️ Clear", callback_data="poll_clear")],
                    [InlineKeyboardButton("❌ Stop", callback_data="poll_stop")]
                ]
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_msg_id,
                    text=f"📮 *Poll Collection Active!*\n\n"
                         f"📊 Collected: {count} polls\n\n"
                         f"✅ Keep forwarding polls\n"
                         f"🗑️ Auto-deleting forwarded polls\n"
                         f"📈 Live counter updating\n\n"
                         f"Click buttons when done!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                print(f"✅ Updated status message for user {user_id} (count: {count})")
            except Exception as e:
                print(f"⚠️ Could not update status for user {user_id}: {e}")
    
    async def handle_export_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export to CSV with cleanup"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        polls = self.get_polls(user_id)
        if not polls:
            await query.answer("❌ No polls collected!")
            return
        
        # Clean polls
        cleaned_polls = self.cleanup_polls(polls)
        
        # Convert to question format
        questions = [
            {
                'question_description': p['question'],
                'options': p['options'],
                'correct_answer_index': p['correct_index'],
                'explanation': p['explanation']
            }
            for p in cleaned_polls
        ]
        
        # Generate CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = config.OUTPUT_DIR / f"polls_{user_id}_{timestamp}.csv"
        CSVGenerator.questions_to_csv(questions, csv_path)
        
        # Send file
        with open(csv_path, 'rb') as f:
            await context.bot.send_document(
                user_id, f,
                filename=f"collected_polls_{timestamp}.csv",
                caption=f"📊 *CSV Export*\n\n"
                        f"Total: {len(polls)} polls\n"
                        f"✨ Cleaned (removed tags & links)\n"
                        f"Format: Standard CSV",
                parse_mode='Markdown'
            )
        
        csv_path.unlink(missing_ok=True)
        await query.answer("✅ CSV exported!")
        await query.edit_message_text(
            f"✅ *Export Complete!*\n\n"
            f"📊 Exported: {len(polls)} polls\n\n"
            f"Collection still active.\n"
            f"Use /collectpolls to manage.",
            parse_mode='Markdown'
        )
    
    async def handle_export_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export to PDF"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        polls = self.get_polls(user_id)
        if not polls:
            await query.answer("❌ No polls collected!")
            return
        
        # Clean and convert
        cleaned_polls = self.cleanup_polls(polls)
        questions = [
            {
                'question_description': p['question'],
                'options': p['options'],
                'correct_answer_index': p['correct_index'],
                'correct_option': chr(65 + p['correct_index']) if p['correct_index'] >= 0 else 'A',
                'explanation': p['explanation']
            }
            for p in cleaned_polls
        ]
        
        # Delegate to PDF exporter
        from processors.pdf_exporter import pdf_exporter
        await pdf_exporter.handle_pdf_export_start(update, context, questions)
    
    async def handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear polls"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        self.clear_polls(user_id)
        keyboard = [[InlineKeyboardButton("❌ Stop", callback_data="poll_stop")]]
        await query.answer("🗑️ Cleared!")
        await query.edit_message_text(
            "🗑️ *Polls Cleared!*\n\n"
            "📊 Collected: 0 polls\n\n"
            "Start forwarding again!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop collection"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        count = self.stop_collection(user_id)
        await query.answer("❌ Stopped!")
        await query.edit_message_text(
            f"❌ *Collection Stopped*\n\n"
            f"📊 Final: {count} polls\n\n"
            f"Use /collectpolls to start again.",
            parse_mode='Markdown'
        )

# Global instance
poll_collector = PollCollector()
