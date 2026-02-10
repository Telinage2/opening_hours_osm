from typing import Optional
import datetime

import pytest

from opening_hours_osm import (
    OpeningHours,
    RuleKind,
)
from opening_hours_osm.schedule import TimeRange, ExtendedTime


@pytest.mark.parametrize(
    "value,date,schedule",
    [
        (
            "week01:10:00-12:00",
            datetime.date(2020, 1, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "week01:10:00-12:00",
            datetime.date(2020, 1, 6),
            [],
        ),
        (
            "week01,23-24:10:00-12:00",
            datetime.date(2020, 1, 6),
            [],
        ),
        (
            "week01,22-23:10:00-12:00",
            datetime.date(2020, 5, 31),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "week01,22-23:10:00-12:00",
            datetime.date(2020, 6, 7),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "week01-53/2:10:00-12:00",
            [
                datetime.date(2020, 1, 1),
                datetime.date(2020, 1, 15),
                datetime.date(2020, 1, 29),
            ],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "week01-53/2:10:00-12:00",
            [datetime.date(2020, 1, 8), datetime.date(2020, 1, 22)],
            [],
        ),
    ],
)
def test_week_range(
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


@pytest.mark.parametrize(
    "value,start,expected_end",
    [
        # Week 52 of 7569 is the last week of the year and ends at the 28th
        (
            "week 52 ; Jun",
            datetime.datetime(7569, 12, 28, 8, 5),
            datetime.datetime(7569, 12, 29),
        ),
        (
            "week 1 ; Jun",
            datetime.datetime(7569, 12, 28, 8, 5),
            datetime.datetime(7569, 12, 29),
        ),
        # Week 52 of 2021 is the last week and ends on the 2th of January
        (
            "week 52 ; Jun",
            datetime.datetime(2021, 12, 28, 8, 5),
            datetime.datetime(2022, 1, 3),
        ),
        # Week 53 of 2020 ends on 3rd of January
        (
            "week 53 ; Jun",
            datetime.datetime(2020, 12, 28, 8, 5),
            datetime.datetime(2021, 1, 4),
        ),
        # There is no week 53 from 2021 to 2026
        (
            "week 53",
            datetime.datetime(2021, 1, 15, 8, 5),
            datetime.datetime(2026, 12, 28),
        ),
    ],
)
def test_last_year_week(
    value: str, start: datetime.datetime, expected_end: Optional[datetime.datetime]
):
    oh = OpeningHours.parse(value)
    assert oh.next_change(start) == expected_end


def test_outside_wrapping_range():
    oh = OpeningHours.parse("2030 week52-01")
    assert oh.next_change(datetime.datetime(2024, 6, 1, 12, 0)) is not None
    assert oh.is_open(datetime.datetime(2030, 1, 1, 12, 0))
    assert oh.is_closed(datetime.datetime(2024, 6, 1, 12, 0))
