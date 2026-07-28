"""Tests proving no provider call can occur before explicit approval.

These tests enforce the Clay HQ invariant: an external image provider is
never invoked unless an explicit, scope-matched approval record exists with
status='approved'. They also verify that the default ImageProviderRegistry
with no configured providers cannot make any external call.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from clay_ops.images import (
    ImageCapabilities,
    ImageProviderError,
    ImageProviderRegistry,
    ImageResult,
    UnavailableImageProvider,
)
from clay_ops.provider_capabilities import all_providers_unavailable, describe_known_providers
from clay_ops.store import OperationalStore
from clay_ops.workflows.image_generation import ImageGenerationWorkflow


class SpyProvider:
    """A mock provider that records whether generate() was ever called."""
    def __init__(self, available=True):
        self.provider_id = "spy"
        self._available = available
        self.call_count = 0

    def capabilities(self):
        return ImageCapabilities(available=self._available, models=("spy-v1",), aspect_ratios=("1:1",), max_variants=4)

    def generate(self, request):
        self.call_count += 1
        return ImageResult(status="completed", outputs=[])


def test_unavailable_provider_cannot_generate(tmp_path):
    """The default UnavailableImageProvider always raises on generate()."""
    provider = UnavailableImageProvider()
    assert not provider.capabilities().available
    with pytest.raises(ImageProviderError, match="No image provider"):
        provider.generate({"prompt": "test"})


def test_default_registry_returns_only_unavailable(tmp_path):
    """ImageProviderRegistry() with no providers has only 'unavailable'."""
    registry = ImageProviderRegistry()
    provider = registry.get("anything")
    assert provider.provider_id == "unavailable"
    assert not provider.capabilities().available
    with pytest.raises(ImageProviderError):
        provider.generate({"prompt": "test"})


def test_execute_requires_approved_matching_approval(tmp_path):
    """execute() must reject if approval is missing, unapproved, or scope-mismatched."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    spy = SpyProvider(available=True)
    registry = ImageProviderRegistry([spy])
    workflow = ImageGenerationWorkflow(root, store, registry=registry)

    # Submit creates an approval request (status=awaiting_approval), not an attempt.
    result = workflow.submit(
        project_name="Test", brief="Brief", prompt="Clay figure",
        references=[], style="clay", aspect_ratio="1:1",
        variant_count=1, provider="spy", model="spy-v1",
    )
    assert result["status"] == "awaiting_approval"
    assert result["approval_id"] is not None
    assert spy.call_count == 0  # No provider call before approval

    # execute() without approval must fail.
    with pytest.raises(ValueError, match="approval"):
        workflow.execute(result["request_id"], result["approval_id"])
    assert spy.call_count == 0  # Still no provider call

    # Reject the approval — execute() must still refuse.
    store.resolve_approval(result["approval_id"], approve=False, actor="Ryan", scope={"action": "execute_image_provider", "project_id": result["project_id"], "request_id": result["request_id"], "run_id": result["run_id"], "provider": "spy"})
    with pytest.raises(ValueError, match="[Aa]pproved"):
        workflow.execute(result["request_id"], result["approval_id"])
    assert spy.call_count == 0  # Still no provider call


def test_submit_with_unavailable_provider_blocks_without_approval(tmp_path):
    """When the provider is unavailable, submit() blocks and never creates an approval."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    registry = ImageProviderRegistry()  # default = unavailable only
    workflow = ImageGenerationWorkflow(root, store, registry=registry)

    result = workflow.submit(
        project_name="Test", brief="Brief", prompt="Clay figure",
        references=[], style=None, aspect_ratio=None,
        variant_count=1, provider="unavailable", model=None,
    )
    assert result["status"] == "blocked"
    assert result["approval_id"] is None  # No approval created when provider unavailable

    # Attempting to execute the blocked request must fail.
    with pytest.raises(ValueError, match="approval"):
        workflow.execute(result["request_id"], "fake-approval")


def test_known_providers_all_report_unavailable():
    """Every known provider slot reports unavailable — none can be called."""
    providers = describe_known_providers()
    assert len(providers) > 0
    assert all_providers_unavailable(providers)
    for provider in providers:
        assert provider["status"] == "unavailable"
        assert provider["capabilities"]["available"] is False


def test_execute_with_wrong_approval_id_is_rejected(tmp_path):
    """execute() must reject a mismatched approval_id even if a real approval exists."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    spy = SpyProvider(available=True)
    registry = ImageProviderRegistry([spy])
    workflow = ImageGenerationWorkflow(root, store, registry=registry)

    result = workflow.submit(
        project_name="Test", brief="Brief", prompt="Clay figure",
        references=[], style="clay", aspect_ratio="1:1",
        variant_count=1, provider="spy", model="spy-v1",
    )
    # Approve the real one, but try to execute with a fake approval_id.
    store.resolve_approval(result["approval_id"], approve=True, actor="Ryan", scope={"action": "execute_image_provider", "project_id": result["project_id"], "request_id": result["request_id"], "run_id": result["run_id"], "provider": "spy"})
    with pytest.raises(ValueError, match="approval"):
        workflow.execute(result["request_id"], "approval-totally-fake")
    assert spy.call_count == 0
