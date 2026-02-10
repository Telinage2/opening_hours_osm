from typing import Optional, Union, Sequence, TypeVar, Iterable, Iterator, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import enum
import datetime
import calendar
import math

from opening_hours_osm.context import Context
from opening_hours_osm.model.enums import HolidayKind
from opening_hours_osm.model.util import (
    ModelBase,
    Bitfield,
    fmt_days_offset,
    fmt_offset,
    fmt_selector,
)
from opening_hours_osm.util import (
    DATE_START,
    DATE_END,
    DATE_ZERO,
    Peekable,
    OsmParsingException,
    SupportsRichComparisonT,
    create_date_opt,
    next_day,
    next_day_opt,
    wrapping_contains,
)


T = TypeVar("T")
Df = TypeVar("Df", bound="DateFilter")


def filter_seq(seq: Sequence[Df], date: datetime.date, ctx: Context) -> bool:
    return not seq or any(x.filter(date, ctx) for x in seq)


def interval_contains(interval: "DateInterval", date: datetime.date) -> bool:
    return date >= interval[0] and date <= interval[1]


def ensure_increasing_iter(
    iterable: Iterable[SupportsRichComparisonT],
) -> Iterator[SupportsRichComparisonT]:
    it = iter(iterable)

    try:
        current = next(it)
    except StopIteration:
        return

    yield current

    for value in it:
        if value > current:
            current = value
            yield current


def intervals_from_bounds(
    bounds_start: Iterable[datetime.date], bounds_end: Iterable[datetime.date]
) -> Iterator["DateInterval"]:
    bstart = Peekable(ensure_increasing_iter(bounds_start))
    bend = Peekable(ensure_increasing_iter(bounds_end))

    while True:
        start = bstart.peek()
        if start is not None:
            while bend.next_if(lambda end: end < start) is not None:  # type: ignore
                pass

        range_start = bstart.peek()
        range_end = bend.peek()

        if range_start is None and range_end is None:
            break
        elif range_start is None and range_end is not None:
            next(bend)
            yield DATE_START.date(), range_end
        elif range_start is not None and range_end is None:
            next(bstart)
            yield range_start, DATE_END.date()
        elif range_start is not None and range_end is not None:
            if range_start == range_end:
                next(bend)
            next(bstart)
            yield range_start, range_end
        else:
            raise Exception("unreachable")


def is_open_from_intervals(
    date: datetime.date, intervals: Iterable["DateInterval"]
) -> bool:
    first_interval = next((x for x in intervals if x[1] >= date), None)
    if first_interval is None:
        return False
    return interval_contains(first_interval, date)


def is_open_from_bounds(
    date: datetime.date,
    bounds_start: Iterable[datetime.date],
    bounds_end: Iterable[datetime.date],
) -> bool:
    return is_open_from_intervals(date, intervals_from_bounds(bounds_start, bounds_end))


def next_change_from_intervals(
    date: datetime.date, intervals: Iterable["DateInterval"]
) -> datetime.date:
    first_interval = next((x for x in intervals if x[1] >= date), None)
    if first_interval is None:
        return DATE_END.date()
    if first_interval[0] <= date:
        return next_day(first_interval[1])
    else:
        return first_interval[0]


def next_change_from_bounds(
    date: datetime.date,
    bounds_start: Iterable[datetime.date],
    bounds_end: Iterable[datetime.date],
) -> datetime.date:
    """Find next change from iterators of "starting of an interval" to "end of an interval"."""
    return next_change_from_intervals(
        date, intervals_from_bounds(bounds_start, bounds_end)
    )


def date_on_year(
    date: "DateUnion",
    for_year: int,
    date_builder: Callable[[int, int, int], datetime.date],
) -> Optional[datetime.date]:
    """Project date on a given year"""
    if isinstance(date, VariableDate):
        return date.to_date(for_year)
    elif date.year is None:
        return date_builder(for_year, date.month, date.day)
    else:
        return date_builder(date.year, date.month, date.day)


def valid_ymd_before(year: int, month: int, day: int) -> datetime.date:
    """Get the first valid date before given "yyyy/mm/dd", for example if 2021/02/30 is given, this
    will return february 28th as 2021 is not a leap year.
    """
    d = create_date_opt(year, month, day)
    if d is not None:
        return d

    for x in reversed(range(28, day)):
        d = create_date_opt(year, month, x)
        if d is not None:
            return d

    return DATE_END.date()


def valid_ymd_after(year: int, month: int, day: int) -> datetime.date:
    """Get the first valid date after given "yyyy/mm/dd", for example if 2021/02/30 is given, this
    will return march 1st of 2021.
    """
    d = create_date_opt(year, month, day)
    if d is not None:
        return d

    for x in reversed(range(28, day)):
        d = create_date_opt(year, month, x)
        if d is not None:
            d = next_day_opt(d)
            if d is not None:
                return d

    return DATE_END.date()


class DateFilter(ABC):
    @abstractmethod
    def filter(self, date: datetime.date, ctx: Context) -> bool:
        """Return true if the given date is included in the date range"""

    @abstractmethod
    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        """Return the next date when the filter will change"""


def next_change_hint_seq(
    seq: Sequence[DateFilter], date: datetime.date, ctx: Context
) -> datetime.date:
    """Return the next date when one of the filters will change"""
    if not seq:
        return DATE_END.date()

    return min((x.next_change_hint(date, ctx) for x in seq))


class Weekday(enum.IntEnum):
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
class YearRange(ModelBase, DateFilter):
    start: int
    end: Optional[int]
    step: int = 1

    def __post_init__(self):
        # if self.end and self.end < self.start:
        #     raise OsmParsingException(
        #         "Year range with start year > end year is invalid"
        #     )
        if self.step < 1:
            raise OsmParsingException(
                "You can not use year ranges with period equals zero."
            )

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        return (
            wrapping_contains(self.start, self.end or DATE_END.year, date.year)
            and abs(date.year - self.start) % self.step == 0
        )

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        if self.end and self.start > self.end:
            return DATE_ZERO

        if self.end and self.end < date.year:
            # 1. time exceeded the range, the state won't ever change
            return DATE_END.date()
        elif date.year < self.start:
            # 2. time didn't reach the range yet
            next_year = self.start
        elif self.end is None:
            return DATE_END.date()
        elif self.step == 1:
            # 3. time is in the range and step is naive
            next_year = self.end + 1
        elif (date.year - self.start) % self.step == 0:
            # 4. time matches the range with step >= 2
            next_year = date.year + 1
        else:
            # 5. time is in the range but doesn't match the step
            def round_up(x: int, d: int) -> int:
                return d * math.ceil(x / d)

            next_year = self.start + round_up(date.year - self.start, self.step)

        return datetime.date(next_year, 1, 1)

    def __str__(self) -> str:
        res = str(self.start)
        if self.end is None:
            res += "+"
        elif self.start != self.end:
            res += f"-{self.end}"
        if self.step != 1:
            res += f"/{self.step}"
        return res


class Month(enum.IntEnum):
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
    Dec = 12

    def next(self) -> "Month":
        nv = self + 1
        if nv > 12:
            nv = 1
        return Month(nv)

    def __str__(self) -> str:
        return self.name


@dataclass
class MonthRange(ModelBase, DateFilter):
    start: Month
    end: Month
    year: Optional[int] = None

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        return (self.year or date.year) == date.year and wrapping_contains(
            self.start, self.end, date.month
        )

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        if self.year is None:
            if self.end.next() == self.start:
                return DATE_END.date()
            if wrapping_contains(self.start, self.end, date.month):
                naive = datetime.date(date.year, self.end.next(), 1)
            else:
                naive = datetime.date(date.year, self.start, 1)

            if naive > date:
                return naive
            else:
                return naive.replace(year=naive.year + 1)
        else:
            start = create_date_opt(self.year, self.start, 1)
            if start is None:
                return DATE_ZERO
            if self.start <= self.end and self.end < Month.Dec:
                end = create_date_opt(self.year, self.end + 1, 1)
            else:
                end = create_date_opt(self.year + 1, self.end % 12 + 1, 1)
            if end is None:
                return DATE_ZERO

            return next_change_from_bounds(date, [start], [end])

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
                diff = (7 + date.weekday() - self.wday_offset.weekday) % 7
                res -= datetime.timedelta(days=diff)
                assert res.weekday() == self.wday_offset.weekday
            case WeekDayOffsetKind.NEXT:
                diff = (7 + self.wday_offset.weekday - date.weekday()) % 7
                res += datetime.timedelta(days=diff)
                assert res.weekday() == self.wday_offset.weekday

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

    def __post_init__(self):
        if self.year:
            datetime.date(self.year, self.month, self.day)
        else:
            dom = calendar.monthrange(2024, self.month)[1]
            if self.day > dom:
                raise OsmParsingException(f"{self.month} has only {dom} days")

    def to_date(self, for_year: Optional[int]) -> datetime.date:
        if self.year is None:
            if for_year is None:
                raise ValueError("CalendarDate has no year, for_year expected")
            return datetime.date(for_year, self.month, self.day)
        else:
            return datetime.date(self.year, self.month, self.day)

    def __str__(self) -> str:
        res = ""
        if self.year is not None:
            res += f"{self.year} "
        res += f"{self.month} {self.day}"
        return res

    def __lt__(self, value: object) -> bool:
        if not isinstance(value, CalendarDate):
            raise TypeError("can only compare to CalendarDate")
        return self.to_date(DATE_START.year) < value.to_date(DATE_START.year)


class VariableDateKind(enum.Enum):
    EASTER = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class VariableDate(ModelBase):
    kind: VariableDateKind = VariableDateKind.EASTER
    year: Optional[int] = None

    def to_date(self, for_year: int) -> Optional[datetime.date]:
        match self.kind:
            case VariableDateKind.EASTER:
                return self.easter(self.year or for_year)

    @staticmethod
    def easter(year: int) -> Optional[datetime.date]:
        """Find Easter date for given year

        See https://en.wikipedia.org/wiki/Date_of_Easter#Anonymous_Gregorian_algorithm"""

        a = year % 19
        b = int(year / 100)
        c = year % 100
        d = int(b / 4)
        e = b % 4
        f = int((b + 8) / 25)
        g = int((b - f + 1) / 3)
        h = (19 * a + b - d - g + 15) % 30
        i = int(c / 4)
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
        m = int((a + 11 * h + 22 * l) / 451)
        n = int((h + l - 7 * m + 114) / 31)
        o = (h + l - 7 * m + 114) % 31

        return create_date_opt(year, n, o + 1)

    def __str__(self) -> str:
        res = ""
        if self.year is not None:
            res += f"{self.year} "
        res += str(self.kind)
        return res


type DateUnion = CalendarDate | VariableDate


@dataclass
class DateRange(ModelBase, DateFilter):
    start_date: DateUnion
    start_offset: DateOffset
    end_date: DateUnion
    end_offset: DateOffset

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        if self.start_date == FEB_29 and self.end_date == FEB_29:
            ydates = (
                create_date_opt(y, 2, 29)
                for y in range(date.year - 1, DATE_END.year + 1)
            )
            return is_open_from_intervals(
                date,
                (
                    (self.start_offset.apply(d), self.end_offset.apply(d))
                    for d in ydates
                    if d is not None
                ),
            )

        ydates_start = (
            date_on_year(self.start_date, y, valid_ymd_after)
            for y in range(date.year - 1, date.year + 2)
        )
        ydates_end = (
            date_on_year(self.end_date, y, valid_ymd_before)
            for y in range(date.year - 1, date.year + 2)
        )
        return is_open_from_bounds(
            date,
            (self.start_offset.apply(d) for d in ydates_start if d),
            (self.end_offset.apply(d) for d in ydates_end if d),
        )

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        if (
            isinstance(self.start_date, CalendarDate)
            and self.start_date.year is not None
            and isinstance(self.end_date, CalendarDate)
        ):
            start = self.start_offset.apply(self.start_date.to_date(None))
            end = self.end_offset.apply(self.end_date.to_date(self.start_date.year))
            if start > end:
                end = end.replace(year=end.year + 1)

            return next_change_from_bounds(date, [start], [end])
        else:
            if self.start_date == FEB_29 and self.end_date == FEB_29:
                ydates = (
                    create_date_opt(y, 2, 29)
                    for y in range(date.year - 1, DATE_END.year + 1)
                )
                return next_change_from_intervals(
                    date,
                    (
                        (self.start_offset.apply(d), self.end_offset.apply(d))
                        for d in ydates
                        if d is not None
                    ),
                )

            ydates_start = (
                date_on_year(self.start_date, y, valid_ymd_after)
                for y in range(date.year - 1, date.year + 10)
            )
            ydates_end = (
                date_on_year(self.end_date, y, valid_ymd_before)
                for y in range(date.year - 1, date.year + 10)
            )
            return next_change_from_bounds(
                date,
                (self.start_offset.apply(d) for d in ydates_start if d),
                (self.end_offset.apply(d) for d in ydates_end if d),
            )

    def __str__(self) -> str:
        res = f"{self.start_date}{self.start_offset}"
        if self.start_date != self.end_date or self.start_offset != self.end_offset:
            res += f"-{self.end_date}{self.end_offset}"
        return res


type MonthdayRange = Union[MonthRange, DateRange]


@dataclass
class WeekRange(ModelBase, DateFilter):
    start: int
    end: int
    step: int = 1

    def __post_init__(self):
        if self.step > 26:
            raise OsmParsingException(
                "You have specified a week period which is greater than 26. 26.5 is the half of the maximum 53 week dates per year so a week date period greater than 26 would only apply once per year."
            )

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        week = date.isocalendar().week
        return (
            wrapping_contains(self.start, self.end, week)
            # TODO: what happens when week < range.start ?
            and max(week - self.start, 0) % self.step == 0
        )

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        isocal = date.isocalendar()
        week = isocal.week
        if self.start > self.end:
            # TODO: wrapping implemented well?
            return DATE_ZERO

        if wrapping_contains(self.start, self.end, week):
            if self.step == 1:
                weeknum = self.end % 54 + 1
            elif (week - self.start) % self.step == 0:
                weeknum = week % 54 + 1
            else:
                return DATE_ZERO
        else:
            weeknum = self.start

        try:
            res = datetime.date.fromisocalendar(isocal.year, weeknum, 1)
        except ValueError:
            return DATE_ZERO
        while res <= date:
            try:
                res = datetime.date.fromisocalendar(
                    res.isocalendar().year + 1, weeknum, 1
                )
            except ValueError:
                return DATE_ZERO
        return res

    def __str__(self) -> str:
        if self.start == self.end and self.step == 1:
            return f"{self.start:02}"

        res = f"{self.start:02}-{self.end:02}"
        if self.step != 1:
            res += f"/{self.step}"
        return res


@dataclass
class WeekDayRange(ModelBase, DateFilter):
    start: Weekday
    end: Weekday
    offset: int = 0
    nth_from_start: Bitfield = field(default_factory=Bitfield)
    nth_from_end: Bitfield = field(default_factory=Bitfield)

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        if self.start > self.end:
            # Handle wrapping ranges
            return WeekDayRange(
                self.start,
                Weekday.Su,
                self.offset,
                self.nth_from_start,
                self.nth_from_end,
            ).filter(date, ctx) or WeekDayRange(
                Weekday.Mo,
                self.end,
                self.offset,
                self.nth_from_start,
                self.nth_from_end,
            ).filter(date, ctx)

        d = date - datetime.timedelta(days=self.offset)
        pos_from_start = int((d.day - 1) / 7)
        pos_from_end = int((calendar.monthrange(d.year, d.month)[1] - d.day) / 7)

        return wrapping_contains(self.start, self.end, d.weekday()) and (
            self.nth_from_start.get(pos_from_start)
            or self.nth_from_end.get(pos_from_end)
        )

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        return DATE_ZERO

    def __str__(self) -> str:
        res = str(self.start)

        if self.start != self.end:
            res += f"-{self.end}"

        if False in self.nth_from_start or False in self.nth_from_end:
            weeknums = [str(p + 1) for p in self.nth_from_start.set_positions()] + [
                str(-p - 1) for p in self.nth_from_end.set_positions()
            ]
            res += "[" + ",".join(weeknums) + "]"

        res += fmt_days_offset(self.offset)
        return res


@dataclass
class HolidayRange(ModelBase, DateFilter):
    kind: HolidayKind
    offset: int = 0

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        d = date - datetime.timedelta(days=self.offset)
        return ctx.holidays.is_holiday(d, self.kind)

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        d = date - datetime.timedelta(days=self.offset)
        if ctx.holidays.is_holiday(d, self.kind):
            return next_day_opt(d) or DATE_ZERO
        else:
            nxt = ctx.holidays.first_holiday_after(d, self.kind)
            if nxt is not None:
                return nxt + datetime.timedelta(days=self.offset)
            else:
                return DATE_END.date()

    def __str__(self) -> str:
        res = str(self.kind)
        res += fmt_offset(self.offset)
        return res


type WeekDayRangeUnion = Union[WeekDayRange, HolidayRange]


@dataclass
class DaySelector(ModelBase, DateFilter):
    year: Sequence[YearRange] = field(default_factory=list)
    monthday: Sequence[MonthdayRange] = field(default_factory=list)
    week: Sequence[WeekRange] = field(default_factory=list)
    weekday: Sequence[WeekDayRangeUnion] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            not self.year and not self.monthday and not self.week and not self.weekday
        )

    def filter(self, date: datetime.date, ctx: Context) -> bool:
        return (
            filter_seq(self.year, date, ctx)
            and filter_seq(self.monthday, date, ctx)
            and filter_seq(self.week, date, ctx)
            and filter_seq(self.weekday, date, ctx)
        )

    def next_change_hint(self, date: datetime.date, ctx: Context) -> datetime.date:
        # If there is no date filter, then all dates shall match
        if self.is_empty():
            return DATE_END.date()

        parts = [
            next_change_hint_seq(self.year, date, ctx) or DATE_ZERO,
            next_change_hint_seq(self.monthday, date, ctx) or DATE_ZERO,
            next_change_hint_seq(self.week, date, ctx) or DATE_ZERO,
            next_change_hint_seq(self.weekday, date, ctx) or DATE_ZERO,
        ]

        m = min(*parts)
        return m

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


type DateInterval = tuple[datetime.date, datetime.date]

FEB_29 = CalendarDate(None, Month.Feb, 29)
