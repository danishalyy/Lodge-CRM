from urllib.parse import urlsplit
from ..config import settings
from .providers.base import ProviderUnavailable
from .providers.vllm import VLLMProvider


def configuration_state():
    if settings.ai_configuration_invalid:
        return "misconfigured"
    if not settings.ai_enabled:
        return "disabled"
    if settings.ai_provider == "test":
        return "test_only" if settings.app_env == "test" else "misconfigured"
    if (
        settings.ai_provider != "vllm"
        or not settings.vllm_base_url
        or not settings.vllm_model
    ):
        return "misconfigured"
    try:
        url = urlsplit(settings.vllm_base_url)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.scheme not in {"http", "https"}
        ):
            return "misconfigured"
        if settings.app_env == "production" and (
            url.scheme != "https" or not settings.vllm_api_key
        ):
            return "misconfigured"
        if settings.ai_max_context <= settings.ai_max_output_tokens + 1024:
            return "misconfigured"
    except ValueError:
        return "misconfigured"
    return "configured"


def get_provider():
    state = configuration_state()
    if state == "test_only":
        from .providers.testing import TestProvider

        return (
            TestProvider()
        )  # Tests provide an explicit deterministic script through dependency override.
    if state != "configured":
        raise ProviderUnavailable("ai_" + state)
    return VLLMProvider(settings)


def health_ready():
    """One bounded health probe per configuration, not one network call per UI visit."""
    import hashlib
    import redis

    client = redis.Redis.from_url(
        settings.redis_url, socket_connect_timeout=1, socket_timeout=1
    )
    key = (
        "ai:health:"
        + hashlib.sha256(
            (
                settings.vllm_base_url + settings.vllm_model + settings.vllm_api_key
            ).encode()
        ).hexdigest()
    )
    try:
        cached = client.get(key)
        if cached is not None:
            return cached == b"1"
        if not client.set(key + ":probe", "1", nx=True, ex=5):
            return False
        try:
            ready = get_provider().health()
        except ProviderUnavailable:
            ready = False
        client.set(key, "1" if ready else "0", ex=10)
        return ready
    except redis.RedisError:
        return False
    finally:
        client.close()
