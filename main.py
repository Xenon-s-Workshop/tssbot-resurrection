"""
TSS Telegram Bot - Main Entry Point
Complete quiz bot with all Phase 1 fixes
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self):
        print("🔧 Initializing...")
        
        print("🔑 API rotator...")
        self.api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
        
        print("📄 PDF processor...")
        self.pdf_processor = PDFProcessor(self.api_rotator)
        
        print("🎮 Handlers...")
        self.bot_handlers = BotHandlers()
        
        print("🔘 Callbacks...")
        self.callback_handlers = CallbackHandlers(self.bot_handlers)
        
        print("🤖 Application...")
        self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        self._register_handlers()
        
        print("✅ Initialized")
    
    def _register_handlers(self):
        """Register handlers"""
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
        """Post-init"""
        print("🔧 Post-init...")
        
        poll_collector.set_application(application)
        application.bot_data['callback_handlers'] = self.callback_handlers
        
        print("✅ Post-init complete")
    
    async def process_queue(self):
        """Process queue"""
        from bot.content_processor import ContentProcessor
        
        while True:
            try:
                task = task_queue.get_next_task()
                
                if task:
                    user_id = task['user_id']
                    state = task['state']
                    context = task['context']
                    
                    print(f"⚙️ Processing user {user_id}")
                    
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
                        print(f"❌ Error user {user_id}: {e}")
                        import traceback
                        traceback.print_exc()
                        
                        try:
                            await context.bot.send_message(
                                user_id,
                                f"❌ Failed: `{str(e)[:150]}`",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                    
                    finally:
                        task_queue.set_processing(user_id, False)
                
                await asyncio.sleep(1)
            
            except Exception as e:
                print(f"❌ Queue error: {e}")
                await asyncio.sleep(5)
    
    def run(self):
        """Run bot"""
        print("=" * 60)
        print(f"🚀 Starting {config.BOT_NAME}")
        print("=" * 60)
        
        async def startup():
            asyncio.create_task(self.process_queue())
        
        self.application.post_init = lambda app: asyncio.gather(
            self.post_init(app),
            startup()
        )
        
        print("🎯 Running")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

def main():
    """Main"""
    try:
        print("\n" + "=" * 60)
        print(f"   {config.BOT_NAME} v{config.BOT_VERSION}")
        print("=" * 60 + "\n")
        
        bot = BotApplication()
        bot.run()
        
    except KeyboardInterrupt:
        print("\n\n👋 Stopped")
    except Exception as e:
        print(f"\n\n❌ Fatal: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
