"""
Quiz poster — sends Telegram quiz polls to a channel or group.
Features:
- 2-attempt retry per question with reason logging
- Progress callback
- Batch rate-limiting
- Header message support
"""

import asyncio
import logging
from typing import List, Dict, Optional, Callable
from telegram.error import RetryAfter, TimedOut, BadRequest, Forbidden
from config import config

logger = logging.getLogger(__name__)

OPTION_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
MAX_QUESTION_LEN = 300
MAX_EXPLANATION_LEN = 200


class QuizPoster:
    # ── Formatters ────────────────────────────────────────────────────────────

    @staticmethod
    def format_question(text: str, marker: str) -> str:
        prefix = f"{marker}\n\n" if marker else ""
        full = f"{prefix}{text}"
        if len(full) > MAX_QUESTION_LEN:
            max_body = MAX_QUESTION_LEN - len(prefix) - 3
            full = f"{prefix}{text[:max_body]}..."
        return full

    @staticmethod
    def format_explanation(text: str, tag: str) -> Optional[str]:
        if not text:
            return None
        suffix = f" [{tag}]" if tag else ""
        full = f"{text}{suffix}"
        if len(full) > MAX_EXPLANATION_LEN:
            max_body = MAX_EXPLANATION_LEN - len(suffix) - 3
            full = f"{text[:max_body]}...{suffix}"
        return full

    # ── Single quiz sender ────────────────────────────────────────────────────

    @staticmethod
    async def send_quiz_with_retry(
        context,
        chat_id: int,
        question: Dict,
        quiz_marker: str,
        explanation_tag: str,
        message_thread_id: Optional[int] = None,
        max_retries: int = 2,
    ) -> Dict:
        """
        Returns dict: {"success": bool, "reason": str}
        """
        options = (question.get("options") or [])[:10]
        if len(options) < 2:
            return {"success": False, "reason": "fewer than 2 options"}

        correct_id = question.get("correct_answer_index", 0)
        if not isinstance(correct_id, int) or correct_id < 0 or correct_id >= len(options):
            correct_id = 0

        formatted_q = QuizPoster.format_question(
            question.get("question_description") or "", quiz_marker
        )
        formatted_e = QuizPoster.format_explanation(
            question.get("explanation") or "", explanation_tag
        )

        last_reason = "unknown error"
        for attempt in range(max_retries):
            try:
                await context.bot.send_poll(
                    chat_id=chat_id,
                    question=formatted_q,
                    options=options,
                    type="quiz",
                    correct_option_id=correct_id,
                    explanation=formatted_e,
                    is_anonymous=True,
                    message_thread_id=message_thread_id,
                )
                return {"success": True, "reason": ""}

            except RetryAfter as e:
                wait = e.retry_after + 1
                logger.warning(f"Rate limited — waiting {wait}s (attempt {attempt+1})")
                await asyncio.sleep(wait)
                last_reason = f"rate limited ({e.retry_after}s)"

            except TimedOut:
                logger.warning(f"Timed out (attempt {attempt+1})")
                await asyncio.sleep(2)
                last_reason = "timed out"

            except Forbidden as e:
                logger.error(f"Forbidden: {e}")
                return {"success": False, "reason": f"forbidden: {e}"}

            except BadRequest as e:
                logger.error(f"BadRequest: {e}")
                return {"success": False, "reason": f"bad request: {e}"}

            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt+1}): {e}")
                await asyncio.sleep(1)
                last_reason = str(e)

        return {"success": False, "reason": last_reason}

    # ── Batch poster ──────────────────────────────────────────────────────────

    @staticmethod
    async def post_header(context, chat_id: int, header: str, thread_id: Optional[int] = None):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=header,
                message_thread_id=thread_id,
            )
        except Exception as e:
            logger.warning(f"Header send failed: {e}")

    @staticmethod
    async def post_quizzes_batch(
        context,
        chat_id: int,
        questions: List[Dict],
        quiz_marker: str,
        explanation_tag: str,
        message_thread_id: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        header: Optional[str] = None,
    ) -> Dict:
        total = len(questions)
        success = failed = skipped = 0
        failures: List[str] = []

        # Send header first
        if header:
            await QuizPoster.post_header(context, chat_id, header, message_thread_id)
            await asyncio.sleep(0.5)

        for i in range(0, total, config.BATCH_SIZE):
            batch = questions[i: i + config.BATCH_SIZE]

            for local_idx, q in enumerate(batch):
                global_idx = i + local_idx + 1

                if progress_callback:
                    try:
                        await progress_callback(global_idx, total)
                    except Exception:
                        pass

                if not (q.get("question_description") or "").strip():
                    skipped += 1
                    logger.warning(f"Q{global_idx}: empty question — skipped")
                    continue
                if not q.get("options"):
                    skipped += 1
                    logger.warning(f"Q{global_idx}: no options — skipped")
                    continue

                result = await QuizPoster.send_quiz_with_retry(
                    context, chat_id, q, quiz_marker, explanation_tag, message_thread_id
                )
                if result["success"]:
                    success += 1
                else:
                    failed += 1
                    failures.append(f"Q{global_idx}: {result['reason']}")
                    logger.warning(f"Q{global_idx} failed: {result['reason']}")

                if global_idx < total:
                    await asyncio.sleep(config.POLL_DELAY)

            # Inter-batch pause
            if i + config.BATCH_SIZE < total:
                await asyncio.sleep(config.BATCH_DELAY)

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "failures": failures,
        }
