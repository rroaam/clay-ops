from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from .canon import CanonRegistry
from .contracts import ContractError
from .demo import DemoOrchestrator
from .slack_adapter import SlackAdapterError
from .slack_intake import ingest_from_adapter, ingest_from_file
from .store import OperationalStore
from .workflows.copy_review import CopyReviewWorkflow

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"


def _store():
    return OperationalStore(RUNTIME / "clay-ops.sqlite3")


def _print(value):
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def doctor():
    checks = {
        "ops_root": ROOT.is_dir(),
        "git_repository": (ROOT / ".git").is_dir(),
        "runtime_confined": RUNTIME.resolve().parent == ROOT.resolve(),
        "canon_registry": (ROOT / "config/canon-registry.json").is_file(),
        "dashboard_is_canon": False,
        "hermes_api_enabled_by_clay_ops": False,
        "external_actions_available": False,
    }
    _store()
    status = "pass" if all(value is True for key, value in checks.items() if key not in {"dashboard_is_canon", "hermes_api_enabled_by_clay_ops", "external_actions_available"}) else "fail"
    _print({"status": status, "checks": checks, "note": "Hermes API capability is intentionally not probed before supervised enablement."})
    return 0 if status == "pass" else 1


def validate():
    issues = []
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            issues.append(f"{path.name}: {exc}")
    try:
        refs = CanonRegistry(ROOT).resolve_all()
    except Exception as exc:
        issues.append(str(exc))
        refs = []
    for path in [ROOT / "registries/agents.json", ROOT / "registries/tools.json", ROOT / "workflows/copy-review/v1.json", ROOT / "policies/approval-policy.json"]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("schema_version") != "1.0.0":
                issues.append(f"{path}: schema-version mismatch")
        except Exception as exc:
            issues.append(f"{path}: {exc}")
    _print({"status": "pass" if not issues else "fail", "issues": issues, "schemas": len(list((ROOT / "schemas").glob("*.schema.json"))), "canon_references": len(refs)})
    return 0 if not issues else 1


def build_parser():
    parser = argparse.ArgumentParser(prog="clay-ops")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("validate")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    serve.add_argument("--port", default=8765, type=int)
    workflow = commands.add_parser("workflow")
    workflow.add_subparsers(dest="workflow_command", required=True).add_parser("list")
    run = commands.add_parser("run")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    review = run_sub.add_parser("copy-review")
    source = review.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--source")
    review.add_argument("--target", required=True)
    review.add_argument("--acceptance", action="append", required=True)
    review.add_argument("--canon", action="append", required=True)
    review.add_argument("--provenance-label", default="ryan-provided")
    show = run_sub.add_parser("show")
    show.add_argument("run_id")
    approval = commands.add_parser("approval")
    approval_sub = approval.add_subparsers(dest="approval_command", required=True)
    approval_sub.add_parser("list")
    resolve = approval_sub.add_parser("resolve")
    resolve.add_argument("approval_id")
    choice = resolve.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    choice.add_argument("--request-changes", action="store_true")
    resolve.add_argument("--reason")
    slack = commands.add_parser("slack-intake")
    slack_group = slack.add_mutually_exclusive_group(required=True)
    slack_group.add_argument("--file", help="Local packet JSON file for ingestion")
    slack_group.add_argument("--channel", help="Slack channel_id for live ingestion (requires --thread)")
    slack.add_argument("--thread", help="Slack message_ts for live ingestion (requires --channel)")
    slack_check = commands.add_parser("slack-check")
    slack_check.set_defaults(slack_check=True)

    # Phase 0: Simulation commands
    sim = commands.add_parser("simulation", help="Phase 0 event simulation")
    sim.add_argument("--database", default="data/simulation/clay-ops.sim.db",
                     help="Simulation database path (isolated from production)")
    sim_sub = sim.add_subparsers(dest="simulation_command", required=True)

    # simulation event-simulate
    event_sim = sim_sub.add_parser("event-simulate", help="Simulate event ingestion")
    event_sim_group = event_sim.add_mutually_exclusive_group(required=True)
    event_sim_group.add_argument("--fixture", help="Path to fixture JSON")
    event_sim_group.add_argument("--all", action="store_true", help="Process all fixtures in fixtures/ directory")
    event_sim.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # simulation project-status
    proj_status = sim_sub.add_parser("project-status", help="Show project state")
    proj_status.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # simulation work-ledger
    ledger = sim_sub.add_parser("work-ledger", help="Show work ledger")
    ledger.add_argument("--section", choices=["items", "blockers", "approvals"],
                       default="items", help="Section to display")
    ledger.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    # simulation reset
    reset = sim_sub.add_parser("reset", help="Reset simulation database")
    reset.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor()
        if args.command == "validate":
            return validate()
        if args.command == "serve":
            from .adapters.hermes_api import HermesAPIAdapter
            from .api import create_server
            from .seed import seed_clay_projects

            token = os.environ.get("CLAY_HERMES_TOKEN", "")
            hermes = HermesAPIAdapter(os.environ.get("CLAY_HERMES_URL", "http://127.0.0.1:8642"), token) if token else None
            store = _store()
            # Seed the four truthful Clay projects on startup
            seed_clay_projects(store)
            server = create_server((args.host, args.port), root=ROOT, store=store, hermes=hermes)
            _print({"status": "ready", "url": f"http://{args.host}:{args.port}", "cors": "disabled", "command_headers": {"Content-Type": "application/json", "Origin": "http://<loopback-dashboard-origin>", "X-Clay-HQ-Server": "1"}, "hermes": "runtime-connected" if hermes else "not-configured"})
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
                store.db.close()
            return 0
        if args.command == "workflow":
            doc = json.loads((ROOT / "workflows/copy-review/v1.json").read_text(encoding="utf-8"))
            _print([{"workflow_id": doc["workflow_id"], "version": doc["version"], "purpose": doc["purpose"], "side_effect_mode": doc["side_effect_mode"]}])
            return 0
        store = _store()
        if args.command == "run" and args.run_command == "copy-review":
            provenance = {"kind": "direct" if args.text is not None else "local-read-only-source", "label": args.provenance_label}
            if args.source:
                provenance["path"] = str(Path(args.source).expanduser().resolve())
            result = CopyReviewWorkflow(ROOT, store, RUNTIME / "artifacts").run(text=args.text, source_reference=args.source, target_surface=args.target, acceptance_criteria=args.acceptance, canon_reference_ids=args.canon, source_provenance=provenance)
            _print(result)
            return 0
        if args.command == "run" and args.run_command == "show":
            _print({"projection": store.project_run(args.run_id), "result_packet": store.get_result_for_run(args.run_id), "events": store.list_events(args.run_id)})
            return 0
        if args.command == "approval" and args.approval_command == "list":
            _print(store.list_approvals())
            return 0
        if args.command == "approval" and args.approval_command == "resolve":
            disposition = "changes_requested" if args.request_changes else "approved" if args.approve else "rejected"
            decision = DemoOrchestrator(ROOT, store, RUNTIME / "artifacts").resolve(
                args.approval_id,
                disposition,
                actor="Ryan",
                reason=args.reason,
            )
            _print(decision)
            return 0
        if args.command == "slack-intake":
            if args.file:
                result = ingest_from_file(args.file)
                _print(result["needs_ryan"])
                return 0
            if args.channel:
                if not args.thread:
                    _print({"status": "error", "codes": ["SLACK_THREAD_REQUIRED"], "message": "--channel requires --thread"})
                    return 2
                result = ingest_from_adapter(channel_id=args.channel, thread_ts=args.thread)
                _print(result["needs_ryan"])
                return 0
        if args.command == "slack-check":
            from .slack_adapter import LiveSlackAdapter, SlackAdapterNotConfiguredError, is_adapter_configured
            if not is_adapter_configured():
                _print({"status": "error", "codes": ["SLACK_ADAPTER_NOT_CONFIGURED"], "message": "SLACK_OAUTH_TOKEN not set"})
                return 1
            adapter = LiveSlackAdapter()
            result = adapter.check_connection()
            if result:
                _print({"status": "ok", "team_id": result.get("team_id"), "team_name": result.get("team")})
                return 0
            _print({"status": "error", "codes": ["SLACK_CONNECTION_FAILED"], "message": "Token validation failed"})
            return 1
        if args.command == "simulation":
            from .simulation_cli import handle_simulation_command
            return handle_simulation_command(args)
    except (ContractError, OSError, ValueError) as exc:
        codes = getattr(exc, "codes", "CLAY_OPS_ERROR")
        _print({"status": "error", "codes": codes, "message": str(exc)})
        return 2
    except SlackAdapterError as exc:
        _print({"status": "error", "codes": exc.codes, "message": str(exc)})
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
