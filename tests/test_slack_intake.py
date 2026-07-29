from __future__ import annotations
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from clay_ops.slack_intake import (
    build_intake_packet,
    build_needs_ryan_packet,
    extract_candidates,
    pilot_extraction_rules,
    pilot_justin_onboarding_thread,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def intake_packet() -> dict:
    return pilot_justin_onboarding_thread()


@pytest.fixture
def rules() -> list:
    return pilot_extraction_rules()


def test_pilot_intake_packet_validates_against_schema(repo_root, intake_packet):
    schema = json.loads((repo_root / "schemas" / "slack-intake-packet.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(intake_packet))
    assert errors == [], [e.message for e in errors]


def test_pilot_candidates_validate_against_schema(repo_root, intake_packet, rules):
    schema = json.loads((repo_root / "schemas" / "knowledge-candidate.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    candidates = extract_candidates(intake_packet, extraction_rules=rules)
    assert candidates
    for candidate in candidates:
        errors = list(validator.iter_errors(candidate))
        assert errors == [], [f"{candidate['candidate_id']}: {e.message}" for e in errors]


@pytest.mark.parametrize("expected", [
    "proposed_decision",
    "open_question",
    "source_material",
    "task",
])
def test_pilot_classification_taxonomy(expected, intake_packet, rules):
    candidates = extract_candidates(intake_packet, extraction_rules=rules)
    assert any(c["classification"] == expected for c in candidates)


def test_pilot_no_confirmation_or_canon_write(intake_packet, rules):
    candidates = extract_candidates(intake_packet, extraction_rules=rules)
    assert all(c["classification"] != "confirmed_decision" for c in candidates)
    assert all(c["review_status"] == "pending" for c in candidates)
    assert all(c["authority_check"]["recommended_action"] != "write_canon" for c in candidates)


def test_candidate_ids_are_stable(intake_packet, rules):
    first = extract_candidates(intake_packet, extraction_rules=rules)
    second = extract_candidates(intake_packet, extraction_rules=rules)
    assert [c["candidate_id"] for c in first] == [c["candidate_id"] for c in second]


def test_needs_ryan_requires_approval_before_canon(intake_packet, rules):
    candidates = extract_candidates(intake_packet, extraction_rules=rules)
    packet = build_needs_ryan_packet(intake_packet, candidates)
    assert packet["required_approver"] == "Ryan"
    assert packet["review_status"] == "pending"
    assert "Approve" in packet["action_required"]
    assert packet["candidates"]


def test_attachment_ingestion_is_recorded(intake_packet):
    names = [a["name"] for a in intake_packet["attachments"]]
    assert any("First Four Experiences.md" in name for name in names)
    assert any("First Four Experiences.pdf" in name for name in names)


def test_member_data_is_blocked():
    with pytest.raises(ValueError, match="SLACK_PHI_PII_BLOCKED"):
        build_intake_packet(
            workspace_id="synthetic-workspace",
            channel_id="synthetic-channel",
            channel_name="members",
            thread_ts="1722300000.000099",
            root_author_id="synthetic-user-x",
            root_author_name="X",
            root_message_ts="1722300000.000099",
            root_permalink="https://synthetic.slack.com/archives/synthetic-channel/p1722300000000099",
            messages=[{
                "message_ts": "1722300000.000099",
                "author_id": "synthetic-user-x",
                "author_name": "X",
                "permalink": "https://synthetic.slack.com/archives/synthetic-channel/p1722300000000099",
                "text_preview": "Member name and date of birth for patient follow-up.",
                "attachment_ids": [],
            }],
            attachments=[],
        )


def test_intake_does_not_store_credentials_or_call_slack(intake_packet):
    blob = json.dumps(intake_packet)
    assert "bearer" not in blob.lower()
    assert "xoxb" not in blob
    assert "slack.com/api" not in blob


def test_conflict_flags_include_open_alternatives(intake_packet, rules):
    candidates = extract_candidates(intake_packet, extraction_rules=rules)
    packet = build_needs_ryan_packet(intake_packet, candidates)
    assert any(f["conflict_status"] != "no_prior_record" for f in packet["conflict_flags"])


def test_pilot_interpretation_treats_options_as_candidates_not_decisions(intake_packet, rules):
    candidates = extract_candidates(intake_packet, extraction_rules=rules)
    approved = [c for c in candidates if c["review_status"] == "approved"]
    assert approved == []
    assert any(c["classification"] == "proposed_decision" for c in candidates)
    assert not any(c["classification"] == "confirmed_decision" for c in candidates)
