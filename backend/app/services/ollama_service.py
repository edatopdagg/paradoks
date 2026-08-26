import requests

from app.core.config import (
    OLLAMA_CHAT_URL,
    OLLAMA_MODEL_NAME,
    OLLAMA_TIMEOUT_SECONDS,
)


class OllamaServiceError(RuntimeError):
    """Ollama servisiyle iletişim sırasında oluşan kontrollü hata."""


def _ns_to_seconds(
    value: int | float | None,
) -> float:
    """
    Ollama duration değerleri nanosecond olarak gelir.
    Saniyeye çevirir.
    """

    if not value:
        return 0.0

    return float(value) / 1_000_000_000


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

        # Model istekler arasında RAM'de kalsın.
        "keep_alive": "30m",

        "options": {
            "temperature": 0.0,
            "num_predict": 1024,
            "num_ctx": 4096,
            "repeat_penalty": 1.15,
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

        content = (
            response_data[
                "message"
            ][
                "content"
            ]
            .strip()
        )

    except (
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        raise OllamaServiceError(
            "Ollama geçersiz bir cevap biçimi döndürdü."
        ) from error

    if not content:
        raise OllamaServiceError(
            "Ollama boş bir cevap döndürdü."
        )

    # ---------------------------------------------------------
    # OLLAMA DETAYLI PERFORMANS
    # ---------------------------------------------------------

    total_duration = _ns_to_seconds(
        response_data.get(
            "total_duration"
        )
    )

    load_duration = _ns_to_seconds(
        response_data.get(
            "load_duration"
        )
    )

    prompt_eval_duration = _ns_to_seconds(
        response_data.get(
            "prompt_eval_duration"
        )
    )

    eval_duration = _ns_to_seconds(
        response_data.get(
            "eval_duration"
        )
    )

    prompt_eval_count = int(
        response_data.get(
            "prompt_eval_count"
        )
        or 0
    )

    eval_count = int(
        response_data.get(
            "eval_count"
        )
        or 0
    )

    tokens_per_second = (
        eval_count / eval_duration
        if eval_duration > 0
        else 0.0
    )

    print()
    print("=" * 50)
    print("[OLLAMA PERF]")

    print(
        f"[OLLAMA] Model load: "
        f"{load_duration:.2f} sn"
    )

    print(
        f"[OLLAMA] Prompt token: "
        f"{prompt_eval_count}"
    )

    print(
        f"[OLLAMA] Prompt processing: "
        f"{prompt_eval_duration:.2f} sn"
    )

    print(
        f"[OLLAMA] Output token: "
        f"{eval_count}"
    )

    print(
        f"[OLLAMA] Generation: "
        f"{eval_duration:.2f} sn"
    )

    print(
        f"[OLLAMA] Generation hizi: "
        f"{tokens_per_second:.2f} token/sn"
    )

    print(
        f"[OLLAMA] Ollama total: "
        f"{total_duration:.2f} sn"
    )

    print("=" * 50)
    print()

    return content