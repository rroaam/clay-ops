"""Focused tests for the composite Supervised Workflow projection.

Verifies: real demo project/request/context/approval are linked into
`supervised_workflow`, the approval stays pending, the provider stays
blocked, and the evidence timeline reflects the true state — no
fabricated execution or provider connection.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from clay_ops.images import ImageProviderRegistry
from clay_ops.projection import ProjectionService
from clay_ops.seed import seed_clay_projects
from clay_ops.store import OperationalStore


def _make_projection(tmp_path: Path) -> ProjectionService:
    store = OperationalStore(tmp_path / "clay_ops.db")
    seed_clay_projects(store)
    return ProjectionService(tmp_path, store, ImageProviderRegistry())


def test_supervised_workflow_present_in_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        snapshot = projection.snapshot()
        assert "supervised_workflow" in snapshot
        sw = snapshot["supervised_workflow"]
        assert set(sw.keys()) == {
            "active_build", "source_registry", "advisor_board",
            "exact_approval", "evidence_timeline", "demo",
        }


def test_demo_project_and_request_are_real_records():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        sw = projection.snapshot()["supervised_workflow"]
        assert sw["demo"]["project_id"] == "project-clay-image-system"
        assert sw["demo"]["request_id"] == "request-clay-morning-demo-draft"
        assert sw["demo"]["context_id"] == "context-clay-brand-system"
        assert sw["demo"]["approval_id"] == "approval-clay-morning-demo-draft"


def test_provider_remains_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        sw = projection.snapshot()["supervised_workflow"]
        assert sw["demo"]["provider_blocked"] is True
        blocking = {c["condition"]: c["active"] for c in sw["exact_approval"]["blocking_conditions"]}
        assert blocking["provider_unavailable"] is True


def test_approval_remains_pending_not_executed():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        sw = projection.snapshot()["supervised_workflow"]
        approval = sw["exact_approval"]
        assert approval["status"] == "pending"
        assert approval["destination"].startswith("local loopback only")
        blocking = {c["condition"]: c["active"] for c in approval["blocking_conditions"]}
        assert blocking["approval_pending"] is True
        assert blocking["approval_expired_or_rejected"] is False


def test_advisor_board_has_six_roles_and_ryan_pending():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        sw = projection.snapshot()["supervised_workflow"]
        roles = {item["role"] for item in sw["advisor_board"]}
        assert roles == {
            "Hermes", "Brand Steward", "Creative Director",
            "Copy and Claims", "Systems and QA", "Ryan",
        }
        ryan = next(item for item in sw["advisor_board"] if item["role"] == "Ryan")
        assert ryan["review_status"] == "pending"
        assert ryan["decision"] == "pending"


def test_evidence_timeline_ends_with_blocked_and_pending_decision():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        sw = projection.snapshot()["supervised_workflow"]
        steps = [item["step"] for item in sw["evidence_timeline"]]
        assert "blocked_external_action" in steps
        assert "operator_decision" in steps
        blocked_item = next(i for i in sw["evidence_timeline"] if i["step"] == "blocked_external_action")
        assert blocked_item["status"] == "blocked"
        decision_item = next(i for i in sw["evidence_timeline"] if i["step"] == "operator_decision")
        assert decision_item["status"] == "pending"


def test_active_build_locks_claude_owned_files():
    with tempfile.TemporaryDirectory() as tmp:
        projection = _make_projection(Path(tmp))
        sw = projection.snapshot()["supervised_workflow"]
        locked = sw["active_build"]["locked_files"]
        assert any("landing-v5" in f for f in locked)
        assert any("BlueprintDoc.tsx" in f for f in locked)
        assert sw["active_build"]["owner"] == "Claude Code"
