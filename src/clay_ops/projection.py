from __future__ import annotations

import json
from pathlib import Path

from .images import ImageProviderRegistry
from .store import OperationalStore, utc_now


# Truthful mapping from the creative-workflows.json roadmap registry status
# vocabulary to the projected workflow status vocabulary already rendered by
# the dashboard's StatusPill/normalizeStatus. `functional` is the only status
# that may render as live/healthy; every other roadmap label degrades honestly
# instead of being promoted to a completed or healthy state.
_ROADMAP_STATUS_MAP = {
    "functional": "active",
    "planned": "unavailable",
    "scaffolded": "degraded",
    "unavailable": "unavailable",
}


def _load_creative_roadmap(root: Path) -> list[dict]:
    """Load the Creative OS workflow roadmap registry as projected workflows.

    Never raises: an unreadable or malformed registry yields an empty list so
    a missing file degrades the roadmap section rather than crashing the
    entire projection.
    """
    path = Path(root) / "registries" / "creative-workflows.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    entries = data.get("workflows", []) if isinstance(data, dict) else []
    roadmap = []
    for entry in entries:
        if not isinstance(entry, dict) or "id" not in entry or "name" not in entry:
            continue
        raw_status = entry.get("status", "planned")
        status = _ROADMAP_STATUS_MAP.get(raw_status, "degraded")
        roadmap.append({"id": entry["id"], "name": entry["name"], "status": status, "mode": "creative_roadmap"})
    return roadmap


AGENTS = [
    {"id": "studio-director", "name": "Studio Director", "role": "Deterministic local parent stage", "status": "simulated"},
    {"id": "copywriter", "name": "Copywriter", "role": "Deterministic local copy stage", "status": "simulated"},
    {"id": "web-builder", "name": "Web Builder", "role": "Deterministic responsive website stage", "status": "simulated"},
    {"id": "email-designer", "name": "Email Designer", "role": "Deterministic responsive email stage", "status": "simulated"},
    {"id": "image-director", "name": "Image Director", "role": "Capability check only; generation unavailable", "status": "unavailable"},
]


class ProjectionService:
    def __init__(self, root: Path, store: OperationalStore, registry: ImageProviderRegistry | None = None):
        self.root = Path(root).resolve()
        self.store = store
        self.registry = registry or ImageProviderRegistry()

    def _project_projections(self, projects: list[dict], *, assets: list[dict], generation_requests: list[dict]) -> list[dict]:
        """Shape stored creative-project documents into the dashboard's
        CreativeProject projection contract.

        The canonical stored document (see schemas/creative-project.schema.json)
        only guarantees schema_version, project_id, name, brief, tags, and
        created_at. The dashboard projection additionally requires
        description, project_type, status, updated_at, run_ids, and
        asset_ids. This method derives those fields truthfully from stored
        or computable data — it never invents narrative content:

        - description mirrors the canonical stored `brief` verbatim (both
          fields are emitted so the dashboard can read either name without
          Clay Ops renaming or migrating the stored field).
        - project_type/status/updated_at fall back to honest, neutral
          defaults when the stored document predates those fields, rather
          than fabricating a specific claim.
        - run_ids/asset_ids are computed from actual linked records, not
          copied from unrelated state.
        """
        assets_by_project: dict[str, list[str]] = {}
        for asset in assets:
            assets_by_project.setdefault(asset.get("project_id", ""), []).append(asset["asset_id"])
        runs_by_project: dict[str, list[str]] = {}
        for request in generation_requests:
            if request.get("run_id"):
                runs_by_project.setdefault(request.get("project_id", ""), []).append(request["run_id"])

        shaped = []
        for value in projects:
            item = dict(value)
            project_id = item["project_id"]
            brief = item.get("brief") or ""
            item.setdefault("description", brief)
            item["brief"] = brief
            item.setdefault("project_type", "general")
            item.setdefault("status", "active")
            item.setdefault("updated_at", item.get("created_at", utc_now()))
            item["run_ids"] = runs_by_project.get(project_id, [])
            item["asset_ids"] = assets_by_project.get(project_id, [])
            shaped.append(item)
        return shaped

    def _asset_projections(self, assets: list[dict]) -> list[dict]:
        """Shape stored creative-asset documents into the dashboard's
        CreativeAsset projection contract.

        The canonical stored asset document (see
        schemas/creative-asset.schema.json) uses `name`, `relative_path`,
        `byte_size`, and `status`. The dashboard contract additionally
        requires `filename`, `artifact_path`, `file_size`, `asset_type`,
        `source_type`, `generation_status`, and `variant_of`. Every value
        below is either copied verbatim from the stored record or derived
        from data already present on it (MIME family, provenance kind,
        parent-asset linkage) — nothing is invented.
        """
        by_parent: dict[str, list[str]] = {}
        for asset in assets:
            parent = asset.get("parent_asset_id")
            if parent:
                by_parent.setdefault(parent, []).append(asset["asset_id"])

        shaped = []
        for value in assets:
            item = dict(value)
            item["preview_url"] = "/api/artifacts/" + item["relative_path"]
            item.setdefault("filename", item.get("name", item["asset_id"]))
            item.setdefault("artifact_path", item["relative_path"])
            item.setdefault("file_size", item.get("byte_size"))
            mime = item.get("mime_type", "")
            item.setdefault("asset_type", mime.split("/", 1)[0] if "/" in mime else "file")
            provenance = item.get("provenance") or {}
            item.setdefault("source_type", provenance.get("kind", "unknown"))
            item.setdefault("generation_status", item.get("status", "unknown"))
            if item.get("parent_asset_id"):
                item.setdefault("variant_of", item["parent_asset_id"])
            related = by_parent.get(item["asset_id"], [])
            if related:
                item.setdefault("related_variant_ids", related)
            shaped.append(item)
        return shaped

    def _generation_request_projections(self, requests: list[dict]) -> list[dict]:
        """Shape stored generation-request documents into the dashboard's
        GenerationRequest projection contract.

        The canonical stored document uses `references` and `variant_count`.
        The dashboard contract additionally requires `reference_asset_ids`
        and `requested_variant_count`. Both aliases are copied verbatim from
        the stored values — no fabricated reference IDs or counts.
        """
        shaped = []
        for value in requests:
            item = dict(value)
            item.setdefault("reference_asset_ids", list(item.get("references", [])))
            item.setdefault("requested_variant_count", item.get("variant_count", 0))
            shaped.append(item)
        return shaped

    def _provider_projections(self, providers: list[dict]) -> list[dict]:
        """Shape provider capability records into the dashboard's
        CreativeProvider projection contract.

        The registry's describe() output uses `provider_id`/`status` plus a
        nested `capabilities.models` list. The dashboard contract also
        requires a top-level `label` and `models` list. Both are derived
        truthfully from data already on the record (the provider_id itself,
        and the same models list already reported) — no invented provider
        names or capability claims.
        """
        shaped = []
        for value in providers:
            item = dict(value)
            item.setdefault("label", item["provider_id"].replace("_", " ").title())
            item.setdefault("models", list(item.get("capabilities", {}).get("models", [])))
            shaped.append(item)
        return shaped

    def snapshot(self) -> dict:
        approvals = self.store.list_approvals()
        runs = []
        for base in self.store.list_runs():
            run_id = base["run_id"]
            events = self.store.list_events(run_id)
            artifacts = []
            for artifact in self.store.list_artifacts(run_id):
                item = dict(artifact)
                item["preview_url"] = "/api/artifacts/" + item["relative_path"]
                artifacts.append(item)
            run_approvals = [item for item in approvals if item and item["run_id"] == run_id]
            result = self.store.get_result_for_run(run_id)
            task = self.store.get_task(base["task_id"])
            hermes_observations = [
                event["payload"].get("remote_status")
                for event in events
                if event["event_type"].startswith("hermes.run.") and event["payload"].get("remote_status")
            ]
            hermes_status = hermes_observations[-1] if hermes_observations else (result or {}).get("hermes_status", "not_attempted")
            runs.append(
                {
                    **base,
                    "brief": (task or {}).get("brief", ""),
                    "status": events[-1]["status"] if events else "unknown",
                    "events": events,
                    "artifacts": artifacts,
                    "approvals": run_approvals,
                    "result": result,
                    "canon_snapshots": self.store.list_canon_snapshots(run_id),
                    "hermes_run_id": (result or {}).get("hermes_run_id"),
                    "hermes_status": hermes_status,
                }
            )

        pending = [approval for approval in approvals if approval and approval["status"] == "pending"]
        all_artifacts = [artifact for run in runs for artifact in run["artifacts"]]
        hermes_verified = any(run.get("hermes_run_id") and run.get("hermes_status") == "completed" for run in runs)
        hermes_observed = any(
            event["event_type"].startswith("hermes.run.")
            for run in runs
            for event in run["events"]
        )
        eod_verified = any(
            run["workflow_id"] == "clay-hq-eod-demo"
            and run.get("result") is not None
            and bool(run.get("artifacts"))
            for run in runs
        )
        image_events = [
            event["payload"]
            for run in runs
            for event in run["events"]
            if event["payload"].get("stage") == "image-attempt"
        ]
        provider_attempts = [
            payload for payload in image_events
            if payload.get("status") == "attempted"
            and payload.get("attempted") is True
            and isinstance(payload.get("evidence"), dict)
            and payload["evidence"].get("kind") == "provider-result"
        ]
        providers = self._provider_projections(self.registry.describe())
        provider_available = any(item["status"] == "available" for item in providers)
        if provider_attempts:
            image_health_status = "connected_verified"
            image_health_evidence = "Provider-backed attempt evidenced."
        elif provider_available:
            image_health_status = "available_not_verified"
            image_health_evidence = "A provider reports capability, but no provider execution is evidenced."
        elif any(payload.get("status") == "unavailable" for payload in image_events) or not provider_available:
            image_health_status = "unavailable"
            image_health_evidence = "Runtime capability evidence reports no configured image provider."
        else:
            image_health_status = "degraded"
            image_health_evidence = "No provider-backed image artifact evidenced."
        projects_raw = self.store.list_projects()
        assets = self._asset_projections(self.store.list_assets())
        generation_requests = self._generation_request_projections(self.store.list_generation_requests())
        projects = self._project_projections(projects_raw, assets=assets, generation_requests=generation_requests)
        return {
            "schema_version": "1.0.0",
            "generated_at": utc_now(),
            "summary": {
                "runs": len(runs),
                "active": sum(run["status"] in {"queued", "running", "awaiting_approval"} for run in runs),
                "needs_ryan": len(pending),
                "artifacts": len(all_artifacts),
                "projects": len(projects),
                "assets": len(assets),
                "generation_requests": len(generation_requests),
            },
            "projects": projects,
            "assets": assets,
            # `creative_assets` is emitted alongside the canonical internal
            # `assets` key (used by the loopback /api/projects/*/assets
            # route and internal filtering above) so the dashboard's
            # CreativeAsset projection contract has the key name it expects
            # without renaming the field Clay Ops uses internally.
            "creative_assets": assets,
            "generation_requests": generation_requests,
            "providers": providers,
            "runs": runs,
            "needs_ryan": pending,
            "agents": AGENTS,
            "workflows": [
                {"id": "clay-hq-eod-demo", "name": "EOD Campaign Build", "status": "local_verified" if eod_verified else "ready_local", "mode": "supervised"},
                {"id": "website-build", "name": "Responsive Website Build", "status": "local_verified" if any(a["kind"] == "website/html" for a in all_artifacts) else "ready_local", "mode": "local_only"},
                {"id": "email-design", "name": "Responsive Email Design", "status": "local_verified" if any(a["kind"] == "email/html" for a in all_artifacts) else "ready_local", "mode": "local_only"},
                *_load_creative_roadmap(self.root),
            ],
            "outputs": all_artifacts,
            "health": {
                "clay_ops": {"label": "Clay Ops API", "status": "connected_verified", "evidence": "Loopback projection served from local SQLite."},
                "sqlite": {"label": "Append-only event store", "status": "connected_verified", "evidence": "Projection query completed."},
                "hermes": {
                    "label": "Hermes Runs API",
                    "status": "connected_verified" if hermes_verified else "degraded" if hermes_observed else "not_configured",
                    "evidence": "Completed structured run recorded." if hermes_verified else "Hermes run evidence exists, but no completed run is recorded." if hermes_observed else "No Hermes run evidence recorded.",
                },
                "image_provider": {"label": "Image generation", "status": image_health_status, "evidence": image_health_evidence},
                "browser_hermes": {"label": "Browser → Hermes", "status": "blocked_by_policy", "evidence": "Browser only calls the Next.js server proxy."},
                "external_actions": {"label": "Deploy / send / publish", "status": "blocked_by_policy", "evidence": "No release adapters are exposed."},
                "gmail": {"label": "Gmail send", "status": "not_configured", "evidence": "No email was sent."},
                "vercel": {"label": "Vercel deploy", "status": "not_configured", "evidence": "No project link or deploy path used."},
                "demo_fixture": {"label": "Local deterministic builders", "status": "simulated", "evidence": "Website/email HTML are real local artifacts; orchestration labels remain demo-only."},
            },
        }
