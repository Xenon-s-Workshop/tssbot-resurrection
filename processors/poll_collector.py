"""
Poll Collector - COMPLETE REWRITE with BATCH PROCESSING
Based on reference implementation with auto-delete and live progress
"""

import re
import asyncio
from typing import List, Dict
from datetime import datetime
from telegram import Update, Poll, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from processors.csv_processor import CSVGenerator
from config import config

class PollCollector:
    def __init__(self):
        self.sessions = {}  # {user_id: session_data}
        self.MAX_POLLS = 200
        self.BATCH_DELAY = 2  # Wait 2 seconds before processing batch
        print("✅ Poll Collector initialized with batch processing")
    
    # ==================== SESSION MANAGEMENT ====================
    
    def is_collecting(self, user_id: int) -> bool:
        """Check if user has active collection session"""
        return user_id in self.sessions and self.sessions[user_id].get('is_collecting', False)
    
    def start_collection(self, user_id: int, filename: str = None):
        """Start collecting polls for user"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"polls_{timestamp}.csv"
        
        self.sessions[user_id] = {
            'is_collecting': True,
            'polls': [],
            'pending_polls': [],  # Batch queue
            'filename': filename,
            'started_at': datetime.now(),
            'status_msg_id': None,
            'processing_task': None,
            'chat_id': None
        }
        print(f"📮 Started collection for user {user_id}")
    
    def stop_collection(self, user_id: int) -> int:
        """Stop collecting and return count"""
        if user_id in self.sessions:
            # Cancel pending task
            session = self.sessions[user_id]
            if session.get('processing_task') and not session['processing_task'].done():
                session['processing_task'].cancel()
            
            count = len(session.get('polls', []))
            del self.sessions[user_id]
            print(f"❌ Stopped collection for user {user_id} ({count} polls)")
            return count
        return 0
    
    def add_poll_to_batch(self, user_id: int, poll: Poll, message_obj) -> bool:
        """Add poll to pending batch"""
        if not self.is_collecting(user_id):
            return False
        
        session = self.sessions[user_id]
        
        # Check limit
        if len(session['polls']) >= self.MAX_POLLS:
            return False
        
        # Extract poll data
        poll_data = self._extract_poll_data(poll)
        if not poll_data:
            return False
        
        # Add to pending batch
        session['pending_polls'].append({
            'data': poll_data,
            'message': message_obj
        })
        
        return True
    
    def set_status_message(self, user_id: int, message_id: int, chat_id: int):
        """Store status message info"""
        if user_id in self.sessions:
            self.sessions[user_id]['status_msg_id'] = message_id
            self.sessions[user_id]['chat_id'] = chat_id
    
    # ==================== DATA EXTRACTION ====================
    
    def _extract_poll_data(self, poll: Poll) -> Dict:
        """Extract and clean poll data"""
        if not poll:
            return None
        
        # Get question and options
        question = self._cleanup_text(poll.question) or "Unknown Question"
        options = [self._cleanup_text(opt.text) if opt.text else "" for opt in poll.options]
        
        # Pad to 5 options
        while len(options) < 5:
            options.append('')
        
        # Get correct answer (1-indexed)
        correct_answer = ''
        if poll.correct_option_id is not None:
            correct_answer = str(poll.correct_option_id + 1)
        else:
            return None  # Skip polls without correct answer
        
        # Get explanation
        explanation = self._cleanup_text(poll.explanation) if poll.explanation else ''
        
        return {
            'questions': question,
            'option1': options[0],
            'option2': options[1],
            'option3': options[2],
            'option4': options[3],
            'option5': options[4],
            'answer': correct_answer,
            'explanation': explanation,
            'type': '1',
            'section': '1'
        }
    
    @staticmethod
    def _cleanup_text(text: str) -> str:
        """Remove tags, links, and clean whitespace"""
        if not text:
            return ''
        
        # Remove question numbers
        text = re.sub(r'^\d+[.\)]\s*', '', text)
        text = re.sub(r'^[০১২৩৪৫৬৭৮৯]+[।)]\s*', '', text)
        text = re.sub(r'^\(\d+\)\s*', '', text)
        
        # Remove brackets and tags
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\{.*?\}', '', text)
        text = re.sub(r'【.*?】', '', text)
        
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        text = re.sub(r't\.me/\S+', '', text)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'^\s*[-•·*]\s*', '', text)
        
        return text.strip()
    
    # ==================== BATCH PROCESSING ====================
    
    async def process_pending_batch(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Process pending polls in batch after delay"""
        session = self.sessions.get(user_id)
        if not session:
            return
        
        # Wait for batch to accumulate
        await asyncio.sleep(self.BATCH_DELAY)
        
        pending = session['pending_polls']
        if not pending:
            return
        
        # Process all pending polls
        last_question = None
        for item in pending:
            if len(session['polls']) >= self.MAX_POLLS:
                break
            
            session['polls'].append(item['data'])
            last_question = item['data']['questions']
            
            # Delete the message
            try:
                await item['message'].delete()
            except Exception as e:
                print(f"⚠️ Could not delete poll: {e}")
        
        # Clear pending
        session['pending_polls'] = []
        
        # Update progress
        await self._update_progress_message(user_id, last_question, context)
    
    async def _update_progress_message(self, user_id: int, last_question: str, context: ContextTypes.DEFAULT_TYPE):
        """Update or send progress message"""
        session = self.sessions.get(user_id)
        if not session:
            return
        
        count = len(session['polls'])
        progress_bar = self._create_progress_bar(count, self.MAX_POLLS)
        
        # Format last question preview
        last_q_text = ""
        if last_question:
            preview = last_question[:60] + "..." if len(last_question) > 60 else last_question
            last_q_text = f"\n📝 **Last Question:** {preview}\n"
        
        text = (
            f"✅ **Polls processed: {count}/{self.MAX_POLLS}**\n"
            f"{progress_bar}\n"
            f"{last_q_text}\n"
            f"Send more polls or use `/done` to finish."
        )
        
        # Update or create message
        if session['status_msg_id'] and session['chat_id']:
            try:
                await context.bot.edit_message_text(
                    chat_id=session['chat_id'],
                    message_id=session['status_msg_id'],
                    text=text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                # If edit fails, send new message
                print(f"⚠️ Could not edit message: {e}")
                msg = await context.bot.send_message(
                    session['chat_id'],
                    text,
                    parse_mode='Markdown'
                )
                session['status_msg_id'] = msg.message_id
        
        # Send max warning
        if count >= self.MAX_POLLS:
            await context.bot.send_message(
                session['chat_id'],
                f"🎉 **Maximum polls collected!** ({self.MAX_POLLS})\nUse `/done` to generate CSV.",
                parse_mode='Markdown'
            )
    
    @staticmethod
    def _create_progress_bar(current: int, total: int, length: int = 10) -> str:
        """Create visual progress bar"""
        filled = int(length * current / total) if total else 0
        filled = max(0, min(length, filled))
        bar = '█' * filled + '░' * (length - filled)
        percentage = (current / total) * 100 if total else 0
        return f"[{bar}] {percentage:.1f}%"
    
    # ==================== COMMAND HANDLERS ====================
    
    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /collectpolls command"""
        user_id = update.effective_user.id
        
        if self.is_collecting(user_id):
            # Already collecting - show status
            count = len(self.sessions[user_id]['polls'])
            keyboard = [
                [InlineKeyboardButton("📊 Export CSV", callback_data="poll_export_csv")],
                [InlineKeyboardButton("📄 Export PDF", callback_data="poll_export_pdf")],
                [InlineKeyboardButton("🗑️ Clear All", callback_data="poll_clear")],
                [InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]
            ]
            await update.message.reply_text(
                f"📮 **Poll Collection Active**\n\n"
                f"📊 Collected: **{count}** polls\n\n"
                f"✅ Forward or send polls to me\n"
                f"🗑️ Forwarded polls auto-delete\n"
                f"📈 Progress updates live every 2s",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            # Start new collection
            self.start_collection(user_id)
            
            keyboard = [[InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]]
            
            msg = await update.message.reply_text(
                "📮 **Poll Collection Started!**\n\n"
                "📊 Collected: **0** polls\n\n"
                "✅ Now forward or send polls to me\n"
                "🗑️ Forwarded polls auto-delete\n"
                "📈 Counter updates live\n\n"
                "💡 **Tip:** Just forward polls from any chat!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            self.set_status_message(user_id, msg.message_id, update.effective_chat.id)
    
    async def handle_poll_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming poll - ADD TO BATCH"""
        user_id = update.effective_user.id
        
        if not self.is_collecting(user_id):
            print(f"⚠️ User {user_id} sent poll but not collecting")
            return
        
        poll = update.message.poll if update.message else update.poll
        if not poll:
            return
        
        session = self.sessions[user_id]
        
        # Add to batch
        if self.add_poll_to_batch(user_id, poll, update.message):
            print(f"📥 Added poll to batch for user {user_id}: {poll.question[:50]}...")
            
            # Start or restart processing task
            if session.get('processing_task') is None or session['processing_task'].done():
                session['processing_task'] = asyncio.create_task(
                    self.process_pending_batch(user_id, context)
                )
        else:
            print(f"⚠️ Could not add poll for user {user_id}")
    
    async def handle_export_csv(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export to CSV"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.sessions.get(user_id)
        if not session or not session['polls']:
            await query.answer("❌ No polls collected!")
            return
        
        await query.answer("📊 Generating CSV...")
        
        # Generate CSV
        import tempfile
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = session['filename']
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv', encoding='utf-8') as tmp:
            CSVGenerator.questions_to_csv(session['polls'], tmp.name)
            
            with open(tmp.name, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=filename,
                    caption=f"📊 **CSV Export Complete!**\n\n"
                            f"📝 Total polls: **{len(session['polls'])}**\n"
                            f"✨ Cleaned and formatted\n\n"
                            f"Collection still active!",
                    parse_mode='Markdown'
                )
        
        import os
        os.unlink(tmp.name)
        
        await query.edit_message_text(
            f"✅ **CSV Exported!**\n\n"
            f"📊 Exported: **{len(session['polls'])}** polls\n\n"
            f"Collection still active.\nUse /collectpolls to manage.",
            parse_mode='Markdown'
        )
    
    async def handle_export_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export to PDF"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.sessions.get(user_id)
        if not session or not session['polls']:
            await query.answer("❌ No polls collected!")
            return
        
        await query.answer("📄 Preparing PDF export...")
        
        # Convert to questions format
        questions = []
        for p in session['polls']:
            questions.append({
                'question_description': p['questions'],
                'options': [p['option1'], p['option2'], p['option3'], p['option4'], p['option5']],
                'correct_answer_index': int(p['answer']) - 1 if p['answer'] else 0,
                'correct_option': chr(65 + (int(p['answer']) - 1)) if p['answer'] else 'A',
                'explanation': p['explanation']
            })
        
        # Start PDF export
        from processors.pdf_exporter import pdf_exporter
        await pdf_exporter.handle_pdf_export_start(update, context, questions)
    
    async def handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear all polls"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        session = self.sessions.get(user_id)
        if session:
            session['polls'] = []
            session['pending_polls'] = []
        
        keyboard = [[InlineKeyboardButton("❌ Stop Collection", callback_data="poll_stop")]]
        
        await query.answer("🗑️ All polls cleared!")
        await query.edit_message_text(
            "🗑️ **All Polls Cleared!**\n\n"
            "📊 Collected: **0** polls\n\n"
            "✅ Ready to collect again\n"
            "💡 Forward polls to start collecting!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop collection"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        count = self.stop_collection(user_id)
        
        await query.answer("❌ Collection stopped!")
        await query.edit_message_text(
            f"❌ **Collection Stopped**\n\n"
            f"📊 Final count: **{count}** polls\n\n"
            f"✅ Use /collectpolls to start again",
            parse_mode='Markdown'
        )

# Global instance
poll_collector = PollCollector()
