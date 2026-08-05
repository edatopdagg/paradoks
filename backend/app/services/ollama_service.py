import requests

from app.core.config import (
    OLLAMA_CHAT_URL,
    OLLAMA_MODEL_NAME,
    OLLAMA_TIMEOUT_SECONDS,
)


def generate_with_ollama(
    system_prompt: str,
    user_prompt: str,
) -> str:
    payload = {
        "model": OLLAMA_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "stream": False,
        "think": False,
        "options": {
          "temperature": 0.0,
          "num_predict": 256,
          "num_ctx": 4096,
          },
    }

    response = requests.post(
        OLLAMA_CHAT_URL,
        json=payload,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    response_data = response.json()
    return response_data["message"]["content"].strip()