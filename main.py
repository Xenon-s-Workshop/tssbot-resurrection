"""
TSS Bot - Main Entry Point
Dual AI: Gemini (primary) + DeepSeek (secondary, toggle in /settings)
PROPER CLEANUP - NO GHOST BUGS
"""

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, PollHandler
from config import config
from database import db
from utils.api_rotator import GeminiAPIRotator
from utils.queue_manager import task_queue
from processors.pdf_processor import PDFProcessor
from processors.deepseek_processor import DeepSeekProcessor, DEEPSEEK_MODELS
from bot.handlers import BotHandlers
from bot.callbacks import CallbackHandlers
from bot.content_processor import ContentProcessor

# Initialize AI processors
api_rotator = GeminiAPIRotator(config.GEMINI_API_KEYS)
gemini_processor = PDFProcessor(api_rotator)
deepseek_processor = DeepSeekProcessor(model=DEEPSEEK_MODELS[7])  # Default: DeepSeek-R1

class QueueProcessor:
    """Queue processor with PROPER CLEANUP and dual AI support"""

    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers
        self.running = False
        self.content_processor = ContentProcessor(bot_handlers)

    async def start(self):
        if self.running:
            return
        self.running = True
        print("🔄 Queue processor started")

        while self.running:
            try:
                task = task_queue.get_next_task()

                if task:
                    user_id = task['user_id']
                    task_data = task['data']

                    # Mark processing
                    task_queue.set_processing(user_id, True)

                    try:
                        await self.content_processor.process_content(
                            user_id=user_id,
                            content_type=task_data['content_type'],
                            content_paths=task_data['content_paths'],
                            page_range=task_data.get('page_range'),
                            mode=task_data['mode'],
                            context=task_data['context']
                        )
                    except Exception as e:
                        print(f"❌ Error for user {user_id}: {e}")
                        try:
                            await task_data['context'].bot.send_message(
                                user_id, f"❌ Processing failed: {str(e)[:200]}"
                            )
                        except:
                            pass
                    finally:
                        # CRITICAL: ALWAYS CLEAR — prevents ghost bug
                        task_queue.set_processing(user_id, False)
                        print(f"✅ Cleared processing for user {user_id}")

                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Queue processor error: {e}")
                await asyncio.sleep(3)

async def post_init(application: Application):
    bot_handlers = application.bot_data['handlers']
    queue_processor = QueueProcessor(bot_handlers)
    asyncio.create_task(queue_processor.start())
    print("✅ Queue processor initialized")

def main():
    print(f"🤖 Starting {config.BOT_NAME}...")
    print(f"🟢 Gemini model: {config.GEMINI_MODEL}")
    print(f"🔵 DeepSeek default: {DEEPSEEK_MODELS[7]}")

    # Handlers
    bot_handlers = BotHandlers(gemini_processor, deepseek_processor)
    callback_handlers = CallbackHandlers(bot_handlers)

    # Application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.bot_data['handlers'] = bot_handlers
    application.post_init = post_init

    # ==================== COMMANDS ====================
    application.add_handler(CommandHandler("start",       bot_handlers.start))
    application.add_handler(CommandHandler("help",        bot_handlers.help_command))
    application.add_handler(CommandHandler("settings",    bot_handlers.settings_command))
    application.add_handler(CommandHandler("info",        bot_handlers.info_command))
    application.add_handler(CommandHandler("collectpolls",bot_handlers.collectpolls_command))
    application.add_handler(CommandHandler("model",       bot_handlers.model_command))
    application.add_handler(CommandHandler("queue",       bot_handlers.queue_command))
    application.add_handler(CommandHandler("cancel",      bot_handlers.cancel_command))
    application.add_handler(CommandHandler("authorize",   bot_handlers.authorize_command))
    application.add_handler(CommandHandler("revoke",      bot_handlers.revoke_command))
    application.add_handler(CommandHandler("users",       bot_handlers.users_command))

    # ==================== MESSAGES ====================
    application.add_handler(MessageHandler(filters.Document.ALL, bot_handlers.handle_document))
    application.add_handler(MessageHandler(filters.PHOTO,        bot_handlers.handle_photo))
    application.add_handler(PollHandler(bot_handlers.handle_poll))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback_handlers.handle_text))

    # ==================== CALLBACKS ====================
    application.add_handler(CallbackQueryHandler(callback_handlers.handle_callback))

    print(f"✅ {config.BOT_NAME} running!")
    print(f"  Auth: {'on' if config.AUTH_ENABLED else 'off'} | Sudo: {len(config.SUDO_USER_IDS)} users")
    print(f"  Use /settings to toggle AI provider per-user")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
