from opening_hours_osm.model.util import Bitfield

def test_bitfield():
    bf = Bitfield()
    assert not bf
    assert False in bf

    bf.set(0, True)
    assert bf.get(0)
    assert bf.v == 0b1
    assert bf
    assert False in bf

    bf.set(1, True)
    assert bf.get(1)
    assert bf.v == 0b11

    bf.set(4, True)
    assert bf.get(4)
    assert bf.v == 0b10011

    bf.set(1, False)
    assert not bf.get(1)
    assert bf.v == 0b10001
