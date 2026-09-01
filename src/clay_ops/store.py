from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .policy import ApprovalError
from .redaction import redact

SCHEMA_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sanitize(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


class ImmutableRecordError(RuntimeError):
    pass


class OperationalStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self._transaction_depth = 0
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY, packet TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, workflow_id TEXT NOT NULL, execution_mode TEXT NOT NULL CHECK(execution_mode IN ('structured','manual/unstructured')), created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_type TEXT NOT NULL, status TEXT NOT NULL, actor TEXT NOT NULL, recorded_at TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL, UNIQUE(run_id,sequence));
            CREATE TABLE IF NOT EXISTS approvals(approval_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, action TEXT NOT NULL, scope TEXT NOT NULL, reason TEXT NOT NULL, requested_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approval_decisions(decision_id TEXT PRIMARY KEY, approval_id TEXT NOT NULL UNIQUE, decision TEXT NOT NULL CHECK(decision IN ('approved','rejected','changes_requested')), actor TEXT NOT NULL, scope TEXT NOT NULL, reason TEXT, recorded_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(artifact_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(run_id,relative_path));
            CREATE TABLE IF NOT EXISTS canon_snapshots(snapshot_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reference_id TEXT NOT NULL, repository_path TEXT NOT NULL, relative_file_path TEXT NOT NULL, git_commit TEXT NOT NULL, blob_hash TEXT NOT NULL, content_sha256 TEXT NOT NULL, authority_class TEXT NOT NULL, recorded_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS results(result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL, payload TEXT NOT NULL, completed INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS creative_projects(project_id TEXT PRIMARY KEY, name TEXT NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generation_requests(request_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES creative_projects(project_id), run_id TEXT NOT NULL, status TEXT NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS creative_assets(asset_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES creative_projects(project_id), request_id TEXT REFERENCES generation_requests(request_id), run_id TEXT, parent_asset_id TEXT REFERENCES creative_assets(asset_id), relative_path TEXT NOT NULL UNIQUE, document TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS creative_contexts(context_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES creative_projects(project_id), document TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS creative_assets_project_idx ON creative_assets(project_id, created_at);
            CREATE INDEX IF NOT EXISTS generation_requests_project_idx ON generation_requests(project_id, created_at);
            CREATE INDEX IF NOT EXISTS creative_contexts_project_idx ON creative_contexts(project_id, updated_at);
            CREATE TABLE IF NOT EXISTS work_items(work_item_id TEXT PRIMARY KEY, requester TEXT NOT NULL, requester_slack_id TEXT NOT NULL, surface TEXT NOT NULL, channel_id TEXT NOT NULL, thread_id TEXT NOT NULL, requested_outcome TEXT NOT NULL, status TEXT NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS work_item_events(work_item_event_id TEXT PRIMARY KEY, work_item_id TEXT NOT NULL REFERENCES work_items(work_item_id), sequence INTEGER NOT NULL, event_type TEXT NOT NULL, status TEXT NOT NULL, actor TEXT NOT NULL, recorded_at TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL, UNIQUE(work_item_id,sequence));
            CREATE INDEX IF NOT EXISTS work_items_thread_idx ON work_items(channel_id, thread_id, created_at);
            CREATE INDEX IF NOT EXISTS work_items_requester_idx ON work_items(requester, created_at);
            CREATE TRIGGER IF NOT EXISTS work_item_events_no_update BEFORE UPDATE ON work_item_events BEGIN SELECT RAISE(ABORT,'IMMUTABLE_WORK_ITEM_EVENTS'); END;
            CREATE TRIGGER IF NOT EXISTS work_item_events_no_delete BEFORE DELETE ON work_item_events BEGIN SELECT RAISE(ABORT,'IMMUTABLE_WORK_ITEM_EVENTS'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'IMMUTABLE_EVENTS'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'IMMUTABLE_EVENTS'); END;
            CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON approval_decisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_APPROVAL_DECISIONS'); END;
            CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON approval_decisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_APPROVAL_DECISIONS'); END;
            CREATE TRIGGER IF NOT EXISTS approvals_no_update BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT,'IMMUTABLE_APPROVAL_REQUESTS'); END;
            CREATE TRIGGER IF NOT EXISTS approvals_no_delete BEFORE DELETE ON approvals BEGIN SELECT RAISE(ABORT,'IMMUTABLE_APPROVAL_REQUESTS'); END;
            CREATE TRIGGER IF NOT EXISTS completed_results_no_update BEFORE UPDATE ON results WHEN OLD.completed=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_COMPLETED_RESULT'); END;
            CREATE TRIGGER IF NOT EXISTS completed_results_no_delete BEFORE DELETE ON results WHEN OLD.completed=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_COMPLETED_RESULT'); END;
            CREATE TRIGGER IF NOT EXISTS artifacts_no_update BEFORE UPDATE ON artifacts BEGIN SELECT RAISE(ABORT,'IMMUTABLE_ARTIFACTS'); END;
            CREATE TRIGGER IF NOT EXISTS artifacts_no_delete BEFORE DELETE ON artifacts BEGIN SELECT RAISE(ABORT,'IMMUTABLE_ARTIFACTS'); END;
            CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON canon_snapshots BEGIN SELECT RAISE(ABORT,'IMMUTABLE_CANON_SNAPSHOTS'); END;
            CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON canon_snapshots BEGIN SELECT RAISE(ABORT,'IMMUTABLE_CANON_SNAPSHOTS'); END;
            """
        )
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_decision_per_approval ON approval_decisions(approval_id)")
        self.db.commit()

    @contextmanager
    def transaction(self):
        outermost = self._transaction_depth == 0
        if outermost:
            self.db.execute("BEGIN IMMEDIATE")
        self._transaction_depth += 1
        try:
            yield self
        except Exception:
            self._transaction_depth -= 1
            if outermost:
                self.db.rollback()
            raise
        else:
            self._transaction_depth -= 1
            if outermost:
                self.db.commit()

    def _execute(self, sql, params=()):
        try:
            cur = self.db.execute(sql, params)
            if self._transaction_depth == 0:
                self.db.commit()
            return cur
        except sqlite3.IntegrityError as exc:
            if self._transaction_depth == 0:
                self.db.rollback()
            if "IMMUTABLE" in str(exc):
                raise ImmutableRecordError(str(exc)) from None
            raise

    def save_task(self, packet):
        self._execute("INSERT INTO tasks VALUES(?,?,?)", (packet["task_id"], canonical(sanitize(packet)), utc_now()))

    def create_run(self, run_id, task_id, workflow_id, execution_mode="structured"):
        self._execute("INSERT INTO runs VALUES(?,?,?,?,?)", (run_id, task_id, workflow_id, execution_mode, utc_now()))

    def append_event(self, run_id, event_type, status, payload, actor="agent:clay-ops"):
        payload = sanitize(payload)
        standalone = self._transaction_depth == 0
        if standalone:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT sequence,record_hash FROM events WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
            sequence = row["sequence"] + 1 if row else 1
            previous = row["record_hash"] if row else "GENESIS"
            event_id = f"event-{uuid.uuid4().hex}"
            recorded = utc_now()
            basis = {"schema_version": SCHEMA_VERSION, "event_id": event_id, "run_id": run_id, "sequence": sequence, "event_type": event_type, "status": status, "actor": actor, "recorded_at": recorded, "payload": payload, "previous_hash": previous}
            basis["record_hash"] = hashlib.sha256(canonical(basis).encode()).hexdigest()
            self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, run_id, sequence, event_type, status, actor, recorded, canonical(payload), previous, basis["record_hash"]))
            if standalone:
                self.db.commit()
            return basis
        except Exception:
            if standalone:
                self.db.rollback()
            raise

    def list_events(self, run_id):
        rows = self.db.execute("SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["schema_version"] = SCHEMA_VERSION
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    def project_run(self, run_id):
        run = self.db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        events = self.list_events(run_id)
        return {**(dict(run) if run else {"run_id": run_id}), "status": events[-1]["status"] if events else "unknown", "last_event": events[-1] if events else None, "event_count": len(events)}

    def list_runs(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()]

    def list_artifacts(self, run_id=None):
        if run_id is None:
            rows = self.db.execute("SELECT * FROM artifacts ORDER BY created_at DESC").fetchall()
        else:
            rows = self.db.execute("SELECT * FROM artifacts WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def list_canon_snapshots(self, run_id):
        return [dict(row) for row in self.db.execute("SELECT * FROM canon_snapshots WHERE run_id=? ORDER BY recorded_at", (run_id,)).fetchall()]

    def get_task(self, task_id):
        row = self.db.execute("SELECT packet FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return json.loads(row["packet"]) if row else None

    def save_result(self, result_id, run_id, task_id, payload, completed=True):
        self._execute("INSERT INTO results VALUES(?,?,?,?,?,?)", (result_id, run_id, task_id, canonical(sanitize(payload)), 1 if completed else 0, utc_now()))

    def get_result_for_run(self, run_id):
        row = self.db.execute("SELECT payload FROM results WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def create_approval(self, approval_id, run_id, action, scope, reason):
        requested = utc_now()
        self._execute("INSERT INTO approvals VALUES(?,?,?,?,?,?)", (approval_id, run_id, action, canonical(scope), redact(reason), requested))
        return {"schema_version": SCHEMA_VERSION, "approval_id": approval_id, "run_id": run_id, "action": action, "scope": scope, "reason": redact(reason), "status": "pending", "requested_at": requested}

    def resolve_approval(self, approval_id, approve, actor, scope, reason=None, request_changes=False):
        standalone = self._transaction_depth == 0
        if standalone:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if not row:
                raise ApprovalError([{"code": "APPROVAL_NOT_FOUND", "message": "Approval not found."}])
            if json.loads(row["scope"]) != scope:
                raise ApprovalError([{"code": "APPROVAL_SCOPE_MISMATCH", "message": "Resolution scope does not match request."}])
            if self.db.execute("SELECT 1 FROM approval_decisions WHERE approval_id=?", (approval_id,)).fetchone():
                raise ApprovalError([{"code": "APPROVAL_REPLAY", "message": "Approval already resolved."}])
            decision = "changes_requested" if request_changes else ("approved" if approve else "rejected")
            decision_id = f"decision-{uuid.uuid4().hex}"
            recorded = utc_now()
            self.db.execute("INSERT INTO approval_decisions VALUES(?,?,?,?,?,?,?)", (decision_id, approval_id, decision, actor, canonical(scope), redact(reason or ""), recorded))
            if standalone:
                self.db.commit()
            return {"decision_id": decision_id, "approval_id": approval_id, "decision": decision, "actor": actor, "scope": scope, "reason": redact(reason or ""), "recorded_at": recorded}
        except ApprovalError:
            if standalone:
                self.db.rollback()
            raise
        except sqlite3.IntegrityError:
            if standalone:
                self.db.rollback()
            raise ApprovalError([{"code": "APPROVAL_REPLAY", "message": "Approval already resolved."}]) from None
        except Exception:
            if standalone:
                self.db.rollback()
            raise

    def list_approval_decisions(self, approval_id):
        return [dict(row) for row in self.db.execute("SELECT * FROM approval_decisions WHERE approval_id=? ORDER BY recorded_at", (approval_id,)).fetchall()]

    def get_approval(self, approval_id):
        row = self.db.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["scope"] = json.loads(item["scope"])
        decisions = self.list_approval_decisions(approval_id)
        item["status"] = decisions[-1]["decision"] if decisions else "pending"
        return item

    def list_approvals(self):
        return [self.get_approval(row["approval_id"]) for row in self.db.execute("SELECT approval_id FROM approvals ORDER BY requested_at DESC")]

    def record_artifact(self, artifact_id, run_id, relative_path, sha256, kind):
        self._execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?)", (artifact_id, run_id, relative_path, sha256, kind, utc_now()))
        return {"artifact_id": artifact_id, "run_id": run_id, "relative_path": relative_path, "sha256": sha256, "kind": kind}

    def snapshot_canon(self, run_id, ref):
        snapshot_id = f"snapshot-{uuid.uuid4().hex}"
        self._execute("INSERT INTO canon_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)", (snapshot_id, run_id, ref["id"], ref["repository_path"], ref["relative_file_path"], ref["git_commit"], ref["blob_hash"], ref["content_sha256"], ref["authority_class"], utc_now()))
        return snapshot_id

    def create_project(self, document):
        value = sanitize(document)
        self._execute(
            "INSERT INTO creative_projects VALUES(?,?,?,?)",
            (value["project_id"], value["name"], canonical(value), value["created_at"]),
        )
        return value

    def get_project(self, project_id):
        row = self.db.execute("SELECT document FROM creative_projects WHERE project_id=?", (project_id,)).fetchone()
        return json.loads(row["document"]) if row else None

    def list_projects(self):
        return [json.loads(row["document"]) for row in self.db.execute("SELECT document FROM creative_projects ORDER BY created_at DESC")]

    def update_project(self, project_id, *, name=None, tags=None):
        """Rename and/or retag an existing project record without deleting
        or rewriting its original brief/evidence. Used to distinguish
        verification-only records from production Clay workspaces (see
        docs/CREATIVE-OS-PHASE-2B.md) — the original brief text, project_id,
        and created_at timestamp are preserved exactly as recorded."""
        value = self.get_project(project_id)
        if value is None:
            raise ValueError("Creative project not found.")
        if name is not None:
            cleaned = str(name).strip()
            if not cleaned:
                raise ValueError("Project name cannot be empty.")
            value["name"] = cleaned[:200]
        if tags is not None:
            value["tags"] = list(dict.fromkeys(str(tag) for tag in tags if str(tag)))
        value = sanitize(value)
        self._execute("UPDATE creative_projects SET name=?, document=? WHERE project_id=?", (value["name"], canonical(value), project_id))
        return value

    def save_generation_request(self, document):
        value = sanitize(document)
        self._execute(
            "INSERT INTO generation_requests VALUES(?,?,?,?,?,?)",
            (value["request_id"], value["project_id"], value["run_id"], value["status"], canonical(value), value["created_at"]),
        )
        return value

    def update_generation_request(self, request_id, **changes):
        current = self.get_generation_request(request_id)
        if current is None:
            raise ValueError("Generation request not found.")
        allowed = {"status", "attempt_status", "error", "approval_id"}
        if set(changes) - allowed:
            raise ValueError("Unsupported generation request update.")
        current.update(sanitize(changes))
        self._execute("UPDATE generation_requests SET status=?, document=? WHERE request_id=?", (current["status"], canonical(current), request_id))
        return current

    def get_generation_request(self, request_id):
        row = self.db.execute("SELECT document FROM generation_requests WHERE request_id=?", (request_id,)).fetchone()
        return json.loads(row["document"]) if row else None

    def list_generation_requests(self, project_id=None):
        if project_id is None:
            rows = self.db.execute("SELECT document FROM generation_requests ORDER BY created_at DESC")
        else:
            rows = self.db.execute("SELECT document FROM generation_requests WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        return [json.loads(row["document"]) for row in rows]

    def create_asset(self, document):
        value = sanitize(document)
        if value.get("parent_asset_id"):
            parent = self.get_asset(value["parent_asset_id"])
            if parent is None or parent["project_id"] != value["project_id"]:
                raise ValueError("Variant parent must belong to the same project.")
        self._execute(
            "INSERT INTO creative_assets VALUES(?,?,?,?,?,?,?,?)",
            (value["asset_id"], value["project_id"], value.get("request_id"), value.get("run_id"), value.get("parent_asset_id"), value["relative_path"], canonical(value), value["created_at"]),
        )
        return value

    def get_asset(self, asset_id):
        row = self.db.execute("SELECT document FROM creative_assets WHERE asset_id=?", (asset_id,)).fetchone()
        return json.loads(row["document"]) if row else None

    def list_assets(self, project_id=None):
        if project_id is None:
            rows = self.db.execute("SELECT document FROM creative_assets ORDER BY created_at DESC")
        else:
            rows = self.db.execute("SELECT document FROM creative_assets WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        return [json.loads(row["document"]) for row in rows]

    def update_asset_metadata(self, asset_id, *, favorite=None, tags=None):
        value = self.get_asset(asset_id)
        if value is None:
            raise ValueError("Creative asset not found.")
        if favorite is not None:
            value["favorite"] = bool(favorite)
        if tags is not None:
            value["tags"] = list(dict.fromkeys(str(tag) for tag in tags if str(tag)))
        self._execute("UPDATE creative_assets SET document=? WHERE asset_id=?", (canonical(sanitize(value)), asset_id))
        return value

    def create_context(self, document):
        value = sanitize(document)
        self._execute(
            "INSERT INTO creative_contexts VALUES(?,?,?,?,?)",
            (value["context_id"], value["project_id"], canonical(value), value["created_at"], value["updated_at"]),
        )
        return value

    def get_context(self, context_id):
        row = self.db.execute("SELECT document FROM creative_contexts WHERE context_id=?", (context_id,)).fetchone()
        return json.loads(row["document"]) if row else None

    def list_contexts(self, project_id=None):
        if project_id is None:
            rows = self.db.execute("SELECT document FROM creative_contexts ORDER BY updated_at DESC")
        else:
            rows = self.db.execute("SELECT document FROM creative_contexts WHERE project_id=? ORDER BY updated_at DESC", (project_id,))
        return [json.loads(row["document"]) for row in rows]

    def update_context(self, context_id, **fields):
        """Apply an explicit operator edit to an existing brand-context
        record. Only fields already defined by the creative-context schema
        may be updated; created_at/context_id/project_id are immutable.
        Missing/unset brand fields are never backfilled with fabricated
        content — callers pass only the fields they have real values for."""
        current = self.get_context(context_id)
        if current is None:
            raise ValueError("Creative context not found.")
        allowed = {
            "name", "brand_name", "brand_description", "positioning", "audience", "voice_and_tone",
            "design_principles", "color_tokens", "typography_references", "image_direction",
            "campaign_context", "product_context", "prohibited_claims", "source_reference_ids", "provenance",
        }
        if set(fields) - allowed:
            raise ValueError("Unsupported creative context update.")
        current.update(sanitize(fields))
        current["updated_at"] = utc_now()
        self._execute("UPDATE creative_contexts SET document=?, updated_at=? WHERE context_id=?", (canonical(current), current["updated_at"], context_id))
        return current

    def raw_update(self, table, record_id, values):
        keys = {"events": "event_id", "results": "result_id", "approvals": "approval_id", "approval_decisions": "decision_id", "artifacts": "artifact_id", "canon_snapshots": "snapshot_id"}
        if table not in keys or not values:
            raise ValueError("Unsupported table")
        if any(not column.isascii() or not column.isidentifier() for column in values):
            raise ValueError("Unsupported column")
        columns = ", ".join(f"{key}=?" for key in values)
        self._execute(f"UPDATE {table} SET {columns} WHERE {keys[table]}=?", [*values.values(), record_id])

    def raw_delete(self, table, record_id):
        keys = {"events": "event_id", "results": "result_id", "approvals": "approval_id", "approval_decisions": "decision_id", "artifacts": "artifact_id", "canon_snapshots": "snapshot_id"}
        if table not in keys:
            raise ValueError("Unsupported table")
        self._execute(f"DELETE FROM {table} WHERE {keys[table]}=?", (record_id,))

    # ── work items (Clay team access ledger) ───────────────────────────────

    def create_work_item(self, work_item_id, requester, requester_slack_id, surface, channel_id, thread_id, requested_outcome, document, status="received"):
        created = utc_now()
        value = sanitize(document)
        self._execute(
            "INSERT INTO work_items VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (work_item_id, requester, requester_slack_id, surface, str(channel_id or ""), str(thread_id or ""), redact(str(requested_outcome)), status, canonical(value), created, created),
        )
        return {"work_item_id": work_item_id, "status": status, "created_at": created, "updated_at": created}

    def append_work_item_event(self, work_item_id, event_type, status, payload, actor="north"):
        payload = sanitize(payload)
        standalone = self._transaction_depth == 0
        if standalone:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT sequence,record_hash FROM work_item_events WHERE work_item_id=? ORDER BY sequence DESC LIMIT 1", (work_item_id,)).fetchone()
            sequence = row["sequence"] + 1 if row else 1
            previous = row["record_hash"] if row else "GENESIS"
            event_id = f"wievent-{uuid.uuid4().hex}"
            recorded = utc_now()
            basis = {"schema_version": SCHEMA_VERSION, "work_item_event_id": event_id, "work_item_id": work_item_id, "sequence": sequence, "event_type": event_type, "status": status, "actor": actor, "recorded_at": recorded, "payload": payload, "previous_hash": previous}
            basis["record_hash"] = hashlib.sha256(canonical(basis).encode()).hexdigest()
            self.db.execute("INSERT INTO work_item_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, work_item_id, sequence, event_type, status, actor, recorded, canonical(payload), previous, basis["record_hash"]))
            if standalone:
                self.db.commit()
            return basis
        except Exception:
            if standalone:
                self.db.rollback()
            raise

    def set_work_item_status(self, work_item_id, status, document=None):
        updated = utc_now()
        if document is None:
            self._execute("UPDATE work_items SET status=?, updated_at=? WHERE work_item_id=?", (status, updated, work_item_id))
        else:
            self._execute("UPDATE work_items SET status=?, document=?, updated_at=? WHERE work_item_id=?", (status, canonical(sanitize(document)), updated, work_item_id))
        return {"work_item_id": work_item_id, "status": status, "updated_at": updated}

    def get_work_item(self, work_item_id):
        row = self.db.execute("SELECT * FROM work_items WHERE work_item_id=?", (work_item_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["document"] = json.loads(item["document"])
        return item

    def find_work_item_by_thread(self, channel_id, thread_id):
        """Return the most recent work item anchored to a Slack thread.

        An empty ``thread_id`` never matches: a top-level message that has not
        started a thread is a new request, not a continuation of an older one.
        """
        thread_id = str(thread_id or "").strip()
        if not thread_id:
            return None
        row = self.db.execute(
            "SELECT work_item_id FROM work_items WHERE channel_id=? AND thread_id=? ORDER BY created_at DESC LIMIT 1",
            (str(channel_id or ""), thread_id),
        ).fetchone()
        return self.get_work_item(row["work_item_id"]) if row else None

    def list_work_items(self, requester=None, status=None):
        sql = "SELECT work_item_id FROM work_items"
        clauses, params = [], []
        if requester is not None:
            clauses.append("requester=?")
            params.append(requester)
        if status is not None:
            clauses.append("status=?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"
        return [self.get_work_item(row["work_item_id"]) for row in self.db.execute(sql, params).fetchall()]

    def list_work_item_events(self, work_item_id):
        rows = self.db.execute("SELECT * FROM work_item_events WHERE work_item_id=? ORDER BY sequence", (work_item_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["schema_version"] = SCHEMA_VERSION
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result
