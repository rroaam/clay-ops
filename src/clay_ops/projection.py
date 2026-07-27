from __future__ import annotations

from pathlib import Path

from .store import OperationalStore, utc_now


AGENTS = [
    {"id": "studio-director", "name": "Studio Director", "role": "Deterministic local parent stage", "status": "simulated"},
    {"id": "copywriter", "name": "Copywriter", "role": "Deterministic local copy stage", "status": "simulated"},
    {"id": "web-builder", "name": "Web Builder", "role": "Deterministic responsive website stage", "status": "simulated"},
    {"id": "email-designer", "name": "Email Designer", "role": "Deterministic responsive email stage", "status": "simulated"},
    {"id": "image-director", "name": "Image Director", "role": "Capability check only; generation unavailable", "status": "unavailable"},
]


class ProjectionService:
    def __init__(self, root: Path, store: OperationalStore):
        self.root = Path(root).resolve()
        self.store = store

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
        if provider_attempts:
            image_health_status = "connected_verified"
            image_health_evidence = "Provider-backed attempt evidenced."
        elif any(payload.get("status") == "unavailable" for payload in image_events):
            image_health_status = "unavailable"
            image_health_evidence = "Runtime capability evidence reports no configured image provider."
        else:
            image_health_status = "degraded"
            image_health_evidence = "No provider-backed image artifact evidenced."
        return {
            "schema_version": "1.0.0",
            "generated_at": utc_now(),
            "summary": {
                "runs": len(runs),
                "active": sum(run["status"] in {"queued", "running", "awaiting_approval"} for run in runs),
                "needs_ryan": len(pending),
                "artifacts": len(all_artifacts),
            },
            "runs": runs,
            "needs_ryan": pending,
            "agents": AGENTS,
            "workflows": [
                {"id": "clay-hq-eod-demo", "name": "EOD Campaign Build", "status": "local_verified" if eod_verified else "ready_local", "mode": "supervised"},
                {"id": "website-build", "name": "Responsive Website Build", "status": "local_verified" if any(a["kind"] == "website/html" for a in all_artifacts) else "ready_local", "mode": "local_only"},
                {"id": "email-design", "name": "Responsive Email Design", "status": "local_verified" if any(a["kind"] == "email/html" for a in all_artifacts) else "ready_local", "mode": "local_only"},
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
