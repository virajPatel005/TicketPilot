#!/usr/bin/env python3
"""Validate data/holdout_tickets.csv (no LLM calls)."""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT = ROOT / "data" / "holdout_tickets.csv"
KB_DIR = ROOT / "kb"

CATEGORIES = {"Access/Login", "Software", "Hardware", "Network/VPN",
              "Data/Reports", "Security", "Other/Unclear"}
PRIORITIES = {"High", "Medium", "Low"}
TEAMS = {"Service Desk", "IT Support", "Network Team", "Security Team",
         "Data/Apps Team"}
SENSITIVITIES = {"normal", "access-related", "security-incident",
                 "trial-data-related"}
ADMIN_RE = re.compile(
    r"\b(admin(istrator)?|elevated|root access|superuser|sudo|sysadmin)\b",
    re.IGNORECASE)


def kb_doc_ids():
    ids = set()
    for path in KB_DIR.glob("*.md"):
        head = path.read_text(encoding="utf-8")[:300]
        for line in head.splitlines():
            if line.startswith("doc_id:"):
                ids.add(line.split(":", 1)[1].strip())
    return ids


def main() -> int:
    errors = []
    kb_ids = kb_doc_ids()
    with HOLDOUT.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    seen = Counter()
    for row in rows:
        tid = row["ticket_id"]
        seen[tid] += 1
        for field, allowed in (("category", CATEGORIES),
                               ("priority", PRIORITIES), ("team", TEAMS),
                               ("sensitivity", SENSITIVITIES)):
            if row[field].strip() not in allowed:
                errors.append(f"{tid}: bad {field}={row[field]!r}")
        if row["expected_kb_doc"].strip() not in kb_ids | {"none"}:
            errors.append(f"{tid}: unknown expected_kb_doc "
                          f"{row['expected_kb_doc']!r}")
        text = f"{row['subject']} {row['description']}"
        expect = (row["sensitivity"].strip()
                  in ("security-incident", "trial-data-related")
                  or bool(ADMIN_RE.search(text))
                  or row["category"].strip() == "Other/Unclear")
        actual = row["needs_human_approval"].strip().lower() == "true"
        if expect != actual:
            errors.append(f"{tid}: approval={actual} but rule expects "
                          f"{expect}")
    dupes = [t for t, n in seen.items() if n > 1]
    if dupes:
        errors.append(f"duplicate ticket_ids: {dupes}")
    print(f"tickets: {len(rows)}")
    print("category:", dict(sorted(
        Counter(r["category"] for r in rows).items())))
    print("priority:", dict(sorted(
        Counter(r["priority"] for r in rows).items())))
    print("edge_type:", dict(sorted(
        Counter(r["edge_type"] for r in rows).items())))
    print("approvals:",
          sum(1 for r in rows
              if r["needs_human_approval"].strip().lower() == "true"))
    print("no-KB:", sum(1 for r in rows
                         if r["expected_kb_doc"].strip() == "none"))
    if errors:
        print("\nERRORS:")
        for error in errors:
            print(" ", error)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
