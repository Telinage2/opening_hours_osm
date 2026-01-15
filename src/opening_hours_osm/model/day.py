from typing import Optional, Union, Sequence
from dataclasses import dataclass, field
import enum
import datetime

from opening_hours_osm.model.util import (
    ModelBase,
    Bitfield,
    fmt_days_offset,
    fmt_offset,
    fmt_selector,
)


class Weekday(enum.Enum):
    Mo = 0
    Tu = 1
    We = 2
    Th = 3
    Fr = 4
    Sa = 5
    Su = 6

    def __str__(self) -> str:
        return self.name


@dataclass
class YearRange(ModelBase):
    start: int
    end: Optional[int] = None
    step: int = 1

    def __str__(self) -> str:
        res = str(self.start)
        if self.end is None:
            res += "+"
        elif self.start != self.end:
            res += f"-{self.end}"
        if self.step != 1:
            res += f"/{self.step}"
        return res


class Month(enum.Enum):
    Jan = 1
    Feb = 2
    Mar = 3
    Apr = 4
    May = 5
    Jun = 6
    Jul = 7
    Aug = 8
    Sep = 9
    Oct = 10
    Nov = 11
    Dez = 12

    def next(self) -> "Month":
        nv = self.value + 1
        if nv > 12:
            nv = 1
        return Month(nv)

    def __str__(self) -> str:
        return self.name


@dataclass
class MonthRange(ModelBase):
    start: Month
    end: Month
    year: Optional[int] = None

    def __str__(self) -> str:
        res = ""
        if self.year:
            res += f"{self.year} "
        res += str(self.start)
        if self.start != self.end:
            res += f"-{self.end}"
        return res


class WeekDayOffsetKind(enum.Enum):
    NONE = enum.auto()
    NEXT = enum.auto()
    PREV = enum.auto()


@dataclass
class WeekDayOffset(ModelBase):
    kind: WeekDayOffsetKind = WeekDayOffsetKind.NONE
    weekday: Weekday = Weekday.Mo

    def __str__(self) -> str:
        match self.kind:
            case WeekDayOffsetKind.NEXT:
                return f"+{self.weekday}"
            case WeekDayOffsetKind.PREV:
                return f"-{self.weekday}"
        return ""


@dataclass
class DateOffset(ModelBase):
    wday_offset: WeekDayOffset = field(default_factory=WeekDayOffset)
    day_offset: int = 0

    def apply(self, date: datetime.date) -> datetime.date:
        res = date + datetime.timedelta(days=self.day_offset)

        match self.wday_offset.kind:
            case WeekDayOffsetKind.PREV:
                diff = (7 + date.weekday() - self.wday_offset.weekday.value) % 7
                res -= datetime.timedelta(days=diff)
                assert res.weekday() == self.wday_offset.weekday.value
            case WeekDayOffsetKind.NEXT:
                diff = (7 + self.wday_offset.weekday.value - date.weekday()) % 7
                res += datetime.timedelta(days=diff)
                assert res.weekday() == self.wday_offset.weekday.value

        return res

    def __str__(self) -> str:
        res = str(self.wday_offset)
        res += fmt_days_offset(self.day_offset)
        return res


@dataclass
class CalendarDate(ModelBase):
    year: Optional[int]
    month: Month
    day: int

    def __str__(self) -> str:
        res = ""
        if self.year is not None:
            res += f"{self.year} "
        res += f"{self.month} {self.day}"
        return res


class VariableDateKind(enum.Enum):
    EASTER = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class VariableDate(ModelBase):
    kind: VariableDateKind = VariableDateKind.EASTER
    year: Optional[int] = None

    def __str__(self) -> str:
        res = ""
        if self.year is not None:
            res += f"{self.year} "
        res += str(self.kind)
        return res


type DateUnion = CalendarDate | VariableDate


@dataclass
class DateRange(ModelBase):
    start_date: DateUnion
    start_offset: DateOffset
    end_date: DateUnion
    end_offset: DateOffset

    def __str__(self) -> str:
        res = f"{self.start_date}{self.start_offset}"
        if self.start_date != self.end_date or self.start_offset != self.end_offset:
            res += f"-{self.end_date}{self.end_offset}"
        return res


type MonthdayRange = Union[MonthRange, DateRange]


@dataclass
class WeekRange(ModelBase):
    start: int
    end: int
    step: int = 1

    def __str__(self) -> str:
        if self.start == self.end and self.step == 1:
            return f"{self.start:02}"

        res = f"{self.start:02}-{self.end:02}"
        if self.step != 1:
            res += f"/{self.step}"
        return res


@dataclass
class WeekDayRange(ModelBase):
    start: Weekday
    end: Weekday
    offset: int = 0
    nth_from_start: Bitfield = field(default_factory=Bitfield)
    nth_from_end: Bitfield = field(default_factory=Bitfield)

    def __str__(self) -> str:
        res = str(self.start)

        if self.start != self.end:
            res += f"-{self.end}"

        if self.nth_from_start.contains(False) or self.nth_from_end.contains(False):
            weeknums = [str(p + 1) for p in self.nth_from_start.set_positions()] + [
                str(-p - 1) for p in self.nth_from_end.set_positions()
            ]
            res += "[" + ",".join(weeknums) + "]"

        res += fmt_days_offset(self.offset)
        return res


class HolidayKind(enum.Enum):
    PH = enum.auto()
    SH = enum.auto()

    def __str__(self) -> str:
        return self.name


@dataclass
class HolidayRange(ModelBase):
    kind: HolidayKind
    offset: int = 0

    def __str__(self) -> str:
        res = str(self.kind)
        res += fmt_offset(self.offset)
        return res


type WeekDayRangeUnion = Union[WeekDayRange, HolidayRange]


@dataclass
class DaySelector(ModelBase):
    year: Sequence[YearRange] = field(default_factory=list)
    monthday: Sequence[MonthdayRange] = field(default_factory=list)
    week: Sequence[WeekRange] = field(default_factory=list)
    weekday: Sequence[WeekDayRangeUnion] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            not self.year and not self.monthday and not self.week and not self.weekday
        )

    def __str__(self) -> str:
        res = ""
        if self.year or self.monthday or self.week:
            res += fmt_selector(self.year)
            res += fmt_selector(self.monthday)

            if self.week:
                if self.year or self.monthday:
                    res += " "
                res += "week"
                res += fmt_selector(self.week)

            if self.weekday:
                res += " "
        res += fmt_selector(self.weekday)
        return res
