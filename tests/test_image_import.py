from __future__ import annotations

import base64
import struct
import zlib

import pytest

from clay_ops.contracts import ContractError
from clay_ops.image_import import LocalImageImporter
from clay_ops.store import OperationalStore, utc_now


def png(width=2, height=3):
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    return signature + chunk


def make_importer(tmp_path, max_bytes=1024):
    root = tmp_path / "ops"
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    store.create_project({"schema_version": "1.0.0", "project_id": "project-one", "name": "One", "brief": "", "tags": [], "created_at": utc_now()})
    return LocalImageImporter(root / "runtime" / "artifacts", store, max_bytes=max_bytes), store


def test_import_uses_request_bytes_and_records_verified_metadata(tmp_path):
    importer, store = make_importer(tmp_path)
    asset = importer.import_bytes(project_id="project-one", data=png(), mime_type="image/png", name="Hero image.png", tags=["hero"])

    assert asset["width"] == 2 and asset["height"] == 3
    assert asset["name"] == "Hero-image.png"
    assert asset["provenance"] == {"kind": "imported", "source": "request_bytes"}
    assert asset["evidence"]["signature_verified"] is True
    assert (tmp_path / "ops" / "runtime" / "artifacts" / asset["relative_path"]).read_bytes() == png()
    assert store.project_run(asset["run_id"])["status"] == "completed"


def test_allowlisted_signatures_and_stdlib_dimensions(tmp_path):
    cases = [
        ("image/gif", "x.gif", b"GIF89a" + struct.pack("<HH", 2, 3) + b"\x00" * 8, (2, 3)),
        ("image/jpeg", "x.jpg", b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x03\x00\x02\x03\x01\x11\x00", (2, 3)),
        ("image/webp", "x.webp", b"RIFF" + (22).to_bytes(4, "little") + b"WEBPVP8X" + (10).to_bytes(4, "little") + b"\x00\x00\x00\x00" + (1).to_bytes(3, "little") + (2).to_bytes(3, "little"), (2, 3)),
    ]
    importer, _ = make_importer(tmp_path)
    for mime_type, name, data, dimensions in cases:
        asset = importer.import_bytes(project_id="project-one", data=data, mime_type=mime_type, name=name)
        assert (asset["width"], asset["height"]) == dimensions


def test_import_rejects_paths_bad_mime_signature_and_oversize(tmp_path):
    importer, _ = make_importer(tmp_path, max_bytes=64)
    with pytest.raises(ContractError, match="name"):
        importer.import_bytes(project_id="project-one", data=png(), mime_type="image/png", name="../../escape.png")
    with pytest.raises(ContractError, match="MIME"):
        importer.import_bytes(project_id="project-one", data=png(), mime_type="image/svg+xml", name="x.svg")
    with pytest.raises(ContractError, match="signature"):
        importer.import_bytes(project_id="project-one", data=b"not png", mime_type="image/png", name="x.png")
    with pytest.raises(ContractError, match="size"):
        importer.import_bytes(project_id="project-one", data=png() + b"x" * 100, mime_type="image/png", name="x.png")


def test_import_rejects_unknown_project_and_client_paths_are_not_an_input(tmp_path):
    importer, _ = make_importer(tmp_path)
    with pytest.raises(ValueError, match="Project"):
        importer.import_bytes(project_id="project-missing", data=png(), mime_type="image/png", name="x.png")
    with pytest.raises(TypeError):
        importer.import_bytes(project_id="project-one", client_path="/tmp/private.png", mime_type="image/png", name="x.png")
