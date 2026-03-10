"""
Authentication utilities - FIXED: Proper type checking for context
Decorators for requiring authorization and sudo access
"""

from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.ext._utils.types import CCT
from database import db

def _get_user_id(update: Update):
    """
    Safely extract user ID from various update types
    Returns None if user ID cannot be determined (e.g., channel posts)
    """
    # Check if update is actually an Update object
    if not isinstance(update, Update):
        return None
    
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
    """Decorator to require authentication - handles both functions and instance methods"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Handle instance methods: args[0] might be 'self'
        # Find the Update and Context objects in arguments
        update = None
        context = None
        
        for arg in args:
            if isinstance(arg, Update):
                update = arg
            # Check for context by checking if it has 'bot' attribute
            elif hasattr(arg, 'bot') and hasattr(arg, 'user_data'):
                context = arg
        
        # If no Update found in args, it might not be a handler
        if update is None:
            return await func(*args, **kwargs)
        
        user_id = _get_user_id(update)
        
        # Skip auth check if user_id cannot be determined
        if user_id is None:
            return
        
        # Check authorization
        if not db.is_authorized(user_id):
            # Only send message if it's a regular message/callback (not poll answer)
            if context and (update.message or update.callback_query):
                await context.bot.send_message(
                    user_id,
                    "🔒 *Access Denied*\n\nYou are not authorized to use this bot.\nContact an administrator.",
                    parse_mode='Markdown'
                )
            return
        
        return await func(*args, **kwargs)
    
    return wrapper

def require_sudo(func):
    """Decorator to require sudo access - handles both functions and instance methods"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Handle instance methods: args[0] might be 'self'
        # Find the Update and Context objects in arguments
        update = None
        context = None
        
        for arg in args:
            if isinstance(arg, Update):
                update = arg
            # Check for context by checking if it has 'bot' attribute
            elif hasattr(arg, 'bot') and hasattr(arg, 'user_data'):
                context = arg
        
        # If no Update found in args, it might not be a handler
        if update is None:
            return await func(*args, **kwargs)
        
        user_id = _get_user_id(update)
        
        # Skip sudo check if user_id cannot be determined
        if user_id is None:
            return
        
        # Check sudo access
        if not db.is_sudo(user_id):
            # Only send message if it's a regular message/callback (not poll answer)
            if context and (update.message or update.callback_query):
                await context.bot.send_message(
                    user_id,
                    "🔐 *Admin Access Required*\n\nThis command is only available to administrators.",
                    parse_mode='Markdown'
                )
            return
        
        return await func(*args, **kwargs)
    
    return wrapper
