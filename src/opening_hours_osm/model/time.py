from typing import Optional, Self, Union, Sequence, Iterator, TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime

from opening_hours_osm.model.enums import TimeEvent
from opening_hours_osm.model.util import ModelBase, fmt_selector
from opening_hours_osm.context import Context
from opening_hours_osm.util import OsmParsingException, range_intersection, ranges_union


@dataclass
class NaiveTimeSelectorIterator:
    date: datetime.date
    ctx: Context
    inner: Iterator["TimeSpan"]

    def __iter__(self) -> Iterator[tuple["ExtendedTime", "ExtendedTime"]]:
        return self

    def __next__(self) -> tuple["ExtendedTime", "ExtendedTime"]:
        span = next(self.inner)
        return span.as_naive(self.date, self.ctx)


_T = TypeVar("_T")


class TimeFilter[_T](ABC):
    def is_immutable_full_day(self) -> bool:
        return False

    @abstractmethod
    def as_naive(self, date: datetime.date, ctx: Context) -> _T: ...


class ExtendedTime(ModelBase, TimeFilter["ExtendedTime"]):
    def __init__(self, hour: int, minute: int) -> None:
        self.__check(hour, minute)
        self.hour = hour
        self.minute = minute

    @staticmethod
    def __check(hour: int, minute: int):
        if hour > 48 or hour < 0:
            raise OsmParsingException("hour out of range")
        if minute > 59 or minute < 0 or (hour == 48 and minute > 0):
            raise OsmParsingException("minute out of range")

    @staticmethod
    def __is_out_of_range(hour: int, minute: int) -> bool:
        return (
            hour > 48
            or hour < 0
            or minute > 59
            or minute < 0
            or (hour == 48 and minute > 0)
        )

    @classmethod
    def from_sys(cls, time: datetime.time) -> Self:
        return cls(time.hour, time.minute)

    def to_sys(self) -> datetime.time:
        return datetime.time(self.hour, self.minute)

    def add_minutes(self, minutes: int) -> Self:
        return type(self)(self.hour, self.minute + minutes)

    def add_minutes_opt(self, minutes: int) -> Optional[Self]:
        if self.__is_out_of_range(self.hour, self.minute + minutes):
            return None
        return type(self)(self.hour, self.minute + minutes)

    def add_hours_opt(self, hours: int) -> Optional[Self]:
        if self.__is_out_of_range(self.hour + hours, self.minute):
            return None
        return type(self)(self.hour + hours, self.minute)

    def add_hours(self, hours: int) -> Self:
        return type(self)(self.hour + hours, self.minute)

    def mins_from_midnight(self) -> int:
        """Get the total number of minutes from *00:00*."""
        return self.minute + 60 * self.hour

    @classmethod
    def from_mins_from_midnight(cls, mins: int) -> Self:
        hour = int(mins / 60)
        minute = mins % 60
        return cls(hour, minute)

    def as_naive(self, date: datetime.date, ctx: Context) -> "ExtendedTime":
        return self

    def __str__(self) -> str:
        return f"{self.hour:02}:{self.minute:02}"

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, ExtendedTime)
            and self.hour == value.hour
            and self.minute == value.minute
        )

    def __lt__(self, value: object) -> bool:
        if not isinstance(value, ExtendedTime):
            raise TypeError("can only compare to ExtendedTime")
        return self.mins_from_midnight() < value.mins_from_midnight()

    def __gt__(self, value: object) -> bool:
        if not isinstance(value, ExtendedTime):
            raise TypeError("can only compare to ExtendedTime")
        return self.mins_from_midnight() > value.mins_from_midnight()

    def __ge__(self, value: object) -> bool:
        if not isinstance(value, ExtendedTime):
            raise TypeError("can only compare to ExtendedTime")
        return self.mins_from_midnight() >= value.mins_from_midnight()

    def __le__(self, value: object) -> bool:
        if not isinstance(value, ExtendedTime):
            raise TypeError("can only compare to ExtendedTime")
        return self.mins_from_midnight() <= value.mins_from_midnight()


MIDNIGHT_00 = ExtendedTime(0, 0)
MIDNIGHT_24 = ExtendedTime(24, 0)
MIDNIGHT_48 = ExtendedTime(48, 0)


@dataclass
class Duration(ModelBase):
    def __init__(self, hours: int, minutes: int) -> None:
        self.hours = hours + int(minutes / 60)
        self.minutes = minutes % 60

    def __str__(self) -> str:
        return f"{self.hours:02}:{self.minutes:02}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)})"


@dataclass
class VariableTime(ModelBase, TimeFilter[ExtendedTime]):
    event: TimeEvent
    offset: int

    def as_naive(self, date: datetime.date, ctx: Context) -> ExtendedTime:
        t = ctx.locale.event_time(date, self.event)
        return (
            ExtendedTime(t.hour, t.minute).add_minutes_opt(self.offset) or MIDNIGHT_00
        )

    def __str__(self) -> str:
        res = str(self.event)
        if self.offset < 0:
            res += str(self.offset)
        elif self.offset > 0:
            res += f"+{self.offset}"
        return res


type TimeUnion = Union[ExtendedTime, VariableTime]


@dataclass
class TimeSpan(ModelBase, TimeFilter[tuple[ExtendedTime, ExtendedTime]]):
    start: TimeUnion
    end: TimeUnion
    open_end: bool = False
    repeats: Optional[Duration] = None
    """
    This notation describes a repeated event:

    10:00-16:00/90 and 10:00-16:00/01:30 are evaluated as "from ten am to four pm every 1½ hours". Especially departure times can be written very concise and compact using this notation. The interval time following the "/" is valid but ignored for opening_hours.
    """

    def is_immutable_full_day(self) -> bool:
        return (
            self.start == MIDNIGHT_00
            and self.end == MIDNIGHT_24
            and not self.open_end
            and self.repeats is None
        )

    def as_naive(
        self, date: datetime.date, ctx: Context
    ) -> tuple[ExtendedTime, ExtendedTime]:
        start = self.start.as_naive(date, ctx)
        end = self.end.as_naive(date, ctx)

        # If end < start, it actually wraps to next day
        if start >= end:
            end = end.add_hours_opt(24)
            assert end, "overflow during TimeSpan resolution"

        assert start <= end
        return start, end

    def __str__(self) -> str:
        res = str(self.start)

        if not self.open_end or self.end != MIDNIGHT_24:
            res += f"-{self.end}"
        if self.open_end:
            res += "+"
        if self.repeats is not None:
            res += "/"
            if self.repeats.hours > 0:
                res += f"{self.repeats.hours:02}:"
            res += f"{self.repeats.minutes:02}"

        return res


@dataclass
class TimeSelector(ModelBase, TimeFilter[NaiveTimeSelectorIterator]):
    time: Sequence[TimeSpan] = field(
        default_factory=lambda: [TimeSpan(MIDNIGHT_00, MIDNIGHT_24)]
    )

    def __init__(self, time: Optional[list[TimeSpan]] = None) -> None:
        if not time:
            self.time = [TimeSpan(MIDNIGHT_00, MIDNIGHT_24)]
        else:
            self.time = time

    def is_00_24(self) -> bool:
        return len(self.time) == 1 and self.time[0] == TimeSpan(
            MIDNIGHT_00, MIDNIGHT_24
        )

    def is_immutable_full_day(self) -> bool:
        return all(span.is_immutable_full_day() for span in self.time)

    def as_naive(self, date: datetime.date, ctx: Context) -> NaiveTimeSelectorIterator:
        return NaiveTimeSelectorIterator(date, ctx, iter(self.time))

    def intervals_at(
        self, date: datetime.date, ctx: Context
    ) -> Iterator[tuple[ExtendedTime, ExtendedTime]]:
        return ranges_union(
            (
                x
                for x in (
                    range_intersection(r, (MIDNIGHT_00, MIDNIGHT_24))
                    for r in self.as_naive(date, ctx)
                )
                if x is not None
            )
        )

    def intervals_at_next_day(
        self, date: datetime.date, ctx: Context
    ) -> Iterator[tuple[ExtendedTime, ExtendedTime]]:
        return ranges_union(
            (
                (x[0].add_hours(-24), x[1].add_hours(-24))
                for x in (
                    range_intersection(r, (MIDNIGHT_24, MIDNIGHT_48))
                    for r in self.as_naive(date, ctx)
                )
                if x is not None
            )
        )

    def __str__(self) -> str:
        return fmt_selector(self.time)
