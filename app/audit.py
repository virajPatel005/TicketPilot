"""Append-only SQLite audit log with a SHA-256 hash chain.

Every event is a NEW row chained to the previous one (prev_hash -> row_hash),
so any tampering with a past row breaks verification. No UPDATE/DELETE
code paths exist here. Never stores API keys.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import load_settings

GENESIS = "GENESIS"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    input_json TEXT NOT NULL,
    ai_output_json TEXT NOT NULL,
    confidence REAL,
    retrieved_doc_ids TEXT NOT NULL DEFAULT '[]',
    provider TEXT,
    key_label TEXT,
    model TEXT,
    tokens INTEGER,
    latency_ms INTEGER,
    status TEXT NOT NULL,
    approver TEXT,
    decision_note TEXT,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL
)
"""


def _connect(db_path=None):
    path = Path(db_path or load_settings().audit_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    conn = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
    if created:
        # New audit DBs are owner-only so the tamper-evident trail cannot be
        # read or rewritten by other local users.
        try:
            os.chmod(str(path), 0o600)
        except OSError:
            pass
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(SCHEMA)
    return conn


def _canonical(row: dict) -> str:
    """Canonical JSON used for hashing (stable key order, no row_hash)."""
    payload = {k: row[k] for k in row if k not in ("row_hash", "id")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str)


def _hash(row: dict) -> str:
    return hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["input"] = json.loads(d.pop("input_json") or "{}")
    d["ai_output"] = json.loads(d.pop("ai_output_json") or "{}")
    d["retrieved_doc_ids"] = json.loads(d.pop("retrieved_doc_ids") or "[]")
    return d


def append_event(ticket_id, input_data, ai_output, confidence, doc_ids,
                 provider, key_label, model, tokens, latency_ms, status,
                 approver=None, decision_note=None, trace_id=None,
                 revises_audit_id=None, db_path=None) -> int:
    """Append one event row; returns the new row id. Never updates/deletes.

    The read-last + insert run in one BEGIN IMMEDIATE transaction so
    concurrent writers serialize on SQLite's write lock and the chain
    cannot fork.
    """
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        last = conn.execute(
            "SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        prev_hash = last["row_hash"] if last else GENESIS
        ai_output = dict(ai_output or {})
        if revises_audit_id is not None:
            ai_output["revision_of"] = revises_audit_id
        row = {
            "ticket_id": ticket_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_json": json.dumps(input_data or {}, default=str),
            "ai_output_json": json.dumps(ai_output, default=str),
            "confidence": confidence,
            "retrieved_doc_ids": json.dumps(list(doc_ids or [])),
            "provider": provider,
            "key_label": key_label,
            "model": model,
            "tokens": tokens,
            "latency_ms": latency_ms,
            "status": status,
            "approver": approver,
            "decision_note": decision_note,
            "prev_hash": prev_hash,
        }
        if trace_id is not None:
            row["ai_output_json"] = json.dumps(
                {**(ai_output or {}), "trace_id": trace_id}, default=str)
        row["row_hash"] = _hash(row)
        cur = conn.execute(
            """INSERT INTO audit_log (ticket_id, timestamp, input_json,
               ai_output_json, confidence, retrieved_doc_ids, provider,
               key_label, model, tokens, latency_ms, status, approver,
               decision_note, prev_hash, row_hash)
               VALUES (:ticket_id, :timestamp, :input_json, :ai_output_json,
               :confidence, :retrieved_doc_ids, :provider, :key_label,
               :model, :tokens, :latency_ms, :status, :approver,
               :decision_note, :prev_hash, :row_hash)""", row)
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_ticket_history(ticket_id, db_path=None):
    """All audit rows for one ticket, oldest first."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE ticket_id = ? ORDER BY id",
            (ticket_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_pending(db_path=None):
    """Tickets whose latest status is pending_approval (one entry each).

    Each entry includes the original request fields (subject,
    description, and department/channel/affected_system when present)
    lifted from the audit row's input_json, plus all existing fields.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM audit_log WHERE id IN (
                   SELECT MAX(id) FROM audit_log GROUP BY ticket_id)
               AND status = 'pending_approval' ORDER BY id""").fetchall()
        out = []
        for row in rows:
            d = _row_to_dict(row)
            inp = d["input"]
            d["subject"] = inp.get("subject", "")
            d["description"] = inp.get("description", "")
            d["department"] = inp.get("department")
            d["channel"] = inp.get("channel")
            d["affected_system"] = inp.get("affected_system")
            out.append(d)
        return out
    finally:
        conn.close()


def list_tickets(status=None, search=None, limit: int = 200, db_path=None):
    """One entry per ticket_id from its LATEST audit row, newest first.

    revision_count counts decision rows (approved/rejected) for the ticket.
    """
    conn = _connect(db_path)
    try:
        latest = conn.execute(
            """SELECT * FROM audit_log WHERE id IN (
                   SELECT MAX(id) FROM audit_log GROUP BY ticket_id)
               ORDER BY timestamp DESC LIMIT ?""", (limit,)).fetchall()
        entries = []
        for row in latest:
            d = _row_to_dict(row)
            first = conn.execute(
                "SELECT timestamp FROM audit_log WHERE ticket_id = ? "
                "ORDER BY id LIMIT 1", (d["ticket_id"],)).fetchone()
            revisions = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE ticket_id = ? "
                "AND status IN ('approved', 'rejected')",
                (d["ticket_id"],)).fetchone()[0]
            fix = d["ai_output"].get("suggested_fix", {})
            triage = d["ai_output"].get("triage", {})
            entries.append({
                "ticket_id": d["ticket_id"],
                "subject": d["input"].get("subject", ""),
                "category": triage.get("category", ""),
                "priority": triage.get("priority", ""),
                "team": triage.get("team", ""),
                "sensitivity": triage.get("sensitivity", ""),
                "confidence": d["confidence"],
                "status": d["status"],
                "approver": d["approver"],
                "decision_note": d["decision_note"],
                "suggested_fix": {"found": fix.get("found", False),
                                  "doc_ids": fix.get("doc_ids", [])},
                "provider": d["provider"], "key_label": d["key_label"],
                "first_seen": first["timestamp"] if first else d["timestamp"],
                "last_updated": d["timestamp"],
                "revision_count": revisions,
                "input": d["input"], "ai_output": d["ai_output"],
                "latest_id": d["id"],
            })
        if status:
            entries = [e for e in entries if e["status"] == status]
        if search:
            needle = search.lower()
            entries = [e for e in entries
                       if needle in e["ticket_id"].lower()
                       or needle in e["subject"].lower()]
        return entries[:limit]
    finally:
        conn.close()


def verify_chain(db_path=None):
    """Recompute every row_hash and prev_hash link.

    Returns {valid, checked, first_bad_id, reason} where reason is
    "prev_hash mismatch", "row_hash mismatch" or None.
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        prev_hash = GENESIS
        for row in rows:
            d = dict(row)
            stored_hash = d.pop("row_hash")
            if d["prev_hash"] != prev_hash:
                return {"valid": False, "checked": len(rows),
                        "first_bad_id": d["id"],
                        "reason": "prev_hash mismatch"}
            if _hash(d) != stored_hash:
                return {"valid": False, "checked": len(rows),
                        "first_bad_id": d["id"],
                        "reason": "row_hash mismatch"}
            prev_hash = stored_hash
        return {"valid": True, "checked": len(rows), "first_bad_id": None,
                "reason": None}
    finally:
        conn.close()
