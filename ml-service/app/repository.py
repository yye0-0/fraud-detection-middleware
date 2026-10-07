from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(os.getenv("DATABASE_PATH", "data/triage.sqlite"))


class CaseRepository:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL UNIQUE,
                account_id TEXT NOT NULL,
                amount REAL NOT NULL,
                tx_type TEXT NOT NULL,
                step INTEGER NOT NULL,
                risk_score REAL NOT NULL,
                decision TEXT NOT NULL,
                model_version TEXT NOT NULL,
                reason_codes TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                disposition TEXT,
                reviewer TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS review_audit (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                action TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                disposition TEXT NOT NULL,
                notes TEXT,
                event_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id)
            )""")

    def add_case(self, case: dict) -> None:
        with self.connection() as conn:
            conn.execute("""INSERT INTO cases (
                case_id, transaction_id, account_id, amount, tx_type, step, risk_score,
                decision, model_version, reason_codes, payload, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                case["caseId"], case["transactionId"], case["accountId"], case["amount"],
                case["type"], case["step"], case["fraudProbability"], case["decision"],
                case["modelVersion"], json.dumps(case["reasonCodes"]),
                json.dumps(case["transaction"], separators=(",", ":")),
                "OPEN" if case["decision"] == "REVIEW" else "CLEARED", case["createdAt"],
            ))

    def list_cases(self, status: str | None, limit: int, offset: int) -> list[dict]:
        with self.connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM cases WHERE status=? ORDER BY risk_score DESC, created_at ASC LIMIT ? OFFSET ?",
                                    (status, limit, offset)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM cases ORDER BY risk_score DESC, created_at ASC LIMIT ? OFFSET ?",
                                    (limit, offset)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["reason_codes"] = json.loads(item.pop("reason_codes"))
            item["transaction"] = json.loads(item.pop("payload"))
            output.append(item)
        return output

    def case_status(self, case_id: str) -> str | None:
        with self.connection() as conn:
            row = conn.execute("SELECT status FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return row["status"] if row else None

    def has_transaction(self, transaction_id: str) -> bool:
        with self.connection() as conn:
            row = conn.execute("SELECT 1 FROM cases WHERE transaction_id=?", (transaction_id,)).fetchone()
        return row is not None

    def review(self, case_id: str, reviewer: str, disposition: str, notes: str, reviewed_at: str) -> dict | None:
        with self.connection() as conn:
            result = conn.execute("""UPDATE cases SET status='RESOLVED', disposition=?, reviewer=?, notes=?, reviewed_at=?
                WHERE case_id=? AND status='OPEN'""", (disposition, reviewer, notes, reviewed_at, case_id))
            if result.rowcount != 1:
                return None
            conn.execute("INSERT INTO review_audit(case_id, action, reviewer, disposition, notes, event_at) VALUES (?, 'RESOLVE', ?, ?, ?, ?)",
                         (case_id, reviewer, disposition, notes, reviewed_at))
            row = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        item = dict(row)
        item["reason_codes"] = json.loads(item.pop("reason_codes"))
        item["transaction"] = json.loads(item.pop("payload"))
        return item

    def summary(self) -> dict:
        with self.connection() as conn:
            counts = {row["status"]: row["n"] for row in conn.execute("SELECT status, COUNT(*) n FROM cases GROUP BY status")}
            dispositions = {row["disposition"]: row["n"] for row in conn.execute("SELECT disposition, COUNT(*) n FROM cases WHERE disposition IS NOT NULL GROUP BY disposition")}
            timing = conn.execute("SELECT AVG((julianday(reviewed_at)-julianday(created_at))*86400.0) avg_seconds FROM cases WHERE reviewed_at IS NOT NULL").fetchone()
            events = conn.execute("SELECT COUNT(*) n FROM review_audit").fetchone()["n"]
        return {"cases": counts, "dispositions": dispositions, "averageReviewSeconds": round(timing["avg_seconds"] or 0, 2), "auditEvents": events}

    def export_reviews(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute("SELECT case_id, transaction_id, risk_score, disposition, reviewer, notes, created_at, reviewed_at FROM cases WHERE disposition IS NOT NULL ORDER BY reviewed_at").fetchall()
        return [dict(row) for row in rows]
