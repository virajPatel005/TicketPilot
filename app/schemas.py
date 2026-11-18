"""Pydantic v2 schemas for ticket input and LLM triage output."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["Access/Login", "Software", "Hardware", "Network/VPN",
                   "Data/Reports", "Security", "Other/Unclear"]
Priority = Literal["High", "Medium", "Low"]
Team = Literal["Service Desk", "IT Support", "Network Team", "Security Team",
               "Data/Apps Team"]
Sensitivity = Literal["normal", "access-related", "security-incident",
                      "trial-data-related"]


class TicketIn(BaseModel):
    """Incoming ticket from the API caller."""

    ticket_id: str = Field(max_length=100)
    subject: str = Field(max_length=200)
    description: str = Field(max_length=5000)
    department: Optional[str] = Field(default=None, max_length=100)
    channel: Optional[str] = Field(default=None, max_length=50)
    affected_system: Optional[str] = Field(default=None, max_length=100)
    business_impact: Optional[str] = Field(default=None, max_length=200)


class TriageOut(BaseModel):
    """LLM triage result; needs_human_approval is re-enforced in code."""

    category: Category
    sub_category: str = Field(max_length=100)
    priority: Priority
    team: Team
    sensitivity: Sensitivity
    confidence: float = Field(ge=0, le=1)
    needs_human_approval: bool
    reason: str = Field(max_length=300)


class CallMeta(BaseModel):
    """Metadata recorded for every LLM call (no keys, no ticket text)."""

    provider: str
    key_label: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    status: str


class SuggestedFix(BaseModel):
    """RAG fix suggestion (Stage 3)."""

    answer: str
    doc_ids: list[str] = []
    found: bool


class TriageResponse(BaseModel):
    """POST /triage response: triage result plus call metadata."""

    ticket_id: str
    triage: TriageOut
    meta: CallMeta
    suggested_fix: SuggestedFix
    audit_id: int
    status: str  # auto_resolved | pending_approval


class DecisionIn(BaseModel):
    """POST /approvals/{ticket_id}/decision body."""

    approver: str
    decision: Literal["approve", "reject"]
    note: str = ""
