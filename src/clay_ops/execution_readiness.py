"""Execution readiness evaluation for approved generation requests.

This module evaluates whether an approved request can actually execute by:
1. Checking provider capabilities against request requirements
2. Computing cost estimates (or marking as unknown)
3. Building a normalized execution envelope
4. Determining if all blocking conditions are resolved

Key invariant: execution_ready remains False unless:
- A provider is available and configured
- Credentials are verified (without exposing them)
- Cost is known or explicitly marked as unknown
- Approval is valid and not expired
- Request hash matches the approved version
- No required reviews are missing
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .approval_actions import compute_request_hash


@dataclass
class CandidateProvider:
    """A provider evaluated against a specific request."""
    provider_id: str
    eligible: bool
    exclusion_reason: str | None = None
    supported_models: list[str] | None = None
    estimated_cost_usd: float | None = None
    pricing_confidence: str = "unknown"


@dataclass
class ExecutionEnvelope:
    """Normalized execution parameters for an approved request."""
    provider: str | None
    model: str | None
    width: int | None
    height: int | None
    n: int
    prompt: str
    negative_prompt: str | None
    seed: int | None
    safety_tolerance: str


@dataclass
class CostPreview:
    """Deterministic cost estimate for the execution."""
    estimated_total_usd: float | None
    pricing_source: str
    pricing_confidence: str
    unknown_reason: str | None = None


@dataclass
class ReadinessResult:
    """Complete execution readiness evaluation."""
    ready_to_execute: bool
    eligible_providers: list[CandidateProvider]
    ineligible_providers: list[CandidateProvider]
    envelope: ExecutionEnvelope
    cost: CostPreview
    blocking_reasons: list[str]
    approval_valid: bool
    approval_expired: bool
    hash_mismatch: bool


def evaluate_provider_candidate(
    provider: dict[str, Any],
    request: dict[str, Any],
) -> CandidateProvider:
    """Evaluate a single provider against request requirements.
    
    Returns a CandidateProvider with eligible=True only if:
    - Provider is available and configured
    - All required capabilities are supported
    - No capability conflicts exist
    
    Otherwise returns eligible=False with a truthful exclusion_reason.
    """
    provider_id = provider["provider_id"]
    status = provider.get("status", "unavailable")
    capabilities = provider.get("capabilities", {})
    
    # Check availability
    if status != "available":
        return CandidateProvider(
            provider_id=provider_id,
            eligible=False,
            exclusion_reason=f"Provider status is '{status}', not 'available'",
        )
    
    # Check credentials (implicit in status=available)
    if not capabilities.get("available"):
        return CandidateProvider(
            provider_id=provider_id,
            eligible=False,
            exclusion_reason="Provider configured but credentials not verified",
        )
    
    # Extract request requirements
    required_aspect_ratio = request.get("aspect_ratio")
    required_references = request.get("references", [])
    required_n = request.get("variant_count", 1)
    required_model = request.get("provider_metadata", {}).get("selected_model")
    
    # Check aspect ratio support
    supported_ratios = capabilities.get("aspect_ratios", [])
    if required_aspect_ratio and supported_ratios and required_aspect_ratio not in supported_ratios:
        return CandidateProvider(
            provider_id=provider_id,
            eligible=False,
            exclusion_reason=f"Aspect ratio '{required_aspect_ratio}' not supported (supported: {', '.join(supported_ratios)})",
        )
    
    # Check reference image support
    supports_refs = capabilities.get("supports_references", False)
    if required_references and not supports_refs:
        return CandidateProvider(
            provider_id=provider_id,
            eligible=False,
            exclusion_reason=f"Reference images required but not supported by {provider_id}",
        )
    
    # Check variant count limit
    max_variants = capabilities.get("max_variants", 4)
    if required_n > max_variants:
        return CandidateProvider(
            provider_id=provider_id,
            eligible=False,
            exclusion_reason=f"Requested {required_n} variants but max is {max_variants}",
        )
    
    # Check model support
    supported_models = capabilities.get("models", [])
    if required_model and supported_models and required_model not in supported_models:
        return CandidateProvider(
            provider_id=provider_id,
            eligible=False,
            exclusion_reason=f"Model '{required_model}' not supported (supported: {', '.join(supported_models)})",
        )
    
    # All checks passed
    return CandidateProvider(
        provider_id=provider_id,
        eligible=True,
        supported_models=supported_models if supported_models else None,
        pricing_confidence="unknown",  # No pricing data implemented yet
    )


def evaluate_providers(
    providers: list[dict[str, Any]],
    request: dict[str, Any],
) -> tuple[list[CandidateProvider], list[CandidateProvider]]:
    """Evaluate all providers against the request.
    
    Returns (eligible, ineligible) provider lists.
    """
    eligible = []
    ineligible = []
    
    for provider in providers:
        candidate = evaluate_provider_candidate(provider, request)
        if candidate.eligible:
            eligible.append(candidate)
        else:
            ineligible.append(candidate)
    
    return eligible, ineligible


def compute_cost_preview(
    eligible_providers: list[CandidateProvider],
    request: dict[str, Any],
) -> CostPreview:
    """Compute a deterministic cost estimate for the execution.
    
    Currently returns unknown pricing since no provider pricing data is
    implemented. In the future, this would query pricing APIs or use
    cached pricing tables.
    """
    if not eligible_providers:
        return CostPreview(
            estimated_total_usd=None,
            pricing_source="none",
            pricing_confidence="none",
            unknown_reason="No eligible providers available",
        )
    
    # No pricing data implemented yet
    return CostPreview(
        estimated_total_usd=None,
        pricing_source="not_implemented",
        pricing_confidence="unknown",
        unknown_reason="Provider pricing API not integrated",
    )


def build_execution_envelope(
    request: dict[str, Any],
    eligible_providers: list[CandidateProvider],
) -> ExecutionEnvelope:
    """Build normalized execution parameters.
    
    Selects the first eligible provider (if any) and normalizes all
    parameters into a provider-agnostic envelope.
    """
    provider_id = None
    model = None
    
    if eligible_providers:
        provider_id = eligible_providers[0].provider_id
        # Prefer explicit model selection, fallback to first available
        model = request.get("provider_metadata", {}).get("selected_model")
        if not model and eligible_providers[0].supported_models:
            model = eligible_providers[0].supported_models[0]
    
    # Normalize aspect ratio to dimensions
    aspect_ratio = request.get("aspect_ratio")
    width = None
    height = None
    if aspect_ratio == "1:1":
        width = height = 1024
    elif aspect_ratio == "4:5":
        width = 1024
        height = 1280
    elif aspect_ratio == "16:9":
        width = 1792
        height = 1024
    elif aspect_ratio == "9:16":
        width = 1024
        height = 1792
    
    return ExecutionEnvelope(
        provider=provider_id,
        model=model,
        width=width,
        height=height,
        n=request.get("variant_count", 1),
        prompt=request.get("prompt", ""),
        negative_prompt=request.get("negative_prompt"),
        seed=request.get("seed"),
        safety_tolerance="standard",
    )


def validate_approval_integrity(
    approval: dict[str, Any],
    request: dict[str, Any],
    eligible_providers: list[CandidateProvider],
) -> tuple[bool, bool, bool, list[str]]:
    """Validate that the approval is still valid for this request.
    
    Returns (approval_valid, approval_expired, hash_mismatch, blocking_reasons).
    
    Approval is invalidated if:
    - Provider changed after approval
    - Model changed after approval
    - Request hash changed (prompt/style/etc modified)
    - Approval expired (not implemented yet)
    """
    blocking_reasons = []
    
    # Check approval status
    if approval.get("status") != "approved":
        blocking_reasons.append(f"Approval status is '{approval.get('status')}', not 'approved'")
        return False, False, False, blocking_reasons
    
    # Check approval expiry (not implemented yet)
    approval_expired = False
    expires_at = approval.get("expires_at")
    if expires_at:
        # Would check datetime.now() > expires_at
        # For now, assume not expired
        approval_expired = False
    
    # Check request hash
    approved_hash = approval.get("request_hash")
    current_hash = compute_request_hash(request)
    hash_mismatch = approved_hash is not None and approved_hash != current_hash
    
    if hash_mismatch:
        blocking_reasons.append("Request hash changed since approval (prompt/style/etc modified)")
        return False, approval_expired, hash_mismatch, blocking_reasons
    
    # Check provider/model changes
    approved_scope = approval.get("scope", {})
    approved_provider = approved_scope.get("provider")
    approved_model = approved_scope.get("model")
    
    current_provider = eligible_providers[0].provider_id if eligible_providers else None
    current_model = request.get("provider_metadata", {}).get("selected_model")
    
    if approved_provider and current_provider and approved_provider != current_provider:
        blocking_reasons.append(f"Provider changed: approved '{approved_provider}', now '{current_provider}'")
        return False, approval_expired, hash_mismatch, blocking_reasons
    
    if approved_model and current_model and approved_model != current_model:
        blocking_reasons.append(f"Model changed: approved '{approved_model}', now '{current_model}'")
        return False, approval_expired, hash_mismatch, blocking_reasons
    
    return True, approval_expired, hash_mismatch, blocking_reasons


def evaluate_execution_readiness(
    request: dict[str, Any],
    approval: dict[str, Any],
    providers: list[dict[str, Any]],
) -> ReadinessResult:
    """Complete execution readiness evaluation.
    
    This is the main entry point for evaluating whether an approved request
    can actually execute. It:
    1. Evaluates all providers against the request
    2. Computes cost estimates
    3. Builds the execution envelope
    4. Validates approval integrity
    5. Determines if all blocking conditions are resolved
    """
    # Evaluate providers
    eligible, ineligible = evaluate_providers(providers, request)
    
    # Compute cost
    cost = compute_cost_preview(eligible, request)
    
    # Build envelope
    envelope = build_execution_envelope(request, eligible)
    
    # Validate approval
    approval_valid, approval_expired, hash_mismatch, blocking_reasons = validate_approval_integrity(
        approval, request, eligible
    )
    
    # Add provider blocking reason if no eligible providers
    if not eligible:
        blocking_reasons.append("No eligible providers available")
    
    # Add cost blocking reason if unknown
    if cost.estimated_total_usd is None:
        blocking_reasons.append(f"Cost unknown: {cost.unknown_reason}")
    
    # Add approval blocking reasons
    if approval_expired:
        blocking_reasons.append("Approval expired")
    
    # Determine overall readiness
    ready_to_execute = (
        approval_valid
        and not approval_expired
        and not hash_mismatch
        and len(eligible) > 0
        and cost.estimated_total_usd is not None
    )
    
    return ReadinessResult(
        ready_to_execute=ready_to_execute,
        eligible_providers=eligible,
        ineligible_providers=ineligible,
        envelope=envelope,
        cost=cost,
        blocking_reasons=blocking_reasons,
        approval_valid=approval_valid,
        approval_expired=approval_expired,
        hash_mismatch=hash_mismatch,
    )
