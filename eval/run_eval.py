#!/usr/bin/env python3
"""Stage 5B evaluation: component, pipeline and application metrics.

Usage: python3 eval/run_eval.py [--limit N] [--no-judge] [--run-id ID]

Groq only (LLM_PROVIDER is forced to groq). Uses a TEMPORARY audit DB.
Per-ticket results are cached under eval/cache/<run_id>.jsonl so a crashed
run can resume with the same --run-id without repeating LLM calls.
Never prints full API keys.
"""
import argparse
import csv
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force a temp audit DB before any app module reads settings.
# Provider comes from LLM_PROVIDER (default groq); OpenAI runs use
# LLM_PROVIDER=openai with OPENAI_MODEL from env. Groq is the default.
_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")
_RUN_ID = None  # set in main() before importing app modules that load settings


def _setup_env(run_id: str) -> Path:
    tmp_db = ROOT / "eval" / f"tmp_audit_{run_id}.db"
    os.environ["AUDIT_DB_PATH"] = str(tmp_db)
    return tmp_db


CATEGORIES = ["Access/Login", "Software", "Hardware", "Network/VPN",
              "Data/Reports", "Security", "Other/Unclear"]
PRIORITIES = ["High", "Medium", "Low"]
TEAMS = ["Service Desk", "IT Support", "Network Team", "Security Team",
         "Data/Apps Team"]


# ---------------------------------------------------------------- metrics
def norm_bool(value) -> bool:
    """Normalize the golden approval column (mixes TRUE/true/FALSE)."""
    return str(value).strip().lower() == "true"


def accuracy(pairs) -> float:
    """Fraction of (golden, predicted) pairs that match."""
    pairs = list(pairs)
    if not pairs:
        return 0.0
    return sum(1 for g, p in pairs if g == p) / len(pairs)


def rank_of(doc_ids, expected):
    """1-based rank of expected doc in the list, or None (0 = not found)."""
    try:
        return list(doc_ids).index(expected) + 1
    except ValueError:
        return None


def hit_at_k(rank, k) -> float:
    return 1.0 if (rank is not None and rank <= k) else 0.0


def mrr(rank) -> float:
    return (1.0 / rank) if rank else 0.0


def prf1(tp, fp, fn):
    """Precision, recall, F1 from counts (0.0 when undefined)."""
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def macro_f1(pairs, labels) -> float:
    """Macro-averaged F1 over the given label set."""
    pairs = list(pairs)
    if not pairs:
        return 0.0
    f1s = []
    for label in labels:
        tp = sum(1 for g, p in pairs if g == label and p == label)
        fp = sum(1 for g, p in pairs if g != label and p == label)
        fn = sum(1 for g, p in pairs if g == label and p != label)
        f1s.append(prf1(tp, fp, fn)[2])
    return sum(f1s) / len(f1s)


def confusion_matrix(pairs, labels):
    """{golden: {predicted: count}} for every label."""
    matrix = {g: {p: 0 for p in labels} for g in labels}
    for golden, predicted in pairs:
        if golden in matrix and predicted in matrix[golden]:
            matrix[golden][predicted] += 1
    return matrix


def failure_stage(record):
    """First failing stage for one ticket record, or None if it passes.

    Order: triage (category/team) -> retrieval (doc) -> generation
    (found/doc_ids) -> approval-rule (approval flag).
    """
    if not (record["category_ok"] and record["team_ok"]):
        return "triage"
    if not record["doc_ok"]:
        return "retrieval"
    if not record["generation_ok"]:
        return "generation"
    if not record["approval_ok"]:
        return "approval-rule"
    return None


def percentiles(values, points=(50, 95)):
    """Percentiles of a numeric list (0.0 when empty)."""
    values = sorted(values)
    if not values:
        return {p: 0.0 for p in points}
    out = {}
    for p in points:
        idx = min(len(values) - 1, int(p / 100 * len(values)))
        out[p] = values[idx]
    return out


# ------------------------------------------------------------------- main
def load_golden():
    with (ROOT / "data" / "golden_tickets.csv").open(
            newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_questions():
    with (ROOT / "data" / "kb_questions.csv").open(
            newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


JUDGE_SYSTEM = """You judge whether IT fix steps are faithful to help articles.
Reply with ONLY a JSON object: {"score": 1-5, "reason": "short"}.
5 = every step is supported by the articles, nothing invented.
1 = steps contradict or are not in the articles at all.
"""


def judge_faithfulness(answer, doc_texts, settings, key_manager):
    """LLM-as-judge faithfulness score 1-5 for one generated fix."""
    from app import llm_client
    user = ("Help articles:\n" + "\n\n".join(doc_texts)
            + "\n\nGenerated fix:\n" + answer)
    data, _meta = llm_client.complete_json(
        JUDGE_SYSTEM, user, ticket_id="judge", settings=settings,
        key_manager=key_manager)
    score = int(data.get("score", 0))
    return min(5, max(1, score)), str(data.get("reason", ""))[:120]


def run_one_ticket(row, settings, key_manager):
    """Triage + RAG for one golden ticket. Returns a result record."""
    from app.rag import suggest_fix
    from app.schemas import TicketIn
    from app.triage import triage_ticket

    ticket = TicketIn(ticket_id=row["ticket_id"], subject=row["subject"],
                      description=row["description"],
                      department=row.get("department") or None,
                      channel=row.get("channel") or None,
                      affected_system=row.get("affected_system") or None,
                      business_impact=row.get("business_impact") or None)
    out, meta = triage_ticket(ticket, settings=settings,
                              key_manager=key_manager)
    fix = suggest_fix(ticket, out, settings=settings,
                      key_manager=key_manager)
    expected_doc = row["expected_kb_doc"].strip()
    doc_ok = (expected_doc in fix["doc_ids"]) if expected_doc != "none" \
        else (fix["found"] is False)
    generation_ok = (fix["found"] is True and doc_ok) \
        if expected_doc != "none" else (fix["found"] is False)
    golden_approval = norm_bool(row["needs_human_approval"])
    record = {
        "ticket_id": row["ticket_id"], "subject": row["subject"],
        "difficulty": row["difficulty"], "edge_type": row["edge_type"],
        "golden_category": row["category"], "pred_category": out.category,
        "category_ok": out.category == row["category"],
        "golden_priority": row["priority"], "pred_priority": out.priority,
        "priority_ok": out.priority == row["priority"],
        "golden_team": row["team"], "pred_team": out.team,
        "team_ok": out.team == row["team"],
        "confidence": out.confidence,
        "golden_approval": golden_approval,
        "pred_approval": bool(out.needs_human_approval),
        "approval_ok": bool(out.needs_human_approval) == golden_approval,
        "expected_doc": expected_doc,
        "retrieved_docs": fix["doc_ids"], "doc_ok": doc_ok,
        "generation_ok": generation_ok, "found": fix["found"],
        "answer": fix["answer"][:500],
        "provider": meta["provider"], "key_label": meta["key_label"],
        "model": meta["model"],
        "prompt_tokens": meta["prompt_tokens"],
        "completion_tokens": meta["completion_tokens"],
        "latency_ms": meta["latency_ms"], "status": meta["status"],
    }
    record["failing_stage"] = failure_stage(record)
    record["e2e_pass"] = (record["category_ok"] and record["team_ok"]
                          and record["approval_ok"] and record["doc_ok"])
    return record


def retrieval_eval(settings):
    """Level 1a: hit@1/hit@3/MRR on kb_questions + golden tickets."""
    from app import kb
    questions = load_questions()
    hits1, hits3, mrrs, none_ok = [], [], [], 0
    none_total = 0
    for q in questions:
        expected = q["expected_kb_doc"].strip()
        results = kb.retrieve(q["question"], k=3)
        doc_ids = [r["doc_id"] for r in results]
        if expected == "none":
            none_total += 1
            if not results:
                none_ok += 1
        else:
            rank = rank_of(doc_ids, expected)
            hits1.append(hit_at_k(rank, 1))
            hits3.append(hit_at_k(rank, 3))
            mrrs.append(mrr(rank))
    golden = load_golden()
    g_hits1, g_hits3, g_mrrs, g_none_ok, g_none_total = [], [], [], 0, 0
    for row in golden:
        expected = row["expected_kb_doc"].strip()
        category = row["category"] if row["category"] != "Other/Unclear" else None
        results = kb.retrieve(f"{row['subject']} {row['description']}",
                              category=category, k=3)
        doc_ids = [r["doc_id"] for r in results]
        if expected == "none":
            g_none_total += 1
            if not results:
                g_none_ok += 1
        else:
            rank = rank_of(doc_ids, expected)
            g_hits1.append(hit_at_k(rank, 1))
            g_hits3.append(hit_at_k(rank, 3))
            g_mrrs.append(mrr(rank))
    return {
        "questions": {"n": len(questions), "hit@1": _mean(hits1),
                      "hit@3": _mean(hits3), "mrr": _mean(mrrs),
                      "none_correct": f"{none_ok}/{none_total}"},
        "golden_tickets": {"hit@1": _mean(g_hits1), "hit@3": _mean(g_hits3),
                           "mrr": _mean(g_mrrs),
                           "none_correct": f"{g_none_ok}/{g_none_total}"},
    }


def _mean(values):
    return round(sum(values) / len(values), 4) if values else 0.0


def _slice_accuracy(records, field, key):
    groups = defaultdict(list)
    for r in records:
        groups[r[field]].append(r[key])
    return {g: round(sum(v) / len(v), 3) for g, v in sorted(groups.items())}


def build_report(run_id, provider, model, started_at, records, retrieval,
                 judge_scores, app_metrics, slices):
    cat_pairs = [(r["golden_category"], r["pred_category"]) for r in records]
    pri_pairs = [(r["golden_priority"], r["pred_priority"]) for r in records]
    team_pairs = [(r["golden_team"], r["pred_team"]) for r in records]
    appr_pairs = [(r["golden_approval"], r["pred_approval"]) for r in records]
    tp = sum(1 for g, p in appr_pairs if g and p)
    fp = sum(1 for g, p in appr_pairs if not g and p)
    fn = sum(1 for g, p in appr_pairs if g and not p)
    appr_p, appr_r, appr_f1 = prf1(tp, fp, fn)
    safety_bad = sum(1 for r in records
                     if r["golden_approval"] and not r["pred_approval"])
    buckets = {"<0.7": [], "0.7-0.9": [], "0.9-1.0": []}
    wrong_high_conf = 0
    for r in records:
        bucket = ("<0.7" if r["confidence"] < 0.7
                  else "0.7-0.9" if r["confidence"] < 0.9 else "0.9-1.0")
        buckets[bucket].append(r["category_ok"])
        if not r["category_ok"] and r["confidence"] >= 0.9:
            wrong_high_conf += 1
    bucket_acc = {b: (round(sum(v) / len(v), 3) if v else None)
                  for b, v in buckets.items()}
    gen_records = [r for r in records if r["expected_doc"] != "none"]
    gen_doc_ok = _mean([1.0 if r["generation_ok"] else 0.0
                        for r in gen_records])
    none_records = [r for r in records if r["expected_doc"] == "none"]
    none_ok = _mean([1.0 if r["generation_ok"] else 0.0
                     for r in none_records])
    failures = [r for r in records if r["failing_stage"]]
    e2e = _mean([1.0 if r["e2e_pass"] else 0.0 for r in records])

    metrics = {
        "run_id": run_id, "provider": provider, "model": model,
        "started_at": started_at, "n": len(records),
        "component": {
            "retrieval": retrieval,
            "category_accuracy": round(accuracy(cat_pairs), 4),
            "priority_accuracy": round(accuracy(pri_pairs), 4),
            "team_accuracy": round(accuracy(team_pairs), 4),
            "category_macro_f1": round(macro_f1(cat_pairs, CATEGORIES), 4),
            "category_confusion": confusion_matrix(cat_pairs, CATEGORIES),
            "priority_confusion": confusion_matrix(pri_pairs, PRIORITIES),
            "calibration_buckets": bucket_acc,
            "wrong_with_confidence_ge_0.9": wrong_high_conf,
            "generation_doc_rate": gen_doc_ok,
            "generation_none_rate": none_ok,
            "judge_scores": judge_scores,
        },
        "pipeline": {
            "approval_precision": round(appr_p, 4),
            "approval_recall": round(appr_r, 4),
            "approval_f1": round(appr_f1, 4),
            "safety_wrongly_auto_resolved": safety_bad,
            "e2e_pass_rate": e2e,
            "failure_attribution": dict(Counter(r["failing_stage"]
                                               for r in failures)),
        },
        "application": app_metrics,
        "slices": slices,
    }

    lines = [
        "# TicketPilot Eval Report", "",
        f"Run ID: `{run_id}`  |  Date: {started_at}  |  "
        f"Provider: {provider}  |  Model: {model}  |  Tickets: {len(records)}",
        "", "## Component", "",
        "| Metric | Value |",
        "|---|---|",
        f"| Retrieval questions hit@1 | {retrieval['questions']['hit@1']} |",
        f"| Retrieval questions hit@3 | {retrieval['questions']['hit@3']} |",
        f"| Retrieval questions MRR | {retrieval['questions']['mrr']} |",
        f"| Retrieval none correct | {retrieval['questions']['none_correct']} |",
        f"| Golden retrieval hit@1 | {retrieval['golden_tickets']['hit@1']} |",
        f"| Golden retrieval hit@3 | {retrieval['golden_tickets']['hit@3']} |",
        f"| Golden retrieval MRR | {retrieval['golden_tickets']['mrr']} |",
        f"| Golden none correct | {retrieval['golden_tickets']['none_correct']} |",
        f"| Category accuracy | {metrics['component']['category_accuracy']} |",
        f"| Priority accuracy | {metrics['component']['priority_accuracy']} |",
        f"| Team accuracy | {metrics['component']['team_accuracy']} |",
        f"| Category macro F1 | {metrics['component']['category_macro_f1']} |",
        f"| Generation doc rate | {gen_doc_ok} |",
        f"| Generation none rate | {none_ok} |",
        f"| Judge mean score | "
        f"{round(_mean(list(judge_scores.values())), 3) if judge_scores else 'skipped'} |",
        "", "Calibration (category accuracy by confidence bucket):",
        "", "| Bucket | Accuracy |", "|---|---|",
        *[f"| {b} | {v} |" for b, v in bucket_acc.items()],
        f"| Wrong with confidence >= 0.9 | {wrong_high_conf} |",
        "", "Category confusion matrix (golden -> predicted):", "",
        _matrix_md(metrics["component"]["category_confusion"], CATEGORIES),
        "", "Priority confusion matrix (golden -> predicted):", "",
        _matrix_md(metrics["component"]["priority_confusion"], PRIORITIES),
        "", "## Pipeline", "",
        "| Metric | Value |",
        "|---|---|",
        f"| Approval precision | {round(appr_p, 4)} |",
        f"| Approval recall | {round(appr_r, 4)} |",
        f"| Approval F1 | {round(appr_f1, 4)} |",
        f"| **Safety: wrongly auto-resolved** | **{safety_bad}** |",
        f"| End-to-end pass rate | {e2e} |",
        f"| Failure attribution | {metrics['pipeline']['failure_attribution']} |",
        "", "## Application", "",
        "| Metric | Value |",
        "|---|---|",
        f"| Latency p50 (ms) | {app_metrics['latency_p50_ms']} |",
        f"| Latency p95 (ms) | {app_metrics['latency_p95_ms']} |",
        f"| Avg tokens/ticket | {app_metrics['avg_tokens']} |",
        f"| Total tokens | {app_metrics['total_tokens']} |",
        f"| Requests per key_label | {app_metrics['requests_per_key']} |",
        f"| LLM error rate | {app_metrics['error_rate']} |",
        f"| Injection tickets approval+priority OK | "
        f"{app_metrics['injection_ok']} |",
        f"| Typo/vague/missing-info category acc | "
        f"{app_metrics['robustness_category_acc']} |",
        f"| Empty description handling | {app_metrics['empty_input']} |",
        f"| Audit verify_chain | {app_metrics['audit_verify']} |",
        f"| Audit tamper detected | {app_metrics['audit_tamper']} |",
        "| Groq cost | free (tokens recorded above) |",
        "| OpenAI cost | estimate, not run |",
        "", "## Slices", "",
        "| Slice | Category acc | Priority acc | Team acc | Approval acc |",
        "|---|---|---|---|---|",
    ]
    for label, sl in slices.items():
        lines.append(
            f"| {label} | {sl['category']} | {sl['priority']} | "
            f"{sl['team']} | {sl['approval']} |")
    lines += ["", "## Top failures", ""]
    lines.append("| ID | Stage | Golden -> Predicted | Doc |")
    lines.append("|---|---|---|---|")
    for r in failures[:15]:
        lines.append(
            f"| {r['ticket_id']} | {r['failing_stage']} | "
            f"{r['golden_category']}/{r['golden_priority']}/"
            f"{r['golden_team']}/{r['golden_approval']} -> "
            f"{r['pred_category']}/{r['pred_priority']}/{r['pred_team']}/"
            f"{r['pred_approval']} | {r['expected_doc']} vs "
            f"{','.join(r['retrieved_docs']) or 'none'} |")
    lines += ["", "## Findings", ""]
    lines += _findings(metrics, records)
    return metrics, "\n".join(lines) + "\n"


def _matrix_md(matrix, labels):
    header = "| golden \\ pred | " + " | ".join(labels) + " |"
    sep = "|" + "---|" * (len(labels) + 1)
    rows = ["| " + " | ".join(
        [g] + [str(matrix[g][p]) for p in labels]) + " |" for g in labels]
    return "\n".join([header, sep, *rows])


def _findings(metrics, records):
    comp = metrics["component"]
    pipe = metrics["pipeline"]
    by_stage = pipe["failure_attribution"]
    weakest = (max(by_stage, key=by_stage.get) if by_stage
               else "none")
    hard = [r for r in records if r["difficulty"] == "hard"]
    hard_acc = _mean([1.0 if r["category_ok"] else 0.0 for r in hard])
    return [
        f"- Category accuracy is {comp['category_accuracy']} "
        f"(macro F1 {comp['category_macro_f1']}); team accuracy "
        f"{comp['team_accuracy']}, priority {comp['priority_accuracy']}.",
        f"- Retrieval hit@3 on golden tickets is "
        f"{metrics['component']['retrieval']['golden_tickets']['hit@3']} "
        f"(MRR {metrics['component']['retrieval']['golden_tickets']['mrr']}).",
        f"- Safety: {pipe['safety_wrongly_auto_resolved']} tickets that "
        f"needed approval were wrongly auto-resolved "
        f"(approval precision {pipe['approval_precision']}, "
        f"recall {pipe['approval_recall']}).",
        f"- Most failures are attributed to stage '{weakest}' "
        f"({by_stage.get(weakest, 0)} tickets).",
        f"- Hard tickets: category accuracy {hard_acc} "
        f"({len(hard)} tickets); "
        f"{comp['wrong_with_confidence_ge_0.9']} wrong categories had "
        f"confidence >= 0.9.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp_db = _setup_env(run_id)
    started_at = datetime.now(timezone.utc).isoformat()

    from app import audit, kb
    from app.config import load_key_pool, load_settings
    from app.key_manager import KeyManager

    settings = load_settings()
    assert settings.llm_provider == _PROVIDER, (
        f"settings provider {settings.llm_provider} != env {_PROVIDER}")
    key_manager = KeyManager(
        load_key_pool(enable_openrouter=settings.enable_openrouter),
        cooldown_sec=settings.key_cooldown_sec,
        enable_openrouter=settings.enable_openrouter)
    provider = settings.llm_provider
    model = {"groq": settings.groq_model,
             "openrouter": settings.openrouter_model,
             "openai": settings.openai_model}.get(provider, "")

    cache_path = ROOT / "eval" / "cache" / f"{run_id}.jsonl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cached = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                cached[rec["ticket_id"]] = rec

    golden = load_golden()
    if args.limit:
        golden = golden[:args.limit]
    records = []
    errors = 0
    for row in golden:
        if row["ticket_id"] in cached:
            records.append(cached[row["ticket_id"]])
            print(f"[{row['ticket_id']}] cached")
            continue
        t0 = time.perf_counter()
        try:
            record = run_one_ticket(row, settings, key_manager)
            if record["status"] != "ok":
                errors += 1
        except Exception as exc:  # noqa: BLE001 - record and continue
            errors += 1
            record = {"ticket_id": row["ticket_id"],
                      "subject": row["subject"], "difficulty": row["difficulty"],
                      "edge_type": row["edge_type"],
                      "golden_category": row["category"], "pred_category": "ERROR",
                      "category_ok": False, "golden_priority": row["priority"],
                      "pred_priority": "ERROR", "priority_ok": False,
                      "golden_team": row["team"], "pred_team": "ERROR",
                      "team_ok": False, "confidence": 0.0,
                      "golden_approval": norm_bool(row["needs_human_approval"]),
                      "pred_approval": False, "approval_ok": False,
                      "expected_doc": row["expected_kb_doc"],
                      "retrieved_docs": [], "doc_ok": False,
                      "generation_ok": False, "found": False, "answer": "",
                      "provider": provider, "key_label": "-",
                      "model": model, "prompt_tokens": 0,
                      "completion_tokens": 0, "latency_ms": 0,
                      "status": f"error:{type(exc).__name__}"}
            record["failing_stage"] = failure_stage(record)
            record["e2e_pass"] = False
        elapsed = round((time.perf_counter() - t0) * 1000)
        if not record.get("latency_ms"):
            record["latency_ms"] = elapsed
        records.append(record)
        with cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"[{row['ticket_id']}] stage={record['failing_stage']} "
              f"key={record['key_label']}")
        time.sleep(1)  # stay under Groq rate limits

    # Audit rows (temp DB) so the audit check is meaningful.
    for record in records:
        audit.append_event(
            ticket_id=record["ticket_id"], input_data={"eval": True},
            ai_output={"pred_category": record["pred_category"]},
            confidence=record["confidence"],
            doc_ids=record["retrieved_docs"], provider=record["provider"],
            key_label=record["key_label"], model=record["model"],
            tokens=record["prompt_tokens"] + record["completion_tokens"],
            latency_ms=record["latency_ms"],
            status="pending_approval" if record["pred_approval"]
            else "auto_resolved", db_path=str(tmp_db))

    retrieval = retrieval_eval(settings)

    # Judge (max 30 tickets with an expected doc).
    judge_scores = {}
    if not args.no_judge:
        judged = 0
        for record in records:
            if judged >= 30 or record["expected_doc"] == "none" \
                    or not record["found"]:
                continue
            doc_texts = []
            for doc_id in record["retrieved_docs"]:
                sections = kb.get_sections(doc_id)
                doc_texts.append(
                    f"[{doc_id}]\n"
                    + "\n".join(f"{k}:\n{v}" for k, v in sections.items()))
            try:
                score, _reason = judge_faithfulness(
                    record["answer"], doc_texts, settings, key_manager)
                judge_scores[record["ticket_id"]] = score
            except Exception as exc:  # noqa: BLE001
                print(f"judge failed for {record['ticket_id']}: "
                      f"{type(exc).__name__}")
            judged += 1
            time.sleep(1)

    # Robustness: empty-description input must fail gracefully.
    empty_result = _empty_input_check(settings, key_manager)

    latencies = [r["latency_ms"] for r in records]
    pct = percentiles(latencies)
    tokens = [r["prompt_tokens"] + r["completion_tokens"] for r in records]
    requests_per_key = {s["label"]: s["requests"]
                        for s in key_manager.status() if s["requests"]}
    injection = [r for r in records if r["edge_type"] == "prompt-injection"]
    injection_ok = (f"{sum(1 for r in injection if r['approval_ok'] and r['priority_ok'])}/{len(injection)}"
                    if injection else "n/a")
    robust = [r for r in records
              if r["edge_type"] in ("typo", "vague", "missing-info")]
    app_metrics = {
        "latency_p50_ms": pct[50], "latency_p95_ms": pct[95],
        "avg_tokens": round(_mean(tokens), 1) if tokens else 0,
        "total_tokens": sum(tokens),
        "requests_per_key": requests_per_key,
        "error_rate": round(errors / len(records), 4) if records else 0,
        "injection_ok": injection_ok,
        "robustness_category_acc": (
            round(_mean([1.0 if r["category_ok"] else 0.0
                         for r in robust]), 3) if robust else None),
        "empty_input": empty_result,
        "audit_verify": audit.verify_chain(db_path=str(tmp_db)),
        "audit_tamper": "pending",
    }
    # Tamper check on the temp DB, then delete it.
    import sqlite3
    conn = sqlite3.connect(str(tmp_db))
    conn.execute("UPDATE audit_log SET status='approved' WHERE id=1")
    conn.commit()
    conn.close()
    after = audit.verify_chain(db_path=str(tmp_db))
    app_metrics["audit_tamper"] = (
        "detected" if (not after["valid"]
                       and after["first_bad_id"] == 1) else "MISSED")
    tmp_db.unlink(missing_ok=True)

    slices = {}
    for label, group in (("difficulty=easy", [r for r in records if r["difficulty"] == "easy"]),
                         ("difficulty=medium", [r for r in records if r["difficulty"] == "medium"]),
                         ("difficulty=hard", [r for r in records if r["difficulty"] == "hard"]),
                         ("edge_type=typo", [r for r in records if r["edge_type"] == "typo"]),
                         ("edge_type=vague", [r for r in records if r["edge_type"] == "vague"]),
                         ("edge_type=multi-issue", [r for r in records if r["edge_type"] == "multi-issue"]),
                         ("edge_type=prompt-injection", [r for r in records if r["edge_type"] == "prompt-injection"]),
                         ("edge_type=none", [r for r in records if r["edge_type"] == "none"])):
        slices[label] = {
            "category": _slice_accuracy(group, "difficulty", "category_ok")
            if False else round(_mean([1.0 if r["category_ok"] else 0.0
                                       for r in group]), 3),
            "priority": round(_mean([1.0 if r["priority_ok"] else 0.0
                                     for r in group]), 3),
            "team": round(_mean([1.0 if r["team_ok"] else 0.0
                                 for r in group]), 3),
            "approval": round(_mean([1.0 if r["approval_ok"] else 0.0
                                     for r in group]), 3),
        }

    metrics, report = build_report(run_id, provider, model, started_at,
                                   records, retrieval, judge_scores,
                                   app_metrics, slices)
    metrics["records"] = records
    eval_dir = ROOT / "eval"
    (eval_dir / "report.md").write_text(report, encoding="utf-8")
    (eval_dir / f"results_{run_id}.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    with (eval_dir / "failures.csv").open("w", newline="",
                                         encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "ticket_id", "subject", "golden_category", "pred_category",
            "golden_priority", "pred_priority", "golden_team", "pred_team",
            "golden_approval", "pred_approval", "expected_doc",
            "retrieved_docs", "failing_stage"])
        writer.writeheader()
        for r in records:
            if r["failing_stage"]:
                writer.writerow({
                    "ticket_id": r["ticket_id"], "subject": r["subject"],
                    "golden_category": r["golden_category"],
                    "pred_category": r["pred_category"],
                    "golden_priority": r["golden_priority"],
                    "pred_priority": r["pred_priority"],
                    "golden_team": r["golden_team"],
                    "pred_team": r["pred_team"],
                    "golden_approval": r["golden_approval"],
                    "pred_approval": r["pred_approval"],
                    "expected_doc": r["expected_doc"],
                    "retrieved_docs": ";".join(r["retrieved_docs"]),
                    "failing_stage": r["failing_stage"]})
    print(f"\nRun {run_id}: {len(records)} tickets, "
          f"e2e={metrics['pipeline']['e2e_pass_rate']}, "
          f"safety_bad={metrics['pipeline']['safety_wrongly_auto_resolved']}")
    from app import llm_client as _lc
    prompt_total = sum(r["prompt_tokens"] for r in records)
    completion_total = sum(r["completion_tokens"] for r in records)
    print(f"Tokens (triage calls): input={prompt_total} "
          f"output={completion_total}")
    print(f"Budget guard spend: ${ _lc._spend():.4f} "
          f"(budget ${settings.openai_budget_usd:.2f})")
    print(f"Wrote eval/report.md, eval/failures.csv, "
          f"eval/results_{run_id}.json")
    return 0


def _empty_input_check(settings, key_manager) -> str:
    """Empty description must fail gracefully (validation error or safe label)."""
    from app.schemas import TicketIn
    from app.triage import triage_ticket
    try:
        ticket = TicketIn(ticket_id="EMPTY-1", subject="", description="")
        out, _meta = triage_ticket(ticket, settings=settings,
                                   key_manager=key_manager)
    except Exception as exc:  # noqa: BLE001 - any clean failure is graceful
        return f"graceful ({type(exc).__name__})"
    if out.category == "Other/Unclear" and out.needs_human_approval:
        return "graceful (Other/Unclear + approval)"
    return f"UNEXPECTED label {out.category}"


if __name__ == "__main__":
    sys.exit(main())
