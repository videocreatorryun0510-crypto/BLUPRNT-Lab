"""Replaceable HTTP boundary for Gemini Sandbox."""

from typing import Protocol

import httpx

from presentation_engine_adapter.gemini_models import (
    GeminiHttpResponse,
    GeminiProviderRequest,
)


class GeminiTransportTimeout(RuntimeError):
    pass


class GeminiTransportNetworkError(RuntimeError):
    pass


class GeminiTransport(Protocol):
    def post(
        self,
        request: GeminiProviderRequest,
        *,
        api_key: str,
        timeout_seconds: float,
    ) -> GeminiHttpResponse: ...


class HttpxGeminiTransport:
    """Send one stateless Gemini Interactions request."""

    def post(
        self,
        request: GeminiProviderRequest,
        *,
        api_key: str,
        timeout_seconds: float,
    ) -> GeminiHttpResponse:
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(
                    request.endpoint,
                    headers={
                        "x-goog-api-key": api_key,
                        "content-type": "application/json",
                    },
                    json=request.body,
                )
        except httpx.TimeoutException as error:
            raise GeminiTransportTimeout from error
        except httpx.NetworkError as error:
            raise GeminiTransportNetworkError from error
        return GeminiHttpResponse(
            status_code=response.status_code,
            content=response.content,
        )
