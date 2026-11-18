"""LLM client tests: JSON retry and OpenAI budget guard (mocked HTTP)."""
import pytest

from app import llm_client
from app.config import Settings
from app.key_manager import KeyManager

GOOD_JSON = ('{"category": "Software", "sub_category": "license", '
             '"priority": "Low", "team": "IT Support", "sensitivity": '
             '"normal", "confidence": 0.9, "needs_human_approval": false, '
             '"reason": "ok"}')


class FakeResp:
    def __init__(self, status_code=200, content=GOOD_JSON, usage=None):
        self.status_code = status_code
        self._content = content
        self._usage = usage or {"prompt_tokens": 10, "completion_tokens": 5}

    def json(self):
        return {"choices": [{"message": {"content": self._content}}],
                "usage": self._usage}


def make_km():
    return KeyManager({"groq": [("GROQ_API_KEY_1", "g1-aaaa")],
                       "openrouter": [], "openai": []})


def make_settings(**kw):
    base = {"groq_model": "m", "openrouter_model": "m2", "openai_model": "m3"}
    return Settings(**{**base, **kw})


def test_retries_on_bad_json_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_post(base_url, key, model, messages, timeout=30):
        calls["n"] += 1
        return FakeResp(content="not json at all" if calls["n"] == 1
                        else GOOD_JSON)

    monkeypatch.setattr(llm_client, "post_chat", fake_post)
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    data, meta = llm_client.complete_json(
        "sys", "user", settings=make_settings(), key_manager=make_km())
    assert data["category"] == "Software"
    assert calls["n"] == 2
    assert meta["status"] == "ok" and meta["key_label"] == "GROQ_API_KEY_1"


def test_429_marks_key_and_retries(monkeypatch):
    km = KeyManager({"groq": [("GROQ_API_KEY_1", "g1-aaaa"),
                              ("GROQ_API_KEY_2", "g2-bbbb")],
                     "openrouter": [], "openai": []})
    responses = iter([FakeResp(status_code=429), FakeResp()])
    monkeypatch.setattr(llm_client, "post_chat",
                        lambda *a, **k: next(responses))
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    data, meta = llm_client.complete_json(
        "sys", "user", settings=make_settings(), key_manager=km)
    assert meta["key_label"] == "GROQ_API_KEY_2"
    st = {s["label"]: s for s in km.status()}
    assert st["GROQ_API_KEY_1"]["in_cooldown"] is True


def test_all_groq_cooldown_raises_clear_error(monkeypatch):
    km = KeyManager({"groq": [("GROQ_API_KEY_1", "g1-aaaa")],
                     "openrouter": [("OPENROUTER_API_KEY_1", "o1-1111")],
                     "openai": []}, cooldown_sec=60, sleep=lambda s: None)
    km.mark_rate_limited("GROQ_API_KEY_1")
    with pytest.raises(llm_client.LLMError, match="in cooldown"):
        llm_client.complete_json("sys", "user",
                                 settings=make_settings(), key_manager=km)


def test_budget_guard_stops_openai_run(monkeypatch):
    km = KeyManager({"groq": [], "openrouter": [],
                     "openai": [("OPENAI_API_KEY", "sk-aaaa")]})
    monkeypatch.setattr(llm_client, "post_chat",
                        lambda *a, **k: FakeResp())
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    llm_client.reset_spend()
    settings = make_settings(llm_provider="openai",
                             openai_budget_usd=0.0001)  # ~15 tokens costs more
    with pytest.raises(llm_client.BudgetExceeded):
        llm_client.complete_json("sys", "user", settings=settings,
                                 key_manager=km)
    assert llm_client._spend() == 0.0  # nothing spent past the guard


def test_budget_guard_allows_small_spend(monkeypatch):
    km = KeyManager({"groq": [], "openrouter": [],
                     "openai": [("OPENAI_API_KEY", "sk-aaaa")]})
    monkeypatch.setattr(llm_client, "post_chat",
                        lambda *a, **k: FakeResp())
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    llm_client.reset_spend()
    settings = make_settings(llm_provider="openai", openai_budget_usd=10.0)
    data, meta = llm_client.complete_json(
        "sys", "user", settings=settings, key_manager=km)
    assert meta["provider"] == "openai"
    assert llm_client._spend() > 0
