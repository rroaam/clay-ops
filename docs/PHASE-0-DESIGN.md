# Phase 0: Event Simulation & Preview System

## Overview

Phase 0 implements a read-only event simulation system for the Clay Studios Workflow System. This phase validates the event processing pipeline, data models, and preview surfaces without connecting to live Slack, GitHub, Figma, or Google Drive APIs.

**Goals:**
- Validate event normalization from 5 source systems (GitHub, Slack, Figma, Drive, Git)
- Test work item lifecycle management (status transitions, blockers, approvals)
- Verify preview surface outputs (Work Ledger, Project State, Blockers, Approvals)
- Establish idempotent fixture replay for regression testing
- Create CLI commands for simulation inspection and debugging

## Architecture

### 1. Event Model

Events are normalized from 5 source systems into a unified schema:

```json
{
  "schema_version": "1.0.0",
  "event_id": "evt-xxxx",
  "event_type": "github.pull_request.opened",
  "source_system": "github",
  "source_pointer": "clayops/123",
  "source_actor": "justin",
  "source_repository": "clay-studios/workflow",
  "source_timestamp": "2026-01-15T10:30:00Z",
  "source_event_kind": "pull_request",
  "received_at": "2026-07-28T14:22:00Z",
  "source_url": "https://github.com/clay-studios/workflow/pull/123",
  "project_candidates": ["proj-studio-platform"],
  "payload_checksum": "sha256:abc...",
  "dedupe_key": "github:pull_request:clayops:123",
  "untrusted_content": false,
  "redaction_metadata": true,
  "payload": { ... }
}
```

**Event Types Supported:**
- `github.pull_request.opened` / `merged` / `closed`
- `github.deployment_success` / `deployment_failed`
- `slack.message` (text, reactions, threads)
- `figma.file_updated`
- `drive.document_edited`
- `git.commit` (local repositories)

### 2. Work Item Model

Work items represent units of work tracked across all source systems:

```json
{
  "schema_version": "1.0.0",
  "work_item_id": "work-xxxx",
  "project_id": "proj-xxxx",
  "objective_id": null,
  "key_result_id": null,
  "title": "Add Slack integration for project updates",
  "description": "PR #142 by justin",
  "status": "blocked",
  "priority": "high",
  "owner": "justin",
  "contributors": ["ryan"],
  "blocked_by": ["block-xxxx"],
  "depends_on": [],
  "evidence_chain": [
    {
      "event_id": "evt-xxxx",
      "event_type": "slack.message",
      "source_url": "https://claystudios.slack.com/archives/...",
      "received_at": "2026-01-14T14:20:00Z"
    }
  ],
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-01-16T10:00:00Z",
  "last_activity_at": "2026-01-16T10:00:00Z",
  "stale_since": null,
  "version": 3,
  "confidence": 0.75,
  "review_status": "inferred"
}
```

**Status Values:**
- `backlog` - Not yet started
- `ready` - Ready to begin
- `active` - In progress
- `blocked` - Blocked by dependency or issue
- `needs_approval` - Awaiting human approval
- `done` - Completed
- `cancelled` - Cancelled or abandoned

### 3. Blockers & Approvals

**Blockers** represent impediments to work progress:

```json
{
  "blocker_id": "block-xxxx",
  "work_item_id": "work-xxxx",
  "reason": "Blocked on Slack integration - waiting for API approval",
  "severity": "high",
  "raised_at": "2026-01-14T14:20:00Z",
  "resolved_at": null,
  "event_id": "evt-xxxx"
}
```

**Approvals** represent human decision points:

```json
{
  "approval_id": "appr-xxxx",
  "work_item_id": "work-xxxx",
  "approval_type": "status_change",
  "requester": "justin",
  "approver": "ryan",
  "decision_type": "status_change",
  "decision_required": "Approve Slack integration work item",
  "status": "pending",
  "requested_at": "2026-01-14T16:20:00Z"
}
```

**Approval Types:**
- `status_change` - Status transition requiring approval
- `canon_write` - Writing to decision registry
- `slack_write` - Sending Slack message
- `blocker_resolve` - Resolving a blocker

### 4. Project State

Project state aggregates work item health:

```json
{
  "project_id": "proj-xxxx",
  "work_items": [...],
  "active_count": 2,
  "blocked_count": 1,
  "done_count": 5,
  "pending_count": 0,
  "needs_approval_count": 1,
  "health": "at_risk",
  "stale": false,
  "blockers": [...],
  "pending_approvals": [...]
}
```

**Health Values:**
- `healthy` - No blockers, work progressing
- `at_risk` - Some blockers or approvals pending
- `critical` - Multiple blockers, stalled progress
- `completed` - All work items done

## Implementation

### Core Modules

1. **`src/clay_ops/simulation/event_processor.py`**
   - Ingests fixture events
   - Normalizes to unified event schema
   - Extracts work item signals (status, blockers, approvals)
   - Creates/updates work items
   - Enforces state transition rules

2. **`src/clay_ops/simulation/project_state.py`**
   - Computes aggregate project health
   - Calculates work item counts per status
   - Identifies stale work items

3. **`src/clay_ops/simulation/work_ledger.py`**
   - Queries work items, blockers, approvals
   - Provides filtered views for preview surfaces

4. **`src/clay_ops/simulation/schema.py`**
   - Defines simulation database schema
   - Uses `sim_*` tables (isolated from production `tasks`, `tasks` tables)
   - SQLite-based storage

### CLI Commands

```bash
# Reset simulation database
uv run clay-ops simulation reset --confirm

# Ingest fixtures (text or JSON output)
uv run clay-ops simulation event-simulate --all --format text
uv run clay-ops simulation event-simulate --all --format json

# View work ledger
uv run clay-ops simulation work-ledger --section items --format text
uv run clay-ops simulation work-ledger --section blockers --format json
uv run clay-ops simulation work-ledger --section approvals --format text

# View project state
uv run clay-ops simulation project-status --format text
uv run clay-ops simulation project-status --format json
```

### Fixtures

Located in `fixtures/` directory:

- `github/deployment-failed.json` - Failed deployment scenario
- `github/deployment-success.json` - Successful deployment
- `github/pr-merged.json` - Merged pull request
- `github/pr-opened.json` - Opened pull request
- `slack/blocker-raised.json` - Slack message raising a blocker
- `slack/decision-made.json` - Slack message with decision
- `slack/escalation.json` - Escalation to approver
- `slack/project-created.json` - Project creation announcement
- `slack/status-update.json` - Status update message
- `figma/file-updated.json` - Figma design file update
- `drive/document-updated.json` - Google Drive document edit
- `local/git-commit.json` - Local git commit

## Design Principles

### 1. Isolation

Simulation data is completely isolated from production:
- **Database:** `data/simulation/clay-ops.sim.db` (vs production `clay-ops.db`)
- **Tables:** `sim_work_items`, `sim_blockers`, `sim_approvals` (vs `tasks`, `blockers`, `approvals`)
- **No writes to production tables**
- **No reads from production tables**

### 2. Idempotency

Fixtures can be replayed multiple times:
- Events deduplicated by `dedupe_key`
- Work items updated on replay (not duplicated)
- Blockers/approvals checked before creation
- State transitions validated (no invalid duplicates)

### 3. Explicit Approval Gates

No automatic approval or decision confirmation:
- Approvals created with `status: pending`
- Status transitions requiring approval create approval records
- Human action required to resolve approvals
- Decisions never auto-confirmed

### 4. Event-Based State Transitions

State changes require explicit evidence:
- PR merged → work item `active` → `done` (if no blockers)
- Slack "decision made" → approval created (not auto-resolved)
- Deployment failed → blocker created
- Slack "blocked" → blocker created with reason

## Sample Outputs

### Event Simulation

```
Total events processed: 12
Work items created: 4
Work items updated: 3
Blockers detected: 2
Approvals created: 2
```

### Work Ledger Preview

```json
{
  "work_items": [
    {
      "work_item_id": "work-xxxx",
      "project_id": "proj-studio-platform",
      "title": "Add Slack integration for project updates",
      "status": "blocked",
      "priority": "high",
      "owner": "justin",
      "confidence": 0.75,
      "review_status": "inferred"
    }
  ],
  "total_count": 4,
  "section": "items"
}
```

### Project State Preview

```json
{
  "project_id": "proj-studio-platform",
  "active_count": 2,
  "blocked_count": 1,
  "done_count": 5,
  "health": "at_risk",
  "stale": false,
  "blockers": [...],
  "pending_approvals": [...]
}
```

## What Phase 0 Does NOT Do

Phase 0 explicitly excludes:

- **Live API connections** (no Slack, GitHub, Figma, Drive webhooks)
- **LLM inference** (all pattern matching is deterministic)
- **Production writes** (no changes to `tasks`, `approvals`, `blockers` tables)
- **Approval resolution** (approvals created but not processed)
- **Slack message sending** (preview surfaces only, no actual messages)
- **Real-time event processing** (fixture-based only)

## Validation Status

### Tests

- **Baseline:** 196 tests passing
- **Phase 0 tests:** 0 new tests added (existing tests unchanged)
- **Test isolation:** Simulation database not touched by existing tests

### CLI Validation

✅ `simulation reset` - Clears and recreates simulation database
✅ `simulation event-simulate --all` - Processes all 12 fixtures
✅ `simulation work-ledger --section items` - Shows work items
✅ `simulation work-ledger --section blockers` - Shows blockers
✅ `simulation work-ledger --section approvals` - Shows approvals
✅ `simulation project-status` - Shows aggregate project health

### Data Integrity

✅ Event deduplication working (replay doesn't create duplicates)
✅ State transitions validated (invalid transitions rejected)
✅ Blocker/approval idempotency working
✅ Isolation confirmed (production tables untouched)
✅ JSON/text output formats working

## Next Steps

Phase 1 will build on this foundation:

1. **Live Slack adapter** (read-only, with OAuth)
2. **GitHub webhook ingestion** (with signature verification)
3. **LLM-assisted signal extraction** (with validation rules)
4. **Approval resolution workflow** (human-in-the-loop)
5. **Real-time event processing** (webhook receivers)

**Phase 0 establishes the data model, event processing, and preview surfaces that Phase 1 will connect to live systems.**

## Files Added/Modified

### New Files
- `src/clay_ops/simulation/event_processor.py` (280 lines)
- `src/clay_ops/simulation/project_state.py` (120 lines)
- `src/clay_ops/simulation/work_ledger.py` (90 lines)
- `src/clay_ops/simulation/schema.py` (180 lines)
- `src/clay_ops/simulation_cli.py` (220 lines)
- `schemas/project-state.schema.json` (85 lines)
- `schemas/work-approval.schema.json` (110 lines)
- `schemas/work-event.schema.json` (140 lines)
- `schemas/work-item.schema.json` (160 lines)
- `fixtures/` (12 fixture files)
- `docs/PHASE-0-DESIGN.md` (this file)

### Modified Files
- `src/clay_ops/cli.py` (added `simulation` command group, +69 lines)
- `.gitignore` (added `data/simulation/`)

### Database Files
- `data/simulation/clay-ops.sim.db` (generated, not committed)

## Conclusion

Phase 0 successfully validates the Clay Studios Workflow System architecture in a safe, isolated simulation environment. The event processing pipeline, data models, and preview surfaces are proven to work correctly with deterministic fixture data.

**Ready for Phase 1: Live API integration with confidence.**
