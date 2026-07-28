"""Tests for execution readiness evaluation.

These tests verify that the provider-readiness system correctly:
1. Evaluates provider capabilities against request requirements
2. Computes cost previews (or marks as unknown)
3. Builds normalized execution envelopes
4. Validates approval integrity
5. Determines overall execution readiness

Key invariant: execution_ready remains False unless all conditions are met.
"""
from __future__ import annotations

import pytest

from clay_ops.execution_readiness import (
    build_execution_envelope,
    compute_cost_preview,
    evaluate_execution_readiness,
    evaluate_providers,
    validate_approval_integrity,
)


def make_request(
    prompt="A sculptural matte-ceramic vessel",
    style="clay",
    aspect_ratio="4:5",
    variant_count=3,
    references=None,
    provider_metadata=None,
):
    """Helper to create a normalized request."""
    return {
        "prompt": prompt,
        "style": style,
        "aspect_ratio": aspect_ratio,
        "variant_count": variant_count,
        "references": references or [],
        "provider_metadata": provider_metadata or {},
    }


def make_available_provider(
    provider_id,
    models=("model-v1",),
    aspect_ratios=("1:1", "4:5", "16:9"),
    max_variants=4,
    supports_references=False,
):
    """Helper to create a fully available provider."""
    return {
        "provider_id": provider_id,
        "status": "available",
        "capabilities": {
            "available": True,
            "models": list(models),
            "aspect_ratios": list(aspect_ratios),
            "max_variants": max_variants,
            "supports_references": supports_references,
        },
    }


def make_unavailable_provider(provider_id, reason="No adapter configured"):
    """Helper to create an unavailable provider."""
    return {
        "provider_id": provider_id,
        "status": "unavailable",
        "reason": reason,
        "capabilities": {
            "available": False,
            "models": [],
            "aspect_ratios": [],
            "max_variants": 0,
            "supports_references": False,
        },
    }


def test_evaluate_providers_all_unavailable():
    """When all providers are unavailable, all are marked ineligible."""
    request = make_request()
    providers = [
        make_unavailable_provider("flux"),
        make_unavailable_provider("dall-e"),
    ]
    
    eligible, ineligible = evaluate_providers(providers, request)
    
    assert len(eligible) == 0
    assert len(ineligible) == 2
    assert all(c.eligible is False for c in ineligible)
    assert all("status is 'unavailable'" in c.exclusion_reason for c in ineligible)


def test_evaluate_providers_one_eligible():
    """When one provider is available and supports requirements, it's eligible."""
    request = make_request(aspect_ratio="4:5", variant_count=2)
    providers = [
        make_available_provider("flux", aspect_ratios=("1:1", "4:5"), max_variants=4),
        make_unavailable_provider("dall-e"),
    ]
    
    eligible, ineligible = evaluate_providers(providers, request)
    
    assert len(eligible) == 1
    assert eligible[0].provider_id == "flux"
    assert len(ineligible) == 1
    assert ineligible[0].provider_id == "dall-e"


def test_evaluate_providers_aspect_ratio_not_supported():
    """Provider is ineligible if aspect ratio not supported."""
    request = make_request(aspect_ratio="9:16")
    providers = [
        make_available_provider("flux", aspect_ratios=("1:1", "4:5")),
    ]
    
    eligible, ineligible = evaluate_providers(providers, request)
    
    assert len(eligible) == 0
    assert len(ineligible) == 1
    assert "Aspect ratio '9:16' not supported" in ineligible[0].exclusion_reason


def test_evaluate_providers_references_not_supported():
    """Provider is ineligible if references required but not supported."""
    request = make_request(references=["ref1.png", "ref2.png"])
    providers = [
        make_available_provider("flux", supports_references=False),
    ]
    
    eligible, ineligible = evaluate_providers(providers, request)
    
    assert len(eligible) == 0
    assert len(ineligible) == 1
    assert "Reference images required but not supported" in ineligible[0].exclusion_reason


def test_evaluate_providers_variant_count_exceeded():
    """Provider is ineligible if requested variants exceed max."""
    request = make_request(variant_count=10)
    providers = [
        make_available_provider("flux", max_variants=4),
    ]
    
    eligible, ineligible = evaluate_providers(providers, request)
    
    assert len(eligible) == 0
    assert len(ineligible) == 1
    assert "Requested 10 variants but max is 4" in ineligible[0].exclusion_reason


def test_evaluate_providers_model_not_supported():
    """Provider is ineligible if selected model not in supported list."""
    request = make_request(provider_metadata={"selected_model": "model-v99"})
    providers = [
        make_available_provider("flux", models=("model-v1", "model-v2")),
    ]
    
    eligible, ineligible = evaluate_providers(providers, request)
    
    assert len(eligible) == 0
    assert len(ineligible) == 1
    assert "Model 'model-v99' not supported" in ineligible[0].exclusion_reason


def test_compute_cost_preview_no_eligible_providers():
    """Cost preview is unknown when no eligible providers."""
    request = make_request()
    eligible = []
    
    cost = compute_cost_preview(eligible, request)
    
    assert cost.estimated_total_usd is None
    assert cost.pricing_confidence == "none"
    assert cost.unknown_reason == "No eligible providers available"


def test_compute_cost_preview_eligible_but_no_pricing():
    """Cost preview is unknown when pricing API not integrated."""
    request = make_request()
    eligible = [make_available_provider("flux")]
    
    cost = compute_cost_preview(eligible, request)
    
    assert cost.estimated_total_usd is None
    assert cost.pricing_source == "not_implemented"
    assert cost.pricing_confidence == "unknown"
    assert "Provider pricing API not integrated" in cost.unknown_reason


def test_build_execution_envelope_no_eligible():
    """Envelope has None provider/model when no eligible providers."""
    request = make_request(aspect_ratio="4:5")
    eligible = []
    
    envelope = build_execution_envelope(request, eligible)
    
    assert envelope.provider is None
    assert envelope.model is None
    assert envelope.width == 1024
    assert envelope.height == 1280
    assert envelope.n == 3


def test_build_execution_envelope_with_eligible():
    """Envelope selects first eligible provider and normalizes aspect ratio."""
    request = make_request(aspect_ratio="16:9")
    providers = [make_available_provider("flux", models=("model-v1", "model-v2"))]
    eligible, _ = evaluate_providers(providers, request)
    
    envelope = build_execution_envelope(request, eligible)
    
    assert envelope.provider == "flux"
    assert envelope.model == "model-v1"
    assert envelope.width == 1792
    assert envelope.height == 1024
    assert envelope.n == 3


def test_build_execution_envelope_explicit_model():
    """Envelope uses explicit model selection if provided."""
    request = make_request(
        aspect_ratio="1:1",
        provider_metadata={"selected_model": "model-v2"},
    )
    providers = [make_available_provider("flux", models=("model-v1", "model-v2"))]
    eligible, _ = evaluate_providers(providers, request)
    
    envelope = build_execution_envelope(request, eligible)
    
    assert envelope.model == "model-v2"
    assert envelope.width == 1024
    assert envelope.height == 1024


def test_validate_approval_integrity_approved():
    """Approval is valid when status is approved and no conflicts."""
    from clay_ops.approval_actions import compute_request_hash
    
    request = make_request()
    approval = {
        "status": "approved",
        "request_hash": compute_request_hash(request),
        "scope": {"provider": "flux", "model": "model-v1"},
    }
    providers = [make_available_provider("flux")]
    eligible, _ = evaluate_providers(providers, request)
    
    valid, expired, mismatch, reasons = validate_approval_integrity(approval, request, eligible)
    
    assert valid is True
    assert expired is False
    assert mismatch is False
    assert len(reasons) == 0


def test_validate_approval_integrity_not_approved():
    """Approval is invalid when status is not approved."""
    request = make_request()
    approval = {
        "status": "pending",
        "request_hash": "abc",
        "scope": {},
    }
    eligible = []
    
    valid, expired, mismatch, reasons = validate_approval_integrity(approval, request, eligible)
    
    assert valid is False
    assert "Approval status is 'pending'" in reasons[0]


def test_validate_approval_integrity_hash_mismatch():
    """Approval is invalidated when request hash changed."""
    request = make_request(prompt="Original prompt")
    from clay_ops.approval_actions import compute_request_hash
    original_hash = compute_request_hash(request)
    
    # Modify the request
    request["prompt"] = "Modified prompt"
    
    approval = {
        "status": "approved",
        "request_hash": original_hash,
        "scope": {},
    }
    eligible = []
    
    valid, expired, mismatch, reasons = validate_approval_integrity(approval, request, eligible)
    
    assert valid is False
    assert mismatch is True
    assert "Request hash changed since approval" in reasons[0]


def test_validate_approval_integrity_provider_changed():
    """Provider change invalidates approval."""
    from clay_ops.approval_actions import compute_request_hash
    
    request = make_request(prompt="Test prompt")
    approval = {
        "status": "approved",
        "request_hash": compute_request_hash(request),
        "scope": {"provider": "flux", "model": "model-v1"},
    }
    providers = [make_available_provider("dall-e", models=("dall-e-3",))]
    eligible, ineligible = evaluate_providers(providers, request)
    
    valid, expired, mismatch, reasons = validate_approval_integrity(approval, request, eligible)
    
    assert valid is False
    assert len(reasons) > 0
    # Should mention provider change
    assert any("provider" in reason.lower() for reason in reasons)


def test_validate_approval_integrity_model_changed():
    """Approval is invalidated when model changed after approval."""
    from clay_ops.approval_actions import compute_request_hash
    
    request = make_request(provider_metadata={"selected_model": "model-v2"})
    approval = {
        "status": "approved",
        "request_hash": compute_request_hash(request),
        "scope": {"provider": "flux", "model": "model-v1"},
    }
    providers = [make_available_provider("flux")]
    eligible, _ = evaluate_providers(providers, request)
    
    valid, expired, mismatch, reasons = validate_approval_integrity(approval, request, eligible)
    
    assert valid is False
    assert "Model changed" in reasons[0]


def test_evaluate_execution_readiness_not_ready():
    """Execution is not ready when providers unavailable."""
    request = make_request()
    approval = {
        "status": "approved",
        "request_hash": "abc",
        "scope": {},
    }
    providers = [make_unavailable_provider("flux")]
    
    result = evaluate_execution_readiness(request, approval, providers)
    
    assert result.ready_to_execute is False
    assert len(result.eligible_providers) == 0
    assert len(result.ineligible_providers) == 1
    assert result.envelope.provider is None
    assert result.cost.estimated_total_usd is None
    assert "No eligible providers available" in result.blocking_reasons
    assert any("Cost unknown" in reason for reason in result.blocking_reasons)


def test_evaluate_execution_readiness_ready_if_all_conditions_met():
    """Execution is ready when all conditions are met (except pricing)."""
    from clay_ops.approval_actions import compute_request_hash
    
    request = make_request()
    approval = {
        "status": "approved",
        "request_hash": compute_request_hash(request),
        "scope": {"provider": "flux", "model": "model-v1"},
    }
    providers = [make_available_provider("flux", models=("model-v1",))]
    
    result = evaluate_execution_readiness(request, approval, providers)
    
    # Still not ready because pricing is unknown
    assert result.ready_to_execute is False
    assert len(result.eligible_providers) == 1
    assert result.envelope.provider == "flux"
    assert result.envelope.model == "model-v1"
    assert result.approval_valid is True
    assert any("Cost unknown" in reason for reason in result.blocking_reasons)


def test_evaluate_execution_readiness_approval_invalid_blocks():
    """Execution is not ready when approval is invalid."""
    request = make_request()
    approval = {
        "status": "rejected",
        "request_hash": "abc",
        "scope": {},
    }
    providers = [make_available_provider("flux")]
    
    result = evaluate_execution_readiness(request, approval, providers)
    
    assert result.ready_to_execute is False
    assert result.approval_valid is False
    assert any("Approval status is 'rejected'" in reason for reason in result.blocking_reasons)


def test_evaluate_execution_readiness_hash_mismatch_blocks():
    """Execution is not ready when request hash changed."""
    request = make_request(prompt="Original")
    from clay_ops.approval_actions import compute_request_hash
    original_hash = compute_request_hash(request)
    
    request["prompt"] = "Modified"
    
    approval = {
        "status": "approved",
        "request_hash": original_hash,
        "scope": {},
    }
    providers = [make_available_provider("flux")]
    
    result = evaluate_execution_readiness(request, approval, providers)
    
    assert result.ready_to_execute is False
    assert result.hash_mismatch is True
    assert any("Request hash changed" in reason for reason in result.blocking_reasons)
