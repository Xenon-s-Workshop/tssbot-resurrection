import os
from pathlib import Path


class Config:
    # Core
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

    # Paths
    TEMP_DIR = Path("temp")
    OUTPUT_DIR = Path("output")
    FONTS_DIR = Path("fonts")

    # Processing
    MAX_CONCURRENT_IMAGES = 10
    MAX_QUEUE_SIZE = 20
    GEMINI_MODEL = "gemini-2.0-flash-exp"
    POLL_DELAY = 1.5
    BATCH_SIZE = 30
    BATCH_DELAY = 5

    # ── Per-user defaults (overridable via /settings) ──────────────────
    # QUIZ_MARKER : prepended to every quiz question posted to a channel.
    #   Renders in Telegram poll as:
    #       [TSS]
    #
    #       What is the capital of France?
    DEFAULT_QUIZ_MARKER = os.getenv("QUIZ_MARKER", "[TSS]")

    # EXPLANATION_TAG : appended inside every explanation.
    #   Renders in Telegram poll explanation as:
    #       Paris is the capital of France. [t.me/tss]
    DEFAULT_EXPLANATION_TAG = os.getenv("EXPLANATION_TAG", "t.me/tss")

    DEFAULT_PDF_MODE = "inline"   # "inline" or "answer_key"

    GENERATION_CONFIG = {
        "temperature": 0.1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }

    SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    def __init__(self):
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required!")
        if not self.GEMINI_API_KEYS or self.GEMINI_API_KEYS == [""]:
            raise ValueError("GEMINI_API_KEYS environment variable is required!")
        self.TEMP_DIR.mkdir(exist_ok=True)
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        self.FONTS_DIR.mkdir(exist_ok=True)


config = Config()
