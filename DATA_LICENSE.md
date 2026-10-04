# Data attribution and license notice

This notice concerns the data, separately from the Apache License 2.0 that
applies to this repository's software.

**Upstream dataset:** Fanaee-T, H. (2013). *Bike Sharing* [Dataset].
UCI Machine Learning Repository. <https://doi.org/10.24432/C5W894>.

The [UCI source page](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset),
accessed 2026-10-04, identifies the dataset as licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Sharing and adaptation require appropriate attribution, a license reference and
an indication of changes. The [license text](https://creativecommons.org/licenses/by/4.0/legalcode)
also includes its warranty disclaimer. No endorsement by UCI or the authors is
implied.

The archive requests this associated publication citation:
Fanaee-T, H., and Gama, J. (2013). *Event labeling combining ensemble detectors
and background knowledge*. Progress in Artificial Intelligence.
<https://doi.org/10.1007/s13748-013-0040-3>.

The historical `bike.csv` is a numerically reconciled derivative of the UCI
hourly table. Changes include renamed/dropped columns, date formatting,
month-based seasons, scaled weather values and CSV line endings. The
[data audit](docs/data.md) documents exact relationships, conflicting source
metadata and the hashes of the compared snapshots. The modernization preserves
this derivative byte-for-byte.

The original intermediary and transformation script remain unknown. This
notice records the verified upstream terms and attribution; it does not claim
to reconstruct every step in the derivative's distribution history. The
software license is not a substitute for these data terms.
