"""
Schema for the simulation database.
Separate from production to ensure no writes to real data.
"""

SIMULATION_SCHEMA = """
-- Work events (immutable, deduplicated)
CREATE TABLE IF NOT EXISTS sim_work_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_pointer TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload JSON NOT NULL,
    inferred_signals JSON,
    received_at TEXT NOT NULL,
    UNIQUE(source_system, source_pointer)
);

-- Work items (mutable, state-driven)
CREATE TABLE IF NOT EXISTS sim_work_items (
    work_item_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    objective_id TEXT,
    key_result_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL CHECK (status IN ('backlog', 'ready', 'active', 'blocked', 'needs_approval', 'done', 'cancelled')),
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low', 'none')),
    owner TEXT NOT NULL,
    contributors JSON,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL,
    stale_since TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    review_status TEXT NOT NULL CHECK (review_status IN ('inferred', 'human_confirmed', 'needs_confirmation', 'auto_approved')),
    state_transition_requires_confirmation BOOLEAN NOT NULL DEFAULT false
);

-- Work item relationships (blocked_by, depends_on, relates_to)
CREATE TABLE IF NOT EXISTS sim_work_item_relations (
    from_work_item_id TEXT NOT NULL,
    to_work_item_id TEXT NOT NULL,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('blocked_by', 'depends_on', 'relates_to')),
    PRIMARY KEY (from_work_item_id, to_work_item_id, relation_type),
    FOREIGN KEY (from_work_item_id) REFERENCES sim_work_items(work_item_id),
    FOREIGN KEY (to_work_item_id) REFERENCES sim_work_items(work_item_id)
);

-- State transitions (immutable history)
CREATE TABLE IF NOT EXISTS sim_state_transitions (
    transition_id TEXT PRIMARY KEY,
    work_item_id TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    transition_type TEXT NOT NULL CHECK (transition_type IN ('evidence_based', 'manual', 'stale', 'contradiction')),
    event_id TEXT,
    timestamp TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence JSON,
    FOREIGN KEY (work_item_id) REFERENCES sim_work_items(work_item_id),
    FOREIGN KEY (event_id) REFERENCES sim_work_events(event_id)
);

-- Blockers
CREATE TABLE IF NOT EXISTS sim_blockers (
    blocker_id TEXT PRIMARY KEY,
    work_item_id TEXT NOT NULL,
    blocking_work_item_id TEXT,
    reason TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    raised_at TEXT NOT NULL,
    resolved_at TEXT,
    event_id TEXT,
    FOREIGN KEY (work_item_id) REFERENCES sim_work_items(work_item_id),
    FOREIGN KEY (blocking_work_item_id) REFERENCES sim_work_items(work_item_id),
    FOREIGN KEY (event_id) REFERENCES sim_work_events(event_id)
);

-- Approvals
CREATE TABLE IF NOT EXISTS sim_approvals (
    approval_id TEXT PRIMARY KEY,
    work_item_id TEXT NOT NULL,
    approval_type TEXT NOT NULL CHECK (approval_type IN ('status_change', 'owner_assignment', 'decision_confirmation', 'canon_write')),
    requester TEXT NOT NULL,
    approver TEXT NOT NULL,
    decision_required TEXT NOT NULL,
    options JSON NOT NULL,
    recommendation JSON,
    evidence JSON NOT NULL,
    requested_at TEXT NOT NULL,
    due_at TEXT,
    response JSON,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'cancelled')),
    resolved_at TEXT,
    confirmed_metadata JSON,
    FOREIGN KEY (work_item_id) REFERENCES sim_work_items(work_item_id)
);

-- Notifications (persisted notification policy decisions)
CREATE TABLE IF NOT EXISTS sim_notifications (
    notification_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    work_item_id TEXT,
    notification_type TEXT NOT NULL CHECK (notification_type IN (
        'blocker_created', 'approval_requested', 'status_change', 'work_created',
        'stale_detected', 'deadline_approaching', 'routine_suppressed'
    )),
    destination TEXT NOT NULL CHECK (destination IN ('slack', 'studio_center', 'daily_stack', 'recap')),
    suppressed BOOLEAN NOT NULL DEFAULT false,
    suppression_reason TEXT,
    priority_score REAL NOT NULL CHECK (priority_score >= 0 AND priority_score <= 1),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    metadata JSON,
    created_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES sim_work_events(event_id),
    FOREIGN KEY (work_item_id) REFERENCES sim_work_items(work_item_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_work_items_project ON sim_work_items(project_id);
CREATE INDEX IF NOT EXISTS idx_work_items_status ON sim_work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_owner ON sim_work_items(owner);
CREATE INDEX IF NOT EXISTS idx_transitions_work_item ON sim_state_transitions(work_item_id);
CREATE INDEX IF NOT EXISTS idx_blockers_work_item ON sim_blockers(work_item_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON sim_approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_approvers ON sim_approvals(approver);
"""
