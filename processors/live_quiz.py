"""
Live Quiz System - WITH LEADERBOARD
Sequential quiz posting with real-time scoring and automatic winner announcement
"""

import asyncio
import re
from datetime import datetime
from typing import List, Dict, Optional
from telegram import Update, Poll
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

class LiveQuizManager:
    def __init__(self):
        self.quiz_sessions = {}  # {session_id: session_data}
        self.active_locks = {}  # {chat_id: asyncio.Lock}
        print("✅ Live Quiz Manager initialized")
    
    # ==================== SESSION MANAGEMENT ====================
    
    def create_session(
        self,
        chat_id: int,
        questions: List[Dict],
        time_per_question: int,
        custom_message: str = None
    ) -> str:
        """Create new quiz session"""
        session_id = f"{chat_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        self.quiz_sessions[session_id] = {
            'chat_id': chat_id,
            'questions': questions,
            'user_scores': {},  # {user_id: score_data}
            'current_question': 0,
            'time_per_question': time_per_question,
            'start_time': datetime.utcnow(),
            'custom_message': custom_message,
            'lock': self.active_locks.setdefault(str(chat_id), asyncio.Lock())
        }
        
        print(f"✅ Created quiz session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data"""
        return self.quiz_sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """Delete session"""
        if session_id in self.quiz_sessions:
            del self.quiz_sessions[session_id]
            print(f"🗑️ Deleted quiz session: {session_id}")
    
    # ==================== QUIZ EXECUTION ====================
    
    async def run_quiz(self, session_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Run complete quiz sequence"""
        session = self.get_session(session_id)
        if not session:
            return
        
        # Use lock to ensure sequential posting
        async with session['lock']:
            total = len(session['questions'])
            
            # Send custom message if provided
            if session['custom_message']:
                try:
                    await context.bot.send_message(
                        chat_id=session['chat_id'],
                        text=session['custom_message']
                    )
                    await asyncio.sleep(2)  # Pause after announcement
                except Exception as e:
                    print(f"⚠️ Could not send custom message: {e}")
            
            # Post questions sequentially
            while session['current_question'] < total:
                await self.send_question(session_id, context)
                await asyncio.sleep(session['time_per_question'] + 1)
                session['current_question'] += 1
            
            # Send final leaderboard
            await self.finish_quiz(session_id, context)
    
    async def send_question(self, session_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Send single quiz question"""
        session = self.get_session(session_id)
        if not session:
            return
        
        idx = session['current_question']
        total = len(session['questions'])
        q = session['questions'][idx]
        
        # Format question with progress
        header = f"[{idx+1}/{total}] "
        question_text = header + q['question_description']
        
        # Format options
        options = []
        for i, opt in enumerate(q['options']):
            if opt:  # Skip empty options
                options.append(opt)
        
        if len(options) < 2:
            print(f"⚠️ Question {idx+1} has less than 2 options, skipping")
            return
        
        # Find correct answer index
        correct_letter = q.get('correct_option', 'A')
        correct_idx = ord(correct_letter) - ord('A')
        
        # Adjust if option was removed
        if correct_idx >= len(options):
            correct_idx = 0
        
        # Format explanation
        explanation = q.get('explanation', '')
        if explanation and len(explanation) > 200:
            explanation = explanation[:197] + "..."
        
        # Send poll
        try:
            msg = await context.bot.send_poll(
                chat_id=session['chat_id'],
                question=question_text,
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_idx,
                is_anonymous=False,
                open_period=session['time_per_question'],
                explanation=explanation
            )
            
            # Store poll info for answer tracking
            poll_id = msg.poll.id
            context.bot_data[poll_id] = {
                'session_id': session_id,
                'correct_idx': correct_idx,
                'correct_letter': correct_letter
            }
            
            print(f"✅ Sent question {idx+1}/{total}")
            
        except Exception as e:
            print(f"❌ Error sending question {idx+1}: {e}")
    
    async def handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle poll answer for scoring"""
        answer = update.poll_answer
        poll_data = context.bot_data.get(answer.poll_id)
        
        if not poll_data:
            return
        
        session = self.get_session(poll_data['session_id'])
        if not session:
            return
        
        user = answer.user
        selected_idx = answer.option_ids[0] if answer.option_ids else None
        
        if selected_idx is None:
            return
        
        # Check if correct
        is_correct = (selected_idx == poll_data['correct_idx'])
        
        # Update score
        user_scores = session['user_scores'].setdefault(user.id, {
            'name': user.full_name,
            'username': user.username or "",
            'correct': 0,
            'wrong': 0,
            'score': 0.0
        })
        
        if is_correct:
            user_scores['correct'] += 1
            user_scores['score'] += 1.0
        else:
            user_scores['wrong'] += 1
            user_scores['score'] -= 0.25
        
        print(f"📊 {user.full_name}: {'✓' if is_correct else '✗'} Score: {user_scores['score']:.2f}")
    
    async def finish_quiz(self, session_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Send final leaderboard"""
        session = self.quiz_sessions.pop(session_id, None)
        if not session:
            return
        
        chat_id = session['chat_id']
        scores = list(session['user_scores'].values())
        scores.sort(key=lambda x: (x['score'], x['correct']), reverse=True)
        
        total_q = len(session['questions'])
        duration = datetime.utcnow() - session['start_time']
        mins, secs = divmod(int(duration.total_seconds()), 60)
        
        # Build leaderboard message
        lines = [
            "*🏁 Quiz Finished\\!*",
            f"*Questions:* {total_q}",
            f"*Duration:* {mins}m {secs}s",
            f"*Participants:* {len(scores)}",
            "",
            "*🏆 Leaderboard 🏆*",
            ""
        ]
        
        if not scores:
            lines.append("_No participants_")
        else:
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(scores[:15]):
                if i < 3:
                    rank = medals[i]
                else:
                    rank = f"{i+1}\\."
                
                # Escape username/name for MarkdownV2
                name = p['username'] and f"@{p['username']}" or p['name']
                name = self._escape_markdown(name)
                
                lines.append(f"{rank} *{name}*")
                
                score_str = f"{p['score']:.2f}".replace('.', '\\.').replace('-', '\\-')
                lines.append(f"   Score: {score_str} \\(✓{p['correct']} ✗{p['wrong']}\\)")
                lines.append("")
        
        text = "\n".join(lines)
        
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            print(f"❌ Error sending leaderboard: {e}")
    
    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape characters for MarkdownV2"""
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# Global instance
live_quiz_manager = LiveQuizManager()
