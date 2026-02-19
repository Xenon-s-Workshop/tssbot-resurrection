from typing import List
from threading import Lock

class GeminiAPIRotator:
    def __init__(self, api_keys: List[str]):
        self.api_keys = [key.strip() for key in api_keys if key.strip()]
        self.current_index = 0
        self.lock = Lock()
        if not self.api_keys:
            raise ValueError("No valid API keys!")
    
    def get_next_key(self) -> str:
        with self.lock:
            key = self.api_keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            return key
