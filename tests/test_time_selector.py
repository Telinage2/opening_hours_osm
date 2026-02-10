import datetime

import pytest

from opening_hours_osm import OpeningHours, RuleKind
from opening_hours_osm.context import Context, GeoLocale
from opening_hours_osm.schedule import TimeRange, ExtendedTime


@pytest.mark.parametrize(
    "value,localized,schedule",
    [
        # basic timespan
        (
            "14:00-19:00",
            False,
            [TimeRange(ExtendedTime(14, 0), ExtendedTime(19, 0), RuleKind.OPEN)],
        ),
        (
            "10:00-12:00,14:00-16:00",
            False,
            [
                TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN),
                TimeRange(ExtendedTime(14, 0), ExtendedTime(16, 0), RuleKind.OPEN),
            ],
        ),
        (
            "10:00-12:00,11:00-16:00 unknown",
            False,
            [
                TimeRange(ExtendedTime(10, 0), ExtendedTime(16, 0), RuleKind.UNKNOWN),
            ],
        ),
        # events
        (
            "(dawn-02:30)-(dusk+02:30)",
            False,
            [TimeRange(ExtendedTime(3, 30), ExtendedTime(22, 30), RuleKind.OPEN)],
        ),
        (
            "(dawn+00:30)-(dusk-00:30)",
            False,
            [TimeRange(ExtendedTime(6, 30), ExtendedTime(19, 30), RuleKind.OPEN)],
        ),
        (
            "sunrise-19:45",
            False,
            [TimeRange(ExtendedTime(7, 0), ExtendedTime(19, 45), RuleKind.OPEN)],
        ),
        (
            "08:15-sunset",
            False,
            [TimeRange(ExtendedTime(8, 15), ExtendedTime(19, 0), RuleKind.OPEN)],
        ),
        # events (localized)
        (
            "(dawn-02:30)-(dusk+02:30)",
            True,
            [
                TimeRange(ExtendedTime(0, 0), ExtendedTime(0, 58), RuleKind.OPEN),
                TimeRange(ExtendedTime(2, 40), ExtendedTime(24, 0), RuleKind.OPEN),
            ],
        ),
        (
            "(dawn+00:30)-(dusk-00:30)",
            True,
            [
                TimeRange(ExtendedTime(5, 40), ExtendedTime(21, 58), RuleKind.OPEN),
            ],
        ),
        (
            "sunrise-19:45",
            True,
            [
                TimeRange(ExtendedTime(5, 51), ExtendedTime(19, 45), RuleKind.OPEN),
            ],
        ),
        (
            "08:15-sunset",
            True,
            [
                TimeRange(ExtendedTime(8, 15), ExtendedTime(21, 46), RuleKind.OPEN),
            ],
        ),
        # overlap
        (
            "10:00-12:00,14:00-25:30",
            False,
            [
                TimeRange(ExtendedTime(0, 0), ExtendedTime(1, 30), RuleKind.OPEN),
                TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN),
                TimeRange(ExtendedTime(14, 0), ExtendedTime(24, 0), RuleKind.OPEN),
            ],
        ),
        (
            "Su 14:00-25:30",
            False,
            [
                TimeRange(ExtendedTime(0, 0), ExtendedTime(1, 30), RuleKind.OPEN),
            ],
        ),
        (
            "23:00-01:00",
            False,
            [
                TimeRange(ExtendedTime(0, 0), ExtendedTime(1, 0), RuleKind.OPEN),
                TimeRange(ExtendedTime(23, 0), ExtendedTime(24, 0), RuleKind.OPEN),
            ],
        ),
    ],
)
def test_time_selector(value: str, localized: bool, schedule: list[TimeRange]):
    oh = OpeningHours.parse(value)

    if localized:
        oh.ctx = Context(GeoLocale(48.87, 2.29))

    got_schedule = oh.schedule_at(datetime.date(2020, 6, 1))
    assert got_schedule.ranges == schedule


def test_dusk_open_ended():
    oh = OpeningHours.parse("Jun dusk+")
    assert oh.next_change(datetime.datetime(2024, 6, 21, 22, 30)) == datetime.datetime(
        2024, 6, 22
    )


def test_same_bounds():
    oh = OpeningHours.parse("Mo 04:00-04:00")
    assert oh.schedule_at(datetime.date(2025, 2, 24)).ranges == [
        TimeRange(ExtendedTime(4, 0), ExtendedTime(24, 0), RuleKind.OPEN)
    ]
    assert oh.schedule_at(datetime.date(2025, 2, 25)).ranges == [
        TimeRange(ExtendedTime(0, 0), ExtendedTime(4, 0), RuleKind.OPEN)
    ]
    assert oh.schedule_at(datetime.date(2025, 2, 26)).ranges == []
