#!/usr/bin/env python3
"""Ingest kb/*.md into ChromaDB at CHROMA_PATH (safe to rerun)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.kb import ingest  # noqa: E402


def main() -> int:
    """Run ingestion and print the ingested document count."""
    count = ingest()
    print(f"Ingested {count} KB docs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
