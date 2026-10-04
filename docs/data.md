# Data contract

The maintained loader reads the existing `bike.csv` without modifying it.
It accepts UTF-8 (with an optional BOM) and CSV newline conventions, including
the historical file's carriage-return separators.

## Required fields

| CSV column | Validation | Use |
| --- | --- | --- |
| `Date` | Parseable month/day/year date | Calendar timestamp |
| `Hour` | Integer from 0 through 23 | Calendar timestamp |
| `Total Users` | Nonnegative integer | Observed target |
| `Casual Users` | Nonnegative integer | Validate target total only |
| `Registered Users` | Nonnegative integer | Validate target total only |

The component counts must sum to `Total Users`. Header names must be unique,
row widths must match the header, and timestamps must be unique. Observations
are sorted by timestamp. Extra named fields are allowed but not used or
validated by the baseline.

## Verified snapshot

- 17,379 observations, spanning 2011-01-01 00:00 to 2012-12-31 23:00.
- 17,544 hourly calendar positions in that inclusive span, leaving 165 absent.
- SHA-256: `77b9643b9a646c229fe8fcd972ab8689885235b6d31eb3e469661f2b5523fd97`.

Absence is not a zero-rental observation. A gap may have several explanations;
the baseline does not impute a cause. The historical file is not shipped inside
the package wheel and the runtime does not fetch replacement data.

## Unresolved provenance

The historical notebook does not establish a complete upstream data lineage.
The original source, exact transformation history, field units, season coding,
timezone and data redistribution terms remain to be verified in
[issue #2](https://github.com/DiogoRibeiro7/bike-sharing/issues/2).

The temperature headers name Fahrenheit, but the baseline does not interpret or
use those fields. The software's Apache license does not resolve the data's
license. The current work retains the existing file and records its identity.
