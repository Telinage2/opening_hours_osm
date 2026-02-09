import datetime

import pytest

from opening_hours_osm import (
    OpeningHours,
    RuleKind,
)
from opening_hours_osm.opening_hours import DateTimeRange
from opening_hours_osm.schedule import TimeRange, ExtendedTime


@pytest.mark.parametrize(
    "value,start,end,expected_intervals",
    [
        pytest.param(
            "Mo-Su 00:00-06:00, 23:00-00:00",
            datetime.datetime(2024, 11, 11, 1, 0),
            datetime.datetime(2024, 11, 12, 1, 0),
            [
                DateTimeRange(
                    datetime.datetime(2024, 11, 11, 1, 0),
                    datetime.datetime(2024, 11, 11, 6, 0),
                    RuleKind.OPEN,
                ),
                DateTimeRange(
                    datetime.datetime(2024, 11, 11, 6, 0),
                    datetime.datetime(2024, 11, 11, 23, 0),
                    RuleKind.CLOSED,
                ),
                DateTimeRange(
                    datetime.datetime(2024, 11, 11, 23, 0),
                    datetime.datetime(2024, 11, 12, 1, 0),
                    RuleKind.OPEN,
                ),
            ],
            id="no_interval_after_last_midnight",
        ),
        pytest.param(
            "00:30-05:30",
            datetime.datetime(2024, 11, 25, 17, 30),
            datetime.datetime(2024, 11, 26, 9, 0),
            [
                DateTimeRange(
                    datetime.datetime(2024, 11, 25, 17, 30),
                    datetime.datetime(2024, 11, 26, 0, 30),
                    RuleKind.CLOSED,
                ),
                DateTimeRange(
                    datetime.datetime(2024, 11, 26, 0, 30),
                    datetime.datetime(2024, 11, 26, 5, 30),
                    RuleKind.OPEN,
                ),
                DateTimeRange(
                    datetime.datetime(2024, 11, 26, 5, 30),
                    datetime.datetime(2024, 11, 26, 9, 0),
                    RuleKind.CLOSED,
                ),
            ],
            id="only_close_when_no_day_filter",
        ),
        pytest.param(
            "Mo-Sa 09:00-20:00/21:00",
            datetime.datetime(2024, 11, 25, 17, 30),
            datetime.datetime(2024, 11, 26, 9, 0),
            [
                DateTimeRange(
                    datetime.datetime(2024, 11, 25, 17, 30),
                    datetime.datetime(2024, 11, 25, 20, 0),
                    RuleKind.OPEN,
                ),
                DateTimeRange(
                    datetime.datetime(2024, 11, 25, 20, 0),
                    datetime.datetime(2024, 11, 26, 9, 0),
                    RuleKind.CLOSED,
                ),
            ],
            id="invalid_time_step_panics",
        ),
    ],
)
def test_parser_intervals(
    value: str,
    start: datetime.datetime,
    end: datetime.datetime,
    expected_intervals: list[DateTimeRange],
):
    oh = OpeningHours.parse(value)
    intervals = list(oh.iter_range(start, end))
    assert intervals == expected_intervals


@pytest.mark.parametrize(
    "value,date,schedule",
    [
        # Exact date
        ("2020Jun01 open", datetime.date(2020, 5, 31), []),
        (
            "2020Jun01:10:00-12:10",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 10), RuleKind.OPEN)],
        ),
        ("2020Jun01 open", datetime.date(2020, 6, 2), []),
        # Ranges
        (
            "Jan-Jun:11:58-11:59",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(11, 58), ExtendedTime(11, 59), RuleKind.OPEN)],
        ),
        (
            "May15-01:10:00-12:00",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "May15-01:10:00-12:00",
            datetime.date(2020, 6, 2),
            [],
        ),
        (
            "2019Sep01-2020Jul31:10:00-12:00",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "2019Sep01+:10:00-12:00",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "2019Sep01-Jul01:10:00-12:00",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        (
            "Sep01-Jul01:10:00-12:00",
            datetime.date(2020, 6, 1),
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
    ],
)
def test_month_selector(value: str, date: datetime.date, schedule: list[TimeRange]):
    oh = OpeningHours.parse(value)
    got_schedule = oh.schedule_at(date)
    assert got_schedule.ranges == schedule


def test_jump_month_interval():
    oh = OpeningHours.parse("Jun")
    assert oh.next_change(datetime.datetime(2024, 2, 15, 10, 0)) == datetime.datetime(
        2024, 6, 1
    )
    assert oh.next_change(datetime.datetime(2024, 6, 15, 10, 0)) == datetime.datetime(
        2024, 7, 1
    )


def test_feb29_point():
    oh = OpeningHours.parse("Feb29")

    # 2020 is a leap year
    assert not oh.is_open(datetime.datetime(2020, 2, 28, 12, 0))
    assert oh.is_open(datetime.datetime(2020, 2, 29, 12, 0))
    assert not oh.is_open(datetime.datetime(2020, 3, 1, 12, 0))

    # 2021 is NOT a leap year
    assert not oh.is_open(datetime.datetime(2021, 2, 28, 12, 0))
    assert not oh.is_open(datetime.datetime(2021, 3, 1, 12, 0))


def test_feb29_starts_interval():
    oh = OpeningHours.parse("Feb29-Mar15")

    # 2020 is a leap year
    assert not oh.is_open(datetime.datetime(2020, 2, 28, 12, 0))
    assert oh.is_open(datetime.datetime(2020, 2, 29, 12, 0))
    assert oh.is_open(datetime.datetime(2020, 3, 1, 12, 0))
    assert not oh.is_open(datetime.datetime(2020, 3, 16, 12, 0))

    # 2021 is NOT a leap year
    assert not oh.is_open(datetime.datetime(2021, 2, 28, 12, 0))
    assert oh.is_open(datetime.datetime(2021, 3, 1, 12, 0))
    assert not oh.is_open(datetime.datetime(2021, 3, 16, 12, 0))


def test_feb29_ends_interval():
    oh = OpeningHours.parse("Feb15-Feb29")

    # 2020 is a leap year
    assert not oh.is_open(datetime.datetime(2020, 2, 14, 12, 0))
    assert oh.is_open(datetime.datetime(2020, 2, 15, 12, 0))
    assert oh.is_open(datetime.datetime(2020, 2, 29, 12, 0))
    assert not oh.is_open(datetime.datetime(2020, 3, 1, 12, 0))

    # 2021 is NOT a leap year
    assert not oh.is_open(datetime.datetime(2021, 2, 14, 12, 0))
    assert oh.is_open(datetime.datetime(2021, 2, 15, 12, 0))
    assert oh.is_open(datetime.datetime(2021, 2, 28, 12, 0))
    assert not oh.is_open(datetime.datetime(2021, 3, 1, 12, 0))
