from __future__ import annotations

import json

import pytest

from clay_ops.contracts import validate_document
from clay_ops.store import OperationalStore


def project_doc(**overrides):
    value = {
        "schema_version": "1.0.0", "project_id": "project-summer", "name": "Summer", "brief": "Bright launch",
        "tags": ["launch"], "created_at": "2026-07-27T00:00:00Z",
    }
    value.update(overrides)
    return value


def request_doc(**overrides):
    value = {
        "schema_version": "1.0.0", "request_id": "request-one", "project_id": "project-summer",
        "run_id": "run-one", "prompt": "Clay figure in sunlight", "references": ["asset://reference-one"],
        "style": "clay", "aspect_ratio": "1:1", "variant_count": 2, "provider": "unavailable",
        "model": None, "status": "blocked", "attempt_status": "not_attempted", "error": None,
        "approval_id": None, "created_at": "2026-07-27T00:00:00Z",
    }
    value.update(overrides)
    return value


def asset_doc(**overrides):
    value = {
        "schema_version": "1.0.0", "asset_id": "asset-one", "project_id": "project-summer",
        "request_id": "request-one", "run_id": "run-one", "parent_asset_id": None, "variant_index": 0,
        "name": "sun.png", "mime_type": "image/png", "relative_path": "run-one/images/sun.png",
        "sha256": "a" * 64, "byte_size": 68, "width": 1, "height": 1, "favorite": False,
        "tags": ["hero"], "provenance": {"kind": "imported", "source": "request_bytes"},
        "evidence": {"signature_verified": True}, "status": "available", "created_at": "2026-07-27T00:00:00Z",
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize("kind,document", [
    ("creative-project", project_doc()),
    ("generation-request", request_doc()),
    ("creative-asset", asset_doc()),
])
def test_creative_contracts_validate(repo_root, kind, document):
    validate_document(kind, document, repo_root / "schemas")


def test_store_persists_project_request_asset_links_and_metadata(tmp_path):
    store = OperationalStore(tmp_path / "ops.sqlite3")
    store.create_project(project_doc())
    store.save_generation_request(request_doc())
    store.create_asset(asset_doc())
    store.update_asset_metadata("asset-one", favorite=True, tags=["hero", "approved"])

    assert store.get_project("project-summer")["brief"] == "Bright launch"
    assert store.get_generation_request("request-one")["attempt_status"] == "not_attempted"
    asset = store.get_asset("asset-one")
    assert asset["favorite"] is True
    assert asset["tags"] == ["hero", "approved"]
    assert asset["provenance"]["kind"] == "imported"
    assert store.list_assets("project-summer") == [asset]


def test_variant_parent_must_belong_to_same_project(tmp_path):
    store = OperationalStore(tmp_path / "ops.sqlite3")
    store.create_project(project_doc())
    store.create_project(project_doc(project_id="project-other", name="Other"))
    store.create_asset(asset_doc(request_id=None, run_id=None))
    with pytest.raises(ValueError, match="same project"):
        store.create_asset(asset_doc(asset_id="asset-two", project_id="project-other", request_id=None, run_id=None, parent_asset_id="asset-one", relative_path="other.png"))


def test_project_scoped_lists_do_not_leak_other_projects(tmp_path):
    store = OperationalStore(tmp_path / "ops.sqlite3")
    store.create_project(project_doc())
    store.create_project(project_doc(project_id="project-other", name="Other"))
    store.save_generation_request(request_doc())
    store.save_generation_request(request_doc(request_id="request-other", project_id="project-other", run_id="run-other"))
    store.create_asset(asset_doc())
    store.create_asset(asset_doc(asset_id="asset-other", project_id="project-other", request_id="request-other", run_id="run-other", relative_path="run-other/other.png"))

    assert {x["asset_id"] for x in store.list_assets("project-summer")} == {"asset-one"}
    assert {x["request_id"] for x in store.list_generation_requests("project-summer")} == {"request-one"}
