from __future__ import annotations
import copy
import json
import pytest
from jsonschema import Draft202012Validator
from clay_ops.contracts import ContractError, validate_document


def test_schemas_are_full_draft_202012_and_valid(repo_root):
    for path in sorted((repo_root / "schemas").glob("*.schema.json")):
        schema=json.loads(path.read_text())
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)


def test_valid_task_packet(sample_task, repo_root):
    validate_document("task-packet", sample_task, repo_root / "schemas")


def test_schema_version_mismatch_rejected(sample_task, repo_root):
    sample_task["schema_version"]="0.1.0-prototype"
    with pytest.raises(ContractError) as exc:
        validate_document("task-packet", sample_task, repo_root / "schemas")
    assert "SCHEMA_VERSION_MISMATCH" in exc.value.codes


def test_missing_acceptance_criteria_has_domain_code(sample_task, repo_root):
    sample_task["acceptance_criteria"]=[]
    with pytest.raises(ContractError) as exc:
        validate_document("task-packet", sample_task, repo_root / "schemas")
    assert "MISSING_ACCEPTANCE_CRITERIA" in exc.value.codes


def test_missing_input_provenance_rejected(sample_task, repo_root):
    del sample_task["input"]["source_provenance"]
    with pytest.raises(ContractError) as exc:
        validate_document("task-packet", sample_task, repo_root / "schemas")
    assert "MISSING_INPUT_PROVENANCE" in exc.value.codes
