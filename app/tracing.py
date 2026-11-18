"""Optional Langfuse tracing: one trace per ticket, metrics/labels only.

Uses the langfuse v5 SDK API (start_observation + flush). Never sends API
keys or full ticket text. If keys are missing or Langfuse fails, everything
degrades to no-ops and the app runs normally.
"""
import logging
import os

logger = logging.getLogger(__name__)

_client = None
_warned = False


def _warn_once(msg):
    global _warned
    if not _warned:
        logger.warning("Langfuse tracing disabled: %s", msg)
        _warned = True


def enabled() -> bool:
    """True when the Langfuse keys are set (host optional, Cloud default)."""
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY")
                and os.getenv("LANGFUSE_SECRET_KEY"))


def _get_client():
    global _client
    if _client is None:
        from langfuse import Langfuse
        _client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST") or None)
    return _client


def start_trace(ticket_id, provider, key_label):
    """Start one trace (root span) for a ticket; returns a handle or None."""
    if not enabled():
        return None
    try:
        client = _get_client()
        trace_id = client.create_trace_id()
        root = client.start_observation(
            trace_context={"trace_id": trace_id},
            name=f"triage-{ticket_id}", as_type="span",
            metadata={"ticket_id": ticket_id, "provider": provider,
                      "key_label": key_label,
                      "tags": [str(provider), str(key_label),
                               str(ticket_id)]})
        return {"client": client, "trace_id": trace_id, "root": root}
    except Exception as exc:  # noqa: BLE001 - tracing must never break the app
        _warn_once(f"{type(exc).__name__}: {exc}")
        return None


def span(trace, name, **metrics):
    """Record a child span (triage/retrieval/generation) with metrics only."""
    if trace is None:
        return
    try:
        obs = trace["client"].start_observation(
            trace_context={"trace_id": trace["trace_id"]},
            name=name, as_type="span", metadata=metrics)
        obs.end()
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"{type(exc).__name__}: {exc}")


def end_root(trace):
    """End the root span (never raises)."""
    if trace is None:
        return
    try:
        trace["root"].end()
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"{type(exc).__name__}: {exc}")


def flush(trace=None):
    """Flush batched traces so short runs do not lose them."""
    if trace is None:
        return
    try:
        trace["client"].flush()
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"{type(exc).__name__}: {exc}")


def trace_id_of(trace):
    """Langfuse trace id for the audit row, or None (never raises)."""
    if trace is None:
        return None
    try:
        return trace.get("trace_id")
    except Exception:  # noqa: BLE001
        return None
