from __future__ import annotations
import pytest
from clay_ops.contracts import ContractError, validate_document
from clay_ops.redaction import redact
from clay_ops.store import OperationalStore


def test_result_without_task_id_rejected(repo_root):
    packet={"schema_version":"1.0.0","packet_type":"RESULT_PACKET"}
    with pytest.raises(ContractError) as exc: validate_document("result-packet",packet,repo_root/"schemas")
    assert "RESULT_TASK_ID_REQUIRED" in exc.value.codes


def test_false_completion_without_evidence_rejected(repo_root):
    packet={"schema_version":"1.0.0","packet_type":"RESULT_PACKET","result_id":"result-x","task_id":"task-x","run_id":"run-x","workflow_id":"copy-review","status":"pass","summary":"done","gate_results":[],"evidence":[],"outputs":{},"approval_required":False,"approval_status":"not_requested","canon_mutations":[],"external_side_effects":[],"completed_at":"2026-01-01T00:00:00Z"}
    with pytest.raises(ContractError) as exc: validate_document("result-packet",packet,repo_root/"schemas")
    assert "FALSE_COMPLETION_WITHOUT_EVIDENCE" in exc.value.codes


def test_secret_shaped_output_redacted():
    raw="Authorization: Bearer example-secret-value and api_key=example-key-value"
    cleaned=redact(raw)
    assert "example-secret-value" not in cleaned and "example-key-value" not in cleaned
    assert "[REDACTED]" in cleaned


def test_no_dashboard_authority_in_result(repo_root):
    packet={"schema_version":"1.0.0","packet_type":"RESULT_PACKET","result_id":"result-x","task_id":"task-x","run_id":"run-x","workflow_id":"copy-review","status":"awaiting_approval","summary":"review","gate_results":[{"gate_id":"g","status":"held","reason":"hold","evidence_refs":["artifact://x"]}],"evidence":[{"kind":"artifact","ref":"artifact://x","sha256":"0"*64}],"outputs":{"authority":"dashboard"},"approval_required":True,"approval_status":"pending","canon_mutations":[],"external_side_effects":[],"completed_at":"2026-01-01T00:00:00Z"}
    with pytest.raises(ContractError) as exc: validate_document("result-packet",packet,repo_root/"schemas")
    assert "DASHBOARD_NOT_AUTHORITATIVE" in exc.value.codes


def assert_task_code(sample_task, repo_root, mutate, code):
    mutate(sample_task)
    with pytest.raises(ContractError) as exc:
        validate_document("task-packet", sample_task, repo_root / "schemas")
    assert code in exc.value.codes


def test_publish_request_is_forbidden(sample_task, repo_root):
    assert_task_code(sample_task, repo_root, lambda p: p.__setitem__("requested_actions", ["publish"]), "PUBLISH_FORBIDDEN")


def test_deployment_request_is_forbidden(sample_task, repo_root):
    assert_task_code(sample_task, repo_root, lambda p: p.__setitem__("requested_actions", ["deploy"]), "DEPLOYMENT_FORBIDDEN")


def test_credential_request_is_forbidden(sample_task, repo_root):
    assert_task_code(sample_task, repo_root, lambda p: p.__setitem__("requested_actions", ["credential_access"]), "CREDENTIAL_ACCESS_FORBIDDEN")


def test_unknown_agent_is_rejected(sample_task, repo_root):
    assert_task_code(sample_task, repo_root, lambda p: p.__setitem__("assigned_agent", "unknown"), "UNKNOWN_AGENT")


def test_unknown_tool_is_rejected(sample_task, repo_root):
    assert_task_code(sample_task, repo_root, lambda p: p.__setitem__("allowed_tools", ["unknown"]), "UNKNOWN_TOOL")


def test_write_scope_outside_runtime_is_rejected(sample_task, repo_root):
    assert_task_code(sample_task, repo_root, lambda p: p.__setitem__("write_scope", ["../production"]), "WRITE_SCOPE_OUTSIDE_RUNTIME")


def test_missing_result_evidence_has_domain_code(repo_root):
    packet={"schema_version":"1.0.0","packet_type":"RESULT_PACKET","result_id":"result-x","task_id":"task-x","run_id":"run-x","workflow_id":"copy-review","status":"fail","summary":"failed","gate_results":[{"gate_id":"g","status":"fail","reason":"failed","evidence_refs":["artifact://x"]}],"evidence":[],"outputs":{},"approval_required":False,"approval_status":"not_requested","canon_mutations":[],"external_side_effects":[],"completed_at":"2026-01-01T00:00:00Z"}
    with pytest.raises(ContractError) as exc:
        validate_document("result-packet", packet, repo_root / "schemas")
    assert "MISSING_EVIDENCE" in exc.value.codes


def test_worker_canon_mutation_has_domain_code(repo_root):
    packet={"schema_version":"1.0.0","packet_type":"RESULT_PACKET","result_id":"result-x","task_id":"task-x","run_id":"run-x","workflow_id":"copy-review","status":"fail","summary":"failed","gate_results":[{"gate_id":"g","status":"fail","reason":"failed","evidence_refs":["artifact://x"]}],"evidence":[{"kind":"artifact","ref":"artifact://x","sha256":"0"*64}],"outputs":{},"approval_required":False,"approval_status":"not_requested","canon_mutations":[{"attempt":"edit"}],"external_side_effects":[],"completed_at":"2026-01-01T00:00:00Z"}
    with pytest.raises(ContractError) as exc:
        validate_document("result-packet", packet, repo_root / "schemas")
    assert "CANON_MUTATION_FORBIDDEN" in exc.value.codes
