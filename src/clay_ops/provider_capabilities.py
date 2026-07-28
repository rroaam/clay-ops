"""Provider-neutral capability records for Clay HQ.

This module defines known image-generation provider capability slots in a
provider-agnostic vocabulary. Every slot is registered as unavailable by
default — no provider is configured, no credential is stored, no external
call can occur.

The projection boundary surfaces these records to the dashboard so the
Generate view can show an honest provider selector (all unavailable, all
blocked) without inventing capability claims.

Adding a real provider:
    1. Implement ImageProvider protocol in a dedicated adapter module.
    2. Register via KNOWN_PROVIDERS with available=True and real model list.
    3. Pass it to ImageProviderRegistry(...) at server startup.
    None of this happens automatically — it requires explicit operator action.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .images import ImageCapabilities, ImageProvider


@dataclass(frozen=True)
class KnownProviderSlot:
    """A provider identity with truthful capability metadata.

    `available` defaults to False — the slot documents a known provider
    category without implying it is configured or callable.
    """
    provider_id: str
    label: str
    reason: str
    models: tuple[str, ...] = ()
    aspect_ratios: tuple[str, ...] = ()
    max_variants: int = 0
    supports_references: bool = False
    available: bool = False

    def capabilities(self) -> ImageCapabilities:
        return ImageCapabilities(
            available=self.available,
            models=self.models,
            aspect_ratios=self.aspect_ratios,
            max_variants=self.max_variants,
            supports_references=self.supports_references,
        )


# Known provider capability slots — all unavailable.
# These are the industry-standard slots Clay HQ documents without
# configuring. Each one stays unavailable until an operator explicitly
# provisions credentials and registers a real adapter.
KNOWN_PROVIDERS: tuple[KnownProviderSlot, ...] = (
    KnownProviderSlot(
        provider_id="flux",
        label="Flux (Black Forest Labs)",
        reason="No adapter configured. No credential stored.",
    ),
    KnownProviderSlot(
        provider_id="midjourney",
        label="Midjourney",
        reason="No adapter configured. No credential stored.",
    ),
    KnownProviderSlot(
        provider_id="dall-e",
        label="DALL·E (OpenAI)",
        reason="No adapter configured. No credential stored.",
    ),
    KnownProviderSlot(
        provider_id="ideogram",
        label="Ideogram",
        reason="No adapter configured. No credential stored.",
    ),
)


def describe_known_providers() -> list[dict]:
    """Project known provider slots into the dashboard's provider vocabulary.

    The output matches the shape of ImageProviderRegistry.describe() so the
    projection can merge them without schema changes. All status values are
    'unavailable' — no provider is callable.
    """
    return [
        {
            "provider_id": slot.provider_id,
            "label": slot.label,
            "status": "unavailable",
            "reason": slot.reason,
            "models": list(slot.models),
            "capabilities": {
                "available": False,
                "models": list(slot.models),
                "aspect_ratios": list(slot.aspect_ratios),
                "max_variants": slot.max_variants,
                "supports_references": slot.supports_references,
            },
        }
        for slot in KNOWN_PROVIDERS
    ]


def all_providers_unavailable(providers: list[dict]) -> bool:
    """Verify that no provider in the list reports a ready/available state.

    Used as a safety invariant — if this ever returns False, the generation
    gate must be re-audited before shipping.
    """
    ready_states = {"ready", "available", "connected", "connected_verified"}
    return all(
        str(item.get("status", "")).strip().lower() not in ready_states
        for item in providers
    )
