"""
TSS Telegram Bot - Main Entry Point
Complete quiz management bot with Gemini AI integration
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self):
        print("🔧 Initializing bot application...")
        
        # Initialize API rotator
        print("🔑 Initializing Gemini API rotator...")
        self.api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
        
        # Initialize PDF processor with API rotator
        print("📄 Initializing PDF processor...")
        self.pdf_processor = PDFProcessor(self.api_rotator)
        
        # Initialize bot handlers - NO ARGUMENT NEEDED
        print("🎮 Initializing handlers...")
        self.bot_handlers = BotHandlers()
        
        # Initialize callback handlers
        print("🔘 Initializing callbacks...")
        self.callback_handlers = CallbackHandlers(self.bot_handlers)
        
        # Create application
        print("🤖 Creating bot application...")
        self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Register handlers
        self._register_handlers()
        
        print("✅ Bot application initialized successfully!")
    
    def _register_handlers(self):
        """Register all command and message handlers"""
        app = self.application
        
        # ==================== COMMAND HANDLERS ====================
        app.add_handler(CommandHandler("start", self.bot_handlers.start_command))
        app.add_handler(CommandHandler("help", self.bot_handlers.help_command))
        app.add_handler(CommandHandler("settings", self.bot_handlers.settings_command))
        app.add_handler(CommandHandler("info", self.bot_handlers.info_command))
        app.add_handler(CommandHandler("queue", self.bot_handlers.queue_command))
        app.add_handler(CommandHandler("cancel", self.bot_handlers.cancel_command))
        app.add_handler(CommandHandler("collectpolls", self.bot_handlers.collectpolls_command))
        app.add_handler(CommandHandler("model", self.bot_handlers.model_command))
        app.add_handler(CommandHandler("livequiz", self.bot_handlers.livequiz_command))
        
        # Admin commands
        app.add_handler(CommandHandler("authorize", self.bot_handlers.authorize_command))
        app.add_handler(CommandHandler("revoke", self.bot_handlers.revoke_command))
        app.add_handler(CommandHandler("users", self.bot_handlers.users_command))
        
        # ==================== MESSAGE HANDLERS ====================
        # Document handler (PDF)
        app.add_handler(MessageHandler(
            filters.Document.PDF | filters.Document.FileExtension("pdf"),
            self.bot_handlers.handle_document
        ))
        
        # CSV handler
        app.add_handler(MessageHandler(
            filters.Document.FileExtension("csv"),
            self.bot_handlers.handle_csv
        ))
        
        # Photo handler
        app.add_handler(MessageHandler(
            filters.PHOTO,
            self.bot_handlers.handle_photo
        ))
        
        # Text handler (for various input states)
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.callback_handlers.handle_text
        ))
        
        # ==================== CALLBACK HANDLERS ====================
        app.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback))
        
        # ==================== POLL ANSWER HANDLER ====================
        app.add_handler(MessageHandler(
            filters.UpdateType.POLL_ANSWER,
            live_quiz_manager.handle_poll_answer
        ))
        
        print("✅ All handlers registered")
    
    async def post_init(self, application: Application):
        """Post-initialization setup"""
        print("🔧 Running post-initialization...")
        
        # Set application reference for poll collector
        poll_collector.set_application(application)
        
        # Store callback handlers in bot_data for access from commands
        application.bot_data['callback_handlers'] = self.callback_handlers
        
        print("✅ Post-initialization complete")
    
    async def process_queue(self):
        """Background task to process queue"""
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
                        # Mark as processing
                        task_queue.set_processing(user_id, True)
                        
                        # Process content
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
                        print(f"❌ Error processing task for user {user_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        try:
                            await context.bot.send_message(
                                user_id,
                                f"❌ Processing failed:\n`{str(e)[:200]}`",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                    
                    finally:
                        # Always clear processing state
                        task_queue.set_processing(user_id, False)
                
                # Small delay
                await asyncio.sleep(1)
            
            except Exception as e:
                print(f"❌ Queue processor error: {e}")
                await asyncio.sleep(5)
    
    def run(self):
        """Run the bot"""
        print("=" * 60)
        print(f"🚀 Starting {config.BOT_NAME}")
        print("=" * 60)
        
        # Start queue processor as background task
        asyncio.create_task(self.process_queue())
        
        # Run post_init
        self.application.post_init = self.post_init
        
        # Start polling
        print("🎯 Bot is running! Press Ctrl+C to stop.")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

def main():
    """Main entry point"""
    try:
        # Print startup banner
        print("\n" + "=" * 60)
        print(f"   {config.BOT_NAME} v{config.BOT_VERSION}")
        print("   Telegram Quiz Bot with Gemini AI")
        print("=" * 60 + "\n")
        
        # Initialize and run bot
        bot = BotApplication()
        bot.run()
        
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
