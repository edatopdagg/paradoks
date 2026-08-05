import requests

from app.core.config import (
    OLLAMA_CHAT_URL,
    OLLAMA_MODEL_NAME,
    OLLAMA_TIMEOUT_SECONDS,
)


class OllamaServiceError(RuntimeError):
    """Ollama servisiyle iletişim sırasında oluşan kontrollü hata."""


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

    try:
        response = requests.post(
            OLLAMA_CHAT_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

    except requests.Timeout as error:
        raise OllamaServiceError(
            "Ollama modeli belirtilen süre içinde yanıt vermedi."
        ) from error

    except requests.ConnectionError as error:
        raise OllamaServiceError(
            "Ollama servisine bağlanılamadı. "
            "Ollama'nın çalıştığından emin olun."
        ) from error

    except requests.HTTPError as error:
        raise OllamaServiceError(
            "Ollama API bir HTTP hatası döndürdü: "
            f"{response.status_code}"
        ) from error

    except requests.RequestException as error:
        raise OllamaServiceError(
            "Ollama isteği sırasında beklenmeyen bir bağlantı hatası oluştu."
        ) from error

    try:
        response_data = response.json()
        content = response_data["message"]["content"].strip()

    except (ValueError, KeyError, TypeError) as error:
        raise OllamaServiceError(
            "Ollama geçersiz bir cevap biçimi döndürdü."
        ) from error

    if not content:
        raise OllamaServiceError(
            "Ollama boş bir cevap döndürdü."
        )

    return content