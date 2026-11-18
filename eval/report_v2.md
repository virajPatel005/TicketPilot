# TicketPilot Eval Report

Run ID: `20261108-145425`  |  Date: 2026-11-08T14:54:25.076599+00:00  |  Provider: groq  |  Model: openai/gpt-oss-120b  |  Tickets: 60

## Component

| Metric | Value |
|---|---|
| Retrieval questions hit@1 | 1.0 |
| Retrieval questions hit@3 | 1.0 |
| Retrieval questions MRR | 1.0 |
| Retrieval none correct | 5/5 |
| Golden retrieval hit@1 | 0.9038 |
| Golden retrieval hit@3 | 0.9231 |
| Golden retrieval MRR | 0.9135 |
| Golden none correct | 3/8 |
| Category accuracy | 0.9333 |
| Priority accuracy | 0.6667 |
| Team accuracy | 0.8667 |
| Category macro F1 | 0.9225 |
| Generation doc rate | 0.9231 |
| Generation none rate | 0.375 |
| Judge mean score | 4.467 |

Calibration (category accuracy by confidence bucket):

| Bucket | Accuracy |
|---|---|
| <0.7 | 1.0 |
| 0.7-0.9 | None |
| 0.9-1.0 | 0.931 |
| Wrong with confidence >= 0.9 | 4 |

Category confusion matrix (golden -> predicted):

| golden \ pred | Access/Login | Software | Hardware | Network/VPN | Data/Reports | Security | Other/Unclear |
|---|---|---|---|---|---|---|---|
| Access/Login | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| Software | 1 | 9 | 0 | 0 | 0 | 0 | 0 |
| Hardware | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| Network/VPN | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| Data/Reports | 0 | 1 | 0 | 0 | 8 | 0 | 0 |
| Security | 0 | 0 | 0 | 0 | 0 | 11 | 0 |
| Other/Unclear | 0 | 0 | 2 | 0 | 0 | 0 | 4 |

Priority confusion matrix (golden -> predicted):

| golden \ pred | High | Medium | Low |
|---|---|---|---|
| High | 9 | 2 | 0 |
| Medium | 3 | 22 | 0 |
| Low | 4 | 11 | 9 |

## Pipeline

| Metric | Value |
|---|---|
| Approval precision | 0.55 |
| Approval recall | 0.8462 |
| Approval F1 | 0.6667 |
| **Safety: wrongly auto-resolved** | **2** |
| End-to-end pass rate | 0.6167 |
| Failure attribution | {'triage': 8, 'retrieval': 7, 'approval-rule': 8} |

## Application

| Metric | Value |
|---|---|
| Latency p50 (ms) | 1046 |
| Latency p95 (ms) | 1421 |
| Avg tokens/ticket | 1099.2 |
| Total tokens | 65953 |
| Requests per key_label | {'GROQ_API_KEY_1': 15, 'GROQ_API_KEY_2': 15, 'GROQ_API_KEY_3': 15, 'GROQ_API_KEY_5': 15, 'GROQ_API_KEY_6': 15, 'GROQ_API_KEY_7': 14, 'GROQ_API_KEY_8': 14, 'GROQ_API_KEY_9': 14, 'GROQ_API_KEY_10': 14, 'GROQ_API_KEY_11': 14} |
| LLM error rate | 0.0 |
| Injection tickets approval+priority OK | 2/4 |
| Typo/vague/missing-info category acc | 1.0 |
| Empty description handling | graceful (Other/Unclear + approval) |
| Audit verify_chain | {'valid': True, 'checked': 60, 'first_bad_id': None} |
| Audit tamper detected | detected |
| Groq cost | free (tokens recorded above) |
| OpenAI cost | estimate, not run |

## Slices

| Slice | Category acc | Priority acc | Team acc | Approval acc |
|---|---|---|---|---|
| difficulty=easy | 0.917 | 0.542 | 0.917 | 0.792 |
| difficulty=medium | 0.9 | 0.7 | 0.8 | 0.75 |
| difficulty=hard | 1.0 | 0.867 | 0.867 | 0.933 |
| edge_type=typo | 1.0 | 0.4 | 1.0 | 0.8 |
| edge_type=vague | 1.0 | 0.75 | 0.75 | 0.75 |
| edge_type=multi-issue | 1.0 | 1.0 | 1.0 | 1.0 |
| edge_type=prompt-injection | 0.75 | 0.75 | 0.5 | 0.5 |
| edge_type=none | 0.939 | 0.606 | 0.879 | 0.849 |

## Top failures

| ID | Stage | Golden -> Predicted | Doc |
|---|---|---|---|
| G-002 | triage | Access/Login/Medium/IT Support/False -> Access/Login/Medium/Service Desk/False | kb-002 vs kb-002,kb-001,kb-003 |
| G-004 | triage | Access/Login/High/Security Team/True -> Access/Login/High/Data/Apps Team/True | kb-014 vs kb-014,kb-001,kb-003 |
| G-005 | triage | Access/Login/Medium/IT Support/False -> Access/Login/Medium/Service Desk/False | kb-002 vs kb-002,kb-001,kb-003 |
| G-008 | triage | Software/Low/IT Support/False -> Access/Login/Medium/Service Desk/True | kb-007 vs kb-014 |
| G-018 | retrieval | Software/Low/IT Support/False -> Software/Low/IT Support/False | none vs kb-006 |
| G-020 | triage | Hardware/High/Service Desk/False -> Hardware/Medium/IT Support/False | kb-009 vs kb-009,kb-013,kb-008 |
| G-021 | retrieval | Security/High/Security Team/True -> Security/High/Security Team/True | kb-013 vs none |
| G-025 | retrieval | Security/High/Security Team/True -> Security/High/Security Team/True | kb-013 vs none |
| G-038 | triage | Data/Reports/Medium/Data/Apps Team/False -> Software/Medium/IT Support/False | kb-010 vs none |
| G-039 | approval-rule | Data/Reports/Low/Data/Apps Team/False -> Data/Reports/Low/Data/Apps Team/True | kb-011 vs kb-011,kb-010 |
| G-041 | approval-rule | Data/Reports/Medium/Data/Apps Team/False -> Data/Reports/Medium/Data/Apps Team/True | kb-011 vs kb-011 |
| G-044 | approval-rule | Data/Reports/Low/Data/Apps Team/False -> Data/Reports/Medium/Data/Apps Team/True | kb-011 vs kb-011 |
| G-047 | approval-rule | Security/Medium/Security Team/False -> Security/High/Security Team/True | kb-012 vs kb-012 |
| G-048 | approval-rule | Security/Low/Security Team/False -> Security/High/Security Team/True | kb-012 vs kb-012 |
| G-050 | approval-rule | Security/Low/Security Team/False -> Security/High/Security Team/True | kb-012 vs kb-012 |

## Known limits

The golden set was used for tuning, so v2 scores are optimistic (the model
was tuned against the same tickets it was scored on). A held-out set —
new tickets written after tuning, never used for prompt or threshold
decisions — is the next step before trusting these numbers.

## Findings

- Category accuracy is 0.9333 (macro F1 0.9225); team accuracy 0.8667, priority 0.6667.
- Retrieval hit@3 on golden tickets is 0.9231 (MRR 0.9135).
- Safety: 2 tickets that needed approval were wrongly auto-resolved (approval precision 0.55, recall 0.8462).
- Most failures are attributed to stage 'triage' (8 tickets).
- Hard tickets: category accuracy 1.0 (15 tickets); 4 wrong categories had confidence >= 0.9.
