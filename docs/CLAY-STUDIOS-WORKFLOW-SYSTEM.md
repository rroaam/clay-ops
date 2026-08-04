# Clay Studios Workflow System

Read-only operational ledger for multi-system work tracking. All writes require explicit human approval.

## Purpose

Unify Slack, GitHub, Figma, Drive, and local Git activity into a single source of truth for:
- Project progress and blockers
- Decision history and ownership
- Approval workflows and status changes
- Evidence-linked state transitions

No system may auto-write. No inference becomes canon without Ryan's explicit approval.

## Architecture

### Current Foundation

Existing clay-ops provides:
- `OperationalStore` (SQLite, immutable runs/events/artifacts)
- `slack_intake.py` (read-only Slack ingestion, candidate extraction)
- `approval_actions.py` (human approval gates)
- `CanonRegistry` (Git-pinned canonical documents)
- Schema validation (jsonschema Draft 2020-12)

### New Components

**Work Ledger** (`work_ledger.py`)
- Stores work items, objectives, approvals, state transitions
- Extends `OperationalStore` with `work_items`, `work_approvals`, `state_transitions` tables
- All mutations require evidence (source event IDs)

**Event Normalization Layer** (`event_normalizer.py`)
- Transforms source-specific events into normalized `work-event.schema.json`
- Handles: Slack messages, GitHub PRs/issues, Figma files, Drive docs, local Git
- Deduplicates via SHA256 of canonical payload

**Project State Engine** (`project_state.py`)
- Computes aggregate project health from work items
- Detects: stale work, blocker chains, deadline risk
- Never writes directly—emits `project-state` projections

**Approval Queue** (`work_approval.py`)
- Routes inferred decisions/status changes to Ryan
- Options: approve, reject, request changes
- Immutable audit trail with device/IP hints

### Database Schema

```sql
-- Work Items
CREATE TABLE work_items (
  work_item_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  objective_id TEXT,
  key_result_id TEXT,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL CHECK(status IN ('backlog','ready','active','blocked','needs_approval','done','cancelled')),
  owner TEXT,
  contributors TEXT, -- JSON array
  priority TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_activity_at TEXT NOT NULL,
  next_action TEXT,
  due_date TEXT,
  confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL CHECK(review_status IN ('inferred','human_confirmed','needs_ryan','rejected')),
  evidence_chain TEXT NOT NULL, -- JSON array of {event_id, event_type, source_url, received_at, weight}
  FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Work Approvals
CREATE TABLE work_approvals (
  approval_id TEXT PRIMARY KEY,
  work_item_id TEXT NOT NULL,
  decision_type TEXT NOT NULL,
  requester TEXT NOT NULL,
  approver TEXT NOT NULL,
  evidence_links TEXT NOT NULL, -- JSON
  options TEXT NOT NULL, -- JSON
  decision_required TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('open','approved','rejected','changes_requested','superseded','expired')),
  requested_at TEXT NOT NULL,
  response TEXT, -- JSON or null
  confirmed_metadata TEXT, -- JSON or null
  FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id)
);

-- State Transitions (immutable)
CREATE TABLE state_transitions (
  transition_id TEXT PRIMARY KEY,
  work_item_id TEXT NOT NULL,
  from_status TEXT NOT NULL,
  to_status TEXT NOT NULL,
  event_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  confidence_delta REAL,
  FOREIGN KEY (work_item_id) REFERENCES work_items(work_item_id),
  FOREIGN KEY (event_id) REFERENCES work_events(event_id)
);

-- Work Events (normalized)
CREATE TABLE work_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  source_system TEXT NOT NULL,
  source_event_kind TEXT NOT NULL,
  source_url TEXT NOT NULL,
  received_at TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  redacted_payload TEXT NOT NULL, -- JSON
  attachments TEXT, -- JSON
  signature_verified BOOLEAN,
  dedupe_key TEXT NOT NULL UNIQUE
);
```

### Data Flow

```
Source System (Slack/GitHub/Figma/Drive)
  ↓
Webhook/Poll (read-only, scoped)
  ↓
Event Normalizer (validate, dedupe, redact)
  ↓
work_events table (immutable)
  ↓
Inference Engine (rule-based signal detection)
  ↓
Candidate Work Item / Status Change
  ↓
[if confidence < 0.8] → work_approvals table (needs_ryan)
[if confidence >= 0.8] → direct write to work_items (rare)
  ↓
Project State Engine (aggregate)
  ↓
Slack Canvas / Dashboard (read-only projections)
```

**Critical**: Inference engine uses keyword matching (regex), NOT LLM. No natural language inference without explicit human approval.

## Project State Engine

### State Model

```
backlog → ready → active → done
                ↓
            blocked → needs_approval → active
                                      ↓
                                  cancelled
```

Valid transitions:
- `backlog → ready`: Work item created or prioritized
- `ready → active`: Work started (first commit, Figma edit, Slack thread)
- `active → blocked`: Explicit blocker identified (dependency, missing info)
- `blocked → needs_approval`: Blocker requires human decision
- `needs_approval → active`: Approval granted, unblocked
- `active → done`: Completion signal (PR merged, Figma link shared, Slack "done")
- Any → `cancelled`: Explicit cancellation

### State Inference Rules

| Signal | Source | Inferred State | Confidence | Requires Approval |
|--------|--------|----------------|------------|-------------------|
| PR opened | GitHub | active | 0.6 | No |
| PR merged | GitHub | done | 0.9 | No (if single work item) |
| PR closed (unmerged) | GitHub | blocked | 0.7 | Yes |
| "blocked" in Slack | Slack | blocked | 0.5 | Yes |
| "need approval" in Slack | Slack | needs_approval | 0.7 | Yes |
| "done" + link in Slack | Slack | done | 0.6 | Yes |
| Figma comment resolved | Figma | active (unblocked) | 0.5 | No |
| Drive doc created | Drive | active | 0.4 | Yes |
| Git commit to main | Local | done (if linked) | 0.8 | No |

**Confidence Threshold**: Any state change with confidence < 0.8 requires `needs_ryan` review.

### Stale Work Detection

Work item is `stale` if:
- `status == active` AND `last_activity_at` > 7 days ago
- `status == blocked` AND `last_activity_at` > 14 days ago
- `status == needs_approval` AND `requested_at` > 30 days ago

Stale work triggers Slack notification to owner + Ryan.

## Approval Queue

### Approval Types

1. **confirm_decision**: "Ryan confirmed X decision on 2026-07-29"
2. **confirm_status_change**: "Mark work-item-xyz as done?"
3. **confirm_owner_assignment**: "Assign Ryan as owner of work-item-xyz?"
4. **approve_canon_write**: "Add decision to decisions registry?"
5. **approve_external_action**: "Send Slack message to #announcements?"
6. **escalate_blocker**: "Work-item-xyz blocked. Need decision on X."

### Approval Flow

```
Inference detects state change opportunity
  ↓
Check confidence (if < 0.8) → create approval
  ↓
Post to Slack (private message to Ryan or #approvals channel)
  ↓
Wait for response (Slack block action / CLI `/clay-ops approval respond`)
  ↓
[approved] → apply state change, update work_items
[rejected] → mark approval rejected, no state change
[changes_requested] → re-infer with new context
```

### Approval Immutability

- `approval_id` is UUID, never reused
- `response` field is write-once
- `confirmed_metadata` captures device/IP for audit
- Superseded approvals link to replacement via `superseded_by` field

## Event Processing Model

### Event Ingestion

**Slack**
- Webhook: channel messages, thread replies, reactions
- Poll: files (PDF, images, docs)
- Scopes: `channels:history`, `groups:history`, `files:read`, `reactions:read`

**GitHub**
- Webhook: push, pull_request, issues, deployments
- Signature verification required (HMAC SHA256)
- Scopes: `repo:read`, `issues:read`

**Figma**
- Webhook: file updates, comments
- Signature verification required (RSA-SHA256)
- Scopes: file read comments

**Drive**
- Poll: document updates (every 5 min)
- OAuth2 service account, read-only
- Scopes: `drive.readonly`

**Local Git**
- Git hook: `post-commit`, `post-merge`
- Parses commit message for work item refs
- No network, no credentials

### Event Normalization

Every event normalized to `work-event.schema.json`:
- `event_id`: UUID
- `event_type`: `slack.message`, `github.pull_request.opened`, etc.
- `source_system`: `slack`, `github`, `figma`, `drive`, `local`
- `source_url`: Permanent link to source
- `payload_sha256`: For deduplication
- `redacted_payload`: Secrets removed, PHI blocked

### Signal Detection (No LLM)

Regex-based keyword matching:
```python
SIGNALS = {
  'slack.message': {
    'mentions_owner': r'\b(ryan|justin)@?\b',
    'mentions_decision': r'\b(decided|approved|rejected|confirmed)\b',
    'mentions_blocker': r'\b(blocked|waiting on|need\s+input)\b',
    'mentions_deadline': r'\b(due\s+\d{4}-\d{2}-\d{2}|by\s+next\s+week)\b',
    'mentions_approval': r'\b(ryan,?\s+(please|can|need)|approval\s+needed)\b',
  },
  'github.pull_request.opened': {
    'links_work_item': r'work[-_]item[:\s]+([a-zA-Z0-9-]+)',
    'fixes_issue': r'(fixes|closes)\s+#\d+',
  },
  # ... etc
}
```

**No inference without evidence**. Every signal must link to at least one `event_id`.

## Evidence Requirements

### Minimum Evidence

- **Work item creation**: 1 event (Slack thread, GitHub issue, etc.)
- **Status change**: 1 event (PR merged, Slack "done", Figma link)
- **Owner assignment**: 1 event (Slack @mention, GitHub assignee)
- **Blocker**: 1 event (Slack "blocked", PR review request)
- **Done**: 2 events (PR merged + Slack confirmation, or explicit Ryan approval)

### Evidence Chain

Each work item stores `evidence_chain`:
```json
[
  {
    "event_id": "wev-abc123",
    "event_type": "slack.message",
    "source_url": "https://slack.com/archives/C123/p1234567890",
    "received_at": "2026-07-29T10:00:00Z",
    "weight": 0.8
  },
  {
    "event_id": "wev-def456",
    "event_type": "github.pull_request.merged",
    "source_url": "https://github.com/org/repo/pull/42",
    "received_at": "2026-07-29T14:00:00Z",
    "weight": 0.9
  }
]
```

Weighted by source reliability:
- GitHub merged PR: 0.9
- Slack message from owner: 0.8
- Slack message from non-owner: 0.5
- Figma file update: 0.6
- Drive doc update: 0.4

### No Fabrication

- Never synthesize work items without events
- Never infer "done" from inactivity
- Never mark "blocked" without explicit signal
- Confidence < 0.5 → discard, don't store

## Review Boundaries

### What Ryan Must Approve

1. **Status changes** with confidence < 0.8
2. **Owner assignments** for work items
3. **Decision confirmations** (Slack "Ryan confirmed X")
4. **Canon writes** (adding to decisions/task registries)
5. **External actions** (posting to Slack channels)
6. **Blocker escalations** (unblocking requires decision)

### What Auto-Advances (No Approval)

1. PR opened → work item `active`
2. PR merged (single work item) → `done`
3. Git commit to main (linked work item) → `done`
4. Figma comment resolved → removes blocker (if single blocker)

### What Never Auto-Advances

1. Slack "I'm done" → requires explicit approval
2. Drive doc created → requires owner confirmation
3. GitHub issue closed → requires reason verification
4. Any state change from non-owner

## Slack Integration

### Read-Only (Always On)

- Ingest messages from approved channels (#projects, #decisions, #blockers)
- Extract candidates via `slack_intake.py`
- Normalize to `work-event.schema.json`
- Store in `work_events` table

### Write (Requires Approval)

- Post approval request to Ryan (DM or #approvals)
- Post status update to #projects (after Ryan approves)
- Post decision summary to #decisions (after Ryan confirms)

### Slack Surfaces

See `SLACK-SURFACE-MAP.md` for Canvas/List definitions.

## Security Constraints

### Credentials

- Slack OAuth token: env var only, never logged
- GitHub webhook secret: env var only, verified via HMAC
- Drive service account: key file path, never committed
- Figma webhook secret: env var only, verified via RSA

### Redaction

- All payloads go through `redaction.py` before storage
- Bearer tokens, API keys, signed URLs → `[REDACTED]`
- PHI (email, phone, SSN) → blocked at ingestion

### Network

- Webhooks: HTTPS only, signature-verified
- Polling: read-only scopes
- No outbound writes without approval

## Non-Negotiables

1. **No auto-decisions**: Every confirmation requires explicit Ryan approval
2. **No fabricated activity**: Every work item needs evidence
3. **No LLM inference**: Regex keyword matching only
4. **No silent failures**: Every error logged and notified
5. **No canon writes without approval**: Registry updates require `work_approval`
6. **No commit/push**: Implementation is local-only until Ryan approves

## Testing Strategy

### Phase 1: Read-Only Events
- Fixture payloads for each source system
- Unit tests for event normalization
- Integration tests for webhook signature verification
- Deduplication tests (same event twice)

### Phase 2: Work Ledger
- State transition validation (allowed/disallowed transitions)
- Evidence chain integrity (every state change has event)
- Stale work detection (time-based queries)
- Approval flow (create, respond, apply)

### Phase 3: Project State
- Aggregate computation (blockers, stale, deadlines)
- Health signal detection (blocker chains, approval bottlenecks)
- Slack projection format (Canvas/List schema validation)

### Phase 4: Slack Integration
- Live webhook ingestion (staging Slack workspace)
- Approval request/response round-trip
- Canvas/List sync (read-only projections)
- Error handling (webhook failures, signature mismatches)

## Open Questions for Ryan

1. **Stale thresholds**: Is 7 days for active work reasonable? Should this vary by priority?

2. **Approval channel**: Should approvals go to Ryan DM or #approvals channel (visible to team)?

3. **Slack surfaces**: Which existing Slack canvases/lists should we sync to?
   - Project tracker
   - Studio overview
   - Objectives and Key Results
   - Decision register
   - Blocker board

4. **Owner assignment**: Should work items default to Ryan, or require explicit assignment?

5. **Confidence tuning**: Are the confidence thresholds in "State Inference Rules" appropriate?

6. **Figma/Drive priority**: Should we defer Figma/Drive integration until GitHub/Slack are stable?

7. **Historical backfill**: Should we ingest past 30 days of Slack/GitHub to seed the ledger?

8. **Notification volume**: How many Slack notifications per day is acceptable before suppressing?

---

**Status**: Specification only. No implementation. No production writes. No commits.

**Next**: Ryan reviews, answers open questions, approves implementation plan.
