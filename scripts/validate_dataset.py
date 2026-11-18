#!/usr/bin/env python3
"""Validate data/golden_tickets.csv and data/kb_questions.csv (no LLM calls)."""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "data" / "golden_tickets.csv"
QUESTIONS = ROOT / "data" / "kb_questions.csv"
KB_DIR = ROOT / "kb"

CATEGORIES = {"Access/Login", "Software", "Hardware", "Network/VPN",
              "Data/Reports", "Security", "Other/Unclear"}
PRIORITIES = {"High", "Medium", "Low"}
TEAMS = {"Service Desk", "IT Support", "Network Team", "Security Team",
         "Data/Apps Team"}
SENSITIVITIES = {"normal", "access-related", "security-incident",
                 "trial-data-related"}
DIFFICULTIES = {"easy", "medium", "hard"}
EDGE_TYPES = {"none", "typo", "vague", "multi-issue", "off-topic",
              "missing-info", "urgent-tone", "prompt-injection"}
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
    """Run all dataset checks; print counts. Returns 0 if clean, 1 on errors."""
    errors = []
    kb_ids = kb_doc_ids()
    with GOLDEN.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    seen = Counter()
    for row in rows:
        tid = row["ticket_id"]
        seen[tid] += 1
        for field, allowed in (("category", CATEGORIES),
                               ("priority", PRIORITIES), ("team", TEAMS),
                               ("sensitivity", SENSITIVITIES),
                               ("difficulty", DIFFICULTIES),
                               ("edge_type", EDGE_TYPES)):
            if row[field].strip() not in allowed:
                errors.append(f"{tid}: bad {field}={row[field]!r}")
        if row["expected_kb_doc"].strip() not in kb_ids | {"none"}:
            errors.append(f"{tid}: unknown expected_kb_doc "
                          f"{row['expected_kb_doc']!r}")
        # Approval rule (AGENTS.md, without the confidence condition).
        text = f"{row['subject']} {row['description']}"
        expect = (row["sensitivity"].strip() != "normal"
                  or bool(ADMIN_RE.search(text))
                  or row["category"].strip() == "Other/Unclear")
        actual = row["needs_human_approval"].strip().lower() == "true"
        if expect != actual:
            errors.append(f"{tid}: approval={actual} but rule expects "
                          f"{expect}")
    dupes = [t for t, n in seen.items() if n > 1]
    if dupes:
        errors.append(f"duplicate ticket_ids: {dupes}")

    with QUESTIONS.open(newline="", encoding="utf-8") as fh:
        questions = list(csv.DictReader(fh))
    for q in questions:
        if q["expected_kb_doc"].strip() not in kb_ids | {"none"}:
            errors.append(f"{q['question_id']}: unknown expected_kb_doc "
                          f"{q['expected_kb_doc']!r}")
    matched = {q["expected_kb_doc"] for q in questions} - {"none"}
    missing_docs = kb_ids - matched
    if missing_docs:
        errors.append(f"kb_questions missing docs: {sorted(missing_docs)}")

    def counts(field):
        return dict(sorted(Counter(r[field].strip() for r in rows).items()))

    print(f"tickets: {len(rows)}")
    print("category:", counts("category"))
    print("priority:", counts("priority"))
    print("difficulty:", counts("difficulty"))
    print("edge_type:", counts("edge_type"))
    approvals = sum(1 for r in rows
                    if r["needs_human_approval"].strip().lower() == "true")
    nokb = sum(1 for r in rows if r["expected_kb_doc"].strip() == "none")
    print(f"needs_human_approval=true: {approvals}")
    print(f"expected_kb_doc=none: {nokb}")
    print(f"kb_questions: {len(questions)} "
          f"({len(matched)} with doc, "
          f"{sum(1 for q in questions if q['expected_kb_doc']=='none')} none)")
    if errors:
        print("\nERRORS:")
        for error in errors:
            print(" ", error)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
