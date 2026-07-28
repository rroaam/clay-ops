"""Focused tests for the interactive approval decision loop.

Covers: request-hash binding, idempotency/replay rejection, provider-blocked
messaging on approve, permanent block on reject, hash invalidation on
changes-requested, and truthful structured errors. No provider is ever
called and no external side effect occurs.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from clay_ops.approval_actions import ApprovalActionError, compute_request_hash, decide_approval
from clay_ops.provider_capabilities import describe_known_providers
from clay_ops.seed import seed_clay_projects
from clay_ops.store import OperationalStore


UNAVAILABLE_PROVIDERS = describe_known_providers()


def _store(tmp_path: Path) -> OperationalStore:
    store = OperationalStore(tmp_path / "clay_ops.db")
    seed_clay_projects(store)
    return store


def test_request_hash_deterministic_and_changes_with_content():
    a = {"prompt": "x", "references": [], "style": "clay", "aspect_ratio": "1:1", "variant_count": 1, "provider": "unavailable", "model": None}
    b = dict(a)
    assert compute_request_hash(a) == compute_request_hash(b)
    b["prompt"] = "y"
    assert compute_request_hash(a) != compute_request_hash(b)


def test_approve_pending_demo_request_blocked_by_provider():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        outcome = decide_approval(
            store,
            approval_id="approval-clay-morning-demo-draft",
            generation_request_id="request-clay-morning-demo-draft",
            decision="approved",
            actor="Ryan",
            reason="Looks correct.",
            submitted_request_hash=None,
            providers=UNAVAILABLE_PROVIDERS,
        )
        assert outcome.decision == "approved"
        assert outcome.provider_blocked is True
        assert outcome.status_message == "Approved, execution blocked: provider unavailable"
        assert outcome.execution_status == "blocked"

        # Needs-Ryan / projection reflects resolved status now.
        approval = store.get_approval("approval-clay-morning-demo-draft")
        assert approval["status"] == "approved"


def test_replay_same_decision_is_rejected_idempotently():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        decide_approval(
            store, approval_id="approval-clay-morning-demo-draft",
            generation_request_id="request-clay-morning-demo-draft", decision="approved",
            actor="Ryan", reason="ok", submitted_request_hash=None, providers=UNAVAILABLE_PROVIDERS,
        )
        with pytest.raises(ApprovalActionError) as excinfo:
            decide_approval(
                store, approval_id="approval-clay-morning-demo-draft",
                generation_request_id="request-clay-morning-demo-draft", decision="approved",
                actor="Ryan", reason="ok again", submitted_request_hash=None, providers=UNAVAILABLE_PROVIDERS,
            )
        assert excinfo.value.codes == ["APPROVAL_ALREADY_FINALIZED"]


def test_hash_mismatch_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        with pytest.raises(ApprovalActionError) as excinfo:
            decide_approval(
                store, approval_id="approval-clay-morning-demo-draft",
                generation_request_id="request-clay-morning-demo-draft", decision="approved",
                actor="Ryan", reason="ok", submitted_request_hash="deadbeef" * 8,
                providers=UNAVAILABLE_PROVIDERS,
            )
        assert excinfo.value.codes == ["REQUEST_HASH_MISMATCH"]


def test_unknown_approval_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        with pytest.raises(ApprovalActionError) as excinfo:
            decide_approval(
                store, approval_id="approval-does-not-exist",
                generation_request_id="request-clay-morning-demo-draft", decision="approved",
                actor="Ryan", reason="ok", submitted_request_hash=None, providers=UNAVAILABLE_PROVIDERS,
            )
        assert excinfo.value.codes == ["APPROVAL_NOT_FOUND"]


def test_reject_permanently_blocks_the_request_version():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        outcome = decide_approval(
            store, approval_id="approval-clay-morning-demo-draft",
            generation_request_id="request-clay-morning-demo-draft", decision="rejected",
            actor="Ryan", reason="Not on brief.", submitted_request_hash=None, providers=UNAVAILABLE_PROVIDERS,
        )
        assert outcome.decision == "rejected"
        assert outcome.execution_status == "not_applicable"
        assert "permanently blocked" in outcome.status_message
        approval = store.get_approval("approval-clay-morning-demo-draft")
        assert approval["status"] == "rejected"
        # Replay must still be rejected — rejection is final, not resumable.
        with pytest.raises(ApprovalActionError) as excinfo:
            decide_approval(
                store, approval_id="approval-clay-morning-demo-draft",
                generation_request_id="request-clay-morning-demo-draft", decision="approved",
                actor="Ryan", reason="changed my mind", submitted_request_hash=None, providers=UNAVAILABLE_PROVIDERS,
            )
        assert excinfo.value.codes == ["APPROVAL_ALREADY_FINALIZED"]


def test_request_changes_invalidates_current_hash_binding():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        request = store.get_generation_request("request-clay-morning-demo-draft")
        original_hash = compute_request_hash(request)
        outcome = decide_approval(
            store, approval_id="approval-clay-morning-demo-draft",
            generation_request_id="request-clay-morning-demo-draft", decision="changes_requested",
            actor="Ryan", reason="Please adjust lighting direction.", submitted_request_hash=None,
            providers=UNAVAILABLE_PROVIDERS,
        )
        assert outcome.decision == "changes_requested"
        assert outcome.request_hash == original_hash
        assert "new request hash is required" in outcome.status_message
        approval = store.get_approval("approval-clay-morning-demo-draft")
        assert approval["status"] == "changes_requested"


def test_unsupported_decision_value_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(Path(tmp))
        with pytest.raises(ApprovalActionError) as excinfo:
            decide_approval(
                store, approval_id="approval-clay-morning-demo-draft",
                generation_request_id="request-clay-morning-demo-draft", decision="maybe",
                actor="Ryan", reason="", submitted_request_hash=None, providers=UNAVAILABLE_PROVIDERS,
            )
        assert excinfo.value.codes == ["UNSUPPORTED_DECISION"]
