import numpy as np
import pandas as pd

from app.train import chronological_splits, sample_training_rows
from app.real_data_benchmark import capacity_metrics, temporal_split


def test_chronological_split_keeps_time_order():
    data = pd.DataFrame({
        "step": list(range(1, 101)),
        "isFraud": [int(i % 5 == 0) for i in range(1, 101)],
    })
    train, validation, test, cuts = chronological_splits(data)
    assert train.step.max() < validation.step.min()
    assert validation.step.max() < test.step.min()
    assert cuts["testStepMin"] == int(test.step.min())


def test_training_sample_preserves_positive_rows():
    data = pd.DataFrame({"step": range(100), "isFraud": [1] * 10 + [0] * 90})
    selected = sample_training_rows(data, max_rows=30, seed=7)
    assert len(selected) == 30
    assert int(selected.isFraud.sum()) == 10


def test_real_data_split_is_temporal_and_keeps_three_windows():
    data = pd.DataFrame({
        "Time": range(100),
        "Class": [int(i % 3 == 0) for i in range(100)],
    })
    train, validation, test = temporal_split(data)
    assert train.Time.max() < validation.Time.min()
    assert validation.Time.max() < test.Time.min()
    assert len(train) == 60 and len(validation) == 20 and len(test) == 20


def test_capacity_metric_uses_same_review_count_for_benchmark():
    y = np.array([0, 1, 0, 1, 0, 0, 0, 0, 1, 0])
    amount = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    score = np.array([0, 9, 1, 8, 2, 3, 4, 5, 6, 7], dtype=float)
    report = capacity_metrics(y, score, amount, 0.2, amount)
    assert report["model"]["reviewCount"] == report["amountDescendingBaseline"]["reviewCount"] == 2
    assert report["model"]["fraudCaught"] == 2
    assert report["amountDescendingBaseline"]["fraudCaught"] == 0
