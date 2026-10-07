import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("RISK_API_URL", "http://localhost:8000")
st.set_page_config(page_title="Fraud Review Desk", page_icon="🔎", layout="wide")
st.title("Fraud Review Desk")
st.caption("Risk-ranked work queue · synthetic PaySim demo · decisions remain with the analyst")


def api_get(path, **kwargs):
    response = requests.get(f"{API}{path}", timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def api_post(path, payload):
    response = requests.post(f"{API}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


try:
    summary = api_get("/ops/summary")
    metrics = api_get("/model/metrics")
except requests.RequestException as exc:
    st.error(f"Risk API is unavailable: {exc}")
    st.stop()

opened = summary["cases"].get("OPEN", 0)
resolved = summary["cases"].get("RESOLVED", 0)
evaluation = metrics["testMetrics"]
columns = st.columns(4)
columns[0].metric("Open cases", opened)
columns[1].metric("Reviewed", resolved)
columns[2].metric("Avg. handling time", f"{summary['averageReviewSeconds']:.1f}s")
columns[3].metric("Reviews / 10k at fixed cap", f"{evaluation['reviewsPer10000AtCapacity']:,}")

with st.expander("Offline model evidence (chronological holdout)", expanded=False):
    st.write(f"Model: `{metrics['model']['modelVersion']}` · dataset revision: `{metrics['model']['datasetRevision']}`")
    st.warning("These metrics are from synthetic PaySim data and are shown only to inspect the demo pipeline. Do not use them as evidence of real-world model quality. The batch top-K row enforces the fixed review capacity; a single-event threshold can drift as the fraud rate changes.")
    st.json(evaluation)

st.subheader("Priority queue")
queue = api_get("/cases", params={"status": "OPEN", "limit": 200})
if not queue:
    st.info("No open cases. Load the demo queue with `python -m scripts.seed_demo_queue` or submit a transaction below.")
else:
    table = pd.DataFrame([{
        "Case": x["case_id"], "Transaction": x["transaction_id"],
        "Score": x["risk_score"], "Decision": x["decision"],
        "Type": x["tx_type"], "Amount": x["amount"], "Step": x["step"],
        "Signals": ", ".join(x["reason_codes"]),
    } for x in queue])
    st.dataframe(table, use_container_width=True, hide_index=True)
    by_id = {x["case_id"]: x for x in queue}
    selected_id = st.selectbox("Open a case", list(by_id), format_func=lambda k: f"{k[:8]} · score {by_id[k]['risk_score']:.3f} · {by_id[k]['tx_type']} {by_id[k]['amount']:,.2f}")
    case = by_id[selected_id]
    with st.container(border=True):
        st.markdown(f"**Transaction:** `{case['transaction_id']}`  ·  **Account:** `{case['account_id']}`")
        st.markdown(f"**Model score:** {case['risk_score']:.4f}  ·  **Decision:** {case['decision']}")
        st.markdown("**Reason codes:** " + (", ".join(case["reason_codes"]) or "none"))
        st.json(case["transaction"])
    with st.form("review_form"):
        reviewer = st.text_input("Reviewer ID", value="analyst-1")
        disposition = st.selectbox("Disposition", ["CONFIRMED_FRAUD", "FALSE_POSITIVE", "ESCALATED", "NO_ACTION"])
        notes = st.text_area("Review note", max_chars=2000)
        submitted = st.form_submit_button("Save disposition")
        if submitted:
            try:
                api_post(f"/cases/{selected_id}/review", {"reviewer": reviewer, "disposition": disposition, "notes": notes})
                st.success("Disposition saved to the audit trail.")
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Could not save review: {exc}")

st.divider()
with st.expander("Score a new transaction", expanded=False):
    with st.form("score_form"):
        left, right = st.columns(2)
        txid = left.text_input("Transaction ID")
        account = right.text_input("Account ID", value="demo-account")
        step = left.number_input("Simulation hour", min_value=1, max_value=10000, value=700)
        tx_type = right.selectbox("Type", ["TRANSFER", "CASH_OUT", "PAYMENT", "DEBIT", "CASH_IN"])
        amount = left.number_input("Amount", min_value=0.0, value=8200.0)
        old_origin = right.number_input("Origin balance before", min_value=0.0, value=9000.0)
        new_origin = left.number_input("Origin balance after", min_value=0.0, value=800.0)
        old_dest = right.number_input("Destination balance before", min_value=0.0, value=0.0)
        new_dest = left.number_input("Destination balance after", min_value=0.0, value=0.0)
        score_button = st.form_submit_button("Score transaction")
        if score_button:
            try:
                result = api_post("/score", {
                    "transactionId": txid, "accountId": account, "step": int(step), "type": tx_type,
                    "amount": amount, "oldbalanceOrg": old_origin, "newbalanceOrig": new_origin,
                    "oldbalanceDest": old_dest, "newbalanceDest": new_dest,
                })
                st.success(f"{result['decision']} · risk score {result['fraudProbability']:.4f} · case {result['caseId']}")
            except requests.RequestException as exc:
                st.error(f"Scoring failed: {exc}")

st.caption("Review decisions are append-audited. Export the feedback ledger from `/reviews/export` for model monitoring and labeling workflows.")
