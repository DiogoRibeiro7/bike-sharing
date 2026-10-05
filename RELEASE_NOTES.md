This release completes a bounded forecasting-to-decision case study: one audited
dataset, four interpretable point candidates, empirical intervals and one
asymmetric-cost workload planning study.

The frozen October–December assessment covers 2,168 observed hours. Poisson MAE
is 61.378 rentals/hour. Nominal 90% interval coverage is 85.19% overall and 74.81%
at high predicted demand. These shortfalls are reported without retuning.
At equal planning costs, the selected residual policy has final loss 62.766;
its small validation advantage over the point forecast does not persist.

The source and JSON evidence include exact reproduction commands, configuration
and source hashes, cost scenarios and limitations. The attached two-page decision
brief is written in LaTeX. Wheel and source distributions accompany the study;
the CSV remains repository data and is not included in the wheel.

These results do not establish realised savings, lost demand, station-level
rebalancing feasibility or reliable conditional coverage. Source provenance and
timezone/unit qualifications remain documented.
