"""Minimal connectivity check: confirms OPENAI_API_KEY / AI_MODEL / OPENAI_BASE_URL
are set correctly by making one small request.

    python -m scripts.temp.check_openai
"""

from dotenv import load_dotenv
from openai import OpenAI

from scripts.vertical_slice import config


def main() -> None:
    load_dotenv()

    model = config.get_model()
    base_url = config.get_base_url()
    print(f"model: {model}")
    print(f"base_url: {base_url or '(default)'}")

    client = OpenAI(api_key=config.get_api_key(), base_url=base_url)
    response = client.responses.create(model=model, input="ping")
    print("output_text:", response.output_text)


if __name__ == "__main__":
    main()
