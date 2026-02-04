import json
from pathlib import Path
import datetime
from zoneinfo import ZoneInfo

import pytest

from opening_hours_osm import OpeningHours
from opening_hours_osm.opening_hours import (
    RuleSequence,
    RuleKind,
    RuleOperator,
    DateTimeRange,
)
from opening_hours_osm.model.day import (
    DaySelector,
    YearRange,
    MonthRange,
    DateRange,
    MonthdayRange,
    WeekRange,
    WeekDayRange,
    WeekDayRangeUnion,
    HolidayRange,
    HolidayKind,
    DateUnion,
    DateOffset,
    Weekday,
    CalendarDate,
    VariableDate,
    Month,
    Bitfield,
)
from opening_hours_osm.model.time import (
    TimeSelector,
    TimeSpan,
    TimeUnion,
    ExtendedTime,
    VariableTime,
    TimeEvent,
)
from opening_hours_osm.context import Context, GeoLocale, CalendarHolidays

DIR_TESTFILES = Path.absolute(Path(__file__).parent / "testfiles")
TZ = ZoneInfo("Europe/Berlin")


# Import the holidays used by the Rust library for test cases to match
HOLIDAYS = CalendarHolidays()
with open(DIR_TESTFILES / "holidays_de.txt") as f:
    holidays = []
    for line in f.readlines():
        line = line.strip()
        if line:
            holidays.append(datetime.date.fromisoformat(line))
    HOLIDAYS.set_holidays(holidays)


def pytest_generate_tests(metafunc: pytest.Metafunc):
    with open(DIR_TESTFILES / "rust_cases.json") as f:
        test_data = json.load(f)

    if metafunc.function == test_parser:
        metafunc.parametrize("data", test_data, ids=(x["s"] for x in test_data))


ctx = Context(GeoLocale(48.36658170393406, 10.89542692530624), HOLIDAYS)


def map_rules(rules: list[dict]) -> list[RuleSequence]:
    def map_month(s: str) -> Month:
        return Month[s[:3]]

    def map_date_union(d: dict) -> DateUnion:
        if "Fixed" in d:
            d = d["Fixed"]
            return CalendarDate(d["year"], map_month(d["month"]), d["day"])
        else:
            d = d["Easter"]
            return VariableDate(year=d["year"])

    def map_date_offset(d: dict) -> DateOffset:
        return DateOffset(day_offset=d["day_offset"])  # wday offset not supported

    def map_md_range(md: dict) -> MonthdayRange:
        if "Date" in md:
            d = md["Date"]
            return DateRange(
                map_date_union(d["start"][0]),
                map_date_offset(d["start"][1]),
                map_date_union(d["end"][0]),
                map_date_offset(d["end"][1]),
            )
        else:
            m = md["Month"]
            return MonthRange(
                map_month(m["range"]["start"]),
                map_month(m["range"]["end"]),
                m["year"],
            )

    def map_weekday_range(wd: dict) -> WeekDayRangeUnion:
        if "Fixed" in wd:
            wd = wd["Fixed"]
            return WeekDayRange(
                Weekday[wd["range"]["start"][:2]],
                Weekday[wd["range"]["end"][:2]],
                wd["offset"],
                Bitfield.from_list(wd["nth_from_start"]),
                Bitfield.from_list(wd["nth_from_end"]),
            )
        else:
            hr = wd["Holiday"]
            match hr["kind"]:
                case "Public":
                    kind = HolidayKind.PH
                case "School":
                    kind = HolidayKind.SH
                case _:
                    raise ValueError("holiday kind " + hr["kind"])
            return HolidayRange(kind, hr["offset"])

    def map_day_selector(ds: dict) -> DaySelector:
        return DaySelector(
            [
                YearRange(y["range"]["start"], y["range"]["end"], y["step"])
                for y in ds["year"]
            ],
            [map_md_range(md) for md in ds["monthday"]],
            [
                WeekRange(w["range"]["start"], w["range"]["end"], w["step"])
                for w in ds["week"]
            ],
            [map_weekday_range(wd) for wd in ds["weekday"]],
        )

    def map_time_union(t: dict) -> TimeUnion:
        if "Fixed" in t:
            t = t["Fixed"]
            return ExtendedTime(t["hour"], t["minute"])
        else:
            t = t["Variable"]
            return VariableTime(TimeEvent[t["event"].upper()], t["offset"])

    def map_time_selector(ts: dict) -> TimeSelector:
        return TimeSelector(
            [
                TimeSpan(
                    map_time_union(t["range"]["start"]),
                    map_time_union(t["range"]["end"]),
                    t["open_end"],
                    # t["repeats"] not supported,
                )
                for t in ts["time"]
            ]
        )

    res = []
    for r in rules:
        res.append(
            RuleSequence(
                map_day_selector(r["day_selector"]),
                map_time_selector(r["time_selector"]),
                RuleKind[r["kind"].upper()],
                RuleOperator[r["operator"].upper()],
                r["comments"],
            )
        )
    return res


def map_dt(dt: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(dt)

    return parsed.astimezone(TZ)


def map_ranges(ranges: list[dict]) -> list[DateTimeRange]:
    return [
        DateTimeRange(
            map_dt(r["range"]["start"]),
            map_dt(r["range"]["end"]),
            RuleKind[r["kind"].upper()],
            r["comments"],
        )
        for r in ranges
    ]


def test_parser(data: dict):
    value = data["s"]
    astro = "sunrise" in value or "sunset" in value
    expected_ranges = map_ranges(data["ranges"])
    expected_rules = map_rules(data["rules"])

    oh = OpeningHours.parse(value, ctx)
    assert oh.expr.rules == expected_rules

    ranges = list(
        oh.iter_range(
            datetime.datetime(2021, 4, 4, tzinfo=TZ),
            datetime.datetime(2021, 4, 18, tzinfo=TZ),
        )
    )

    if astro:
        # The astro library for Rust produceed slightly different results
        assert len(ranges) == len(expected_ranges)
        threshold = datetime.timedelta(minutes=2)
        for r, expected in zip(ranges, expected_ranges):
            d_start = abs(r.start - expected.start)
            assert d_start <= threshold
            d_end = abs(r.end - expected.end)
            assert d_end <= threshold
            assert r.kind == expected.kind
            assert r.comments == expected.comments
    else:
        assert ranges == expected_ranges
