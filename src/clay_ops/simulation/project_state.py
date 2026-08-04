"""
Project state engine.
Computes aggregate project state from work items and transitions.
"""
import sqlite3
from datetime import datetime
from typing import Optional


class ProjectStateEngine:
    """Compute and track project state."""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def compute_state(self) -> dict:
        """Compute overall state across all projects."""
        cursor = self.conn.execute("SELECT DISTINCT project_id FROM sim_work_items")
        projects = [row['project_id'] for row in cursor.fetchall()]
        
        return {
            'projects': {pid: self.compute_project_state(pid) for pid in projects}
        }
    
    def compute_project_state(self, project_id: str) -> dict:
        """Compute aggregate state for a project."""
        # Get all work items for project
        cursor = self.conn.execute(
            """SELECT status, priority, confidence, stale_since, last_activity_at
               FROM sim_work_items WHERE project_id = ?""",
            (project_id,)
        )
        items = cursor.fetchall()
        
        if not items:
            return {
                'project_id': project_id,
                'work_items': [],
                'active_count': 0,
                'blocked_count': 0,
                'done_count': 0,
                'pending_count': 0,
                'needs_approval_count': 0,
                'health': 'unknown',
                'stale': False,
                'blockers': [],
                'pending_approvals': []
            }
        
        # Count by status
        status_counts = {}
        for item in items:
            status = item['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get blockers
        work_item_ids = [
            row['work_item_id'] for row in self.conn.execute(
                "SELECT work_item_id FROM sim_work_items WHERE project_id = ?",
                (project_id,)
            ).fetchall()
        ]
        
        placeholders = ','.join('?' * len(work_item_ids))
        blockers = self.conn.execute(
            f"""SELECT b.*, w.title as work_item_title
                FROM sim_blockers b
                JOIN sim_work_items w ON b.work_item_id = w.work_item_id
                WHERE b.work_item_id IN ({placeholders}) AND b.resolved_at IS NULL""",
            work_item_ids
        ).fetchall()
        
        # Get pending approvals
        approvals = self.conn.execute(
            f"""SELECT a.*, w.title as work_item_title
                FROM sim_approvals a
                JOIN sim_work_items w ON a.work_item_id = w.work_item_id
                WHERE a.work_item_id IN ({placeholders}) AND a.status = 'pending'""",
            work_item_ids
        ).fetchall()
        
        # Check for stale items
        stale_count = sum(1 for item in items if item['stale_since'] is not None)
        
        # Determine overall health
        health = self._determine_health(status_counts, blockers, approvals, stale_count)
        
        return {
            'project_id': project_id,
            'work_items': [dict(row) for row in items],
            'active_count': status_counts.get('active', 0),
            'blocked_count': status_counts.get('blocked', 0) + len(blockers),
            'done_count': status_counts.get('done', 0),
            'pending_count': status_counts.get('pending', 0),
            'needs_approval_count': status_counts.get('needs_approval', 0),
            'health': health,
            'stale': stale_count > 0,
            'blockers': [dict(b) for b in blockers],
            'pending_approvals': [dict(a) for a in approvals]
        }
    
    def _determine_health(self, status_counts: dict, blockers: list, approvals: list, stale_count: int) -> str:
        """Determine overall project health."""
        total_items = sum(status_counts.values())
        done_count = status_counts.get('done', 0)
        blocked_count = status_counts.get('blocked', 0) + len(blockers)
        needs_approval_count = status_counts.get('needs_approval', 0) + len(approvals)
        
        # Health heuristics
        if total_items == 0:
            return 'unknown'
        
        # Critical: More blockers than active items
        if blocked_count > status_counts.get('active', 0):
            return 'critical'
        
        # At risk: High stale count or many pending approvals
        if stale_count > total_items * 0.3:
            return 'at_risk'
        if needs_approval_count > total_items * 0.3:
            return 'at_risk'
        
        # Good: Most items done or active
        if done_count + status_counts.get('active', 0) > total_items * 0.7:
            return 'good'
        
        # Needs attention: Mixed state
        return 'needs_attention'
    
    def get_activity_summary(self, project_id: str, hours: int = 24) -> dict:
        """Get activity summary for the last N hours."""
        cutoff = datetime.utcnow()
        cutoff = cutoff.replace(hour=cutoff.hour - hours)
        cutoff_str = cutoff.isoformat() + 'Z'
        
        # Recent events
        cursor = self.conn.execute(
            """SELECT event_type, COUNT(*) as count
               FROM sim_work_events e
               JOIN sim_work_items w ON e.work_item_id = w.work_item_id
               WHERE w.project_id = ? AND e.timestamp > ?
               GROUP BY event_type""",
            (project_id, cutoff_str)
        )
        events = cursor.fetchall()
        
        # Recent state transitions
        cursor = self.conn.execute(
            """SELECT from_status, to_status, COUNT(*) as count
               FROM sim_state_transitions t
               JOIN sim_work_items w ON t.work_item_id = w.work_item_id
               WHERE w.project_id = ? AND t.timestamp > ?
               GROUP BY from_status, to_status""",
            (project_id, cutoff_str)
        )
        transitions = cursor.fetchall()
        
        return {
            'project_id': project_id,
            'period_hours': hours,
            'event_counts': {row['event_type']: row['count'] for row in events},
            'transitions': [dict(t) for t in transitions],
            'total_events': sum(row['count'] for row in events),
            'total_transitions': sum(row['count'] for row in transitions)
        }
    
    def detect_stale_work(self, days: int = 7) -> list:
        """Detect work items that haven't been updated in N days."""
        cutoff = datetime.utcnow()
        cutoff = cutoff.replace(day=cutoff.day - days)
        cutoff_str = cutoff.isoformat() + 'Z'
        
        cursor = self.conn.execute(
            """SELECT work_item_id, title, project_id, status, last_activity_at
               FROM sim_work_items
               WHERE status IN ('active', 'needs_approval')
               AND last_activity_at < ?
               AND (stale_since IS NULL OR stale_since = '')""",
            (cutoff_str,)
        )
        stale_items = cursor.fetchall()
        
        # Update stale_since timestamp
        for item in stale_items:
            self.conn.execute(
                "UPDATE sim_work_items SET stale_since = ? WHERE work_item_id = ?",
                (datetime.utcnow().isoformat() + 'Z', item['work_item_id'])
            )
        self.conn.commit()
        
        return [dict(item) for item in stale_items]
    
    def generate_daily_summary(self, date: Optional[str] = None) -> dict:
        """Generate daily summary for all projects."""
        if date is None:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Get all active projects
        projects = self.conn.execute(
            "SELECT DISTINCT project_id FROM sim_work_items"
        ).fetchall()
        
        summary = {
            'date': date,
            'projects': {},
            'total_events': 0,
            'total_transitions': 0,
            'blockers_created': 0,
            'approvals_created': 0
        }
        
        for project in projects:
            project_id = project['project_id']
            
            # Project state
            state = self.compute_project_state(project_id)
            
            # Activity
            activity = self.get_activity_summary(project_id, 24)
            
            summary['projects'][project_id] = {
                'state': state,
                'activity': activity
            }
            
            summary['total_events'] += activity['total_events']
            summary['total_transitions'] += activity['total_transitions']
            summary['blockers_created'] += len(state['blockers'])
            summary['approvals_created'] += len(state['pending_approvals'])
        
        return summary
