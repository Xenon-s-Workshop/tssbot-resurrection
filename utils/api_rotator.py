import logging
from typing import List
from threading import Lock

logger = logging.getLogger(__name__)


class GeminiAPIRotator:
    """Round-robin API key rotator for Gemini."""

    def __init__(self, api_keys: List[str]):
        self.api_keys = [key.strip() for key in api_keys if key.strip()]
        self.current_index = 0
        self.lock = Lock()
        if not self.api_keys:
            raise ValueError("No valid Gemini API keys provided!")
        logger.info(f"✅ API Rotator initialized with {len(self.api_keys)} key(s)")

    def get_next_key(self) -> str:
        with self.lock:
            key = self.api_keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            return key
