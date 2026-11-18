"""Round-robin key manager with 429 cooldown and OpenRouter fallback."""
import time

from .config import OPENROUTER_ORDER


def last4(key: str) -> str:
    """Last 4 chars of a key for safe display (never the full key)."""
    return key[-4:] if len(key) >= 4 else "****"


class KeyManager:
    """Hands out keys round-robin; tracks requests/errors/cooldown per key.

    Groq-only by default: if all Groq keys cool down, wait for the shortest
    remaining cooldown (max ``max_waits`` waits per request) then retry.
    OpenRouter (order 1, 3, 4, 2) is only used when enable_openrouter=True.
    """

    def __init__(self, pool, cooldown_sec: int = 60, clock=time.monotonic,
                 sleep=time.sleep, enable_openrouter: bool = False):
        self.cooldown_sec = cooldown_sec
        self._clock = clock
        self._sleep = sleep
        self.enable_openrouter = enable_openrouter
        # Groq: round-robin in label order. OpenRouter: fixed 1,3,4,2 order.
        self._groq = list(pool.get("groq", []))
        or_by_label = dict(pool.get("openrouter", [])) if enable_openrouter else {}
        self._openrouter = [(label, or_by_label[label])
                            for label in OPENROUTER_ORDER
                            if label in or_by_label]
        self._openai = list(pool.get("openai", []))
        self._groq_idx = 0
        self._or_idx = 0
        self._stats = {}  # label -> {provider, last4, requests, errors, cooldown_until}
        for provider, pairs in (("groq", self._groq),
                                ("openrouter", self._openrouter),
                                ("openai", self._openai)):
            for label, key in pairs:
                self._stats[label] = {"provider": provider, "last4": last4(key),
                                      "requests": 0, "errors": 0,
                                      "cooldown_until": 0.0}

    def _in_cooldown(self, label: str) -> bool:
        return self._clock() < self._stats[label]["cooldown_until"]

    def shortest_cooldown_remaining(self, exclude_label=None):
        """Seconds until the soonest Groq key leaves cooldown, or None."""
        now = self._clock()
        remaining = [s["cooldown_until"] - now
                     for label, s in self._stats.items()
                     if s["provider"] == "groq" and label != exclude_label
                     and s["cooldown_until"] > now]
        return min(remaining) if remaining else None

    def _try_groq(self, exclude_label):
        if not self._groq:
            return None
        for _ in range(len(self._groq)):
            label, key = self._groq[self._groq_idx % len(self._groq)]
            self._groq_idx += 1
            if label == exclude_label or self._in_cooldown(label):
                continue
            self._stats[label]["requests"] += 1
            return "groq", label, key
        return None

    def _try_openrouter(self, exclude_label):
        if not (self.enable_openrouter and self._openrouter):
            return None
        for _ in range(len(self._openrouter)):
            label, key = self._openrouter[self._or_idx % len(self._openrouter)]
            self._or_idx += 1
            if label == exclude_label or self._in_cooldown(label):
                continue
            self._stats[label]["requests"] += 1
            return "openrouter", label, key
        return None

    def get_next_key(self, exclude_label=None, max_waits: int = 3):
        """Return (provider, label, key).

        Groq round-robin first. If every Groq key is cooling down, wait for
        the shortest remaining cooldown (at most ``max_waits`` waits) and
        retry. Only if ENABLE_OPENROUTER is on, fall back to OpenRouter
        (order 1, 3, 4, 2). Returns None when nothing is available.
        """
        waits = 0
        while True:
            picked = self._try_groq(exclude_label)
            if picked:
                return picked
            if self.enable_openrouter:
                picked = self._try_openrouter(exclude_label)
                if picked:
                    return picked
            wait = self.shortest_cooldown_remaining(exclude_label)
            if wait is None or waits >= max_waits:
                return None
            self._sleep(wait)
            waits += 1

    def get_openai_key(self):
        """Return the single OpenAI key entry, or None."""
        if not self._openai:
            return None
        label, key = self._openai[0]
        self._stats[label]["requests"] += 1
        return "openai", label, key

    def mark_rate_limited(self, label: str) -> None:
        """Put a key into cooldown after a 429 and count the error."""
        if label in self._stats:
            self._stats[label]["errors"] += 1
            self._stats[label]["cooldown_until"] = self._clock() + self.cooldown_sec

    def mark_error(self, label: str) -> None:
        """Count a non-429 error for a key."""
        if label in self._stats:
            self._stats[label]["errors"] += 1

    def status(self):
        """Per-key status: labels + last4 only, never full keys."""
        now = self._clock()
        return [
            {"provider": s["provider"], "label": label, "last4": s["last4"],
             "requests": s["requests"], "errors": s["errors"],
             "in_cooldown": now < s["cooldown_until"],
             "cooldown_remaining_sec": max(
                 0, round(s["cooldown_until"] - now, 1))}
            for label, s in self._stats.items()
        ]
