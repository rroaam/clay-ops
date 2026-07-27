from __future__ import annotations
import pytest
from clay_ops.store import OperationalStore
from clay_ops.workflows.copy_review import CopyReviewWorkflow


def run(repo_root,tmp_path,text,canon_ids=("brand-design-law","copy-language-law")):
    store=OperationalStore(tmp_path/"ops.db")
    return CopyReviewWorkflow(repo_root,store,tmp_path/"artifacts").run(text=text,target_surface="homepage",acceptance_criteria=["No unsupported claims"],canon_reference_ids=list(canon_ids),source_provenance={"kind":"direct","label":"test"})


def test_clean_review_awaits_approval_and_never_edits_source(repo_root,tmp_path):
    result=run(repo_root,tmp_path,"A steadier relationship with your health.")
    assert result["result_packet"]["status"] == "awaiting_approval"
    assert result["approval"]["status"] == "pending"
    assert result["result_packet"]["external_side_effects"] == []
    assert result["result_packet"]["canon_mutations"] == []


def test_exact_input_hash_surface_and_provenance_recorded(repo_root,tmp_path):
    result=run(repo_root,tmp_path,"Clear support for daily health decisions.")
    packet=result["task_packet"]
    assert len(packet["input"]["content_sha256"]) == 64
    assert packet["input"]["target_surface"] == "homepage"
    assert packet["input"]["source_provenance"]["label"] == "test"


def test_obvious_unsupported_health_claim_fails(repo_root,tmp_path):
    result=run(repo_root,tmp_path,"Clay cures diabetes and guarantees outcomes.")
    assert result["result_packet"]["status"] == "fail"
    assert next(g for g in result["result_packet"]["gate_results"] if g["gate_id"]=="unsupported-health-claim")["status"] == "fail"


def test_healthcare_claim_without_named_authority_needs_review(repo_root,tmp_path):
    result=run(repo_root,tmp_path,"Clay improves your metabolic health.")
    gate=next(g for g in result["result_packet"]["gate_results"] if g["gate_id"]=="healthcare-authority")
    assert gate["status"] == "needs_human_review"
    assert result["result_packet"]["status"] == "awaiting_approval"


def test_core_product_definition_never_authoritatively_passes_claim(repo_root,tmp_path):
    result=run(repo_root,tmp_path,"Clay improves your health outcomes.",("healthcare-context-insufficient",))
    gate=next(g for g in result["result_packet"]["gate_results"] if g["gate_id"]=="healthcare-authority")
    assert gate["status"] == "needs_human_review"


def test_copy_review_rolls_back_database_state_on_artifact_failure(repo_root, tmp_path, monkeypatch):
    store = OperationalStore(tmp_path / "ops.db")
    workflow = CopyReviewWorkflow(repo_root, store, tmp_path / "artifacts")

    def fail_record(*args, **kwargs):
        raise RuntimeError("simulated artifact DB failure")

    monkeypatch.setattr(store, "record_artifact", fail_record)
    with pytest.raises(RuntimeError, match="simulated artifact DB failure"):
        workflow.run(
            text="A steadier relationship with your health.",
            target_surface="homepage",
            acceptance_criteria=["No unsupported claims"],
            canon_reference_ids=["brand-design-law", "copy-language-law"],
            source_provenance={"kind": "direct", "label": "test"},
        )
    assert store.list_runs() == []
