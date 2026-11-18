#!/usr/bin/env python3
"""Langfuse connection check: auth, one test trace, flush. Never prints keys."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402


def main() -> int:
    """Run the Langfuse auth + test-trace check. Returns 0 on OK, 1 on error."""
    load_dotenv()
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
                 "LANGFUSE_HOST"):
        print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
    try:
        from langfuse import Langfuse
        client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST") or None)
        if hasattr(client, "auth_check"):
            print("auth_check:", client.auth_check())
        trace_id = client.create_trace_id()
        span = client.start_observation(
            trace_context={"trace_id": trace_id},
            name="ticketpilot-connection-test", as_type="span",
            metadata={"ticket_id": "connection-test"})
        span.end()
        client.flush()
        client.shutdown()
        print(f"OK trace_id={trace_id}")
        return 0
    except Exception as exc:  # noqa: BLE001 - print exact error, never keys
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
