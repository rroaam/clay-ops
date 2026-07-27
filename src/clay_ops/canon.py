from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from typing import Any, Iterable
from .contracts import ContractError, validate_document

class CanonError(ContractError): pass

def _run_git(repo: Path,*args: str, binary: bool=False):
    p=subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=not binary,check=False)
    if p.returncode: raise CanonError([{"code":"CANON_UNRESOLVABLE","message":"Pinned Git object cannot be resolved."}])
    return p.stdout

class CanonRegistry:
    def __init__(self,ops_root: Path):
        self.ops_root=Path(ops_root).expanduser().resolve()
        path=self.ops_root/"config/canon-registry.json"
        try: self.config=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError) as exc: raise CanonError([{"code":"CANON_REGISTRY_INVALID","message":str(exc)}]) from None
        self.refs={r.get("id"):r for r in self.config.get("references",[])}
    def resolve_all(self): return [self.resolve(i) for i in self.refs]
    def resolve_many(self,ids: Iterable[str]): return [self.resolve(i) for i in ids]
    def resolve(self,reference_id: str) -> dict[str,Any]:
        if reference_id=="dashboard" or "dashboard" in reference_id.lower(): raise CanonError([{"code":"DASHBOARD_NOT_AUTHORITATIVE","message":"Dashboard cannot be canon."}])
        ref=self.refs.get(reference_id)
        if not ref: raise CanonError([{"code":"CANON_REFERENCE_MISSING","message":f"Unknown canon reference: {reference_id}"}])
        try: validate_document("canon-reference",ref,self.ops_root/"schemas")
        except ContractError as exc:
            code="CANON_UNPINNED" if any(not ref.get(k) for k in ("git_commit","blob_hash","content_sha256")) else "CANON_REFERENCE_INVALID"
            raise CanonError([{"code":code,"message":str(exc)}]) from None
        if ref.get("access")!="read-only": raise CanonError([{"code":"CANON_WRITABLE_REFERENCE","message":"Canon reference must be declared read-only."}])
        repo=(self.ops_root/ref["repository_path"]).resolve()
        if "dashboard" in repo.name.lower(): raise CanonError([{"code":"DASHBOARD_NOT_AUTHORITATIVE","message":"Dashboard cannot be canon."}])
        if not repo.is_dir(): raise CanonError([{"code":"CANON_UNRESOLVABLE","message":"Canonical repository is unavailable."}])
        rel=Path(ref["relative_file_path"])
        working=(repo/rel).resolve()
        if repo not in working.parents or not working.is_file() or working.is_symlink(): raise CanonError([{"code":"CANON_UNRESOLVABLE","message":"Canonical file is missing or escapes its repository."}])
        commit=ref["git_commit"]
        blob=_run_git(repo,"rev-parse",f"{commit}:{rel.as_posix()}").strip()
        if blob!=ref["blob_hash"]: raise CanonError([{"code":"CANON_PIN_MISMATCH","message":"Pinned Git blob does not match."}])
        data=_run_git(repo,"show",f"{commit}:{rel.as_posix()}",binary=True)
        digest=hashlib.sha256(data).hexdigest()
        if digest!=ref["content_sha256"]: raise CanonError([{"code":"CANON_PIN_MISMATCH","message":"Pinned content hash does not match."}])
        return {**ref,"repository_path":str(repo),"resolved_file_path":str(working)}
