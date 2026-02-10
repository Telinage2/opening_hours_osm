from typing import Optional
import datetime

import pytest

from opening_hours_osm import (
    OpeningHours,
    OsmParsingException,
    Context,
    CountryHolidays,
    RuleKind,
)
from opening_hours_osm.schedule import Schedule, TimeRange, ExtendedTime
from opening_hours_osm.model.enums import HolidayKind


@pytest.mark.parametrize(
    "value,date,country,schedule",
    [
        (
            "2020:10:00-12:00; PH off",
            datetime.date(2020, 7, 14),
            "FR",
            [TimeRange(ExtendedTime(0, 0), ExtendedTime(24, 0), RuleKind.CLOSED)],
        ),
        (
            "2020:10:00-12:00; PH off",
            datetime.date(2020, 7, 14),
            "US",
            [TimeRange(ExtendedTime(10, 0), ExtendedTime(12, 0), RuleKind.OPEN)],
        ),
        # Independence Day is a federal holiday. If July 4 is a Saturday, it is
        # observed on Friday, July 3.
        (
            "2020:10:00-12:00; PH off",
            datetime.date(2020, 7, 3),
            "US",
            [TimeRange(ExtendedTime(0, 0), ExtendedTime(24, 0), RuleKind.CLOSED)],
        ),
    ],
)
def test_holidays(
    value: str, date: datetime.date, country: str, schedule: list[TimeRange]
):
    ctx = Context(holidays=CountryHolidays(country))
    assert ctx.holidays.is_holiday(date, HolidayKind.PH) == all(
        s.kind == RuleKind.CLOSED for s in schedule
    )

    oh = OpeningHours.parse(value, ctx)
    got_schedule = oh.schedule_at(date)
    expected_schedule = Schedule(schedule)
    assert got_schedule == expected_schedule


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sdasdlasdj a3reaw",
        "\n",
        ";",
        "||",
        'Mo[2] - 7 days; 00:23-00:42 unknown "warning at correct position?"',
        ':week 02-54 00:00-24:00; 00:23-00:42 unknown "warning at correct position?"',
        ':::week 02-54 00:00-24:00; 00:23-00:42 unknown "warning at correct position?"',
        'week :2-54 00:00-24:00; 00:23-00:42 unknown "warning at correct position?"',
        "week week",
        "week week 05",
        "week 00",
        "week 54",
        "week 01-54",
        "week 00-54",
        "week 30-40/27",
        'week week 00:00-24:00; 00:23-00:42 unknown "warning at correct position?"',
        'week 02-53 00:00-24:00:; 00:23-00:42 unknown "warning at correct position?"',
        'week 02-53 00:00-24:00:::; 00:23-00:42 unknown "warning at correct position?"',
        'week 02-53 00::00-24:00; 00:23-00:42 unknown "warning at correct position?"',
        '(sunrise+01:00-sunset; 00:23-00:42 unknown "warning at correct position?"',
        '(sunrise+01::)-sunset; 00:23-00:42 unknown "warning at correct position?"',
        '(sunrise)-sunset; 00:23-00:42 unknown "warning at correct position?"',
        '(sunset-1); 00:23-00:42 unknown "warning at correct position?"',
        '(sunrise+2); 00:23-00:42 unknown "warning at correct position?"',
        '(dawn-1); 00:23-00:42 unknown "warning at correct position?"',
        '(dusk+3); 00:23-00:42 unknown "warning at correct position?"',
        '(; 00:23-00:42 unknown "warning at correct position?"',
        'sunrise-(; 00:23-00:42 unknown "warning at correct position?"',
        'sunrise-sunset,(; 00:23-00:42 unknown "warning at correct position?"',
        'dusk;dawn; 00:23-00:42 unknown "warning at correct position?"',
        'dusk; 00:23-00:42 unknown "warning at correct position?"',
        '27:00-29:00; 00:23-00:42 unknown "warning at correct position?"',
        '14:/; 00:23-00:42 unknown "warning at correct position?"',
        '14:00/; 00:23-00:42 unknown "warning at correct position?"',
        '14:00-/; 00:23-00:42 unknown "warning at correct position?"',
        '14:00-16:00,.; 00:23-00:42 unknown "warning at correct position?"',
        '11; 00:23-00:42 unknown "warning at correct position?"',
        '11am; 00:23-00:42 unknown "warning at correct position?"',
        '14:00-16:00,11:00; 00:23-00:42 unknown "warning at correct position?"',
        '21:00-22:60; 00:23-00:42 unknown "warning at correct position?"',
        '21:60-22:59; 00:23-00:42 unknown "warning at correct position?"',
        'Sa[1.; 00:23-00:42 unknown "warning at correct position?"',
        'Sa[1,0,3]; 00:23-00:42 unknown "warning at correct position?"',
        'Sa[1,3-6]; 00:23-00:42 unknown "warning at correct position?"',
        'Sa[1,3-.]; 00:23-00:42 unknown "warning at correct position?"',
        'Sa[1,3,.]; 00:23-00:42 unknown "warning at correct position?"',
        'PH + 2 day; 00:23-00:42 unknown "warning at correct position?"',
        'Su-PH; 00:23-00:42 unknown "warning at correct position?"',
        'easter + 370 days; 00:23-00:42 unknown "warning at correct position?"',
        'easter - 2 days - 2012 easter + 2 days: open "Easter Monday"; 00:23-00:42 unknown "warning at correct position?"',
        '2012 easter - 2 days - easter + 2 days: open "Easter Monday"; 00:23-00:42 unknown "warning at correct position?"',
        'Jan,,,Dec; 00:23-00:42 unknown "warning at correct position?"',
        'Mo,,Th; 00:23-00:42 unknown "warning at correct position?"',
        '12:00-15:00/60; 00:23-00:42 unknown "warning at correct position?"',
        '12:00-15:00/1:; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 00-Aug 23; 00:23-00:42 unknown "warning at correct position?"',
        'Feb 30-Aug 02; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 02-Aug 42; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 02-Aug 32; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 02-32; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 32-34; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 02-32/2; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 32; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 02-20/0; 00:23-00:42 unknown "warning at correct position?"',
        '2014-2020/0; 00:23-00:42 unknown "warning at correct position?"',
        '2014/0; 00:23-00:42 unknown "warning at correct position?"',
        '2014-; 00:23-00:42 unknown "warning at correct position?"',
        '26:00-27:00; 00:23-00:42 unknown "warning at correct position?"',
        '23:00-55:00; 00:23-00:42 unknown "warning at correct position?"',
        '23:59-48:01; 00:23-00:42 unknown "warning at correct position?"',
        '25am-26pm; 00:23-00:42 unknown "warning at correct position?"',
        '24am-26pm; 00:23-00:42 unknown "warning at correct position?"',
        '23am-49pm; 00:23-00:42 unknown "warning at correct position?"',
        '10:am - 8:pm; 00:23-00:42 unknown "warning at correct position?"',
        '25pm-26am; 00:23-00:42 unknown "warning at correct position?"',
        '12:00; 00:23-00:42 unknown "warning at correct position?"',
        '„testing„; 00:23-00:42 unknown "warning at correct position?"',
        '‚testing‚; 00:23-00:42 unknown "warning at correct position?"',
        '»testing«; 00:23-00:42 unknown "warning at correct position?"',
        '」testing「; 00:23-00:42 unknown "warning at correct position?"',
        '』testing『; 00:23-00:42 unknown "warning at correct position?"',
        '』testing「; 00:23-00:42 unknown "warning at correct position?"',
        '』testing«; 00:23-00:42 unknown "warning at correct position?"',
        '』testing"; 00:23-00:42 unknown "warning at correct position?"',
        '"testing«; 00:23-00:42 unknown "warning at correct position?"',
        ' || open; 00:23-00:42 unknown "warning at correct position?"',
        'Jan 00; 00:23-00:42 unknown "warning at correct position?"',
        'Jan 32; 00:23-00:42 unknown "warning at correct position?"',
        'Feb 30; 00:23-00:42 unknown "warning at correct position?"',
        'Mar 32; 00:23-00:42 unknown "warning at correct position?"',
        'Apr 31; 00:23-00:42 unknown "warning at correct position?"',
        'Mai 32; 00:23-00:42 unknown "warning at correct position?"',
        'Jun 31; 00:23-00:42 unknown "warning at correct position?"',
        'Jul 32; 00:23-00:42 unknown "warning at correct position?"',
        'Aug 32; 00:23-00:42 unknown "warning at correct position?"',
        'Sep 31; 00:23-00:42 unknown "warning at correct position?"',
        'Oct 32; 00:23-00:42 unknown "warning at correct position?"',
        'Nov 31; 00:23-00:42 unknown "warning at correct position?"',
        'Dec 32; 00:23-00:42 unknown "warning at correct position?"',
        'We 12:00-18:00,,,,,,; 00:23-00:42 unknown "warning at correct position?"',
    ],
)
def test_parser_fail(value: str):
    with pytest.raises(OsmParsingException):
        OpeningHours.parse(value)


@pytest.mark.parametrize(
    "value,start,expected_end",
    [
        pytest.param(
            "Apr 1 - Nov 3 00:00-24:00",
            datetime.datetime(2018, 6, 11),
            datetime.datetime(2018, 11, 4),
            id="handling_of_spaces",
        ),
        pytest.param(
            "2022 Jan 1-2023 Dec 31",
            datetime.datetime(2022, 1, 1),
            datetime.datetime(2024, 1, 1),
            id="no_date_range_end_in_intervals",
        ),
        pytest.param(
            "Jan-Dec", datetime.datetime(2024, 1, 1), None, id="infinite_loop"
        ),
    ],
)
def test_parser_issues(
    value: str, start: datetime.datetime, expected_end: Optional[datetime.datetime]
):
    oh = OpeningHours.parse(value)
    assert oh.next_change(start) == expected_end
