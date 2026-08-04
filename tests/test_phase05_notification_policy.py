"""Phase 0.5: Notification Policy Tests.

These tests exercise NotificationPolicy.evaluate_event() directly by inserting
fixture rows into an in-memory simulation database. Assertions are aligned to
the ACTUAL schema defined in src/clay_ops/simulation/schema.py:

- sim_work_events columns: event_id, event_type, source_system, source_pointer,
  timestamp, payload, received_at. (No 'normalized_payload' column.)
- sim_work_items columns: work_item_id, project_id, objective_id, key_result_id,
  title, description, status (NOT 'state'), priority, owner (NOT 'assignee'),
  contributors, created_at, updated_at, last_activity_at, stale_since, version,
  confidence, review_status, state_transition_requires_confirmation.
- sim_blockers columns: blocker_id, work_item_id, blocking_work_item_id,
  reason, severity, raised_at, resolved_at, event_id.
- sim_approvals columns: approval_id, work_item_id, approval_type, requester,
  approver, decision_required, options, recommendation, evidence, requested_at,
  due_at, response, status, resolved_at, confirmed_metadata.
- sim_notifications columns: notification_id, event_id, work_item_id,
  notification_type, destination, suppressed, suppression_reason,
  priority_score (NOT 'priority'), title, body (NOT 'message'), metadata,
  created_at.
"""
import json
import sqlite3

from clay_ops.simulation.notification_policy import NotificationPolicy
from clay_ops.simulation.schema import SIMULATION_SCHEMA


def setup_test_db():
    """Create test database with actual simulation schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SIMULATION_SCHEMA)
    return conn


def _insert_event(conn, event_id, event_type, source_system, source_pointer,
                  timestamp, payload_dict):
    conn.execute("""
        INSERT INTO sim_work_events
        (event_id, event_type, source_system, source_pointer, timestamp, payload, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_id, event_type, source_system, source_pointer, timestamp,
          json.dumps(payload_dict), timestamp))


def _insert_work_item(conn, work_item_id, project_id, title, status, priority,
                      owner="ryan", confidence=0.8, review_status="needs_confirmation",
                      created_at="2026-01-14T14:20:00Z"):
    conn.execute("""
        INSERT INTO sim_work_items
        (work_item_id, project_id, title, status, priority, owner,
         created_at, updated_at, last_activity_at, confidence, review_status,
         state_transition_requires_confirmation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (work_item_id, project_id, title, status, priority, owner,
          created_at, created_at, created_at, confidence, review_status))


def _insert_blocker(conn, blocker_id, work_item_id, reason, severity, raised_at,
                    event_id=None):
    conn.execute("""
        INSERT INTO sim_blockers
        (blocker_id, work_item_id, reason, severity, raised_at, event_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (blocker_id, work_item_id, reason, severity, raised_at, event_id))


def _insert_approval(conn, approval_id, work_item_id, approval_type, requester,
                     approver, decision_required, requested_at, due_at,
                     options=None, evidence=None):
    conn.execute("""
        INSERT INTO sim_approvals
        (approval_id, work_item_id, approval_type, requester, approver,
         decision_required, options, evidence, requested_at, due_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (approval_id, work_item_id, approval_type, requester, approver,
          decision_required,
          json.dumps(options or [{"id": "approve", "label": "Approve"}]),
          json.dumps(evidence or []), requested_at, due_at))


def test_blocker_notification_creation():
    """Events for work items with active blockers produce blocker notifications."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-blocker-001"
    work_item_id = "work-test-001"
    _insert_event(conn, event_id, "slack.message", "slack",
                  "slack.com/C0123/p1", "2026-01-14T14:20:00Z",
                  {"text": "Blocked on legal approval"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-001", "blocked", "high")
    _insert_blocker(conn, "block-test-001", work_item_id,
                    "Legal approval needed", "high", "2026-01-14T14:20:00Z",
                    event_id)
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    assert len(notifications) > 0
    # At least one notification is triggered by a blocker
    blocker_notifs = [n for n in notifications
                      if n["notification_type"] == "blocker_created"]
    assert len(blocker_notifs) > 0
    assert any(n["priority_score"] == 0.95 for n in blocker_notifs)


def test_approval_notification_creation():
    """Pending approvals produce approval notifications with high priority."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-approval-001"
    work_item_id = "work-test-002"
    _insert_event(conn, event_id, "slack.message", "slack",
                  "slack.com/C0123/p2", "2026-01-14T15:00:00Z",
                  {"text": "Need approval"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-002", "needs_approval",
                      "medium")
    _insert_approval(conn, "appr-test-001", work_item_id, "status_change",
                     "justin", "ryan", "Deploy to production?",
                     "2026-01-14T15:00:00Z", "2026-01-15T15:00:00Z")
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    assert len(notifications) > 0
    approval_notifs = [n for n in notifications
                       if n["notification_type"] == "approval_requested"]
    assert len(approval_notifs) > 0
    assert any(n["priority_score"] >= 0.7 for n in approval_notifs)


def test_routine_event_suppression():
    """Routine events are suppressed but still produce low-priority records."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-routine-001"
    _insert_event(conn, event_id, "github.push", "github",
                  "github.com/clay/repo/push/1", "2026-01-15T09:00:00Z",
                  {"commits": [{"message": "Nice work", "author": "dev"}]})
    conn.commit()

    notifications = policy.evaluate_event(event_id)
    # Routine commits are suppressed; if any record is produced it must be
    # flagged as suppressed with low priority.
    for notif in notifications:
        assert notif.get("suppressed") is True
        assert notif["priority_score"] <= 0.1


def test_high_priority_state_change():
    """High-priority state changes on critical items generate notifications."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-high-001"
    work_item_id = "work-test-004"
    _insert_event(conn, event_id, "slack.message", "slack",
                  "slack.com/C0123/p4", "2026-01-15T10:00:00Z",
                  {"text": "Critical bug fix"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-004", "active", "critical",
                      confidence=0.9)

    # Record a state transition referencing this event
    conn.execute("""
        INSERT INTO sim_state_transitions
        (transition_id, work_item_id, from_status, to_status, transition_type,
         event_id, timestamp, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("trans-test-001", work_item_id, "backlog", "active",
          "evidence_based", event_id, "2026-01-15T10:00:00Z", 0.9))
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    # Status-change notifications exist and should carry meaningful priority
    status_notifs = [n for n in notifications
                     if n["notification_type"] == "status_change"]
    assert len(status_notifs) > 0
    assert any(n["priority_score"] >= 0.6 for n in status_notifs)


def test_deployment_failure_notification():
    """Deployment failures trigger high-priority notifications."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-deploy-fail-001"
    work_item_id = "work-test-005"
    _insert_event(conn, event_id, "github.deployment_failed", "github",
                  "github.com/clay/repo/deploy/prod-123",
                  "2026-01-15T11:00:00Z",
                  {"deployment": "prod-deploy-123", "reason": "failed"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-005", "active", "high")
    # Attach a blocker representing the deployment failure
    _insert_blocker(conn, "block-deploy-001", work_item_id,
                    "Deployment to prod failed", "high",
                    "2026-01-15T11:00:00Z", event_id)
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    blocker_notifs = [n for n in notifications
                      if n["notification_type"] == "blocker_created"]
    assert len(blocker_notifs) > 0
    assert any(n["priority_score"] >= 0.9 for n in blocker_notifs)


def test_multiple_notifications_per_event():
    """An event affecting a blocked work item with a pending approval can
    produce notifications of both types."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-multi-001"
    work_item_id = "work-test-006"
    _insert_event(conn, event_id, "slack.message", "slack",
                  "slack.com/C0123/p6", "2026-01-15T12:00:00Z",
                  {"text": "Blocked and needs approval"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-006", "blocked", "high")
    _insert_blocker(conn, "block-test-002", work_item_id,
                    "Technical blocker", "high", "2026-01-15T12:00:00Z",
                    event_id)
    _insert_approval(conn, "appr-test-002", work_item_id, "status_change",
                     "justin", "ryan", "Unblock?", "2026-01-15T12:00:00Z",
                     "2026-01-16T12:00:00Z")
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    types = {n["notification_type"] for n in notifications}
    assert "blocker_created" in types
    assert "approval_requested" in types


def test_notification_insertion():
    """Notifications produced by evaluate_event can be persisted via
    NotificationPolicy.insert_notifications."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-insert-001"
    _insert_event(conn, event_id, "github.pull_request.opened", "github",
                  "github.com/clay/repo/pr/42", "2026-01-15T13:00:00Z",
                  {"pr_number": 42})
    conn.commit()

    notifications = policy.evaluate_event(event_id)
    policy.insert_notifications(notifications)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sim_notifications WHERE event_id = ?",
                   (event_id,))
    stored_count = cursor.fetchone()[0]
    assert stored_count == len(notifications)


def test_destination_routing():
    """High-priority blocker notifications route to Slack destination."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-routing-001"
    work_item_id = "work-test-007"
    _insert_event(conn, event_id, "slack.message", "slack",
                  "slack.com/C0123/p7", "2026-01-15T14:00:00Z",
                  {"text": "High priority blocker"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-007", "blocked", "critical",
                      confidence=0.9)
    _insert_blocker(conn, "block-test-003", work_item_id,
                    "Critical blocker", "critical", "2026-01-15T14:00:00Z",
                    event_id)
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    slack_notifs = [n for n in notifications if n["destination"] == "slack"]
    assert len(slack_notifs) > 0


def test_message_formatting():
    """Notification titles and bodies are non-empty strings."""
    conn = setup_test_db()
    policy = NotificationPolicy(conn)

    event_id = "evt-test-format-001"
    work_item_id = "work-test-008"
    _insert_event(conn, event_id, "slack.message", "slack",
                  "slack.com/C0123/p8", "2026-01-15T15:00:00Z",
                  {"text": "Test message"})
    _insert_work_item(conn, work_item_id, "proj-test", "Test Work-008", "active", "medium")
    conn.commit()

    notifications = policy.evaluate_event(event_id, work_item_id)
    for notif in notifications:
        assert isinstance(notif["title"], str) and len(notif["title"]) > 0
        assert len(notif["title"]) <= 200
        assert isinstance(notif["body"], str) and len(notif["body"]) > 0
        assert len(notif["body"]) <= 2000
