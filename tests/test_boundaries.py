from __future__ import annotations
import os
from pathlib import Path
import pytest
from clay_ops.artifacts import ArtifactStore, confined_path
from clay_ops.store import OperationalStore
from clay_ops.contracts import ContractError
from clay_ops.canon import CanonRegistry, CanonError


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ContractError) as exc:
        confined_path(tmp_path, "../escape.json")
    assert "PATH_ESCAPE" in exc.value.codes


def test_symlink_escape_rejected(tmp_path):
    outside=tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ContractError) as exc:
        confined_path(tmp_path, "link/file.json")
    assert "SYMLINK_ESCAPE" in exc.value.codes


def test_all_canon_references_are_pinned_readonly_and_resolvable(repo_root):
    registry=CanonRegistry(repo_root)
    snapshots=registry.resolve_all()
    assert snapshots
    assert all(s["git_commit"] and s["blob_hash"] and s["content_sha256"] for s in snapshots)
    assert all(s["access"] == "read-only" for s in snapshots)


def test_unpinned_canon_rejected(repo_root, tmp_path):
    cfg={"schema_version":"1.0.0","repository_root":"../clayhc-clay-engine","references":[{"id":"bad","relative_file_path":"DESIGN.md","git_commit":"","blob_hash":"","content_sha256":"","authority_class":"brand-law","access":"read-only"}]}
    import json
    p=tmp_path / "config"; p.mkdir(); (p/"canon-registry.json").write_text(json.dumps(cfg))
    with pytest.raises(CanonError) as exc:
        CanonRegistry(tmp_path).resolve("bad")
    assert "CANON_UNPINNED" in exc.value.codes


def test_dashboard_cannot_be_canon(repo_root):
    with pytest.raises(CanonError) as exc:
        CanonRegistry(repo_root).resolve("dashboard")
    assert "DASHBOARD_NOT_AUTHORITATIVE" in exc.value.codes


def test_artifact_write_rejects_symlink_swapped_destination(tmp_path, monkeypatch):
    root = tmp_path / 'artifacts'; outside = tmp_path / 'outside'; outside.mkdir()
    store = OperationalStore(tmp_path / 'db.sqlite')
    artifacts = ArtifactStore(root, store)
    (root / 'run').mkdir()
    (root / 'run' / 'target.txt').symlink_to(outside / 'escaped.txt')
    with pytest.raises(FileExistsError):
        artifacts.write_text('run', 'run/target.txt', 'secret')
    assert not (outside / 'escaped.txt').exists()


def test_artifact_file_is_compensated_when_database_record_fails(tmp_path):
    class FailingStore:
        def record_artifact(self, *args):
            raise RuntimeError('database unavailable')
    root = tmp_path / 'artifacts'
    artifacts = ArtifactStore(root, FailingStore())
    with pytest.raises(RuntimeError):
        artifacts.write_text('run', 'run/result.txt', 'local')
    assert not (root / 'run' / 'result.txt').exists()
