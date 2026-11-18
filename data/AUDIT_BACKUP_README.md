# Audit backup — forked chain (2026-11-08)

`audit_backup_forked_20261108.db` is the old TicketPilot audit log,
preserved **unmodified as evidence**. Do not delete it and do not edit it.

## What happened

The hash chain forked at rows 3 and 4: both rows point at row 2's hash
(`prev_hash`), so row 4 does not chain to row 3 and `verify_chain`
reported `first_bad_id: 4`.

## Cause

Rows 3 and 4 were written 0.3 ms apart by two concurrent processes. The
old `append_event` did a SELECT of the last row followed by an INSERT
without a transaction, so both writers read row 2 as "last" and chained
to it, forking the chain. Row data, the hash formula, and the canonical
JSON were all unchanged — every row's stored hash still reproduces
exactly; only the 3→4 link is wrong.

## Fix

`app/audit.py` now wraps the read-last + insert in one
`BEGIN IMMEDIATE` transaction (busy timeout 5 s), so SQLite serializes
concurrent writers and the chain cannot fork. `verify_chain` now also
reports a failure `reason` (`prev_hash mismatch` / `row_hash mismatch`).

The app now creates a fresh `data/audit.db` on next start. The backup
above is kept as-is for the record.
