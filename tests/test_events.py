from __future__ import annotations
import pytest
from clay_ops.store import OperationalStore, ImmutableRecordError


def test_events_append_only_and_projection_reconstructable(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite")
    s.append_event("run-1","run.created","queued",{"n":1})
    s.append_event("run-1","run.started","running",{"n":2})
    s.append_event("run-1","run.awaiting_approval","awaiting_approval",{"n":3})
    assert s.project_run("run-1")["status"] == "awaiting_approval"
    assert [e["sequence"] for e in s.list_events("run-1")] == [1,2,3]


def test_event_mutation_rejected(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite"); e=s.append_event("run-1","run.created","queued",{})
    with pytest.raises(ImmutableRecordError): s.raw_update("events",e["event_id"],{"status":"forged"})


def test_raw_update_rejects_non_identifier_columns(tmp_path):
    s = OperationalStore(tmp_path / "db.sqlite")
    event = s.append_event("run-1", "run.created", "queued", {})
    with pytest.raises(ValueError, match="Unsupported column"):
        s.raw_update("events", event["event_id"], {"status = ?; DELETE FROM events; --": "forged"})


def test_completed_result_immutable(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite")
    s.save_result("result-1","run-1","task-1",{"status":"awaiting_approval"},completed=True)
    with pytest.raises(ImmutableRecordError): s.raw_update("results","result-1",{"payload":"{}"})
    with pytest.raises(ImmutableRecordError): s.raw_delete("results","result-1")


def test_event_delete_rejected(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite")
    event=s.append_event("run-1","run.created","queued",{})
    with pytest.raises(ImmutableRecordError): s.raw_delete("events",event["event_id"])


def test_artifact_sha256_recorded(tmp_path):
    from clay_ops.artifacts import ArtifactStore
    s=OperationalStore(tmp_path/"db.sqlite")
    record=ArtifactStore(tmp_path/"artifacts",s).write_json("run-1","evidence/a.json",{"ok":True})
    assert len(record["sha256"])==64
