"""Eval metric tests with tiny fake data (no network)."""
import importlib.util
import pathlib

import pytest

spec = importlib.util.spec_from_file_location(
    "run_eval", pathlib.Path("eval/run_eval.py"))
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)


def test_norm_bool():
    assert run_eval.norm_bool("TRUE") is True
    assert run_eval.norm_bool(" true ") is True
    assert run_eval.norm_bool("false") is False
    assert run_eval.norm_bool("FALSE") is False


def test_accuracy():
    pairs = [("a", "a"), ("a", "b"), ("b", "b"), ("b", "b")]
    assert run_eval.accuracy(pairs) == 0.75
    assert run_eval.accuracy([]) == 0.0


def test_hit_at_k_and_mrr():
    rank = run_eval.rank_of(["x", "kb-004", "y"], "kb-004")
    assert rank == 2
    assert run_eval.hit_at_k(rank, 1) == 0.0
    assert run_eval.hit_at_k(rank, 3) == 1.0
    assert run_eval.mrr(rank) == 0.5
    assert run_eval.rank_of(["x"], "kb-004") is None
    assert run_eval.mrr(None) == 0.0


def test_prf1_and_macro_f1():
    p, r, f1 = run_eval.prf1(2, 2, 0)
    assert (p, r) == (0.5, 1.0)
    assert abs(f1 - 2 / 3) < 1e-9
    pairs = [("A", "A"), ("A", "B"), ("B", "B")]
    assert run_eval.macro_f1(pairs, ["A", "B"]) == pytest.approx(
        (run_eval.prf1(1, 0, 1)[2] + run_eval.prf1(1, 1, 0)[2]) / 2)


def test_confusion_matrix():
    pairs = [("A", "A"), ("A", "B"), ("B", "B")]
    matrix = run_eval.confusion_matrix(pairs, ["A", "B"])
    assert matrix["A"] == {"A": 1, "B": 1}
    assert matrix["B"] == {"A": 0, "B": 1}


def base_record(**overrides):
    record = {"category_ok": True, "team_ok": True, "doc_ok": True,
              "generation_ok": True, "approval_ok": True}
    record.update(overrides)
    return record


def test_failure_attribution_order():
    assert run_eval.failure_stage(base_record()) is None
    assert run_eval.failure_stage(base_record(team_ok=False)) == "triage"
    assert run_eval.failure_stage(base_record(doc_ok=False)) == "retrieval"
    assert run_eval.failure_stage(
        base_record(generation_ok=False)) == "generation"
    assert run_eval.failure_stage(
        base_record(approval_ok=False)) == "approval-rule"
    # First failing stage wins.
    assert run_eval.failure_stage(
        base_record(category_ok=False, approval_ok=False)) == "triage"
    assert run_eval.failure_stage(
        base_record(doc_ok=False, approval_ok=False)) == "retrieval"


def test_percentiles():
    pct = run_eval.percentiles([10, 20, 30, 40])
    assert pct[50] == 30
    assert run_eval.percentiles([]) == {50: 0.0, 95: 0.0}
