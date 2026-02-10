import datetime

import pytest

from opening_hours_osm import OpeningHours, RuleKind, Context, CountryHolidays
from opening_hours_osm.schedule import TimeRange, ExtendedTime


@pytest.mark.parametrize(
    "value,date,schedule",
    [
        # basic range
        (
            "Mo-Su",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(0, 0), ExtendedTime(24, 0), RuleKind.OPEN)],
        ),
        (
            "Tu",
            datetime.date(2020, 6, 1),
            [],
        ),
        (
            "We",
            datetime.date(2020, 6, 1),
            [],
        ),
        (
            "Mo-Tu,Th,Sa-Su 10:00-12:00",
            [
                datetime.date(2020, 6, 1),
                datetime.date(2020, 6, 2),
                datetime.date(2020, 6, 4),
                datetime.date(2020, 6, 6),
                datetime.date(2020, 6, 7),
            ],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "Mo-Tu,Th,Sa-Su 10:00-12:00",
            [
                datetime.date(2020, 6, 3),
                datetime.date(2020, 6, 5),
            ],
            [],
        ),
        # nth
        (
            "Mo[2-4] 10:00-12:00",
            [
                datetime.date(2020, 6, 8),
                datetime.date(2020, 6, 15),
                datetime.date(2020, 6, 22),
            ],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "Mo[2-4] 10:00-12:00",
            [
                datetime.date(2020, 6, 1),
                datetime.date(2020, 6, 29),
            ],
            [],
        ),
        (
            "Mo[1] 10:00-12:00",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "Mo[1] 10:00-12:00",
            [datetime.date(2020, 6, 8), datetime.date(2020, 6, 2)],
            [],
        ),
        # nth reversed
        (
            "Mo[2-4] +2 days 10:00-12:00",
            [
                datetime.date(2020, 6, 10),
                datetime.date(2020, 6, 17),
                datetime.date(2020, 6, 24),
            ],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "Mo[2-4] +2 days 10:00-12:00",
            [
                datetime.date(2020, 6, 3),
                datetime.date(2020, 7, 1),
            ],
            [],
        ),
        (
            "Mo[1] -1 day 10:00-12:00",
            datetime.date(2020, 5, 31),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "Mo[1] -1 day 10:00-12:00",
            [
                datetime.date(2020, 6, 1),
                datetime.date(2020, 6, 7),
            ],
            [],
        ),
    ],
)
def test_weekday_selector(
    value: str, date: datetime.date | list[datetime.date], schedule: list[TimeRange]
):
    oh = OpeningHours.parse(value)
    if isinstance(date, list):
        for d in date:
            got_schedule = oh.schedule_at(d)
            assert got_schedule.ranges == schedule
    else:
        got_schedule = oh.schedule_at(date)
        assert got_schedule.ranges == schedule


def test_holiday():
    ctx = Context(holidays=CountryHolidays("FR"))
    oh = OpeningHours.parse("PH 10:00-16:00", ctx)
    assert oh.is_open(datetime.datetime(2014, 7, 14, 12, 0))
    assert oh.is_closed(datetime.datetime(2014, 7, 13, 12, 0))


def test_easter_days():
    oh = OpeningHours.parse("24/7 open ; easter off")
    assert oh.is_open(datetime.datetime(2024, 3, 30, 12, 0))
    assert oh.is_closed(datetime.datetime(2024, 3, 31, 12, 0))
    assert oh.is_open(datetime.datetime(2024, 4, 1, 12, 0))


def test_easter_interval():
    oh = OpeningHours.parse("Jan01-easter")
    assert oh.is_closed(datetime.datetime(2023, 12, 31, 12, 0))
    assert oh.is_open(datetime.datetime(2024, 1, 1, 12, 0))
    assert oh.is_open(datetime.datetime(2024, 3, 30, 12, 0))
    assert oh.is_open(datetime.datetime(2024, 3, 31, 12, 0))
    assert oh.is_closed(datetime.datetime(2024, 4, 1, 12, 0))

    oh = OpeningHours.parse("easter-Dec31")
    assert oh.is_closed(datetime.datetime(2024, 3, 30, 12, 0))
    assert oh.is_open(datetime.datetime(2024, 3, 31, 12, 0))
    assert oh.is_open(datetime.datetime(2024, 12, 31, 12, 0))
    assert oh.is_closed(datetime.datetime(2025, 1, 1, 12, 0))
