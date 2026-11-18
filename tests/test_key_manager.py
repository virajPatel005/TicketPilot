"""Key manager tests: round-robin, cooldown, fallback order, dedupe."""
import time

from app.config import dedupe_keys, load_key_pool
from app.key_manager import KeyManager


def pool():
    return {
        "groq": [("GROQ_API_KEY_1", "g1-aaaa"), ("GROQ_API_KEY_2", "g2-bbbb"),
                 ("GROQ_API_KEY_3", "g3-cccc")],
        "openrouter": [("OPENROUTER_API_KEY_1", "o1-1111"),
                       ("OPENROUTER_API_KEY_2", "o2-2222"),
                       ("OPENROUTER_API_KEY_3", "o3-3333"),
                       ("OPENROUTER_API_KEY_4", "o4-4444")],
        "openai": [],
    }


def test_round_robin_order():
    km = KeyManager(pool(), cooldown_sec=60)
    labels = [km.get_next_key()[1] for _ in range(4)]
    assert labels == ["GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
                      "GROQ_API_KEY_1"]


def test_cooldown_after_429_skips_key():
    km = KeyManager(pool(), cooldown_sec=60)
    first = km.get_next_key()[1]
    km.mark_rate_limited(first)
    nxt = km.get_next_key()[1]
    assert nxt != first
    st = {s["label"]: s for s in km.status()}
    assert st[first]["in_cooldown"] is True
    assert st[first]["errors"] == 1


def test_groq_only_by_default_openrouter_never_used():
    km = KeyManager(pool(), cooldown_sec=60)  # enable_openrouter=False
    for label, _ in pool()["groq"]:
        km.mark_rate_limited(label)
    slept = []
    km._sleep = lambda s: slept.append(s)
    assert km.get_next_key() is None
    assert len(slept) == 3  # max 3 waits, then gives up
    providers = {s["provider"] for s in km.status()}
    assert "openrouter" not in providers


def test_wait_and_retry_after_shortest_cooldown():
    now = [0.0]
    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)
        now[0] += seconds  # sleeping advances time past the cooldown

    km = KeyManager(pool(), cooldown_sec=30, clock=lambda: now[0],
                    sleep=fake_sleep)
    for label, _ in pool()["groq"]:
        km.mark_rate_limited(label)
    picked = km.get_next_key()
    assert picked[0] == "groq"
    assert slept == [30.0]  # waited exactly the shortest remaining cooldown


def test_openrouter_fallback_only_when_enabled_order_1_3_4_2():
    km = KeyManager(pool(), cooldown_sec=60, enable_openrouter=True,
                    sleep=lambda s: None)  # mocked sleep: no real waiting
    for label, _ in pool()["groq"]:
        km.mark_rate_limited(label)
    order = [km.get_next_key()[1] for _ in range(4)]
    assert order == ["OPENROUTER_API_KEY_1", "OPENROUTER_API_KEY_3",
                     "OPENROUTER_API_KEY_4", "OPENROUTER_API_KEY_2"]
    for label in order:
        km.mark_rate_limited(label)
    assert km.get_next_key() is None  # everything cooling down


def test_cooldown_expires():
    now = [1000.0]
    km = KeyManager(pool(), cooldown_sec=10, clock=lambda: now[0])
    label = km.get_next_key()[1]
    km.mark_rate_limited(label)
    now[0] += 11
    st = {s["label"]: s for s in km.status()}
    assert st[label]["in_cooldown"] is False


def test_duplicate_key_removal_keeps_first_and_warns(caplog):
    pool_env = {"GROQ_API_KEY_1": "same-value", "GROQ_API_KEY_2": "same-value",
                "GROQ_API_KEY_3": "other-value"}
    from app import config
    pairs = [(f"GROQ_API_KEY_{i}", pool_env.get(f"GROQ_API_KEY_{i}", ""))
             for i in (1, 2, 3)]
    with caplog.at_level("WARNING", logger="app.config"):
        deduped = dedupe_keys(pairs)
    assert deduped == [("GROQ_API_KEY_1", "same-value"),
                       ("GROQ_API_KEY_3", "other-value")]
    # Warned with labels only: the full value must not appear in the log.
    assert "GROQ_API_KEY_2" in caplog.text
    assert "same-value" not in caplog.text


def test_load_key_pool_skips_empty_and_dedupes():
    env = {"GROQ_API_KEY_1": "k1", "GROQ_API_KEY_2": "k1",
           "GROQ_API_KEY_3": "", "OPENROUTER_API_KEY_1": "o1"}
    loaded = load_key_pool(env={**env})
    assert loaded["groq"] == [("GROQ_API_KEY_1", "k1")]
    assert loaded["openrouter"] == []  # disabled by default


def test_load_key_pool_openrouter_only_when_enabled():
    env = {"GROQ_API_KEY_1": "k1", "OPENROUTER_API_KEY_2": "o2",
           "OPENROUTER_API_KEY_1": "o1", "ENABLE_OPENROUTER": "true"}
    loaded = load_key_pool(env=env)
    # Fallback order 1, 3, 4, 2 is preserved in the pool.
    assert loaded["openrouter"] == [("OPENROUTER_API_KEY_1", "o1"),
                                    ("OPENROUTER_API_KEY_2", "o2")]
