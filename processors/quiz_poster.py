"""
Quiz Poster - WITH CUSTOM MESSAGE and SUCCESS COUNTER
Posts quizzes with custom announcement message
Sends "?/200" format success message to destination
"""

import asyncio
from typing import List, Dict, Optional
from telegram.ext import ContextTypes
from telegram.error import RetryAfter, TimedOut
from config import config

class QuizPoster:
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
    
    @staticmethod
    async def post_quizzes_batch(
        context,
        chat_id,
        questions,
        marker,
        tag,
        thread_id=None,
        progress_callback=None,
        custom_message=None
    ):
        """
        Post quizzes with custom message and success counter
        
        Args:
            custom_message: Custom announcement message to send first
            
        Returns success counter in format: sent/total
        """
        total = len(questions)
        success = failed = skipped = 0
        
        # Send custom message if provided
        if custom_message:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=custom_message,
                    message_thread_id=thread_id
                )
                print(f"✅ Sent custom message: {custom_message[:50]}...")
            except Exception as e:
                print(f"⚠️ Could not send custom message: {e}")
        
        # Post quizzes
        for i in range(0, total, config.BATCH_SIZE):
            batch = questions[i:i + config.BATCH_SIZE]
            
            for idx, q in enumerate(batch):
                global_idx = i + idx + 1
                
                # Update progress
                if progress_callback:
                    await progress_callback(global_idx, total, success, failed)
                
                # Validate question
                if not q.get('question_description') or not q.get('options'):
                    skipped += 1
                    continue
                
                # Send quiz
                if await QuizPoster.send_quiz_with_retry(context, chat_id, q, marker, tag, thread_id):
                    success += 1
                else:
                    failed += 1
                
                # Delay between quizzes
                if global_idx < total:
                    await asyncio.sleep(config.POLL_DELAY)
            
            # Delay between batches
            if i + config.BATCH_SIZE < total:
                await asyncio.sleep(config.BATCH_DELAY)
        
        # Send success counter to destination in format: "?/200"
        try:
            counter_message = f"{success}/{total}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=counter_message,
                message_thread_id=thread_id
            )
            print(f"✅ Sent success counter: {counter_message}")
        except Exception as e:
            print(f"⚠️ Could not send counter: {e}")
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped
        }
