"""
Phase 0 event simulation CLI.
"""
import argparse
import json
import sys
from pathlib import Path
from clay_ops.simulation.event_processor import EventProcessor
from clay_ops.simulation.project_state import ProjectStateEngine
from clay_ops.simulation.work_ledger import WorkLedger
from clay_ops.simulation.schema import SIMULATION_SCHEMA
import sqlite3


def cmd_event_simulate(args):
    """Simulate event ingestion from fixtures."""
    processor = EventProcessor(args.database)
    
    fixture_files = []
    if args.all:
        # Process all fixture files in deterministic order
        fixture_dir = Path("fixtures")
        fixture_files = sorted([
            f for f in fixture_dir.rglob("*.json")
            if f.is_file() and not f.name.startswith("_")
        ])
    else:
        fixture_path = Path(args.fixture)
        if not fixture_path.exists():
            print(f"Fixture not found: {fixture_path}", file=sys.stderr)
            return 1
        fixture_files = [fixture_path]
    
    results = []
    for fixture_file in fixture_files:
        with open(fixture_file) as f:
            try:
                fixtures = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON in {fixture_file}: {e}", file=sys.stderr)
                continue
        
        # Handle both single fixture and array of fixtures
        if isinstance(fixtures, dict):
            fixtures = [fixtures]
        
        for fixture in fixtures:
            result = processor.process_fixture(fixture)
            results.append({
                "fixture_file": str(fixture_file),
                "event_type": fixture.get("event_type"),
                "timestamp": fixture.get("timestamp"),
                "result": result
            })
            if args.format == "text":
                print(f"Processed: {fixture_file.name} - {fixture.get('event_type')} @ {fixture.get('timestamp')}")
    
    processor.conn.close()
    
    if args.format == "json":
        print(json.dumps({
            "total_processed": len(results),
            "work_items_created": sum(1 for r in results if r["result"].get("work_item_id")),
            "work_items_updated": sum(1 for r in results if r["result"].get("work_item_updated")),
            "blockers_detected": sum(len(r["result"].get("blockers_detected", [])) for r in results),
            "approvals_created": sum(len(r["result"].get("approvals_required", [])) for r in results),
            "results": results
        }, indent=2))
    else:
        print(f"\nTotal events processed: {len(results)}")
        print(f"Work items created: {sum(1 for r in results if r['result'].get('work_item_id'))}")
        print(f"Work items updated: {sum(1 for r in results if r['result'].get('work_item_updated'))}")
        print(f"Blockers detected: {sum(len(r['result'].get('blockers_detected', [])) for r in results)}")
        print(f"Approvals created: {sum(len(r['result'].get('approvals_required', [])) for r in results)}")
    
    return 0


def cmd_project_status(args):
    """Show project state preview."""
    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    
    engine = ProjectStateEngine(conn)
    state = engine.compute_state()
    
    if getattr(args, 'format', 'text') == "json":
        output = {
            "schema_version": "1.0.0",
            "computed_at": state.get("computed_at"),
            "projects": state.get("projects", {}),
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print("\n=== Project State Preview ===\n")
        
        for project_id, project_data in state['projects'].items():
            print(f"Project: {project_id}")
            print(f"  Health: {project_data['health']}")
            print(f"  Active: {project_data['active_count']}, Done: {project_data['done_count']}, "
                  f"Blocked: {project_data['blocked_count']}, Stale: {project_data['stale']}")
            
            if project_data['blockers']:
                print(f"  Blockers:")
                for blocker in project_data['blockers']:
                    print(f"    - {blocker['reason']} (raised {blocker['raised_at'][:10]})")
            
            if project_data['pending_approvals']:
                print(f"  Pending Approvals: {len(project_data['pending_approvals'])}")
            
            print()
    
    conn.close()
    return 0


def cmd_work_ledger(args):
    """Show work ledger preview."""
    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    
    ledger = WorkLedger(conn)
    fmt = getattr(args, 'format', 'text')
    
    data = {}
    if args.section == 'items':
        items = ledger.get_work_items(status=getattr(args, 'status', None))
        data = {"work_items": [dict(i) for i in items[:50]], "total_count": len(items), "section": "items"}
    elif args.section == 'blockers':
        blockers = ledger.get_blockers()
        data = {"blockers": [dict(b) for b in blockers], "total_count": len(blockers), "section": "blockers"}
    elif args.section == 'approvals':
        approvals = ledger.get_approvals(status=getattr(args, 'approval_status', None) or 'pending')
        data = {"approvals": [dict(a) for a in approvals], "total_count": len(approvals), "section": "approvals"}
    
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"\n=== Work Ledger Preview (section: {args.section}) ===\n")
        
        if args.section == 'items':
            items = data["work_items"]
            print(f"Work Items ({data['total_count']} total):\n")
            for item in items[:10]:
                print(f"  [{item['work_item_id']}] {item['title']}")
                print(f"    Status: {item['status']} | Priority: {item['priority']}")
                print(f"    Updated: {item['updated_at'][:16]} | Confidence: {item['confidence']:.2f}")
                if item['stale_since']:
                    print(f"    ⚠️  STALE since {item['stale_since'][:10]}")
                print()
        
        elif args.section == 'blockers':
            blockers = data["blockers"]
            print(f"Active Blockers ({data['total_count']} total):\n")
            for blocker in blockers:
                print(f"  [{blocker['work_item_id']}] {blocker['reason']}")
                print(f"    Raised: {blocker['raised_at'][:16]} by {blocker.get('raised_by', 'system')}")
                print()
        
        elif args.section == 'approvals':
            approvals = data["approvals"]
            status_filter = getattr(args, 'approval_status', None) or 'pending'
            print(f"Approvals ({data['total_count']} {status_filter}):\n")
            for approval in approvals:
                print(f"  [{approval['approval_id']}] {approval['approval_type']}")
                print(f"    Work Item: {approval['work_item_id']}")
                print(f"    Requested: {approval['requested_at'][:16]} by {approval['requester']}")
                print(f"    Status: {approval['status']}")
                if approval.get('decision_summary'):
                    print(f"    Decision: {approval['decision_summary']}")
                print()
    
    conn.close()
    return 0


def cmd_simulation_reset(args):
    """Reset simulation database."""
    db_path = Path(args.database)
    
    if db_path.exists():
        if args.confirm:
            db_path.unlink()
            print(f"Deleted: {db_path}")
        else:
            print(f"Would delete: {db_path}")
            response = input("Confirm? (yes/no): ").strip().lower()
            if response == 'yes':
                db_path.unlink()
                print(f"Deleted: {db_path}")
            else:
                print("Cancelled")
                return 0
    
    # Recreate schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SIMULATION_SCHEMA)
    conn.commit()
    conn.close()
    
    print(f"Initialized: {db_path}")
    return 0


def handle_simulation_command(args):
    """Dispatch simulation subcommands."""
    if args.simulation_command == "event-simulate":
        return cmd_event_simulate(args)
    elif args.simulation_command == "project-status":
        return cmd_project_status(args)
    elif args.simulation_command == "work-ledger":
        return cmd_work_ledger(args)
    elif args.simulation_command == "reset":
        return cmd_simulation_reset(args)
    else:
        print(f"Unknown simulation command: {args.simulation_command}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="Phase 0 Event Simulation")
    parser.add_argument('--database', default='data/simulation/clay-ops.sim.db',
                       help='Simulation database path')
    
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # event-simulate
    sim_parser = subparsers.add_parser('event-simulate', help='Simulate event ingestion')
    sim_parser.add_argument('--fixture', required=True, help='Path to fixture JSON')
    sim_parser.set_defaults(func=cmd_event_simulate)
    
    # project-status
    status_parser = subparsers.add_parser('project-status', help='Show project state')
    status_parser.set_defaults(func=cmd_project_status)
    
    # work-ledger
    ledger_parser = subparsers.add_parser('work-ledger', help='Show work ledger')
    ledger_parser.add_argument('--section', choices=['items', 'blockers', 'approvals'],
                              default='items', help='Section to display')
    ledger_parser.add_argument('--status', help='Filter work items by status')
    ledger_parser.add_argument('--approval-status', help='Filter approvals by status')
    ledger_parser.set_defaults(func=cmd_work_ledger)
    
    # simulation-reset
    reset_parser = subparsers.add_parser('simulation-reset', help='Reset simulation database')
    reset_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    reset_parser.set_defaults(func=cmd_simulation_reset)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
