"""
Configuration Module
All bot settings and environment variables
"""

import os
from pathlib import Path

class Config:
    # ==================== TELEGRAM BOT ====================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # ==================== GEMINI AI ====================
    # Get API keys from environment (comma-separated)
    GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")
    
    # ✅ CORRECT MODEL NAME - Use this for free tier (March 2026)
    GEMINI_MODEL = "gemini-2.5-flash"
    
    # Other valid free models (alternatives):
    # GEMINI_MODEL = "gemini-2.5-flash-lite"  # Faster, simpler tasks
    # GEMINI_MODEL = "gemini-2.5-pro"         # More complex reasoning
    
    # ==================== MONGODB ====================
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    
    # ==================== AUTHORIZATION ====================
    # Sudo user IDs (comma-separated in env var)
    SUDO_USER_IDS = [
        int(x.strip()) 
        for x in os.getenv("SUDO_USER_IDS", "").split(",") 
        if x.strip()
    ]
    
    # Enable/disable authorization
    AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    
    # ==================== BOT SETTINGS ====================
    BOT_NAME = "TSS Bot"
    BOT_VERSION = "2.0"  # ← ADDED THIS
    
    # ==================== DIRECTORIES ====================
    # Temporary file storage
    TEMP_DIR = Path("temp")
    
    # Output file storage
    OUTPUT_DIR = Path("output")
    
    # ==================== PROCESSING SETTINGS ====================
    # Maximum concurrent image processing tasks
    MAX_CONCURRENT_IMAGES = 10
    
    # Maximum queue size
    MAX_QUEUE_SIZE = 20
    
    # Task timeout (seconds)
    TASK_TIMEOUT = 300  # 5 minutes
    
    # ==================== QUIZ POSTING SETTINGS ====================
    # Delay between individual polls (seconds)
    POLL_DELAY = 1.5
    
    # Number of polls per batch
    BATCH_SIZE = 30
    
    # Delay between batches (seconds)
    BATCH_DELAY = 5
    
    # ==================== LIVE QUIZ SETTINGS ====================
    # Default time per question (seconds)
    DEFAULT_QUIZ_TIME = 10
    
    # Maximum players to show on leaderboard
    MAX_LEADERBOARD_DISPLAY = 15
    
    # ==================== POLL COLLECTION SETTINGS ====================
    # Maximum polls to collect
    MAX_POLLS_COLLECT = 200
    
    # Batch processing delay (seconds)
    POLL_BATCH_DELAY = 2
    
    # ==================== PDF EXPORT SETTINGS ====================
    # Maximum questions per page (standard format)
    PDF_QUESTIONS_PER_PAGE_STANDARD = 8
    
    # Maximum questions per page (detailed format)
    PDF_QUESTIONS_PER_PAGE_DETAILED = 5
    
    # ==================== INITIALIZATION ====================
    def __init__(self):
        """Validate configuration and create directories"""
        
        # Validate required settings
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN is required!")
        
        if not self.GEMINI_API_KEYS or self.GEMINI_API_KEYS == ['']:
            raise ValueError("❌ GEMINI_API_KEYS is required!")
        
        # Clean API keys (remove empty strings)
        self.GEMINI_API_KEYS = [
            key.strip() 
            for key in self.GEMINI_API_KEYS 
            if key.strip()
        ]
        
        if not self.GEMINI_API_KEYS:
            raise ValueError("❌ No valid GEMINI_API_KEYS found!")
        
        # Create directories
        self.TEMP_DIR.mkdir(exist_ok=True)
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        
        # Print configuration
        self._print_config()
    
    def _print_config(self):
        """Print configuration summary"""
        print("=" * 60)
        print(f"⚙️  {self.BOT_NAME} v{self.BOT_VERSION} Configuration")
        print("=" * 60)
        print(f"🤖 Gemini Model: {self.GEMINI_MODEL}")
        print(f"🔑 API Keys: {len(self.GEMINI_API_KEYS)} loaded")
        print(f"🔐 Auth: {'Enabled' if self.AUTH_ENABLED else 'Disabled'}")
        print(f"👑 Sudo Users: {len(self.SUDO_USER_IDS)}")
        print(f"📂 Temp Dir: {self.TEMP_DIR}")
        print(f"📂 Output Dir: {self.OUTPUT_DIR}")
        print(f"⚙️  Max Concurrent: {self.MAX_CONCURRENT_IMAGES}")
        print(f"📋 Max Queue Size: {self.MAX_QUEUE_SIZE}")
        print(f"⏱️  Task Timeout: {self.TASK_TIMEOUT}s")
        print("=" * 60)
        
        # Warnings
        if self.GEMINI_MODEL not in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]:
            print("⚠️  WARNING: You're using a non-standard model name!")
            print(f"⚠️  Current: {self.GEMINI_MODEL}")
            print(f"⚠️  Recommended: gemini-2.5-flash")
            print("=" * 60)

# ==================== GLOBAL INSTANCE ====================
# Create global config instance
config = Config()
