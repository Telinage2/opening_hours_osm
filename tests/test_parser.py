"""
Tests sourced from the JS library
https://github.com/opening-hours/opening_hours.js/blob/develop/test/test.js
"""

import pytest
from datetime import datetime

from opening_hours_osm import parse_opening_hours

"""
test.addTest('Time intervals', [
        '10:00-12:00',
        '08:00-09:00; 10:00-12:00',
        '10:00-12:00,',
        '10:00-12:00;',
        '10-12', // Do not use. Returns warning.
        '10:00-11:00,11:00-12:00',
        '10:00-12:00,10:30-11:30',
        '10:00-14:00; 12:00-14:00 off',
    ], '2012-10-01 0:00', '2012-10-08 0:00', [
        [ '2012-10-01 10:00', '2012-10-01 12:00' ],
        [ '2012-10-02 10:00', '2012-10-02 12:00' ],
        [ '2012-10-03 10:00', '2012-10-03 12:00' ],
        [ '2012-10-04 10:00', '2012-10-04 12:00' ],
        [ '2012-10-05 10:00', '2012-10-05 12:00' ],
        [ '2012-10-06 10:00', '2012-10-06 12:00' ],
        [ '2012-10-07 10:00', '2012-10-07 12:00' ],
    ], 1000 * 60 * 60 * 2 * 7, 0, true, {}, 'not last test');
    name, values, from, to, expected_intervals, expected_duration, expected_unknown_duration, expected_weekstable, nominatim_data, last, oh_mode
"""


@pytest.mark.parametrize(
    "values,d_from,d_to,expected_intervals,expected_duration,expected_unknown_duration,expected_weekstable",
    [
        (
            [
                "10:00-12:00",
                "08:00-09:00; 10:00-12:00",
                "10:00-12:00,",
                "10:00-12:00;",
                "10:00-11:00,11:00-12:00",
                "10:00-12:00,10:30-11:30",
                "10:00-14:00; 12:00-14:00 off",
            ],
            "2012-10-01 0:00",
            "2012-10-08 0:00",
            [
                ("2012-10-01 10:00", "2012-10-01 12:00"),
                ("2012-10-02 10:00", "2012-10-02 12:00"),
                ("2012-10-03 10:00", "2012-10-03 12:00"),
                ("2012-10-04 10:00", "2012-10-04 12:00"),
                ("2012-10-05 10:00", "2012-10-05 12:00"),
                ("2012-10-06 10:00", "2012-10-06 12:00"),
                ("2012-10-07 10:00", "2012-10-07 12:00"),
            ],
            1000 * 60 * 60 * 2 * 7,
            0,
            True,
        )
    ],
)
def test_time_intervals(
    values: list[str],
    d_from: str,
    d_to: str,
    expected_intervals: list,
    expected_duration: int,
    expected_unknown_duration: int,
    expected_weekstable: bool,
):
    pass


def run_test(
    value: str,
    d_from: datetime | str,
    d_to: datetime | str,
    expected_intervals: list,
    expected_duration: int,
    expected_unknown_duration: int,
    expected_weekstable: bool,
    nominatim_data: dict = {},
):
    if isinstance(d_from, datetime):
        date_from = d_from
    else:
        date_from = datetime.strptime(d_from, "%Y-%m-%d %H:%M")
    if isinstance(d_to, datetime):
        date_to = d_from
    else:
        date_to = datetime.strptime(d_to, "%Y-%m-%d %H:%M")

    oh = parse_opening_hours(value)

