from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from database import db
from config import config

def _get_user_id(update: Update) -> int:
    """Safely extract user_id from various update types"""
    # Try effective_user (messages, commands)
    if update.effective_user:
        return update.effective_user.id
    
    # Try callback_query (button presses)
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    
    # Try poll (polls sent to bot)
    if update.poll and hasattr(update, 'poll_answer'):
        return update.poll_answer.user.id
    
    # Unsupported update type (e.g., channel posts, my_chat_member updates)
    return None

def require_auth(func):
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = _get_user_id(update)
        
        # Skip auth for updates without user (e.g., channel posts, my_chat_member)
        if user_id is None:
            return
        
        if not db.is_authorized(user_id):
            # Try to get username
            username = "User"
            if update.effective_user:
                username = update.effective_user.username or update.effective_user.first_name or "User"
            
            # Try to send message
            try:
                if update.message:
                    await update.message.reply_text(
                        f"🔒 *Access Denied*\n\n@{username}, you are not authorized to use {config.BOT_NAME}.\n\nPlease contact an administrator.",
                        parse_mode='Markdown'
                    )
                elif update.callback_query:
                    await update.callback_query.answer("🔒 Access Denied", show_alert=True)
            except:
                pass
            return
        
        return await func(self, update, context, *args, **kwargs)
    return wrapper

def require_sudo(func):
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = _get_user_id(update)
        
        # Skip for non-user updates
        if user_id is None:
            return
        
        if not db.is_sudo(user_id):
            try:
                if update.message:
                    await update.message.reply_text(
                        "🔐 *Sudo Access Required*\n\nThis command requires admin privileges.",
                        parse_mode='Markdown'
                    )
                elif update.callback_query:
                    await update.callback_query.answer("🔐 Sudo required", show_alert=True)
            except:
                pass
            return
        
        return await func(self, update, context, *args, **kwargs)
    return wrapper
