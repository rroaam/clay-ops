from __future__ import annotations
import pytest
from clay_ops.store import OperationalStore, ImmutableRecordError
from clay_ops.policy import ApprovalError
import threading


def pending(store):
    return store.create_approval("approval-1","run-1","review_acceptance",{"run_id":"run-1","result_id":"result-1"},"Accept review only")


def test_approval_decisions_append_only(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite"); pending(s)
    s.resolve_approval("approval-1",True,"Ryan",{"run_id":"run-1","result_id":"result-1"})
    rows=s.list_approval_decisions("approval-1")
    assert len(rows)==1 and rows[0]["decision"]=="approved"
    with pytest.raises(ImmutableRecordError): s.raw_delete("approval_decisions",rows[0]["decision_id"])


def test_approval_scope_mismatch_rejected(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite"); pending(s)
    with pytest.raises(ApprovalError) as exc:
        s.resolve_approval("approval-1",True,"Ryan",{"run_id":"other","result_id":"result-1"})
    assert "APPROVAL_SCOPE_MISMATCH" in exc.value.codes


def test_approval_replay_rejected(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite"); pending(s)
    scope={"run_id":"run-1","result_id":"result-1"}; s.resolve_approval("approval-1",True,"Ryan",scope)
    with pytest.raises(ApprovalError) as exc: s.resolve_approval("approval-1",True,"Ryan",scope)
    assert "APPROVAL_REPLAY" in exc.value.codes


def test_approval_never_converts_missing_clinical_authority(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite"); pending(s)
    s.resolve_approval("approval-1",True,"Ryan",{"run_id":"run-1","result_id":"result-1"})
    assert s.get_approval("approval-1")["action"] == "review_acceptance"


def test_approval_request_is_immutable(tmp_path):
    s=OperationalStore(tmp_path/"db.sqlite"); pending(s)
    with pytest.raises(ImmutableRecordError):
        s.raw_update('approvals', 'approval-1', {'reason': 'rewritten'})
    with pytest.raises(ImmutableRecordError):
        s.raw_delete('approvals', 'approval-1')


def test_concurrent_approval_resolution_records_exactly_one_decision(tmp_path):
    path = tmp_path / 'db.sqlite'
    setup = OperationalStore(path); pending(setup); setup.db.close()
    scope={"run_id":"run-1","result_id":"result-1"}
    barrier = threading.Barrier(2)
    outcomes=[]
    def resolve():
        store = OperationalStore(path)
        barrier.wait()
        try:
            store.resolve_approval('approval-1', True, 'Ryan', scope)
            outcomes.append('ok')
        except ApprovalError as exc:
            outcomes.append(exc.codes[0])
        finally:
            store.db.close()
    threads=[threading.Thread(target=resolve) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    verify=OperationalStore(path)
    assert sorted(outcomes) == ['APPROVAL_REPLAY', 'ok']
    assert len(verify.list_approval_decisions('approval-1')) == 1
