# PLAN.md — TicketPilot

Demo for an IT Business Automation Intern interview at Signant Health
(clinical trial software — traceability and human sign-off matter).
Deadline: 2 days.

## Architecture

```text
Ticket
  -> LLM triage (category / priority / team / sensitivity / confidence)
  -> Chroma RAG (KB retrieval, local embeddings)
  -> Decision / approval (needs_human_approval rules)
  -> Audit log (SQLite, SHA-256 hash chain)
  -> Langfuse (trace per ticket)
```

## Folder structure

```text
TicketPilot/
  app/          # FastAPI app + llm_client
  ui/           # Streamlit UI
  kb/           # 15 synthetic KB docs (*.md)
  data/         # golden_tickets.csv
  eval/         # eval scripts + results (key_check_results.csv)
  scripts/      # check_keys.py
  tests/        # pytest
  .env.example
  AGENTS.md / PLAN.md / README.md
```

## Provider policy (Part A)

Fallback order: Groq round-robin -> wait-and-retry (shortest cooldown,
max 3 waits) -> OpenAI only for the final run. OpenRouter is optional and
off by default (`ENABLE_OPENROUTER=false`); when on, order is 1, 3, 4, 2.
Duplicate Groq keys: keep the first, drop the rest, label-only warning.

## Stage checklist

- [x] **Stage 1** — Setup and key check (done: `scripts/check_keys.py`;
      11 Groq OK, 3 of 4 OpenRouter OK, OpenRouter key 2 rate-limited)
- [x] **Stage 2** — Core triage endpoint and `llm_client` with key manager
- [x] **Stage 3** — KB (15 synthetic docs in `kb/`) and RAG
- [x] **Stage 4** — Approval flow and hash-chained audit log
- [x] **Stage 5A** — Golden dataset (`data/golden_tickets.csv`, 60 tickets;
      `data/kb_questions.csv`, 20 questions; `scripts/validate_dataset.py`)
- [x] **Stage 5B** — Eval script + report (`eval/run_eval.py`, `eval/report.md`;
      run `20261108-143141`: category acc 0.9333, e2e 0.6, safety misses 2)
- [x] **Stage 5C** — Tuning round 1 (prompt rubric, approval rule, keyword
      safety net, KB_MIN_SCORE 0.25); v2 e2e 0.617, safety misses still 2
      (different tickets). See `eval/compare_v1_v2.md`.
- [x] **Stage 6** — Streamlit UI v2: Light/Dark enterprise theme
      (`ui/theme.py`, `scripts/check_contrast.py`, screenshots in
      `docs/screenshots/v2/`)
- [x] **Stage 7a** — Tickets Dashboard + revise-decision
      (`GET /tickets`, `/tickets/summary`, revision flow; screenshots in
      `docs/screenshots/v3/`)
- [x] **Stage 5D** — OpenAI comparison run (`eval/compare_groq_openai.md`;
      OpenAI e2e 0.65, safety misses 0, spend $0.0434). See
      `eval/report_openai.md`.
- [x] **Hold-out (Groq)** — 30 unseen tickets (`data/holdout_tickets.csv`);
      category 0.9333, e2e 0.7, safety misses 0, injection resistance
      11/12. See `eval/holdout_report.md`.
- [x] **Hold-out (OpenAI)** — 30 unseen tickets on gpt-4o-mini; category
      0.8667, e2e 0.5667, safety misses 0, injection resistance 11/12.
      See `eval/holdout_report_openai.md`.
- [ ] **Stage 7** — README, demo video, interview prep

## Golden dataset (`data/golden_tickets.csv`)

80–100 tickets (start with 40), synthetic and hand-reviewed.

Columns: ticket_id, created_at, channel, requester_name, department, role,
location, affected_system, subject, description, attachments_mentioned,
business_impact, deadline_mentioned, category, sub_category, priority,
priority_reason, team, needs_human_approval, approval_reason, sensitivity,
expected_kb_doc, expected_fix_steps, difficulty (easy/medium/hard),
edge_type (typo, vague, multi-issue, off-topic, missing-info, urgent-tone,
prompt-injection).

Plus about 15 KB retrieval questions and some tickets with no matching KB doc.

Metrics: category/priority/team accuracy, confusion matrix, correct
human-routing rate, retrieval hit rate, cost and latency per ticket. Run on
Groq first, then the same set on OpenAI, and compare in a table. Slice
results by difficulty and edge_type.

## KB (`kb/*.md`)

15 docs, each with title, category, steps, when to escalate, owner team.
Topics: password reset, MFA, account locked, VPN, Wi-Fi, software install,
license, laptop issues, new device, report/Excel failing, data access request,
phishing reporting, lost device, admin access policy, plus one more.

## Example flows

1. **Answerable (VPN):** employee can't connect to VPN -> Network/VPN,
   Retrieved KB doc, fix steps returned, no human approval needed.
2. **Needs human (admin access to trial database):** admin/elevated access to
   trial data requested -> sensitivity = trial-data-related,
   `needs_human_approval = true`, routed to approver, audit row written.
3. **No answer (lunch menu today):** off-topic -> category Other/Unclear,
   confidence low, `needs_human_approval = true`, RAG says it does not know.
