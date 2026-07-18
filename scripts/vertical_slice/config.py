import os

DEFAULT_MODEL = "gpt-5.6-luna"


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
