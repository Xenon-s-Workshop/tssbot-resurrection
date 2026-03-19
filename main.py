"""
Telegram Quiz Bot — Main entry point.
Fixes applied:
- Global error handler logs + notifies user
- Poll answer handler for /collectpolls
- show_dest_ callback routed through content_processor
- Queue processor with proper lifecycle
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    filters,
)
from config import config
from database import db
from utils.api_rotator import GeminiAPIRotator
from utils.queue_manager import task_queue
from processors.pdf_processor import PDFProcessor
from bot.handlers import BotHandlers
from bot.callbacks import CallbackHandlers
from bot.content_processor import ContentProcessor

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Shared instances ──────────────────────────────────────────────────────────

api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
pdf_processor_instance = PDFProcessor(api_rotator)


# ── Queue processor ───────────────────────────────────────────────────────────

class QueueProcessor:
    def __init__(self, bot_handlers: BotHandlers):
        self.bot_handlers = bot_handlers
        self.content_processor = ContentProcessor(bot_handlers)
        self.running = False

    async def start(self):
        if self.running:
            return
        self.running = True
        logger.info("🔄 Queue processor started")

        while self.running:
            try:
                task = task_queue.get_next_task()
                if task:
                    user_id = task["user_id"]
                    task_data = task["data"]
                    task_queue.set_processing(user_id, True)
                    try:
                        await self.content_processor.process_content(
                            user_id=user_id,
                            content_type=task_data["content_type"],
                            content_paths=task_data["content_paths"],
                            page_range=task_data.get("page_range"),
                            mode=task_data["mode"],
                            context=task_data["context"],
                        )
                    except Exception as e:
                        logger.error(f"Queue task error for user {user_id}: {e}", exc_info=True)
                    finally:
                        task_queue.set_processing(user_id, False)
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Queue loop error: {e}", exc_info=True)
                await asyncio.sleep(3)


# ── Global error handler ──────────────────────────────────────────────────────

async def global_error_handler(update: object, context):
    logger.error("Unhandled exception:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. The team has been notified.\n"
                "Please try again or use /cancel to reset your session."
            )
        except Exception:
            pass


# ── Post-init hook ────────────────────────────────────────────────────────────

async def post_init(application: Application):
    bot_handlers = application.bot_data["handlers"]
    queue_processor = QueueProcessor(bot_handlers)
    asyncio.create_task(queue_processor.start())
    logger.info("✅ Queue processor initialised")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    bot_handlers = BotHandlers(pdf_processor_instance)
    callback_handlers = CallbackHandlers(bot_handlers)

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.bot_data["handlers"] = bot_handlers
    application.post_init = post_init

    # Commands
    application.add_handler(CommandHandler("start", bot_handlers.start))
    application.add_handler(CommandHandler("help", bot_handlers.help_command))
    application.add_handler(CommandHandler("settings", bot_handlers.settings_command))
    application.add_handler(CommandHandler("info", bot_handlers.info_command))
    application.add_handler(CommandHandler("model", bot_handlers.model_command))
    application.add_handler(CommandHandler("queue", bot_handlers.queue_command))
    application.add_handler(CommandHandler("cancel", bot_handlers.cancel_command))
    application.add_handler(CommandHandler("collectpolls", bot_handlers.collect_polls_command))
    # Auth management
    application.add_handler(CommandHandler("adduser", bot_handlers.adduser_command))
    application.add_handler(CommandHandler("removeuser", bot_handlers.removeuser_command))
    application.add_handler(CommandHandler("listusers", bot_handlers.listusers_command))

    # Messages
    application.add_handler(MessageHandler(filters.Document.ALL, bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, bot_handlers.handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback_handlers.handle_text))

    # Callbacks
    application.add_handler(CallbackQueryHandler(callback_handlers.handle_callback))

    # Poll answers
    application.add_handler(PollAnswerHandler(bot_handlers.handle_poll_answer))

    # Global error handler
    application.add_error_handler(global_error_handler)

    logger.info("🤖 Bot started!")
    logger.info(f"⚡ Max workers: {config.MAX_CONCURRENT_IMAGES}")
    logger.info(f"📦 Queue limit: {config.MAX_QUEUE_SIZE}")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
