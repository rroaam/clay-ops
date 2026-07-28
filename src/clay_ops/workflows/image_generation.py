from __future__ import annotations

import uuid
from pathlib import Path

from ..image_import import LocalImageImporter
from ..images import ImageProviderRegistry, normalize_provider_error
from ..store import OperationalStore, utc_now


class ImageGenerationWorkflow:
    workflow_id = "image-generation"

    def __init__(self, root: Path, store: OperationalStore, *, registry: ImageProviderRegistry | None = None):
        self.root = Path(root).resolve()
        self.store = store
        self.registry = registry or ImageProviderRegistry()

    def submit(self, *, project_name: str, brief: str, prompt: str, references: list[str], style: str | None,
               aspect_ratio: str | None, variant_count: int, provider: str, model: str | None) -> dict:
        if not project_name.strip() or not prompt.strip():
            raise ValueError("Project name and prompt are required.")
        if not 1 <= int(variant_count) <= 16:
            raise ValueError("Variant count must be between 1 and 16.")
        suffix = uuid.uuid4().hex
        project_id, request_id, run_id, task_id = (f"project-{suffix}", f"request-{suffix}", f"run-{suffix}", f"task-{suffix}")
        now = utc_now()
        project = {"schema_version": "1.0.0", "project_id": project_id, "name": project_name.strip()[:200], "brief": brief[:10000], "tags": [], "created_at": now}
        self.store.create_project(project)
        self.store.save_task({"task_id": task_id, "workflow_id": self.workflow_id, "brief": brief, "prompt": prompt})
        self.store.create_run(run_id, task_id, self.workflow_id)
        self.store.append_event(run_id, "run.created", "queued", {"project_id": project_id, "request_id": request_id})

        selected = self.registry.get(provider)
        caps = selected.capabilities()
        error = None
        approval_id = None
        status = "awaiting_approval"
        supported = caps.available
        if not caps.available:
            status = "blocked"
            error = {"code": "PROVIDER_UNAVAILABLE", "message": "Requested image provider is unavailable.", "retryable": False}
        elif model and caps.models and model not in caps.models:
            supported = False
            status = "blocked"
            error = {"code": "CAPABILITY_UNSUPPORTED", "message": "Requested model is unsupported.", "retryable": False}
        elif aspect_ratio and caps.aspect_ratios and aspect_ratio not in caps.aspect_ratios:
            supported = False
            status = "blocked"
            error = {"code": "CAPABILITY_UNSUPPORTED", "message": "Requested aspect ratio is unsupported.", "retryable": False}
        elif variant_count > caps.max_variants:
            supported = False
            status = "blocked"
            error = {"code": "CAPABILITY_UNSUPPORTED", "message": "Requested variant count exceeds provider capability.", "retryable": False}

        request = {
            "schema_version": "1.0.0", "request_id": request_id, "project_id": project_id, "run_id": run_id,
            "prompt": prompt, "references": list(references), "style": style, "aspect_ratio": aspect_ratio,
            "variant_count": int(variant_count), "provider": provider, "model": model, "status": status,
            "attempt_status": "not_attempted", "error": error, "approval_id": None, "created_at": now,
        }
        if supported:
            approval_id = f"approval-{uuid.uuid4().hex}"
            scope = {"action": "execute_image_provider", "project_id": project_id, "request_id": request_id, "run_id": run_id, "provider": provider}
            self.store.create_approval(approval_id, run_id, "execute_image_provider", scope, "External image provider execution requires explicit approval.")
            request["approval_id"] = approval_id
            self.store.append_event(run_id, "approval.requested", status, {"approval_id": approval_id, "scope": scope, "external_action": True})
        else:
            self.store.append_event(run_id, "image.generation.blocked", status, {"attempted": False, "error": error})
        self.store.save_generation_request(request)
        return {"project_id": project_id, "request_id": request_id, "run_id": run_id, "approval_id": approval_id, "status": status}

    def execute(self, request_id: str, approval_id: str) -> dict:
        request = self.store.get_generation_request(request_id)
        if request is None or request.get("approval_id") != approval_id:
            raise ValueError("Matching generation approval is required.")
        approval = self.store.get_approval(approval_id)
        expected_scope = {"action": "execute_image_provider", "project_id": request["project_id"], "request_id": request_id, "run_id": request["run_id"], "provider": request["provider"]}
        if approval is None or approval["status"] != "approved" or approval["scope"] != expected_scope:
            raise ValueError("Approved matching generation approval is required.")
        if request["attempt_status"] != "not_attempted":
            raise ValueError("Generation request has already been attempted.")
        provider = self.registry.get(request["provider"])
        if not provider.capabilities().available:
            raise ValueError("Approved provider is no longer available.")
        self.store.append_event(request["run_id"], "image.provider.started", "running", {"request_id": request_id, "provider": request["provider"], "attempted": True})
        try:
            result = provider.generate(request)
            status = result.status if result.status in {"partial", "completed", "failed", "cancelled"} else "failed"
            error = result.error
            importer = LocalImageImporter(self.root / "runtime" / "artifacts", self.store)
            for index, output in enumerate(result.outputs):
                importer.import_generated(
                    project_id=request["project_id"], request_id=request_id, run_id=request["run_id"],
                    data=output["data"], mime_type=output["mime_type"], name=output.get("name", f"variant-{index}"),
                    variant_index=index, evidence=output.get("evidence", {}), parent_asset_id=output.get("parent_asset_id"),
                )
        except Exception as exc:
            status, error = "failed", normalize_provider_error(exc)
        updated = self.store.update_generation_request(request_id, status=status, attempt_status="attempted", error=error)
        self.store.append_event(request["run_id"], "image.provider.finished", status, {"request_id": request_id, "attempted": True, "error": error})
        return updated
