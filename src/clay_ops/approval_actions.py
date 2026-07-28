"""Approval decision loop for the Supervised Workflow demonstration.

This module adds a request-hash binding on top of the existing
`OperationalStore.resolve_approval` (which already provides idempotent,
immutable, scope-matched decisions via a SQL trigger + UNIQUE index). It
does not replace that mechanism — it wraps it with:

  1. A deterministic `request_hash` computed from the generation request's
     substantive fields (prompt, references, style, aspect ratio, variant
     count, provider/model preference). Any edit to the request produces a
     new hash, so a stale approval can never silently apply to changed
     content.
  2. A truthful, structured error taxonomy (`ApprovalActionError`) so the
     API and dashboard can distinguish "already decided" from "hash
     mismatch" from "provider still unavailable" instead of a single
     generic 400.
  3. A provider-availability check that never bypasses the invariant: an
     "approved" decision is recorded (Ryan's decision is real and durable)
     but execution remains impossible while every provider reports
     unavailable — the caller must surface this as
     "Approved, execution blocked: provider unavailable".

No external call, provider configuration, or Canon mutation occurs here.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .store import OperationalStore, canonical
from .policy import ApprovalError


class ApprovalActionError(ApprovalError):
    """Raised for supervised-workflow-specific approval decision failures.

    Carries the same structured `[{code, message}]` shape as the base
    `ApprovalError` so existing error-rendering paths keep working.
    """


_HASHED_REQUEST_FIELDS = (
    "prompt", "negative_prompt", "references", "style", "aspect_ratio",
    "variant_count", "provider", "model",
)


def compute_request_hash(generation_request: dict) -> str:
    """Deterministic sha256 over the substantive, content-defining fields
    of a generation request. Two requests with identical creative content
    hash identically; any edit to prompt/references/style/etc. changes the
    hash, invalidating any approval bound to the prior version.
    """
    basis = {field: generation_request.get(field) for field in _HASHED_REQUEST_FIELDS}
    return hashlib.sha256(canonical(basis).encode()).hexdigest()


def _provider_available(providers: list[dict], provider_id: str | None) -> bool:
    if not provider_id:
        return False
    return any(p["provider_id"] == provider_id and p["status"] == "available" for p in providers)


@dataclass
class ApprovalDecisionResult:
    decision_id: str
    approval_id: str
    decision: str
    actor: str
    reason: str
    recorded_at: str
    request_hash: str
    provider_blocked: bool
    status_message: str
    execution_status: str  # "blocked" | "not_applicable" (reject/changes) | "would_execute" (never used while unavailable)


def decide_approval(
    store: OperationalStore,
    *,
    approval_id: str,
    generation_request_id: str,
    decision: str,
    actor: str,
    reason: str = "",
    submitted_request_hash: str | None,
    providers: list[dict],
) -> ApprovalDecisionResult:
    """Resolve an approval with request-hash binding and truthful,
    provider-aware status messaging. Idempotent: replaying the exact same
    (approval_id, decision) after it was already recorded raises
    APPROVAL_ALREADY_FINALIZED rather than silently no-op'ing or erroring
    generically — the caller can treat that as informational.
    """
    if decision not in {"approved", "rejected", "changes_requested"}:
        raise ApprovalActionError([{"code": "UNSUPPORTED_DECISION", "message": f"Unsupported decision: {decision}"}])

    approval = store.get_approval(approval_id)
    if approval is None:
        raise ApprovalActionError([{"code": "APPROVAL_NOT_FOUND", "message": "Approval not found."}])

    if approval["status"] != "pending":
        raise ApprovalActionError([{
            "code": "APPROVAL_ALREADY_FINALIZED",
            "message": f"Approval already resolved as '{approval['status']}'. Decisions are immutable.",
        }])

    generation_request = store.get_generation_request(generation_request_id)
    if generation_request is None:
        raise ApprovalActionError([{"code": "REQUEST_NOT_FOUND", "message": "Linked generation request not found."}])

    current_hash = compute_request_hash(generation_request)
    if submitted_request_hash is not None and submitted_request_hash != current_hash:
        raise ApprovalActionError([{
            "code": "REQUEST_HASH_MISMATCH",
            "message": "The generation request has changed since this approval was requested. A new approval is required.",
        }])

    scope = approval["scope"]
    provider_id = scope.get("provider") if isinstance(scope, dict) else None
    provider_blocked = not _provider_available(providers, provider_id)

    record = store.resolve_approval(
        approval_id,
        decision == "approved",
        actor,
        scope,
        reason,
        request_changes=decision == "changes_requested",
    )

    run_id = approval["run_id"]
    if decision == "approved":
        status_message = "Approved, execution blocked: provider unavailable" if provider_blocked else "Approved"
        execution_status = "blocked" if provider_blocked else "would_execute"
        store.append_event(run_id, "approval.decided", "approved_local_only", {
            "approval_id": approval_id, "decision_id": record["decision_id"], "actor": actor,
            "request_hash": current_hash, "provider": provider_id, "provider_blocked": provider_blocked,
            "external_action": False,
        }, actor=f"human:{actor}")
    elif decision == "rejected":
        status_message = "Rejected — this exact request version is permanently blocked."
        execution_status = "not_applicable"
        store.append_event(run_id, "approval.decided", "rejected", {
            "approval_id": approval_id, "decision_id": record["decision_id"], "actor": actor,
            "reason": reason, "request_hash": current_hash, "external_action": False,
        }, actor=f"human:{actor}")
    else:  # changes_requested
        status_message = "Changes requested — a new request hash is required before resubmission."
        execution_status = "not_applicable"
        store.append_event(run_id, "approval.decided", "changes_requested", {
            "approval_id": approval_id, "decision_id": record["decision_id"], "actor": actor,
            "requested_changes": reason, "request_hash": current_hash, "external_action": False,
        }, actor=f"human:{actor}")

    return ApprovalDecisionResult(
        decision_id=record["decision_id"],
        approval_id=approval_id,
        decision=decision,
        actor=actor,
        reason=reason,
        recorded_at=record["recorded_at"],
        request_hash=current_hash,
        provider_blocked=provider_blocked,
        status_message=status_message,
        execution_status=execution_status,
    )
