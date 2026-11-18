"""Concurrency tests: parallel append_event must never fork the chain."""
import sqlite3
import threading

from app import audit


def _append(db, ticket_id):
    audit.append_event(
        ticket_id=ticket_id, input_data={"subject": "s", "description": "d"},
        ai_output={"triage": {}}, confidence=0.5, doc_ids=[],
        provider="groq", key_label="GROQ_API_KEY_1", model="m", tokens=1,
        latency_ms=1, status="auto_resolved", db_path=db)


def test_concurrent_appends_do_not_fork(tmp_path):
    db = str(tmp_path / "audit.db")
    threads = [threading.Thread(target=_append, args=(db, f"T{i}"))
               for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    result = audit.verify_chain(db_path=db)
    assert result["valid"] is True
    assert result["checked"] == 8
    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    assert count == 8


def test_forged_prev_hash_is_reported_with_reason(tmp_path):
    db = str(tmp_path / "audit.db")
    _append(db, "T1")
    _append(db, "T2")
    conn = sqlite3.connect(db)
    conn.execute("UPDATE audit_log SET prev_hash='forged' WHERE id=2")
    conn.commit()
    conn.close()
    result = audit.verify_chain(db_path=db)
    assert result["valid"] is False
    assert result["first_bad_id"] == 2
    assert result["reason"] == "prev_hash mismatch"
