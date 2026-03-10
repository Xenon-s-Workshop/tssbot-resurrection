"""
Authentication utilities - FIXED: Safe poll answer handling
Decorators for requiring authorization and sudo access
"""

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from database import db

def _get_user_id(update: Update):
    """
    Safely extract user ID from various update types
    Returns None if user ID cannot be determined (e.g., channel posts)
    """
    # Regular message or callback from user
    if update.effective_user:
        return update.effective_user.id
    
    # Callback query
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    
    # Poll answer - FIXED: Check if poll_answer exists first
    if update.poll_answer and update.poll_answer.user:
        return update.poll_answer.user.id
    
    # Cannot determine user (e.g., channel post, anonymous poll)
    return None

def require_auth(func):
    """Decorator to require authentication"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = _get_user_id(update)
        
        # Skip auth check if user_id cannot be determined
        if user_id is None:
            return
        
        # Check authorization
        if not db.is_authorized(user_id):
            # Only send message if it's a regular message/callback (not poll answer)
            if update.message or update.callback_query:
                await context.bot.send_message(
                    user_id,
                    "🔒 *Access Denied*\n\nYou are not authorized to use this bot.\nContact an administrator.",
                    parse_mode='Markdown'
                )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def require_sudo(func):
    """Decorator to require sudo access"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = _get_user_id(update)
        
        # Skip sudo check if user_id cannot be determined
        if user_id is None:
            return
        
        # Check sudo access
        if not db.is_sudo(user_id):
            # Only send message if it's a regular message/callback (not poll answer)
            if update.message or update.callback_query:
                await context.bot.send_message(
                    user_id,
                    "🔐 *Admin Access Required*\n\nThis command is only available to administrators.",
                    parse_mode='Markdown'
                )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper
