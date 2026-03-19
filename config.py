"""
Configuration Module - Complete Settings
All bot configuration and environment variables
"""

import os
from pathlib import Path

class Config:
    # Bot Information
    BOT_NAME = "TSS Bot"
    BOT_VERSION = "2.1.0"
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Gemini AI Configuration
    GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")
    GEMINI_MODEL = "gemini-2.0-flash-exp"
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    
    # Authorization Settings
    AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    SUDO_USER_IDS = [int(uid) for uid in os.getenv("SUDO_USER_IDS", "").split(",") if uid.strip()]
    
    # Quiz Posting Settings
    POLL_DELAY = 2  # Seconds between individual quizzes
    BATCH_SIZE = 10  # Number of quizzes per batch
    BATCH_DELAY = 5  # Seconds between batches
    
    # Live Quiz Settings
    DEFAULT_QUIZ_TIME = 10  # Seconds per question
    MAX_LEADERBOARD_DISPLAY = 15  # Max users to show in leaderboard
    
    # Task Queue Settings
    TASK_TIMEOUT = 300  # 5 minutes timeout for stuck tasks
    
    # Directory Configuration
    BASE_DIR = Path(__file__).parent
    TEMP_DIR = BASE_DIR / "temp"
    OUTPUT_DIR = BASE_DIR / "output"
    
    # Create directories if they don't exist
    TEMP_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Validation
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable not set")
    
    if not GEMINI_API_KEYS or not GEMINI_API_KEYS[0]:
        raise ValueError("❌ GEMINI_API_KEYS environment variable not set")
    
    # Display configuration
    print(f"✅ Configuration loaded: {BOT_NAME} v{BOT_VERSION}")
    print(f"   - Model: {GEMINI_MODEL}")
    print(f"   - API Keys: {len(GEMINI_API_KEYS)} configured")
    print(f"   - Auth: {'Enabled' if AUTH_ENABLED else 'Disabled'}")
    print(f"   - Sudo Users: {len(SUDO_USER_IDS)}")

# Create global config instance
config = Config()
