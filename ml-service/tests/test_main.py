from fastapi import HTTPException
from pydantic import ValidationError

import app.main as main
from app.repository import CaseRepository



class FakeModel:
    review_threshold = 0.65
    metadata = {"modelVersion": "test-model-v1", "datasetId": "test"}

    def predict(self, transactions):
        return [0.82 for _ in transactions]


def transaction(transaction_id="tx-1"):
    return {
        "transactionId": transaction_id, "accountId": "acct-1", "step": 700,
        "type": "TRANSFER", "amount": 8200, "oldbalanceOrg": 9000,
        "newbalanceOrig": 800, "oldbalanceDest": 0, "newbalanceDest": 0,
    }


def setup_function():
    import tempfile
    main.repository = CaseRepository(__import__("pathlib").Path(tempfile.mkdtemp()) / "test.sqlite")
    main.model_bundle = FakeModel()


def test_score_then_review_is_persisted_and_audited():
    body = main.score_one(main.Transaction(**transaction()))
    assert body["decision"] == "REVIEW"
    assert body["modelVersion"] == "test-model-v1"

    queue = main.list_cases("OPEN", 100, 0)
    assert len(queue) == 1
    assert "isFraud" not in queue[0]["transaction"]

    reviewed = main.review_case(body["caseId"], main.ReviewRequest(
        reviewer="analyst-1", disposition="FALSE_POSITIVE", notes="Checked source details"))
    assert reviewed["status"] == "RESOLVED"
    assert main.ops_summary()["auditEvents"] == 1


def test_duplicate_transaction_is_rejected():
    main.score_one(main.Transaction(**transaction()))
    try:
        main.score_one(main.Transaction(**transaction()))
        assert False, "duplicate transaction should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 409


def test_batch_review_selection_respects_configured_capacity():
    transactions = []
    for index in range(100):
        item = transaction(f"batch-{index}")
        item["amount"] = 100
        item["oldbalanceOrg"] = 200
        item["newbalanceOrig"] = 100
        transactions.append(main.Transaction(**item))
    results = main.score_batch(transactions)
    assert len(results) == 100
    assert sum(item["decision"] == "REVIEW" for item in results) == 1
    assert len(main.list_cases("OPEN", 100, 0)) == 1


def test_review_cannot_be_submitted_twice():
    case = main.score_one(main.Transaction(**transaction()))
    payload = main.ReviewRequest(reviewer="analyst-1", disposition="CONFIRMED_FRAUD", notes="matched")
    assert main.review_case(case["caseId"], payload)["status"] == "RESOLVED"
    try:
        main.review_case(case["caseId"], payload)
        assert False, "resolved case should be immutable"
    except HTTPException as exc:
        assert exc.status_code == 409


def test_negative_amount_is_rejected():
    bad = transaction("tx-bad")
    bad["amount"] = -1
    try:
        main.Transaction(**bad)
        assert False, "negative amount should fail validation"
    except ValidationError:
        pass
