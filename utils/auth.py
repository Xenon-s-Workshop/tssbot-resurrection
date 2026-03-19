"""
Authorization Decorator
Checks if user is authorized before allowing command execution
"""

from functools import wraps
from telegram import Update
from database import db
from config import config

def require_auth(func):
    """
    Decorator to require authorization for commands
    Uses duck typing to detect context type
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Find Update and context objects
        update = None
        context = None
        
        for arg in args:
            if isinstance(arg, Update):
                update = arg
            elif hasattr(arg, 'bot') and hasattr(arg, 'user_data'):
                context = arg
        
        # If no update found, allow (internal call)
        if not update:
            return await func(*args, **kwargs)
        
        # Get user_id
        user_id = None
        
        # Try effective_user first
        if hasattr(update, 'effective_user') and update.effective_user:
            user_id = update.effective_user.id
        # Handle poll_answer
        elif hasattr(update, 'poll_answer') and update.poll_answer:
            if hasattr(update.poll_answer, 'user') and update.poll_answer.user:
                user_id = update.poll_answer.user.id
            else:
                # Anonymous poll answer or channel
                return None
        
        # No user_id means anonymous/channel update
        if user_id is None:
            return None
        
        # Check authorization - USE CORRECT METHOD NAME
        if not db.is_user_authorized(user_id):  # ← FIXED: was is_authorized
            # Send unauthorized message if context available
            if context and hasattr(update, 'message') and update.message:
                await update.message.reply_text(
                    "❌ Unauthorized\n\n"
                    "Contact admin for access."
                )
            return None
        
        # User is authorized, execute function
        return await func(*args, **kwargs)
    
    return wrapper
