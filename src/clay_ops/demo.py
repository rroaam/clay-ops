from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from .adapters.hermes_api import CapabilityMismatch, HermesOffline
from .artifacts import ArtifactStore
from .canon import CanonRegistry
from .store import OperationalStore, utc_now


TERMINAL_HERMES_STATES = {"completed", "failed", "stopped", "cancelled", "error"}


class NonterminalHermesRun(RuntimeError):
    pass


def _extract_output(run: dict) -> str:
    for key in ("output", "output_text", "response", "result"):
        value = run.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in ("output", "output_text", "response", "content"):
                text = value.get(nested)
                if isinstance(text, str) and text.strip():
                    return text.strip()
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return ""


def _campaign_payload(output: str) -> dict:
    try:
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            return {"source": "hermes-structured-run", **parsed}
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "source": "hermes-structured-run" if output else "local-fallback",
        "campaign_direction": "Move with clarity",
        "copy_options": ["Built for the work between milestones."],
        "hermes_output": output[:4000] if output else "Hermes produced no parseable copy output.",
    }


def _feature_enabled(capabilities: dict, name: str) -> bool:
    features = capabilities.get("features", {}) if isinstance(capabilities, dict) else {}
    return features.get(name) is True if isinstance(features, dict) else name in features


class DemoOrchestrator:
    """Create a truthful local EOD demo run without external release actions."""

    def __init__(self, root: Path, store: OperationalStore, artifact_root: Path, *, hermes=None):
        self.root = Path(root).resolve()
        self.store = store
        self.artifacts = ArtifactStore(artifact_root, store)
        self.hermes = hermes

    def run(self, brief: str, *, timeout_seconds: int = 180) -> dict:
        with self.store.transaction():
            return self._run(brief, timeout_seconds=timeout_seconds)

    def _run(self, brief: str, *, timeout_seconds: int = 180) -> dict:
        brief = (brief or "").strip()
        if not brief:
            raise ValueError("A non-empty campaign brief is required.")

        task_id = f"task-{uuid.uuid4().hex}"
        run_id = f"run-{uuid.uuid4().hex}"
        result_id = f"result-{uuid.uuid4().hex}"
        task = {
            "task_id": task_id,
            "workflow_id": "clay-hq-eod-demo",
            "brief": brief,
            "target_audience": "active adults",
            "deliverables": ["campaign direction", "responsive website", "responsive email", "image-generation attempt"],
            "requested_actions": ["local_generation", "local_review"],
            "forbidden_actions": ["deploy", "publish", "send", "canon_mutation", "external_message"],
            "created_at": utc_now(),
        }
        hermes_capabilities = {}
        constrained_run_supported = False
        if self.hermes is not None:
            try:
                hermes_capabilities = self.hermes.capabilities()
                constrained_run_supported = _feature_enabled(hermes_capabilities, "run_toolset_constraints")
            except Exception:
                hermes_capabilities = {}
        self.store.save_task(task)
        self.store.create_run(run_id, task_id, "clay-hq-eod-demo", "structured" if constrained_run_supported else "manual/unstructured")
        self.store.append_event(run_id, "run.created", "queued", {"brief": brief, "trigger": "plain-language"}, actor="human:Ryan")

        canon_ids = []
        try:
            for reference in CanonRegistry(self.root).resolve_all():
                canon_ids.append(self.store.snapshot_canon(run_id, reference))
            self.store.append_event(run_id, "canon.resolved", "running", {"snapshot_ids": canon_ids, "authority": "pinned-read-only"}, actor="agent:studio-director")
        except Exception as exc:
            self.store.append_event(run_id, "canon.degraded", "degraded", {"reason": type(exc).__name__, "claim": "No canon success was fabricated."}, actor="agent:studio-director")

        self.store.append_event(run_id, "agent.stage.started", "running", {"stage": "campaign-direction", "agent": "studio-director", "parent": None}, actor="agent:studio-director")

        hermes_run_id = None
        hermes_status = "unavailable"
        hermes_output = ""
        hermes_event_evidence = ""
        hermes_failure_artifact = None
        if self.hermes is not None:
            prompt = f"""Produce copy direction for a LOCAL-ONLY Clay HQ operational demo.
Campaign brief: {brief}
Return concise JSON with campaign_direction and copy_options. No tools are available; do not perform or request external actions."""
            if not constrained_run_supported:
                hermes_status = "unavailable_constraints"
                self.store.append_event(run_id, "hermes.run.unavailable", "degraded", {"reason": "run_toolset_constraints_not_advertised", "submission_performed": False}, actor="agent:studio-director")
            else:
                try:
                    created = self.hermes.create_demo_run(prompt, idempotency_key=f"clay-hq:{run_id}")
                    hermes_run_id = created["run_id"]
                    self.store.append_event(run_id, "hermes.run.submitted", "running", {"hermes_run_id": hermes_run_id, "execution_mode": "structured", "enabled_toolsets": []}, actor="agent:studio-director")
                    deadline = time.monotonic() + timeout_seconds
                    remote = self.hermes.get_run(hermes_run_id)
                    while remote.get("status") not in TERMINAL_HERMES_STATES and remote.get("status") != "waiting_for_approval" and time.monotonic() < deadline:
                        time.sleep(1)
                        remote = self.hermes.get_run(hermes_run_id)
                    observed_status = str(remote.get("status", "unknown"))
                    if observed_status not in TERMINAL_HERMES_STATES:
                        stop_reason = "waiting_for_approval" if observed_status == "waiting_for_approval" else "timeout"
                        try:
                            stop_result = self.hermes.stop_run(hermes_run_id)
                            self.store.append_event(run_id, "hermes.run.stop_requested", "degraded", {"hermes_run_id": hermes_run_id, "reason": stop_reason, "remote_status": observed_status, "stop_response": stop_result}, actor="agent:studio-director")
                        except Exception as exc:
                            self.store.append_event(run_id, "hermes.run.stop_failed", "degraded", {"hermes_run_id": hermes_run_id, "reason": stop_reason, "remote_status": observed_status, "error_type": type(exc).__name__}, actor="agent:studio-director")
                            raise NonterminalHermesRun("Hermes stop request failed before a terminal state was observed.") from exc
                        stop_deadline = time.monotonic() + max(0, min(30, timeout_seconds))
                        remote = self.hermes.get_run(hermes_run_id)
                        observed_status = str(remote.get("status", "unknown"))
                        while observed_status not in TERMINAL_HERMES_STATES and time.monotonic() < stop_deadline:
                            time.sleep(0.1)
                            remote = self.hermes.get_run(hermes_run_id)
                            observed_status = str(remote.get("status", "unknown"))
                        if observed_status not in TERMINAL_HERMES_STATES:
                            raise NonterminalHermesRun("Hermes did not reach a terminal state after stop was requested.")
                        hermes_status = observed_status
                    else:
                        hermes_status = observed_status
                    hermes_output = _extract_output(remote) if observed_status == "completed" else ""
                    try:
                        event_stream = self.hermes.get_run_events(hermes_run_id)
                        hermes_event_evidence = event_stream if isinstance(event_stream, str) else json.dumps(event_stream, sort_keys=True)
                    except Exception as exc:
                        hermes_event_evidence = f"events-unavailable:{type(exc).__name__}"
                    self.store.append_event(run_id, "hermes.run.observed", "running" if hermes_status == "completed" else "degraded", {"hermes_run_id": hermes_run_id, "remote_status": hermes_status, "event_stream_sha256": hashlib.sha256(hermes_event_evidence.encode()).hexdigest(), "output_present": bool(hermes_output)}, actor="agent:studio-director")
                    if observed_status in {"failed", "error", "cancelled", "stopped"}:
                        failure = {"hermes_run_id": hermes_run_id, "remote_status": observed_status, "output_used": False, "event_stream_sha256": hashlib.sha256(hermes_event_evidence.encode()).hexdigest()}
                        hermes_failure_artifact = self.artifacts.write_json(run_id, f"{run_id}/hermes/failure.json", failure)
                        self.store.append_event(run_id, "hermes.run.terminal_failure", "degraded", {**failure, "artifact_id": hermes_failure_artifact["artifact_id"]}, actor="agent:studio-director")
                except (CapabilityMismatch, HermesOffline) as exc:
                    hermes_status = "unavailable"
                    self.store.append_event(run_id, "hermes.run.failed", "degraded", {"error_type": type(exc).__name__, "submission_completed": bool(hermes_run_id)}, actor="agent:studio-director")

        campaign = _campaign_payload(hermes_output)
        campaign_artifact = self.artifacts.write_json(run_id, f"{run_id}/campaign/direction.json", campaign)
        self.store.append_event(run_id, "agent.stage.completed", "running", {"stage": "campaign-direction", "artifact_id": campaign_artifact["artifact_id"]}, actor="agent:studio-director")
        self.store.append_event(run_id, "agent.handoff", "running", {"from": "studio-director", "to": "copywriter", "artifact_id": campaign_artifact["artifact_id"]}, actor="agent:studio-director")

        copy_options = campaign.get("copy_options") if isinstance(campaign.get("copy_options"), list) else []
        headline = str(copy_options[0]) if copy_options else "Built for the work between milestones."
        self.store.append_event(run_id, "agent.stage.completed", "running", {"stage": "copy-options", "headline": headline}, actor="agent:copywriter")

        website = self.artifacts.write_text(run_id, f"{run_id}/website/index.html", self._website_html(headline), kind="website/html")
        self.store.append_event(run_id, "agent.stage.completed", "running", {"stage": "website-build", "artifact_id": website["artifact_id"], "verification": "responsive-css-present"}, actor="agent:web-builder")

        email = self.artifacts.write_text(run_id, f"{run_id}/email/index.html", self._email_html(headline), kind="email/html")
        self.store.append_event(run_id, "agent.stage.completed", "running", {"stage": "email-design", "artifact_id": email["artifact_id"], "verification": "responsive-email-css-present", "send_performed": False}, actor="agent:email-designer")

        image_capability = _feature_enabled(hermes_capabilities, "image_generation")
        if not image_capability:
            image_status = "unavailable"
            image_reason = "Structured capability data did not advertise image generation."
        else:
            image_status = "not_attempted"
            image_reason = "Image generation capability was advertised but intentionally not invoked through Hermes."
        image_evidence = {"kind": "capability-check", "capability": "image_generation", "available": image_capability, "attempted": False}
        image_attempt = self.artifacts.write_json(
            run_id,
            f"{run_id}/image/attempt.json",
            {"status": image_status, "reason": image_reason, "evidence": image_evidence, "credential_access": False, "external_release": False},
        )
        self.store.append_event(run_id, "agent.stage.completed", "degraded", {"stage": "image-attempt", "status": image_status, "attempted": False, "evidence": image_evidence, "artifact_id": image_attempt["artifact_id"]}, actor="agent:image-director")

        approval_id = f"approval-{uuid.uuid4().hex}"
        scope = {"run_id": run_id, "result_id": result_id, "action": "release_review"}
        approval = self.store.create_approval(approval_id, run_id, "release_review", scope, "Review local campaign, website, email, and image-attempt evidence. Approval performs no external action.")
        result = {
            "result_id": result_id,
            "task_id": task_id,
            "run_id": run_id,
            "workflow_id": "clay-hq-eod-demo",
            "status": "awaiting_approval",
            "execution_mode": "structured" if hermes_run_id else "manual/unstructured",
            "hermes_run_id": hermes_run_id,
            "hermes_status": hermes_status,
            "artifacts": [campaign_artifact, website, email, image_attempt] + ([hermes_failure_artifact] if hermes_failure_artifact else []),
            "approval": approval,
            "external_side_effects": [],
            "canon_mutations": [],
        }
        self.store.save_result(result_id, run_id, task_id, result, completed=True)
        self.store.append_event(run_id, "approval.requested", "awaiting_approval", {"approval_id": approval_id, "scope": scope, "external_action": False}, actor="agent:studio-director")
        return result

    def resolve(self, approval_id: str, decision: str, *, actor="Ryan", reason="") -> dict:
        with self.store.transaction():
            return self._resolve(approval_id, decision, actor=actor, reason=reason)

    def _resolve(self, approval_id: str, decision: str, *, actor="Ryan", reason="") -> dict:
        approval = self.store.get_approval(approval_id)
        if not approval:
            raise ValueError("Approval not found.")
        if decision not in {"approved", "rejected", "changes_requested"}:
            raise ValueError("Unsupported approval decision.")
        record = self.store.resolve_approval(
            approval_id,
            decision == "approved",
            actor,
            approval["scope"],
            reason,
            request_changes=decision == "changes_requested",
        )
        status = "approved_local_only" if decision == "approved" else decision
        self.store.append_event(approval["run_id"], "approval.resolved", status, {"approval_id": approval_id, "decision_id": record["decision_id"], "external_action": False}, actor=f"human:{actor}")
        if decision == "approved":
            self.store.append_event(
                approval["run_id"],
                "run.resumed",
                "approved_local_only",
                {
                    "approval_id": approval_id,
                    "decision_id": record["decision_id"],
                    "external_action": False,
                    "resume_scope": "local-evidence-only",
                },
                actor=f"human:{actor}",
            )
        return record

    @staticmethod
    def _website_html(headline: str) -> str:
        safe = headline.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Clay Movement Campaign — Local Preview</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#09100d;color:#f2eee5;font-family:Arial,sans-serif}}main{{min-height:100vh;display:grid;place-items:center;padding:8vw}}.frame{{width:min(1120px,100%);border-top:1px solid #c8ff00;padding-top:24px}}.eyebrow{{font:12px monospace;letter-spacing:.18em;text-transform:uppercase;color:#c8ff00}}h1{{font-size:clamp(48px,10vw,144px);line-height:.86;letter-spacing:-.06em;max-width:10ch;margin:.35em 0}}p{{font-size:clamp(16px,2vw,24px);max-width:32ch;color:#a9b2ac}}.cta{{display:inline-block;margin-top:28px;border:1px solid #f2eee5;padding:14px 18px;text-transform:uppercase;font:12px monospace;letter-spacing:.12em}}@media(max-width:600px){{main{{padding:24px}}h1{{font-size:52px}}}}</style></head><body><main><section class=\"frame\"><div class=\"eyebrow\">Clay · local campaign preview · not deployed</div><h1>{safe}</h1><p>Daily movement, designed around the life already in motion.</p><span class=\"cta\">Review locally</span></section></main></body></html>"""

    @staticmethod
    def _email_html(headline: str) -> str:
        safe = headline.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Clay Email — Local Preview</title><style>body{{margin:0;background:#e9e7df;color:#101512;font-family:Arial,sans-serif}}.shell{{max-width:640px;margin:0 auto;background:#fff}}.top{{background:#0b110e;color:#fff;padding:48px 42px}}.mark{{font:11px monospace;letter-spacing:.16em;color:#c8ff00;text-transform:uppercase}}h1{{font-size:46px;line-height:.95;letter-spacing:-.04em;margin:30px 0 18px}}.body{{padding:36px 42px;font-size:18px;line-height:1.55}}.button{{display:inline-block;background:#0b110e;color:#fff;padding:14px 18px;text-decoration:none;font:12px monospace;letter-spacing:.1em;text-transform:uppercase}}.notice{{margin-top:32px;font:10px monospace;color:#66716b}}@media(max-width:680px){{.top,.body{{padding:28px 22px}}h1{{font-size:38px}}}}</style></head><body><div class=\"shell\"><div class=\"top\"><div class=\"mark\">Clay · responsive email preview</div><h1>{safe}</h1></div><div class=\"body\"><p>A simple invitation to make movement part of the day you already have.</p><span class=\"button\">Review the campaign</span><p class=\"notice\">LOCAL PREVIEW ONLY · NOT SENT</p></div></div></body></html>"""
