"""Dashboard + revision tests (tmp DB, mocked LLM via TestClient)."""
import pytest
from fastapi.testclient import TestClient

from app import audit, main as main_module


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "audit.db")
    real_connect = audit._connect
    monkeypatch.setattr(main_module.audit, "_connect",
                        lambda db_path=None: real_connect(path))
    return path


def append(db, ticket_id, status, subject="s", **kw):
    return audit.append_event(
        ticket_id=ticket_id,
        input_data={"subject": subject, "description": "d"},
        ai_output={"triage": {"category": "Software", "priority": "Low",
                              "team": "IT Support", "sensitivity": "normal"},
                   "suggested_fix": {"found": True, "doc_ids": ["kb-006"]}},
        confidence=0.9, doc_ids=["kb-006"], provider="groq",
        key_label="GROQ_API_KEY_1", model="m", tokens=10, latency_ms=5,
        status=status, db_path=db, **kw)


def fake_triage(monkeypatch, payload):
    meta = {"provider": "groq", "key_label": "GROQ_API_KEY_1",
            "model": "m", "prompt_tokens": 1, "completion_tokens": 1,
            "latency_ms": 1, "status": "ok"}

    def fake(ticket, settings=None, key_manager=None):
        from app.schemas import TriageOut
        return TriageOut(**payload), meta

    monkeypatch.setattr(main_module, "triage_ticket", fake)
    monkeypatch.setattr(
        main_module, "suggest_fix",
        lambda ticket, out, settings=None, key_manager=None:
        {"answer": "steps", "doc_ids": ["kb-014"], "found": True})


ADMIN = {"category": "Access/Login", "sub_category": "admin access",
         "priority": "High", "team": "Security Team",
         "sensitivity": "trial-data-related", "confidence": 0.98,
         "needs_human_approval": True, "reason": "admin"}


def test_list_tickets_latest_status_and_revision_count(db):
    append(db, "T1", "pending_approval", subject="vpn")
    append(db, "T1", "approved", approver="mgr", decision_note="ok")
    append(db, "T2", "auto_resolved", subject="printer")
    tickets = audit.list_tickets(db_path=db)
    assert [t["ticket_id"] for t in tickets] == ["T2", "T1"]  # newest first
    t1 = [t for t in tickets if t["ticket_id"] == "T1"][0]
    assert t1["status"] == "approved"
    assert t1["revision_count"] == 1
    assert t1["first_seen"] <= t1["last_updated"]
    assert t1["suggested_fix"] == {"found": True, "doc_ids": ["kb-006"]}
    assert audit.list_tickets(status="approved", db_path=db)[0][
        "ticket_id"] == "T1"
    assert audit.list_tickets(search="print", db_path=db)[0][
        "ticket_id"] == "T2"


def test_revise_approved_to_rejected_via_api(db, monkeypatch):
    fake_triage(monkeypatch, ADMIN)
    client = TestClient(main_module.app)
    client.post("/triage", json={"ticket_id": "ADM-1", "subject": "Admin",
                                 "description": "admin access"})
    r1 = client.post("/approvals/ADM-1/decision",
                     json={"approver": "team.lead", "decision": "approve"})
    assert r1.json()["status"] == "approved"
    # Revision without a note -> 422
    r2 = client.post("/approvals/ADM-1/decision",
                     json={"approver": "team.lead", "decision": "reject"})
    assert r2.status_code == 422
    # Same decision -> 409
    r3 = client.post("/approvals/ADM-1/decision",
                     json={"approver": "team.lead", "decision": "approve",
                           "note": "again"})
    assert r3.status_code == 409
    # Valid revision -> 200, new status, revision recorded
    r4 = client.post("/approvals/ADM-1/decision",
                     json={"approver": "team.lead", "decision": "reject",
                           "note": "wrong scope"})
    assert r4.status_code == 200
    assert r4.json()["status"] == "rejected"
    history = client.get("/audit/ADM-1").json()["history"]
    assert [h["status"] for h in history] == [
        "pending_approval", "approved", "rejected"]
    assert history[-1]["ai_output"]["revision_of"] == history[1]["id"]
    tickets = client.get("/tickets").json()["tickets"]
    entry = [t for t in tickets if t["ticket_id"] == "ADM-1"][0]
    assert entry["status"] == "rejected"
    assert entry["revision_count"] == 2
    assert audit.verify_chain(db_path=db)["valid"] is True


def test_summary_counts(db, monkeypatch):
    fake_triage(monkeypatch, ADMIN)
    client = TestClient(main_module.app)
    client.post("/triage", json={"ticket_id": "S-1", "subject": "Admin",
                                 "description": "admin"})
    summary = client.get("/tickets/summary").json()
    assert summary == {"total": 1, "auto_resolved": 0,
                       "pending_approval": 1, "approved": 0, "rejected": 0}
    client.post("/approvals/S-1/decision",
                json={"approver": "mgr", "decision": "approve"})
    summary = client.get("/tickets/summary").json()
    assert summary["approved"] == 1 and summary["pending_approval"] == 0


def test_auto_resolved_can_be_rejected_with_note(db, monkeypatch):
    payload = dict(ADMIN, needs_human_approval=False, sensitivity="normal",
                   category="Network/VPN", team="Network Team")
    fake_triage(monkeypatch, payload)
    client = TestClient(main_module.app)
    client.post("/triage", json={"ticket_id": "V-1", "subject": "VPN",
                                 "description": "vpn down"})
    r = client.post("/approvals/V-1/decision",
                    json={"approver": "mgr", "decision": "reject",
                          "note": "actually wrong"})
    assert r.status_code == 200
    assert [h["status"] for h in
            client.get("/audit/V-1").json()["history"]] == [
        "auto_resolved", "rejected"]
