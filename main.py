"""
TSS Telegram Bot - Main Entry Point
Complete quiz bot with proper error handling and UX
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
    ContextTypes
)

from config import config
from database import db
from bot.handlers import BotHandlers
from bot.callbacks import CallbackHandlers
from processors.poll_collector import poll_collector
from processors.live_quiz import live_quiz_manager
from utils.queue_manager import task_queue
from processors.pdf_processor import PDFProcessor
from utils.api_rotator import GeminiAPIRotator

# Enhanced logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self):
        print("🔧 Initializing bot...")
        
        self.api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
        self.pdf_processor = PDFProcessor(self.api_rotator)
        self.bot_handlers = BotHandlers()
        self.callback_handlers = CallbackHandlers(self.bot_handlers)
        self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Register global error handler
        self.application.add_error_handler(self.error_handler)
        
        self._register_handlers()
        
        print("✅ Bot initialized successfully")
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)
        
        # Try to inform user
        try:
            if update and hasattr(update, 'effective_user') and update.effective_user:
                user_id = update.effective_user.id
                error_msg = str(context.error)
                
                # Shorten error message
                if len(error_msg) > 200:
                    error_msg = error_msg[:200] + "..."
                
                await context.bot.send_message(
                    user_id,
                    f"❌ **Error**\n\n`{error_msg}`\n\nPlease try again or contact admin.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    def _register_handlers(self):
        """Register all handlers"""
        app = self.application
        
        # Commands
        app.add_handler(CommandHandler("start", self.bot_handlers.start_command))
        app.add_handler(CommandHandler("help", self.bot_handlers.help_command))
        app.add_handler(CommandHandler("settings", self.bot_handlers.settings_command))
        app.add_handler(CommandHandler("info", self.bot_handlers.info_command))
        app.add_handler(CommandHandler("queue", self.bot_handlers.queue_command))
        app.add_handler(CommandHandler("cancel", self.bot_handlers.cancel_command))
        app.add_handler(CommandHandler("collectpolls", self.bot_handlers.collectpolls_command))
        app.add_handler(CommandHandler("model", self.bot_handlers.model_command))
        app.add_handler(CommandHandler("livequiz", self.bot_handlers.livequiz_command))
        
        # Admin
        app.add_handler(CommandHandler("authorize", self.bot_handlers.authorize_command))
        app.add_handler(CommandHandler("revoke", self.bot_handlers.revoke_command))
        app.add_handler(CommandHandler("users", self.bot_handlers.users_command))
        
        # Files
        app.add_handler(MessageHandler(
            filters.Document.PDF | filters.Document.FileExtension("pdf"),
            self.bot_handlers.handle_document
        ))
        
        app.add_handler(MessageHandler(
            filters.Document.FileExtension("csv"),
            self.bot_handlers.handle_csv
        ))
        
        app.add_handler(MessageHandler(
            filters.Document.FileExtension("json"),
            self.bot_handlers.handle_json
        ))
        
        app.add_handler(MessageHandler(
            filters.PHOTO,
            self.bot_handlers.handle_photo
        ))
        
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.callback_handlers.handle_text
        ))
        
        # Callbacks
        app.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback))
        
        # Poll answers
        app.add_handler(PollAnswerHandler(live_quiz_manager.handle_poll_answer))
        
        print("✅ Handlers registered")
    
    async def post_init(self, application: Application):
        """Post initialization"""
        poll_collector.set_application(application)
        application.bot_data['callback_handlers'] = self.callback_handlers
        print("✅ Post-init complete")
    
    async def process_queue(self):
        """Process task queue"""
        from bot.content_processor import ContentProcessor
        
        while True:
            try:
                task = task_queue.get_next_task()
                
                if task:
                    user_id = task['user_id']
                    state = task['state']
                    context = task['context']
                    
                    print(f"⚙️ Processing task for user {user_id}")
                    
                    try:
                        task_queue.set_processing(user_id, True)
                        
                        processor = ContentProcessor(self.bot_handlers)
                        await processor.process_content(
                            user_id,
                            state['content_type'],
                            state['content_paths'],
                            state.get('page_range'),
                            state['mode'],
                            context
                        )
                        
                    except Exception as e:
                        logger.error(f"Task processing error for user {user_id}: {e}", exc_info=True)
                        
                        try:
                            await context.bot.send_message(
                                user_id,
                                f"❌ **Processing Failed**\n\n`{str(e)[:200]}`",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                    
                    finally:
                        task_queue.set_processing(user_id, False)
                
                await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"Queue processing error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    def run(self):
        """Run the bot"""
        print("\n" + "=" * 60)
        print(f"🚀 Starting {config.BOT_NAME} v{config.BOT_VERSION}")
        print("=" * 60 + "\n")
        
        async def startup():
            asyncio.create_task(self.process_queue())
        
        self.application.post_init = lambda app: asyncio.gather(
            self.post_init(app),
            startup()
        )
        
        print("🎯 Bot is now running...")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

def main():
    """Main entry point"""
    try:
        print("\n" + "=" * 60)
        print(f"   {config.BOT_NAME} v{config.BOT_VERSION}")
        print("   Quiz Generation & Management Bot")
        print("=" * 60 + "\n")
        
        bot = BotApplication()
        bot.run()
        
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n\n❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
