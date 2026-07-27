import pytest

from clay_ops import cli
from clay_ops.cli import build_parser
from clay_ops.store import OperationalStore


def test_serve_defaults_to_loopback_projection_port():
    args = build_parser().parse_args(["serve"])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8765


def test_cli_approval_resolution_appends_atomic_resume_timeline(tmp_path, monkeypatch):
    store = OperationalStore(tmp_path / "ops.db")
    store.save_task({"task_id": "task-1", "brief": "Review copy"})
    store.create_run("run-1", "task-1", "copy-review", "manual/unstructured")
    store.create_approval(
        "approval-1",
        "run-1",
        "review_acceptance",
        {"run_id": "run-1", "result_id": "result-1"},
        "Review only",
    )
    monkeypatch.setattr(cli, "_store", lambda: store)

    assert cli.main(["approval", "resolve", "approval-1", "--approve"]) == 0

    assert [event["event_type"] for event in store.list_events("run-1")] == [
        "approval.resolved",
        "run.resumed",
    ]


def test_cli_approval_resolution_rolls_back_if_resume_event_fails(tmp_path, monkeypatch):
    store = OperationalStore(tmp_path / "ops.db")
    store.save_task({"task_id": "task-1", "brief": "Review copy"})
    store.create_run("run-1", "task-1", "copy-review", "manual/unstructured")
    store.create_approval(
        "approval-1",
        "run-1",
        "review_acceptance",
        {"run_id": "run-1", "result_id": "result-1"},
        "Review only",
    )
    original_append = store.append_event

    def fail_resume(*args, **kwargs):
        if args[1] == "run.resumed":
            raise RuntimeError("forced resume failure")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(store, "append_event", fail_resume)
    monkeypatch.setattr(cli, "_store", lambda: store)

    with pytest.raises(RuntimeError, match="forced resume failure"):
        cli.main(["approval", "resolve", "approval-1", "--approve"])

    assert store.get_approval("approval-1")["status"] == "pending"
    assert store.list_approval_decisions("approval-1") == []
    assert store.list_events("run-1") == []
