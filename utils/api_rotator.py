"""
API Key Rotator - Rotates through multiple Gemini API keys
Handles rate limiting by switching keys
"""

import time
from typing import List

class APIRotator:
    def __init__(self, api_keys: List[str]):
        """
        Initialize API rotator with list of keys
        
        Args:
            api_keys: List of API keys to rotate through
        """
        if not api_keys or api_keys == ['']:
            raise ValueError("No API keys provided!")
        
        self.api_keys = [key.strip() for key in api_keys if key.strip()]
        self.current_index = 0
        self.key_failures = {key: 0 for key in self.api_keys}
        self.last_rotation = time.time()
        
        print(f"✅ API Rotator initialized with {len(self.api_keys)} keys")
    
    def get_current_key(self) -> str:
        """Get current API key"""
        return self.api_keys[self.current_index]
    
    def rotate(self):
        """Rotate to next API key"""
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        self.last_rotation = time.time()
        print(f"🔄 Rotated to API key #{self.current_index + 1}/{len(self.api_keys)}")
    
    def mark_failure(self, api_key: str = None):
        """
        Mark current or specific key as failed
        Automatically rotates if too many failures
        """
        key = api_key or self.get_current_key()
        
        if key in self.key_failures:
            self.key_failures[key] += 1
            print(f"⚠️ API key failure count: {self.key_failures[key]}")
            
            # Rotate if current key has failures
            if self.key_failures[key] >= 3:
                print(f"🔄 Auto-rotating due to failures")
                self.rotate()
    
    def reset_failures(self):
        """Reset failure counts for all keys"""
        self.key_failures = {key: 0 for key in self.api_keys}
        print("✅ Failure counts reset")
    
    def get_status(self) -> dict:
        """Get rotator status"""
        return {
            'total_keys': len(self.api_keys),
            'current_index': self.current_index,
            'failures': self.key_failures,
            'time_since_rotation': time.time() - self.last_rotation
        }
