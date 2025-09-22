"""A thread-safe, fixed-capacity ring buffer."""

import threading
from collections import deque


class Ring:
    """A thread-safe, fixed-capacity ring buffer for LSL chunks.

    This class implements a deque-based ring buffer with a configurable drop
    policy (either drop oldest or reject newest when full). It is designed to
    be thread-safe for one producer and one consumer.

    Attributes:
        q (collections.deque): The underlying deque instance.
        capacity (int): The maximum capacity of the ring buffer.
        drop_oldest (bool): If True, the oldest item is dropped when the buffer is full.
            If False, the newest item is rejected.
        lock (threading.Lock): Lock to ensure thread safety.
        drops (int): Counter for the number of dropped or rejected items.
    """

    def __init__(self, capacity: int, drop_oldest: bool = True) -> None:
        """Initialize the Ring buffer.

        Args:
            capacity (int): The maximum number of items the ring can hold.
            drop_oldest (bool): The policy for handling a full buffer. If True, the
                oldest item is overwritten. If False, the new item is rejected.
        """
        self.q = deque(maxlen=capacity if drop_oldest else None)
        self.capacity = capacity
        self.drop_oldest = drop_oldest
        self.lock = threading.Lock()
        self.drops = 0  # count of overwritten or rejected items

    def push(self, item: object) -> bool:
        """Add an item to the ring buffer.

        If the buffer is full, it either drops the oldest item or rejects the
        new item based on the drop_oldest policy.

        Args:
            item (object): The item to be added to the buffer.

        Returns:
            bool: True if the item was added, False if it was rejected.
        """
        with self.lock:
            if not self.drop_oldest and len(self.q) >= self.capacity:
                self.drops += 1  # reject newest
                return False
            # Check if buffer was full before appending (to count overwrites)
            before_full = (len(self.q) == self.q.maxlen) if self.q.maxlen else False
            self.q.append(item)
            if self.q.maxlen and before_full:
                self.drops += 1  # leftmost overwritten
            return True

    def drain_upto(self, max_items: int) -> list:
        """Remove and return up to a specified number of items from the buffer.

        This method drains items from the left (oldest) of the buffer.

        Args:
            max_items (int): The maximum number of items to remove.

        Returns:
            list: Items from the buffer, containing at most max_items items.
        """
        items = []
        # Remove up to max_items from the left (oldest) of the buffer
        with self.lock:
            for _ in range(min(max_items, len(self.q))):
                items.append(self.q.popleft())
        return items
