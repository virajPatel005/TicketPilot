#!/usr/bin/env python3
"""Check Groq + OpenRouter API keys from .env. Never prints full keys."""
import csv
import os
import sys
import time

import requests
from dotenv import load_dotenv # type: ignore

TIMEOUT = 15
GROQ_LABELS = [f"GROQ_API_KEY_{i}" for i in range(1, 12)]
OR_LABELS = [f"OPENROUTER_API_KEY_{i}" for i in range(1, 5)]
GROQ_MODEL = "openai/gpt-oss-120b"


def last4(key: str) -> str:
    return key[-4:] if len(key) >= 4 else "****"


def status_for_code(code: int, phase_ok: bool) -> str:
    if code in (401, 403):
        return "INVALID"
    if code == 429:
        return "RATE_LIMITED"
    # Validity passed but generation failed (or validity itself errored non-auth).
    return "MODEL_ERROR" if phase_ok else "NETWORK_ERROR"


def get_free_model() -> str | None:
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=TIMEOUT)
        r.raise_for_status()
        for m in r.json().get("data", []):
            mid = m.get("id", "")
            if mid.endswith(":free"):
                return mid
    except Exception as e:  # noqa: BLE001 - record, don't crash
        print(f"[warn] could not fetch free model list: {type(e).__name__}: {e}")
    return None


def check_groq(label: str, key: str) -> dict:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    latency = 0
    try:
        t0 = time.perf_counter()
        r = requests.get(
            "https://api.groq.com/openai/v1/models", headers=headers, timeout=TIMEOUT
        )
        latency = round((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            return {"provider": "groq", "label": label, "last4": last4(key),
                    "status": status_for_code(r.status_code, False),
                    "latency_ms": latency, "note": f"models HTTP {r.status_code}"}
        time.sleep(1)
        t0 = time.perf_counter()
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": "Say OK"}],
                  "max_tokens": 5},
            timeout=TIMEOUT,
        )
        latency = round((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            return {"provider": "groq", "label": label, "last4": last4(key),
                    "status": "OK", "latency_ms": latency, "note": f"generated with {GROQ_MODEL}"}
        return {"provider": "groq", "label": label, "last4": last4(key),
                "status": status_for_code(r.status_code, True),
                "latency_ms": latency, "note": f"chat HTTP {r.status_code}"}
    except requests.Timeout:
        return {"provider": "groq", "label": label, "last4": last4(key),
                "status": "NETWORK_ERROR", "latency_ms": latency, "note": "timeout"}
    except requests.RequestException as e:
        return {"provider": "groq", "label": label, "last4": last4(key),
                "status": "NETWORK_ERROR", "latency_ms": latency,
                "note": type(e).__name__}


def check_openrouter(label: str, key: str, free_model: str | None) -> dict:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    latency = 0
    try:
        t0 = time.perf_counter()
        r = requests.get(
            "https://openrouter.ai/api/v1/key", headers=headers, timeout=TIMEOUT
        )
        latency = round((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            return {"provider": "openrouter", "label": label, "last4": last4(key),
                    "status": status_for_code(r.status_code, False),
                    "latency_ms": latency, "note": f"key HTTP {r.status_code}"}
        note = "key valid"
        try:
            d = r.json().get("data", {})
            usage, limit = d.get("usage"), d.get("limit")
            if usage is not None or limit is not None:
                note = f"usage={usage} limit={limit}"
        except Exception:  # noqa: BLE001
            pass
        if not free_model:
            return {"provider": "openrouter", "label": label, "last4": last4(key),
                    "status": "MODEL_ERROR", "latency_ms": latency,
                    "note": f"{note}; no :free model available"}
        time.sleep(1)
        t0 = time.perf_counter()
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={"model": free_model, "messages": [{"role": "user", "content": "Say OK"}],
                  "max_tokens": 5},
            timeout=TIMEOUT,
        )
        latency = round((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            return {"provider": "openrouter", "label": label, "last4": last4(key),
                    "status": "OK", "latency_ms": latency,
                    "note": f"{note}; generated with {free_model}"}
        return {"provider": "openrouter", "label": label, "last4": last4(key),
                "status": status_for_code(r.status_code, True),
                "latency_ms": latency, "note": f"{note}; chat HTTP {r.status_code}"}
    except requests.Timeout:
        return {"provider": "openrouter", "label": label, "last4": last4(key),
                "status": "NETWORK_ERROR", "latency_ms": latency, "note": "timeout"}
    except requests.RequestException as e:
        return {"provider": "openrouter", "label": label, "last4": last4(key),
                "status": "NETWORK_ERROR", "latency_ms": latency,
                "note": type(e).__name__}


def main() -> int:
    load_dotenv()
    free_model = get_free_model()
    if free_model:
        print(f"Free model selected: {free_model}")
    rows = []
    for label in GROQ_LABELS:
        key = (os.getenv(label) or "").strip()
        rows.append({"provider": "groq", "label": label, "last4": last4(key) if key else "-",
                     "status": "MISSING", "latency_ms": 0, "note": "missing or empty"}
                    if not key else check_groq(label, key))
        print(f"[{rows[-1]['status']}] {label} ...{rows[-1]['last4']}")
        time.sleep(1)
    for label in OR_LABELS:
        key = (os.getenv(label) or "").strip()
        rows.append({"provider": "openrouter", "label": label,
                     "last4": last4(key) if key else "-",
                     "status": "MISSING", "latency_ms": 0, "note": "missing or empty"}
                    if not key else check_openrouter(label, key, free_model))
        print(f"[{rows[-1]['status']}] {label} ...{rows[-1]['last4']}")
        time.sleep(1)

    cols = ["provider", "label", "last4", "status", "latency_ms", "note"]
    widths = {c: max(len(c), max(len(str(r[c])) for r in rows)) for c in cols}
    print("\n" + " | ".join(c.ljust(widths[c]) for c in cols))
    print("-+-".join("-" * widths[c] for c in cols))
    for r in rows:
        print(" | ".join(str(r[c]).ljust(widths[c]) for c in cols))

    print("\nSummary:")
    for prov in ("groq", "openrouter"):
        ok = [r["label"] for r in rows if r["provider"] == prov and r["status"] == "OK"]
        failed = [r["label"] for r in rows if r["provider"] == prov and r["status"] != "OK"]
        print(f"  {prov}: {len(ok)} OK, {len(failed)} failed")
        if failed:
            print(f"    failed: {', '.join(failed)}")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "eval", "key_check_results.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
