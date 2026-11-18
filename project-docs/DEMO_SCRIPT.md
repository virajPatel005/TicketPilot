# Demo Script — TicketPilot (2 minutes)

## Pre-demo checklist

- [ ] `pkill -f uvicorn` (kill any old server first)
- [ ] `bash scripts/run_all.sh` — UI on http://127.0.0.1:8501, API docs on
      http://127.0.0.1:8000/docs
- [ ] One server only — if the UI behaves oddly, check there isn't a second
      uvicorn holding port 8000
- [ ] Langfuse dashboard tab open (traces appear per ticket)
- [ ] Audit Log page: Verify chain shows valid
- [ ] Theme chosen (Light or Dark) before clicking anything
- [ ] Browser zoom set to 100%
- [ ] Notifications off, chat apps closed

## 0:00–0:15 — The problem and the pitch

"IT teams read and route every ticket by hand. TicketPilot does the first
pass automatically — triage, a suggested fix, and a human decision where
it matters — and writes every step to a tamper-evident audit log. Built
for regulated environments, where traceability and human sign-off
matter."

## 0:15–0:45 — Submit Ticket

1. Click the **VPN issue** sample and submit. Point at the result:
   auto-resolved, Network/VPN, fix steps with KB doc citations (kb-004,
   kb-005). "Routine ticket, no human needed."
2. Click **Admin access to the trial database** and submit. The result is
   **pending approval**: sensitivity trial-data-related, admin access
   requested. "The sensitive one stops for a human."

## 0:45–1:15 — Approvals / Dashboard

1. Open **Approvals** (or the Dashboard): approve the admin ticket as a
   named approver (e.g. `team.lead`). Point at the queue clearing.
2. On the **Tickets Dashboard**, open the same ticket: the timeline shows
   pending → approved. Then **Revise to Rejected** with a reason note and
   show the third timeline row. "Decisions can change, but only by adding
   a new row — history is never edited."

## 1:15–1:30 — Audit Log

Click **Verify chain**: "Chain valid." One sentence: "Every row stores a
SHA-256 hash of its contents plus the previous row's hash, so any edit
breaks the chain and the verifier says exactly where."

## 1:30–1:50 — Eval Report

Show the v1 vs v2 table, then Groq vs OpenAI. Focus on the **safety
metric**: tickets that needed approval but were wrongly auto-resolved —
on the golden set OpenAI had 0 and Groq v2 had 2 (the keyword safety
net fixed the original misses); on the hold-out set both had 0,
because the approval rule is code, not the model. Groq led on most
hold-out metrics, but the prompts were tuned on Groq and the set is
small, so call the comparison indicative. One honest limitation: "The
golden set was also used for tuning, so those scores are optimistic."

## 1:50–2:00 — Close

"Same code, one setting to switch providers; the OpenAI run cost about
four cents. Next step: a larger hold-out set and regression checks in
CI."

## If something breaks

- **UI shows "API not reachable":** one server is probably still running
  from before (or none is). Run `pkill -f uvicorn`, then
  `bash scripts/run_all.sh`, and confirm `curl http://127.0.0.1:8000/health`.
- **Triage hangs or errors with 429/rate limits:** the key pool cools a
  key down on 429 and retries with the next key; check Key Usage in the
  sidebar for which keys are cooling down.
- **Verify chain shows invalid:** before anything else, check whether two
  servers wrote to the same DB (the known failure mode). Restart with a
  single server and re-check; the backup in `data/` is evidence, not
  live data.
- **Langfuse traces missing:** keys may be unset — the app runs fine
  without them by design. Run `python3 scripts/langfuse_check.py` to see
  why.
- **Port 8501 already in use:** kill the old Streamlit process, then
  restart with `scripts/run_all.sh`.
