import pandas as pd

from app.features import MODEL_FEATURES, engineer_features, operational_reason_codes


def test_feature_contract_excludes_labels_and_identifiers():
    raw = pd.DataFrame([{
        "step": 10, "type": "TRANSFER", "amount": 8200,
        "oldbalanceOrg": 9000, "newbalanceOrig": 800,
        "oldbalanceDest": 0, "newbalanceDest": 0,
    }])
    features = engineer_features(raw)
    assert list(features.columns) == MODEL_FEATURES
    assert "isFraud" not in features
    assert "isFlaggedFraud" not in features


def test_explanation_produces_business_readable_signals():
    reasons = operational_reason_codes({
        "type": "TRANSFER", "amount": 8999, "oldbalanceOrg": 9000,
        "newbalanceOrig": 0, "oldbalanceDest": 0, "newbalanceDest": 0,
    })
    assert "HIGH_AMOUNT" in reasons
    assert "ORIGIN_ACCOUNT_DRAINED" in reasons
