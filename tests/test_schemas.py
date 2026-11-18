"""Schema tests: invalid category/confidence must be rejected."""
import pytest
from pydantic import ValidationError

from app.schemas import TicketIn, TriageOut

VALID = {"category": "Software", "sub_category": "license", "priority": "Low",
         "team": "IT Support", "sensitivity": "normal", "confidence": 0.9,
         "needs_human_approval": False, "reason": "ok"}


def test_valid_triage_out():
    assert TriageOut(**VALID).confidence == 0.9


def test_invalid_category_rejected():
    with pytest.raises(ValidationError):
        TriageOut(**{**VALID, "category": "NotARealCategory"})


def test_confidence_out_of_range_rejected():
    for bad in (-0.1, 1.5):
        with pytest.raises(ValidationError):
            TriageOut(**{**VALID, "confidence": bad})


def test_ticket_in_optional_fields_default_none():
    t = TicketIn(ticket_id="T1", subject="s", description="d")
    assert t.department is None and t.business_impact is None


def test_subject_over_max_length_rejected():
    with pytest.raises(ValidationError):
        TicketIn(ticket_id="T1", subject="x" * 201, description="d")


def test_description_over_max_length_rejected():
    with pytest.raises(ValidationError):
        TicketIn(ticket_id="T1", subject="s", description="x" * 5001)


def test_reason_over_max_length_rejected():
    with pytest.raises(ValidationError):
        TriageOut(**{**VALID, "reason": "x" * 301})


def test_at_max_length_is_accepted():
    t = TicketIn(ticket_id="T1", subject="x" * 200, description="x" * 5000)
    assert len(t.subject) == 200 and len(t.description) == 5000
