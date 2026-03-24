"""
TSS Bot - Main Entry Point (Simplified - No Job Queue)
"""

import logging
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
                "❌ **Error**\n\nAn error occurred. Please try again or contact admin.",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

async def post_init(application: Application):
    """Post initialization tasks"""
    poll_collector.set_application(application)
    logger.info("✅ Post-init tasks completed")

def main():
    """Main function"""
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    bot_handlers = BotHandlers()
    callback_handlers = CallbackHandlers(bot_handlers)
    
    application.bot_data['bot_handlers'] = bot_handlers
    
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
    
    # Poll collection
    application.add_handler(CommandHandler("collectpolls", bot_handlers.handle_collectpolls))
    application.add_handler(CommandHandler("merge", bot_handlers.handle_merge))
    application.add_handler(CommandHandler("done", bot_handlers.handle_done))
    application.add_handler(CommandHandler("status", bot_handlers.handle_status))
    
    # Document handlers
    application.add_handler(MessageHandler(filters.Document.PDF, bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.FileExtension("csv"), bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.FileExtension("json"), bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.Document.ALL, bot_handlers.handle_document))
    
    # Photo handler
    application.add_handler(MessageHandler(filters.PHOTO, bot_handlers.handle_photo))
    
    # Poll handler
    application.add_handler(MessageHandler(filters.POLL, bot_handlers.handle_poll))
    
    # Text handler (must be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback_handlers.handle_text))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(callback_handlers.handle_callback))
    application.add_handler(PollAnswerHandler(live_quiz_manager.handle_poll_answer))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Post init (removed job queue)
    application.post_init = post_init
    
    logger.info("🚀 Starting TSS Bot...")
    logger.info(f"📊 Model: {config.GEMINI_MODEL}")
    logger.info(f"🔑 API Keys: {len(config.GEMINI_API_KEYS)}")
    logger.info(f"🔐 Auth: {'Enabled' if config.AUTH_ENABLED else 'Disabled'}")
    logger.info(f"👥 Sudo Users: {len(config.SUDO_USER_IDS)}")
    
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
