from __future__ import annotations

import base64
import binascii
import ipaddress
import json
import mimetypes
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .artifacts import confined_path
from .demo import DemoOrchestrator
from .image_import import LocalImageImporter
from .images import ImageProviderRegistry
from .projection import ProjectionService
from .redaction import redact
from .store import OperationalStore, utc_now
from .workflows.image_generation import ImageGenerationWorkflow


MAX_BODY_BYTES = 16 * 1024 * 1024
SERVER_MARKER_HEADER = "X-Clay-HQ-Server"


def _loopback_authority(value: str) -> bool:
    try:
        parsed = urlsplit(f"//{value}")
        host = parsed.hostname
        _ = parsed.port
        if parsed.username is not None or parsed.password is not None or not host:
            return False
        if host.lower() == "localhost":
            return True
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def _loopback_origin(value: str) -> bool:
    return value == "http://127.0.0.1:3001"


def _handler(root: Path, store: OperationalStore, hermes=None, image_registry=None, image_max_bytes=10 * 1024 * 1024):
    database_path = store.path
    image_registry = image_registry or ImageProviderRegistry()
    artifact_root = (root / "runtime" / "artifacts").resolve()

    class ClayOpsHandler(BaseHTTPRequestHandler):
        server_version = "ClayOpsLoopback/1.0"

        def log_message(self, format, *args):
            # Never log request bodies, authorization values, or query strings.
            return

        def _json(self, status: int, value: dict):
            data = (json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            # Deliberately no Access-Control-Allow-Origin header.
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError("Request body must be non-empty and within the configured API limit.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required.")
            return payload

        def _validate_command_request(self) -> bool:
            if not _loopback_authority(self.headers.get("Host", "")):
                self._json(HTTPStatus.FORBIDDEN, {"status": "error", "message": "Loopback Host required."})
                return False
            if self.headers.get(SERVER_MARKER_HEADER) != "1":
                self._json(HTTPStatus.FORBIDDEN, {"status": "error", "message": f"{SERVER_MARKER_HEADER}: 1 required."})
                return False
            if not _loopback_origin(self.headers.get("Origin", "")):
                self._json(HTTPStatus.FORBIDDEN, {"status": "error", "message": "Loopback Origin required."})
                return False
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"status": "error", "message": "Content-Type application/json required."})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                if not _loopback_authority(self.headers.get("Host", "")):
                    self._json(HTTPStatus.FORBIDDEN, {"status": "error", "message": "Loopback Host required."})
                    return
                if path == "/health":
                    self._json(HTTPStatus.OK, {"status": "ok", "bind_policy": "loopback-only", "cors": "disabled"})
                    return
                if path == "/api/projection":
                    local_store = OperationalStore(database_path)
                    try:
                        self._json(HTTPStatus.OK, ProjectionService(root, local_store, image_registry).snapshot())
                    finally:
                        local_store.db.close()
                    return
                if path == "/api/projects" or path == "/api/generation-requests" or path.startswith("/api/projects/") or path.startswith("/api/generation-requests/"):
                    local_store = OperationalStore(database_path)
                    try:
                        snapshot = ProjectionService(root, local_store, image_registry).snapshot()
                        if path == "/api/projects":
                            value = {"projects": snapshot["projects"]}
                        elif path == "/api/generation-requests":
                            value = {"generation_requests": snapshot["generation_requests"]}
                        elif path.startswith("/api/projects/") and path.endswith("/assets"):
                            project_id = unquote(path.removeprefix("/api/projects/").removesuffix("/assets").rstrip("/"))
                            value = {"assets": [item for item in snapshot["assets"] if item["project_id"] == project_id]}
                        elif path.startswith("/api/projects/"):
                            project_id = unquote(path.removeprefix("/api/projects/"))
                            item = next((item for item in snapshot["projects"] if item["project_id"] == project_id), None)
                            if item is None:
                                self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "Project not found."}); return
                            value = item
                        else:
                            request_id = unquote(path.removeprefix("/api/generation-requests/"))
                            item = next((item for item in snapshot["generation_requests"] if item["request_id"] == request_id), None)
                            if item is None:
                                self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "Generation request not found."}); return
                            value = item
                        self._json(HTTPStatus.OK, value)
                    finally:
                        local_store.db.close()
                    return
                if path.startswith("/api/artifacts/"):
                    relative = unquote(path.removeprefix("/api/artifacts/"))
                    artifact = confined_path(artifact_root, relative)
                    if not artifact.is_file():
                        self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "Artifact not found."})
                        return
                    data = artifact.read_bytes()
                    content_type = mimetypes.guess_type(artifact.name)[0] or "application/octet-stream"
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "Not found."})
            except Exception as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": redact(str(exc))})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                if not self._validate_command_request():
                    return
                body = self._body()
                if path == "/api/projects":
                    name = str(body.get("name", "")).strip()
                    if not name:
                        raise ValueError("Project name is required.")
                    project = {"schema_version": "1.0.0", "project_id": f"project-{uuid.uuid4().hex}", "name": name[:200], "brief": str(body.get("brief", ""))[:10000], "tags": list(body.get("tags", [])), "created_at": utc_now()}
                    local_store = OperationalStore(database_path)
                    try:
                        local_store.create_project(project)
                    finally:
                        local_store.db.close()
                    self._json(HTTPStatus.CREATED, project)
                    return
                if path == "/api/generation-requests":
                    local_store = OperationalStore(database_path)
                    try:
                        result = ImageGenerationWorkflow(root, local_store, registry=image_registry).submit(
                            project_name=str(body.get("project_name", "")), brief=str(body.get("brief", "")), prompt=str(body.get("prompt", "")),
                            references=list(body.get("references", [])), style=body.get("style"), aspect_ratio=body.get("aspect_ratio"),
                            variant_count=int(body.get("variant_count", 1)), provider=str(body.get("provider", "unavailable")), model=body.get("model"),
                        )
                    finally:
                        local_store.db.close()
                    self._json(HTTPStatus.CREATED, result)
                    return
                if path == "/api/imports/images":
                    try:
                        data = base64.b64decode(str(body.get("data_base64", "")), validate=True)
                    except (binascii.Error, ValueError):
                        raise ValueError("Valid base64 image bytes are required.") from None
                    local_store = OperationalStore(database_path)
                    try:
                        result = LocalImageImporter(artifact_root, local_store, max_bytes=image_max_bytes).import_bytes(
                            project_id=str(body.get("project_id", "")), data=data, mime_type=str(body.get("mime_type", "")),
                            name=str(body.get("name", "")), tags=list(body.get("tags", [])), parent_asset_id=body.get("parent_asset_id"),
                        )
                    finally:
                        local_store.db.close()
                    self._json(HTTPStatus.CREATED, result)
                    return
                if path.startswith("/api/assets/") and path.endswith("/metadata"):
                    asset_id = unquote(path.removeprefix("/api/assets/").removesuffix("/metadata").rstrip("/"))
                    local_store = OperationalStore(database_path)
                    try:
                        result = local_store.update_asset_metadata(asset_id, favorite=body.get("favorite"), tags=body.get("tags"))
                    finally:
                        local_store.db.close()
                    self._json(HTTPStatus.OK, result)
                    return
                if path == "/api/runs":
                    local_store = OperationalStore(database_path)
                    try:
                        result = DemoOrchestrator(root, local_store, root / "runtime" / "artifacts", hermes=hermes).run(str(body.get("brief", "")))
                    finally:
                        local_store.db.close()
                    self._json(HTTPStatus.CREATED, result)
                    return
                if path.startswith("/api/approvals/"):
                    approval_id = unquote(path.removeprefix("/api/approvals/"))
                    local_store = OperationalStore(database_path)
                    try:
                        result = DemoOrchestrator(root, local_store, root / "runtime" / "artifacts", hermes=hermes).resolve(
                            approval_id,
                            str(body.get("decision", "")),
                            actor=str(body.get("actor", "Ryan"))[:80] or "Ryan",
                            reason=str(body.get("reason", ""))[:2000],
                        )
                    finally:
                        local_store.db.close()
                    self._json(HTTPStatus.OK, result)
                    return
                self._json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "Not found."})
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "message": redact(str(exc))})
            except Exception as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"status": "error", "message": redact(str(exc))})

    return ClayOpsHandler


def create_server(address, *, root: Path, store: OperationalStore, hermes=None, image_registry=None, image_max_bytes=10 * 1024 * 1024):
    host, _port = address
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Clay Ops API may bind only to loopback.")
    return ThreadingHTTPServer(address, _handler(Path(root).resolve(), store, hermes, image_registry, image_max_bytes))
