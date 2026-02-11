"""Check that basic features work"""

from opening_hours_osm import OpeningHours
from opening_hours_osm.opening_hours import TimeRange, RuleKind
from opening_hours_osm.model.time import ExtendedTime
import datetime


def run():
    oh = OpeningHours.parse("10:00-18:00")
    schedule = oh.schedule_at(datetime.date(2026, 2, 10))
    assert schedule.ranges == [
        TimeRange(ExtendedTime(10, 0), ExtendedTime(18, 0), RuleKind.OPEN)
    ]
    print("OK")


if __name__ == "__main__":
    run()
