from typing import Sequence
import enum
import datetime
from dataclasses import dataclass

from opening_hours_osm.model.enums import RuleKind


class ModelBase:
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)})"


class Sign(enum.IntEnum):
    PLUS = 1
    MINUS = -1


@dataclass
class DateTimeRange:
    start: datetime.datetime
    end: datetime.datetime
    kind: RuleKind
    comments: list[str]


def fmt_offset(offset: int) -> str:
    res = ""
    if offset != 0:
        res += " "
        res += " "
        if offset > 0:
            res += "+"
        res += str(offset)
    return res


def fmt_days_offset(offset: int) -> str:
    res = ""
    if offset != 0:
        res += " "
        if offset > 0:
            res += "+"
        res += f"{offset} day"
        if abs(offset) > 1:
            res += "s"

    return res


def fmt_selector(seq: Sequence) -> str:
    res = ""
    if seq:
        res += str(seq[0])
        for elm in seq[1:]:
            res += f", {elm}"
    return res


class Bitfield:
    def __init__(self, len=5) -> None:
        if len < 1:
            raise ValueError("len must be at least 1")
        self.v = 0
        self.len = len

    def _check_i(self, i: int):
        if i < 0 or i >= self.len:
            raise ValueError(f"index out of range; len={self.len}")

    def set(self, i: int, val: bool):
        self._check_i(i)
        if val:
            self.v |= 1 << i
        else:
            self.v ^= 1 << i

    def get(self, i: int) -> bool:
        return bool(self.v & (1 << i))

    def contains(self, val: bool) -> bool:
        if val:
            return bool(self.v)
        else:
            return self.v != (1 << self.len) - 1

    def set_positions(self) -> list[int]:
        res = []
        for i in range(self.len):
            if self.get(i):
                res.append(i)
        return res

    def set_all(self, val: bool):
        if val:
            self.v = (1 << self.len) - 1
        else:
            self.v = 0

    def __eq__(self, value: object, /) -> bool:
        return isinstance(value, Bitfield) and self.v == value.v
