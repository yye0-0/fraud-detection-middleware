from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.features import operational_reason_codes
from app.model_bundle import ModelBundle
from app.repository import CaseRepository

app = FastAPI(title="Fraud Risk Triage API", version="2.0.0")
repository = CaseRepository()
model_bundle: ModelBundle | None = None
METRICS_PATH = Path(os.getenv("METRICS_PATH", "reports/evaluation.json"))


class Transaction(BaseModel):
    transactionId: str = Field(min_length=1, max_length=100)
    accountId: str = Field(min_length=1, max_length=100)
    step: int = Field(ge=1, le=10000)
    type: str = Field(min_length=1, max_length=40)
    amount: float = Field(ge=0)
    oldbalanceOrg: float = Field(ge=0)
    newbalanceOrig: float = Field(ge=0)
    oldbalanceDest: float = Field(ge=0)
    newbalanceDest: float = Field(ge=0)
    currency: str = Field(default="XXX", max_length=3)
    additionalRuleSignals: list[str] = Field(default_factory=list, max_length=30)


class ReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)
    disposition: Literal["CONFIRMED_FRAUD", "FALSE_POSITIVE", "ESCALATED", "NO_ACTION"]
    notes: str = Field(default="", max_length=2000)


class ScoredCase(BaseModel):
    caseId: str
    transactionId: str
    decision: str
    fraudProbability: float
    reviewThreshold: float
    reviewThreshold: float
    modelVersion: str
    reasonCodes: list[str]
    createdAt: str


def get_model() -> ModelBundle:
    global model_bundle
    if model_bundle is None:
        try:
            model_bundle = ModelBundle()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return model_bundle


def score_transactions(transactions: list[Transaction], allow_existing: bool = False,
                       capacity_ranked: bool = False) -> list[dict]:
    if not transactions:
        return []
    model = get_model()
    inputs = [item.model_dump() for item in transactions]
    scores = model.predict(inputs)
    top_k_review = set()
    if capacity_ranked and scores:
        capacity = max(1, int(len(scores) * float(model.metadata.get("reviewBudgetRate", 0.01)) + 0.999999))
        top_k_review = set(sorted(range(len(scores)), key=lambda index: (scores[index], index), reverse=True)[:capacity])
    now = datetime.now(timezone.utc).isoformat()
    results = []
    for index, (item, probability) in enumerate(zip(transactions, scores, strict=True)):
        if allow_existing and repository.has_transaction(item.transactionId):
            continue
        reasons = list(dict.fromkeys(operational_reason_codes(item.model_dump()) + item.additionalRuleSignals))
        hard_rule = bool(item.additionalRuleSignals) or "HIGH_VALUE_TRANSFER_RULE" in reasons
        if capacity_ranked:
            # This route enforces the configured batch quota. Rules remain visible context,
            # but cannot overrun the analyst's capacity.
            needs_review = index in top_k_review
        else:
            # Single-event scoring uses the validation-period threshold. Monitor live rate
            # drift; use /score/batch when a hard review cap is required.
            needs_review = probability >= model.review_threshold or hard_rule
        record = {
            "caseId": str(uuid.uuid4()), "transactionId": item.transactionId,
            "accountId": item.accountId, "amount": item.amount, "type": item.type,
            "step": item.step, "fraudProbability": round(float(probability), 6),
            "reviewThreshold": model.review_threshold,
            "decision": "REVIEW" if needs_review else "APPROVE",
            "modelVersion": model.metadata["modelVersion"], "reasonCodes": reasons,
            "transaction": item.model_dump(), "createdAt": now,
        }
        try:
            repository.add_case(record)
        except Exception as exc:
            if "UNIQUE constraint failed: cases.transaction_id" in str(exc):
                raise HTTPException(status_code=409, detail=f"transactionId {item.transactionId} was already scored") from exc
            raise
        results.append(ScoredCase(**record).model_dump())
    return results


@app.get("/health")
def health() -> dict:
    try:
        model = get_model()
        return {"status": "ok", "modelVersion": model.metadata["modelVersion"]}
    except HTTPException:
        raise


@app.get("/about")
def about() -> dict:
    model = get_model()
    return {
        "use": "Risk-based transaction review prioritization",
        "dataset": model.metadata["datasetId"],
        "datasetRevision": model.metadata["datasetRevision"],
        "datasetLicense": model.metadata["datasetLicense"],
        "modelVersion": model.metadata["modelVersion"],
        "syntheticDataOnly": True,
        "notForRealCustomerDecisions": True,
    }


@app.post("/score", response_model=ScoredCase)
def score_one(transaction: Transaction) -> dict:
    return score_transactions([transaction])[0]


@app.post("/score/batch", response_model=list[ScoredCase])
def score_batch(transactions: list[Transaction]) -> list[dict]:
    if len(transactions) > 1000:
        raise HTTPException(status_code=413, detail="Batch limit is 1000 transactions")
    return score_transactions(transactions, allow_existing=True, capacity_ranked=True)


@app.get("/cases")
def list_cases(status: Literal["OPEN", "RESOLVED"] | None = "OPEN",
               limit: int = Query(default=100, ge=1, le=500),
               offset: int = Query(default=0, ge=0)) -> list[dict]:
    return repository.list_cases(status, limit, offset)


@app.post("/cases/{case_id}/review")
def review_case(case_id: str, review: ReviewRequest) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    result = repository.review(case_id, review.reviewer, review.disposition, review.notes, now)
    if result is None:
        status = repository.case_status(case_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Case was not found")
        raise HTTPException(status_code=409, detail="Case is not open for disposition")
    return result


@app.get("/ops/summary")
def ops_summary() -> dict:
    return repository.summary()


@app.get("/reviews/export")
def export_reviews() -> Response:
    records = repository.export_reviews()
    buffer = io.StringIO()
    columns = ["case_id", "transaction_id", "risk_score", "disposition", "reviewer", "notes", "created_at", "reviewed_at"]
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(records)
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=review-feedback.csv"})


@app.get("/model/metrics")
def model_metrics() -> dict:
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Training evaluation report not found")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
