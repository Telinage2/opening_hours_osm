from typing import Sequence
from dataclasses import dataclass
import enum

from opening_hours_osm.model import day, time  # noqa: F401
from opening_hours_osm.model.day import DaySelector
from opening_hours_osm.model.time import TimeSelector
from opening_hours_osm.model.util import ModelBase


class RuleKind(enum.Enum):
    OPEN = enum.auto()
    CLOSED = enum.auto()
    UNKNOWN = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()


class RuleOperator(enum.Enum):
    NORMAL = enum.auto()
    ADDITIONAL = enum.auto()
    FALLBACK = enum.auto()

    def _separator(self):
        match self:
            case self.NORMAL:
                return "; "
            case self.ADDITIONAL:
                return ", "
            case self.FALLBACK:
                return " | "


@dataclass
class RuleSequence(ModelBase):
    day_selector: DaySelector
    time_selector: TimeSelector
    kind: RuleKind
    operator: RuleOperator
    comments: list[str]

    def is_constant(self) -> bool:
        return self.day_selector.is_empty() and self.time_selector.is_00_24()

    def __str__(self) -> str:
        is_empty = True
        res = ""

        if self.is_constant():
            is_empty = False
            res += "24/7"
        else:
            is_empty = self.day_selector.is_empty()
            res += str(self.day_selector)

            if not self.time_selector.is_00_24():
                if not is_empty:
                    res += " "
                is_empty = is_empty and self.time_selector.is_00_24()
                res += str(self.time_selector)

        if self.kind != RuleKind.OPEN:
            if not is_empty:
                res += " "
            is_empty = False
            res += str(self.kind)

        if self.comments:
            if not is_empty:
                res += " "
            res += ", ".join(self.comments)

        return res


@dataclass
class OpeningHoursExpression(ModelBase):
    rules: Sequence[RuleSequence]

    def is_constant(self) -> bool:
        """
        Check if this expression is *trivially* constant (ie. always evaluated at the exact same
        status). Note that this may return `false` for an expression that is constant but should
        cover most common cases.
        """
        if not self.rules:
            return True

        kind = self.rules[-1].kind

        # Ignores rules from the end as long as they are all evaluated to the same kind.
        search_tail_full = None
        for rs in reversed(self.rules):
            if (
                rs.day_selector.is_empty()
                or not rs.time_selector.is_00_24()
                or rs.kind != kind
            ):
                search_tail_full = rs
                break

        if search_tail_full is None:
            return kind == RuleKind.CLOSED

        return search_tail_full.kind == kind and search_tail_full.is_constant()

    def __str__(self) -> str:
        if not self.rules:
            return "closed"

        res = str(self.rules[0])

        for rule in self.rules[1:]:
            res += rule.operator._separator()
            res += str(rule)

        return res
