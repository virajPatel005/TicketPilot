"""Audit tests: hash chain, append-only, approval flow, no Langfuse keys."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import audit, main as main_module
from app.tracing import enabled as langfuse_enabled


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "audit.db")
    real_connect = audit._connect
    monkeypatch.setattr(main_module.audit, "_connect",
                        lambda db_path=None: real_connect(path))
    return path


def append(db, ticket_id="T1", status="pending_approval", **kw):
    return audit.append_event(
        ticket_id=ticket_id, input_data={"subject": "s", "description": "d"},
        ai_output={"triage": {}}, confidence=0.5, doc_ids=["kb-001"],
        provider="groq", key_label="GROQ_API_KEY_1", model="m", tokens=10,
        latency_ms=5, status=status, db_path=db, **kw)


def test_valid_chain_verifies(db):
    append(db, "T1")
    append(db, "T2", status="auto_resolved")
    result = audit.verify_chain(db_path=db)
    assert result == {"valid": True, "checked": 2, "first_bad_id": None,
                      "reason": None}


def test_tampering_is_detected_with_first_bad_id(db):
    append(db, "T1")
    append(db, "T2")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE audit_log SET status='approved' WHERE id=1")
    conn.commit()
    conn.close()
    result = audit.verify_chain(db_path=db)
    assert result["valid"] is False
    assert result["first_bad_id"] == 1


def test_append_only_no_update_or_delete_code():
    import pathlib
    source = pathlib.Path("app/audit.py").read_text()
    assert "UPDATE audit_log" not in source
    assert "DELETE FROM audit_log" not in source
    assert "DROP TABLE" not in source


def test_decision_is_a_new_chained_row(db):
    append(db, "T1")
    append(db, "T1", status="approved", approver="mgr", decision_note="ok")
    history = audit.get_ticket_history("T1", db_path=db)
    assert [h["status"] for h in history] == ["pending_approval", "approved"]
    assert history[1]["prev_hash"] == history[0]["row_hash"]
    assert history[1]["approver"] == "mgr"
    assert audit.verify_chain(db_path=db)["valid"] is True
    assert audit.list_pending(db_path=db) == []


def fake_triage(monkeypatch, payload, fix=None):
    out_meta = {"provider": "groq", "key_label": "GROQ_API_KEY_1",
                "model": "m", "prompt_tokens": 1, "completion_tokens": 1,
                "latency_ms": 1, "status": "ok"}

    def fake_triage_ticket(ticket, settings=None, key_manager=None):
        from app.schemas import TriageOut
        return TriageOut(**payload), out_meta

    monkeypatch.setattr(main_module, "triage_ticket", fake_triage_ticket)
    monkeypatch.setattr(
        main_module, "suggest_fix",
        lambda ticket, out, settings=None, key_manager=None:
        fix or {"answer": "steps", "doc_ids": ["kb-014"], "found": True})


ADMIN = {"category": "Access/Login", "sub_category": "admin access",
         "priority": "High", "team": "Service Desk",
         "sensitivity": "trial-data-related", "confidence": 0.97,
         "needs_human_approval": True, "reason": "admin"}
NORMAL = {"category": "Network/VPN", "sub_category": "VPN",
          "priority": "Medium", "team": "Network Team",
          "sensitivity": "normal", "confidence": 0.99,
          "needs_human_approval": False, "reason": "vpn"}


def test_admin_ticket_pending_then_approved(db, monkeypatch):
    fake_triage(monkeypatch, ADMIN)
    client = TestClient(main_module.app)
    resp = client.post("/triage", json={
        "ticket_id": "ADM-1", "subject": "Admin",
        "description": "admin access to trial database"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_approval"
    pending = client.get("/approvals/pending").json()["pending"]
    assert [p["ticket_id"] for p in pending] == ["ADM-1"]

    decision = client.post("/approvals/ADM-1/decision", json={
        "approver": "manager.test", "decision": "approve", "note": "ok"})
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    assert client.get("/approvals/pending").json()["pending"] == []
    history = client.get("/audit/ADM-1").json()["history"]
    assert [h["status"] for h in history] == ["pending_approval", "approved"]

    # Approving again (no longer pending) must fail.
    again = client.post("/approvals/ADM-1/decision", json={
        "approver": "manager.test", "decision": "approve"})
    assert again.status_code == 409


def test_normal_ticket_auto_resolved(db, monkeypatch):
    fake_triage(monkeypatch, NORMAL,
                fix={"answer": "steps", "doc_ids": ["kb-004"],
                     "found": True})
    client = TestClient(main_module.app)
    resp = client.post("/triage", json={
        "ticket_id": "VPN-1", "subject": "VPN", "description": "vpn down"})
    assert resp.json()["status"] == "auto_resolved"
    assert client.get("/approvals/pending").json()["pending"] == []


def test_empty_approver_rejected(db, monkeypatch):
    fake_triage(monkeypatch, ADMIN)
    client = TestClient(main_module.app)
    client.post("/triage", json={
        "ticket_id": "ADM-2", "subject": "Admin", "description": "admin"})
    resp = client.post("/approvals/ADM-2/decision", json={
        "approver": "  ", "decision": "approve"})
    assert resp.status_code == 422


def test_invalid_decision_rejected(db, monkeypatch):
    fake_triage(monkeypatch, ADMIN)
    client = TestClient(main_module.app)
    client.post("/triage", json={
        "ticket_id": "ADM-3", "subject": "Admin", "description": "admin"})
    resp = client.post("/approvals/ADM-3/decision", json={
        "approver": "mgr", "decision": "maybe"})
    assert resp.status_code == 422


def test_app_works_without_langfuse_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    assert langfuse_enabled() is False
    assert TestClient(main_module.app).get("/health").status_code == 200


def test_triage_survives_langfuse_client_errors(db, monkeypatch):
    from app import tracing
    fake_triage(monkeypatch, NORMAL,
                fix={"answer": "steps", "doc_ids": ["kb-004"],
                     "found": True})

    def boom():
        raise RuntimeError("langfuse down")

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setattr(tracing, "_get_client", boom)
    monkeypatch.setattr(tracing, "_client", None)
    resp = TestClient(main_module.app).post("/triage", json={
        "ticket_id": "VPN-LF", "subject": "VPN", "description": "vpn down"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "auto_resolved"


def test_list_pending_includes_original_request(db):
    append(db, "REQ-1", "pending_approval")
    pending = audit.list_pending(db_path=db)
    assert len(pending) == 1
    entry = pending[0]
    assert entry["subject"] == "s"
    assert entry["description"] == "d"
    assert entry["department"] is None
    assert entry["channel"] is None
    assert entry["affected_system"] is None


def test_verify_endpoint(db):
    append(db, "T9")
    assert TestClient(main_module.app).get("/audit/verify").json() == {
        "valid": True, "checked": 1, "first_bad_id": None, "reason": None}
