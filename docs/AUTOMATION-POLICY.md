# Automation Policy

Defines what triggers processing, what triggers notification, and what stays silent. Goal: Ryan is interrupted only for work he genuinely needs to act on.

## Tiers of Processing

### Tier 0 — Immediate, Event-Driven (< 5 seconds)

Triggered by webhook receipt with valid signature. Processing is synchronous and must complete before webhook ACK.

**Applies to**:
- GitHub `pull_request.merged`
- GitHub `pull_request.closed` (not merged)
- Slack messages in approved channels matching `mentions_approval_request` signal
- Figma `file_version` events (new version published)
- Any webhook failing signature verification (logged, not processed)

**Does NOT apply to**:
- Slack `reaction_added` (always batched)
- Slack `message` without signals (always silent)
- GitHub `push` to non-default branch (deferred to reconcile)
- Drive document edits (always polled, never webhook)

### Tier 1 — Hourly Silent Reconciliation

Runs on cron every hour at :00. Idempotent, no human notifications unless threshold is crossed.

**Actions**:
- Re-compute every `project_state` from `work_items`
- Detect new stale work items
- Detect new blocker chains (A blocked by B blocked by C)
- Detect deadline risk (`due_at` < 3 days, status not `done`)
- Expire approvals past `due_at`
- Re-scan Drive documents for updates
- Re-scan Slack threads for missed replies (cursor pagination)

**Notifications**: None at Tier 1 unless threshold crossed. Log only.

### Tier 2 — Morning Personal Work Stack

Runs once daily at 08:30 local time (configurable per user).

**Action**: Builds and delivers DS-5 (Personalized Daily Work Stack) DM.

**Suppress if**:
- User has no active work items, no pending approvals, no blockers
- Weekend (Saturday/Sunday) unless work item is `priority=critical`
- Previous stack was never opened (track `viewed_at` on each stack delivery)

### Tier 3 — Midday Exceptions-Only Update

Runs at 12:30 local time.

**Action**: Posts a single message to #studio-activity only if at least one of:
- New blocker created since morning
- Work item status change crossed from `active`→`done`
- Approval received since morning
- Stale work item crossed 7-day threshold

**Suppress if**: None of the above.

### Tier 4 — End-of-Day Studio Recap

Runs at 18:00 local time.

**Action**: Posts to #studio-activity:
- Work items completed today (by owner)
- Blockers opened today
- Approvals resolved today
- Top-3 projects by activity

**Suppress if**: Zero activity across all projects.

### Tier 5 — Monday Priority Digest

Runs Monday at 09:00.

**Action**: Posts to #studio-activity + DM to Ryan:
- Top 5 priorities this week (from `priority=critical/high` + `due_at` within 7 days)
- Blockers carried over from last week
- OKR progress delta vs. last Monday
- Pending approvals older than 7 days

**Suppress**: Never. Monday digest is always delivered, even if contents are "no changes this week" (to confirm the system is alive).

### Tier 6 — Friday OKR Progress Summary

Runs Friday at 16:00.

**Action**: Updates DS-1 (Q3/Q4 Growth Planning Canvas) placeholders with:
- Key result progress (% toward target, source evidence)
- Projects contributing to each key result this week
- Confidence change since last Friday

**Requires**: Human approval via `approve_external_action` before canvas write.

## Notification Thresholds

A Slack notification is emitted ONLY when at least one of:

| # | Trigger | Surface | Recipient |
|---|---------|---------|-----------|
| N1 | New approval assigned to Ryan | DM + #approvals mention | Ryan |
| N2 | New blocker created | DM + #blockers channel | Owner + Ryan |
| N3 | Deadline ≤ 24h with status ≠ done | DM | Owner + Ryan |
| N4 | Deadline ≤ 72h with status = blocked | DM | Owner + Ryan |
| N5 | Deployment failure (GitHub `deployment.status` = failure) | DM + #deployments | Ryan |
| N6 | Critical-priority work item state change | #studio-activity | All |
| N7 | Action that contradicts confirmed decision | DM | Ryan |
| N8 | Work item created with `depends_on` user explicitly | DM | Owner + assignee of dependency |
| N9 | Stale work crosses 7-day threshold | DM | Owner + Ryan |
| N10 | Approval expires without response | DM | Requester + Ryan |

## Notification Suppression

Notifications are suppressed when:

- **Same event re-delivered**: Dedupe by `event_id + event_type + recipient` within 24h window
- **Batch boundary**: Tier 1 reconcile never notifies — only logs
- **Quiet hours**: 22:00–07:00 user local time, all notifications held to morning stack (except N5 deployment failures)
- **Owner away**: If user marked away, hold to their next stack delivery (except N5)
- **Duplicate across systems**: Slack "merged PR #42" and GitHub `pull_request.merged #42` within 60s → one notification

## Noise Filtering

Routine activity is processed silently (enters `work_events` but triggers no notification, no state change):

- **Git commits** to feature branches
- **PR opened** (only notifies if explicitly `mentions_blocker` or `mentions_approval_request`)
- **Figma comment** (unless `mentions_blocker`)
- **Drive document edit** by non-owner
- **Slack reaction** (any emoji)
- **Slack thread reply** with no signal keywords
- **Routine re-edits** of messages (Slack `message_edited`)

Activity crosses into notification when it matches at least one row in the Notification Thresholds table above.

## Idempotency Rules

- Every webhook must be ACK'd exactly once. Use `event_id` + `payload_sha256` as idempotency key.
- Duplicate webhooks (retries) produce a log entry but no new `work_event`.
- Approval responses are single-use. Second click returns `APPROVAL_REPLAY` error.
- State transitions are append-only; `from`/`to` pair can repeat but `transition_id` is unique.

## Retry Policy

| Action | Max retries | Backoff | Final behavior |
|--------|-------------|---------|----------------|
| Webhook ACK | 1 (immediate) | — | Source retries per spec |
| Slack block post | 3 | 1s, 5s, 30s exponential | Drop + log to `unacknowledged_notifications` |
| Canvas update | 3 | 1s, 5s, 30s exponential | Mark surface `unavailable` for this tick |
| Slack DM | 3 | 1s, 5s, 30s exponential | Fall back to #approvals mention |
| Drive polling | Infinite | 5 min between attempts | Continue trying, no alert |
| Approval state write | 3 | immediate | Fail loudly, do not lose decision |

## Reconciliation Windows

- **Short reconcile**: 1 hour window. Runs at :00 every hour. Checks events received since last run.
- **Daily reconcile**: 08:00 local time. Recomputes full `project_state` for every project. Detects drift vs. source systems.
- **Weekly reconcile**: Monday 07:00. Rescans OKR canvas, re-links work items to key results. Flags orphaned items.

## Drift Detection

Hourly reconcile compares local state to source systems:

- Work item `done` but source PR not merged → revert to `active`, notify Ryan
- Work item `active` but source PR deleted → mark `cancelled`, notify Ryan
- Work item owner disagrees with GitHub assignee → flag `needs_ryan`, no auto-reassign
- OKR canvas lists key result not tracked in any work item → create `backlog` work item with confidence 0.3

Drift corrections NEVER reduce confidence; they only raise new approvals or flag discrepancies.

## Quiet Channels

The following events are always silent even if matched by notification rules:

- Bot's own messages (self-filter by `author_id = bot_user_id`)
- Webhook test messages (`SLACK_TEST_WEBHOOK` prefix)
- Fixture replay events (tagged `source_system = "manual"` + `payload.fixture = true`)
- Events from channels not in `registries/approved-channels.json`

## Rate Limits

- Maximum 5 Slack notifications to Ryan per 1-hour window (except N5 deployment failures)
- Maximum 10 #studio-activity posts per 1-hour window
- Maximum 1 Canvas write per 30 minutes
- Burst allowance: 3x normal rate for 5 minutes after long outage

## Policy Configuration

All thresholds are in `policies/automation-policy.json`:

```json
{
  "schema_version": "1.0.0",
  "policy_id": "clay-studios-automation-v1",
  "tier_schedules": {
    "tier_1_reconcile": "0 * * * *",
    "tier_2_morning_stack": "30 8 * * *",
    "tier_3_midday": "30 12 * * *",
    "tier_4_eod_recap": "0 18 * * *",
    "tier_5_monday_digest": "0 9 * * 1",
    "tier_6_friday_okr": "0 16 * * 5"
  },
  "quiet_hours": {"start": "22:00", "end": "07:00"},
  "rate_limits": {
    "ryan_per_hour": 5,
    "studio_activity_per_hour": 10,
    "canvas_writes_per_30min": 1
  },
  "stale_thresholds": {
    "active_days": 7,
    "blocked_days": 14,
    "needs_approval_days": 30
  }
}
```

## Non-Negotiable Rules

1. **Tier 0 webhook processing must complete before ACK**, even if it means rejecting the webhook. Never fabricate a received event.
2. **No auto-approved notifications**. Every notification derives from a real event with verified evidence.
3. **No silent failures**. Every retry exhaustion is logged to `unacknowledged_notifications` table and surfaced in next morning stack.
4. **No cross-user notification leakage**. Ryan's DMs are Ryan's. Contributors see only their own stacks unless explicitly included.
5. **No notification for the bot's own activity**. Self-events are filtered before rule evaluation.
