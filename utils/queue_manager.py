"""
Task Queue Manager - WITH GHOST BUG FIX
Manages task queue and processing state
Automatically clears stuck tasks
"""

import asyncio
import time
from typing import Optional, Dict, Any
from collections import deque

class TaskQueue:
    def __init__(self):
        self.queue = deque()  # Queue of tasks
        self.processing = {}  # {user_id: start_time}
        print("✅ Task Queue initialized")
    
    def add_task(self, user_id: int, state: Dict, context):
        """Add task to queue"""
        self.queue.append({
            'user_id': user_id,
            'state': state,
            'context': context,
            'added_at': time.time()
        })
        print(f"📋 Added task for user {user_id} to queue (pos: {len(self.queue)})")
    
    def get_next_task(self) -> Optional[Dict]:
        """Get next task from queue"""
        if self.queue:
            return self.queue.popleft()
        return None
    
    def is_in_queue(self, user_id: int) -> bool:
        """Check if user has task in queue"""
        return any(task['user_id'] == user_id for task in self.queue)
    
    def is_processing(self, user_id: int) -> bool:
        """Check if user task is currently processing"""
        return user_id in self.processing
    
    def set_processing(self, user_id: int, processing: bool):
        """Set processing state for user"""
        if processing:
            self.processing[user_id] = time.time()
            print(f"⚙️ Started processing for user {user_id}")
        else:
            # CRITICAL: Always use del to remove from dict
            if user_id in self.processing:
                del self.processing[user_id]
                print(f"✅ Completed processing for user {user_id}")
    
    def get_queue_position(self, user_id: int) -> Optional[int]:
        """Get user's position in queue (1-indexed)"""
        for idx, task in enumerate(self.queue, 1):
            if task['user_id'] == user_id:
                return idx
        return None
    
    def get_queue_length(self) -> int:
        """Get total queue length"""
        return len(self.queue)
    
    def clear_user(self, user_id: int):
        """Force clear user from queue and processing"""
        # Remove from queue
        self.queue = deque([task for task in self.queue if task['user_id'] != user_id])
        
        # Remove from processing
        if user_id in self.processing:
            del self.processing[user_id]
        
        print(f"🗑️ Cleared all tasks for user {user_id}")
    
    def _check_timeout(self, user_id: int = None):
        """Check for timed out tasks and clear them"""
        current_time = time.time()
        timeout = 300  # 5 minutes
        
        if user_id:
            # Check specific user
            if user_id in self.processing:
                start_time = self.processing[user_id]
                if current_time - start_time > timeout:
                    print(f"⏰ Task for user {user_id} timed out, clearing...")
                    del self.processing[user_id]
        else:
            # Check all processing tasks
            timed_out = []
            for uid, start_time in self.processing.items():
                if current_time - start_time > timeout:
                    timed_out.append(uid)
            
            for uid in timed_out:
                print(f"⏰ Task for user {uid} timed out, clearing...")
                del self.processing[uid]

# Global instance
task_queue = TaskQueue()