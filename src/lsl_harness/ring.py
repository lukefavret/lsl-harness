import threading
from collections import deque


class Ring:
    def __init__(self, capacity: int, drop_oldest: bool = True):
        self.q = deque(maxlen=capacity if drop_oldest else None)
        self.cap = capacity
        self.drop_oldest = drop_oldest
        self.lock = threading.Lock()
        self.drops = 0  # count of overwritten or rejected items

    def push(self, item):
        with self.lock:
            if not self.drop_oldest and len(self.q) >= self.cap:
                self.drops += 1  # reject newest
                return False
            before_full = (len(self.q) == self.q.maxlen) if self.q.maxlen else False
            self.q.append(item)
            if self.q.maxlen and before_full:
                self.drops += 1  # leftmost overwritten
            return True

    def drain_upto(self, max_items: int):
        items = []
        with self.lock:
            for _ in range(min(max_items, len(self.q))):
                items.append(self.q.popleft())
        return items
