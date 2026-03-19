"""
Quiz Poster with Retry System and Progress Tracking
"""

import asyncio
from typing import List, Dict
from telegram.error import RetryAfter, TimedOut
from config import config

class QuizPoster:
    def __init__(self):
        self.active_postings = {}
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
    async def send_quiz_with_retry(context, chat_id, question, marker, tag, thread_id=None, max_retries=2):
        """Send quiz with retry logic"""
        for attempt in range(max_retries + 1):
            try:
                opts = question.get('options', [])[:10]
                if len(opts) < 2:
                    print(f"⚠️ Skipping: less than 2 options")
                    return (False, "Less than 2 options")
                
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
                return (True, None)
                
            except RetryAfter as e:
                if attempt < max_retries:
                    print(f"⏳ Rate limit, waiting {e.retry_after}s...")
                    await asyncio.sleep(e.retry_after)
                else:
                    return (False, f"Rate limited: {e.retry_after}s")
            
            except TimedOut:
                if attempt < max_retries:
                    print(f"⏳ Timeout, retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(2)
                else:
                    return (False, "Timeout after retries")
            
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Quiz send error: {error_msg}")
                return (False, error_msg[:100])
        
        return (False, "Failed after retries")
    
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
        """Post quizzes with retry system"""
        total = len(questions)
        success = failed = 0
        failed_questions = []
        
        # Register session
        if user_id:
            self.active_postings[user_id] = {'cancel': False}
        
        # Post quizzes
        for i in range(0, total, config.BATCH_SIZE):
            # Check cancellation
            if user_id and self.active_postings.get(user_id, {}).get('cancel'):
                print(f"🛑 Cancelled by user")
                break
            
            batch = questions[i:i + config.BATCH_SIZE]
            
            for idx, q in enumerate(batch):
                if user_id and self.active_postings.get(user_id, {}).get('cancel'):
                    break
                
                global_idx = i + idx + 1
                
                # Progress callback
                if progress_callback:
                    await progress_callback(global_idx, total, success, failed)
                
                # Send with retry
                result, error = await self.send_quiz_with_retry(
                    context, chat_id, q, marker, tag, thread_id
                )
                
                if result:
                    success += 1
                else:
                    failed += 1
                    failed_questions.append({
                        'number': global_idx,
                        'question': q.get('question_description', '')[:50],
                        'error': error
                    })
                
                # Delay
                if global_idx < total:
                    await asyncio.sleep(config.POLL_DELAY)
            
            if user_id and self.active_postings.get(user_id, {}).get('cancel'):
                break
            
            # Batch delay
            if i + config.BATCH_SIZE < total:
                await asyncio.sleep(config.BATCH_DELAY)
        
        # Send counter: ?/total
        try:
            counter_message = f"?/{total}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=counter_message,
                message_thread_id=thread_id
            )
            print(f"✅ Sent counter: {counter_message}")
        except Exception as e:
            print(f"⚠️ Counter send failed: {e}")
        
        # Cleanup
        if user_id and user_id in self.active_postings:
            del self.active_postings[user_id]
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'failed_questions': failed_questions
        }
    
    def cancel_posting(self, user_id: int):
        """Cancel active posting"""
        if user_id in self.active_postings:
            self.active_postings[user_id]['cancel'] = True
            return True
        return False

quiz_poster = QuizPoster()
