# TicketPilot Eval Report

Run ID: `20261108-143141`  |  Date: 2026-11-08T14:31:41.155166+00:00  |  Provider: groq  |  Model: openai/gpt-oss-120b  |  Tickets: 60

## Component

| Metric | Value |
|---|---|
| Retrieval questions hit@1 | 1.0 |
| Retrieval questions hit@3 | 1.0 |
| Retrieval questions MRR | 1.0 |
| Retrieval none correct | 5/5 |
| Golden retrieval hit@1 | 0.8269 |
| Golden retrieval hit@3 | 0.8462 |
| Golden retrieval MRR | 0.8365 |
| Golden none correct | 7/8 |
| Category accuracy | 0.9333 |
| Priority accuracy | 0.6333 |
| Team accuracy | 0.8667 |
| Category macro F1 | 0.9353 |
| Generation doc rate | 0.8077 |
| Generation none rate | 0.75 |
| Judge mean score | 4.433 |

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
| Software | 0 | 10 | 0 | 0 | 0 | 0 | 0 |
| Hardware | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| Network/VPN | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| Data/Reports | 2 | 1 | 0 | 0 | 6 | 0 | 0 |
| Security | 1 | 0 | 0 | 0 | 0 | 10 | 0 |
| Other/Unclear | 0 | 0 | 0 | 0 | 0 | 0 | 6 |

Priority confusion matrix (golden -> predicted):

| golden \ pred | High | Medium | Low |
|---|---|---|---|
| High | 8 | 2 | 1 |
| Medium | 5 | 12 | 8 |
| Low | 1 | 5 | 18 |

## Pipeline

| Metric | Value |
|---|---|
| Approval precision | 0.4783 |
| Approval recall | 0.8462 |
| Approval F1 | 0.6111 |
| **Safety: wrongly auto-resolved** | **2** |
| End-to-end pass rate | 0.6 |
| Failure attribution | {'approval-rule': 7, 'triage': 10, 'retrieval': 7} |

## Application

| Metric | Value |
|---|---|
| Latency p50 (ms) | 948 |
| Latency p95 (ms) | 1251 |
| Avg tokens/ticket | 677.6 |
| Total tokens | 40655 |
| Requests per key_label | {'GROQ_API_KEY_1': 14, 'GROQ_API_KEY_2': 14, 'GROQ_API_KEY_3': 14, 'GROQ_API_KEY_5': 14, 'GROQ_API_KEY_6': 14, 'GROQ_API_KEY_7': 14, 'GROQ_API_KEY_8': 14, 'GROQ_API_KEY_9': 13, 'GROQ_API_KEY_10': 13, 'GROQ_API_KEY_11': 13} |
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
| difficulty=easy | 0.875 | 0.667 | 0.875 | 0.833 |
| difficulty=medium | 1.0 | 0.6 | 0.9 | 0.7 |
| difficulty=hard | 0.933 | 0.6 | 0.8 | 0.8 |
| edge_type=typo | 1.0 | 0.6 | 0.8 | 1.0 |
| edge_type=vague | 1.0 | 0.25 | 0.75 | 0.75 |
| edge_type=multi-issue | 1.0 | 0.25 | 1.0 | 1.0 |
| edge_type=prompt-injection | 1.0 | 0.75 | 0.75 | 0.75 |
| edge_type=none | 0.909 | 0.636 | 0.879 | 0.697 |

## Top failures

| ID | Stage | Golden -> Predicted | Doc |
|---|---|---|---|
| G-001 | approval-rule | Access/Login/Medium/Service Desk/False -> Access/Login/Low/Service Desk/True | kb-001 vs kb-001,kb-003,kb-002 |
| G-002 | triage | Access/Login/Medium/IT Support/False -> Access/Login/Medium/Service Desk/True | kb-002 vs kb-002,kb-001,kb-003 |
| G-004 | triage | Access/Login/High/Security Team/True -> Access/Login/High/Service Desk/True | kb-014 vs kb-014,kb-001 |
| G-005 | triage | Access/Login/Medium/IT Support/False -> Access/Login/Low/Service Desk/True | kb-002 vs kb-002,kb-001,kb-003 |
| G-010 | retrieval | Software/Low/IT Support/False -> Software/Low/IT Support/False | kb-006 vs none |
| G-012 | approval-rule | Software/High/IT Support/False -> Software/High/IT Support/True | kb-006 vs kb-006,kb-007 |
| G-014 | retrieval | Software/Low/IT Support/False -> Software/Low/IT Support/False | kb-006 vs none |
| G-017 | triage | Software/Low/IT Support/False -> Software/Low/Service Desk/False | kb-006 vs none |
| G-018 | retrieval | Software/Low/IT Support/False -> Software/Low/IT Support/False | none vs kb-006 |
| G-020 | triage | Hardware/High/Service Desk/False -> Hardware/Low/IT Support/False | kb-009 vs kb-009 |
| G-021 | triage | Security/High/Security Team/True -> Access/Login/High/Service Desk/True | kb-013 vs kb-002 |
| G-024 | triage | Hardware/Low/Service Desk/False -> Hardware/Low/IT Support/False | kb-009 vs kb-009 |
| G-025 | retrieval | Security/High/Security Team/True -> Security/High/Security Team/False | kb-013 vs none |
| G-036 | approval-rule | Data/Reports/Medium/Data/Apps Team/False -> Data/Reports/Low/Data/Apps Team/True | kb-010 vs kb-010 |
| G-038 | triage | Data/Reports/Medium/Data/Apps Team/False -> Software/High/IT Support/False | kb-010 vs none |

## Findings

- Category accuracy is 0.9333 (macro F1 0.9353); team accuracy 0.8667, priority 0.6333.
- Retrieval hit@3 on golden tickets is 0.8462 (MRR 0.8365).
- Safety: 2 tickets that needed approval were wrongly auto-resolved (approval precision 0.4783, recall 0.8462).
- Most failures are attributed to stage 'triage' (10 tickets).
- Hard tickets: category accuracy 0.9333 (15 tickets); 4 wrong categories had confidence >= 0.9.
