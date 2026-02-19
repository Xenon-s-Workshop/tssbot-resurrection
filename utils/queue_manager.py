"""
Queue Manager - FIXED VERSION
- Ghost bug eliminated with proper cleanup
- Timeout handling for stuck tasks
- Proper state management
"""

from typing import Dict, Optional
from datetime import datetime
import time
from threading import Lock
from config import config

class TaskQueue:
    def __init__(self):
        self.queue = []
        self.lock = Lock()
        self.processing = {}  # {user_id: {'started': datetime, 'timestamp': float}}
        print("✅ Queue Manager initialized")
    
    def add_task(self, user_id: int, task_data: Dict) -> int:
        """Add task to queue. Returns: position (>0), -1 (full), -2 (already queued/processing)"""
        with self.lock:
            # Check if processing - with timeout detection
            if user_id in self.processing:
                proc_info = self.processing[user_id]
                elapsed = time.time() - proc_info.get('timestamp', 0)
                if elapsed > 300:  # 5 minutes timeout
                    print(f"⏰ TIMEOUT: Clearing stale task for user {user_id} ({elapsed:.0f}s)")
                    del self.processing[user_id]
                else:
                    print(f"⚠️ User {user_id} is already processing (elapsed: {elapsed:.0f}s)")
                    return -2
            
            # Check if in queue
            for task in self.queue:
                if task['user_id'] == user_id:
                    print(f"⚠️ User {user_id} already in queue")
                    return -2
            
            # Check queue size
            if len(self.queue) >= config.MAX_QUEUE_SIZE:
                print(f"❌ Queue full ({len(self.queue)}/{config.MAX_QUEUE_SIZE})")
                return -1
            
            # Add to queue
            self.queue.append({
                'user_id': user_id,
                'data': task_data,
                'timestamp': datetime.now(),
                'added_at': time.time()
            })
            position = len(self.queue)
            print(f"✅ User {user_id} added to queue at position {position}")
            return position
    
    def get_next_task(self) -> Optional[Dict]:
        """Get next task from queue"""
        with self.lock:
            if self.queue:
                task = self.queue.pop(0)
                print(f"📤 Dequeued task for user {task['user_id']}")
                return task
            return None
    
    def get_position(self, user_id: int) -> int:
        """Get user's position in queue. Returns 0 if not in queue."""
        with self.lock:
            for idx, task in enumerate(self.queue):
                if task['user_id'] == user_id:
                    return idx + 1
            return 0
    
    def is_processing(self, user_id: int) -> bool:
        """Check if user is currently being processed"""
        with self.lock:
            if user_id in self.processing:
                # Double-check for timeout
                proc_info = self.processing[user_id]
                elapsed = time.time() - proc_info.get('timestamp', 0)
                if elapsed > 300:
                    print(f"⏰ Removing stale processing flag for user {user_id}")
                    del self.processing[user_id]
                    return False
                return True
            return False
    
    def set_processing(self, user_id: int, status: bool):
        """
        CRITICAL FIX: Proper state management
        Set status=True when starting, status=False when done
        """
        with self.lock:
            if status:
                # Start processing
                self.processing[user_id] = {
                    'started': datetime.now(),
                    'timestamp': time.time()
                }
                print(f"▶️ START: User {user_id} processing started")
            else:
                # Stop processing - ALWAYS CLEAR
                if user_id in self.processing:
                    elapsed = time.time() - self.processing[user_id].get('timestamp', 0)
                    del self.processing[user_id]
                    print(f"✅ STOP: User {user_id} processing completed ({elapsed:.1f}s) - STATE CLEARED")
                else:
                    print(f"⚠️ WARN: User {user_id} not in processing dict (already cleared or never started)")
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        with self.lock:
            return len(self.queue)
    
    def clear_user(self, user_id: int):
        """FORCE CLEAR: Remove user from queue and processing"""
        with self.lock:
            # Clear from queue
            original_size = len(self.queue)
            self.queue = [t for t in self.queue if t['user_id'] != user_id]
            removed_from_queue = original_size - len(self.queue)
            
            # Clear from processing
            was_processing = user_id in self.processing
            if was_processing:
                del self.processing[user_id]
            
            print(f"🗑️ FORCE CLEAR: User {user_id} - "
                  f"Removed from queue: {removed_from_queue}, "
                  f"Was processing: {was_processing}")
    
    def get_status_summary(self) -> str:
        """Get queue status for debugging"""
        with self.lock:
            queue_users = [t['user_id'] for t in self.queue]
            processing_users = list(self.processing.keys())
            return (f"Queue: {queue_users} ({len(queue_users)} tasks), "
                   f"Processing: {processing_users} ({len(processing_users)} users)")

task_queue = TaskQueue()
