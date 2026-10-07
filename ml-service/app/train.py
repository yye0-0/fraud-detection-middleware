"""Download, train, calibrate, and evaluate the PaySim risk-prioritization model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, precision_score,
                             recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, RAW_FIELDS, engineer_features

DATASET_ID = "flwrlabs/fed-fraud-paysim-banks"
DATASET_REVISION = "e803add98e4f03e7fa3f9a54754404d6565a83d7"
LABEL = "isFraud"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"
PROCESSED = ROOT / "data" / "processed"


def load_public_dataset() -> pd.DataFrame:
    dataset = load_dataset(DATASET_ID, revision=DATASET_REVISION)
    keep = RAW_FIELDS + [LABEL, "isFlaggedFraud"]
    frames = []
    for split in dataset.keys():
        frame = dataset[split].select_columns(keep).to_pandas()
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    data[LABEL] = pd.to_numeric(data[LABEL], errors="raise").astype("int8")
    data = data.sort_values(["step"], kind="mergesort").reset_index(drop=True)
    if data[LABEL].nunique() != 2 or data["step"].nunique() < 10:
        raise ValueError("Dataset contents do not satisfy the expected label/time contract")
    return data


def chronological_splits(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    step_counts = data.groupby("step", sort=True).size()
    cumulative = step_counts.cumsum() / len(data)
    train_end = int(cumulative.index[np.searchsorted(cumulative.to_numpy(), 0.70, side="left")])
    validation_end = int(cumulative.index[np.searchsorted(cumulative.to_numpy(), 0.85, side="left")])
    train = data[data.step <= train_end]
    validation = data[(data.step > train_end) & (data.step <= validation_end)]
    test = data[data.step > validation_end]
    metadata = {"trainStepMax": int(train_end), "validationStepRange": [int(train_end + 1), int(validation_end)],
                "testStepMin": int(validation_end + 1), "testStepMax": int(step_counts.index[-1]),
                "splitMethod": "chronological by step, with whole steps assigned to minimize row-share deviation"}
    if any(part[LABEL].nunique() != 2 for part in (train, validation, test)):
        raise ValueError("A chronological partition has only one class; adjust split cut points")
    return train, validation, test, metadata


def sample_training_rows(train: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    if max_rows <= 0 or len(train) <= max_rows:
        return train
    positives = train[train[LABEL] == 1]
    negatives = train[train[LABEL] == 0]
    negative_budget = max(1, max_rows - len(positives))
    if len(positives) >= max_rows:
        selected = positives.sample(n=max_rows, random_state=seed)
    else:
        selected = pd.concat([positives, negatives.sample(n=min(negative_budget, len(negatives)), random_state=seed)])
    return selected.sort_values("step", kind="mergesort").reset_index(drop=True)


def make_estimator() -> Pipeline:
    prep = ColumnTransformer([
        ("type", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median"))]), NUMERIC_FEATURES),
    ], remainder="drop", verbose_feature_names_out=False)
    classifier = HistGradientBoostingClassifier(
        max_iter=120, learning_rate=0.08, max_leaf_nodes=20, l2_regularization=1.0,
        class_weight="balanced", random_state=42,
    )
    return Pipeline([("features", prep), ("classifier", classifier)])


def calibrated_probability(estimator, calibrator, data: pd.DataFrame) -> np.ndarray:
    raw = estimator.predict_proba(engineer_features(data))[:, 1]
    clipped = np.clip(raw, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    return calibrator.predict_proba(logits)[:, 1]


def metrics(y: np.ndarray, probabilities: np.ndarray, threshold: float, flagged: np.ndarray, budget: float) -> dict:
    threshold_review = probabilities >= threshold
    review = threshold_review | (flagged == 1)
    positives = int(y.sum())
    top_n = max(1, int(np.ceil(len(y) * budget)))
    top_indices = np.argsort(probabilities)[-top_n:]
    model_recall = float(recall_score(y, review, zero_division=0))
    baseline_recall = float(((flagged == 1) & (y == 1)).sum() / max(1, positives))
    return {
        "transactions": int(len(y)), "fraudCases": positives,
        "fraudRate": round(float(y.mean()), 6),
        "averagePrecision": round(float(average_precision_score(y, probabilities)), 6),
        "rocAuc": round(float(roc_auc_score(y, probabilities)), 6),
        "brierScore": round(float(brier_score_loss(y, probabilities)), 6),
        "reviewBudgetRate": budget,
        "thresholdTestReviewRate": round(float(threshold_review.mean()), 6),
        "thresholdRateMultipleVsBudget": round(float(threshold_review.mean()) / budget, 3),
        "thresholdReviewCount": int(threshold_review.sum()),
        "thresholdQueueReviewCountWithExistingFlag": int(review.sum()),
        "thresholdQueueReviewRateWithExistingFlag": round(float(review.mean()), 6),
        "thresholdQueuePrecisionWithExistingFlag": round(float(precision_score(y, review, zero_division=0)), 6),
        "thresholdQueueFraudRecallWithExistingFlag": round(model_recall, 6),
        "topKPrecision": round(float(y[top_indices].mean()), 6),
        "topKReviewRate": round(float(top_n / len(y)), 6),
        "reviewsPer10000AtCapacity": int(round(float(top_n / len(y)) * 10000)),
        "topKFalsePositiveReviews": int(top_n - y[top_indices].sum()),
        "topKFraudCaptured": int(y[top_indices].sum()),
        "topKFraudCaptureRate": round(float(y[top_indices].sum() / max(1, positives)), 6),
        "baselineFlaggedRate": round(float(flagged.mean()), 6),
        "baselineFlaggedCount": int((flagged == 1).sum()),
        "baselineFlaggedFraudRecall": round(baseline_recall, 6),
        "baselineFlaggedPrecision": round(float(y[flagged == 1].mean()) if (flagged == 1).any() else 0.0, 6),
        "fraudRecallLiftVsExistingFlag": round(model_recall - baseline_recall, 6),
        "additionalFraudCasesCapturedVsExistingFlag": int(review[y == 1].sum() - ((flagged == 1) & (y == 1)).sum()),
        "reviewsPer10000AtThreshold": int(round(float(threshold_review.mean()) * 10000)),
    }


def create_demo_cases(test: pd.DataFrame, probabilities: np.ndarray, limit: int = 500) -> None:
    """Create a label-free demonstration queue; never expose `isFraud` to reviewers."""
    order = np.argsort(probabilities)[::-1][:limit]
    sample = test.iloc[order].reset_index(drop=True)
    cases = []
    for i, row in sample.iterrows():
        cases.append({
            "transactionId": f"paysim-demo-{i + 1:06d}",
            "accountId": f"synthetic-account-{int(row['step'])}-{i + 1:06d}",
            "step": int(row["step"]), "type": str(row["type"]), "amount": float(row["amount"]),
            "oldbalanceOrg": float(row["oldbalanceOrg"]), "newbalanceOrig": float(row["newbalanceOrig"]),
            "oldbalanceDest": float(row["oldbalanceDest"]), "newbalanceDest": float(row["newbalanceDest"]),
        })
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "demo_cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")


def train(max_train_rows: int = 750_000, review_budget: float = 0.01) -> dict:
    if not (0 < review_budget < 1):
        raise ValueError("review_budget must be between 0 and 1")
    data = load_public_dataset()
    train_all, validation, test, time_metadata = chronological_splits(data)
    train = sample_training_rows(train_all, max_train_rows, seed=42)
    estimator = make_estimator()
    estimator.fit(engineer_features(train), train[LABEL].to_numpy())

    validation_raw = estimator.predict_proba(engineer_features(validation))[:, 1]
    validation_logit = np.log(np.clip(validation_raw, 1e-6, 1 - 1e-6) / np.clip(1 - validation_raw, 1e-6, 1)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=500)
    calibrator.fit(validation_logit, validation[LABEL].to_numpy())
    validation_scores = calibrated_probability(estimator, calibrator, validation)
    threshold = float(np.quantile(validation_scores, 1 - review_budget, method="higher"))

    test_scores = calibrated_probability(estimator, calibrator, test)
    test_y = test[LABEL].to_numpy()
    baseline = test["isFlaggedFraud"].fillna(0).to_numpy(dtype=int)
    evaluation = metrics(test_y, test_scores, threshold, baseline, review_budget)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    bundle_metadata = {
        "modelVersion": "paysim-hgb-platt-v1", "datasetId": DATASET_ID,
        "datasetRevision": DATASET_REVISION, "datasetLicense": "CC-BY-4.0",
        "featureColumns": CATEGORICAL_FEATURES + NUMERIC_FEATURES,
        "excludedColumns": ["isFraud", "isFlaggedFraud", "BankID", "nameOrig", "nameDest"],
        "split": time_metadata, "trainRowsAvailable": int(len(train_all)),
        "trainRowsUsed": int(len(train)), "validationRows": int(len(validation)),
        "testRows": int(len(test)), "reviewBudgetRate": review_budget,
        "reviewThreshold": threshold,
    }
    import joblib
    joblib.dump({"estimator": estimator, "calibrator": calibrator, "review_threshold": threshold,
                 "metadata": bundle_metadata}, ARTIFACTS / "model_bundle.joblib", compress=3)
    report = {
        "evaluationType": "synthetic_workflow_demo",
        "interpretation": "Pipeline and queue smoke evidence only; not a real-world fraud-performance estimate.",
        "model": bundle_metadata,
        "testMetrics": evaluation,
    }
    (REPORTS / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    create_demo_cases(test, test_scores)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-train-rows", type=int, default=750_000)
    parser.add_argument("--review-budget", type=float, default=0.01, help="Fraction of transactions routed to the review queue")
    args = parser.parse_args()
    report = train(args.max_train_rows, args.review_budget)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
