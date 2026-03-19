"""Poll Collector"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class PollCollector:
    def __init__(self):
        self.application = None
        self.sessions = {}
        print("✅ Poll Collector initialized")
    
    def set_application(self, app):
        self.application = app
    
    async def start_collection(self, update, context):
        """Start poll collection"""
        user_id = update.effective_user.id
        
        self.sessions[user_id] = {
            'polls': [],
            'active': True
        }
        
        keyboard = [
            [InlineKeyboardButton("📊 Export CSV", callback_data="poll_export_csv")],
            [InlineKeyboardButton("📄 Export PDF", callback_data="poll_export_pdf")],
            [InlineKeyboardButton("🗑️ Clear", callback_data="poll_clear")],
            [InlineKeyboardButton("🛑 Stop", callback_data="poll_stop")]
        ]
        
        await update.message.reply_text(
            "📊 **Poll Collection Started**\n\n"
            "Forward polls to me. I'll collect results.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_export_csv(self, update, context):
        await update.callback_query.answer("CSV export coming soon")
    
    async def handle_export_pdf(self, update, context):
        await update.callback_query.answer("PDF export coming soon")
    
    async def handle_clear(self, update, context):
        user_id = update.effective_user.id
        if user_id in self.sessions:
            self.sessions[user_id]['polls'] = []
        await update.callback_query.answer("✅ Cleared")
    
    async def handle_stop(self, update, context):
        user_id = update.effective_user.id
        if user_id in self.sessions:
            del self.sessions[user_id]
        await update.callback_query.edit_message_text("🛑 **Collection Stopped**")

poll_collector = PollCollector()
