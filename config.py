import os
from pathlib import Path

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    SUDO_USER_IDS = [int(x.strip()) for x in os.getenv("SUDO_USER_IDS", "").split(",") if x.strip()]
    AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    BOT_NAME = "TSS Bot"
    TEMP_DIR = Path("temp")
    OUTPUT_DIR = Path("output")
    MAX_CONCURRENT_IMAGES = 10
    MAX_QUEUE_SIZE = 20
    GEMINI_MODEL = "gemini-2.0-flash"
    POLL_DELAY = 1.5
    BATCH_SIZE = 30
    BATCH_DELAY = 5
    
    def __init__(self):
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN required!")
        if not self.GEMINI_API_KEYS or self.GEMINI_API_KEYS == ['']:
            raise ValueError("GEMINI_API_KEYS required!")
        self.TEMP_DIR.mkdir(exist_ok=True)
        self.OUTPUT_DIR.mkdir(exist_ok=True)

config = Config()
