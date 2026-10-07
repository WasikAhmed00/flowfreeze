# Public fraud dataset MVP sample

`Fraud.csv` is a bounded 10,000-row sample prepared from the public source repository's cleaned transaction export for the hackathon MVP. It is not upay BD production/customer data. The full source dataset is intentionally not required for local training.

Train with:

```bash
python -m ml.train_real --data-path data/ml/Fraud.csv --max-rows 10000 --seed 42
```
