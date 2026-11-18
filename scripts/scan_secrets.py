#!/usr/bin/env python3
"""Scan the TicketPilot project for leaked secrets.

Read-only helper for the pre-publication security audit. Prints one line per
finding:

    PATH:LINE KIND last4=XXXX

Never prints a full secret/key/token (only the last 4 characters).

Skips .venv/, __pycache__/ and .env (real env files are never read).

Usage:
    python3 scripts/scan_secrets.py           # pattern scan (run by auditor)
    python3 scripts/scan_secrets.py --exact   # exact-match against env
                                                values (NOT run by auditor)

The --exact mode loads secret values from the environment and reports, for
each one, only the label and the paths of files containing it. It is meant to
be run by the project owner after the auditor hands over the report.
"""
import argparse
import collections
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git", "node_modules"}
SKIP_FILES = {".env"}  # real env files are never read by this tool

TEXT_EXTS = {
    ".py", ".md", ".json", ".jsonl", ".csv", ".html", ".css", ".js", ".sh",
    ".toml", ".txt", ".yaml", ".yml", ".log", ".ini", ".cfg", ".svg",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico"}
DB_EXTS = {".db"}

# (kind, compiled regex). The whole match is the secret; only last 4 chars
# are ever reported.
PATTERNS = [
    ("groq-key", re.compile(r"gsk_[A-Za-z0-9_-]{20,}")),
    ("openrouter-key", re.compile(r"sk-or-[A-Za-z0-9_-]{20,}")),
    ("openai-proj-key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("firecrawl-key", re.compile(r"fc-[A-Za-z0-9_-]{20,}")),
    ("langfuse-public-key", re.compile(r"pk-lf-[A-Za-z0-9_-]{20,}")),
    ("langfuse-secret-key", re.compile(r"sk-lf-[A-Za-z0-9_-]{20,}")),
    ("huggingface-key", re.compile(r"hf_[A-Za-z0-9_-]{20,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key-header",
     re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP|ANY) PRIVATE KEY-----")),
    ("bearer-token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}")),
    ("kv-secret",
     re.compile(r"""(?ix)\b(api_key|secret|password)\s*=\s*["']?([A-Za-z0-9._\-]{6,})""")),
]

TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


def last4(val: str) -> str:
    return val[-4:] if len(val) >= 4 else "****"


def shannon(s: str) -> float:
    n = len(s)
    if n == 0:
        return 0.0
    counts = collections.Counter(s)
    return -sum((v / n) * math.log2(v / n) for v in counts.values())


def looks_secret_token(s: str) -> bool:
    """Long, high-entropy token with mixed case and digits (a real key-like
    string). Pure hex hashes/UUIDs and lowercase runs do not qualify."""
    if len(s) < 32:
        return False
    if "/" in s:  # model IDs / paths, never keys
        return False
    if shannon(s) <= 3.5:
        return False
    return (any(c.islower() for c in s) and any(c.isupper() for c in s)
            and any(c.isdigit() for c in s))


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            if name in SKIP_FILES:
                continue
            yield p


def is_text_scannable(p: Path) -> bool:
    if p.suffix.lower() in TEXT_EXTS:
        return True
    # Anything under docs/ or site/ is in scope (covers extension-less files).
    try:
        rel = p.relative_to(ROOT)
    except ValueError:
        return False
    return rel.parts[0] in ("docs", "site")


def scan_text_lines(path, text):
    """Yield (line_no, kind, value) for pattern matches in one text file."""
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        for kind, rx in PATTERNS:
            for m in rx.finditer(line):
                out.append((i, kind, m.group(0)))
        for m in TOKEN_RE.finditer(line):
            tok = m.group(0)
            if looks_secret_token(tok):
                out.append((i, "high-entropy-string", tok))
    return out


def scan_text_file(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text_lines(path, text)


def scan_db_file(path):
    """Extract printable strings from a SQLite db and scan them."""
    out = []
    try:
        data = path.read_bytes()
    except OSError:
        return []
    run_re = re.compile(rb"[\x20-\x7e]{8,}")
    for m in run_re.finditer(data):
        val = m.group(0).decode("utf-8", errors="replace")
        # offset reported as the "line" for binary files
        offset = m.start()
        for kind, rx in PATTERNS:
            for rm in rx.finditer(val):
                out.append((offset, kind, rm.group(0)))
        for tm in TOKEN_RE.finditer(val):
            tok = tm.group(0)
            if looks_secret_token(tok):
                out.append((offset, "high-entropy-string", tok))
    return out


def scan_image_filename(path):
    out = []
    name = path.name
    for kind, rx in PATTERNS:
        for m in rx.finditer(name):
            out.append((0, kind + "-filename", m.group(0)))
    return out


def dedupe(findings):
    seen = set()
    uniq = []
    for item in findings:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def pattern_scan():
    findings = []
    scanned = 0
    for p in iter_files(ROOT):
        rel = str(p.relative_to(ROOT))
        if p.suffix.lower() in IMAGE_EXTS:
            continue
        if p.suffix.lower() in DB_EXTS:
            for offset, kind, val in scan_db_file(p):
                findings.append((str(p), offset, kind, val))
            scanned += 1
            continue
        if not is_text_scannable(p):
            continue
        scanned += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, kind, val in scan_text_lines(p, text):
            findings.append((str(p), line_no, kind, val))
    # add image-filename findings with path
    img_findings = []
    for p in iter_files(ROOT):
        if p.suffix.lower() in IMAGE_EXTS:
            for line_no, kind, val in scan_image_filename(p):
                img_findings.append((str(p), line_no, kind, val))
    findings = img_findings + findings
    findings = dedupe(findings)
    return findings, scanned


def env_secret_values():
    """Secret values present in the environment (labels only are logged)."""
    labels = [f"GROQ_API_KEY_{i}" for i in range(1, 12)]
    # OpenRouter order per AGENTS.md: 1, 3, 4, 2.
    labels += ["OPENROUTER_API_KEY_1", "OPENROUTER_API_KEY_3",
               "OPENROUTER_API_KEY_4", "OPENROUTER_API_KEY_2"]
    labels += ["OPENAI_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    out = {}
    for lab in labels:
        val = (os.getenv(lab) or "").strip()
        if val:
            out[lab] = val
    return out


def exact_scan():
    secrets = env_secret_values()
    if not secrets:
        print("No secret values found in the environment.")
        return 0
    hits = 0
    for p in iter_files(ROOT):
        if p.suffix.lower() in IMAGE_EXTS:
            text = p.name
        elif p.suffix.lower() in DB_EXTS:
            try:
                text = p.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                continue
        else:
            if not is_text_scannable(p):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        rel = str(p.relative_to(ROOT))
        for lab, val in secrets.items():
            if val in text:
                print(f"{lab}: {rel}")
                hits += 1
    print(f"Exact matches: {hits}")
    return 0 if hits == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan for leaked secrets.")
    ap.add_argument("--exact", action="store_true",
                    help="exact-match env secret values against files "
                    "(run by owner, not by auditor)")
    args = ap.parse_args()

    if args.exact:
        return exact_scan()

    findings, scanned = pattern_scan()
    if not findings:
        print(f"No secret findings in {scanned} scanned file(s).")
        return 0
    print(f"Secret findings ({len(findings)}) across scanned files:")
    print("path,line,kind,last4")
    for path, line_no, kind, val in findings:
        print(f"{path},{line_no},{kind},last4={last4(val)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
