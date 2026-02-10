from typing import Optional
import datetime
import pytest
from pytest_mock import MockerFixture

from opening_hours_osm import OpeningHours
from opening_hours_osm.opening_hours import DateTimeRange, TimeRange, RuleKind
from opening_hours_osm.model.time import ExtendedTime


def test_s000_idunn_interval_stops_next_day():
    oh = OpeningHours.parse("Tu-Su 09:30-18:00; Th 09:30-21:45")
    start = datetime.datetime(2018, 6, 11)
    end = start + datetime.timedelta(days=1)
    assert list(oh.iter_range(start, end)) == [
        DateTimeRange(start, end, RuleKind.CLOSED)
    ]


@pytest.mark.parametrize(
    "value,date,schedule",
    [
        pytest.param(
            "Tu-Su 09:30-18:00; Th 09:30-21:45",
            datetime.date(2018, 6, 14),
            [TimeRange(ExtendedTime(9, 30), ExtendedTime(21, 45), RuleKind.OPEN)],
            id="s001_idunn_override_weekday",
        ),
        pytest.param(
            "Tu-Su 09:30-18:00; Th 09:30-21:45",
            datetime.date(2018, 6, 15),
            [TimeRange(ExtendedTime(9, 30), ExtendedTime(18, 0), RuleKind.OPEN)],
            id="s002_idunn_override_weekday_keep_unmatched",
        ),
        pytest.param(
            "Jan-Feb 10:00-20:00",
            datetime.date(2018, 6, 15),
            [],
            id="s003_idunn_space_separator",
        ),
        pytest.param(
            "Mo-Su 09:00-00:00 open",
            datetime.date(2018, 6, 14),
            [TimeRange(ExtendedTime(9, 0), ExtendedTime(24, 0), RuleKind.OPEN)],
            id="s004_idunn_until_midnight_as_00",
        ),
        pytest.param(
            "We-Mo 11:00-19:00",
            [
                datetime.date(2018, 6, 11),
                datetime.date(2018, 6, 13),
                datetime.date(2018, 6, 14),
            ],
            [TimeRange(ExtendedTime(11, 0), ExtendedTime(19, 0), RuleKind.OPEN)],
            id="s005_idunn_days_cycle1",
        ),
        pytest.param(
            "We-Mo 11:00-19:00",
            datetime.date(2018, 6, 12),
            [],
            id="s005_idunn_days_cycle2",
        ),
    ],
)
def test_regression_schedule(
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
        pytest.param(
            "Oct-Mar 07:30-19:30; Apr-Sep 07:00-21:00",
            datetime.datetime(2019, 2, 10, 11, 0),
            datetime.datetime(2019, 2, 10, 19, 30),
            id="s006_idunn_month_cycle",
        ),
        pytest.param(
            "week04",
            datetime.datetime(2024, 12, 31, 12, 0),
            datetime.datetime(2025, 1, 20, 0, 0),
            id="s015_fuzz_31dec_may_be_week_01",
        ),
        pytest.param(
            "week01",
            datetime.datetime(2010, 1, 3, 0, 55),
            datetime.datetime(2010, 1, 4, 0, 0),
            id="s016_fuzz_week01",
        ),
        pytest.param(
            "week01SH",
            datetime.datetime(2010, 1, 3, 0, 55),
            None,
            id="s016_fuzz_week01_sh",
        ),
        pytest.param(
            "May2+",
            datetime.datetime(2020, 1, 1, 12, 0),
            datetime.datetime(2020, 5, 2),
            id="s017_fuzz_open_range_timeout",
        ),
        pytest.param(
            "May2+",
            datetime.datetime(2020, 5, 15, 12, 0),
            datetime.datetime(2021, 1, 1),
            id="s017_fuzz_open_range_timeout2",
        ),
        pytest.param(
            "PH",
            datetime.datetime(2106, 2, 12, 13, 54),
            None,
            id="test_s018_fuzz_ph_infinite_loop",
        ),
        pytest.param(
            "week 13",
            datetime.datetime(7583, 1, 1, 12, 0),
            datetime.datetime(7583, 3, 28),
            id="2106, 2, 12, 13, 54",
        ),
    ],
)
def test_regression(
    value: str,
    start: datetime.datetime,
    expected_end: Optional[datetime.datetime],
    mocker: MockerFixture,
):
    oh = OpeningHours.parse(value)
    spy = mocker.spy(oh, "schedule_at")
    assert oh.next_change(start) == expected_end
    assert spy.call_count < 30000


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(
            "Mo,Th,Sa,Su 09:00-18:00; We,Fr 09:00-21:45; Tu off; Jan 1,May 1,Dec 25: off",
            id="s007_idunn_date_separator",
        ),
        pytest.param(
            "Mo-Su 00:00-01:00, 07:30-24:00 ; PH off",
            id="s008_pj_no_open_before_separator",
        ),
        pytest.param(
            "Mo-Su 00:00-01:00, 07:30-24:00 ; PH off ; 2021 Mar 28 00:00-01:00",
            id="s009_pj_no_open_before_separator",
        ),
    ],
)
def test_regression_parses(value: str):
    OpeningHours.parse(value)


def test_s010_pj_slow_after_24_7(mocker: MockerFixture):
    oh = OpeningHours.parse("24/7 open ; 2021Jan-Feb off")
    spy = mocker.spy(oh, "schedule_at")
    assert oh.next_change(datetime.datetime(2021, 7, 9, 19, 30)) is None
    assert spy.call_count < 10


def test_s010_pj_slow_after_24_7b(mocker: MockerFixture):
    oh = OpeningHours.parse("24/7 open ; 2021 Jan 01-Feb 10 off")
    spy = mocker.spy(oh, "schedule_at")
    assert oh.next_change(datetime.datetime(2021, 7, 9, 19, 30)) is None
    assert spy.call_count < 10


def test_s013_fuzz_slow_weeknum(mocker: MockerFixture):
    oh = OpeningHours.parse("Novweek09")
    spy = mocker.spy(oh, "schedule_at")
    assert oh.next_change(datetime.datetime(2020, 1, 1, 0, 0)) is None
    assert spy.call_count < 8000 * 4
