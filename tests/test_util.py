from opening_hours_osm.util import Peekable, ranges_union

import pytest


def test_peekable():
    p = Peekable(range(5))

    for i in range(5):
        assert p.peek() == i
        assert p.peek() == i
        assert p.next_if(lambda x: x == i) == i

    assert p.peek() is None
    with pytest.raises(StopIteration):
        next(p)


def test_ranges_union():
    ru = list(ranges_union([(1, 3), (8, 10), (5, 8)]))
    assert ru == [(1, 3), (5, 10)]
