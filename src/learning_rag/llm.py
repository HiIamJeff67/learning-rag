import json
import urllib.error
import urllib.request
from typing import Any

from learning_rag.shared.settings import get_config


def complete(
    prompt: str,
    only_free_model: bool = False,
    max_tokens: int | None = None,
    reasoning_tokens: int | None = None,
) -> str:
    key, base, model, cfg_max, cfg_reasoning = get_config(only_free_model)
    if max_tokens is None:
        max_tokens = cfg_max
    if reasoning_tokens is None:
        reasoning_tokens = cfg_reasoning
    # Some servers reject the reasoning field with HTTP 400. Drop it and send once more.
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "reasoning": {"max_tokens": reasoning_tokens},
    }
    payload: dict[str, Any] | None = None
    while payload is None:
        request = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code != 400 or "reasoning" not in body:
                raise
            body.pop("reasoning")
    assert payload is not None
    usage = payload.get("usage") or {}
    if "openrouter.ai" in base and usage.get("cost") not in (0, 0.0):
        raise RuntimeError(f"call was not free, cost={usage.get('cost')}")
    text = payload["choices"][0]["message"].get("content")
    if not text or not str(text).strip():
        raise RuntimeError(f"{model} returned no text")
    return str(text).strip()
