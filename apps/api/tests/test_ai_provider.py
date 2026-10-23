from types import SimpleNamespace
import json
import httpx
import pytest
from app.ai.providers.vllm import VLLMProvider
from app.ai.providers.base import ProviderUnavailable


def config():
    return SimpleNamespace(
        vllm_base_url="https://private.example/v1",
        vllm_api_key="do-not-log-me",
        vllm_model="configured-model",
        ai_request_timeout=2,
        ai_max_output_tokens=128,
    )


def test_vllm_transport_is_bounded_and_ignores_reasoning():
    def handler(request):
        assert request.headers["authorization"] == "Bearer do-not-log-me"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "configured-model"}]})
        body = json.loads(request.content)
        assert body["model"] == "configured-model" and body["max_tokens"] == 128
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "<think>hidden reasoning</think>Final answer",
                            "reasoning_content": "private reasoning",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            },
        )

    provider = VLLMProvider(config(), httpx.MockTransport(handler))
    assert provider.health()
    reply = provider.complete([{"role": "user", "content": "Question"}], [])
    assert (
        reply.content == "Final answer"
        and reply.input_tokens == 12
        and "reasoning" not in repr(reply)
    )


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(500, text="credential leak"),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "<think>unclosed"}}
                ]
            },
        ),
        httpx.Response(200, content=b"x" * 262145),
    ],
)
def test_vllm_failures_are_safe(reply):
    provider = VLLMProvider(config(), httpx.MockTransport(lambda request: reply))
    with pytest.raises(ProviderUnavailable) as error:
        provider.complete([], [])
    assert "credential" not in str(error.value) and "private.example" not in str(
        error.value
    )


def test_vllm_network_error_is_safe_and_no_replay():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret URL", request=request)

    with pytest.raises(ProviderUnavailable):
        VLLMProvider(config(), httpx.MockTransport(handler)).complete([], [])
    assert len(calls) == 1


def test_vllm_validates_tool_json_and_does_not_execute_it():
    response = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "get_tasks",
                                "arguments": '{"lodge_id":"attacker"}',
                            },
                        }
                    ]
                },
            }
        ]
    }
    result = VLLMProvider(
        config(),
        httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    ).complete([], [])
    assert result.tool_calls[0].arguments == {
        "lodge_id": "attacker"
    }  # Registry must reject injected scope independently.
