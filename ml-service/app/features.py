"""PaySim feature contract shared by training and online inference."""
from __future__ import annotations

import numpy as np
import pandas as pd

CATEGORICAL_FEATURES = ["type"]
NUMERIC_FEATURES = [
    "step", "log_amount", "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest",
    "newbalanceDest", "origin_balance_error", "destination_balance_error",
    "amount_to_origin_balance", "origin_drained", "destination_was_empty",
]
MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
RAW_FIELDS = [
    "step", "type", "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest",
]


def engineer_features(transactions: pd.DataFrame) -> pd.DataFrame:
    missing = set(RAW_FIELDS) - set(transactions.columns)
    if missing:
        raise ValueError(f"Missing PaySim fields: {', '.join(sorted(missing))}")
    frame = transactions[RAW_FIELDS].copy()
    for column in RAW_FIELDS:
        if column != "type":
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    frame["type"] = frame["type"].fillna("UNKNOWN").astype(str).str.upper()
    frame["log_amount"] = np.log1p(frame["amount"].clip(lower=0))
    frame["origin_balance_error"] = (
        frame["oldbalanceOrg"] - frame["amount"] - frame["newbalanceOrig"]
    )
    frame["destination_balance_error"] = (
        frame["newbalanceDest"] - frame["oldbalanceDest"] - frame["amount"]
    )
    frame["amount_to_origin_balance"] = frame["amount"] / (frame["oldbalanceOrg"] + 1.0)
    frame["origin_drained"] = (
        (frame["oldbalanceOrg"] > 0) & (frame["newbalanceOrig"] <= 1.0)
    ).astype("int8")
    frame["destination_was_empty"] = (frame["oldbalanceDest"] <= 1.0).astype("int8")
    return frame[MODEL_FEATURES]


def operational_reason_codes(transaction: dict) -> list[str]:
    """Human-readable rule signals; these supplement, and do not replace, model evidence."""
    amount = float(transaction.get("amount", 0) or 0)
    old_origin = float(transaction.get("oldbalanceOrg", 0) or 0)
    new_origin = float(transaction.get("newbalanceOrig", 0) or 0)
    old_dest = float(transaction.get("oldbalanceDest", 0) or 0)
    new_dest = float(transaction.get("newbalanceDest", 0) or 0)
    tx_type = str(transaction.get("type", "")).upper()
    reasons: list[str] = []
    if tx_type == "TRANSFER" and amount > 200_000:
        reasons.append("HIGH_VALUE_TRANSFER_RULE")
    if amount >= 5_000:
        reasons.append("HIGH_AMOUNT")
    if old_origin > 0 and abs(old_origin - amount - new_origin) > max(1.0, old_origin * 0.05):
        reasons.append("ORIGIN_BALANCE_MOVEMENT_MISMATCH")
    if old_dest > 0 and abs(new_dest - old_dest - amount) > max(1.0, old_dest * 0.05):
        reasons.append("DESTINATION_BALANCE_MOVEMENT_MISMATCH")
    if tx_type in {"TRANSFER", "CASH_OUT"} and new_origin <= 1 and old_origin > amount:
        reasons.append("ORIGIN_ACCOUNT_DRAINED")
    return reasons
