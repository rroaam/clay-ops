from __future__ import annotations


class EventLog:
    def __init__(self, store):
        self.store = store

    def append(self, run_id, event_type, status, payload, actor="agent:clay-ops"):
        return self.store.append_event(run_id, event_type, status, payload, actor)

    def timeline(self, run_id):
        return self.store.list_events(run_id)

    def projection(self, run_id):
        return self.store.project_run(run_id)
