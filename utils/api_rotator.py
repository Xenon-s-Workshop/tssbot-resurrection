"""Gemini API Key Rotator"""
from google import genai

class GeminiAPIRotator:
    def __init__(self, api_keys):
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        self.current_index = 0
        print(f"✅ API Rotator: {len(self.api_keys)} keys")
    
    def get_client(self):
        """Get current API client"""
        key = self.api_keys[self.current_index]
        return genai.Client(api_key=key)
    
    def mark_failure(self):
        """Rotate to next key on failure"""
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        print(f"🔄 Rotated to key #{self.current_index + 1}")
