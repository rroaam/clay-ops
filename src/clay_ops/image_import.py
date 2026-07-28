from __future__ import annotations

import hashlib
import re
import struct
import uuid
from pathlib import Path

from .artifacts import ArtifactStore
from .contracts import ContractError
from .store import OperationalStore, utc_now


ALLOWED_MIME = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/webp": ("webp", b"RIFF"),
    "image/gif": ("gif", b"GIF8"),
}


def _issue(code: str, message: str) -> ContractError:
    return ContractError([{"code": code, "message": message}])


def _dimensions(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png" and len(data) >= 24 and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if mime_type == "image/gif" and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if mime_type == "image/webp" and len(data) >= 30 and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X":
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if kind == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        if kind == b"VP8L" and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if mime_type == "image/jpeg":
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            length = int.from_bytes(data[offset:offset + 2], "big")
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and offset + 7 <= len(data):
                return int.from_bytes(data[offset + 5:offset + 7], "big"), int.from_bytes(data[offset + 3:offset + 5], "big")
            if length < 2:
                break
            offset += length
    return None, None


def _safe_name(name: str, extension: str) -> str:
    if not name or Path(name).name != name or ".." in name or "/" in name or "\\" in name:
        raise _issue("UNSAFE_NAME", "Image name must not contain a path.")
    stem = Path(name).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_")[:100]
    if not cleaned:
        cleaned = "image"
    return f"{cleaned}.{extension}"


class LocalImageImporter:
    def __init__(self, artifact_root: Path, store: OperationalStore, *, max_bytes: int = 10 * 1024 * 1024):
        if max_bytes <= 0:
            raise ValueError("Image size cap must be positive.")
        self.artifacts = ArtifactStore(artifact_root, store)
        self.store = store
        self.max_bytes = max_bytes

    def import_generated(self, *, project_id: str, request_id: str, run_id: str, data: bytes, mime_type: str,
                         name: str, variant_index: int, evidence: dict, parent_asset_id: str | None = None) -> dict:
        if mime_type not in ALLOWED_MIME:
            raise _issue("MIME_NOT_ALLOWED", "MIME type is not allowed.")
        if not isinstance(data, bytes) or not data or len(data) > self.max_bytes:
            raise _issue("INVALID_PROVIDER_IMAGE", "Provider image bytes are invalid or exceed the size cap.")
        extension, signature = ALLOWED_MIME[mime_type]
        if not data.startswith(signature) or (mime_type == "image/webp" and (len(data) < 12 or data[8:12] != b"WEBP")):
            raise _issue("SIGNATURE_MISMATCH", "Provider image signature does not match declared MIME type.")
        safe_name = _safe_name(name, extension)
        asset_id = f"asset-{uuid.uuid4().hex}"
        relative = f"{run_id}/images/{asset_id}-{safe_name}"
        width, height = _dimensions(data, mime_type)
        artifact = self.artifacts.write_bytes(run_id, relative, data, mime_type)
        asset = {
            "schema_version": "1.0.0", "asset_id": asset_id, "project_id": project_id, "request_id": request_id,
            "run_id": run_id, "parent_asset_id": parent_asset_id, "variant_index": variant_index, "name": safe_name,
            "mime_type": mime_type, "relative_path": relative, "sha256": hashlib.sha256(data).hexdigest(),
            "byte_size": len(data), "width": width, "height": height, "favorite": False, "tags": [],
            "provenance": {"kind": "generated", "source": "approved_provider", "request_id": request_id},
            "evidence": {"signature_verified": True, "artifact_id": artifact["artifact_id"], **dict(evidence)},
            "status": "available", "created_at": utc_now(),
        }
        self.store.create_asset(asset)
        return asset

    def import_bytes(self, *, project_id: str, data: bytes, mime_type: str, name: str, tags=(), parent_asset_id: str | None = None) -> dict:
        if self.store.get_project(project_id) is None:
            raise ValueError("Project not found.")
        if mime_type not in ALLOWED_MIME:
            raise _issue("MIME_NOT_ALLOWED", "MIME type is not allowed.")
        if not isinstance(data, bytes):
            raise _issue("BYTES_REQUIRED", "Image must be supplied as request bytes.")
        if len(data) > self.max_bytes:
            raise _issue("IMAGE_TOO_LARGE", "Image exceeds the configured size cap.")
        if not data:
            raise _issue("EMPTY_IMAGE", "Image bytes are required.")
        extension, signature = ALLOWED_MIME[mime_type]
        signature_ok = data.startswith(signature) and (mime_type != "image/webp" or len(data) >= 12 and data[8:12] == b"WEBP")
        if not signature_ok:
            raise _issue("SIGNATURE_MISMATCH", "Image signature does not match declared MIME type.")
        safe_name = _safe_name(name, extension)
        suffix = uuid.uuid4().hex
        run_id, task_id, asset_id = f"run-{suffix}", f"task-{suffix}", f"asset-{suffix}"
        relative = f"{run_id}/images/{asset_id}-{safe_name}"
        now = utc_now()
        width, height = _dimensions(data, mime_type)
        self.store.save_task({"task_id": task_id, "workflow_id": "local-image-import", "brief": "Local image import"})
        self.store.create_run(run_id, task_id, "local-image-import")
        self.store.append_event(run_id, "run.created", "running", {"project_id": project_id, "source": "request_bytes"})
        artifact = self.artifacts.write_bytes(run_id, relative, data, mime_type)
        asset = {
            "schema_version": "1.0.0", "asset_id": asset_id, "project_id": project_id, "request_id": None,
            "run_id": run_id, "parent_asset_id": parent_asset_id, "variant_index": None, "name": safe_name,
            "mime_type": mime_type, "relative_path": relative, "sha256": hashlib.sha256(data).hexdigest(),
            "byte_size": len(data), "width": width, "height": height, "favorite": False,
            "tags": list(dict.fromkeys(str(tag) for tag in tags if str(tag))),
            "provenance": {"kind": "imported", "source": "request_bytes"},
            "evidence": {"signature_verified": True, "artifact_id": artifact["artifact_id"]},
            "status": "available", "created_at": now,
        }
        self.store.create_asset(asset)
        self.store.append_event(run_id, "image.imported", "completed", {"project_id": project_id, "asset_id": asset_id, "artifact_id": artifact["artifact_id"]})
        return asset
