"""Task Queue Manager"""
import time
from collections import deque

class TaskQueue:
    def __init__(self):
        self.queue = deque()
        self.processing = {}
        print("✅ Task Queue initialized")
    
    def add_task(self, user_id, state, context):
        self.queue.append({'user_id': user_id, 'state': state, 'context': context, 'added_at': time.time()})
        print(f"📋 Task added for user {user_id}")
    
    def get_next_task(self):
        return self.queue.popleft() if self.queue else None
    
    def is_in_queue(self, user_id):
        return any(t['user_id'] == user_id for t in self.queue)
    
    def is_processing(self, user_id):
        return user_id in self.processing
    
    def set_processing(self, user_id, processing):
        if processing:
            self.processing[user_id] = time.time()
        else:
            self.processing.pop(user_id, None)
    
    def get_queue_position(self, user_id):
        for idx, task in enumerate(self.queue, 1):
            if task['user_id'] == user_id:
                return idx
        return None
    
    def get_queue_length(self):
        return len(self.queue)
    
    def clear_user(self, user_id):
        self.queue = deque([t for t in self.queue if t['user_id'] != user_id])
        self.processing.pop(user_id, None)
    
    def _check_timeout(self, user_id=None):
        timeout = 300
        now = time.time()
        if user_id and user_id in self.processing:
            if now - self.processing[user_id] > timeout:
                del self.processing[user_id]

task_queue = TaskQueue()
