# Data contract and provenance

The maintained loader reads the historical `bike.csv` without modifying its
bytes. The audit reconciles it with UCI's `hour.csv`, downloaded on 2026-10-04.
All **17,379 timestamps and all three rental-count columns match exactly**.
Every remaining local field is also explained by the rules below.

This establishes numeric correspondence to a specific upstream snapshot. It
does **not** recover the original download, intermediary distributor or script
that produced the 2020 CSV. Matching column names alone would not establish this
relationship; the evidence here compares every keyed row and value.

## Source and attribution

The source is Hadi Fanaee-T's [Bike Sharing dataset at UCI](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset),
[DOI 10.24432/C5W894](https://doi.org/10.24432/C5W894). UCI's archive README
attributes rental logs to Capital Bikeshare in Washington, D.C., and weather to
Freemeteo. This audit starts at UCI's distributed hourly table; it does not
reconstruct those earlier feeds.

UCI currently lists **CC BY 4.0** for the dataset. The archive also requests
citation of Fanaee-T and Gama's *Event labeling combining ensemble detectors and
background knowledge*, [DOI 10.1007/s13748-013-0040-3](https://doi.org/10.1007/s13748-013-0040-3).
The repository's [data attribution notice](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/DATA_LICENSE.md)
records these terms separately from the software's Apache 2.0 license.

## Verified field mapping

`u` denotes the named UCI field. Rounding is to the shown decimal precision.
These are relationships verified against **every row**, not a recovered copy of
the original transformation program.

| Historical column | UCI field | Verified relationship and interpretation |
| --- | --- | --- |
| `Date` | `dteday` | Same date, formatted month/day/year instead of ISO date |
| `Hour` | `hr` | Unchanged integer, 0–23 |
| `Season` | date/month | 1 = March–May, 2 = June–August, 3 = September–November, 4 = December–February |
| `Holiday` | `holiday` | Unchanged binary indicator; the holiday calendar was not independently rebuilt |
| `Day of the Week` | `weekday` | Unchanged; Sunday = 0 through Saturday = 6, checked against each date |
| `Working Day` | `workingday` | Unchanged; 1 on Monday–Friday excluding marked holidays |
| `Weather Type` | `weathersit` | Unchanged codes; see interpretation below |
| `Temperature F` | `temp` | `round(17.6 + 84.6 * (u - 0.02) / 0.98, 1)`; legacy scale, physical conversion unresolved |
| `Temperature Feels F` | `atemp` | `round(3.2 + 118.8 * u, 1)`; consistent with UCI page's Celsius inverse then Fahrenheit conversion |
| `Humidity` | `hum` | `100 * u`, relative humidity percentage |
| `Wind Speed` | `windspeed` | `round(67 * u)`; numeric scale recovered, physical unit unverified |
| `Casual Users` | `casual` | Unchanged nonnegative rental count, not a predictor |
| `Registered Users` | `registered` | Unchanged nonnegative rental count, not a predictor |
| `Total Users` | `cnt` | Unchanged target; equals casual plus registered |

UCI's `instant`, `yr` and `mnth` columns are omitted. Local dates preserve the
year and month. The historical CSV uses carriage-return line separators; the
loader accepts these and UTF-8 with an optional BOM.

Weather codes summarize 1: clear/partly cloudy, 2: mist/cloud, 3: light rain/snow,
and 4: severe rain/snow/fog combinations. These are recorded observations, not
archived forecasts. Future observed weather must not become a forecast-time
predictor without an explicit availability policy.

## Metadata conflicts and unresolved units

The UCI web page and the archive's `Readme.txt` disagree:

- The page labels upstream season 1 as winter; the README calls it spring.
  The local file instead follows month-based seasons. Simply rotating UCI's
  codes disagrees with **3,922 rows**, around seasonal boundaries.
- The page defines hourly Celsius temperature as `-8 + 47 * temp`; the README
  describes multiplication by 41. Neither reproduces `Temperature F`.
- The page defines apparent Celsius temperature as `-16 + 66 * atemp`; the
  README describes multiplication by 50. Only the page's rule, followed by
  Fahrenheit conversion and rounding, reproduces `Temperature Feels F`.

For temperature, the observed UCI range is 0.02–1.00. Rescaling that range to
−8–39 °C, then converting to Fahrenheit, reproduces the entire local column.
That is evidence of a possible transformation, not proof of its implementation
or physical correctness. For example, the first local value is **36.6**, while
the web page's inverse and Fahrenheit conversion give **37.9**. We retain the
legacy values and do not silently interpret them as corrected measurements.
The wind-speed scale factor is documented by UCI, but its physical unit is not
established by the inspected primary artifacts.

Neither date/hour table encodes a timezone, UTC offset or daylight-saving fold.
The location does not by itself establish how timestamps were aggregated.
All current evaluation therefore uses the recorded **naive calendar**, with no
UTC conversion or daylight-saving repair. The maintained candidates do not use weather
columns; these unit conflicts do not change their forecasts.

## Coverage and missingness

| Year | Observed rows | Naive hourly positions | Absent hours |
| --- | ---: | ---: | ---: |
| 2011 | 8,645 | 8,760 | 115 |
| 2012 | 8,734 | 8,784 | 50 |
| Total | 17,379 | 17,544 | 165 |

The inclusive span is 2011-01-01 00:00 through 2012-12-31 23:00. There are no
empty cells, duplicate timestamps or zero-total rows in this snapshot. The
local and UCI timestamp sets are identical, so these 165 gaps already exist in
UCI's hourly table; they were not introduced by this derivative. Their causes
cannot be determined from the hourly table alone. A missing row is not evidence
of zero rentals, and is never filled as zero. UCI's no-missing-values metadata
refers to table cells, not a complete hourly grid. Its web page's instance count
of 17,389 also differs from the 17,379 rows in the archive and its README.

Observed rentals describe completed rentals across the system. They do not
identify unconstrained demand, lost rentals, station inventory or a rebalancing
policy. Both count components reveal the target and are excluded as predictors.

## Reproduce the audit

The [source manifest](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/benchmarks/data-sources.json)
records source URLs, access date and SHA-256 hashes. The
[committed audit](https://github.com/DiogoRibeiro7/bike-sharing/blob/master/benchmarks/data-audit.json)
records local validation, monthly gaps and row-level reconciliation totals.

After installing the project, verify local evidence **offline**:

```bash
poetry run python -m bike_sharing.audit --check benchmarks/data-audit.json
```

CI runs this command. It validates all 14 local columns and checks the exact
historical bytes against the committed evidence. An offline check does not
repeat the external-source comparison. To repeat that comparison explicitly:

```bash
mkdir -p results/uci
curl --fail --location \
  'https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip' \
  --output results/uci/source.zip
python -m zipfile --extract results/uci/source.zip results/uci
poetry run python -m bike_sharing.audit \
  --upstream results/uci/hour.csv --check benchmarks/data-audit.json
```

The source check requires matching timestamp sets, applies the listed rules to
every row and checks the source file's hash through comparison with the saved
report. Row order is immaterial to matching; byte identity is separately
recorded. No source downloads occur in CI or forecasting. To generate a fresh
report, omit `--check` and redirect stdout to a new JSON file for review.
The audit does not train a model, compute errors or select candidates. The
separate [frozen final assessment](final-results.md) is now recorded.

## Maintained forecasting loader

The forecasting loader requires only `Date`, `Hour`, `Total Users`,
`Casual Users` and `Registered Users`. It checks dates, integer hours 0–23,
nonnegative integer counts, count totals, unique headers, consistent row widths
and unique timestamps, then sorts records chronologically. Extra named fields
are allowed but unused. The separate audit intentionally applies the stricter
14-column historical schema and calendar/weather-field checks described above.
The historical CSV is not included in the Python wheel.
