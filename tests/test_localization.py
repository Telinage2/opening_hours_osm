import datetime
from zoneinfo import ZoneInfo

from opening_hours_osm import (
    OpeningHours,
    Context,
    TzLocale,
    GeoLocale,
    CountryHolidays,
)

TZ_PARIS = ZoneInfo("Europe/Paris")
COORDS_PARIS = (48.8535, 2.34839)


def test_ctx_with_tz():
    ctx = Context(TzLocale(TZ_PARIS))
    oh = OpeningHours.parse("10:00-18:00", ctx)

    res = oh.next_change(datetime.datetime(2024, 12, 23, 14, 44, tzinfo=TZ_PARIS))
    assert res == datetime.datetime(2024, 12, 23, 18, 0, tzinfo=TZ_PARIS)


def test_ends_at_invalid_time():
    """
    In France, time skipped from 02:00 to 03:00 on 31/03/2024
    See https://www.service-public.fr/particuliers/actualites/A15539
    """
    ctx = Context(TzLocale(TZ_PARIS))
    oh = OpeningHours.parse("10:00-26:30", ctx)

    res = oh.next_change(datetime.datetime(2024, 3, 30, 14, 44, tzinfo=TZ_PARIS))
    assert res == datetime.datetime(2024, 3, 31, 3, 0, tzinfo=TZ_PARIS)


def test_ends_at_ambiguous_time():
    """
    In France, the clock jumped back to 02:00 on 27/10/2024 03:00
    See https://www.service-public.fr/particuliers/actualites/A15263
    """
    ctx = Context(TzLocale(TZ_PARIS))
    oh = OpeningHours.parse("10:00-26:30", ctx)

    res = oh.next_change(datetime.datetime(2024, 10, 27, 14, 44, tzinfo=TZ_PARIS))
    assert res == datetime.datetime(2024, 10, 28, 2, 30, tzinfo=TZ_PARIS)


def test_infer_tz():
    ctx = Context(GeoLocale(*COORDS_PARIS))
    oh = OpeningHours.parse("sunrise-sunset", ctx)

    res = oh.next_change(datetime.datetime(2024, 12, 23, 14, 44, tzinfo=TZ_PARIS))
    assert res == datetime.datetime(2024, 12, 23, 16, 57, tzinfo=TZ_PARIS)


def test_infer_all():
    ctx = Context(GeoLocale(*COORDS_PARIS), CountryHolidays("FR"))
    oh = OpeningHours.parse("sunrise-sunset; PH off", ctx)

    res = oh.next_change(datetime.datetime(2024, 12, 23, 14, 44, tzinfo=TZ_PARIS))
    assert res == datetime.datetime(2024, 12, 23, 16, 57, tzinfo=TZ_PARIS)

    res = oh.next_change(datetime.datetime(2024, 7, 14, 14, 44, tzinfo=TZ_PARIS))
    assert res == datetime.datetime(2024, 7, 15, 6, 3, tzinfo=TZ_PARIS)
