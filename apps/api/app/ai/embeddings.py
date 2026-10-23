"""Real, operator-configured OpenAI/vLLM embedding endpoint. No dummy fallback."""

import math
from urllib.parse import urlsplit
from fastapi import HTTPException
from .providers.vllm import VLLMProvider
from .providers.base import ProviderUnavailable
from .vector import DIMENSIONS
from ..config import settings


def configured():
    try:
        url = urlsplit(settings.ai_embedding_base_url)
        return bool(
            settings.ai_knowledge_enabled
            and not settings.ai_configuration_invalid
            and settings.ai_embedding_model
            and len(settings.ai_embedding_model) <= 160
            and settings.ai_embedding_version
            and len(settings.ai_embedding_version) <= 80
            and url.hostname
            and not (url.username or url.password or url.query or url.fragment)
            and url.scheme in {"https", "http"}
            and (
                settings.app_env != "production"
                or (url.scheme == "https" and settings.ai_embedding_api_key)
            )
        )
    except ValueError:
        return False


class Embeddings:
    def __init__(self, transport=None):
        from types import SimpleNamespace

        if not configured():
            raise ProviderUnavailable("embedding_not_configured")
        config = SimpleNamespace(
            vllm_base_url=settings.ai_embedding_base_url,
            vllm_api_key=settings.ai_embedding_api_key,
            ai_request_timeout=min(settings.ai_request_timeout, 30),
        )
        self.client = VLLMProvider(config, transport)

    def embed(self, texts):
        if not 1 <= len(texts) <= 8 or any(
            not isinstance(t, str) or len(t) > 1800 for t in texts
        ):
            raise ProviderUnavailable("embedding_input_limit")
        data = self.client._request(
            "POST",
            "/embeddings",
            {
                "model": settings.ai_embedding_model,
                "input": texts,
                "encoding_format": "float",
            },
        )
        try:
            rows = sorted(data["data"], key=lambda row: row["index"])
            if [r["index"] for r in rows] != list(range(len(texts))):
                raise ValueError()
            vectors = [r["embedding"] for r in rows]
            if any(
                len(v) != DIMENSIONS
                or any(type(n) not in (int, float) or not math.isfinite(n) for n in v)
                or sum(n * n for n in v) < 1e-12
                for v in vectors
            ):
                raise ValueError()
            return vectors
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ProviderUnavailable("invalid_embeddings") from None


def get_embeddings():
    return Embeddings()
