"""Single LLM interface over Groq/OpenRouter/OpenAI (OpenAI-compatible HTTP).

Model names come from env config; key selection/cooldown via KeyManager.
Never logs or returns full API keys.
"""
import json
import logging
import time

import requests

from .config import load_key_pool, load_settings
from .key_manager import KeyManager

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
JSON_REMINDER = (
    "\n\nIMPORTANT: Reply with ONLY a valid JSON object. No markdown, "
    "no code fences, no extra text."
)

# Running OpenAI spend (USD) for the budget guard; reset_spend() for tests/runs.
_spend_usd = 0.0


class BudgetExceeded(RuntimeError):
    """Raised when the OpenAI budget guard stops a run."""


class LLMError(RuntimeError):
    """Raised when all attempts fail."""


def reset_spend() -> None:
    """Reset the in-process OpenAI spend counter."""
    global _spend_usd
    _spend_usd = 0.0


def _spend() -> float:
    return _spend_usd


def extract_json(text: str) -> dict:
    """Parse JSON from an LLM reply, stripping code fences if present."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def post_chat(base_url, key, model, messages, timeout=30):
    """One chat-completions POST. Split out so tests can mock it."""
    return requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={"model": model, "messages": messages,
              "response_format": {"type": "json_object"}},
        timeout=timeout,
    )


def _attempt(settings, key_manager, system_prompt, user_prompt, ticket_id,
             prev_label=None):
    """Run attempts; return (data, meta). Raises LLMError/BudgetExceeded."""
    global _spend_usd
    use_openai = settings.llm_provider == "openai"
    exclude = prev_label
    last_status = "error"
    for attempt in range(MAX_ATTEMPTS):
        if use_openai:
            picked = key_manager.get_openai_key()
        else:
            picked = key_manager.get_next_key(exclude_label=exclude)
        if picked is None:
            raise LLMError(
                "All Groq keys are in cooldown after 3 waits and no fallback "
                "is available (OpenRouter is disabled unless "
                "ENABLE_OPENROUTER=true)")
        provider, label, key = picked
        model = {"groq": settings.groq_model,
                 "openrouter": settings.openrouter_model,
                 "openai": settings.openai_model}[provider]
        base_url = {"groq": settings.groq_base_url,
                    "openrouter": settings.openrouter_base_url,
                    "openai": settings.openai_base_url}[provider]
        if provider == "openai" and not model:
            raise LLMError("OPENAI_MODEL is not set")
        if provider != "openai" and not model:
            raise LLMError(f"{provider.upper()}_MODEL is not set")
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}]
        t0 = time.perf_counter()
        try:
            resp = post_chat(base_url, key, model, messages)
        except requests.RequestException as exc:
            key_manager.mark_error(label)
            last_status = "network_error"
            logger.warning("LLM call failed (%s ...%s): %s",
                           label, key[-4:], type(exc).__name__)
            exclude = label
            time.sleep(0.5 * (attempt + 1))
            continue
        latency_ms = round((time.perf_counter() - t0) * 1000)
        if resp.status_code == 429:
            key_manager.mark_rate_limited(label)
            last_status = "rate_limited"
            exclude = label
            time.sleep(0.5 * (attempt + 1))
            continue
        if resp.status_code != 200:
            key_manager.mark_error(label)
            last_status = "http_error"
            logger.warning("LLM HTTP %s on %s", resp.status_code, label)
            exclude = label
            time.sleep(0.5 * (attempt + 1))
            continue
        try:
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            key_manager.mark_error(label)
            last_status = "bad_response"
            exclude = label
            logger.warning("Malformed LLM response on %s: %s",
                           label, type(exc).__name__)
            time.sleep(0.5 * (attempt + 1))
            continue
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        # Invalid JSON: retry once with a stricter reminder.
        try:
            data = extract_json(content)
        except (ValueError, TypeError):
            if attempt >= 1:
                raise LLMError("LLM did not return valid JSON after retry")
            logger.warning("Invalid JSON from %s; retrying with reminder", label)
            user_prompt = user_prompt + JSON_REMINDER
            exclude = None  # same key may serve the stricter retry
            continue
        if provider == "openai":
            cost = ((prompt_tokens + completion_tokens) / 1000
                    * settings.openai_price_per_1k_tokens)
            if _spend_usd + cost > settings.openai_budget_usd:
                raise BudgetExceeded(
                    f"OpenAI budget guard: ${ _spend_usd + cost:.4f} would "
                    f"exceed ${settings.openai_budget_usd:.2f}")
            _spend_usd += cost
        meta = {"provider": provider, "key_label": label, "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms, "status": "ok"}
        return data, meta
    raise LLMError(f"LLM call failed after {MAX_ATTEMPTS} attempts "
                   f"(last status: {last_status})")


def complete_json(system_prompt, user_prompt, ticket_id="",
                  settings=None, key_manager=None):
    """Call the LLM and return (parsed_json_dict, call_metadata_dict)."""
    settings = settings or load_settings()
    key_manager = key_manager or KeyManager(
        load_key_pool(enable_openrouter=settings.enable_openrouter),
        cooldown_sec=settings.key_cooldown_sec,
        enable_openrouter=settings.enable_openrouter)
    return _attempt(settings, key_manager, system_prompt, user_prompt,
                    ticket_id)
