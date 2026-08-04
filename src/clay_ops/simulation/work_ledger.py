"""
Work ledger queries.
Read-only access to work items, blockers, approvals, and transitions.
"""
import sqlite3
from typing import Optional


class WorkLedger:
    """Query work ledger data."""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def get_work_item(self, work_item_id: str) -> Optional[dict]:
        """Get single work item."""
        cursor = self.conn.execute(
            "SELECT * FROM sim_work_items WHERE work_item_id = ?",
            (work_item_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        item = dict(row)
        
        # Get blockers
        blockers = self.conn.execute(
            """SELECT * FROM sim_blockers
               WHERE work_item_id = ? AND resolved_at IS NULL""",
            (work_item_id,)
        ).fetchall()
        item['blockers'] = [dict(b) for b in blockers]
        
        # Get pending approvals
        approvals = self.conn.execute(
            """SELECT * FROM sim_approvals
               WHERE work_item_id = ? AND status = 'pending'""",
            (work_item_id,)
        ).fetchall()
        item['pending_approvals'] = [dict(a) for a in approvals]
        
        # Get state history
        transitions = self.conn.execute(
            """SELECT * FROM sim_state_transitions
               WHERE work_item_id = ?
               ORDER BY timestamp ASC""",
            (work_item_id,)
        ).fetchall()
        item['state_history'] = [dict(t) for t in transitions]
        
        return item
    
    def get_work_items(self, status: Optional[str] = None) -> list:
        """Get all work items with accurate aggregate counts.
        
        Uses subqueries to avoid fan-out count inflation from JOINs.
        """
        base_query = """
            SELECT 
                wi.*,
                COALESCE((
                    SELECT COUNT(*) FROM sim_source_events se 
                    WHERE se.work_item_id = wi.work_item_id
                ), 0) as source_event_count,
                COALESCE((
                    SELECT COUNT(*) FROM sim_blockers b 
                    WHERE b.work_item_id = wi.work_item_id AND b.resolved_at IS NULL
                ), 0) as active_blocker_count,
                COALESCE((
                    SELECT COUNT(*) FROM sim_approvals a 
                    WHERE a.work_item_id = wi.work_item_id AND a.status = 'pending'
                ), 0) as pending_approval_count
            FROM sim_work_items wi
        """
        
        params = []
        if status:
            base_query += " WHERE wi.status = ?"
            params.append(status)
        
        base_query += " ORDER BY wi.updated_at DESC, wi.work_item_id ASC"
        
        cursor = self.conn.execute(base_query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_blockers(self, work_item_id: Optional[str] = None, resolved: bool = False) -> list:
        """Get blockers, optionally filtered by work item or resolution status."""
        if work_item_id:
            if resolved:
                cursor = self.conn.execute(
                    """SELECT b.*, w.title as work_item_title
                       FROM sim_blockers b
                       JOIN sim_work_items w ON b.work_item_id = w.work_item_id
                       WHERE b.work_item_id = ?""",
                    (work_item_id,)
                )
            else:
                cursor = self.conn.execute(
                    """SELECT b.*, w.title as work_item_title
                       FROM sim_blockers b
                       JOIN sim_work_items w ON b.work_item_id = w.work_item_id
                       WHERE b.work_item_id = ? AND b.resolved_at IS NULL""",
                    (work_item_id,)
                )
        else:
            if resolved:
                cursor = self.conn.execute(
                    """SELECT b.*, w.title as work_item_title
                       FROM sim_blockers b
                       JOIN sim_work_items w ON b.work_item_id = w.work_item_id"""
                )
            else:
                cursor = self.conn.execute(
                    """SELECT b.*, w.title as work_item_title
                       FROM sim_blockers b
                       JOIN sim_work_items w ON b.work_item_id = w.work_item_id
                       WHERE b.resolved_at IS NULL"""
                )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_approvals(self, status: str = 'pending', approver: Optional[str] = None) -> list:
        """Get approvals by status and optional approver."""
        query = """SELECT a.*, w.title as work_item_title, w.project_id
                   FROM sim_approvals a
                   JOIN sim_work_items w ON a.work_item_id = w.work_item_id
                   WHERE a.status = ?"""
        params = [status]
        
        if approver:
            query += " AND a.approver = ?"
            params.append(approver)
        
        query += " ORDER BY a.requested_at ASC"
        
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_state_history(self, work_item_id: str) -> list:
        """Get state transition history for a work item."""
        cursor = self.conn.execute(
            """SELECT * FROM sim_state_transitions
               WHERE work_item_id = ?
               ORDER BY timestamp ASC""",
            (work_item_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_events_for_work_item(self, work_item_id: str) -> list:
        """Get all events related to a work item."""
        cursor = self.conn.execute(
            """SELECT * FROM sim_work_events
               WHERE event_id IN (
                   SELECT event_id FROM sim_state_transitions WHERE work_item_id = ?
                   UNION
                   SELECT event_id FROM sim_blockers WHERE work_item_id = ?
               )
               ORDER BY timestamp ASC""",
            (work_item_id, work_item_id)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stale_items(self, days: int = 7) -> list:
        """Get work items that are stale (no activity for N days)."""
        cursor = self.conn.execute(
            """SELECT * FROM sim_work_items
               WHERE stale_since IS NOT NULL
               ORDER BY stale_since ASC"""
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_contradictions(self) -> list:
        """Get work items with contradictory evidence."""
        cursor = self.conn.execute(
            """SELECT w.*, COUNT(t.transition_id) as transition_count
               FROM sim_work_items w
               JOIN sim_state_transitions t ON w.work_item_id = t.work_item_id
               GROUP BY w.work_item_id
               HAVING COUNT(t.transition_id) > 2
               AND EXISTS (
                   SELECT 1 FROM sim_state_transitions t2
                   WHERE t2.work_item_id = w.work_item_id
                   AND t2.from_status = w.status
               )"""
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_state_transitions(self, project_id: Optional[str] = None, limit: int = 50) -> list:
        """Get state transitions, optionally filtered by project."""
        if project_id:
            cursor = self.conn.execute(
                """SELECT t.*, w.title as work_item_title, w.project_id
                   FROM sim_state_transitions t
                   JOIN sim_work_items w ON t.work_item_id = w.work_item_id
                   WHERE w.project_id = ?
                   ORDER BY t.timestamp DESC
                   LIMIT ?""",
                (project_id, limit)
            )
        else:
            cursor = self.conn.execute(
                """SELECT t.*, w.title as work_item_title, w.project_id
                   FROM sim_state_transitions t
                   JOIN sim_work_items w ON t.work_item_id = w.work_item_id
                   ORDER BY t.timestamp DESC
                   LIMIT ?""",
                (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_events_in_timeframe(self, hours: int = 24) -> list:
        """Get events from the last N hours."""
        cursor = self.conn.execute(
            """SELECT * FROM sim_work_events
               WHERE datetime(timestamp) >= datetime('now', ?)
               ORDER BY timestamp DESC""",
            (f'-{hours} hours',)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_notifications(self, status: str = 'unread') -> list:
        """Get notifications filtered by status."""
        if status == 'unread':
            cursor = self.conn.execute(
                """SELECT * FROM sim_notifications
                   WHERE status IN ('pending', 'ready_to_send')
                   ORDER BY priority DESC, timestamp ASC"""
            )
        else:
            cursor = self.conn.execute(
                """SELECT * FROM sim_notifications
                   WHERE status = ?
                   ORDER BY timestamp DESC""",
                (status,)
            )
        return [dict(row) for row in cursor.fetchall()]
