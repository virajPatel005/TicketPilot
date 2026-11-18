#!/usr/bin/env python3
"""Check the numbers shown on docs/index.html against the results files.

Prints any mismatch. Exit 1 on mismatch. No network, no API calls.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "index.html"
EVAL = ROOT / "eval"


def load(name):
    return json.loads((EVAL / name).read_text(encoding="utf-8"))


def main() -> int:
    text = SITE.read_text(encoding="utf-8")
    groq = load("results_holdout_groq.json")
    openai = load("results_holdout_openai.json")
    v2 = load("results_v2.json")
    checks = [
        ("safety misses Groq holdout", "0",
         str(groq["safety_misses"])),
        ("safety misses OpenAI holdout", "0",
         str(openai["safety_misses"])),
        ("test tickets total", "90",
         str(v2["n"] + groq["n"])),
        ("injection resistance Groq holdout", "11 of 12",
         f"{round(groq['injection']['rate'] * 12)} of 12"),
        ("approval recall Groq holdout", "1.0",
         str(groq["approval_recall"])),
        ("approval recall OpenAI holdout", "1.0",
         str(openai["approval_recall"])),
        ("latency p50 Groq holdout", "1042",
         str(groq["latency_p50_ms"])),
    ]
    problems = []
    for name, expected, actual in checks:
        if expected not in text:
            problems.append(f"{name}: page missing {expected!r}")
        if actual != expected:
            problems.append(f"{name}: file has {actual!r}, "
                            f"page claims {expected!r}")
    # Broken local links: every assets/*.png and styles.css, script.js.
    for ref in re.findall(r'(?:src|href)="(?!http|#)([^"]+)"', text):
        if not (SITE.parent / ref).exists():
            problems.append(f"missing local file: {ref}")
    if problems:
        print("MISMATCHES:")
        for problem in problems:
            print(" ", problem)
        return 1
    print("All numbers and local links check out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
