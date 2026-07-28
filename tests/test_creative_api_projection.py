from __future__ import annotations

import base64
import json
import struct
import threading
import urllib.error
import urllib.request
import zlib

import pytest

from clay_ops.api import create_server
from clay_ops.images import ImageCapabilities, ImageProviderRegistry, ImageResult
from clay_ops.projection import ProjectionService
from clay_ops.store import OperationalStore


HEADERS = {"Content-Type": "application/json", "Origin": "http://127.0.0.1:3001", "X-Clay-HQ-Server": "1"}


def png():
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)


def call(url, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read())


def test_creative_api_routes_use_command_boundary_and_projection_reads(tmp_path):
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    server = create_server(("127.0.0.1", 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, project = call(base + "/api/projects", "POST", {"name": "Summer", "brief": "Bright"}, HEADERS)
        assert status == 201
        with pytest.raises(urllib.error.HTTPError) as exc:
            call(base + "/api/generation-requests", "POST", {"project_name": "Bad", "prompt": "x"}, {"Content-Type": "application/json"})
        assert exc.value.code == 403

        status, generated = call(base + "/api/generation-requests", "POST", {
            "project_name": "Generated", "brief": "Brief", "prompt": "Clay sun", "references": [], "style": "clay",
            "aspect_ratio": "1:1", "variant_count": 1, "provider": "unavailable", "model": None,
        }, HEADERS)
        assert status == 201 and generated["status"] == "blocked"

        status, asset = call(base + "/api/imports/images", "POST", {
            "project_id": project["project_id"], "name": "hero.png", "mime_type": "image/png",
            "data_base64": base64.b64encode(png()).decode(), "tags": ["hero"],
        }, HEADERS)
        assert status == 201 and asset["provenance"]["source"] == "request_bytes"

        _, projects = call(base + "/api/projects")
        _, assets = call(base + f"/api/projects/{project['project_id']}/assets")
        _, requests = call(base + "/api/generation-requests")
        assert {item["project_id"] for item in projects["projects"]} >= {project["project_id"], generated["project_id"]}
        assert [item["asset_id"] for item in assets["assets"]] == [asset["asset_id"]]
        assert [item["request_id"] for item in requests["generation_requests"]] == [generated["request_id"]]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_projection_reports_creative_collections_providers_and_truthful_summary(tmp_path):
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    snapshot = ProjectionService(root, store).snapshot()
    assert snapshot["projects"] == [] and snapshot["assets"] == [] and snapshot["generation_requests"] == []
    assert snapshot["providers"][0]["provider_id"] == "unavailable"
    assert snapshot["summary"]["projects"] == snapshot["summary"]["assets"] == snapshot["summary"]["generation_requests"] == 0
    assert snapshot["health"]["image_provider"]["status"] == "unavailable"


def test_projection_shapes_stored_projects_into_the_full_dashboard_contract(tmp_path):
    """Clay Ops stores only schema_version/project_id/name/brief/tags/created_at
    (see schemas/creative-project.schema.json). The dashboard's CreativeProject
    contract additionally requires description/project_type/status/updated_at/
    run_ids/asset_ids. The projection boundary must derive those truthfully
    (never fabricating narrative content) so the dashboard's sanitizer never
    receives a project record it cannot parse."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    server = create_server(("127.0.0.1", 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, project = call(base + "/api/projects", "POST", {"name": "Summer", "brief": "Bright and warm."}, HEADERS)
        assert status == 201
        snapshot = ProjectionService(root, store).snapshot()
        shaped = next(item for item in snapshot["projects"] if item["project_id"] == project["project_id"])

        # The canonical stored field is preserved verbatim, never renamed.
        assert shaped["brief"] == "Bright and warm."
        # description mirrors brief exactly — no fabricated content.
        assert shaped["description"] == shaped["brief"] == "Bright and warm."
        # Every field required by the dashboard's CreativeProject contract is present.
        for field in ("project_type", "status", "updated_at", "run_ids", "asset_ids"):
            assert field in shaped
        assert isinstance(shaped["run_ids"], list) and isinstance(shaped["asset_ids"], list)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_projection_shapes_stored_assets_into_the_full_dashboard_contract(tmp_path):
    """Clay Ops stores assets with name/relative_path/byte_size/status
    (see schemas/creative-asset.schema.json). The dashboard's CreativeAsset
    contract additionally requires filename/artifact_path/file_size/
    asset_type/source_type/generation_status. Every derived field must come
    from data already on the stored record — never fabricated."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    server = create_server(("127.0.0.1", 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, project = call(base + "/api/projects", "POST", {"name": "Summer", "brief": "Bright"}, HEADERS)
        assert status == 201
        status, asset = call(base + "/api/imports/images", "POST", {
            "project_id": project["project_id"], "name": "hero.png", "mime_type": "image/png",
            "data_base64": base64.b64encode(png()).decode(), "tags": ["hero"],
        }, HEADERS)
        assert status == 201

        snapshot = ProjectionService(root, store).snapshot()
        shaped = next(item for item in snapshot["assets"] if item["asset_id"] == asset["asset_id"])

        assert shaped["filename"] == "hero.png"
        assert shaped["artifact_path"] == shaped["relative_path"]
        assert shaped["file_size"] == shaped["byte_size"]
        assert shaped["asset_type"] == "image"
        assert shaped["source_type"] == "imported"
        assert shaped["generation_status"] == shaped["status"] == "available"

        # The dashboard's CreativeAsset contract reads `creative_assets`,
        # not the internal `assets` key used by the loopback API routes.
        # Both must be present with identical content at the projection
        # boundary.
        assert snapshot["creative_assets"] == snapshot["assets"]
        assert any(item["asset_id"] == asset["asset_id"] for item in snapshot["creative_assets"])
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_projection_shapes_generation_requests_and_providers_into_the_dashboard_contract(tmp_path):
    """Clay Ops stores generation requests with `references`/`variant_count`
    and describes providers with `provider_id`/nested `capabilities.models`.
    The dashboard's GenerationRequest/CreativeProvider contracts additionally
    require `reference_asset_ids`/`requested_variant_count` and `label`/
    top-level `models`. Every alias must be copied or derived from data
    already on the record — never fabricated."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    server = create_server(("127.0.0.1", 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, generated = call(base + "/api/generation-requests", "POST", {
            "project_name": "Demo", "brief": "Brief", "prompt": "Clay sun", "references": ["asset-ref-1"], "style": "clay",
            "aspect_ratio": "1:1", "variant_count": 3, "provider": "unavailable", "model": None,
        }, HEADERS)
        assert status == 201 and generated["status"] == "blocked"

        snapshot = ProjectionService(root, store).snapshot()
        shaped_request = next(item for item in snapshot["generation_requests"] if item["request_id"] == generated["request_id"])
        assert shaped_request["reference_asset_ids"] == shaped_request["references"] == ["asset-ref-1"]
        assert shaped_request["requested_variant_count"] == shaped_request["variant_count"] == 3
        # Never fabricate a fake attempt or promote status when provider is unavailable.
        assert shaped_request["status"] == "blocked"
        assert shaped_request["attempt_status"] == "not_attempted"

        shaped_provider = snapshot["providers"][0]
        assert shaped_provider["provider_id"] == "unavailable"
        assert shaped_provider["label"] == "Unavailable"
        assert shaped_provider["models"] == list(shaped_provider["capabilities"]["models"]) == []
        assert shaped_provider["status"] == "unavailable"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_creative_roadmap_marks_only_image_functional(repo_root):
    roadmap = json.loads((repo_root / "registries" / "creative-workflows.json").read_text())
    by_id = {item["id"]: item["status"] for item in roadmap["workflows"]}
    assert by_id["image"] == "functional"
    assert set(by_id) == {"image", "design", "landing", "email", "campaign", "social", "presentation", "moodboard", "video"}
    assert all(status == "planned" for key, status in by_id.items() if key != "image")


def test_projection_workflows_include_full_creative_roadmap_without_dropping_operational_entries(repo_root, tmp_path):
    root = tmp_path / "ops"
    root.mkdir()
    (root / "registries").symlink_to(repo_root / "registries")
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    snapshot = ProjectionService(root, store).snapshot()
    by_id = {item["id"]: item["status"] for item in snapshot["workflows"]}

    # Existing operational workflows remain present and untouched.
    assert {"clay-hq-eod-demo", "website-build", "email-design"} <= set(by_id)

    # All nine Creative OS roadmap entries are present.
    roadmap_ids = {"image", "design", "landing", "email", "campaign", "social", "presentation", "moodboard", "video"}
    assert roadmap_ids <= set(by_id)

    # Image is the only roadmap entry represented as functional/active; the
    # rest degrade honestly instead of being promoted to a live state.
    assert by_id["image"] == "active"
    for workflow_id in roadmap_ids - {"image"}:
        assert by_id[workflow_id] in {"unavailable", "degraded"}
        assert by_id[workflow_id] not in {"complete", "local_verified", "healthy", "connected_verified"}

    # No roadmap entry may ever be reported as a completed/healthy state.
    live_statuses = {"complete", "local_verified", "healthy", "connected_verified"}
    for item in snapshot["workflows"]:
        if item["id"] in roadmap_ids and item["id"] != "image":
            assert item["status"] not in live_statuses


def test_context_create_update_and_projection_round_trip(tmp_path):
    """Creative context must flow through the same command-boundary and
    projection-read pattern as projects/assets/requests: create via POST,
    read only via the projection, edit via a scoped POST, never fabricate
    fields the operator did not supply."""
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    server = create_server(("127.0.0.1", 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, project = call(base + "/api/projects", "POST", {"name": "Clay Brand System", "brief": "Design tokens and references."}, HEADERS)
        assert status == 201

        # Creating a context without provenance must be rejected — provenance
        # is required so a brand-context record can never masquerade as
        # verified/authoritative without a truthful source.
        with pytest.raises(urllib.error.HTTPError):
            call(base + "/api/contexts", "POST", {"project_id": project["project_id"], "name": "Clay brand"}, HEADERS)

        status, context = call(base + "/api/contexts", "POST", {
            "project_id": project["project_id"], "name": "Clay brand context",
            "brand_name": "Clay", "brand_description": "Clay is a design studio.",
            "color_tokens": ["#C8FF00"], "typography_references": ["Bebas Neue"],
            "provenance": {"kind": "manual", "source": "operator_entry"},
        }, HEADERS)
        assert status == 201
        assert context["brand_name"] == "Clay"
        # Fields never supplied stay null — nothing is fabricated.
        assert context["positioning"] is None

        snapshot = ProjectionService(root, store).snapshot()
        shaped = next(item for item in snapshot["creative_contexts"] if item["context_id"] == context["context_id"])
        assert shaped["project_id"] == project["project_id"]
        assert shaped["color_tokens"] == ["#C8FF00"]

        status, updated = call(base + "/api/contexts/" + context["context_id"], "POST", {"positioning": "Sculptural motion for modern brands."}, HEADERS)
        assert status == 200
        assert updated["positioning"] == "Sculptural motion for modern brands."
        assert updated["brand_name"] == "Clay"

        snapshot = ProjectionService(root, store).snapshot()
        shaped = next(item for item in snapshot["creative_contexts"] if item["context_id"] == context["context_id"])
        assert shaped["positioning"] == "Sculptural motion for modern brands."
        assert snapshot["summary"]["creative_contexts"] == 1
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_context_must_reference_an_existing_project(tmp_path):
    root = tmp_path / "ops"; root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    server = create_server(("127.0.0.1", 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(urllib.error.HTTPError):
            call(base + "/api/contexts", "POST", {
                "project_id": "project-does-not-exist", "name": "Orphan context",
                "provenance": {"kind": "manual", "source": "operator_entry"},
            }, HEADERS)
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
