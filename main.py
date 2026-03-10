"""
Main Bot Entry Point - GHOST BUG ELIMINATED
Guaranteed cleanup in ALL cases including errors
"""

import asyncio
import logging
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
from processors.pdf_processor import PDFProcessor
from processors.live_quiz import live_quiz_manager
from utils.queue_manager import task_queue
from utils.api_rotator import GeminiAPIRotator
from bot.content_processor import ContentProcessor

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self):
        self.application = None
        
        # Create Gemini API rotator first
        self.api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
        
        # Create PDF processor with API rotator
        self.pdf_processor = PDFProcessor(self.api_rotator)
        
        # Create handlers
        self.bot_handlers = BotHandlers(self.pdf_processor)
        self.callback_handlers = CallbackHandlers(self.bot_handlers)
        self.content_processor = ContentProcessor(self.bot_handlers)
    
    def setup_handlers(self):
        """Setup all handlers"""
        app = self.application
        
        # Commands
        app.add_handler(CommandHandler("start", self.bot_handlers.start))
        app.add_handler(CommandHandler("help", self.bot_handlers.help_command))
        app.add_handler(CommandHandler("settings", self.bot_handlers.settings_command))
        app.add_handler(CommandHandler("info", self.bot_handlers.info_command))
        app.add_handler(CommandHandler("model", self.bot_handlers.model_command))
        app.add_handler(CommandHandler("queue", self.bot_handlers.queue_command))
        app.add_handler(CommandHandler("cancel", self.bot_handlers.cancel_command))
        app.add_handler(CommandHandler("collectpolls", self.bot_handlers.collectpolls_command))
        app.add_handler(CommandHandler("livequiz", self.bot_handlers.livequiz_command))
        
        # Admin commands
        app.add_handler(CommandHandler("authorize", self.bot_handlers.authorize_command))
        app.add_handler(CommandHandler("revoke", self.bot_handlers.revoke_command))
        app.add_handler(CommandHandler("users", self.bot_handlers.users_command))
        
        # Callbacks
        app.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback))
        
        # Messages
        app.add_handler(MessageHandler(filters.Document.ALL, self.bot_handlers.handle_document))
        app.add_handler(MessageHandler(filters.PHOTO, self.bot_handlers.handle_photo))
        app.add_handler(MessageHandler(filters.POLL, self.bot_handlers.handle_poll))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.callback_handlers.handle_text))
        
        # Poll answers for live quiz
        app.add_handler(PollAnswerHandler(live_quiz_manager.handle_poll_answer))
        
        logger.info("✅ All handlers registered")
    
    async def process_queue(self):
        """
        Queue processor with GUARANTEED CLEANUP
        Runs continuously to process queued tasks
        """
        logger.info("🔄 Queue processor started")
        
        while True:
            try:
                task = task_queue.get_next_task()
                
                if task is None:
                    await asyncio.sleep(2)
                    continue
                
                user_id = task['user_id']
                data = task['data']
                
                logger.info(f"▶️ Processing task for user {user_id}")
                
                # Mark as processing
                task_queue.set_processing(user_id, True)
                
                try:
                    # Send initial status
                    await data['context'].bot.send_message(
                        user_id,
                        "⚙️ *Processing started...*",
                        parse_mode='Markdown'
                    )
                    
                    # Process content
                    await self.content_processor.process_content(
                        user_id,
                        data['content_type'],
                        data['content_paths'],
                        data['page_range'],
                        data['mode'],
                        data['context']
                    )
                    
                    logger.info(f"✅ Task completed for user {user_id}")
                
                except Exception as e:
                    logger.error(f"❌ Task error for user {user_id}: {e}", exc_info=True)
                    
                    # Send error message
                    try:
                        await data['context'].bot.send_message(
                            user_id,
                            f"❌ *Processing Failed*\n\n"
                            f"Error: {str(e)[:200]}",
                            parse_mode='Markdown'
                        )
                    except Exception as msg_error:
                        logger.error(f"Could not send error message: {msg_error}")
                
                finally:
                    # ===== CRITICAL: ALWAYS CLEAR PROCESSING STATE =====
                    task_queue.set_processing(user_id, False)
                    logger.info(f"🧹 Cleanup completed for user {user_id}")
            
            except Exception as e:
                logger.error(f"❌ Queue processor error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def post_init(self, application: Application):
        """Initialize after application start"""
        logger.info("🤖 Bot initialization started")
        
        # Start queue processor
        asyncio.create_task(self.process_queue())
        
        logger.info("✅ Bot fully initialized")
    
    def run(self):
        """Run the bot"""
        logger.info(f"🚀 Starting {config.BOT_NAME}")
        logger.info(f"   Model: {config.GEMINI_MODEL}")
        logger.info(f"   Auth: {'Enabled' if config.AUTH_ENABLED else 'Disabled'}")
        logger.info(f"   API Keys: {len(config.GEMINI_API_KEYS)}")
        
        # Build application
        self.application = (
            Application.builder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .post_init(self.post_init)
            .build()
        )
        
        # Setup handlers
        self.setup_handlers()
        
        # Run
        logger.info("✅ Bot is ready!")
        self.application.run_polling(allowed_updates=['message', 'callback_query', 'poll_answer'])

if __name__ == "__main__":
    bot = BotApplication()
    bot.run()
