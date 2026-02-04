from typing import Iterable, Iterator, Self
from dataclasses import dataclass, field
import datetime

from opening_hours_osm.model.time import ExtendedTime, MIDNIGHT_00, MIDNIGHT_24
from opening_hours_osm.model import RuleKind
from opening_hours_osm.util import Peekable, UniqueSortedList, map_opt


@dataclass
class TimeRange:
    start: ExtendedTime
    end: ExtendedTime
    kind: RuleKind
    comments: UniqueSortedList = field(default_factory=UniqueSortedList)

    def contains_time(self, time: datetime.time) -> bool:
        et = ExtendedTime.from_sys(time)
        return self.start <= et and self.end >= et


@dataclass
class Schedule:
    ranges: list[TimeRange]

    @classmethod
    def from_ranges(
        cls,
        ranges: Iterable[tuple[ExtendedTime, ExtendedTime]],
        kind: RuleKind,
        comments: UniqueSortedList = UniqueSortedList(),
    ):
        """Create a new schedule from a list of ranges of same kind and comment"""
        sched_ranges = [
            TimeRange(r[0], r[1], kind, comments) for r in ranges if r[0] < r[1]
        ]
        sched_ranges.sort(key=lambda r: r.start)

        i = 0
        while i + 1 < len(sched_ranges):
            if sched_ranges[i].end >= sched_ranges[i + 1].start:
                sched_ranges[i].end = sched_ranges[i + 1].end
                comments_left = sched_ranges[i].comments
                comments_right = sched_ranges.pop(i + i).comments
                sched_ranges[i].comments = comments_left.union(comments_right)
            else:
                i += 1

        return cls(sched_ranges)

    def is_empty(self) -> bool:
        """Check if a schedule is empty"""
        return not self.ranges

    def is_always_closed(self) -> bool:
        """Check if a schedule is always closed"""
        return all(r.kind == RuleKind.CLOSED for r in self.ranges)

    def addition(self, other: Self) -> Self:
        if other.is_empty():
            return self
        else:
            tr = other.ranges.pop()
            return self.insert(tr).addition(other)

    def insert(self, ins_tr: TimeRange) -> Self:
        # Build sets of intervals before and after the inserted interval
        before: list[TimeRange] = []
        after: list[TimeRange] = []
        for r in self.ranges:
            if r.start < ins_tr.end:
                range_end = min(r.end, ins_tr.start)
                if r.start < range_end:
                    before.append(TimeRange(r.start, range_end, r.kind, r.comments))
                else:
                    ins_tr.comments = ins_tr.comments.union(r.comments)
            if r.end > ins_tr.start:
                range_start = max(r.start, ins_tr.end)
                if range_start < r.end:
                    after.append(TimeRange(range_start, r.end, r.kind, r.comments))
                else:
                    ins_tr.comments = ins_tr.comments.union(r.comments)

        # Extend the inserted interval if it has adjacent intervals with same value
        while (
            before and before[-1].end == ins_tr.start and before[-1].kind == ins_tr.kind
        ):
            tr = before.pop()
            ins_tr.start = tr.start
            ins_tr.comments = tr.comments.union(ins_tr.comments)

        after_it = Peekable(after)
        while True:
            tr = after_it.peek()
            if tr is None or ins_tr.end != tr.start or ins_tr.kind != tr.kind:
                break
            tr = next(after_it)
            ins_tr.end = tr.end
            ins_tr.comments = tr.comments.union(ins_tr.comments)

        ranges = before
        ranges.append(ins_tr)
        ranges.extend(after_it)
        return type(self)(ranges)

    def __iter__(self) -> Iterator[TimeRange]:
        return ScheduleIterator(self)


class ScheduleIterator:
    def __init__(self, schedule: Schedule) -> None:
        self.ranges = Peekable(schedule.ranges)
        self.last_end = MIDNIGHT_00
        self.holes_state = RuleKind.CLOSED

    def __pre_yield(self, value: TimeRange) -> TimeRange:
        assert value.start < value.end, "Infinite loop detected"
        self.last_end = value.end
        return value

    def __iter__(self) -> Iterator[TimeRange]:
        return self

    def __next__(self) -> TimeRange:
        if self.last_end >= MIDNIGHT_24:
            raise StopIteration()

        next_start = map_opt(self.ranges.peek(), lambda x: x.start)
        if next_start == self.last_end:
            # Start from an interval
            yielded_range = next(self.ranges)
        else:
            # Start from a hole
            yielded_range = TimeRange(
                self.last_end, next_start or self.last_end, self.holes_state
            )

        while (next_range := self.ranges.peek()) is not None:
            if next_range.start > yielded_range.end:
                if yielded_range.kind == self.holes_state:
                    # Just extend the closed range with this hole
                    yielded_range.end = next_range.start
                else:
                    # The range before the hole is not closed
                    return self.__pre_yield(yielded_range)

            if yielded_range.kind != next_range.kind:
                # The next range has a different state
                return self.__pre_yield(yielded_range)

            next_range = next(self.ranges)
            yielded_range.end = next_range.end
            yielded_range.comments = yielded_range.comments.union(next_range.comments)

        if yielded_range.kind == self.holes_state:
            yielded_range.end = MIDNIGHT_24
        return self.__pre_yield(yielded_range)
