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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: object, context):
    """Global error handler"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    try:
        if update and hasattr(update, 'effective_message') and update.effective_message:
            await update.effective_message.reply_text(
                "❌ **Error**\n\n"
                "An error occurred. Please try again or contact admin.",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

async def post_init(application: Application):
    """Post initialization tasks"""
    # Set poll collector application reference
    poll_collector.set_application(application)
    logger.info("✅ Post-init tasks completed")

async def queue_processor(context):
    """Background task to process queue"""
    from utils.queue_manager import task_queue
    
    while True:
        try:
            task = task_queue.get_next_task()
            if task:
                user_id = task['user_id']
                state = task['state']
                task_context = task['context']
                
                # Mark as processing
                task_queue.set_processing(user_id, True)
                
                # Get bot handlers
                bot_handlers = context.application.bot_data.get('bot_handlers')
                if bot_handlers:
                    await bot_handlers.process_queued_task(user_id, state, task_context)
                
                # Clear processing
                task_queue.set_processing(user_id, False)
            
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Queue processor error: {e}")
            await asyncio.sleep(5)

def main():
    """Main function"""
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Initialize handlers
    bot_handlers = BotHandlers()
    callback_handlers = CallbackHandlers(bot_handlers)
    
    # Store in bot_data for access by queue processor
    application.bot_data['bot_handlers'] = bot_handlers
    
    # ==================== COMMAND HANDLERS ====================
    
    # Basic commands
    application.add_handler(CommandHandler("start", bot_handlers.handle_start))
    application.add_handler(CommandHandler("help", bot_handlers.handle_help))
    application.add_handler(CommandHandler("settings", bot_handlers.handle_settings))
    application.add_handler(CommandHandler("info", bot_handlers.handle_info))
    application.add_handler(CommandHandler("queue", bot_handlers.handle_queue))
    application.add_handler(CommandHandler("cancel", bot_handlers.handle_cancel))
    application.add_handler(CommandHandler("livequiz", bot_handlers.handle_livequiz))
    application.add_handler(CommandHandler("model", bot_handlers.handle_model))
    
    # Admin commands
    application.add_handler(CommandHandler("authorize", bot_handlers.handle_authorize))
    application.add_handler(CommandHandler("revoke", bot_handlers.handle_revoke))
    application.add_handler(CommandHandler("users", bot_handlers.handle_users))
    
    # Poll collection commands
    application.add_handler(CommandHandler("collectpolls", bot_handlers.handle_collectpolls))
    application.add_handler(CommandHandler("merge", bot_handlers.handle_merge))
    application.add_handler(CommandHandler("done", bot_handlers.handle_done))
    application.add_handler(CommandHandler("status", bot_handlers.handle_status))
    
    # ==================== MESSAGE HANDLERS ====================
    
    # Document handlers (PDF, CSV, JSON)
    application.add_handler(MessageHandler(filters.Document.PDF, bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.CSV, bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.FileExtension("json"), bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.ALL, bot_handlers.handle_document))
    
    # Photo handler
    application.add_handler(MessageHandler(filters.PHOTO, bot_handlers.handle_photo))
    
    # Poll handler
    application.add_handler(MessageHandler(filters.POLL, bot_handlers.handle_poll))
    
    # Text handler (for callbacks)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback_handlers.handle_text))
    
    # ==================== OTHER HANDLERS ====================
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(callback_handlers.handle_callback))
    
    # Poll answer handler for live quiz
    application.add_handler(PollAnswerHandler(live_quiz_manager.handle_poll_answer))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # ==================== POST INIT & JOBS ====================
    
    # Post init
    application.post_init = post_init
    
    # Start queue processor
    application.job_queue.run_repeating(queue_processor, interval=3, first=1)
    
    # ==================== RUN BOT ====================
    
    logger.info("🚀 Starting TSS Bot...")
    logger.info(f"📊 Model: {config.GEMINI_MODEL}")
    logger.info(f"🔑 API Keys: {len(config.GEMINI_API_KEYS)}")
    logger.info(f"🔐 Auth: {'Enabled' if config.AUTH_ENABLED else 'Disabled'}")
    logger.info(f"👥 Sudo Users: {len(config.SUDO_USER_IDS)}")
    
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
