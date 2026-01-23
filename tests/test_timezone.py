import datetime
from zoneinfo import ZoneInfo

from opening_hours_osm.context import TzLocale


def test_timezone_naive():
    tz = ZoneInfo("Europe/Berlin")
    locale = TzLocale(tz)

    dt = datetime.datetime(2026, 1, 23, 12, 0, tzinfo=tz)

    naive = locale.naive(dt)
    assert naive.hour == 12
    assert naive.minute == 0


def test_timezone_localized():
    tz = ZoneInfo("Europe/Berlin")
    locale = TzLocale(tz)

    naive = datetime.datetime(2026, 1, 23, 12, 0)

    dt = locale.localized_datetime(naive)
    assert dt.hour == 12
    assert dt.minute == 0
