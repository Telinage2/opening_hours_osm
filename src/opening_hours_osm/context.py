from typing import Optional
from dataclasses import dataclass, field
import datetime
from zoneinfo import ZoneInfo
from abc import ABC, abstractmethod
import logging

from astral import Observer, sun
from tzfpy import get_tz

from opening_hours_osm.model.enums import TimeEvent, HolidayKind

log = logging.getLogger(__name__)


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
        return naive.astimezone(self.timezone)

    def event_time(self, date: datetime.date, event: TimeEvent) -> datetime.time:
        match event:
            case TimeEvent.DAWN:
                return sun.dawn(self.observer, date).timetz()
            case TimeEvent.SUNRISE:
                return sun.sunrise(self.observer, date).timetz()
            case TimeEvent.SUNSET:
                return sun.sunset(self.observer, date).timetz()
            case TimeEvent.DUSK:
                return sun.dusk(self.observer, date).timetz()
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
        return naive.astimezone(self.timezone)


@dataclass
class Context:
    # holidays: ContextHolidays
    locale: AbstractLocale = field(default_factory=NoLocale)
    approx_bound_interval_size: Optional[datetime.timedelta] = None

    def is_holiday(self, d: datetime.date, kind: HolidayKind) -> bool:
        return False

    def first_holiday_after(
        self, d: datetime.date, kind: HolidayKind
    ) -> Optional[datetime.date]:
        return None
