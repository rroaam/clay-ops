# Slack Knowledge Ingestion Workflow

## Overview

Governed workflow for converting selected Slack threads and attachments into reviewable Clay knowledge packets. **Slack is evidence, NOT automatic canon.**

This workflow extracts decisions, questions, tasks, and source material from Slack conversations, classifies them, checks against canonical sources, and presents them in a "Needs Ryan" review packet. No Slack content is written to canon without explicit human approval.

## Pilot Scope

**Initial intake:** Justin's onboarding / core-assessment thread and the attached "The First Four Experiences" Markdown and PDF files.

**Interpretation rule:** Preserve as candidates, not decisions:
- Pause the digital-only membership direction
- Evaluate Vegas event, ticketed experience, or mobile onboarding alternatives
- Ingest the prior experience-design and audit library as source material
- Prepare approximately 30 items for discussion tomorrow
- Inspect both "First Four Experiences" attachments

No option may be inferred as approved.

## Workflow Stages

### 1. Slack Intake

Capture structured metadata:
- Channel and thread identity
- Message timestamps, authors, permalinks
- Attachment IDs, names, types, source links
- Thread replies
- Ingestion timestamp

**Boundary:** Never store Slack credentials. Never call Slack from tests. Live Slack adapter is out of scope for this slice.

### 2. Content Extraction

Extract only:
- Explicit decisions
- Proposed decisions
- Open questions
- Owners
- Deadlines or meeting requests
- Referenced deliverables
- Product or membership implications
- Supporting claims from attachments

**Boundary:** Never store PHI, PII, or member data. Block intake if any of these signals are detected.

### 3. Classification

Every extracted item must be classified as exactly one of:

- `confirmed_decision` — only if explicitly stated and approved
- `proposed_decision` — option under consideration, not yet approved
- `open_question` — unresolved question for discussion
- `task` — actionable work item
- `source_material` — document, library, or reference to ingest
- `conflict_with_canon` — contradicts existing canonical source
- `duplicate` — already recorded in another intake or registry
- `historical_context` — background information with no action needed

**Pilot rule:** The five items above are classified as `proposed_decision`, `open_question`, `source_material`, `task`, and `source_material` respectively. None are `confirmed_decision`.

### 4. Authority Handling

Compare each candidate against:
- Current source registry
- Decision registry
- Product vision documents
- Member journey / Roadmap sources
- Existing Clay Ops records

Return:
- Current canonical source
- Conflict status
- Recommended action
- Required approver

**Boundary:** Never write Slack content directly into canon.

### 5. Human Approval

Create a "Needs Ryan" review packet before any canonical write. The packet shows:
- Exact Slack source (permalink, timestamp, author)
- Concise extracted meaning
- Proposed destination (decision registry, source registry, project task, roadmap brief, etc.)
- Why it matters
- Conflict or duplication warning
- Approve / reject / request changes

**Boundary:** Slack content remains ephemeral evidence until Ryan approves the candidate.

### 6. Approved Destinations

Only after approval may information be proposed for:
- Decision registry
- Source registry
- Project task
- Roadmap / member-journey brief
- Product strategy brief
- Hermes durable lesson

**Hermes memory rule:** Durable memory may contain only compact verified lessons and source pointers, never the full Slack conversation.

### 7. Pilot Interpretation

For Justin's thread, preserve these as candidates, not decisions:
- Pause the digital-only membership direction
- Evaluate Vegas event, ticketed experience, or mobile onboarding alternatives
- Ingest the prior experience-design and audit library as source material
- Prepare approximately 30 items for discussion tomorrow
- Inspect both "First Four Experiences" attachments

Do not infer that any option has been approved.

## Implementation Artifacts

### Schemas

- `schemas/slack-intake-packet.schema.json` — Structured Slack thread capture
- `schemas/knowledge-candidate.schema.json` — Extracted and classified knowledge candidate

### Module

- `src/clay_ops/slack_intake.py` — Intake, extraction, classification, authority check, and Needs Ryan projection

### Pilot Fixture

- `pilot_justin_onboarding_thread()` — Synthetic metadata representing Justin's onboarding thread
- `pilot_extraction_rules()` — Five extraction rules matching the five candidate items above

### Tests

- `tests/test_slack_intake.py` — Schema validation, classification taxonomy, PHI/PII block, credential-free operation, stable candidate IDs, Needs Ryan projection

## Boundaries

This slice does NOT:
- Store Slack credentials
- Call Slack from tests
- Store PHI, PII, or member data
- Ingest unrelated channels
- Update canon
- Commit or push

## Validation

Run:
```
uv run pytest
git diff --check
```

Clay HQ projection verification if Needs Ryan output changes.

## Next Step for Live Slack Connection

1. Design a Slack adapter boundary:
   - Accept OAuth app credentials via environment variables only
   - Implement `slack_intake_adapter.thread(thread_url: str) -> SlackIntakePacket`
   - Use `slack_sdk` or raw HTTP with retry and rate-limit handling
   - Redact PHI/PII signals before returning the packet
   - Never persist credentials to disk or SQLite

2. Add a Clay HQ route:
   - `POST /hq/slack-intake` accepts a thread URL
   - Returns the intake packet + extracted candidates + Needs Ryan projection
   - Requires Hermes bearer token

3. Add approval actions:
   - Extend `approval_actions.py` with `decide_slack_candidate(store, *, candidate_id, decision, actor, reason)`
   - On approval, append to the appropriate registry (decision, source, task, roadmap) with provenance link to the intake packet

4. Add a Clay Ops registry table:
   - `slack_intake_packets(intake_id, packet, created_at)`
   - `knowledge_candidates(candidate_id, intake_id, candidate, created_at)`

5. Document the live boundary in `docs/SECURITY.md`:
   - Slack credentials are environment-only
   - Intake packets are ephemeral until approved
   - Approval decisions are immutable

This slice stops at human review. Live Slack connection is out of scope.
