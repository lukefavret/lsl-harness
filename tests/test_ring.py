from lsl_harness.ring import Ring


def test_ring_overwrite_count():
    r = Ring(capacity=2, drop_oldest=True)
    r.push(1)
    r.push(2)
    r.push(3)  # overwrites one
    assert r.drops == 1
    items = r.drain_upto(10)
    assert items == [2, 3]
