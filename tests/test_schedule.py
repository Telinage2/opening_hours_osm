from opening_hours_osm.schedule import Schedule, TimeRange
from opening_hours_osm.model.time import ExtendedTime, MIDNIGHT_00, MIDNIGHT_24
from opening_hours_osm.model import RuleKind

import pytest


def test_iter_on_empty_schedule():
    schedule = iter(Schedule([]))
    tr = next(schedule)
    assert tr == TimeRange(MIDNIGHT_00, MIDNIGHT_24, RuleKind.CLOSED)

    with pytest.raises(StopIteration):
        next(schedule)


def test_iter_on_complex_schedule():
    schedule = iter(
        Schedule.from_ranges(
            [
                (ExtendedTime(10, 0), ExtendedTime(12, 0)),
                (ExtendedTime(14, 0), ExtendedTime(16, 0)),
            ],
            RuleKind.OPEN,
            ["Full availability"],
        )
        .addition(
            Schedule.from_ranges(
                [(ExtendedTime(16, 0), ExtendedTime(18, 0))], RuleKind.UNKNOWN
            )
        )
        .addition(
            Schedule.from_ranges(
                [(ExtendedTime(9, 0), ExtendedTime(10, 0))],
                RuleKind.CLOSED,
                ["May take orders"],
            )
        )
        .addition(
            Schedule.from_ranges(
                [(ExtendedTime(22, 0), ExtendedTime(24, 0))], RuleKind.CLOSED
            )
        )
    )

    assert next(schedule) == TimeRange(
        MIDNIGHT_00, ExtendedTime(10, 0), RuleKind.CLOSED, ["May take orders"]
    )
    assert next(schedule) == TimeRange(
        ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN, ["Full availability"]
    )
    assert next(schedule) == TimeRange(
        ExtendedTime(12, 0), ExtendedTime(14, 0), RuleKind.CLOSED
    )
    assert next(schedule) == TimeRange(
        ExtendedTime(14, 0), ExtendedTime(16, 0), RuleKind.OPEN, ["Full availability"]
    )
    assert next(schedule) == TimeRange(
        ExtendedTime(16, 0), ExtendedTime(18, 0), RuleKind.UNKNOWN
    )
    assert next(schedule) == TimeRange(
        ExtendedTime(18, 0), ExtendedTime(24, 0), RuleKind.CLOSED
    )

    with pytest.raises(StopIteration):
        next(schedule)
