from typing import Optional
import datetime

import pytest

from opening_hours_osm.model.day import VariableDate


@pytest.mark.parametrize(
    "year,date",
    [
        (0, None),
        (1901, datetime.date(1901, 4, 7)),
        (1961, datetime.date(1961, 4, 2)),
        (2024, datetime.date(2024, 3, 31)),
        (2025, datetime.date(2025, 4, 20)),
        (2050, datetime.date(2050, 4, 10)),
        (2106, datetime.date(2106, 4, 18)),
        (2200, datetime.date(2200, 4, 6)),
        (3000, datetime.date(3000, 4, 13)),
    ],
)
def test_easter(year: int, date: Optional[datetime.date]):
    assert VariableDate.easter(year) == date
