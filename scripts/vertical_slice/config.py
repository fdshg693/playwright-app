import os

DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_MAX_SESSIONS = 5
DEFAULT_IDLE_SESSION_TIMEOUT_SECONDS = 1800.0


def get_model() -> str:
    return os.environ.get("AI_MODEL", DEFAULT_MODEL)


def get_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Put it in a .env file or export it before running."
        )
    return api_key


def get_base_url() -> str | None:
    return os.environ.get("OPENAI_BASE_URL")


def get_allowed_domains() -> list[str] | None:
    """Comma-separated ALLOWED_DOMAINS (e.g. "localhost,*.example.com"). Unset
    or empty means unrestricted (None) -- unlike get_max_sessions/
    get_idle_timeout_seconds, this guardrail defaults to off (opt-in), so the
    existing demo stories (scripts/stories/*.yaml) keep working without any
    new environment variable (plan/main/08-safety-guardrails.md decision table).
    """
    raw = os.environ.get("ALLOWED_DOMAINS")
    if not raw or not raw.strip():
        return None
    return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]


def get_max_sessions() -> int:
    return int(os.environ.get("MAX_CONCURRENT_SESSIONS", DEFAULT_MAX_SESSIONS))


def get_idle_timeout_seconds() -> float:
    return float(os.environ.get("IDLE_SESSION_TIMEOUT_SECONDS", DEFAULT_IDLE_SESSION_TIMEOUT_SECONDS))
