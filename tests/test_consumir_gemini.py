import json
from unittest.mock import Mock, patch

import pytest
import requests

from skillnest_app.consumir_gemini import (
    GeminiError,
    GeminiRateLimitError,
    consume_gemini_api,
    extract_text,
)

MODEL_RESPONSE = {
    "steps": [
        {"type": "thought", "signature": "abc"},
        {"type": "model_output", "content": [{"type": "text", "text": "Paris"}]},
    ]
}


def _response(status: int = 200, json_data: dict | None = None) -> Mock:
    resp = Mock()
    resp.status_code = status
    resp.text = ""
    resp.json.return_value = json_data
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def test_extract_text_ignores_thought_step():
    assert extract_text(MODEL_RESPONSE) == "Paris"


def test_extract_text_without_model_output_raises():
    with pytest.raises(GeminiError):
        extract_text({"steps": [{"type": "thought", "signature": "abc"}]})


def test_returns_model_text():
    with patch("requests.post", return_value=_response(json_data=MODEL_RESPONSE)):
        assert consume_gemini_api("hola", "key") == "Paris"


def test_logs_llm_call_event_with_latency_and_tokens(caplog):
    data = {
        "id": "v1_abc",
        "usage": {"total_input_tokens": 8, "total_output_tokens": 8},
        **MODEL_RESPONSE,
    }
    with (
        caplog.at_level("INFO"),
        patch("requests.post", return_value=_response(json_data=data)),
    ):
        consume_gemini_api("hola", "key")

    event = json.loads(caplog.records[-1].getMessage())
    assert event["event"] == "llm.call"
    assert event["interaction_id"] == "v1_abc"
    assert event["tokens"]["in"] == 8
    assert event["response_chars"] == len("Paris")
    assert event["latency_ms"] >= 0
    assert "Paris" not in caplog.text


def test_429_raises_rate_limit_error():
    with (
        patch("requests.post", return_value=_response(status=429)),
        pytest.raises(GeminiRateLimitError),
    ):
        consume_gemini_api("hola", "key")


def test_timeout_raises_gemini_error():
    with (
        patch("requests.post", side_effect=requests.Timeout),
        pytest.raises(GeminiError),
    ):
        consume_gemini_api("hola", "key")


def test_invalid_json_raises_gemini_error():
    resp = _response()
    resp.json.side_effect = ValueError
    with patch("requests.post", return_value=resp), pytest.raises(GeminiError):
        consume_gemini_api("hola", "key")
