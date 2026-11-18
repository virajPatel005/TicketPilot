# TicketPilot — Pre-publication Security Audit

**Scope:** everything under the project folder that would be published
(`docs/`, `project-docs/`, `eval/`, `data/`, `scripts/`, `app/`, `ui/`, `tests/`,
`README.md`, `.env.example`, `.gitignore`). Skipped: `.venv/`,
`__pycache__/`, `.env` itself (`.env` was never read — no secret values
were ever inspected). No LLM/API calls were made.

**Report files produced:** `project-docs/SECURITY_REPORT.md` (this report) and
`scripts/scan_secrets.py` (secret scanner, pattern-scan mode was run;
`--exact` mode was written but NOT run).

---

## 1. Secret scan

Scanner: `scripts/scan_secrets.py` (pattern-scan mode, run). It scans text
files, JSON/JSONL/CSV, markdown, HTML/CSS/JS, shell, SQLite DB text
content, `eval/cache/`, logs, and anything under `project-docs/` and `docs/`,
plus image file names. It reports only the path, line, kind and last 4
characters — never a full secret.

**Result: no real secrets found anywhere in scope.**

- `scripts/scan_secrets.py` run (pattern scan): 6 hits, all benign
  high-entropy strings inside the gitignored SQLite files
  `data/audit.db` and `data/audit_backup_forked_20261108.db`. These are
  just key *labels* / model names stored in SQLite cells (e.g.
  `GROQ_API_KEY_1`, `openai/gpt-oss-120b`), not key values, and those DBs
  are gitignored so they are not published.
- No `gsk_`, `sk-`, `sk-or-`, `fc-`, `pk-lf-`, `sk-lf-`, `hf_`, `AKIA`,
  `Bearer`, `api_key=`, `secret=`, `password=`, or private-key headers in
  any scanned file.
- `eval/key_check_results.csv`, `check_keys.py`, `key_manager.py`,
  `ui/app.py`, `app/main.py`, `app/llm_client.py` expose only labels +
  last-4 characters. ✓
- `.env.example` contains only variable names with empty/safe defaults,
  no real values. ✓
- Image file names and alt text in `docs/` contain no secrets. ✓
- README numbers verified against results files via
  `scripts/check_readme_numbers.py`: all match. ✓

`--exact` mode was written (loads values from the environment, compares
against scanned files, prints labels + paths only) but was **not run**,
as instructed.

---

## 2. Gitignore and publish list

`.gitignore` (final, see section 6 below) now ignores: `.env`,
`.env.*` (with `!.env.example` exception), `__pycache__/`, `*.pyc`,
`.pytest_cache/`, `data/audit.db`, `data/audit_backup_*.db`,
`data/llm_calls.jsonl`, `data/chroma/` (CHROMA_PATH), `.venv/`,
`*.log`, `eval/cache/`, `.playwright-mcp/`, `pw-out/`,
`project-docs/screenshots/`.

**Publish list after fix:** 99 files originally; with `data/chroma/`,
`.venv/` and `*.log` added to `.gitignore`, fewer files would be
published. No file exceeds 1 MB. The largest published items are eval
result JSONs (~88 KB each).

**Binary/database files that would be published:** none — `data/chroma/`
is now ignored. The four PNGs in `docs/assets/` are published and were
checked (no secrets/personal data).

**Personal-data check:** `data/golden_tickets.csv` (60 tickets) and
`data/holdout_tickets.csv` (30 tickets) contain synthetic requester
names — no real emails, phone numbers, or real company/customer/colleague
names detected. `data/llm_calls.jsonl` holds smoke-test call metadata
only (key labels, tokens, latency — no ticket text, no keys) and is
gitignored.

---

## 3. Code security review (app/, ui/, scripts/)

All fixes from this report are applied in `app/`, `ui/` and `scripts/`.

**Keys:** no key, key prefix beyond last-4, or ticket text is written to
logs, Langfuse, exceptions, or API responses. `/keys/status` returns
labels + last4 only. `app/llm_client.py` logs `label, key[-4:]` only.
`app/tracing.py` sends ticket_id / provider / key_label to Langfuse
(metrics + labels only, never ticket text or keys); degrades to no-op if
keys missing.

**Injection / unsafe patterns:** no `eval`/`exec`/`pickle`/
`subprocess shell=True`/`os.system`/`yaml.load`. All SQLite queries are
parameterised. No path traversal in file handling. No open redirects.

**UI XSS (fixed):** a single `_esc()` helper (`html.escape`) is used for
every user/LLM-controlled value rendered in `unsafe_allow_html` blocks
(subject, description, reason, sub_category, approver, note, doc ids).

**API exposure:** no authentication by design (local demo). Host binding
is `127.0.0.1` in `scripts/run_all.sh` and uvicorn. `/docs`,
`/redoc`, `/audit/verify`, `/audit/{id}`, `/tickets` remain open; when
`APP_API_TOKEN` is set the API requires `X-API-Token` on `/triage`,
`/approvals/*`, `/tickets*`, `/audit/*` and `/keys/status`; `/health`
stays open. The approval endpoint accepts any approver name (self-declared
approver — documented limitation).

**Input handling:** Pydantic v2 with `max_length` (subject 200,
description 5000, etc.); oversize input returns 422. Empty
subject/description rejected in the UI.

**Audit log:** append-only — no `UPDATE`/`DELETE` in `app/audit.py`.
`BEGIN IMMEDIATE` transaction fix in place (forked-chain race). New
audit DBs are created with mode `0o600`; existing `data/audit.db` and
`data/audit_backup_*.db` set to `0o600`.

**Prompt injection:** ticket text treated as untrusted (system prompt +
code safety net); retrieved KB docs not trusted as instructions.

**Dependencies:** every `requirements.txt` entry is unpinned — pinning
was **not** done pending your approval (item 7).

**Licence:** MIT `LICENSE` added (copyright Viraj Patel, 2026).

---

## 4. Site and docs review

- `docs/index.html`, `README.md`, `project-docs/DEMO_SCRIPT.md`, `eval/*.md`,
  `PLAN.md`, `AGENTS.md`: no secrets, no real personal data, no internal
  paths (`\\wsl.localhost`, `C:\Users`), no private URLs.
- README author line "Viraj Patel · Demo project using synthetic data."
  — intentional portfolio attribution.
- All README evaluation numbers match the results JSON files
  (`scripts/check_readme_numbers.py` passes).
- Placeholder `href="#"` links remain in `docs/index.html` (Demo video,
  Repository, Watch demo, GitHub, LinkedIn), each marked with a `TODO`
  comment. Left in place per instructions; listed as an open item below.
- Screenshots (`project-docs/screenshots/` and `docs/assets/`): opened and
  reviewed `04_keys.png`, `approvals.png`, `dashboard.png`,
  `submit-result.png`, `audit-valid.png` — all show only labels/last-4,
  synthetic subjects, no full keys, emails, real names, or file paths.
  `docs/script.js` has no `innerHTML` with dynamic data (theme toggle +
  IntersectionObserver only) — clean.

---

## 5. Severity summary (as found)

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 4 |
| Medium   | 4 |
| Low      | 2 |
| Info     | 3 |
| **Total**| **13** |

---

## 6. Finding status (fixed / accepted / open)

| ID | Finding | Status | Note |
|----|---------|--------|------|
| H-1 | `data/chroma/` not gitignored; `.venv/`, `*.log` gaps | **Fixed** | `.gitignore` now ignores `data/chroma/`, `.venv/`, `*.log`, `pw-out/`, plus `.env.*` with `!.env.example` exception |
| H-2 | `data/audit.db` world-writable (`0o666`) | **Fixed** | Existing DBs set to `0o600`; `app/audit.py` creates new DBs with `0o600` |
| H-3 | XSS via `unsafe_allow_html` with LLM-controlled text | **Fixed** | `_esc()` helper applied to subject/reason/sub_category/approver/note/doc ids |
| H-4 | No auth; open endpoints; any approver name | **Fixed (controls applied)** | `127.0.0.1` binding; optional `APP_API_TOKEN` + `X-API-Token` on protected routes; `/health` open. No user login/roles (by design, documented) |
| H-5 | No request limits / rate limiting | **Fixed** | Pydantic `max_length` + 422; in-memory rate limit on POST `/triage` (`RATE_LIMIT_PER_MIN`, default 30) |
| M-1 | `.gitignore` gaps (`.venv/`, `*.log`) | **Fixed** | Covered by H-1 |
| M-2 | Open endpoints / any-approver | **Fixed** | Covered by H-4 |
| M-3 | All dependencies unpinned | **Open** | Pinning not done — awaiting your approval (item 7) |
| M-4 | No rate limit | **Fixed** | Covered by H-5 |
| L-1 | Placeholder `href="#"` links in `docs/index.html` | **Accepted (open item)** | Left in place per instructions; listed below |
| L-2 | Eval result files published | **Accepted** | Synthetic test set; intentional to ship |
| I-1 | No `LICENSE` file | **Fixed** | MIT `LICENSE` added (Viraj Patel, 2026) |
| I-2 | Author name in README/footer | **Accepted** | Intentional portfolio attribution |
| I-3 | No real secrets found | **Accepted** | Scanner clean; `--exact` mode written but not run |

---

## 7. Safe to publish?

**NO — not yet.** One open blocking item remains:

- **M-3** All `requirements.txt` dependencies are unpinned. Pinning was
  deliberately **not** done pending your approval (you said "ask me
  before pinning. If I approve, pin each package to the version
  currently installed"). Approve pinning and I'll pin
  `fastapi`, `uvicorn`, `pydantic>=2`, `python-dotenv`, `requests`,
  `pytest`, `httpx`, `chromadb`, `sentence-transformers`, `langfuse`,
  `streamlit` to their installed versions.

### Checklist — manual items only you can do

- [ ] Rotate any exposed key (none found by the scanner; if you run
  `scripts/scan_secrets.py --exact` yourself and it reveals a key in a
  file, rotate it immediately).
- [ ] Check the global opencode configuration outside this project for
  stored keys (this repo's scan covers this project only).
- [ ] Set a spend limit on the OpenAI dashboard (`OPENAI_BUDGET_USD` is
  only a client-side guard).
- [ ] Review `data/` before publishing (confirm synthetic names/emails;
  `data/chroma/` is now gitignored; `audit.db` is `0o600`).
- [ ] Decide whether `eval/results_*.json` should stay published or be
  gitignored.
- [ ] Run `scripts/scan_secrets.py --exact` yourself against your
  environment (written but not run by the auditor).
- [ ] Approve dependency pinning (item 7 / M-3) if you want pinned
  `requirements.txt`.

---

## 8. Open item: placeholder links in docs/index.html

Left in place per instructions (each marked with a `TODO` comment):

- `Demo video` — `href="#"` (header nav)
- `Repository` — `href="#"` (header nav)
- `Watch the demo` — `href="#"` (hero CTA)
- `GitHub` — `href="#"` (footer)
- `LinkedIn` — `href="#"` (footer)

Replace these with real URLs before publishing.

---

## 9. Test results

Ran `python -m pytest -q -p no:langsmith_plugin --continue-on-collection-errors`.

**54 passed, 4 skipped, 7 errors.**

- The 4 skipped are the optional-token / rate-limit tests in
  `tests/test_security.py`, which skip because `fastapi` is not installed
  in this environment (they run where fastapi is available).
- The 7 errors are **pre-existing** collection failures caused by
  missing optional dependencies, not by these changes:
  - `tests/test_audit.py` and `tests/test_dashboard.py` import
    `fastapi` (not installed).
  - `tests/test_kb.py` imports `chromadb` (not installed).
- `pkill -f uvicorn`: not available on this host; no uvicorn server was
  running (uvicorn is not installed), so no server needed stopping.
- Dependency installation: not performed (per the rule to ask before
  installing). `fastapi`, `uvicorn`, `chromadb`, `sentence-transformers`
  and `langfuse` are declared in `requirements.txt` but not installed in
  this environment, so the FastAPI-dependent test modules cannot be
  collected here. They will run in an environment where the requirements
  are installed.
