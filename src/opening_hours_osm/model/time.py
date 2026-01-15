from typing import Optional, Self, Union, Sequence
from dataclasses import dataclass, field
import enum

from opening_hours_osm.model.util import ModelBase, fmt_selector


class ExtendedTime(ModelBase):
    def __init__(self, hour: int, minute: int) -> None:
        self.__check(hour, minute)
        self.hour = hour
        self.minute = minute

    @staticmethod
    def __check(hour: int, minute: int):
        if hour > 48 or hour < 0:
            raise ValueError("hour out of range")
        if minute > 59 or minute < 0 or (hour == 48 and minute > 0):
            raise ValueError("minute out of range")

    def add_minutes(self, minutes: int):
        self.__check(self.hour, self.minute + minutes)
        self.minute += minutes

    def add_hours(self, hours: int):
        self.__check(self.hour + hours, self.minute)
        self.hour += hours

    def mins_from_midnight(self) -> int:
        """Get the total number of minutes from *00:00*."""
        return self.minute + 60 * self.hour

    @classmethod
    def from_mins_from_midnight(cls, mins: int) -> Self:
        hour = int(mins / 60)
        minute = mins % 60
        return cls(hour, minute)

    def __str__(self) -> str:
        return f"{self.hour:02}:{self.minute:02}"

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, ExtendedTime)
            and self.hour == value.hour
            and self.minute == value.minute
        )


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


class TimeEvent(enum.Enum):
    DAWN = enum.auto()
    SUNRISE = enum.auto()
    SUNSET = enum.auto()
    DUSK = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class VariableTime(ModelBase):
    event: TimeEvent
    offset: int

    def __str__(self) -> str:
        res = str(self.event)
        if self.offset < 0:
            res += str(self.offset)
        elif self.offset > 0:
            res += f"+{self.offset}"
        return res


type TimeUnion = Union[ExtendedTime, VariableTime]


@dataclass
class TimeSpan(ModelBase):
    start: TimeUnion
    end: TimeUnion
    open_end: bool = False
    repeats: Optional[Duration] = None

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
class TimeSelector(ModelBase):
    time: Sequence[TimeSpan] = field(
        default_factory=lambda: [TimeSpan(MIDNIGHT_00, MIDNIGHT_24)]
    )

    def __init__(self, time: Optional[list[TimeSpan]] = None) -> None:
        if time is None:
            self.time = [TimeSpan(MIDNIGHT_00, MIDNIGHT_24)]
        else:
            self.time = time

    def is_00_24(self) -> bool:
        return len(self.time) == 1 and self.time[0] == TimeSpan(
            MIDNIGHT_00, MIDNIGHT_24
        )

    def __str__(self) -> str:
        return fmt_selector(self.time)
