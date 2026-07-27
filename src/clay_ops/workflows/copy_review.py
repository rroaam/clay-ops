from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from ..artifacts import ArtifactStore
from ..canon import CanonRegistry
from ..contracts import ContractError, validate_document
from ..store import SCHEMA_VERSION, utc_now

_OBVIOUS = re.compile(r"\b(cure[sd]?|guarantee[sd]?|prevent[sd]?|treat[sd]?|reverse[sd]?|eliminate[sd]?|never need medication)\b", re.I)
_HEALTHCARE = re.compile(r"\b(improv(?:e|es|ed|ing)|health outcomes?|metabolic|blood pressure|weight loss|reduce[sd]? risk|sleep quality|clinical outcome)\b", re.I)


class CopyReviewWorkflow:
    def __init__(self, ops_root: Path, store, artifact_root: Path):
        self.ops_root = Path(ops_root).resolve()
        self.store = store
        self.artifacts = ArtifactStore(artifact_root, store)
        self.canon = CanonRegistry(self.ops_root)

    def run(self, *, text: str | None = None, source_reference: str | None = None, target_surface: str, acceptance_criteria: list[str], canon_reference_ids: list[str], source_provenance: dict):
        with self.store.transaction():
            return self._run(
                text=text,
                source_reference=source_reference,
                target_surface=target_surface,
                acceptance_criteria=acceptance_criteria,
                canon_reference_ids=canon_reference_ids,
                source_provenance=source_provenance,
            )

    def _run(self, *, text: str | None = None, source_reference: str | None = None, target_surface: str, acceptance_criteria: list[str], canon_reference_ids: list[str], source_provenance: dict):
        proposed = self._load_input(text, source_reference)
        if not proposed.strip():
            raise ContractError([{"code": "EMPTY_COPY_INPUT", "message": "Proposed copy cannot be empty."}])
        if not target_surface.strip():
            raise ContractError([{"code": "TARGET_SURFACE_REQUIRED", "message": "Target surface is required."}])
        if not source_provenance:
            raise ContractError([{"code": "MISSING_INPUT_PROVENANCE", "message": "Input provenance is required."}])

        task_id = f"task-{uuid.uuid4().hex}"
        run_id = f"run-{uuid.uuid4().hex}"
        result_id = f"result-{uuid.uuid4().hex}"
        content_hash = hashlib.sha256(proposed.encode()).hexdigest()
        packet = {
            "schema_version": SCHEMA_VERSION,
            "packet_type": "TASK_PACKET",
            "task_id": task_id,
            "workflow_id": "copy-review",
            "title": f"Review copy for {target_surface}",
            "acceptance_criteria": acceptance_criteria,
            "assigned_agent": "clay-copy-reviewer",
            "allowed_tools": ["canon-read", "local-validator", "ops-store-write"],
            "source_of_truth": "canonical-references",
            "canon_reference_ids": canon_reference_ids,
            "requested_actions": ["local_review"],
            "write_scope": ["runtime"],
            "approval": {"status": "not_requested", "approver": None},
            "safety": {"external_side_effects": False, "credentials": False, "canon_writes": False, "deployment": False, "member_data": False},
            "input": {
                "proposed_text": None,
                "source_reference": source_reference,
                "content_sha256": content_hash,
                "target_surface": target_surface,
                "source_provenance": source_provenance,
            },
        }
        validate_document("task-packet", packet, self.ops_root / "schemas")
        refs = self.canon.resolve_many(canon_reference_ids)

        self.store.save_task(packet)
        self.store.create_run(run_id, task_id, "copy-review", "structured")
        self.store.append_event(run_id, "run.created", "queued", {"task_id": task_id, "execution_mode": "structured"})
        self.store.append_event(run_id, "task.validated", "running", {"content_sha256": content_hash, "target_surface": target_surface})
        snapshots = []
        for ref in refs:
            snapshots.append({"snapshot_id": self.store.snapshot_canon(run_id, ref), "reference_id": ref["id"], "git_commit": ref["git_commit"], "blob_hash": ref["blob_hash"], "content_sha256": ref["content_sha256"], "authority_class": ref["authority_class"]})
        self.store.append_event(run_id, "canon.resolved", "running", {"references": snapshots})

        obvious = sorted({m.group(0).lower() for m in _OBVIOUS.finditer(proposed)})
        healthcare_claim = bool(_HEALTHCARE.search(proposed))
        clinical_authority = any(ref["authority_class"] == "approved-clinical-claims" for ref in refs)
        em_dash_count = proposed.count("—")
        brand_ok = any(ref["authority_class"] == "brand-design-law" for ref in refs)
        tone_ok = any(ref["authority_class"] in {"tone-language-law", "copy-constraint-law"} for ref in refs)

        scan = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "input_content_sha256": content_hash,
            "target_surface": target_surface,
            "source_provenance": source_provenance,
            "obvious_unsupported_claim_matches": obvious,
            "healthcare_or_outcome_claim_detected": healthcare_claim,
            "named_approved_claims_authority_resolved": clinical_authority,
            "em_dash_count": em_dash_count,
            "canon_snapshots": snapshots,
        }
        artifact = self.artifacts.write_json(run_id, f"{run_id}/evidence/copy-scan.json", scan)
        evidence_ref = artifact["ref"]

        healthcare_status = "pass" if not healthcare_claim or clinical_authority else "needs_human_review"
        gate_results = [
            {"gate_id": "input-provenance", "status": "pass", "reason": "Input hash, target surface, and source provenance recorded.", "evidence_refs": [evidence_ref]},
            {"gate_id": "canon-pinning", "status": "pass", "reason": "All selected canon references resolved read-only at pinned Git objects and content hashes.", "evidence_refs": [evidence_ref]},
            {"gate_id": "unsupported-health-claim", "status": "fail" if obvious else "pass", "reason": "Obvious unsupported claim language detected." if obvious else "No obvious unsupported claim pattern detected.", "evidence_refs": [evidence_ref]},
            {"gate_id": "healthcare-authority", "status": healthcare_status, "reason": "Healthcare or outcome language lacks a named approved clinical claims authority." if healthcare_status == "needs_human_review" else "No unresolved healthcare authority requirement was triggered.", "evidence_refs": [evidence_ref]},
            {"gate_id": "em-dash", "status": "fail" if em_dash_count else "pass", "reason": f"Found {em_dash_count} em dash character(s)." if em_dash_count else "No em dash found.", "evidence_refs": [evidence_ref]},
            {"gate_id": "brand-design-reference", "status": "pass" if brand_ok else "fail", "reason": "Pinned DESIGN.md authority resolved." if brand_ok else "Pinned brand/design authority is missing.", "evidence_refs": [evidence_ref]},
            {"gate_id": "tone-reference", "status": "pass" if tone_ok else "fail", "reason": "Pinned tone/language authority resolved." if tone_ok else "Pinned tone/language authority is missing.", "evidence_refs": [evidence_ref]},
        ]
        failed = any(g["status"] == "fail" for g in gate_results)
        status = "fail" if failed else "awaiting_approval"
        recommendation = self._recommend(proposed, obvious, healthcare_status, em_dash_count)
        approval = None
        approval_status = "not_requested"
        if not failed:
            approval_id = f"approval-{uuid.uuid4().hex}"
            scope = {"run_id": run_id, "result_id": result_id, "action": "review_acceptance"}
            approval = self.store.create_approval(approval_id, run_id, "review_acceptance", scope, "Accept or reject this review record only; no copy edit or publication will occur.")
            approval_status = "pending"
            gate_results.append({"gate_id": "review-acceptance", "status": "held", "reason": "Ryan review acceptance is pending; this cannot create clinical authority.", "evidence_refs": [evidence_ref]})

        result = {
            "schema_version": SCHEMA_VERSION,
            "packet_type": "RESULT_PACKET",
            "result_id": result_id,
            "task_id": task_id,
            "run_id": run_id,
            "workflow_id": "copy-review",
            "status": status,
            "summary": "Copy failed one or more deterministic gates." if failed else "Copy review completed and is awaiting Ryan's acceptance of the review record.",
            "gate_results": gate_results,
            "evidence": [{"kind": "copy-scan", "ref": evidence_ref, "sha256": artifact["sha256"]}],
            "outputs": {"recommended_revision": recommendation, "input_content_sha256": content_hash, "target_surface": target_surface, "source_provenance": source_provenance, "canon_snapshot_ids": [s["snapshot_id"] for s in snapshots]},
            "approval_required": not failed,
            "approval_status": approval_status,
            "canon_mutations": [],
            "external_side_effects": [],
            "completed_at": utc_now(),
        }
        validate_document("result-packet", result, self.ops_root / "schemas")
        self.store.save_result(result_id, run_id, task_id, result, completed=True)
        self.store.append_event(run_id, "gates.completed", status, {"gate_results": gate_results, "evidence_ref": evidence_ref})
        if approval:
            self.store.append_event(run_id, "approval.requested", "awaiting_approval", {"approval_id": approval["approval_id"], "action": "review_acceptance", "scope": approval["scope"]})
        else:
            self.store.append_event(run_id, "result.completed", "fail", {"result_id": result_id, "evidence_ref": evidence_ref})
        return {"task_packet": packet, "result_packet": result, "approval": approval, "events": self.store.list_events(run_id)}

    @staticmethod
    def _load_input(text, source_reference):
        if (text is None) == (source_reference is None):
            raise ContractError([{"code": "COPY_INPUT_EXCLUSIVE", "message": "Provide exactly one of direct text or a local read-only source reference."}])
        if text is not None:
            return text
        path = Path(source_reference).expanduser()
        if path.is_symlink() or not path.is_file():
            raise ContractError([{"code": "SOURCE_REFERENCE_INVALID", "message": "Source reference must be an existing non-symlink local file."}])
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _recommend(text, obvious, healthcare_status, em_dash_count):
        if not obvious and healthcare_status == "pass" and not em_dash_count:
            return None
        revised = text.replace("—", "-")
        for term in obvious:
            revised = re.sub(re.escape(term), "supports", revised, flags=re.I)
        if healthcare_status == "needs_human_review":
            return "Route the healthcare/outcome statement to a named approved clinical claims authority; until then, rewrite as a non-outcome description of the service."
        return revised
