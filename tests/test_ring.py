"""Tests for the `Ring` buffer implementation.

This module validates core ring buffer behaviors: initialization, push semantics
with and without overwriting, draining under empty/partial/full states, thread
interaction safety, and correct accounting of dropped samples under both
`drop_oldest` policies. Each test focuses on a single aspect of the contract to
keep failures precise.
"""

import threading
import time

import pytest

from lsl_harness.ring import Ring


def test_ring_init():
    """Test ring buffer initialization."""
    r = Ring(capacity=10)
    assert r.capacity == 10
    assert r.drop_oldest is True
    assert r.drops == 0
    assert len(r.q) == 0

    r = Ring(capacity=5, drop_oldest=False)
    assert r.capacity == 5
    assert r.drop_oldest is False


def test_ring_push_not_full():
    """Test pushing items to a ring buffer that is not full."""
    r = Ring(capacity=3)
    assert r.push(1) is True
    assert r.push(2) is True
    assert list(r.q) == [1, 2]
    assert r.drops == 0


def test_ring_drain_empty():
    """Test draining from an empty ring buffer."""
    r = Ring(capacity=3)
    assert r.drain_upto(5) == []


def test_ring_drain_partially_full():
    """Test draining from a partially full ring buffer."""
    r = Ring(capacity=5)
    r.push(1)
    r.push(2)
    r.push(3)
    assert r.drain_upto(2) == [1, 2]
    assert list(r.q) == [3]
    assert r.drain_upto(5) == [3]
    assert list(r.q) == []


def test_ring_overwrite_oldest():
    """Test the drop_oldest=True policy."""
    r = Ring(capacity=3, drop_oldest=True)
    r.push(1)
    r.push(2)
    r.push(3)
    assert list(r.q) == [1, 2, 3]
    assert r.drops == 0

    # This push should overwrite the oldest item (1)
    assert r.push(4) is True
    assert list(r.q) == [2, 3, 4]
    assert r.drops == 1

    # This push should overwrite the oldest item (2)
    assert r.push(5) is True
    assert list(r.q) == [3, 4, 5]
    assert r.drops == 2

    items = r.drain_upto(10)
    assert items == [3, 4, 5]
    assert r.drops == 2


def test_ring_reject_newest():
    """Test the drop_oldest=False policy."""
    r = Ring(capacity=3, drop_oldest=False)
    r.push(1)
    r.push(2)
    r.push(3)
    assert list(r.q) == [1, 2, 3]
    assert r.drops == 0

    # This push should be rejected
    assert r.push(4) is False
    assert list(r.q) == [1, 2, 3]
    assert r.drops == 1

    # This push should also be rejected
    assert r.push(5) is False
    assert list(r.q) == [1, 2, 3]
    assert r.drops == 2

    items = r.drain_upto(10)
    assert items == [1, 2, 3]
    assert r.drops == 2


def test_ring_thread_safety():
    """Basic test for thread safety without drops."""
    num_items = 2000
    r = Ring(capacity=num_items)

    def producer():
        for i in range(num_items):
            r.push(i)

    consumed_items = []

    def consumer_loop():
        # This loop will run until all items produced are consumed
        while len(consumed_items) < num_items:
            drained = r.drain_upto(10)
            if drained:
                consumed_items.extend(drained)
            else:
                # Give producer a chance to run
                time.sleep(0.0001)

    producer_thread = threading.Thread(target=producer)
    consumer_thread = threading.Thread(target=consumer_loop)

    producer_thread.start()
    consumer_thread.start()

    # Add a timeout to prevent tests from hanging
    producer_thread.join(timeout=5)
    consumer_thread.join(timeout=5)

    # Check if threads are still alive (which would indicate a timeout)
    assert not producer_thread.is_alive(), "Producer thread timed out"
    assert not consumer_thread.is_alive(), "Consumer thread timed out"

    assert len(r.q) == 0
    assert len(consumed_items) == num_items
    assert sorted(consumed_items) == list(range(num_items))


@pytest.mark.parametrize("drop_oldest, push_result", [(True, True), (False, False)])
def test_drops_counter(drop_oldest, push_result):
    """Test that the drops counter is incremented correctly."""
    r = Ring(capacity=2, drop_oldest=drop_oldest)
    r.push(1)
    r.push(2)
    assert r.drops == 0

    assert r.push(3) is push_result
    assert r.drops == 1

    assert r.push(4) is push_result
    assert r.drops == 2

    r.drain_upto(1)
    assert r.push(5) is True  # Should not drop, there is space
    assert r.drops == 2

    assert r.push(6) is push_result  # Should drop/reject again
    assert r.drops == 3
