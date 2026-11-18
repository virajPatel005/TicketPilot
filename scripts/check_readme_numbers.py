#!/usr/bin/env python3
"""Check numeric values in README evaluation tables against results JSON.

Prints every mismatch (README value vs results-file value). Exit 1 if
any mismatch is found.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
EVAL = ROOT / "eval"


def load(name):
    return json.loads((EVAL / name).read_text(encoding="utf-8"))


def section_table(text, heading):
    """Return {row_label: [cell, ...]} for the table after a heading."""
    idx = text.find(heading)
    if idx < 0:
        return {}
    lines = text[idx:].splitlines()
    rows = {}
    in_table = False
    for line in lines:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == "Metric":
                in_table = True
                continue
            if in_table and cells and cells[0] not in ("---",) \
                    and not set(cells[0]) <= set("- "):
                rows[cells[0]] = cells[1:]
        elif in_table and rows:
            break
    return rows


def metric_getters():
    return {
        "Category accuracy":
            lambda r: str(r["component"]["category_accuracy"]),
        "Priority accuracy":
            lambda r: str(r["component"]["priority_accuracy"]),
        "Team accuracy": lambda r: str(r["component"]["team_accuracy"]),
        "Approval precision":
            lambda r: str(r["pipeline"]["approval_precision"]),
        "Approval recall": lambda r: str(r["pipeline"]["approval_recall"]),
        "Approval F1": lambda r: str(r["pipeline"]["approval_f1"]),
        "Safety misses":
            lambda r: str(r["pipeline"]["safety_wrongly_auto_resolved"]),
        "End-to-end pass rate":
            lambda r: str(r["pipeline"]["e2e_pass_rate"]),
        "Retrieval hit@3 (golden)":
            lambda r: str(r["component"]["retrieval"]
                          ["golden_tickets"]["hit@3"]),
        "Injection OK":
            lambda r: r["application"]["injection_ok"],
        "Generation none-rate":
            lambda r: str(r["component"]["generation_none_rate"]),
        "Judge mean score":
            lambda r: str(round(
                sum(r["component"]["judge_scores"].values())
                / len(r["component"]["judge_scores"]), 4)),
        "Latency p50 (ms)":
            lambda r: str(r["application"]["latency_p50_ms"]),
        "Latency p95 (ms)":
            lambda r: str(r["application"]["latency_p95_ms"]),
        "Avg tokens per ticket (triage)":
            lambda r: str(r["application"]["avg_tokens"]),
    }


def main() -> int:
    text = README.read_text(encoding="utf-8")
    v1, v2, openai = (load("results_v1.json"), load("results_v2.json"),
                      load("results_openai.json"))
    getters = metric_getters()
    # Groq v1 vs v2 table: columns are v1, v2.
    mismatches = []
    v1_table = section_table(text, "Groq v1 vs v2")
    for label, cells in v1_table.items():
        getter = getters.get(label)
        if getter is None or len(cells) < 2:
            continue
        for cell, results in ((cells[0], v1), (cells[1], v2)):
            expected = getter(results)
            if cell != expected:
                mismatches.append(
                    f"{label}: README={cell} vs results={expected}")
    # Groq v2 vs OpenAI table: columns are Groq v2, OpenAI.
    go_table = section_table(text, "Groq v2 vs OpenAI")
    for label, cells in go_table.items():
        getter = getters.get(label)
        if getter is None or len(cells) < 2:
            continue
        for cell, results in ((cells[0], v2), (cells[1], openai)):
            expected = getter(results)
            if cell != expected:
                mismatches.append(
                    f"{label}: README={cell} vs results={expected}")
    # Hold-out table: columns are Groq, OpenAI.
    holdout = load("results_holdout_groq.json"), load(
        "results_holdout_openai.json")
    holdout_getters = {
        "Category accuracy":
            lambda r: str(r["category_accuracy"]),
        "Priority accuracy":
            lambda r: str(r["priority_accuracy"]),
        "Team accuracy": lambda r: str(r["team_accuracy"]),
        "Approval precision":
            lambda r: str(r["approval_precision"]),
        "Approval recall": lambda r: str(r["approval_recall"]),
        "Approval F1": lambda r: str(r["approval_f1"]),
        "Safety misses": lambda r: str(r["safety_misses"]),
        "End-to-end pass rate": lambda r: str(r["e2e_pass_rate"]),
        "Retrieval hit@3":
            lambda r: str(r["retrieval"]["hit@3"]),
        "Injection resistance":
            lambda r: f"{round(r['injection']['rate'] * 12)}/12",
        "Latency p50 (ms)": lambda r: str(r["latency_p50_ms"]),
        "Latency p95 (ms)": lambda r: str(r["latency_p95_ms"]),
    }
    holdout_table = section_table(text, "Hold-out test")
    for label, cells in holdout_table.items():
        getter = holdout_getters.get(label)
        if getter is None or len(cells) < 2:
            continue
        for cell, results in ((cells[0], holdout[0]),
                              (cells[1], holdout[1])):
            expected = getter(results)
            if cell != expected:
                mismatches.append(
                    f"holdout {label}: README={cell} vs results="
                    f"{expected}")
    if mismatches:
        print("MISMATCHES:")
        for item in mismatches:
            print(" ", item)
        return 1
    print("README numbers all match the results files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
