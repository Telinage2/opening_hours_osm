# opening-hours-osm

Python library for parsing the opening hour format used by OpenStreetMap.

Reference: <https://wiki.openstreetmap.org/wiki/Key:opening_hours>

The library was ported from this Rust library <https://github.com/remi-dupre/opening-hours-rs>.

## Usage

```python
from datetime import datetime

from opening_hours_osm import OpeningHours
from opening_hours_osm.context import Context, GeoLocale, CountryHolidays

ctx = Context(
    # Locale for determining timezone and astronomic events
    GeoLocale(48.36658170393406, 10.89542692530624),
    CountryHolidays("DE", "BY")
)

oh = OpeningHours.parse("Mo-Fr 09:00-18:00; PH off", ctx)

for r in oh.iter_range(datetime(2021, 4, 8, 0, 0), datetime(2021, 4, 11, 0, 0)):
    print(r.start.isoformat(), "-", r.end.isoformat(), r.kind, r.comments)

assert oh.is_open(datetime(2021, 4, 8, 12, 0))
```

```txt
2021-04-08T00:00:00+02:00 - 2021-04-08T09:00:00+02:00 closed []
2021-04-08T09:00:00+02:00 - 2021-04-08T18:00:00+02:00 open []
2021-04-08T18:00:00+02:00 - 2021-04-09T09:00:00+02:00 closed []
2021-04-09T09:00:00+02:00 - 2021-04-09T18:00:00+02:00 open []
2021-04-09T18:00:00+02:00 - 2021-04-11T00:00:00+02:00 closed []
```
