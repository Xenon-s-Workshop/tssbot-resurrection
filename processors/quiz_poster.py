"""
Quiz Poster - WITH CANCELLATION & CORRECT COUNTER FORMAT
Posts quizzes and sends "?/200" counter to destination
"""

import asyncio
from typing import List, Dict, Optional
from telegram.ext import ContextTypes
from telegram.error import RetryAfter, TimedOut
from config import config

class QuizPoster:
    def __init__(self):
        self.active_postings = {}  # {user_id: {'cancel': bool}}
        print("✅ Quiz Poster initialized")
    
    @staticmethod
    def format_question(text: str, marker: str) -> str:
        """Format question with marker"""
        formatted = f"{marker}\n\n{text}"
        if len(formatted) > 300:
            formatted = f"{marker}\n\n{text[:300-len(marker)-6]}..."
        return formatted
    
    @staticmethod
    def format_explanation(explanation: str, tag: str) -> str:
        """Format explanation with tag"""
        if not explanation:
            return None
        formatted = f"{explanation} [{tag}]"
        if len(formatted) > 200:
            formatted = f"{explanation[:200-len(tag)-7]}... [{tag}]"
        return formatted
    
    @staticmethod
    async def send_quiz_with_retry(context, chat_id, question, marker, tag, thread_id=None, max_retries=3):
        """Send single quiz with retry logic"""
        for attempt in range(max_retries):
            try:
                opts = question.get('options', [])[:10]
                if len(opts) < 2:
                    return False
                
                correct_id = max(0, min(question.get('correct_answer_index', 0), len(opts) - 1))
                q = QuizPoster.format_question(question.get('question_description', ''), marker)
                e = QuizPoster.format_explanation(question.get('explanation', ''), tag)
                
                await context.bot.send_poll(
                    chat_id=chat_id,
                    question=q,
                    options=opts,
                    type='quiz',
                    correct_option_id=correct_id,
                    explanation=e,
                    is_anonymous=True,
                    message_thread_id=thread_id
                )
                return True
            except (RetryAfter, TimedOut):
                await asyncio.sleep(2)
            except Exception as e:
                print(f"⚠️ Quiz send error: {e}")
                return False
        return False
    
    async def post_quizzes_batch(
        self,
        context,
        chat_id,
        questions,
        marker,
        tag,
        thread_id=None,
        progress_callback=None,
        custom_message=None,
        user_id=None
    ):
        """
        Post quizzes with custom message
        Sends "?/total" counter to destination (e.g., "145/200")
        """
        total = len(questions)
        success = failed = skipped = 0
        
        # Register posting session
        if user_id:
            self.active_postings[user_id] = {'cancel': False}
        
        # Custom message is now sent and pinned in content_processor
        # Don't send it again here
        
        # Post quizzes
        for i in range(0, total, config.BATCH_SIZE):
            # Check for cancellation
            if user_id and self.active_postings.get(user_id, {}).get('cancel'):
                print(f"🛑 Posting cancelled by user {user_id}")
                break
            
            batch = questions[i:i + config.BATCH_SIZE]
            
            for idx, q in enumerate(batch):
                # Check cancellation again
                if user_id and self.active_postings.get(user_id, {}).get('cancel'):
                    print(f"🛑 Posting cancelled by user {user_id}")
                    break
                
                global_idx = i + idx + 1
                
                # Update progress
                if progress_callback:
                    await progress_callback(global_idx, total, success, failed)
                
                # Validate question
                if not q.get('question_description') or not q.get('options'):
                    skipped += 1
                    continue
                
                # Send quiz
                if await self.send_quiz_with_retry(context, chat_id, q, marker, tag, thread_id):
                    success += 1
                else:
                    failed += 1
                
                # Delay between quizzes
                if global_idx < total:
                    await asyncio.sleep(config.POLL_DELAY)
            
            # Check if cancelled before batch delay
            if user_id and self.active_postings.get(user_id, {}).get('cancel'):
                break
            
            # Delay between batches
            if i + config.BATCH_SIZE < total:
                await asyncio.sleep(config.BATCH_DELAY)
        
        # ===== SEND COUNTER IN FORMAT: ?/total =====
        # Example: "145/200" means 145 quizzes sent successfully out of 200 total
        try:
            counter_message = f"{success}/{total}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=counter_message,
                message_thread_id=thread_id
            )
            print(f"✅ Sent counter to destination: {counter_message}")
        except Exception as e:
            print(f"⚠️ Could not send counter: {e}")
        
        # Cleanup posting session
        if user_id and user_id in self.active_postings:
            del self.active_postings[user_id]
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped
        }
    
    def cancel_posting(self, user_id: int):
        """Cancel active posting for user"""
        if user_id in self.active_postings:
            self.active_postings[user_id]['cancel'] = True
            print(f"🛑 Marked posting for user {user_id} for cancellation")
            return True
        return False


# ===== GLOBAL INSTANCE - MUST BE AT END OF FILE =====
quiz_poster = QuizPoster()
