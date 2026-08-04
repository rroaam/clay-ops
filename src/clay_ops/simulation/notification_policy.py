"""
Notification policy for simulation.
Evaluates events and determines which notifications should be sent, suppressed, or deferred.
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional

class NotificationPolicy:
    """Evaluates events against notification policy rules."""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def evaluate_event(self, event_id: str, work_item_id: Optional[str] = None) -> List[Dict]:
        """
        Evaluate an event and generate notification records.
        
        Returns a list of notification records to be inserted into sim_notifications.
        Each notification includes:
        - notification_type: what kind of notification
        - destination: where it should appear (slack, studio_center, etc.)
        - suppressed: whether it should be suppressed
        - suppression_reason: why it was suppressed (if applicable)
        - priority_score: 0.0-1.0 score for ordering notifications
        - title/body: notification content
        """
        # Fetch the event
        cursor = self.conn.execute(
            "SELECT * FROM sim_work_events WHERE event_id = ?",
            (event_id,)
        )
        event = cursor.fetchone()
        if not event:
            return []
        
        event = dict(event)
        
        # Parse inferred_signals from JSON string
        signals_raw = event.get('inferred_signals')
        if signals_raw is None:
            signals = []
        elif isinstance(signals_raw, str):
            try:
                signals = json.loads(signals_raw)
            except json.JSONDecodeError:
                signals = []
        else:
            signals = signals_raw
        
        # Fallback: check for blocker records if signals doesn't indicate blocker
        if 'blocked' not in signals and work_item_id:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM sim_blockers WHERE work_item_id = ? AND resolved_at IS NULL",
                (work_item_id,)
            )
            if cursor.fetchone()[0] > 0:
                signals.append('blocked')
        
        # Fallback: check for approval records if signals doesn't indicate approval
        if not any(sig in signals for sig in ['decision_required', 'priority']) and work_item_id:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM sim_approvals WHERE work_item_id = ? AND status = 'pending'",
                (work_item_id,)
            )
            if cursor.fetchone()[0] > 0:
                signals.append('decision_required')
        
        # Store parsed signals back for downstream use
        event['inferred_signals'] = signals
        
        notifications = []
        
        # Rule 1: Blocker created
        if 'blocked' in signals:
            notifications.extend(self._blocker_notification(event, work_item_id))
        
        # Rule 2: Approval required
        if signals and any(sig in ['decision_required', 'priority'] for sig in signals):
            notifications.extend(self._approval_notification(event, work_item_id))
        
        # Rule 3: Status change (non-trivial)
        if work_item_id:
            notifications.extend(self._status_change_notification(event, work_item_id))
        
        # Rule 4: Work item created
        if event.get('event_type') in ['github.pull_request.opened', 'github.issue.opened']:
            notifications.extend(self._work_created_notification(event, work_item_id))
        
        # Rule 5: Suppress routine commits
        if event.get('event_type') == 'github.push':
            notifications.extend(self._suppress_routine_commit(event))
        
        return notifications
    
    def _blocker_notification(self, event: Dict, work_item_id: Optional[str]) -> List[Dict]:
        """Generate blocker created notifications."""
        # Determine destination based on blocker severity
        destination = 'studio_center'
        priority_score = 0.95
        
        if work_item_id:
            cursor = self.conn.execute(
                "SELECT severity FROM sim_blockers WHERE work_item_id = ? AND resolved_at IS NULL LIMIT 1",
                (work_item_id,)
            )
            row = cursor.fetchone()
            if row and dict(row).get('severity') in ['critical', 'high']:
                destination = 'slack'
                priority_score = 0.98
        
        return [{
            'notification_id': f"notif-block-{event['event_id']}-{datetime.utcnow().timestamp()}",
            'event_id': event['event_id'],
            'work_item_id': work_item_id,
            'notification_type': 'blocker_created',
            'destination': destination,
            'suppressed': False,
            'suppression_reason': None,
            'priority_score': priority_score,
            'title': f"Blocker detected: {event.get('event_type', 'Unknown')}",
            'body': f"Event {event['event_id']} signals a blocker. Check Studio Center for details.",
            'metadata': {'signals': event.get('inferred_signals', [])},
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }]
    
    def _approval_notification(self, event: Dict, work_item_id: Optional[str]) -> List[Dict]:
        """Generate approval required notifications."""
        return [{
            'notification_id': f"notif-approval-{event['event_id']}-{datetime.utcnow().timestamp()}",
            'event_id': event['event_id'],
            'work_item_id': work_item_id,
            'notification_type': 'approval_requested',
            'destination': 'studio_center',
            'suppressed': False,
            'suppression_reason': None,
            'priority_score': 0.9,
            'title': f"Approval required: {event.get('event_type', 'Unknown')}",
            'body': f"Event {event['event_id']} requires human approval or confirmation.",
            'metadata': {'signals': event.get('inferred_signals', [])},
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }]
    
    def _status_change_notification(self, event: Dict, work_item_id: Optional[str]) -> List[Dict]:
        """Generate status change notifications for non-trivial transitions."""
        # Check if this event caused a status change
        cursor = self.conn.execute(
            """SELECT st.from_status, st.to_status 
               FROM sim_state_transitions st
               WHERE st.event_id = ? AND st.work_item_id = ?""",
            (event['event_id'], work_item_id)
        )
        transitions = cursor.fetchall()
        
        notifications = []
        for trans in transitions:
            trans = dict(trans)
            from_status = trans.get('from_status')
            to_status = trans.get('to_status')
            
            # Skip if no transition or same status
            if not from_status or not to_status or from_status == to_status:
                continue
            
            # Non-trivial transitions get notifications
            trivial = [
                ('backlog', 'ready'),
                ('ready', 'active')
            ]
            if (from_status, to_status) in trivial:
                continue
            
            notifications.append({
                'notification_id': f"notif-status-{event['event_id']}-{to_status}-{datetime.utcnow().timestamp()}",
                'event_id': event['event_id'],
                'work_item_id': work_item_id,
                'notification_type': 'status_change',
                'destination': 'studio_center',
                'suppressed': False,
                'suppression_reason': None,
                'priority_score': 0.7,
                'title': f"Status changed: {from_status} → {to_status}",
                'body': f"Work item status updated to {to_status}.",
                'metadata': {'from_status': from_status, 'to_status': to_status},
                'created_at': datetime.utcnow().isoformat() + 'Z'
            })
        
        return notifications
    
    def _work_created_notification(self, event: Dict, work_item_id: Optional[str]) -> List[Dict]:
        """Generate work item created notifications."""
        return [{
            'notification_id': f"notif-created-{event['event_id']}-{datetime.utcnow().timestamp()}",
            'event_id': event['event_id'],
            'work_item_id': work_item_id,
            'notification_type': 'work_created',
            'destination': 'studio_center',
            'suppressed': False,
            'suppression_reason': None,
            'priority_score': 0.5,
            'title': f"New work item created from {event.get('event_type', 'event')}",
            'body': f"Work item {work_item_id} created from event {event['event_id']}.",
            'metadata': {'event_type': event.get('event_type')},
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }]
    
    def _suppress_routine_commit(self, event: Dict) -> List[Dict]:
        """Suppress routine push/commit notifications."""
        return [{
            'notification_id': f"notif-suppressed-{event['event_id']}-{datetime.utcnow().timestamp()}",
            'event_id': event['event_id'],
            'work_item_id': None,
            'notification_type': 'routine_suppressed',
            'destination': 'studio_center',
            'suppressed': True,
            'suppression_reason': 'Routine commits are suppressed to reduce noise',
            'priority_score': 0.1,
            'title': f"Suppressed: {event.get('event_type', 'push')}",
            'body': f"Routine commit {event['event_id']} was suppressed by notification policy.",
            'metadata': {'event_type': event.get('event_type')},
            'created_at': datetime.utcnow().isoformat() + 'Z'
        }]
    
    def get_unsent_notifications(self) -> List[Dict]:
        """Retrieve all unsent (non-suppressed) notifications."""
        cursor = self.conn.execute(
            """SELECT * FROM sim_notifications 
               WHERE suppressed = false 
               ORDER BY priority_score DESC, created_at ASC"""
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_suppressed_notifications(self) -> List[Dict]:
        """Retrieve all suppressed notifications."""
        cursor = self.conn.execute(
            """SELECT * FROM sim_notifications 
               WHERE suppressed = true 
               ORDER BY created_at DESC"""
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def insert_notifications(self, notifications: List[Dict]):
        """Insert notification records into the database."""
        for notif in notifications:
            self.conn.execute(
                """INSERT INTO sim_notifications 
                   (notification_id, event_id, work_item_id, notification_type, destination,
                    suppressed, suppression_reason, priority_score, title, body, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    notif['notification_id'],
                    notif['event_id'],
                    notif.get('work_item_id'),
                    notif['notification_type'],
                    notif['destination'],
                    notif['suppressed'],
                    notif.get('suppression_reason'),
                    notif['priority_score'],
                    notif['title'],
                    notif['body'],
                    json.dumps(notif.get('metadata', {})),
                    notif['created_at']
                )
            )
        self.conn.commit()
