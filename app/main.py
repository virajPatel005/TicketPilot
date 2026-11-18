"""FastAPI app: triage, approvals, audit verification, key status.

Structured JSON logging with a per-request trace_id. Every triage writes
one hash-chained audit row (Stage 4 replaces data/llm_calls.jsonl).
"""
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from . import audit, tracing
from .config import load_key_pool, load_settings
from .key_manager import KeyManager
from .rag import suggest_fix
from .schemas import DecisionIn, TicketIn, TriageResponse
from .triage import triage_ticket


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "extra", {}) or {})
        return json.dumps(payload)


def _setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


_setup_logging()
logger = logging.getLogger("ticketpilot")

settings = load_settings()
key_manager = KeyManager(
    load_key_pool(enable_openrouter=settings.enable_openrouter),
    cooldown_sec=settings.key_cooldown_sec,
    enable_openrouter=settings.enable_openrouter)

# Optional shared bearer token for the API. When APP_API_TOKEN is set, the
# mutating/read endpoints require the X-API-Token header; when unset the app
# behaves as before (local demo, no auth).
API_TOKEN = (os.getenv("APP_API_TOKEN") or "").strip()
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30") or "30")
_rate_windows: dict[str, list[float]] = defaultdict(list)


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    """Reject requests with a wrong/missing token when APP_API_TOKEN is set."""
    if API_TOKEN and x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid or missing token")


def enforce_rate_limit(client: str) -> None:
    """In-memory rate limit: N requests per minute per client."""
    now = time.time()
    window = _rate_windows[client]
    window[:] = [t for t in window if now - t < 60.0]
    if len(window) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    window.append(now)


app = FastAPI(title="TicketPilot")


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    """Attach a trace_id to every request and log it as JSON."""
    request.state.trace_id = uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    response = await call_next(request)
    logger.info("request", extra={
        "trace_id": request.state.trace_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "latency_ms": round((time.perf_counter() - t0) * 1000),
    })
    response.headers["X-Trace-Id"] = request.state.trace_id
    return response


@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/keys/status", dependencies=[Depends(require_token)])
def keys_status():
    """Per-key request/error/cooldown counts (labels + last4 only)."""
    return {"keys": key_manager.status()}


@app.post("/triage", response_model=TriageResponse,
          dependencies=[Depends(require_token)])
def triage(ticket: TicketIn, request: Request):
    """Triage one ticket via the LLM, write an audit row, return result."""
    enforce_rate_limit(request.client.host if request.client else "unknown")
    out, meta = triage_ticket(ticket, settings=settings, key_manager=key_manager)
    trace = tracing.start_trace(ticket.ticket_id, meta["provider"],
                                meta["key_label"])
    tracing.span(trace, "triage", model=meta["model"],
                 latency_ms=meta["latency_ms"],
                 prompt_tokens=meta["prompt_tokens"],
                 completion_tokens=meta["completion_tokens"])
    fix = suggest_fix(ticket, out, settings=settings, key_manager=key_manager)
    tracing.span(trace, "retrieval", doc_ids=",".join(fix["doc_ids"]))
    tracing.span(trace, "generation", found=fix["found"],
                 doc_ids=",".join(fix["doc_ids"]))
    tracing.end_root(trace)
    tracing.flush(trace)
    status = "pending_approval" if out.needs_human_approval else "auto_resolved"
    langfuse_trace_id = tracing.trace_id_of(trace)
    logger.info("triage", extra={
        "ticket_id": ticket.ticket_id, "provider": meta["provider"],
        "key_label": meta["key_label"], "model": meta["model"],
        "latency_ms": meta["latency_ms"],
        "langfuse_trace_id": langfuse_trace_id})
    audit_id = audit.append_event(
        ticket_id=ticket.ticket_id,
        input_data=ticket.model_dump(),
        ai_output={"triage": out.model_dump(), "suggested_fix": fix},
        confidence=out.confidence,
        doc_ids=fix["doc_ids"],
        provider=meta["provider"], key_label=meta["key_label"],
        model=meta["model"],
        tokens=meta["prompt_tokens"] + meta["completion_tokens"],
        latency_ms=meta["latency_ms"], status=status,
        trace_id=langfuse_trace_id)
    return {"ticket_id": ticket.ticket_id, "triage": out, "meta": meta,
            "suggested_fix": fix, "audit_id": audit_id, "status": status}


@app.get("/tickets/summary", dependencies=[Depends(require_token)])
def tickets_summary():
    """Counts per latest status plus total."""
    tickets = audit.list_tickets(limit=100000)
    counts = {"total": len(tickets), "auto_resolved": 0,
              "pending_approval": 0, "approved": 0, "rejected": 0}
    for ticket in tickets:
        if ticket["status"] in counts:
            counts[ticket["status"]] += 1
    return counts


@app.get("/tickets", dependencies=[Depends(require_token)])
def tickets(status: str = None, q: str = None):
    """One entry per ticket (latest audit row), with optional filters."""
    return {"tickets": audit.list_tickets(status=status, search=q)}


@app.get("/approvals/pending", dependencies=[Depends(require_token)])
def approvals_pending():
    """Tickets whose latest audit status is pending_approval."""
    return {"pending": audit.list_pending()}


@app.get("/audit/verify", dependencies=[Depends(require_token)])
def audit_verify():
    """Run hash-chain verification over the whole audit log."""
    return audit.verify_chain()


@app.get("/audit/{ticket_id}", dependencies=[Depends(require_token)])
def audit_history(ticket_id: str):
    """Full audit history for one ticket."""
    history = audit.get_ticket_history(ticket_id)
    if not history:
        raise HTTPException(status_code=404, detail="ticket not found")
    return {"ticket_id": ticket_id, "history": history}


@app.post("/approvals/{ticket_id}/decision",
          dependencies=[Depends(require_token)])
def approval_decision(ticket_id: str, body: DecisionIn):
    """Approve/reject, or revise an earlier decision (append-only).

    Pending tickets decide as before. Decided tickets can flip to the
    opposite decision with a non-empty approver AND note; same-decision
    revisions are 409. Auto-resolved tickets may be rejected with a note.
    """
    if not (body.approver or "").strip():
        raise HTTPException(status_code=422, detail="approver is required")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=422,
                            detail="decision must be approve or reject")
    history = audit.get_ticket_history(ticket_id)
    if not history:
        raise HTTPException(status_code=404, detail="ticket not found")
    last = history[-1]
    new_status = "approved" if body.decision == "approve" else "rejected"
    current = last["status"]
    revising = current in ("approved", "rejected")
    if current == "auto_resolved" and new_status == "approved":
        raise HTTPException(
            status_code=409,
            detail="auto-resolved tickets can only be rejected")
    if revising and new_status == current:
        raise HTTPException(status_code=409,
                            detail="ticket already has this decision")
    if (revising or current == "auto_resolved") and not (body.note or "").strip():
        raise HTTPException(
            status_code=422,
            detail="a note is required for revisions and reviews")
    audit_id = audit.append_event(
        ticket_id=ticket_id,
        input_data=last["input"], ai_output=last["ai_output"],
        confidence=last["confidence"], doc_ids=last["retrieved_doc_ids"],
        provider=last["provider"], key_label=last["key_label"],
        model=last["model"], tokens=last["tokens"],
        latency_ms=last["latency_ms"], status=new_status,
        approver=body.approver.strip(), decision_note=body.note,
        revises_audit_id=last["id"] if revising else None)
    return {"ticket_id": ticket_id, "status": new_status,
            "audit_id": audit_id}
