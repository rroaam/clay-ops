"""Governed Slack knowledge intake workflow.

Converts selected Slack threads and attachments into reviewable Clay
knowledge packets. Slack is evidence, NOT automatic canon. Every
extracted item remains a `candidate` until Ryan approves it through
the existing `Needs Ryan` queue.

This module never stores Slack credentials, never calls Slack from
tests, never stores PHI/PII/member data, and never mutates canon.
The live Slack adapter boundary is documented in
docs/SLACK_KNOWLEDGE_INGESTION.md and is out of scope for this slice.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .redaction import redact
from .store import OperationalStore, canonical, sanitize, utc_now


def _stable_id(prefix: str, seed: str) -> str:
    return f"{prefix}-{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:12]}"


def _is_member_data(text: str) -> bool:
    low = (text or "").lower()
    return any(token in low for token in (
        "member name", "patient", "date of birth", "ssn", "health record", "hipaa",
        "member id", "patient id", "clinical note",
    ))


def build_intake_packet(
    *,
    workspace_id: str,
    channel_id: str,
    channel_name: str,
    thread_ts: str,
    root_author_id: str,
    root_author_name: str,
    root_message_ts: str,
    root_permalink: str,
    messages: list[dict],
    attachments: list[dict],
    pilot_label: str | None = None,
) -> dict:
    if _is_member_data(
        " ".join(m.get("text_preview", "") for m in messages)
        + " "
        + " ".join(a.get("name", "") for a in attachments)
    ):
        raise ValueError("SLACK_PHI_PII_BLOCKED: intake contains member/PHI/PII data.")
    intake_id = _stable_id("intake", f"{workspace_id}:{channel_id}:{thread_ts}")
    return {
        "schema_version": "1.0.0",
        "intake_id": intake_id,
        "source": {
            "platform": "slack",
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
        },
        "thread": {
            "thread_ts": thread_ts,
            "root_author_id": root_author_id,
            "root_author_name": root_author_name,
            "root_message_ts": root_message_ts,
            "root_permalink": root_permalink,
        },
        "messages": [
            {
                "message_ts": m["message_ts"],
                "author_id": m["author_id"],
                "author_name": m["author_name"],
                "permalink": m["permalink"],
                "text_preview": redact(m.get("text_preview", ""))[:1000],
                "attachment_ids": list(m.get("attachment_ids", [])),
            }
            for m in messages
        ],
        "attachments": [
            {
                "attachment_id": a["attachment_id"],
                "name": a["name"],
                "type": a["type"],
                "source_link": a["source_link"],
                "byte_size": a.get("byte_size"),
            }
            for a in attachments
        ],
        "extracted_at": utc_now(),
        "pilot_label": pilot_label,
    }


def extract_candidates(intake_packet: dict, *, extraction_rules: list[dict]) -> list[dict]:
    extracted = []
    for message in intake_packet["messages"]:
        text = message.get("text_preview", "")
        source_permalink = message["permalink"]
        source_ts = message["message_ts"]
        for rule in extraction_rules:
            matcher = rule.get("match")
            if not matcher or matcher not in text:
                continue
            extracted.append({
                "schema_version": "1.0.0",
                "candidate_id": _stable_id(
                    "candidate",
                    f"{intake_packet['intake_id']}:{source_ts}:{rule.get('rule_id')}",
                ),
                "intake_id": intake_packet["intake_id"],
                "source_message_ts": source_ts,
                "source_permalink": source_permalink,
                "classification": rule["classification"],
                "extracted_meaning": rule["extracted_meaning"],
                "authority_check": {
                    "current_canonical_source": rule.get("current_canonical_source", "none"),
                    "conflict_status": rule.get("conflict_status", "unknown"),
                    "recommended_action": rule.get("recommended_action", "manual_review"),
                    "required_approver": rule.get("required_approver", "Ryan"),
                },
                "proposed_destination": rule.get("proposed_destination", "none"),
                "review_status": "pending",
            })
    return extracted


def build_needs_ryan_packet(intake_packet: dict, candidates: list[dict]) -> dict:
    pending = [c for c in candidates if c.get("review_status") in (None, "pending")]
    conflict_flags = [
        {
            "candidate_id": c["candidate_id"],
            "classification": c["classification"],
            "conflict_status": c["authority_check"]["conflict_status"],
        }
        for c in candidates
        if c["authority_check"]["conflict_status"] not in {"no_prior_record"}
    ]
    return {
        "schema_version": "1.0.0",
        "kind": "slack_knowledge_review",
        "intake_id": intake_packet["intake_id"],
        "channel_name": intake_packet["source"]["channel_name"],
        "thread_permalink": intake_packet["thread"]["root_permalink"],
        "required_approver": "Ryan",
        "review_status": "pending",
        "created_at": utc_now(),
        "candidates": pending,
        "conflict_flags": conflict_flags,
        "action_required": "Approve, reject, or request changes on each candidate before any canonical write.",
    }


def pilot_justin_onboarding_thread() -> dict:
    return build_intake_packet(
        workspace_id="synthetic-clay-workspace",
        channel_id="synthetic-channel-onboarding",
        channel_name="onboarding-core-assessment",
        thread_ts="1722300000.000001",
        root_author_id="synthetic-user-justin",
        root_author_name="Justin Weniger",
        root_message_ts="1722300000.000001",
        root_permalink="https://synthetic.slack.com/archives/synthetic-channel-onboarding/p1722300000000001",
        messages=[
            {
                "message_ts": "1722300000.000001",
                "author_id": "synthetic-user-justin",
                "author_name": "Justin Weniger",
                "permalink": "https://synthetic.slack.com/archives/synthetic-channel-onboarding/p1722300000000001",
                "text_preview": "Onboarding and core assessment. Pause the digital-only membership direction for now. Evaluate Vegas event, ticketed experience, or mobile onboarding alternatives.",
                "attachment_ids": [
                    "synthetic-att-first-four-md",
                    "synthetic-att-first-four-pdf",
                ],
            },
            {
                "message_ts": "1722300010.000002",
                "author_id": "synthetic-user-ryan",
                "author_name": "Ryan",
                "permalink": "https://synthetic.slack.com/archives/synthetic-channel-onboarding/p1722300010000002",
                "text_preview": "Ingest prior experience-design and audit library as source material. Prepare approx 30 items for discussion tomorrow. Inspect both First Four Experiences attachments.",
                "attachment_ids": [],
            },
        ],
        attachments=[
            {
                "attachment_id": "synthetic-att-first-four-md",
                "name": "The First Four Experiences.md",
                "type": "markdown",
                "source_link": "https://synthetic.slack.com/files/synthetic-att-first-four-md",
                "byte_size": 2048,
            },
            {
                "attachment_id": "synthetic-att-first-four-pdf",
                "name": "The First Four Experiences.pdf",
                "type": "pdf",
                "source_link": "https://synthetic.slack.com/files/synthetic-att-first-four-pdf",
                "byte_size": 8192,
            },
        ],
        pilot_label="justin-onboarding-core-assessment",
    )


def pilot_extraction_rules() -> list[dict]:
    return [
        {
            "rule_id": "pause-digital-only",
            "match": "Pause the digital-only membership direction",
            "classification": "proposed_decision",
            "extracted_meaning": "Pause the digital-only membership direction.",
            "current_canonical_source": "roadmap_member_roadmap_brief (candidate, not confirmed)",
            "conflict_status": "open_alternative",
            "recommended_action": "record as proposed decision, await Ryan approval",
            "required_approver": "Ryan",
            "proposed_destination": "roadmap_member_roadmap_brief",
        },
        {
            "rule_id": "evaluate-alternatives",
            "match": "Evaluate Vegas event, ticketed experience, or mobile onboarding alternatives",
            "classification": "open_question",
            "extracted_meaning": "Evaluate Vegas event, ticketed experience, or mobile onboarding alternatives.",
            "current_canonical_source": "none",
            "conflict_status": "no_prior_record",
            "recommended_action": "track as open question for tomorrow's discussion",
            "required_approver": "Ryan",
            "proposed_destination": "roadmap_member_roadmap_brief",
        },
        {
            "rule_id": "ingest-audit-library",
            "match": "Ingest prior experience-design and audit library as source material",
            "classification": "source_material",
            "extracted_meaning": "Ingest prior experience-design and audit library as source material.",
            "current_canonical_source": "source_registry (not yet listed)",
            "conflict_status": "additive_candidate",
            "recommended_action": "register as source material after approval",
            "required_approver": "Ryan",
            "proposed_destination": "source_registry",
        },
        {
            "rule_id": "prepare-30-items",
            "match": "Prepare approx 30 items for discussion tomorrow",
            "classification": "task",
            "extracted_meaning": "Prepare approx 30 items for discussion tomorrow.",
            "current_canonical_source": "none",
            "conflict_status": "no_prior_record",
            "recommended_action": "convert into project task after approval",
            "required_approver": "Ryan",
            "proposed_destination": "project_task",
        },
        {
            "rule_id": "inspect-first-four",
            "match": "Inspect both First Four Experiences attachments",
            "classification": "source_material",
            "extracted_meaning": "Inspect both First Four Experiences attachments.",
            "current_canonical_source": "source_registry (not yet listed)",
            "conflict_status": "additive_candidate",
            "recommended_action": "register as source material after approval",
            "required_approver": "Ryan",
            "proposed_destination": "source_registry",
        },
    ]
