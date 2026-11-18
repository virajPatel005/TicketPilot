---
doc_id: kb-010
title: Report or Excel failing
category: Data/Reports
owner_team: Data/Apps Team
---

## Symptoms

A report will not run, shows blank or wrong numbers, or an Excel file
crashes, shows errors in formulas, or cannot be refreshed. The file may
open but the data is stale, or the export may fail with a timeout. The
problem may affect one report or every report from the same source.

## Steps to fix

1. Refresh the data once more and check the report date range and filters.
2. Try opening a copy of the file, and check for error values such as
   divided-by-zero or missing references in the formulas.
3. Confirm the source system is available and that you still have access
   to the underlying data.
4. Note the report name, the date range, and a screenshot of the error.
5. Submit a ticket with those details and whether other users see the
   same problem.

## When to escalate

Escalate to the Data/Apps Team if numbers look wrong, if the report is
needed for a submission deadline, or if the source data may be corrupted.
Do not edit trial data to force a report to pass; report the discrepancy.
