"""AI client — Cohere (primary) → OpenRouter → Gemini → Groq."""
import re
import time
import requests as _requests
from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = [
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]


def _ask_cohere(prompt: str) -> str:
    resp = _requests.post(
        "https://api.cohere.com/v2/chat",
        headers={
            "Authorization": f"Bearer {settings.cohere_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "command-r-plus-08-2024",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=60,
    )
    if resp.status_code == 429:
        raise RuntimeError("Cohere rate limited")
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"][0]["text"]


def _ask_openrouter(prompt: str) -> str:
    for model in OPENROUTER_MODELS:
        try:
            resp = _requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                print(f"  [OpenRouter 429] {model} rate limited, trying next...")
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [OpenRouter error on {model}] {e}")
            continue
    raise RuntimeError("All OpenRouter models rate limited")


def _parse_retry_delay(error_msg: str, default: int = 65) -> int:
    match = re.search(r'retry in (\d+)', error_msg)
    return int(match.group(1)) + 2 if match else default


def _ask_gemini(prompt: str, retries: int = 3) -> str:
    from google import genai as _genai
    client = _genai.Client(api_key=settings.gemini_api_key)
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            msg = str(e)
            if "429" in msg and "PerDay" in msg:
                raise
            if attempt >= retries - 1:
                raise
            if "503" in msg:
                wait = 10 * (attempt + 1)
                print(f"  [Gemini 503] retrying in {wait}s...")
                time.sleep(wait)
            elif "429" in msg:
                wait = _parse_retry_delay(msg)
                print(f"  [Gemini rate limit] waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def ask_ai(prompt: str) -> str:
    """Send a prompt to the best available AI. Returns the response text."""
    if settings.cohere_api_key:
        try:
            return _ask_cohere(prompt)
        except Exception as e:
            print(f"  [Cohere error] {e}")

    if settings.openrouter_api_key:
        try:
            return _ask_openrouter(prompt)
        except Exception as e:
            print(f"  [OpenRouter error] {e}")

    if settings.gemini_api_key:
        try:
            return _ask_gemini(prompt)
        except Exception as e:
            msg = str(e)
            if "429" in msg and "Day" in msg:
                pass
            else:
                print(f"  [Gemini error] {e}")

    if settings.groq_api_key:
        try:
            resp = _requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [Groq error] {e}")

    raise RuntimeError("No AI API key configured.")
