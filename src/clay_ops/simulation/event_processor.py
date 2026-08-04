"""
Event processor for simulation.
Ingests fixtures, normalizes, deduplicates, and processes events.
"""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .schema import SIMULATION_SCHEMA
from .notification_policy import NotificationPolicy


class EventProcessor:
    """Process events through the simulation pipeline."""
    
    # State transition rules
    VALID_TRANSITIONS = {
        'backlog': ['ready', 'active', 'cancelled'],
        'ready': ['active', 'cancelled'],
        'active': ['done', 'blocked', 'needs_approval', 'cancelled'],
        'blocked': ['active', 'cancelled'],
        'needs_approval': ['active', 'done', 'cancelled'],
        'done': ['active'],  # Can reopen
        'cancelled': ['ready'],  # Can reactivate
    }
    
    def __init__(self, db_path: str = "data/simulation/clay-ops.sim.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self.notification_policy = NotificationPolicy(self.conn)
        
    def _init_schema(self):
        """Initialize simulation database schema."""
        self.conn.executescript(SIMULATION_SCHEMA)
        self.conn.commit()
    
    def ingest_fixture(self, fixture_path: str) -> dict:
        """Ingest a fixture event file."""
        path = Path(fixture_path)
        if not path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")
        
        with open(path) as f:
            raw_event = json.load(f)
        
        return self.process_event(raw_event)
    
    def process_fixture(self, fixture: dict) -> dict:
        """Process a fixture event dict (already loaded)."""
        return self.process_event(fixture)
    
    def process_event(self, raw_event: dict) -> dict:
        """Process a raw event through the full pipeline."""
        # Normalize event
        event = self._normalize_event(raw_event)
        
        # Check for duplicate
        if self._is_duplicate(event):
            return {
                'status': 'duplicate',
                'event_id': event['event_id'],
                'message': 'Event already processed'
            }
        
        # Store event
        self._store_event(event)
        
        # Process event
        result = self._process_event(event)
        
        # Evaluate notification policy and store notifications
        work_item_id = result.get('work_item_id')
        notifications = self.notification_policy.evaluate_event(
            event['event_id'], 
            work_item_id
        )
        stored_count = 0
        for notification in notifications:
            self._store_notification(notification)
            stored_count += 1
        
        return {
            'status': 'processed',
            'event_id': event['event_id'],
            'work_item_id': result.get('work_item_id'),
            'work_item_updated': result.get('work_item_updated', False),
            'state_transition': result.get('state_transition'),
            'blockers_detected': result.get('blockers_detected', []),
            'approvals_required': result.get('approvals_required', []),
            'notifications_generated': len(notifications),
            'notifications_stored': stored_count
        }
    
    def _normalize_event(self, raw: dict) -> dict:
        """Normalize raw event to work-event schema."""
        event_type = raw.get('event_type', '')
        parts = event_type.split('.', 1)
        system = parts[0] if parts else 'unknown'
        action = parts[1] if len(parts) > 1 else 'unknown'
        
        # Generate source pointer
        if system == 'github':
            source_pointer = f"github.com/clay/{raw.get('repository')}/{action}/{raw.get('pr_number', raw.get('deployment_id'))}"
        elif system == 'slack':
            source_pointer = f"{raw['workspace']}.slack.com/archives/{raw['channel_id']}/p{raw['message_id']}"
        elif system == 'figma':
            source_pointer = f"figma.com/file/{raw.get('file_key')}"
        elif system == 'drive':
            source_pointer = f"drive.google.com/file/d/{raw.get('document_id')}"
        elif system == 'local':
            source_pointer = f"local/{raw.get('repository')}/{raw.get('commit_hash')}"
        else:
            raise ValueError(f"Unknown source system: {system}")
        
        # Generate event ID
        event_id = f"evt-{hashlib.sha256(source_pointer.encode()).hexdigest()[:8]}"
        
        # Detect inferred signals
        signals = []
        text = (raw.get('text', '') + ' ' + raw.get('message', '')).lower()
        if 'blocked' in text or 'blocker' in text:
            signals.append('blocked')
        if 'decision' in text or 'approval' in text:
            signals.append('decision_required')
        if 'priority' in text or 'critical' in text:
            signals.append('priority')
        
        return {
            'schema_version': '1.0.0',
            'event_id': event_id,
            'event_type': event_type,
            'source_system': system,
            'source_pointer': source_pointer,
            'timestamp': raw.get('timestamp'),
            'payload': raw,
            'received_at': datetime.utcnow().isoformat() + 'Z',
            'inferred_signals': signals
        }
    
    def _is_duplicate(self, event: dict) -> bool:
        """Check if event already exists."""
        cursor = self.conn.execute(
            "SELECT event_id FROM sim_work_events WHERE source_system = ? AND source_pointer = ?",
            (event['source_system'], event['source_pointer'])
        )
        return cursor.fetchone() is not None
    
    def _store_event(self, event: dict):
        """Store normalized event in simulation database."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO sim_work_events
            (event_id, event_type, source_system, source_pointer, timestamp, payload, inferred_signals, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event['event_id'],
                event['event_type'],
                event['source_system'],
                event['source_pointer'],
                event['timestamp'],
                json.dumps(event['payload']) if isinstance(event['payload'], dict) else event['payload'],
                json.dumps(event.get('inferred_signals', [])),
                event['received_at']
            )
        )
        self.conn.commit()
    
    def _process_event(self, event: dict) -> dict:
        """Process event and update work items."""
        result = {'work_item_id': None, 'state_transition': None, 'blockers_detected': [], 'approvals_required': []}
        payload = event['payload']
        event_type = event['event_type']
        signals = event.get('inferred_signals', [])
        
        # Map to work item
        work_item = self._map_to_work_item(event)
        
        if work_item:
            result['work_item_id'] = work_item['work_item_id']
            
            # Determine state transition
            new_status = self._determine_status(event, work_item['status'])
            
            if new_status and new_status != work_item['status']:
                # Check if transition is valid
                if self._is_valid_transition(work_item['status'], new_status):
                    transition = self._create_state_transition(
                        work_item['work_item_id'],
                        work_item['status'],
                        new_status,
                        event
                    )
                    result['state_transition'] = transition
                else:
                    # Contradiction detected
                    result['contradiction'] = {
                        'from_status': work_item['status'],
                        'to_status': new_status,
                        'requires_human_review': True
                    }
            
            # Detect blockers
            if 'blocked' in signals:
                blocker = self._create_blocker(work_item['work_item_id'], event)
                result['blockers_detected'] = [blocker]
            
            # Detect approval requirements
            if 'decision_required' in signals:
                approval = self._create_approval(work_item['work_item_id'], event)
                result['approvals_required'] = [approval]
        
        return result
    
    def _map_to_work_item(self, event: dict) -> Optional[dict]:
        """Map event to existing or new work item."""
        payload = event['payload']
        
        # Try to find existing work item
        work_item_id = self._find_work_item(event)
        
        if work_item_id:
            cursor = self.conn.execute(
                "SELECT * FROM sim_work_items WHERE work_item_id = ?",
                (work_item_id,)
            )
            row = cursor.fetchone()
            if row:
                # Update last_activity_at
                self.conn.execute(
                    "UPDATE sim_work_items SET last_activity_at = ?, updated_at = ? WHERE work_item_id = ?",
                    (event['timestamp'], datetime.utcnow().isoformat() + 'Z', work_item_id)
                )
                self.conn.commit()
                return dict(row)
        
        # Create new work item if event warrants it
        if self._should_create_work_item(event):
            new_item = self._create_work_item(event)
            return new_item
        
        return None
    
    def _find_work_item(self, event: dict) -> Optional[str]:
        """Find existing work item related to event."""
        payload = event['payload']
        
        # Search by PR number, file key, or mentions
        search_terms = []
        
        if payload.get('pr_number'):
            search_terms.append(f"#{payload['pr_number']}")
        if payload.get('file_key'):
            search_terms.append(payload['file_key'])
        if payload.get('pr_title'):
            search_terms.extend(payload['pr_title'].lower().split())
        if payload.get('text'):
            # Look for project mentions
            text = payload['text'].lower()
            if 'slack integration' in text:
                search_terms.append('slack')
        
        # Query work items
        for term in search_terms:
            cursor = self.conn.execute(
                "SELECT work_item_id FROM sim_work_items WHERE title LIKE ? OR description LIKE ? LIMIT 1",
                (f"%{term}%", f"%{term}%")
            )
            row = cursor.fetchone()
            if row:
                return row['work_item_id']
        
        return None
    
    def _should_create_work_item(self, event: dict) -> bool:
        """Determine if event should create a new work item."""
        signals = event.get('inferred_signals', [])
        event_type = event['event_type']
        
        # Create work item for:
        # - GitHub PR opened (if it's a feature)
        # - Slack message with priority/critical signals
        # - Decision messages
        
        if event_type == 'github.pull_request.opened':
            return True
        if 'priority' in signals or 'decision_required' in signals:
            text = event['payload'].get('text', '').lower()
            if 'q3' in text or 'priority' in text or 'critical' in text:
                return True
        
        return False
    
    def _create_work_item(self, event: dict) -> dict:
        """Create new work item from event."""
        payload = event['payload']
        event_type = event['event_type']
        
        # Generate work item ID
        work_item_id = f"work-{event['event_id'][4:]}"
        
        # Determine title and description
        title = 'Untitled'
        description = ''
        if event_type == 'github.pull_request.opened':
            title = payload.get('pr_title', 'Untitled PR')
            description = f"PR #{payload.get('pr_number')} by {payload.get('author')}"
        elif event_type == 'slack.message':
            text = payload.get('text', '')
            title = text[:80] + '...' if len(text) > 80 else text
            description = text
        
        # Determine owner
        owner = payload.get('author', payload.get('user', 'unknown'))
        
        # Create work item
        self.conn.execute(
            """INSERT INTO sim_work_items 
               (work_item_id, title, description, project_id, objective_id, status, priority, 
                owner, created_at, updated_at, last_activity_at, confidence, review_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                work_item_id,
                title,
                description,
                'proj-slack-integration',  # Could be inferred
                None,
                'backlog',  # Initial status
                'medium',  # Initial priority
                owner,
                event['timestamp'],
                event['timestamp'],
                event['timestamp'],
                0.5,  # Initial confidence
                'inferred'
            )
        )
        self.conn.commit()
        
        return {
            'work_item_id': work_item_id,
            'title': title,
            'status': 'backlog'
        }
    
    def _determine_status(self, event: dict, current_status: str) -> Optional[str]:
        """Determine new status based on event."""
        event_type = event['event_type']
        
        # Event-specific status mappings
        if event_type == 'github.pull_request.opened':
            return 'active' if current_status == 'backlog' else None
        elif event_type == 'github.pull_request.merged':
            return 'done' if current_status == 'active' else None
        elif event_type == 'local.git.commit':
            return 'active' if current_status == 'backlog' else None
        elif 'blocked' in event.get('inferred_signals', []):
            return 'blocked'
        
        return None
    
    def _is_valid_transition(self, from_status: str, to_status: str) -> bool:
        """Check if state transition is valid."""
        allowed = self.VALID_TRANSITIONS.get(from_status, [])
        return to_status in allowed
    
    def _create_state_transition(self, work_item_id: str, from_status: str, to_status: str, event: dict) -> dict:
        """Create state transition record."""
        transition_id = f"trans-{event['event_id'][4:]}"
        
        self.conn.execute(
            """INSERT INTO sim_state_transitions 
               (transition_id, work_item_id, from_status, to_status, transition_type, event_id, timestamp, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                transition_id,
                work_item_id,
                from_status,
                to_status,
                'evidence_based',
                event['event_id'],
                event['timestamp'],
                0.8
            )
        )
        
        # Update work item status
        self.conn.execute(
            "UPDATE sim_work_items SET status = ?, updated_at = ?, version = version + 1 WHERE work_item_id = ?",
            (to_status, event['timestamp'], work_item_id)
        )
        self.conn.commit()
        
        return {
            'transition_id': transition_id,
            'from_status': from_status,
            'to_status': to_status,
            'confidence': 0.8
        }
    
    def _create_blocker(self, work_item_id: str, event: dict) -> dict:
        """Create blocker record."""
        blocker_id = f"block-{event['event_id'][4:]}"
        
        # Extract reason from text
        text = event['payload'].get('text', '')
        reason = text[:200] if text else 'Blocked'
        
        self.conn.execute(
            """INSERT INTO sim_blockers 
               (blocker_id, work_item_id, reason, severity, raised_at, event_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (blocker_id, work_item_id, reason, 'high', event['timestamp'], event['event_id'])
        )
        self.conn.commit()
        
        return {
            'blocker_id': blocker_id,
            'work_item_id': work_item_id,
            'reason': reason,
            'severity': 'high'
        }
    
    def _create_approval(self, work_item_id: str, event: dict) -> dict:
        """Create approval requirement."""
        approval_id = f"appr-{event['event_id'][4:]}"
        
        # Determine approval type
        text = event['payload'].get('text', '').lower()
        if 'decision' in text:
            approval_type = 'decision_confirmation'
        elif 'owner' in text:
            approval_type = 'owner_assignment'
        else:
            approval_type = 'status_change'
        
        # Create options
        options = [
            {'id': 'approve', 'label': 'Approve', 'effect': 'Proceed with change'},
            {'id': 'reject', 'label': 'Reject', 'effect': 'Block change'},
            {'id': 'defer', 'label': 'Defer', 'effect': 'Requires more information'}
        ]
        
        # Create recommendation
        recommendation = {
            'option_id': 'approve',
            'reason': 'Based on event context and team activity',
            'confidence': 0.6
        }
        
        self.conn.execute(
            """INSERT INTO sim_approvals 
               (approval_id, work_item_id, approval_type, requester, approver, decision_required, 
                options, recommendation, evidence, requested_at, due_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                approval_id,
                work_item_id,
                approval_type,
                event['payload'].get('user', 'system'),
                'ryan',  # Default approver
                'Review and approve decision',
                json.dumps(options),
                json.dumps(recommendation),
                json.dumps([event['event_id']]),
                event['timestamp'],
                event['timestamp'],  # Due immediately for simulation
                'pending'
            )
        )
        self.conn.commit()
        
        return {
            'approval_id': approval_id,
            'approval_type': approval_type,
            'approver': 'ryan'
        }
    
    def _store_notification(self, notification: dict):
        """Store a notification record via notification policy."""
        self.notification_policy.insert_notifications([notification])
    
    def close(self):
        """Close database connection."""
        self.conn.close()
