from typing import Optional
from dataclasses import dataclass, field
import datetime
from zoneinfo import ZoneInfo
from abc import ABC, abstractmethod
import logging
import bisect

from astral import Observer, sun
from tzfpy import get_tz
import holidays

from opening_hours_osm.model.enums import TimeEvent, HolidayKind

log = logging.getLogger(__name__)


def _localize_datetime(naive: datetime.datetime, timezone: ZoneInfo):
    for _ in range(120):
        candidate = naive.replace(tzinfo=timezone)
        roundtrip = candidate.astimezone(datetime.timezone.utc).astimezone(timezone)
        if roundtrip.replace(tzinfo=None) == naive:
            return candidate

        naive += datetime.timedelta(minutes=1)

    raise Exception("could not localize datetime")


class AbstractLocale(ABC):
    @abstractmethod
    def naive(self, localized: datetime.datetime) -> datetime.datetime: ...

    @abstractmethod
    def localized_datetime(self, naive: datetime.datetime) -> datetime.datetime: ...

    def event_time(self, date: datetime.date, event: TimeEvent) -> datetime.time:
        match event:
            case TimeEvent.DAWN:
                return datetime.time(hour=6)
            case TimeEvent.SUNRISE:
                return datetime.time(hour=7)
            case TimeEvent.SUNSET:
                return datetime.time(hour=19)
            case TimeEvent.DUSK:
                return datetime.time(hour=20)
            case _:
                raise ValueError(f"unknown TimeEvent {event}")


class NoLocale(AbstractLocale):
    def naive(self, localized: datetime.datetime) -> datetime.datetime:
        return localized

    def localized_datetime(self, naive: datetime.datetime) -> datetime.datetime:
        return naive


class GeoLocale(AbstractLocale):
    def __init__(self, lat: float, lng: float) -> None:
        self.observer = Observer(lat, lng)
        tz_name = get_tz(lat=lat, lng=lng)
        if tz_name:
            self.timezone = ZoneInfo(tz_name)
        else:
            log.warning(f"Could not get timezone for pos {lat};{lng}")
            self.timezone = ZoneInfo("UTC")

    def naive(self, localized: datetime.datetime) -> datetime.datetime:
        return localized.replace(tzinfo=None)

    def localized_datetime(self, naive: datetime.datetime) -> datetime.datetime:
        return _localize_datetime(naive, self.timezone)

    def event_time(self, date: datetime.date, event: TimeEvent) -> datetime.time:
        match event:
            case TimeEvent.DAWN:
                return sun.dawn(self.observer, date, tzinfo=self.timezone).timetz()
            case TimeEvent.SUNRISE:
                return sun.sunrise(self.observer, date, tzinfo=self.timezone).timetz()
            case TimeEvent.SUNSET:
                return sun.sunset(self.observer, date, tzinfo=self.timezone).timetz()
            case TimeEvent.DUSK:
                return sun.dusk(self.observer, date, tzinfo=self.timezone).timetz()
            case _:
                raise ValueError(f"unknown TimeEvent {event}")


class TzLocale(AbstractLocale):
    def __init__(self, tz: str | ZoneInfo) -> None:
        if isinstance(tz, ZoneInfo):
            self.timezone = tz
        else:
            self.timezone = ZoneInfo(tz)

    def naive(self, localized: datetime.datetime) -> datetime.datetime:
        return localized.replace(tzinfo=None)

    def localized_datetime(self, naive: datetime.datetime) -> datetime.datetime:
        return _localize_datetime(naive, self.timezone)


class AbstractHolidays(ABC):
    @abstractmethod
    def is_holiday(self, d: datetime.date, kind: HolidayKind) -> bool:
        """Check if the given date is a holiday"""

    @abstractmethod
    def first_holiday_after(
        self, d: datetime.date, kind: HolidayKind
    ) -> Optional[datetime.date]:
        """Return the first holiday after the given date"""


class CountryHolidays(AbstractHolidays):
    def __init__(self, country: str, subdiv: Optional[str] = None) -> None:
        self.hd = holidays.country_holidays(country, subdiv)

    def is_holiday(self, d: datetime.date, kind: HolidayKind) -> bool:
        if self.hd is not None and kind == HolidayKind.PH:
            res = self.hd.get(d)
            return res is not None
        return False

    def first_holiday_after(
        self, d: datetime.date, kind: HolidayKind
    ) -> Optional[datetime.date]:
        if self.hd is not None and kind == HolidayKind.PH:
            res = self.hd.get_closest_holiday(d)
            if res:
                return res[0]
        return None


class CalendarHolidays(AbstractHolidays):
    def __init__(self) -> None:
        self.hd_lists: dict[HolidayKind, list[datetime.date]] = {}
        self.hd_sets: dict[HolidayKind, set[datetime.date]] = {}

    def set_holidays(
        self, dates: list[datetime.date], kind: HolidayKind = HolidayKind.PH
    ):
        """Import a list of calendar holidays"""
        lst = sorted(dates)
        self.hd_lists[kind] = lst
        self.hd_sets[kind] = set(lst)

    def is_holiday(self, d: datetime.date, kind: HolidayKind) -> bool:
        if kind not in self.hd_sets:
            return False

        return d in self.hd_sets[kind]

    def first_holiday_after(
        self, d: datetime.date, kind: HolidayKind
    ) -> datetime.date | None:
        if kind not in self.hd_lists:
            return None

        lst = self.hd_lists[kind]
        pos = bisect.bisect(lst, d)
        if pos < len(lst):
            return lst[pos]


@dataclass
class Context:
    locale: AbstractLocale = field(default_factory=NoLocale)
    holidays: AbstractHolidays = field(default_factory=CalendarHolidays)
    approx_bound_interval_size: Optional[datetime.timedelta] = None
