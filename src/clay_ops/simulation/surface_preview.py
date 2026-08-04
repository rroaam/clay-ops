from __future__ import annotations

from typing import Dict
from .project_state import ProjectStateEngine
from .work_ledger import WorkLedger


class SurfaceGenerator:
    """Generates preview surfaces for different views."""
    
    def __init__(self, project_state: ProjectStateEngine, ledger: WorkLedger):
        self.project_state = project_state
        self.ledger = ledger
    
    def generate_studio_center(self) -> dict:
        """Generate Studio Center surface preview."""
        state = self.project_state.compute_state()
        
        projects = state.get('projects', {})
        all_work_items = []
        all_blockers = []
        
        for pid, pstate in projects.items():
            all_work_items.extend(pstate.get('work_items', []))
            all_blockers.extend(pstate.get('blockers', []))
        
        # Count states
        total_items = len(all_work_items)
        active_count = sum(1 for w in all_work_items if w.get('status') == 'active')
        blocked_count = len(all_blockers)
        done_count = sum(1 for w in all_work_items if w.get('status') == 'done')
        pending_count = sum(1 for w in all_work_items if w.get('status') == 'pending')
        
        # Find top priorities (high priority, not done)
        top_priorities = []
        for w in all_work_items:
            if w.get('priority') == 'high' and w.get('status') not in ('done', 'cancelled'):
                top_priorities.append({
                    'work_item_id': w.get('work_item_id'),
                    'title': w.get('title'),
                    'status': w.get('status'),
                    'priority': w.get('priority')
                })
        top_priorities = top_priorities[:5]  # Top 5
        
        # Items needing attention (high or critical priority, not done, not in_progress)
        attention_items = []
        for w in all_work_items:
            if (w.get('priority') in ('high', 'critical') 
                and w.get('status') not in ('done', 'cancelled', 'in_progress')):
                attention_items.append({
                    'work_item_id': w.get('work_item_id'),
                    'title': w.get('title'),
                    'status': w.get('status'),
                    'priority': w.get('priority')
                })
        attention_items = attention_items[:10]
        
        return {
            'total_projects': len(projects),
            'active_count': active_count,
            'blocked_count': blocked_count,
            'done_count': done_count,
            'pending_count': pending_count,
            'top_priorities': top_priorities,
            'attention_items': attention_items,
            'total_items': total_items
        }
    
    def generate_project_tracker(self, project_id: str) -> dict:
        """Generate Project Tracker surface preview."""
        project_state = self.project_state.compute_project_state(project_id)
        
        work_items = project_state.get('work_items', [])
        blockers = project_state.get('blockers', [])
        approvals = project_state.get('approvals', [])
        
        # Get state transitions
        transitions = self.ledger.get_state_transitions(project_id)
        
        # Build activity feed (recent transitions + blockers)
        activity = []
        for t in transitions[:20]:
            activity.append({
                'type': 'transition',
                'description': f"{t.get('work_item_id')}: {t.get('from_status')} -> {t.get('to_status')}",
                'timestamp': t.get('timestamp')
            })
        
        for b in blockers[:10]:
            activity.append({
                'type': 'blocker',
                'description': f"{b.get('work_item_id')}: {b.get('reason')}",
                'timestamp': b.get('timestamp')
            })
        
        # Sort by timestamp
        activity.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'project_id': project_id,
            'work_items': work_items,
            'blockers': blockers,
            'approvals': approvals,
            'activity': activity[:20],
            'stats': {
                'total_work_items': len(work_items),
                'total_blockers': len(blockers),
                'total_approvals': len(approvals)
            }
        }
    
    def generate_activity_stream(self, hours: int = 24) -> dict:
        """Generate Activity Stream surface preview."""
        events = self.ledger.get_events_in_timeframe(hours)
        
        # Build activity feed
        activity = []
        for e in events:
            event_type = e.get('event_type')
            
            if event_type == 'state_transition':
                description = f"State change: {e.get('from_status')} -> {e.get('to_status')}"
            elif event_type == 'work_item_created':
                description = f"Work item created: {e.get('title', 'Untitled')}"
            elif event_type == 'blocker_created':
                description = f"Blocker: {e.get('reason', 'No reason')}"
            elif event_type == 'comment':
                description = f"Comment by {e.get('commenter', 'unknown')}"
            elif event_type == 'attachment':
                description = f"Attachment: {e.get('attachment_name', 'Unknown')}"
            else:
                description = event_type
            
            activity.append({
                'type': event_type,
                'description': description,
                'timestamp': e.get('timestamp'),
                'work_item_id': e.get('work_item_id')
            })
        
        return {
            'timeframe_hours': hours,
            'activity': activity,
            'total_events': len(activity)
        }
    
    def generate_daily_stack(self, user_filter: str = None) -> dict:
        """Generate Daily Work Stack surface preview.
        
        Args:
            user_filter: If provided, only show items assigned to this user
        """
        state = self.project_state.compute_state()
        
        all_items = []
        for project_id, project_state in state.get('projects', {}).items():
            for item in project_state.get('work_items', []):
                if user_filter and item.get('owner') != user_filter:
                    continue
                all_items.append(item)
        
        # Filter by status
        done_items = [i for i in all_items if i.get('status') == 'done']
        blocked_items = [i for i in all_items if i.get('status') == 'blocked']
        pending_items = [i for i in all_items if i.get('status') in ['pending', 'ready']]
        
        # Sort done items by most recently updated
        done_items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        # Sort blocked items by priority and staleness
        blocked_items.sort(
            key=lambda x: (
                x.get('priority', 'low'),
                x.get('last_activity_at', '')
            )
        )
        
        # Sort pending items by priority and then updated_at
        pending_items.sort(
            key=lambda x: (
                x.get('priority', 'low'),
                x.get('updated_at', '')
            ),
            reverse=True
        )
        
        # Get pending approvals
        pending_approvals = self.ledger.get_approvals(status='pending')
        
        return {
            'summary': {
                'total_items': len(all_items),
                'done_count': len(done_items),
                'blocked_count': len(blocked_items),
                'pending_count': len(pending_items),
                'pending_approvers': len(pending_approvals)
            },
            'done_items': done_items[:10],
            'blocked_items': blocked_items[:10],
            'pending_items': pending_items[:10],
            'pending_approvals': pending_approvals
        }
    
    def generate_notifications_preview(self) -> dict:
        """Generate Notifications surface preview."""
        notifications = self.ledger.get_notifications(status='unread')
        
        # Categorize notifications
        urgent = []
        high = []
        normal = []
        low = []
        
        for n in notifications:
            priority = n.get('priority', 'normal')
            notif_data = {
                'notification_id': n.get('notification_id'),
                'type': n.get('notification_type'),
                'message': n.get('message'),
                'priority': priority,
                'timestamp': n.get('timestamp'),
                'work_item_id': n.get('work_item_id')
            }
            
            if priority == 'urgent':
                urgent.append(notif_data)
            elif priority == 'high':
                high.append(notif_data)
            elif priority == 'low':
                low.append(notif_data)
            else:
                normal.append(notif_data)
        
        return {
            'urgent': urgent,
            'high': high,
            'normal': normal,
            'low': low,
            'total_unread': len(notifications)
        }
