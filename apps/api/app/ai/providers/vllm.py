"""Single bounded transport for an external vLLM OpenAI-compatible server."""

import json, re, time
import httpx
from .base import Completion, ToolCall, ProviderUnavailable


class VLLMProvider:
    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport
        base = config.vllm_base_url.rstrip("/")
        self.base = base if base.endswith("/v1") else base + "/v1"

    def _request(self, method, path, payload=None, timeout=None):
        timeout = timeout or self.config.ai_request_timeout
        deadline = time.monotonic() + timeout
        headers = (
            {"Authorization": "Bearer " + self.config.vllm_api_key}
            if self.config.vllm_api_key
            else {}
        )
        try:
            # No automatic retries or redirects: inference POST replay may duplicate work.
            with httpx.Client(
                timeout=timeout,
                follow_redirects=False,
                transport=self.transport,
                trust_env=False,
            ) as client:
                with client.stream(
                    method, self.base + path, headers=headers, json=payload
                ) as response:
                    if response.status_code != 200:
                        raise ProviderUnavailable(
                            "provider_overloaded"
                            if response.status_code == 429
                            else "provider_unavailable"
                        )
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 262144 or time.monotonic() > deadline:
                            raise ProviderUnavailable("provider_response_limit")
                        chunks.append(chunk)
                    return json.loads(b"".join(chunks))
        except ProviderUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError, UnicodeError):
            raise ProviderUnavailable("provider_unavailable") from None

    def health(self):
        data = self._request(
            "GET", "/models", timeout=min(3, self.config.ai_request_timeout)
        )
        rows = data.get("data") if isinstance(data, dict) else None
        return isinstance(rows, list) and any(
            isinstance(m, dict) and m.get("id") == self.config.vllm_model for m in rows
        )

    def complete(self, messages, tools):
        payload = {
            "model": self.config.vllm_model,
            "messages": messages,
            "max_tokens": self.config.ai_max_output_tokens,
            "temperature": 0,
            "stream": False,
        }
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        data = self._request("POST", "/chat/completions", payload)
        try:
            if not isinstance(data, dict):
                raise ValueError()
            choice = data["choices"][0]
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise ValueError()
            message = choice["message"]
            raw = message.get("content") or ""
            if not isinstance(raw, str) or len(raw) > 16000:
                raise ValueError()
            # vLLM's separate reasoning_content is deliberately ignored, never persisted.
            content = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
            if "<think>" in content or "</think>" in content:
                raise ValueError()
            calls = []
            raw_calls = message.get("tool_calls") or []
            if not isinstance(raw_calls, list) or len(raw_calls) > 1:
                raise ValueError()
            for call in raw_calls:
                f = call["function"]
                args = (
                    json.loads(f["arguments"])
                    if isinstance(f["arguments"], str)
                    else f["arguments"]
                )
                if (
                    not isinstance(args, dict)
                    or not isinstance(f["name"], str)
                    or not isinstance(call["id"], str)
                    or len(call["id"]) > 100
                ):
                    raise ValueError()
                calls.append(ToolCall(call["id"], f["name"], args))
            if not content and not calls:
                raise ValueError()
            usage = data.get("usage") or {}
            return Completion(
                content=content,
                tool_calls=calls,
                input_tokens=min(1000000, max(0, int(usage.get("prompt_tokens", 0)))),
                output_tokens=min(
                    1000000, max(0, int(usage.get("completion_tokens", 0)))
                ),
            )
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderUnavailable("provider_invalid_response") from None
