"""
TSS Bot - Main Entry Point
Complete with all handlers and error handling
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    filters
)

from config import config
from database import db
from bot.handlers import BotHandlers
from bot.callbacks import CallbackHandlers
from processors.live_quiz import live_quiz_manager
from processors.poll_collector import poll_collector

# ==================== LOGGING ====================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ERROR HANDLER ====================

async def error_handler(update: object, context):
    logger.error(f"Exception while handling an update: {context.error}")
    
    try:
        if update and hasattr(update, 'effective_message') and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Error\n\nAn error occurred. Please try again or contact admin."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

# ==================== POST INIT ====================

async def post_init(application: Application):
    poll_collector.set_application(application)
    logger.info("✅ Post-init tasks completed")

# ==================== QUEUE PROCESSOR ====================

async def queue_processor(context):
    """Runs every few seconds via JobQueue (NON-BLOCKING)"""
    from utils.queue_manager import task_queue

    try:
        task = task_queue.get_next_task()
        if task:
            user_id = task['user_id']
            state = task['state']
            task_context = task['context']

            task_queue.set_processing(user_id, True)

            bot_handlers = context.application.bot_data.get('bot_handlers')
            if bot_handlers:
                await bot_handlers.process_queued_task(user_id, state, task_context)

            task_queue.set_processing(user_id, False)

    except Exception as e:
        logger.error(f"Queue processor error: {e}")

# ==================== FALLBACK (NO JOBQUEUE) ====================

async def queue_processor_fallback(application):
    """Fallback loop if JobQueue is missing"""
    from utils.queue_manager import task_queue

    while True:
        try:
            task = task_queue.get_next_task()
            if task:
                user_id = task['user_id']
                state = task['state']
                task_context = task['context']

                task_queue.set_processing(user_id, True)

                bot_handlers = application.bot_data.get('bot_handlers')
                if bot_handlers:
                    await bot_handlers.process_queued_task(user_id, state, task_context)

                task_queue.set_processing(user_id, False)

            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Fallback queue error: {e}")
            await asyncio.sleep(5)

# ==================== MAIN ====================

def main():
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Init handlers
    bot_handlers = BotHandlers()
    callback_handlers = CallbackHandlers(bot_handlers)

    application.bot_data['bot_handlers'] = bot_handlers

    # ==================== COMMANDS ====================

    application.add_handler(CommandHandler("start", bot_handlers.handle_start))
    application.add_handler(CommandHandler("help", bot_handlers.handle_help))
    application.add_handler(CommandHandler("settings", bot_handlers.handle_settings))
    application.add_handler(CommandHandler("info", bot_handlers.handle_info))
    application.add_handler(CommandHandler("queue", bot_handlers.handle_queue))
    application.add_handler(CommandHandler("cancel", bot_handlers.handle_cancel))
    application.add_handler(CommandHandler("livequiz", bot_handlers.handle_livequiz))
    application.add_handler(CommandHandler("model", bot_handlers.handle_model))

    # Admin
    application.add_handler(CommandHandler("authorize", bot_handlers.handle_authorize))
    application.add_handler(CommandHandler("revoke", bot_handlers.handle_revoke))
    application.add_handler(CommandHandler("users", bot_handlers.handle_users))

    # Poll tools
    application.add_handler(CommandHandler("collectpolls", bot_handlers.handle_collectpolls))
    application.add_handler(CommandHandler("merge", bot_handlers.handle_merge))
    application.add_handler(CommandHandler("done", bot_handlers.handle_done))
    application.add_handler(CommandHandler("status", bot_handlers.handle_status))

    # ==================== FILE HANDLERS ====================

    application.add_handler(MessageHandler(filters.Document.PDF, bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.FileExtension("csv"), bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.FileExtension("json"), bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.ALL, bot_handlers.handle_document))

    # Media
    application.add_handler(MessageHandler(filters.PHOTO, bot_handlers.handle_photo))
    application.add_handler(MessageHandler(filters.POLL, bot_handlers.handle_poll))

    # Text
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback_handlers.handle_text))

    # ==================== OTHER ====================

    application.add_handler(CallbackQueryHandler(callback_handlers.handle_callback))
    application.add_handler(PollAnswerHandler(live_quiz_manager.handle_poll_answer))

    application.add_error_handler(error_handler)

    # ==================== INIT ====================

    application.post_init = post_init

    # ✅ Safe JobQueue start
    if application.job_queue:
        application.job_queue.run_repeating(queue_processor, interval=3, first=1)
        logger.info("✅ JobQueue started")
    else:
        logger.warning("⚠️ JobQueue missing, using fallback loop")

        async def start_fallback(app):
            app.create_task(queue_processor_fallback(app))

        application.post_init = start_fallback

    # ==================== START ====================

    logger.info("🚀 Starting TSS Bot...")
    logger.info(f"📊 Model: {config.GEMINI_MODEL}")
    logger.info(f"🔑 API Keys: {len(config.GEMINI_API_KEYS)}")
    logger.info(f"🔐 Auth: {'Enabled' if config.AUTH_ENABLED else 'Disabled'}")
    logger.info(f"👥 Sudo Users: {len(config.SUDO_USER_IDS)}")

    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

# ==================== ENTRY ====================

if __name__ == '__main__':
    main()
