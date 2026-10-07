from __future__ import annotations

import json
import os
from pathlib import Path

import requests

API = os.getenv("RISK_API_URL", "http://localhost:8000")
INPUT = Path(os.getenv("DEMO_CASES_PATH", "data/processed/demo_cases.json"))


def main() -> None:
    if not INPUT.exists():
        raise SystemExit("Demo cases are missing; run `python -m app.train` first.")
    cases = json.loads(INPUT.read_text(encoding="utf-8"))
    for start in range(0, len(cases), 250):
        batch = cases[start:start + 250]
        response = requests.post(f"{API}/score/batch", json=batch, timeout=180)
        response.raise_for_status()
        print(f"Loaded {min(start + len(batch), len(cases))}/{len(cases)} demo cases")


if __name__ == "__main__":
    main()
