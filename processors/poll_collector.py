"""
Poll Collector - FIXED VERSION
Proper state management, auto-delete, live updates
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
        return user_id in self.sessions and self.sessions[user_id].get('active', False)
    
    def start_collection(self, user_id: int):
        self.sessions[user_id] = {'polls': [], 'active': True, 'started_at': datetime.now()}
        print(f"📮 Started collection for user {user_id}")
    
    def stop_collection(self, user_id: int):
        if user_id in self.sessions:
            count = len(self.sessions[user_id].get('polls', []))
            del self.sessions[user_id]
            print(f"❌ Stopped collection for user {user_id} ({count} polls)")
            return count
        return 0
    
    def add_poll(self, user_id: int, poll: Poll) -> int:
        if not self.is_collecting(user_id):
            return 0
        
        options = [opt.text for opt in poll.options]
        correct_index = poll.correct_option_id if poll.type == 'quiz' and poll.correct_option_id is not None else -1
        
        self.sessions[user_id]['polls'].append({
            'question': poll.question,
            'options': options,
            'correct_index': correct_index,
            'explanation': poll.explanation or ''
        })
        
        count = len(self.sessions[user_id]['polls'])
        print(f"📊 User {user_id} collected poll #{count}")
        return count
    
    def get_polls(self, user_id: int) -> List[Dict]:
        return self.sessions.get(user_id, {}).get('polls', [])
    
    def clear_polls(self, user_id: int):
        if user_id in self.sessions:
            self.sessions[user_id]['polls'] = []
    
    def set_status_message(self, user_id: int, message_id: int):
        if user_id in self.sessions:
            self.sessions[user_id]['status_msg_id'] = message_id
    
    def get_status_message(self, user_id: int) -> int:
        return self.sessions.get(user_id, {}).get('status_msg_id')
    
    @staticmethod
    def cleanup_text(text: str) -> str:
        if not text:
            return text
        text = re.sub(r'\[[^\]]+\]', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        return re.sub(r'\s+', ' ', text).strip()
    
    def cleanup_polls(self, polls: List[Dict]) -> List[Dict]:
        return [{
            'question': self.cleanup_text(p['question']),
            'options': [self.cleanup_text(opt) for opt in p['options']],
            'correct_index': p['correct_index'],
            'explanation': self.cleanup_text(p['explanation'])
        } for p in polls]
    
    # ==================== HANDLERS ====================
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if self.is_collecting(user_id):
            count = len(self.get_polls(user_id))
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
                f"🗑️ Forwarded polls auto-deleted",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            self.start_collection(user_id)
            keyboard = [[InlineKeyboardButton("❌ Stop", callback_data="poll_stop")]]
            msg = await update.message.reply_text(
                "📮 *Poll Collection Started!*\n\n"
                "📊 Collected: 0 polls\n\n"
                "✅ Forward or send polls to me\n"
                "🗑️ Polls will be auto-deleted\n"
                "📈 Counter updates live",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            self.set_status_message(user_id, msg.message_id)
    
    async def handle_poll_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.is_collecting(user_id):
            return
        
        poll = update.message.poll if update.message else None
        if not poll:
            return
        
        count = self.add_poll(user_id, poll)
        
        # Delete forwarded message
        try:
            await update.message.delete()
            print(f"🗑️ Deleted poll message for user {user_id}")
        except Exception as e:
            print(f"⚠️ Could not delete: {e}")
        
        # Update status
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
                    text=f"📮 *Collection Active!*\n\n"
                         f"📊 Collected: {count} polls\n\n"
                         f"✅ Keep forwarding\n"
                         f"🗑️ Auto-deleting polls\n"
                         f"📈 Live updates",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"⚠️ Could not update status: {e}")
    
    async def handle_export_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        polls = self.get_polls(user_id)
        if not polls:
            await query.answer("❌ No polls!")
            return
        
        cleaned = self.cleanup_polls(polls)
        questions = [{
            'question_description': p['question'],
            'options': p['options'],
            'correct_answer_index': p['correct_index'],
            'explanation': p['explanation']
        } for p in cleaned]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = config.OUTPUT_DIR / f"polls_{user_id}_{timestamp}.csv"
        CSVGenerator.questions_to_csv(questions, csv_path)
        
        with open(csv_path, 'rb') as f:
            await context.bot.send_document(
                user_id, f, filename=f"polls_{timestamp}.csv",
                caption=f"📊 CSV Export\n\nTotal: {len(polls)} polls\n✨ Cleaned",
                parse_mode='Markdown'
            )
        
        csv_path.unlink(missing_ok=True)
        await query.answer("✅ CSV sent!")
        await query.edit_message_text(
            f"✅ *Export Complete!*\n\n📊 Exported: {len(polls)} polls\n\n"
            f"Collection still active.\nUse /collectpolls to manage.",
            parse_mode='Markdown'
        )
    
    async def handle_export_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        polls = self.get_polls(user_id)
        if not polls:
            await query.answer("❌ No polls!")
            return
        
        cleaned = self.cleanup_polls(polls)
        questions = [{
            'question_description': p['question'],
            'options': p['options'],
            'correct_answer_index': p['correct_index'],
            'correct_option': chr(65 + p['correct_index']) if p['correct_index'] >= 0 else 'A',
            'explanation': p['explanation']
        } for p in cleaned]
        
        from processors.pdf_exporter import pdf_exporter
        await pdf_exporter.handle_pdf_export_start(update, context, questions)
    
    async def handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        self.clear_polls(user_id)
        keyboard = [[InlineKeyboardButton("❌ Stop", callback_data="poll_stop")]]
        await query.answer("🗑️ Cleared!")
        await query.edit_message_text(
            "🗑️ *Polls Cleared!*\n\n📊 Collected: 0 polls\n\nStart forwarding again!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        count = self.stop_collection(user_id)
        await query.answer("❌ Stopped!")
        await query.edit_message_text(
            f"❌ *Collection Stopped*\n\n📊 Final: {count} polls\n\n"
            f"Use /collectpolls to start again.",
            parse_mode='Markdown'
        )

poll_collector = PollCollector()
