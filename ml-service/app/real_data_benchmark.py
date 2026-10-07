"""Capacity-based benchmark for the public ULB/Worldline credit-card dataset.

This is deliberately a small, transparent baseline rather than a leaderboard
submission. It does not resample the test data, tune on the test window, or
claim production performance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "raw" / "creditcard.csv"
DEFAULT_REPORT = ROOT / "reports" / "ulb_capacity_benchmark.json"
LABEL = "Class"
TIME = "Time"
AMOUNT = "Amount"
FEATURES = [f"V{i}" for i in range(1, 29)] + [AMOUNT]
CAPACITIES = (0.001, 0.0025, 0.005, 0.01, 0.02)


def load_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    required = {TIME, AMOUNT, LABEL, *FEATURES}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    data = data[list(dict.fromkeys([TIME, *FEATURES, LABEL]))].copy()
    data[TIME] = pd.to_numeric(data[TIME], errors="raise")
    data[LABEL] = pd.to_numeric(data[LABEL], errors="raise").astype("int8")
    if set(data[LABEL].unique()) != {0, 1}:
        raise ValueError("Class must contain both 0 and 1")
    if data[FEATURES].isna().any().any():
        raise ValueError("Features contain missing values; inspect the source file first")
    return data.sort_values(TIME, kind="mergesort").reset_index(drop=True)


def temporal_split(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Use first 60%, next 20%, and final 20% of ordered transactions."""
    n = len(data)
    train_end, validation_end = int(n * 0.60), int(n * 0.80)
    train, validation, test = data.iloc[:train_end], data.iloc[train_end:validation_end], data.iloc[validation_end:]
    for name, part in (("train", train), ("validation", validation), ("test", test)):
        if part[LABEL].nunique() < 2:
            raise ValueError(f"{name} time window contains only one class; report this limitation")
    return train, validation, test


def capacity_metrics(y: np.ndarray, scores: np.ndarray, amounts: np.ndarray,
                     capacity: float, baseline_scores: np.ndarray | None = None) -> dict:
    n = len(y)
    k = max(1, int(np.ceil(n * capacity)))
    fraud_total = int(y.sum())
    fraud_amount_total = float(amounts[y == 1].sum())

    def evaluate(ranking: np.ndarray) -> dict:
        selected = np.argsort(ranking, kind="mergesort")[-k:]
        fraud_caught = int(y[selected].sum())
        amount_caught = float(amounts[selected][y[selected] == 1].sum())
        return {
            "reviewCount": int(k),
            "reviewRate": round(k / n, 6),
            "fraudCaught": fraud_caught,
            "fraudCaptureRate": round(fraud_caught / max(1, fraud_total), 6),
            "precisionAtK": round(fraud_caught / k, 6),
            "falsePositiveReviews": int(k - fraud_caught),
            "fraudTransactionAmountCaptured": round(amount_caught, 2),
            "fraudTransactionAmountCaptureRate": round(amount_caught / max(1.0, fraud_amount_total), 6),
        }

    result = {"capacityRate": capacity, "model": evaluate(scores)}
    if baseline_scores is not None:
        result["amountDescendingBaseline"] = evaluate(baseline_scores)
    result["randomExpectedFraudCaught"] = round(k * fraud_total / n, 3)
    return result


def run(data_path: Path = DEFAULT_DATA, report_path: Path = DEFAULT_REPORT) -> dict:
    data = load_data(data_path)
    train, validation, test = temporal_split(data)

    # The middle window is reserved as a validation/monitoring period. This
    # baseline does not tune model parameters or a decision threshold on it.
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, solver="lbfgs"),
    )
    model.fit(train[FEATURES], train[LABEL])
    scores = model.decision_function(test[FEATURES])
    y = test[LABEL].to_numpy()
    amounts = test[AMOUNT].to_numpy(dtype=float)
    amount_baseline = test[AMOUNT].to_numpy(dtype=float)

    results = [capacity_metrics(y, scores, amounts, cap, amount_baseline) for cap in CAPACITIES]
    report = {
        "purpose": "Capacity-based ranking benchmark; not a production-effectiveness claim",
        "source": "ULB/Worldline Credit Card Fraud Detection dataset, mirrored on Zenodo record 7395559",
        "dataNature": "Anonymized real credit-card transactions from September 2013; two-day observation window",
        "target": LABEL,
        "features": FEATURES,
        "excludedFromFeatures": [TIME, LABEL],
        "split": {
            "method": "stable chronological order by Time; first 60% train, next 20% validation, final 20% untouched test",
            "trainRows": len(train), "trainFrauds": int(train[LABEL].sum()),
            "validationRows": len(validation), "validationFrauds": int(validation[LABEL].sum()),
            "testRows": len(test), "testFrauds": int(test[LABEL].sum()),
            "trainTimeRange": [float(train[TIME].min()), float(train[TIME].max())],
            "validationTimeRange": [float(validation[TIME].min()), float(validation[TIME].max())],
            "testTimeRange": [float(test[TIME].min()), float(test[TIME].max())],
        },
        "model": "StandardScaler + LogisticRegression(class_weight='balanced', C=1.0); no resampling; no probability calibration",
        "testMetrics": {
            "fraudRate": round(float(y.mean()), 6),
            "averagePrecision": round(float(average_precision_score(y, scores)), 6),
            "rocAuc": round(float(roc_auc_score(y, scores)), 6),
            "capacitySweep": results,
        },
        "interpretationLimits": [
            "The dataset spans only two days and cannot establish robustness to long-term drift.",
            "V1-V28 are anonymized PCA components and are not investigator-friendly evidence.",
            "Amount captured is transaction amount, not confirmed loss prevented or recovered.",
            "Public benchmark results do not establish performance on any employer's data.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.report), indent=2))


if __name__ == "__main__":
    main()
