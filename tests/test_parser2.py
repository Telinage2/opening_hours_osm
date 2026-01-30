from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from opening_hours_osm import OpeningHours

# from tests import TInterval
from opening_hours_osm.opening_hours import RuleKind, DateTimeRange


@dataclass
class TInterval:
    start: datetime
    end: datetime
    open_end: bool = False
    comment: Optional[str] = None

    def duration(self) -> int:
        """Interval duration in milliseconds"""
        return (self.end - self.start).seconds * 1000

    def __eq__(self, value: object) -> bool:
        if isinstance(value, TInterval):
            return (
                self.start == value.start
                and self.end == value.end
                # and self.open_end == value.open_end
                and self.comment == value.comment
            )
        return False

    def __str__(self) -> str:
        return f"{self.start.isoformat()} - {self.end.isoformat()}"


def test_x():
    oh = OpeningHours.parse("Jan 23-Feb 11,Feb 12 00:00-24:00; Apr 12:00-24:00; PH off")
    print(oh)

    d_from = datetime(2021, 4, 4, 0, 0)
    d_to = datetime(2021, 4, 18, 0, 0)
    # exp_intervals = [
    #     TInterval(datetime(2012, 10, 1, 10, 0), datetime(2012, 10, 1, 12, 0)),
    #     TInterval(datetime(2012, 10, 2, 10, 0), datetime(2012, 10, 2, 12, 0)),
    #     TInterval(datetime(2012, 10, 3, 10, 0), datetime(2012, 10, 3, 12, 0)),
    #     TInterval(datetime(2012, 10, 4, 10, 0), datetime(2012, 10, 4, 12, 0)),
    #     TInterval(datetime(2012, 10, 5, 10, 0), datetime(2012, 10, 5, 12, 0)),
    #     TInterval(datetime(2012, 10, 6, 10, 0), datetime(2012, 10, 6, 12, 0)),
    #     TInterval(datetime(2012, 10, 7, 10, 0), datetime(2012, 10, 7, 12, 0)),
    # ]
    # exp_duration = 50400000

    got_intervals = []
    got_duration = 0

    intervals = list(oh.iter_range(d_from, d_to))
    print(f"{len(intervals)} intervals")

    for interval in intervals:
        if interval.comments:
            comments = "\n".join(interval.comments)
        else:
            comments = None
        niv = TInterval(interval.start, interval.end, False, comments)
        got_intervals.append(niv)
        got_duration += niv.duration()

        print(f"[{interval.kind}] {interval.start.isoformat()} - {interval.end.isoformat()}")

    # assert got_intervals == exp_intervals
    # assert got_duration == exp_duration


if __name__ == "__main__":
    test_x()
