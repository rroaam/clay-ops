from __future__ import annotations
import json
from pathlib import Path
from .contracts import ContractError
class ApprovalError(ContractError): pass
class ApprovalPolicy:
    def __init__(self,path: Path):
        self.document=json.loads(Path(path).read_text(encoding="utf-8")); self.rules={r["action"]:r for r in self.document["rules"]}
    def rule(self,action: str):
        if action not in self.rules: raise ApprovalError([{"code":"ACTION_DEFAULT_DENY","message":f"Unknown action: {action}"}])
        return self.rules[action]
    def require_allowed(self,action: str):
        r=self.rule(action)
        if r["disposition"]=="forbid": raise ApprovalError([{"code":"ACTION_FORBIDDEN","message":f"Action forbidden: {action}"}])
        return r
