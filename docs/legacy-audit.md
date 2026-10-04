# Historical notebook audit

The original `bike_sharing.ipynb` remains unchanged as a 2020 exploratory artifact.
It is not the maintained entry point and its outputs are not current benchmark
results. It is excluded from lint, type and execution checks for that reason.

Inspection identified these evaluation issues:

1. Min-max scaling and PCA are fitted before the train/test split, so evaluation
   feature information influences preprocessing.
2. `train_test_split` randomly mixes time periods; its scores do not establish
   performance when forecasting later observations from earlier ones.
3. The random-forest search calls `GridSearchCV.fit(X, y)` on the full dataset,
   then scores its fitted estimator on `X_test`, which participated in fitting.
4. The notebook mixes printed MSE and RMSE, preventing direct interpretation of
   the displayed numbers as a consistent comparison.
5. Observed contemporaneous weather is available to its regressions without an
   explicit forecast-time availability contract.

The notebook does remove the casual/registered components from predictors;
that existing safeguard is preserved as an explicit rule in the maintained
design. The new code computes weekday directly from the date rather than
reusing the notebook's season recoding.

The first maintained implementation fits only two training-data means. More
complex preprocessing and model selection belong to the temporal benchmark
work, where each fit must be contained within its training fold.
