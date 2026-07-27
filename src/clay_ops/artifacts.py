from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from .contracts import ContractError


def _safe_unlink(root: Path, relative: Path) -> None:
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        os.unlink(relative.parts[-1], dir_fd=directory_fd)
    except FileNotFoundError:
        pass
    finally:
        os.close(directory_fd)


def confined_path(root: Path, relative: str | Path) -> Path:
    root = Path(root).expanduser().resolve()
    raw = Path(relative)
    if raw.is_absolute() or ".." in raw.parts:
        raise ContractError([{"code": "PATH_ESCAPE", "message": "Artifact path must be relative and confined."}])
    cursor = root
    for part in raw.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise ContractError([{"code": "SYMLINK_ESCAPE", "message": "Symlink traversal is forbidden."}])
    resolved = (root / raw).resolve()
    if resolved != root and root not in resolved.parents:
        raise ContractError([{"code": "PATH_ESCAPE", "message": "Artifact path escapes root."}])
    return resolved


class ArtifactStore:
    def __init__(self, root, store):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = store

    def write_bytes(self, run_id, relative, data: bytes, kind: str):
        raw = Path(relative)
        if raw.is_absolute() or not raw.parts or ".." in raw.parts or any(part in {"", "."} for part in raw.parts):
            raise ContractError([{"code": "PATH_ESCAPE", "message": "Artifact path must be relative and confined."}])
        directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        temp_name = f".clay-{uuid.uuid4().hex}.tmp"
        final_name = raw.parts[-1]
        created = False
        try:
            for part in raw.parts[:-1]:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=directory_fd)
                except FileExistsError:
                    pass
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            file_fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
            try:
                view = memoryview(data)
                while view:
                    written = os.write(file_fd, view)
                    view = view[written:]
                os.fsync(file_fd)
            finally:
                os.close(file_fd)
            try:
                os.link(temp_name, final_name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd, follow_symlinks=False)
                created = True
            except FileExistsError:
                raise FileExistsError(self.root / raw) from None
            finally:
                os.unlink(temp_name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        digest = hashlib.sha256(data).hexdigest()
        artifact_id = f"artifact-{uuid.uuid4().hex}"
        try:
            record = self.store.record_artifact(artifact_id, run_id, raw.as_posix(), digest, kind)
        except Exception:
            if created:
                _safe_unlink(self.root, raw)
            raise
        record["ref"] = f"artifact://{run_id}/{Path(relative).as_posix()}"
        return record

    def write_text(self, run_id, relative, value: str, kind="text"):
        return self.write_bytes(run_id, relative, value.encode("utf-8"), kind)

    def write_json(self, run_id, relative, value):
        data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
        return self.write_bytes(run_id, relative, data, "json")
