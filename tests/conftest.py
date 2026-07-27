from __future__ import annotations
import hashlib
from pathlib import Path
import pytest

@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

@pytest.fixture
def sample_task() -> dict:
    text = "Build a steadier relationship with your health."
    return {
        "schema_version":"1.0.0","packet_type":"TASK_PACKET","task_id":"task-test-001",
        "workflow_id":"copy-review","title":"Review copy","acceptance_criteria":["No unsupported claims"],
        "assigned_agent":"clay-copy-reviewer","allowed_tools":["canon-read","local-validator","ops-store-write"],
        "source_of_truth":"canonical-references","canon_reference_ids":["brand-design-law","copy-language-law"],
        "requested_actions":["local_review"],"write_scope":["runtime"],
        "approval":{"status":"not_requested","approver":None},
        "safety":{"external_side_effects":False,"credentials":False,"canon_writes":False,"deployment":False,"member_data":False},
        "input":{"proposed_text":text,"source_reference":None,"content_sha256":hashlib.sha256(text.encode()).hexdigest(),"target_surface":"homepage","source_provenance":{"kind":"direct","label":"ryan-provided"}}
    }
