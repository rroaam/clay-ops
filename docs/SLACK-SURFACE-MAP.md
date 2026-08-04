# Slack Surface Map

Defines the Slack canvases, lists, and message surfaces that Clay Studios Workflow System will produce or consume. Each surface is classified as **derived** (read-only projection, recomputed from Work Ledger) or **canonical** (human-authored, source of truth for decisions).

## Classification Rule

- **Derived surfaces** are recomputed on every event and never edited directly by humans in Slack. Edits are silently overwritten at next sync.
- **Canonical surfaces** are authored by humans (Ryan or team). The Workflow System only reads them and proposes additions, never writes without explicit approval.

## Consumption (Read from Slack)

These are canonical surfaces Clay Studios reads as source events.

### CS-1: Objectives and Key Results Canvas

- **Surface**: Slack canvas document (block kit markdown)
- **Owner**: Ryan
- **Read frequency**: On-change (canvas update webhook) + weekly reconcile
- **Extracts**:
  - Objective titles + owners
  - Key result titles, metrics, targets, owners, current value
  - Q3/Q4 cadence markers
- **Normalization**: Each objective becomes `objective_id: okr-<slug>`. Each key result links via `key_result_id`.
- **Failure behavior**: If canvas becomes unparseable, surface `health_signals.objectives_unavailable = true` and notify Ryan. Do not fabricate OKR values.

### CS-2: Studio Overview Canvas

- **Surface**: Slack canvas
- **Owner**: Ryan
- **Extracts**: Team roster, roles, current priorities
- **Use**: Seed `owner` and `contributors` on work items

### CS-3: Decision Register List

- **Surface**: Slack list (structured columns)
- **Owner**: Ryan (confirmed decisions only)
- **Extracts**: `confirmed_decision` candidates (already approved via existing `slack_intake.py` pipeline)
- **Use**: Authority check for new candidates; conflict detection

## Production (Write to Slack — requires approval)

These are derived surfaces the system proposes updates to, but never writes without explicit `approve_external_action` approval.

### DS-1: Q3/Q4 Growth Planning Canvas

- **Surface**: Slack canvas
- **Content**:
  - Section per project: one-paragraph status, key results progress, next milestone
  - Last meaningful activity timestamp per project
  - Active blockers with link to source
  - Pending approvals count
- **Source data**: Aggregated from `work_items` joined to `okr-<slug>` via `objective_id`
- **Update trigger**: After daily reconcile AND human approval of proposed diff
- **Write permission**: Ryan only, via `approve_external_action` on the specific canvas section
- **Failure behavior**: If proposal conflicts with existing human-authored text (no `{{auto}}` placeholder), escalate as `escalate_blocker` approval
- **Human ownership**: All non-placeholder text remains human-owned; system never overwrites
- **Classification**: Derived (auto-proposed) + Canonical (human-authored placeholders)

### DS-2: Live Project Tracker List

- **Surface**: Slack list with columns
- **Columns**:
  | Column | Source | Auto-filled |
  |--------|--------|-------------|
  | Project name | `projects.name` | Yes (canonical from project seed) |
  | Status badge | `project_state.phase` | Yes (derived) |
  | Owner | `work_items.owner` (most active item) | Yes (derived) |
  | Active items | `COUNT(status='active')` | Yes (derived) |
  | Blocked items | `COUNT(status='blocked')` | Yes (derived) |
  | Next milestone | Earliest `due_at` in active items | Yes (derived) |
  | Last activity | `project_state.last_meaningful_activity_at` | Yes (derived) |
  | Health signal | Red/yellow/green from `health_signals` | Yes (derived) |
  | Notes | Human-authored | No (canonical) |
- **Source data**: `project_state` projection
- **Update trigger**: Hourly silent reconcile + on event (debounced 5 min)
- **Write permission**: Row-level; system updates derived columns, preserves Notes
- **Failure behavior**: If row count diff > 3 rows added/removed in one tick, require approval before applying
- **Classification**: Mixed (derived columns + canonical Notes column)

### DS-3: Decisions and Approvals Canvas

- **Surface**: Slack canvas with two sections
- **Section A — Pending Approvals**:
  - Each open `work_approval` rendered as Slack block kit card:
    - Decision type icon
    - Work item title + link
    - Decision required (verbatim)
    - Options as buttons (approve / reject / request-changes / comment)
    - Evidence links (collapsible)
    - Due date countdown
    - Responded-by badge (once clicked)
  - Sorted by `due_at` ascending, then `requested_at`
  - Auto-expired items (past due, no response) moved to "Expired" section
- **Section B — Confirmed Decisions (last 30 days)**:
  - Read-only projection from `work_approvals WHERE status='approved'`
  - Each row: date, decision type, work item link, approver, selected option, source event permalink
- **Source data**: `work_approvals` + `state_transitions`
- **Update trigger**: Immediate on approval created/resolved; batched 5-min otherwise
- **Write permission**: Ryan only can modify (approve/reject/comment)
- **Failure behavior**: Canvas write failures logged but don't block approval; approval persists in `work_approvals` regardless of canvas state
- **Classification**: Derived projection (read-only for system, interactive for human)

### DS-4: Activity Stream

- **Surface**: Slack channel message stream (e.g., #studio-activity)
- **Content**: One message per meaningful event, grouped hourly
- **Grouping**:
  - Group events by `project_id` + hour bucket
  - Single message per group with bullet list of events
  - Each bullet: `<event_type> · <actor> · <summary> · <source_link>`
- **Source data**: `work_events` filtered by noise policy (see AUTOMATION-POLICY.md)
- **Update trigger**: Hourly batch (silent reconcile) posts summary; urgent events post immediately
- **Write permission**: System, via `approve_external_action` (one-time channel approval)
- **Failure behavior**: Channel unavailable → log only, no retry
- **Classification**: Derived (append-only projection)

### DS-5: Personalized Daily Work Stack

- **Surface**: Slack DM to Ryan (and optionally per-contributor DMs)
- **Content**:
  - Header: "Your work stack for 2026-07-29"
  - Section: **Pending approvals** (count + top 3 with approve/reject buttons)
  - Section: **Active work items you own** (title, next action, due date, last activity)
  - Section: **Blockers needing your input** (title, reason, how long blocked)
  - Section: **Stale work** (items you own with no activity > 7d)
  - Section: **Today's deadlines** (work items with `due_at` = today)
  - Section: **Yesterday's completions** (items marked done in last 24h)
  - Footer: "Reply with work item ID for detail" → triggers ephemeral detail card
- **Source data**: `work_items` filtered by `owner = Ryan` + `work_approvals` filtered by `approver = Ryan`
- **Update trigger**: Daily at 08:30 local time (Ryan's timezone)
- **Write permission**: System, one-time DM channel approval
- **Failure behavior**: If DM fails (e.g., user not found), fall back to #approvals channel mention; log error
- **Classification**: Derived (personalized projection)

## Non-Surfaces (Explicitly Excluded)

These Slack features are NOT used by the Workflow System:

- **Threads on approval cards**: Approval interactions use Slack block actions (buttons, modals, overflow menus), not thread replies. Thread-based approvals are ambiguous and not parseable.
- **Reactions as approvals**: Thumbs-up/emoji reactions are NOT treated as approval. Only explicit button clicks in a `work_approval` context count.
- **Slash commands for state changes**: State changes require evidence; slash commands have no evidence context. Slash commands may be used for read-only queries (`/clay status work-abc123`).
- **Workflow Builder**: Slack's native workflow builder is not used. All workflow logic stays in clay-ops.

## Placeholder Protocol

For DS-1 (canvas with mixed ownership), all auto-generated text must be wrapped in clearly-delimited markers so the system never overwrites human text:

```
<!-- clay:auto:project-xyz:status:start -->
[status paragraph — auto-generated]
<!-- clay:auto:project-xyz:status:end -->

[Ryan's notes here — never overwritten]
```

If a canvas lacks placeholders for a section, the system must request approval to insert the placeholder boundary before writing.

## Permissions Model

All Slack writes require one of:
1. **One-time channel approval**: Ryan approves `approve_external_action` for channel `#studio-activity`. Subsequent posts proceed without approval.
2. **Per-message approval**: Each post requires a new `approve_external_action`. Used for high-sensitivity surfaces (e.g., posting to #announcements).
3. **DM implicit approval**: Personalized DMs to Ryan (DS-5) are pre-approved by one-time setup.

Permission state lives in `registries/slack-surfaces.json` (to be created):

```json
{
  "schema_version": "1.0.0",
  "surfaces": [
    {
      "surface_id": "DS-4",
      "channel_id": "C123...",
      "permission": "one_time_approved",
      "approved_at": "2026-07-29T10:00:00Z",
      "approved_by": "Ryan"
    }
  ]
}
```

## Source Pointer Preservation

Every surface element rendered by the system preserves the original `source_url` as a clickable permalink. No summary replaces the source. If text must be truncated for display, the truncated version is marked with `[…]` and the full text is available at the `source_url`.

## Failure Modes

| Failure | Behavior | User-visible |
|---------|----------|--------------|
| Canvas API rate limit | Exponential backoff, max 5 retries, then skip tick | Log only |
| Canvas document deleted | Surface `unavailable`, no recreation attempt | Error state shown on Dashboard |
| List row conflict | Keep human version, log conflict | Alert to Ryan via DM |
| Block action timeout | Expire after 30 days, surface as `superseded` | "Expired" badge |
| DM delivery failure | Fall back to #approvals mention | Mention in channel |

No surface failure is allowed to fabricate state, auto-approve, or silently drop approvals.
