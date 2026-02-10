from typing import Optional
import datetime

import pytest

from opening_hours_osm import (
    OpeningHours,
    RuleKind,
    Context,
)
from opening_hours_osm.opening_hours import DateTimeRange
from opening_hours_osm.schedule import TimeRange, ExtendedTime


@pytest.mark.parametrize(
    "value,start,expected_end",
    [
        pytest.param(
            "24/7",
            datetime.datetime(2019, 2, 10),
            None,
            id="always_open",
        ),
        pytest.param(
            "24/7",
            datetime.datetime(9999, 12, 31),
            None,
            id="date_limit_exceeded",
        ),
        pytest.param(
            "2020,8000-9000 10:00-22:00",
            datetime.datetime(2021, 2, 9, 21, 0),
            datetime.datetime(8000, 1, 1, 10, 0),
        ),
        pytest.param(
            "2021,8000-9000 10:00-22:00",
            datetime.datetime(2021, 2, 9, 21, 0),
            datetime.datetime(2021, 2, 9, 22, 0),
        ),
        pytest.param(
            "2000-3000",
            datetime.datetime(2021, 2, 9, 21, 0),
            datetime.datetime(3001, 1, 1),
        ),
        pytest.param(
            "2000-3000/42",
            datetime.datetime(2021, 2, 9, 21, 0),
            datetime.datetime(2042, 1, 1),
        ),
        pytest.param(
            "2000-3000/21",
            datetime.datetime(2021, 2, 9, 21, 0),
            datetime.datetime(2022, 1, 1),
        ),
    ],
)
def test_next_change(
    value: str, start: datetime.datetime, expected_end: Optional[datetime.datetime]
):
    oh = OpeningHours.parse(value)
    assert oh.next_change(start) == expected_end


def test_outside_date_bounds():
    before_bounds = datetime.datetime(1789, 7, 14, 12, 0)
    after_bounds = datetime.datetime(9999, 12, 31, 12, 0)

    oh = OpeningHours.parse("24/7")
    assert oh.is_closed(before_bounds)
    assert oh.is_closed(after_bounds)

    assert OpeningHours.parse("3000").next_change(before_bounds) == datetime.datetime(
        3000, 1, 1
    )
    assert oh.next_change(before_bounds) == datetime.datetime(1900, 1, 1)
    assert oh.next_change(after_bounds) is None


def test_with_max_interval_size():
    ctx = Context(approx_bound_interval_size=datetime.timedelta(days=366))
    oh = OpeningHours.parse("2024-2030Jun open", ctx)

    assert oh.next_change(datetime.datetime(2025, 5, 1, 12, 0)) == datetime.datetime(
        2025, 6, 1
    )
    assert oh.next_change(datetime.datetime(2000, 5, 1, 12, 0)) is None
    assert oh.next_change(datetime.datetime(2030, 7, 1, 12, 0)) is None
