"""Settings and API-key pool loading (env only, never logs key values)."""
import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

GROQ_LABELS = [f"GROQ_API_KEY_{i}" for i in range(1, 12)]
OPENROUTER_LABELS = [f"OPENROUTER_API_KEY_{i}" for i in range(1, 5)]
# OpenRouter fallback order required by AGENTS.md: 1, 3, 4, then 2.
OPENROUTER_ORDER = [
    "OPENROUTER_API_KEY_1",
    "OPENROUTER_API_KEY_3",
    "OPENROUTER_API_KEY_4",
    "OPENROUTER_API_KEY_2",
]


@dataclass
class Settings:
    """All runtime settings, read from the environment via python-dotenv."""

    llm_provider: str = "groq"
    enable_openrouter: bool = False
    api_base_url: str = "http://127.0.0.1:8000"
    groq_model: str = ""
    openrouter_model: str = ""
    openai_model: str = ""
    confidence_threshold: float = 0.7
    key_cooldown_sec: int = 60
    openai_budget_usd: float = 5.0
    # Rough USD per 1K tokens (prompt+completion) for the OpenAI budget guard.
    openai_price_per_1k_tokens: float = 0.01
    kb_dir: str = "kb"
    kb_min_score: float = 0.25
    chroma_path: str = "data/chroma"
    audit_db_path: str = "data/audit.db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openai_base_url: str = "https://api.openai.com/v1"


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, "") or default))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


def load_settings() -> Settings:
    """Read settings from the environment (loads .env first)."""
    load_dotenv()
    return Settings(
        llm_provider=(os.getenv("LLM_PROVIDER") or "groq").strip().lower(),
        enable_openrouter=_bool("ENABLE_OPENROUTER", False),
        api_base_url=(os.getenv("API_BASE_URL")
                      or "http://127.0.0.1:8000").rstrip("/"),
        groq_model=(os.getenv("GROQ_MODEL") or "").strip(),
        openrouter_model=(os.getenv("OPENROUTER_MODEL") or "").strip(),
        openai_model=(os.getenv("OPENAI_MODEL") or "").strip(),
        confidence_threshold=_float("CONFIDENCE_THRESHOLD", 0.7),
        key_cooldown_sec=_int("GROQ_KEY_COOLDOWN_SEC", 60),
        openai_budget_usd=_float("OPENAI_BUDGET_USD", 5.0),
        openai_price_per_1k_tokens=_float("OPENAI_PRICE_PER_1K_TOKENS", 0.01),
        kb_dir=os.getenv("KB_DIR") or "kb",
        kb_min_score=_float("KB_MIN_SCORE", 0.25),
        chroma_path=os.getenv("CHROMA_PATH") or "data/chroma",
        audit_db_path=os.getenv("AUDIT_DB_PATH") or "data/audit.db",
        embedding_model=os.getenv("EMBEDDING_MODEL")
        or "sentence-transformers/all-MiniLM-L6-v2",
        groq_base_url=(os.getenv("GROQ_BASE_URL") or "").rstrip("/")
        or "https://api.groq.com/openai/v1",
        openrouter_base_url=(os.getenv("OPENROUTER_BASE_URL") or "").rstrip("/")
        or "https://openrouter.ai/api/v1",
    )


def dedupe_keys(pairs):
    """Drop later entries whose key value duplicates an earlier one.

    Warns with labels only — never with key values.
    """
    seen, out = {}, []
    for label, key in pairs:
        if not key:
            continue
        if key in seen:
            logger.warning(
                "Duplicate API key value: %s duplicates %s; keeping %s only",
                label, seen[key], seen[key],
            )
            continue
        seen[key] = label
        out.append((label, key))
    return out


def load_key_pool(env=None, enable_openrouter=None):
    """Load {(provider, label): key} pools, skipping empty/duplicate keys.

    ``env`` may be a mapping for tests; defaults to os.environ (+ .env).
    OpenRouter keys are only loaded when ENABLE_OPENROUTER is true
    (default false); the OpenRouter code paths remain intact.
    """
    if env is None:
        load_dotenv()
        env = os.environ
    if enable_openrouter is None:
        enable_openrouter = (env.get("ENABLE_OPENROUTER") or "").strip().lower() \
            in ("1", "true", "yes", "on")
    get = env.get
    groq = dedupe_keys([(label, (get(label) or "").strip())
                        for label in GROQ_LABELS])
    if enable_openrouter:
        or_pairs = [(label, (get(label) or "").strip())
                    for label in OPENROUTER_ORDER]
        openrouter = dedupe_keys(or_pairs)
    else:
        openrouter = []
    # Keep Groq/OpenRouter pools independent even if a value repeats across them.
    openai = (get("OPENAI_API_KEY") or "").strip()
    return {
        "groq": groq,
        "openrouter": openrouter,
        "openai": [("OPENAI_API_KEY", openai)] if openai else [],
    }
