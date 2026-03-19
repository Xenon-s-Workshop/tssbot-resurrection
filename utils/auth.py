"""Authorization Decorator - FIXED"""
from functools import wraps
from telegram import Update
from database import db

def require_auth(func):
    """Authorization decorator"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        update = None
        for arg in args:
            if isinstance(arg, Update):
                update = arg
                break
        
        if not update or not hasattr(update, 'effective_user') or not update.effective_user:
            return await func(*args, **kwargs)
        
        user_id = update.effective_user.id
        
        if not db.is_user_authorized(user_id):
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text("❌ Unauthorized. Contact admin.")
            return None
        
        return await func(*args, **kwargs)
    return wrapper
