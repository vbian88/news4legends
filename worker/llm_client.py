import os
import sys
from pathlib import Path

import requests


DEFAULT_API_URL = "http://127.0.0.1:20128/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/openai/gpt-5-nano"


def get_api_key():
    api_key = os.environ.get("OMNIROUTE_API_KEY")

    if api_key:
        return api_key.strip()

    secret_file = os.environ.get("OMNIROUTE_API_KEY_FILE")

    if secret_file:
        path = Path(secret_file)

        if not path.is_file():
            raise RuntimeError(
                f"OmniRoute API key file does not exist: {path}"
            )

        api_key = path.read_text(
            encoding="utf-8"
        ).strip()

        if api_key:
            return api_key

    raise RuntimeError(
        "OmniRoute API key not found. "
        "Set OMNIROUTE_API_KEY or "
        "OMNIROUTE_API_KEY_FILE."
    )


def ask_llm(prompt):
    api_url = os.environ.get(
        "OMNIROUTE_API_URL",
        DEFAULT_API_URL,
    )

    model = os.environ.get(
        "OMNIROUTE_MODEL",
        DEFAULT_MODEL,
    )

    api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"OmniRoute connection/request error: {exc}"
        ) from exc

    if not response.ok:
        raise RuntimeError(
            f"OmniRoute HTTP {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    return data[
        "choices"
    ][0][
        "message"
    ][
        "content"
    ]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f'Usage: python {sys.argv[0]} '
            '"your prompt here"'
        )
        sys.exit(1)

    prompt = sys.argv[1]

    result = ask_llm(prompt)

    print(result)
