from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterable
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_VERSION = "1.0.0"

class ContractError(ValueError):
    def __init__(self, issues: Iterable[dict[str,str]]):
        self.issues=list(issues); self.codes=[i["code"] for i in self.issues]
        super().__init__("; ".join(f"{i['code']}: {i['message']}" for i in self.issues))

def _issue(code: str, message: str) -> dict[str,str]: return {"code":code,"message":message}

def validate_document(kind: str, document: dict[str,Any], schema_dir: Path) -> None:
    issues=[]
    if kind != "canon-reference" and document.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("SCHEMA_VERSION_MISMATCH",f"Expected {SCHEMA_VERSION}."))
    if kind=="task-packet":
        if not document.get("acceptance_criteria"): issues.append(_issue("MISSING_ACCEPTANCE_CRITERIA","At least one acceptance criterion is required."))
        if not document.get("input",{}).get("source_provenance"): issues.append(_issue("MISSING_INPUT_PROVENANCE","Input provenance is required."))
        if "dashboard" in str(document.get("source_of_truth","")).lower(): issues.append(_issue("DASHBOARD_NOT_AUTHORITATIVE","Dashboard is never source of truth."))
        if document.get("assigned_agent") != "clay-copy-reviewer": issues.append(_issue("UNKNOWN_AGENT","Task agent is not registered."))
        allowed={"canon-read","local-validator","ops-store-write"}
        if any(tool not in allowed for tool in document.get("allowed_tools",[])): issues.append(_issue("UNKNOWN_TOOL","Task contains an unregistered tool."))
        actions={str(action).lower() for action in document.get("requested_actions",[])}
        if "publish" in actions: issues.append(_issue("PUBLISH_FORBIDDEN","Publishing is outside Clay Ops Phase 1."))
        if actions & {"deploy","deployment"}: issues.append(_issue("DEPLOYMENT_FORBIDDEN","Deployment is outside Clay Ops Phase 1."))
        if actions & {"credential_access","credentials","secret_access"}: issues.append(_issue("CREDENTIAL_ACCESS_FORBIDDEN","Credential access is forbidden."))
        if actions & {"canon_mutation","canon_write"}: issues.append(_issue("CANON_MUTATION_FORBIDDEN","Canon mutation is forbidden."))
        if any(not str(path).startswith("runtime") or ".." in str(path).split("/") for path in document.get("write_scope",[])): issues.append(_issue("WRITE_SCOPE_OUTSIDE_RUNTIME","Writes must remain under runtime/."))
    if kind=="result-packet":
        if not document.get("task_id"): issues.append(_issue("RESULT_TASK_ID_REQUIRED","Result must link to a task."))
        if not document.get("evidence"): issues.append(_issue("MISSING_EVIDENCE","Result must include immutable evidence."))
        if document.get("status") in {"pass","awaiting_approval"} and (not document.get("evidence") or not document.get("gate_results")):
            issues.append(_issue("FALSE_COMPLETION_WITHOUT_EVIDENCE","A terminal review outcome requires gate and artifact evidence."))
        if "dashboard" in json.dumps(document.get("outputs",{}),sort_keys=True).lower(): issues.append(_issue("DASHBOARD_NOT_AUTHORITATIVE","Result cannot elevate dashboard authority."))
        if document.get("canon_mutations"): issues.append(_issue("CANON_MUTATION_FORBIDDEN","Result may not mutate canon."))
        if document.get("external_side_effects"): issues.append(_issue("EXTERNAL_SIDE_EFFECT_FORBIDDEN","Result may not report external side effects."))
    schema_path=Path(schema_dir)/f"{kind}.schema.json"
    try: schema=json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise ContractError([_issue("SCHEMA_UNAVAILABLE",str(exc))]) from None
    Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema,format_checker=FormatChecker())
    for err in sorted(validator.iter_errors(document),key=lambda e:list(e.absolute_path)):
        loc="$."+".".join(str(p) for p in err.absolute_path) if err.absolute_path else "$"
        issues.append(_issue("SCHEMA_INVALID",f"{loc}: {err.message}"))
    if issues: raise ContractError(issues)
