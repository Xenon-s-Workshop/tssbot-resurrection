"""
Queue Manager - GHOST BUG FIXED
Proper state management with timeout handling
"""

import time
from typing import Dict, Optional, Any
from collections import deque
from config import config

class TaskQueue:
    def __init__(self):
        self.queue = deque()
        self.processing = {}  # {user_id: {'status': bool, 'start_time': float}}
        self.max_size = config.MAX_QUEUE_SIZE
        self.timeout = 300  # 5 minutes timeout
        print("✅ Task Queue initialized")
    
    def add_task(self, user_id: int, task_data: Dict[str, Any]) -> int:
        """Add task to queue. Returns position or -1 if full, -2 if already processing"""
        # Check timeout first
        self._check_timeout(user_id)
        
        # Check if already processing
        if self.is_processing(user_id):
            print(f"⚠️ User {user_id} already has task processing")
            return -2
        
        # Check if already in queue
        for task in self.queue:
            if task['user_id'] == user_id:
                print(f"⚠️ User {user_id} already in queue")
                return -2
        
        # Check queue size
        if len(self.queue) >= self.max_size:
            print(f"❌ Queue full ({self.max_size})")
            return -1
        
        # Add to queue
        self.queue.append({
            'user_id': user_id,
            'data': task_data,
            'added_at': time.time()
        })
        
        position = len(self.queue)
        print(f"✅ Added user {user_id} to queue at position {position}")
        return position
    
    def get_next_task(self) -> Optional[Dict]:
        """Get next task from queue"""
        if not self.queue:
            return None
        
        task = self.queue.popleft()
        print(f"📤 Dequeued task for user {task['user_id']}")
        return task
    
    def set_processing(self, user_id: int, status: bool):
        """Set processing status for user - CRITICAL FIX FOR GHOST BUG"""
        if status:
            # Mark as processing
            self.processing[user_id] = {
                'status': True,
                'start_time': time.time()
            }
            print(f"▶️ START: User {user_id} processing")
        else:
            # CRITICAL: Always delete from dict when stopping
            if user_id in self.processing:
                del self.processing[user_id]
                print(f"✅ STOP: User {user_id} cleared from processing")
            else:
                print(f"⚠️ User {user_id} was not in processing dict")
    
    def is_processing(self, user_id: int) -> bool:
        """Check if user has task processing - with timeout check"""
        if user_id not in self.processing:
            return False
        
        # Check timeout
        if self._check_timeout(user_id):
            return False
        
        return self.processing[user_id]['status']
    
    def _check_timeout(self, user_id: int) -> bool:
        """Check if task has timed out and force clear if needed"""
        if user_id not in self.processing:
            return False
        
        elapsed = time.time() - self.processing[user_id]['start_time']
        if elapsed > self.timeout:
            print(f"⏱️ TIMEOUT: User {user_id} task exceeded {self.timeout}s - force clearing")
            del self.processing[user_id]
            return True
        
        return False
    
    def clear_user(self, user_id: int):
        """Force clear user from queue and processing - GHOST BUG FIX"""
        # Remove from queue
        self.queue = deque([task for task in self.queue if task['user_id'] != user_id])
        
        # CRITICAL: Always delete from processing dict
        if user_id in self.processing:
            del self.processing[user_id]
            print(f"🗑️ FORCE CLEAR: User {user_id} removed from processing")
        
        print(f"🗑️ User {user_id} cleared from queue and processing")
    
    def get_position(self, user_id: int) -> int:
        """Get user position in queue. Returns 0 if not in queue"""
        for idx, task in enumerate(self.queue, 1):
            if task['user_id'] == user_id:
                return idx
        return 0
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return len(self.queue)
    
    def get_status_summary(self) -> str:
        """Debug method to see full status"""
        return (
            f"Queue: {len(self.queue)} tasks\n"
            f"Processing: {len(self.processing)} users\n"
            f"Processing IDs: {list(self.processing.keys())}"
        )

# Global instance
task_queue = TaskQueue()
