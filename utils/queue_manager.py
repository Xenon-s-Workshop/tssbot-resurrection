import logging
from typing import Dict, Optional
from datetime import datetime
from threading import Lock
from config import config

logger = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self):
        self.queue = []
        self.lock = Lock()
        self.processing: Dict[int, Dict] = {}

    def add_task(self, user_id: int, task_data: Dict) -> int:
        with self.lock:
            if user_id in self.processing:
                return -2
            for task in self.queue:
                if task["user_id"] == user_id:
                    return -2
            if len(self.queue) >= config.MAX_QUEUE_SIZE:
                return -1
            self.queue.append({"user_id": user_id, "data": task_data, "timestamp": datetime.now()})
            return len(self.queue)

    def get_next_task(self) -> Optional[Dict]:
        with self.lock:
            if self.queue:
                return self.queue.pop(0)
            return None

    def get_position(self, user_id: int) -> int:
        with self.lock:
            for idx, task in enumerate(self.queue):
                if task["user_id"] == user_id:
                    return idx + 1
            return 0

    def is_processing(self, user_id: int) -> bool:
        with self.lock:
            return user_id in self.processing

    def set_processing(self, user_id: int, status: bool):
        with self.lock:
            if status:
                self.processing[user_id] = {"started": datetime.now()}
            else:
                self.processing.pop(user_id, None)

    def get_queue_size(self) -> int:
        with self.lock:
            return len(self.queue)

    def clear_user(self, user_id: int):
        with self.lock:
            self.queue = [t for t in self.queue if t["user_id"] != user_id]
            self.processing.pop(user_id, None)


task_queue = TaskQueue()
