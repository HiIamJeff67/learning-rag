import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from learning_rag.shared.settings import get_config


def complete(
    prompt: str,
    only_free_model: bool = False,
    *,
    seed: int = 42,
    temperature: float = 0,
    reasoning_effort: str = "low",
) -> dict[str, Any]:
    key, base, model, max_tokens, reasoning_tokens = get_config(only_free_model)
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    host = urlsplit(base).hostname
    if host == "api.openai.com":
        body["max_completion_tokens"] = max_tokens
        if model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
            body["reasoning_effort"] = reasoning_effort
        else:
            body.update(seed=seed, temperature=temperature)
    else:
        body.update(max_tokens=max_tokens, seed=seed, temperature=temperature)
        if host == "openrouter.ai":
            body["reasoning"] = {"max_tokens": reasoning_tokens}

    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        # Keep the provider's reason, never the request headers.
        detail = exc.read().decode("utf-8", errors="replace").replace(key, "[redacted]")
        raise RuntimeError(f"model HTTP {exc.code}: {detail}") from exc

    usage = payload.get("usage") or {}
    if only_free_model and host == "openrouter.ai" and usage.get("cost") not in (0, 0.0):
        raise RuntimeError(f"call was not free, cost={usage.get('cost')}")
    choice = payload["choices"][0]
    text = choice["message"].get("content")
    return {
        "text": str(text).strip() if text else "",
        "request": body,
        "response_id": payload.get("id"),
        "model": payload.get("model"),
        "system_fingerprint": payload.get("system_fingerprint"),
        "finish_reason": choice.get("finish_reason"),
        "usage": usage,
    }
