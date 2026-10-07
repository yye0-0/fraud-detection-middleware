from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.features import engineer_features

DEFAULT_MODEL_PATH = Path(os.getenv("MODEL_PATH", "artifacts/model_bundle.joblib"))


class ModelBundle:
    def __init__(self, path: Path = DEFAULT_MODEL_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Trained model not found at {path}. Run `python -m app.train` first.")
        self.path = path
        self.bundle = joblib.load(path)

    @property
    def metadata(self) -> dict:
        return self.bundle["metadata"]

    @property
    def review_threshold(self) -> float:
        return float(self.bundle["review_threshold"])

    def predict(self, transactions: list[dict]) -> list[float]:
        raw = pd.DataFrame(transactions)
        features = engineer_features(raw)
        base_probability = self.bundle["estimator"].predict_proba(features)[:, 1]
        logits = np.log(np.clip(base_probability, 1e-6, 1 - 1e-6) / np.clip(1 - base_probability, 1e-6, 1))
        calibrated = self.bundle["calibrator"].predict_proba(logits.reshape(-1, 1))[:, 1]
        return calibrated.astype(float).tolist()

    def write_metadata(self, output_path: Path) -> None:
        output_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")
