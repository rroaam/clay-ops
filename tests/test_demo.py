import json
from pathlib import Path

import pytest

from clay_ops.demo import DemoOrchestrator
from clay_ops.projection import ProjectionService
from clay_ops.store import OperationalStore


class CompletedHermes:
    def capabilities(self):
        return {'features': {'run_toolset_constraints': True, 'image_generation': False}}

    def create_demo_run(self, input_text, *, idempotency_key, **kwargs):
        assert 'no tools are available' in input_text.lower()
        assert 'image' not in input_text.lower()
        return {'run_id': 'hermes-structured-1', 'execution_mode': 'structured'}

    def get_run(self, run_id):
        return {
            'run_id': run_id,
            'status': 'completed',
            'output': '{"campaign_direction":"Move with clarity","copy_options":["Built for the work between milestones."]}',
            'execution_mode': 'structured',
        }

    def get_run_events(self, run_id):
        return 'data: {"type":"agent.handoff","from":"studio-director","to":"copywriter"}\n\n'


def make_demo(tmp_path):
    root = tmp_path / 'ops'
    root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    orchestrator = DemoOrchestrator(root, store, root / 'runtime' / 'artifacts', hermes=CompletedHermes())
    return root, store, orchestrator


def test_demo_workflow_creates_real_local_artifacts_and_approval(tmp_path):
    root, store, orchestrator = make_demo(tmp_path)
    result = orchestrator.run('Create a Clay movement campaign for active adults. Local demo only.')

    assert result['status'] == 'awaiting_approval'
    assert result['execution_mode'] == 'structured'
    assert result['hermes_run_id'] == 'hermes-structured-1'
    assert result['approval']['status'] == 'pending'

    artifact_root = root / 'runtime' / 'artifacts'
    website = artifact_root / result['run_id'] / 'website' / 'index.html'
    email = artifact_root / result['run_id'] / 'email' / 'index.html'
    image_attempt = artifact_root / result['run_id'] / 'image' / 'attempt.json'
    campaign = artifact_root / result['run_id'] / 'campaign' / 'direction.json'
    for path in (website, email, image_attempt, campaign):
        assert path.is_file()
    assert '@media' in website.read_text()
    assert 'max-width' in email.read_text()
    assert json.loads(image_attempt.read_text())['status'] in {'attempted', 'degraded', 'unavailable'}

    events = store.list_events(result['run_id'])
    actors = {event['actor'] for event in events}
    assert {'agent:studio-director', 'agent:copywriter', 'agent:web-builder', 'agent:email-designer'} <= actors
    assert any(event['event_type'] == 'agent.handoff' for event in events)
    assert events[-1]['status'] == 'awaiting_approval'


def test_projection_overlays_latest_hermes_observation(tmp_path):
    root = tmp_path / 'ops'
    root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    store.save_task({'task_id': 'task-sync', 'brief': 'Local sync test'})
    store.create_run('run-sync', 'task-sync', 'clay-hq-eod-demo', 'structured')
    store.save_result('result-sync', 'run-sync', 'task-sync', {'hermes_run_id': 'remote-1', 'hermes_status': 'waiting_for_approval'}, completed=True)
    store.append_event('run-sync', 'hermes.run.observed', 'complete', {'hermes_run_id': 'remote-1', 'remote_status': 'completed'}, actor='agent:studio-director')

    projection = ProjectionService(root, store).snapshot()
    assert projection['runs'][0]['hermes_status'] == 'completed'
    assert projection['health']['hermes']['status'] == 'connected_verified'


def test_projection_does_not_claim_unobserved_workflow_or_hermes_configuration(tmp_path):
    root, store, _ = make_demo(tmp_path)
    store.save_task({'task_id': 'task-copy', 'brief': 'Review copy'})
    store.create_run('run-copy', 'task-copy', 'copy-review', 'manual/unstructured')
    store.append_event('run-copy', 'run.failed', 'failed', {'reason': 'test'})

    projection = ProjectionService(root, store).snapshot()

    eod = next(item for item in projection['workflows'] if item['id'] == 'clay-hq-eod-demo')
    assert eod['status'] == 'ready_local'
    assert projection['health']['hermes']['status'] == 'not_configured'
    assert projection['health']['hermes']['evidence'] == 'No Hermes run evidence recorded.'


def test_projection_marks_observed_noncompleted_hermes_run_degraded(tmp_path):
    root, store, _ = make_demo(tmp_path)
    store.save_task({'task_id': 'task-eod', 'brief': 'Local demo'})
    store.create_run('run-eod', 'task-eod', 'clay-hq-eod-demo', 'structured')
    store.append_event(
        'run-eod',
        'hermes.run.observed',
        'degraded',
        {'hermes_run_id': 'remote-1', 'remote_status': 'cancelled'},
    )

    projection = ProjectionService(root, store).snapshot()

    assert projection['health']['hermes']['status'] == 'degraded'
    assert projection['health']['hermes']['evidence'] == 'Hermes run evidence exists, but no completed run is recorded.'


def test_projection_is_sanitized_and_approval_resolution_updates_timeline(tmp_path):
    root, store, orchestrator = make_demo(tmp_path)
    result = orchestrator.run('Local campaign demo without member data.')
    projection = ProjectionService(root, store).snapshot()

    run = next(item for item in projection['runs'] if item['run_id'] == result['run_id'])
    assert run['execution_mode'] == 'structured'
    assert run['status'] == 'awaiting_approval'
    assert len(run['artifacts']) >= 4
    assert all('sha256' in artifact for artifact in run['artifacts'])
    assert projection['needs_ryan'][0]['approval_id'] == result['approval']['approval_id']
    assert projection['health']['clay_ops']['status'] == 'connected_verified'
    assert projection['health']['external_actions']['status'] == 'blocked_by_policy'

    decision = orchestrator.resolve(result['approval']['approval_id'], 'approved', actor='Ryan')
    assert decision['decision'] == 'approved'
    refreshed = ProjectionService(root, store).snapshot()
    updated = next(item for item in refreshed['runs'] if item['run_id'] == result['run_id'])
    assert updated['status'] == 'approved_local_only'
    assert refreshed['needs_ryan'] == []
    assert updated['events'][-1]['actor'] == 'human:Ryan'
    assert updated['events'][-1]['event_type'] == 'run.resumed'


def test_approval_decision_and_timeline_are_atomic(tmp_path, monkeypatch):
    root, store, orchestrator = make_demo(tmp_path)
    result = orchestrator.run('Local campaign demo without member data.')
    approval_id = result['approval']['approval_id']
    original_append = store.append_event

    def fail_resolution_event(run_id, event_type, status, payload, actor='agent:clay-ops'):
        if event_type == 'approval.resolved':
            raise RuntimeError('simulated event write failure')
        return original_append(run_id, event_type, status, payload, actor)

    monkeypatch.setattr(store, 'append_event', fail_resolution_event)
    with pytest.raises(RuntimeError, match='simulated event write failure'):
        orchestrator.resolve(approval_id, 'approved', actor='Ryan')
    assert store.get_approval(approval_id)['status'] == 'pending'
    assert store.list_approval_decisions(approval_id) == []


def test_demo_workflow_rolls_back_database_state_on_artifact_failure(tmp_path, monkeypatch):
    root = tmp_path / 'ops'; root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    orchestrator = DemoOrchestrator(root, store, root / 'runtime' / 'artifacts', hermes=UnsupportedConstraintsHermes())

    def fail_record(*args, **kwargs):
        raise RuntimeError('simulated artifact DB failure')

    monkeypatch.setattr(store, 'record_artifact', fail_record)
    with pytest.raises(RuntimeError, match='simulated artifact DB failure'):
        orchestrator.run('Local campaign only.')
    assert store.list_runs() == []


class UnsupportedConstraintsHermes:
    submitted = False

    def capabilities(self):
        return {'features': {'run_submission': True, 'image_generation': True}}

    def create_demo_run(self, *args, **kwargs):
        self.submitted = True
        raise AssertionError('broad execution must not be submitted')


def test_demo_does_not_submit_without_enforceable_run_constraints(tmp_path):
    root = tmp_path / 'ops'; root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    hermes = UnsupportedConstraintsHermes()
    result = DemoOrchestrator(root, store, root / 'runtime' / 'artifacts', hermes=hermes).run('Local copy direction only.')
    assert hermes.submitted is False
    assert result['execution_mode'] == 'manual/unstructured'
    assert result['hermes_status'] == 'unavailable_constraints'
    image = json.loads((root / 'runtime' / 'artifacts' / result['run_id'] / 'image' / 'attempt.json').read_text())
    assert image['status'] == 'not_attempted'
    assert image['evidence']['attempted'] is False


class WaitingHermes(CompletedHermes):
    def __init__(self): self.stopped = False
    def get_run(self, run_id): return {'run_id': run_id, 'status': 'stopped' if self.stopped else 'waiting_for_approval'}
    def stop_run(self, run_id): self.stopped = True; return {'run_id': run_id, 'status': 'stopping'}


def test_waiting_hermes_run_is_stopped_and_evidenced(tmp_path):
    root = tmp_path / 'ops'; root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    hermes = WaitingHermes()
    result = DemoOrchestrator(root, store, root / 'runtime' / 'artifacts', hermes=hermes).run('Local copy.', timeout_seconds=0)
    assert hermes.stopped is True
    assert result['hermes_status'] == 'stopped'
    stop_events = [e for e in store.list_events(result['run_id']) if e['event_type'] == 'hermes.run.stop_requested']
    assert stop_events[0]['payload']['reason'] == 'waiting_for_approval'


class NeverTerminalHermes(CompletedHermes):
    def get_run(self, run_id): return {'run_id': run_id, 'status': 'stopping'}
    def stop_run(self, run_id): return {'run_id': run_id, 'status': 'stopping'}


def test_nonterminal_hermes_stop_fails_closed(tmp_path):
    root = tmp_path / 'ops'; root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    orchestrator = DemoOrchestrator(root, store, root / 'runtime' / 'artifacts', hermes=NeverTerminalHermes())
    with pytest.raises(RuntimeError, match='terminal'):
        orchestrator.run('Local copy.', timeout_seconds=0)


class FailedHermes(CompletedHermes):
    def get_run(self, run_id): return {'run_id': run_id, 'status': 'failed', 'output': 'image generation attempted successfully'}


def test_terminal_failure_has_artifact_and_text_cannot_fake_image_attempt(tmp_path):
    root = tmp_path / 'ops'; root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    result = DemoOrchestrator(root, store, root / 'runtime' / 'artifacts', hermes=FailedHermes()).run('Local copy.')
    assert any(item['relative_path'].endswith('/hermes/failure.json') for item in result['artifacts'])
    image = json.loads((root / 'runtime' / 'artifacts' / result['run_id'] / 'image' / 'attempt.json').read_text())
    assert image['status'] == 'unavailable'
    assert image['evidence']['attempted'] is False
