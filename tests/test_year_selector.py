import datetime

import pytest

from opening_hours_osm import OpeningHours, RuleKind
from opening_hours_osm.schedule import TimeRange, ExtendedTime


@pytest.mark.parametrize(
    "value,date,schedule",
    [
        # basic range
        (
            "2020:10:00-12:00",
            datetime.date(2020, 1, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "2020:10:00-12:00",
            datetime.date(2021, 1, 1),
            [],
        ),
        (
            "2010-2019,2021,2025+:10:00-12:00",
            [datetime.date(2020, 1, 1), datetime.date(2024, 1, 1)],
            [],
        ),
        (
            "2010-2019,2021,2025+:10:00-12:00",
            [datetime.date(2015, 1, 1), datetime.date(5742, 1, 1)],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "2010-2100/3:10:00-12:00",
            [datetime.date(2010, 1, 1), datetime.date(2019, 1, 1)],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "2010-2100/3:10:00-12:00",
            [datetime.date(2017, 1, 1), datetime.date(2018, 1, 1)],
            [],
        ),
        # wrapping range
        (
            "2030-2010 10:00-12:00",
            [datetime.date(2020, 1, 1), datetime.date(2011, 1, 1)],
            [],
        ),
        (
            "2030-2010 10:00-12:00",
            [datetime.date(2040, 1, 1), datetime.date(2030, 1, 1), datetime.date(2000, 1, 1)],
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
    ],
)
def test_year_selector(
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
