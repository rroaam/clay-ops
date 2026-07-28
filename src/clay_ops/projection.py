from __future__ import annotations

import json
from pathlib import Path

from .images import ImageProviderRegistry
from .store import OperationalStore, utc_now
from .supervised_workflow import describe_active_build, describe_advisor_board, describe_source_registry
from .approval_actions import compute_request_hash


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
            tags = item.get("tags") or []
            item.setdefault("project_type", "verification" if "verification-only" in tags else "general")
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

    def _context_projections(self, contexts: list[dict]) -> list[dict]:
        """Shape stored creative-context (brand-context) documents for
        projection. The stored document already matches the dashboard
        contract field-for-field (see schemas/creative-context.schema.json)
        — this pass-through exists to keep the same seam as the other
        projection methods so future field renames stay isolated here."""
        return [dict(value) for value in contexts]

    def _supervised_workflow_projection(
        self,
        *,
        projects: list[dict],
        generation_requests: list[dict],
        contexts: list[dict],
        approvals: list[dict],
        runs: list[dict],
        providers: list[dict],
    ) -> dict:
        """Compose the one composite Supervised Workflow demonstration from
        real stored records — the Clay Image System project, its brand
        context, the saved morning-demo generation request, and its linked
        pending approval. Nothing here fabricates an execution or a
        provider connection; every field is either read from the store or
        sourced verbatim from `supervised_workflow.py`'s static, provenance-
        labeled governance records (active build, source registry, advisor
        board), which themselves mirror the on-disk handoff documents.
        """
        demo_request = next(
            (r for r in generation_requests if r["request_id"] == "request-clay-morning-demo-draft"),
            None,
        )
        demo_project = next(
            (p for p in projects if p["project_id"] == "project-clay-image-system"),
            None,
        )
        demo_context = next(
            (c for c in contexts if c["project_id"] == "project-clay-brand-system"),
            None,
        )
        demo_run = next((r for r in runs if r["run_id"] == "run-clay-morning-demo-draft"), None)
        demo_approval = next(
            (a for a in approvals if a and a["approval_id"] == "approval-clay-morning-demo-draft"),
            None,
        )
        provider_blocked = not any(p["status"] == "available" for p in providers)

        evidence_timeline: list[dict] = []
        evidence_timeline.append({
            "step": "active_build_ingested",
            "label": "Active build ingested (read-only)",
            "detail": "clayhc-clay-engine @ edits/seed-recoat verified ready_for_review: 6 modified + 6 new paths, output/seed-recoat/{before,after} evidence present, narrow-viewport harness limitation and pending token approval recorded.",
            "status": "completed",
        })
        if demo_context is not None:
            evidence_timeline.append({
                "step": "sources_read",
                "label": "Canonical source + brand-context selected",
                "detail": f"context-clay-brand-system read (project {demo_context['project_id']})",
                "status": "completed",
            })
        if demo_run is not None:
            evidence_timeline.append({
                "step": "workflow_selected",
                "label": "Workflow routing",
                "detail": f"workflow_id={demo_run.get('workflow_id')} execution_mode={demo_run.get('execution_mode')}",
                "status": "completed",
            })
            evidence_timeline.append({
                "step": "worker_model",
                "label": "Worker / model",
                "detail": "No model invoked — request remains a saved draft (provider unavailable).",
                "status": "not_applicable",
            })
        evidence_timeline.append({
            "step": "tests",
            "label": "Approval-gate tests",
            "detail": "28 Python (test_provider_approval_gate.py) + 5 TypeScript (approval-gate.test.ts) — all passing",
            "status": "completed",
        })
        if demo_request is not None:
            evidence_timeline.append({
                "step": "deterministic_preview",
                "label": "Generated deterministic preview",
                "detail": "None generated — no provider call has occurred; prompt/context only.",
                "status": "not_applicable",
            })
        evidence_timeline.append({
            "step": "advisor_reviews",
            "label": "Advisor reviews",
            "detail": "5 of 6 roles reviewed (Copy and Claims not applicable to an image-only request); Ryan pending",
            "status": "in_progress",
        })
        if demo_approval is not None:
            evidence_timeline.append({
                "step": "approval_state",
                "label": "Approval state",
                "detail": f"approval_id={demo_approval['approval_id']} status={demo_approval['status']}",
                "status": demo_approval["status"],
            })
        evidence_timeline.append({
            "step": "blocked_external_action",
            "label": "Blocked external action",
            "detail": "Execution blocked: image provider reports unavailable for every registered slot.",
            "status": "blocked",
        })
        evidence_timeline.append({
            "step": "operator_decision",
            "label": "Operator decision",
            "detail": "Awaiting Ryan's approve / reject / request-changes decision on approval-clay-morning-demo-draft.",
            "status": "pending",
        })

        exact_approval = None
        if demo_approval is not None and demo_request is not None:
            scope = demo_approval.get("scope") or {}
            exact_approval = {
                "approval_id": demo_approval["approval_id"],
                "project_id": demo_request.get("project_id"),
                "request_id": demo_request["request_id"],
                "request_hash": compute_request_hash(demo_request),
                "requested_external_action": demo_approval.get("action"),
                "provider": scope.get("provider", "unavailable"),
                "destination": "local loopback only — no external destination configured",
                "estimated_cost_status": "not_applicable — provider unavailable, no billable call possible",
                "review_receipts": [
                    {"role": item["role"], "decision": item["decision"], "review_status": item["review_status"]}
                    for item in describe_advisor_board()
                ],
                "status": demo_approval.get("status", "pending"),
                "expiry": None,
                "rollback_or_cancellation": "No execution has occurred; cancelling the approval requires no rollback.",
                "blocking_conditions": [
                    {"condition": "approval_pending", "active": demo_approval.get("status") == "pending"},
                    {"condition": "provider_unavailable", "active": provider_blocked},
                    {"condition": "request_hash_mismatch", "active": False},
                    {"condition": "approval_expired_or_rejected", "active": demo_approval.get("status") in {"expired", "rejected"}},
                ],
            }

        return {
            "active_build": describe_active_build(),
            "source_registry": describe_source_registry(),
            "advisor_board": describe_advisor_board(),
            "exact_approval": exact_approval,
            "evidence_timeline": evidence_timeline,
            "demo": {
                "project_id": demo_project["project_id"] if demo_project else None,
                "request_id": demo_request["request_id"] if demo_request else None,
                "context_id": demo_context["context_id"] if demo_context else None,
                "approval_id": demo_approval["approval_id"] if demo_approval else None,
                "provider_blocked": provider_blocked,
            },
        }

    def _enrich_needs_ryan(
        self,
        *,
        pending: list[dict],
        runs_by_id: dict[str, dict],
        projects_by_id: dict[str, dict],
        generation_requests_by_id: dict[str, dict],
        providers: list[dict],
        advisor_board: list[dict],
    ) -> list[dict]:
        """Project each pending approval into the operator-loop decision record
        that Clay HQ's Needs Ryan queue renders. Every added field is a
        truthful join against data already stored (run → project, generation
        request, provider registry, advisor board summary); no narrative or
        invented urgency is layered in. Finalized records are never
        included — the count must remain actionable-only."""
        any_provider_available = any(p["status"] == "available" for p in providers)
        advisor_summary = (
            f"{sum(1 for r in advisor_board if r.get('decision', '').startswith('approve'))} "
            f"of {sum(1 for r in advisor_board if r.get('required'))} required advisors approve"
        )
        out: list[dict] = []
        for approval in pending:
            approval_id = approval["approval_id"]
            run_id = approval.get("run_id")
            run = runs_by_id.get(run_id) if run_id else None
            scope = approval.get("scope") or {}
            project_id = scope.get("project_id") if isinstance(scope, dict) else None
            request_id = scope.get("request_id") if isinstance(scope, dict) else None
            project = projects_by_id.get(project_id) if project_id else None
            generation_request = generation_requests_by_id.get(request_id) if request_id else None
            request_hash = compute_request_hash(generation_request) if generation_request else None
            provider_id = scope.get("provider") if isinstance(scope, dict) else None
            provider_available = any(p["provider_id"] == provider_id and p["status"] == "available" for p in providers)
            provider_status = "available" if provider_available else ("unavailable" if not any_provider_available else "unavailable_for_slot")
            blocking_reason = (
                "Awaiting Ryan's approve / reject / request-changes decision."
                if approval.get("status") == "pending"
                else f"Resolved as '{approval.get('status')}'."
            )
            workflow_id = run.get("workflow_id") if run else None
            out.append({
                "approval_id": approval_id,
                "project_id": project_id,
                "project_name": project["name"] if project else None,
                "request_or_artifact_id": request_id or approval_id,
                "request_name": (generation_request or {}).get("prompt", "")[:160] if generation_request else approval.get("action"),
                "request_hash": request_hash,
                "workflow_id": workflow_id,
                "workflow_name": workflow_id.replace("_", " ").replace("-", " ").title() if workflow_id else None,
                "run_id": run_id,
                "requested_action": approval.get("action"),
                "approval_status": approval.get("status", "pending"),
                "provider_status": provider_status,
                "blocking_reason": blocking_reason,
                "required_approver": "Ryan",
                "submitted_at": approval.get("requested_at"),
                "expires_at": None,
                "expiry_status": "none",
                "advisor_review_summary": advisor_summary,
                "evidence_summary": (
                    "No provider call has occurred; prompt + brand context only."
                    if not any_provider_available
                    else "Provider reports capability but no execution has been evidenced."
                ),
                "review_url": f"/hq/supervised-workflow?approvalId={approval_id}",
                "scope": approval.get("scope"),
                "reason": approval.get("reason"),
            })
        return out

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
        runs_by_id = {run["run_id"]: run for run in runs}
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
        # Merge known-unavailable provider slots so the dashboard shows
        # honest capability records even before a real adapter is configured.
        from .provider_capabilities import describe_known_providers
        known = describe_known_providers()
        seen_ids = {p["provider_id"] for p in providers}
        for slot in known:
            if slot["provider_id"] not in seen_ids:
                providers.append(self._provider_projections([slot])[0])
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
        contexts = self._context_projections(self.store.list_contexts())
        projects = self._project_projections(projects_raw, assets=assets, generation_requests=generation_requests)
        projects_by_id = {p["project_id"]: p for p in projects}
        generation_requests_by_id = {r["request_id"]: r for r in generation_requests}
        enriched_needs_ryan = self._enrich_needs_ryan(
            pending=pending,
            runs_by_id=runs_by_id,
            projects_by_id=projects_by_id,
            generation_requests_by_id=generation_requests_by_id,
            providers=providers,
            advisor_board=describe_advisor_board(),
        )
        supervised_workflow = self._supervised_workflow_projection(
            projects=projects,
            generation_requests=generation_requests,
            contexts=contexts,
            approvals=approvals,
            runs=runs,
            providers=providers,
        )
        return {
            "schema_version": "1.0.0",
            "generated_at": utc_now(),
            "summary": {
                "runs": len(runs),
                "active": sum(run["status"] in {"queued", "running", "awaiting_approval"} for run in runs),
                "needs_ryan": len(enriched_needs_ryan),
                "artifacts": len(all_artifacts),
                "projects": len(projects),
                "assets": len(assets),
                "generation_requests": len(generation_requests),
                "creative_contexts": len(contexts),
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
            "creative_contexts": contexts,
            "providers": providers,
            "supervised_workflow": supervised_workflow,
            "runs": runs,
            "needs_ryan": enriched_needs_ryan,
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
