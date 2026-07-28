from __future__ import annotations

from dataclasses import dataclass

import pytest

from clay_ops.images import (
    ImageCapabilities,
    ImageProviderError,
    ImageProviderRegistry,
    ImageResult,
    UnavailableImageProvider,
    normalize_provider_error,
)
from clay_ops.store import OperationalStore
from clay_ops.workflows.image_generation import ImageGenerationWorkflow


class RecordingProvider:
    provider_id = "recording"

    def __init__(self, result=None, error=None):
        self.calls = 0
        self.result = result or ImageResult(status="completed", outputs=[])
        self.error = error

    def capabilities(self):
        return ImageCapabilities(available=True, models=("model-a",), aspect_ratios=("1:1",), max_variants=4)

    def generate(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def workflow(tmp_path, registry=None):
    root = tmp_path / "ops"
    return ImageGenerationWorkflow(root, OperationalStore(root / "runtime" / "ops.sqlite3"), registry=registry)


def submit(flow, **overrides):
    value = dict(project_name="Summer", brief="Bright launch", prompt="Clay sun", references=[], style="clay", aspect_ratio="1:1", variant_count=2, provider="unavailable", model=None)
    value.update(overrides)
    return flow.submit(**value)


def test_registry_default_is_truthfully_unavailable():
    registry = ImageProviderRegistry()
    provider = registry.get("unavailable")
    assert isinstance(provider, UnavailableImageProvider)
    assert provider.capabilities().available is False
    assert registry.describe()[0]["status"] == "unavailable"


def test_unavailable_submission_creates_links_without_output_or_attempt(tmp_path):
    flow = workflow(tmp_path)
    result = submit(flow)
    request = flow.store.get_generation_request(result["request_id"])

    assert result["status"] == "blocked"
    assert request["attempt_status"] == "not_attempted"
    assert request["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert flow.store.get_project(result["project_id"])["name"] == "Summer"
    assert flow.store.project_run(result["run_id"])["status"] == "blocked"
    assert flow.store.list_assets(result["project_id"]) == []


def test_available_provider_requires_matching_approval_before_execution(tmp_path):
    provider = RecordingProvider()
    registry = ImageProviderRegistry([provider])
    flow = workflow(tmp_path, registry)
    result = submit(flow, provider="recording", model="model-a")

    assert result["status"] == "awaiting_approval"
    assert provider.calls == 0
    with pytest.raises(ValueError, match="approval"):
        flow.execute(result["request_id"], result["approval_id"])
    assert provider.calls == 0

    approval = flow.store.get_approval(result["approval_id"])
    flow.store.resolve_approval(result["approval_id"], True, "Ryan", approval["scope"])
    executed = flow.execute(result["request_id"], result["approval_id"])
    assert executed["status"] == "completed"
    assert executed["attempt_status"] == "attempted"
    assert provider.calls == 1


def test_completed_provider_outputs_become_request_linked_variants(tmp_path):
    import struct
    import zlib

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    image = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    provider = RecordingProvider(ImageResult(status="completed", outputs=[
        {"data": image, "mime_type": "image/png", "name": "one.png", "evidence": {"provider_asset_id": "remote-1"}},
        {"data": image, "mime_type": "image/png", "name": "two.png", "evidence": {"provider_asset_id": "remote-2"}},
    ]))
    flow = workflow(tmp_path, ImageProviderRegistry([provider]))
    submitted = submit(flow, provider="recording")
    approval = flow.store.get_approval(submitted["approval_id"])
    flow.store.resolve_approval(submitted["approval_id"], True, "Ryan", approval["scope"])
    flow.execute(submitted["request_id"], submitted["approval_id"])

    assets = flow.store.list_assets(submitted["project_id"])
    assert {asset["variant_index"] for asset in assets} == {0, 1}
    assert all(asset["request_id"] == submitted["request_id"] and asset["run_id"] == submitted["run_id"] for asset in assets)
    assert all(asset["provenance"]["kind"] == "generated" for asset in assets)


def test_provider_partial_and_cancelled_statuses_remain_truthful(tmp_path):
    for status in ("partial", "cancelled"):
        provider = RecordingProvider(ImageResult(status=status, outputs=[], error={"code": status.upper(), "message": status}))
        flow = workflow(tmp_path / status, ImageProviderRegistry([provider]))
        result = submit(flow, provider="recording")
        approval = flow.store.get_approval(result["approval_id"])
        flow.store.resolve_approval(result["approval_id"], True, "Ryan", approval["scope"])
        assert flow.execute(result["request_id"], result["approval_id"])["status"] == status


def test_provider_errors_are_normalized_without_secrets(tmp_path):
    provider = RecordingProvider(error=RuntimeError("token sk-secret-value failed"))
    flow = workflow(tmp_path, ImageProviderRegistry([provider]))
    result = submit(flow, provider="recording")
    approval = flow.store.get_approval(result["approval_id"])
    flow.store.resolve_approval(result["approval_id"], True, "Ryan", approval["scope"])
    failed = flow.execute(result["request_id"], result["approval_id"])
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "PROVIDER_ERROR"
    assert "sk-secret-value" not in failed["error"]["message"]

    normalized = normalize_provider_error(ImageProviderError("RATE_LIMITED", "slow down", retryable=True))
    assert normalized == {"code": "RATE_LIMITED", "message": "slow down", "retryable": True}
