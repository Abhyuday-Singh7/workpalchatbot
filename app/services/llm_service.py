import os
from typing import List, Dict, Any
import json
import requests


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-1.5-flash:generateContent"
)


def _call_local_http(messages: List[Dict[str, Any]], model: str = "mistral") -> str:
    """
    Call a locally-hosted Mistral (or compatible) HTTP inference endpoint.

    Expected behaviour:
      - The local endpoint URL must be set in `LOCAL_MISTRAL_URL` environment var.
      - This function posts JSON with `model` and `messages` keys and expects
        a JSON response similar to OpenRouter: either
          {"choices": [{"message": {"content": "..."}}]}
        or a single-text field like {"text": "..."}.

    This keeps the integration flexible for different local servers.
    """
    # url = os.getenv("LOCAL_MISTRAL_URL")
    url = "http://localhost:11434/api/generate"
    if not url:
        raise RuntimeError(
            "LOCAL_MISTRAL_URL is not set. Set it to your local Mistral HTTP endpoint."
        )

    payload = {"model": model, "messages": messages}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    # response.raise_for_status()
    # data = response.json()

    # Try OpenRouter-like shape first
    try:
        info = "hello"
        for chunk in response.iter_lines():
            if chunk:
                data = json.loads(chunk.decode())
                info += data.get("response", "")
        return info
    except Exception as e:
        return f"Error processing response: {e}"
    # try:
    #     return data["choices"][0]["message"]["content"]
    # except Exception:
    #     # Fallbacks for other local server shapes
    #     if isinstance(data, dict):
    #         for key in ("text", "response", "output", "result"):
    #             if key in data and isinstance(data[key], str):
    #                 return data[key]
    #         # Some servers return a top-level candidate list
    #         try:
    #             return data["candidates"][0]["content"]["parts"][0]["text"]
    #         except Exception:
    #             pass

    # raise RuntimeError("Unexpected response shape from local LLM endpoint.")


def _call_openrouter(
    messages: List[Dict[str, Any]],
    model: str = "mistralai/mistral-7b-instruct",
) -> str:
    # api_key = os.getenv("OPENROUTER_API_KEY")
    api_key = "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"
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env or environment, or switch LLM_PROVIDER to 'gemini'."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "WorkPal Backend",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("Unexpected response from OpenRouter LLM API.")


def _call_gemini(messages: List[Dict[str, Any]]) -> str:
    """
    Call Google Gemini (Generative Language API) using a simple text prompt
    constructed from the chat messages.

    The API key is read from GEMINI_API_KEY or OPENROUTER_API_KEY for
    convenience if you reused that variable.
    """
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GENAI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY (or GENAI_API_KEY) is not set. Please add your Gemini key to the environment."
        )

    # Flatten chat-style messages into a single text prompt
    parts = []
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        parts.append(f"{role}: {content}")
    text = "\n\n".join(parts)

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text,
                    }
                ]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.post(
        GEMINI_API_URL,
        params={"key": api_key},
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("Unexpected response from Gemini API.")


def call_llm(messages: List[Dict[str, Any]], model: str = "mistralai/mistral-7b-instruct") -> str:
    """
    Call the configured LLM provider.

    LLM_PROVIDER environment variable controls which provider is used:
      - 'openrouter' (default): use OpenRouter Chat Completions API.
      - 'gemini': use Google Gemini Generative Language API.
    """
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    if provider == "gemini":
        return _call_gemini(messages)
    if provider == "local":
        return _call_local_http(messages, model=model)
    # default / fallback: openrouter
    return _call_openrouter(messages, model=model)
