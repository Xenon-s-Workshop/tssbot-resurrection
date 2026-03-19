"""Live Quiz Manager"""
import asyncio
from telegram.ext import ContextTypes

class LiveQuizManager:
    def __init__(self):
        self.sessions = {}
        self.scores = {}
        print("✅ Live Quiz Manager initialized")
    
    def create_session(self, chat_id, questions, time_per_question, custom_message):
        """Create quiz session"""
        session_id = f"live_{chat_id}_{len(self.sessions)}"
        
        self.sessions[session_id] = {
            'chat_id': chat_id,
            'questions': questions,
            'time_per_question': time_per_question,
            'custom_message': custom_message,
            'current_index': 0
        }
        
        self.scores[session_id] = {}
        
        return session_id
    
    async def run_quiz(self, session_id, context: ContextTypes.DEFAULT_TYPE):
        """Run live quiz"""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        chat_id = session['chat_id']
        questions = session['questions']
        
        # Send custom message
        if session['custom_message']:
            await context.bot.send_message(chat_id, session['custom_message'])
        
        # Send questions
        for idx, q in enumerate(questions):
            await self.send_question(session_id, idx, context)
            await asyncio.sleep(session['time_per_question'])
        
        # Send results
        await self.finish_quiz(session_id, context)
    
    async def send_question(self, session_id, index, context):
        """Send question as poll"""
        session = self.sessions[session_id]
        q = session['questions'][index]
        
        poll = await context.bot.send_poll(
            chat_id=session['chat_id'],
            question=f"[{index+1}/{len(session['questions'])}] {q['question_description']}",
            options=q['options'],
            type='quiz',
            correct_option_id=q['correct_answer_index'],
            is_anonymous=False
        )
        
        # Store poll_id
        if 'poll_ids' not in session:
            session['poll_ids'] = {}
        session['poll_ids'][poll.poll.id] = index
    
    async def handle_poll_answer(self, update, context):
        """Handle poll answer"""
        answer = update.poll_answer
        user_id = answer.user.id
        
        # Find session
        for session_id, session in self.sessions.items():
            if 'poll_ids' in session and answer.poll_id in session['poll_ids']:
                question_idx = session['poll_ids'][answer.poll_id]
                question = session['questions'][question_idx]
                
                if user_id not in self.scores[session_id]:
                    self.scores[session_id][user_id] = 0
                
                if len(answer.option_ids) > 0:
                    if answer.option_ids[0] == question['correct_answer_index']:
                        self.scores[session_id][user_id] += 1
    
    async def finish_quiz(self, session_id, context):
        """Send leaderboard"""
        session = self.sessions[session_id]
        scores = self.scores.get(session_id, {})
        
        if not scores:
            await context.bot.send_message(session['chat_id'], "No participants!")
            return
        
        # Sort scores
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        leaderboard = "🏆 **Leaderboard**\n\n"
        
        for rank, (user_id, score) in enumerate(sorted_scores[:15], 1):
            try:
                user = await context.bot.get_chat(user_id)
                name = user.first_name
            except:
                name = f"User {user_id}"
            
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            leaderboard += f"{medal} {name}: {score}\n"
        
        await context.bot.send_message(
            session['chat_id'],
            leaderboard,
            parse_mode='Markdown'
        )
        
        # Cleanup
        del self.sessions[session_id]
        del self.scores[session_id]

live_quiz_manager = LiveQuizManager()
