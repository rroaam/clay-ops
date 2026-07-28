from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol

from .redaction import redact


@dataclass(frozen=True)
class ImageCapabilities:
    available: bool
    models: tuple[str, ...] = ()
    aspect_ratios: tuple[str, ...] = ()
    max_variants: int = 0
    supports_references: bool = False


@dataclass(frozen=True)
class ImageResult:
    status: str
    outputs: list[dict] = field(default_factory=list)
    error: dict | None = None


class ImageProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class ImageProvider(Protocol):
    provider_id: str

    def capabilities(self) -> ImageCapabilities: ...
    def generate(self, request: dict) -> ImageResult: ...


class UnavailableImageProvider:
    provider_id = "unavailable"

    def capabilities(self) -> ImageCapabilities:
        return ImageCapabilities(available=False)

    def generate(self, request: dict) -> ImageResult:
        raise ImageProviderError("PROVIDER_UNAVAILABLE", "No image provider is configured.")


def normalize_provider_error(error: Exception) -> dict:
    if isinstance(error, ImageProviderError):
        return {"code": error.code, "message": redact(str(error)), "retryable": error.retryable}
    return {"code": "PROVIDER_ERROR", "message": redact(str(error)), "retryable": False}


class ImageProviderRegistry:
    def __init__(self, providers=()):
        self._providers = {"unavailable": UnavailableImageProvider()}
        for provider in providers:
            if not provider.provider_id or provider.provider_id == "unavailable":
                raise ValueError("Invalid image provider id.")
            self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> ImageProvider:
        return self._providers.get(provider_id, self._providers["unavailable"])

    def describe(self) -> list[dict]:
        result = []
        for provider_id, provider in sorted(self._providers.items()):
            caps = provider.capabilities()
            result.append({"provider_id": provider_id, "status": "available" if caps.available else "unavailable", "capabilities": asdict(caps)})
        return result
