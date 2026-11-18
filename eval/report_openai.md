# TicketPilot Eval Report

Run ID: `20261108-173501`  |  Date: 2026-11-08T17:35:01.030981+00:00  |  Provider: openai  |  Model: gpt-4o-mini  |  Tickets: 60

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
| Category accuracy | 0.9167 |
| Priority accuracy | 0.6667 |
| Team accuracy | 0.8833 |
| Category macro F1 | 0.9112 |
| Generation doc rate | 0.8654 |
| Generation none rate | 0.75 |
| Judge mean score | 4.867 |

Calibration (category accuracy by confidence bucket):

| Bucket | Accuracy |
|---|---|
| <0.7 | 1.0 |
| 0.7-0.9 | 0.833 |
| 0.9-1.0 | 0.923 |
| Wrong with confidence >= 0.9 | 4 |

Category confusion matrix (golden -> predicted):

| golden \ pred | Access/Login | Software | Hardware | Network/VPN | Data/Reports | Security | Other/Unclear |
|---|---|---|---|---|---|---|---|
| Access/Login | 7 | 0 | 0 | 0 | 0 | 0 | 1 |
| Software | 1 | 9 | 0 | 0 | 0 | 0 | 0 |
| Hardware | 0 | 0 | 6 | 0 | 0 | 0 | 1 |
| Network/VPN | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| Data/Reports | 1 | 1 | 0 | 0 | 7 | 0 | 0 |
| Security | 0 | 0 | 0 | 0 | 0 | 11 | 0 |
| Other/Unclear | 0 | 0 | 0 | 0 | 0 | 0 | 6 |

Priority confusion matrix (golden -> predicted):

| golden \ pred | High | Medium | Low |
|---|---|---|---|
| High | 9 | 2 | 0 |
| Medium | 1 | 24 | 0 |
| Low | 1 | 16 | 7 |

## Pipeline

| Metric | Value |
|---|---|
| Approval precision | 0.5417 |
| Approval recall | 1.0 |
| Approval F1 | 0.7027 |
| **Safety: wrongly auto-resolved** | **0** |
| End-to-end pass rate | 0.65 |
| Failure attribution | {'triage': 8, 'approval-rule': 9, 'retrieval': 4} |

## Application

| Metric | Value |
|---|---|
| Latency p50 (ms) | 2247 |
| Latency p95 (ms) | 2890 |
| Avg tokens/ticket | 809.3 |
| Total tokens | 48558 |
| Requests per key_label | {'OPENAI_API_KEY': 140} |
| LLM error rate | 0.0 |
| Injection tickets approval+priority OK | 3/4 |
| Typo/vague/missing-info category acc | 1.0 |
| Empty description handling | graceful (Other/Unclear + approval) |
| Audit verify_chain | {'valid': True, 'checked': 60, 'first_bad_id': None, 'reason': None} |
| Audit tamper detected | detected |
| Groq cost | free (tokens recorded above) |
| OpenAI cost | estimate, not run |

## Slices

| Slice | Category acc | Priority acc | Team acc | Approval acc |
|---|---|---|---|---|
| difficulty=easy | 0.875 | 0.542 | 0.917 | 0.75 |
| difficulty=medium | 0.95 | 0.7 | 0.85 | 0.8 |
| difficulty=hard | 0.933 | 0.867 | 0.867 | 0.933 |
| edge_type=typo | 1.0 | 0.6 | 1.0 | 0.8 |
| edge_type=vague | 1.0 | 0.75 | 0.75 | 0.75 |
| edge_type=multi-issue | 1.0 | 0.75 | 1.0 | 0.75 |
| edge_type=prompt-injection | 0.75 | 0.75 | 0.75 | 0.75 |
| edge_type=none | 0.879 | 0.545 | 0.849 | 0.818 |

## Top failures

| ID | Stage | Golden -> Predicted | Doc |
|---|---|---|---|
| G-002 | triage | Access/Login/Medium/IT Support/False -> Access/Login/Medium/Service Desk/False | kb-002 vs kb-002,kb-001,kb-003 |
| G-004 | triage | Access/Login/High/Security Team/True -> Other/Unclear/High/Service Desk/True | kb-014 vs none |
| G-005 | triage | Access/Login/Medium/IT Support/False -> Access/Login/Medium/Service Desk/False | kb-002 vs kb-002,kb-001,kb-003 |
| G-008 | triage | Software/Low/IT Support/False -> Access/Login/Medium/Service Desk/False | kb-007 vs kb-014 |
| G-009 | approval-rule | Access/Login/Medium/Service Desk/False -> Access/Login/High/Service Desk/True | kb-001 vs kb-002,kb-001,kb-003 |
| G-018 | retrieval | Software/Low/IT Support/False -> Software/Medium/IT Support/False | none vs kb-006 |
| G-020 | triage | Hardware/High/Service Desk/False -> Hardware/Medium/IT Support/False | kb-009 vs kb-009,kb-013,kb-008 |
| G-021 | retrieval | Security/High/Security Team/True -> Security/High/Security Team/True | kb-013 vs none |
| G-024 | triage | Hardware/Low/Service Desk/False -> Other/Unclear/Medium/Service Desk/True | kb-009 vs none |
| G-025 | retrieval | Security/High/Security Team/True -> Security/High/Security Team/True | kb-013 vs none |
| G-038 | triage | Data/Reports/Medium/Data/Apps Team/False -> Software/Medium/IT Support/False | kb-010 vs none |
| G-039 | approval-rule | Data/Reports/Low/Data/Apps Team/False -> Data/Reports/Medium/Data/Apps Team/True | kb-011 vs kb-011,kb-010 |
| G-041 | triage | Data/Reports/Medium/Data/Apps Team/False -> Access/Login/Medium/Service Desk/True | kb-011 vs kb-014 |
| G-044 | approval-rule | Data/Reports/Low/Data/Apps Team/False -> Data/Reports/High/Data/Apps Team/True | kb-011 vs kb-011 |
| G-045 | approval-rule | Security/Medium/Security Team/False -> Security/Medium/Security Team/True | kb-012 vs kb-012 |

## Findings

- Category accuracy is 0.9167 (macro F1 0.9112); team accuracy 0.8833, priority 0.6667.
- Retrieval hit@3 on golden tickets is 0.9231 (MRR 0.9135).
- Safety: 0 tickets that needed approval were wrongly auto-resolved (approval precision 0.5417, recall 1.0).
- Most failures are attributed to stage 'approval-rule' (9 tickets).
- Hard tickets: category accuracy 0.9333 (15 tickets); 4 wrong categories had confidence >= 0.9.
