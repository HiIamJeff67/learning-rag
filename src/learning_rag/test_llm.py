import io
import json
import urllib.error

import pytest

from . import llm


def test_sol_request_records_the_actual_model_and_token_limit(monkeypatch):
    monkeypatch.setattr(llm, "get_config", lambda *args: ("secret", "https://api.openai.com/v1", "gpt-6.1-sol", 1200, 400))
    requests = []

    def respond(request, **kwargs):
        requests.append(json.loads(request.data))
        return io.BytesIO(json.dumps({
            "id": "test", "model": "gpt-6.1-sol", "usage": {"total_tokens": 10},
            "choices": [{"message": {"content": " answer "}, "finish_reason": "stop"}],
        }).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", respond)
    result = llm.complete("question")
    assert result["text"] == "answer"
    assert requests[0]["max_completion_tokens"] == 1200
    assert requests[0]["reasoning_effort"] == "low"
    assert "seed" not in requests[0] and "reasoning" not in requests[0]
    assert "secret" not in json.dumps(result)


def test_http_errors_keep_the_reason_without_exposing_the_key(monkeypatch):
    monkeypatch.setattr(llm, "get_config", lambda *args: ("secret", "https://api.openai.com/v1", "gpt-6.1-sol", 1200, 400))

    def reject(request, **kwargs):
        raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, io.BytesIO(b"invalid key: secret"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", reject)
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        llm.complete("question")
    assert "secret" not in str(error.value)
