import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_SECONDS = 30


class GeminiError(Exception):
    """Custom exception for Gemini API errors."""


class GeminiRateLimitError(GeminiError):
    """Exception raised for rate limit errors from the Gemini API."""


def get_api_key() -> str:
    """Retrieve the Gemini API key from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY not found in environment variables.")
    return api_key


def extract_text(data: dict) -> str:
    """Extract the model's text from the Gemini API response."""
    for step in data.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for part in step.get("content", []):
            if part.get("type") == "text":
                return str(part["text"])
    raise GeminiError("No text found in the response.")


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def consume_gemini_api(prompt: str, api_key: str, model: str = DEFAULT_MODEL) -> str:
    """Consume the Gemini API with the given prompt and model and respond with the extracted text."""
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {"model": model, "input": prompt}

    start = time.perf_counter()
    try:
        response = requests.post(
            API_URL, headers=headers, json=payload, timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except requests.Timeout as err:
        raise GeminiError(f"Request timed out: {err}") from err
    except requests.ConnectionError as err:
        raise GeminiError(
            "It's not possible to connect to the Gemini API. Check your internet connection."
        ) from err
    except requests.HTTPError as err:
        status_code = response.status_code
        if status_code == 429:
            raise GeminiRateLimitError(
                "Rate limit exceeded. Please try again later."
            ) from err
        logger.error(
            "Gemini HTTP %s after %d ms: %s",
            status_code,
            _elapsed_ms(start),
            response.text[:200],
        )
        raise GeminiError(f"Gemini responded with HTTP {status_code}.") from err
    except requests.RequestException as err:
        raise GeminiError(f"Network error occurred: {err}") from err

    try:
        data = response.json()
    except ValueError as err:
        raise GeminiError("Failed to parse JSON response from Gemini API.") from err

    text = extract_text(data)
    usage = data.get("usage", {})
    logger.info(
        json.dumps(
            {
                "event": "llm.call",
                "interaction_id": data.get("id"),
                "model": model,
                "tokens": {
                    "in": usage.get("total_input_tokens"),
                    "out": usage.get("total_output_tokens"),
                    "thought": usage.get("total_thought_tokens"),
                    "cached": usage.get("total_cached_tokens"),
                },
                "prompt_chars": len(prompt),
                "response_chars": len(text),
                "latency_ms": _elapsed_ms(start),
            }
        )
    )
    return text


if __name__ == "__main__":
    # PoC only: in the real app the environment redirects stdout (12-factor XI).
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "llm_calls.log", mode="a", encoding="utf-8"),
        ],
    )
    load_dotenv()
    try:
        print(consume_gemini_api("What is the capital of Argentina?", get_api_key()))
    except GeminiError as err:
        logger.error("%s", err)
        raise SystemExit(1) from err
