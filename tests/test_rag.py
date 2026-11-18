"""RAG tests: mocked LLM + retrieval, never invents a fix."""
from app.rag import suggest_fix
from app.schemas import TicketIn, TriageOut

TRIAGE = TriageOut(category="Network/VPN", sub_category="VPN",
                   priority="Medium", team="Network Team",
                   sensitivity="normal", confidence=0.9,
                   needs_human_approval=False, reason="vpn")


def ticket():
    return TicketIn(ticket_id="T1", subject="VPN down",
                    description="Cannot connect to VPN.")


def test_rag_uses_only_retrieved_docs():
    docs = [{"doc_id": "kb-004", "title": "VPN troubleshooting",
             "score": 0.9, "snippet": "Steps: restart the VPN client."}]

    def fake_complete(system, user, ticket_id="", settings=None,
                      key_manager=None):
        assert "restart the VPN client" in user  # doc text reached the LLM
        return {"answer": "Restart the VPN client."}, {"status": "ok"}

    out = suggest_fix(ticket(), TRIAGE, retrieve_fn=lambda *a, **k: docs,
                      complete=fake_complete)
    assert out == {"answer": "Restart the VPN client.",
                   "doc_ids": ["kb-004"], "found": True}


def test_rag_never_answers_without_a_match():
    def boom(*a, **k):
        raise AssertionError("LLM must not be called without a match")

    out = suggest_fix(ticket(), TRIAGE, retrieve_fn=lambda *a, **k: [],
                      complete=boom)
    assert out["found"] is False
    assert out["doc_ids"] == []
    assert out["answer"] == ("No matching help article found. Routing to "
                             "Network Team for review.")


def test_admin_policy_fallback_when_llm_declines():
    # LLM declines, but kb-014 matched: code must return the doc's own
    # Steps/When-to-escalate sections with found=true.
    docs = [{"doc_id": "kb-014", "title": "Admin access policy",
             "score": 0.9, "snippet": "Admin access needs approval."}]

    def decline(system, user, ticket_id="", settings=None, key_manager=None):
        assert "POLICIES" in system
        return {"answer": "No matching help article found."}, {"status": "ok"}

    ticket = TicketIn(ticket_id="T9", subject="Admin access",
                      description="Need admin access to trial database.")
    triage = TRIAGE.model_copy(update={"category": "Access/Login",
                                       "team": "Security Team"})
    out = suggest_fix(ticket, triage, retrieve_fn=lambda *a, **k: docs,
                      complete=decline)
    assert out["found"] is True
    assert out["doc_ids"] == ["kb-014"]
    assert "manager" in out["answer"].lower()  # from the doc's own steps
    assert "When to escalate" in out["answer"]


def test_other_unclassified_skips_retrieval():
    triage = TRIAGE.model_copy(update={"category": "Other/Unclear",
                                       "team": "Service Desk"})

    def boom(*a, **k):
        raise AssertionError("retrieval must be skipped for Other/Unclear")

    out = suggest_fix(ticket(), triage, retrieve_fn=boom, complete=boom)
    assert out == {"answer": "Not an IT request. Routing to Service Desk "
                             "for review.",
                   "doc_ids": [], "found": False}


def test_rag_lunch_menu_not_found():
    lunch = TicketIn(ticket_id="T2", subject="Lunch",
                     description="What is the lunch menu?")
    triage = TRIAGE.model_copy(update={"category": "Other/Unclear",
                                       "team": "Service Desk"})
    out = suggest_fix(lunch, triage, retrieve_fn=lambda *a, **k: [],
                      complete=lambda *a, **k: (_ for _ in ()).throw(
                          AssertionError("no LLM call")))
    assert out["found"] is False
