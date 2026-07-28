import json
import threading
import urllib.error
import urllib.request

import pytest

from clay_ops.api import create_server
from clay_ops.store import OperationalStore


class CompletedHermes:
    def capabilities(self):
        return {'features': {'run_toolset_constraints': True, 'image_generation': False}}

    def create_demo_run(self, input_text, *, idempotency_key, **kwargs):
        return {'run_id': 'api-hermes-1'}

    def get_run(self, run_id):
        return {'run_id': run_id, 'status': 'completed', 'output': '{"campaign_direction":"Local movement","copy_options":["Move through the day."]}'}

    def get_run_events(self, run_id):
        return 'data: {"type":"image_generation.unavailable"}\n\n'


COMMAND_HEADERS = {
    'Content-Type': 'application/json',
    'Origin': 'http://127.0.0.1:3001',
    'X-Clay-HQ-Server': '1',
}


def request(url, method='GET', body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or ({'Content-Type': 'application/json'} if body is not None else {}))
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, dict(response.headers), json.loads(response.read() or b'{}')


def test_loopback_api_trigger_projection_artifact_and_approval(tmp_path):
    root = tmp_path / 'ops'
    root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    server = create_server(('127.0.0.1', 0), root=root, store=store, hermes=CompletedHermes())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        status, headers, health = request(base + '/health')
        assert status == 200
        assert health['status'] == 'ok'
        assert 'Access-Control-Allow-Origin' not in headers

        status, _, created = request(base + '/api/runs', 'POST', {'brief': 'Build a local Clay campaign demo.'}, COMMAND_HEADERS)
        assert status == 201
        assert created['status'] == 'awaiting_approval'

        _, _, projection = request(base + '/api/projection')
        run = projection['runs'][0]
        assert run['run_id'] == created['run_id']
        assert projection['needs_ryan'][0]['approval_status'] == 'pending'
        assert all(agent['status'] in {'simulated', 'unavailable'} for agent in projection['agents'])
        assert next(agent for agent in projection['agents'] if agent['id'] == 'image-director')['status'] == 'unavailable'
        assert projection['health']['image_provider']['status'] == 'unavailable'
        image_evidence = next(item for item in run['artifacts'] if item['relative_path'].endswith('/image/attempt.json'))
        with urllib.request.urlopen(base + image_evidence['preview_url'], timeout=10) as response:
            assert json.loads(response.read())['status'] == 'unavailable'

        artifact_url = next(item['preview_url'] for item in run['artifacts'] if item['kind'] == 'website/html')
        with urllib.request.urlopen(base + artifact_url, timeout=10) as response:
            assert response.status == 200
            assert 'text/html' in response.headers['Content-Type']
            assert b'LOCAL' in response.read().upper()

        approval_id = projection['needs_ryan'][0]['approval_id']
        status, _, decision = request(base + f'/api/approvals/{approval_id}', 'POST', {'decision': 'approved', 'actor': 'Ryan'}, COMMAND_HEADERS)
        assert status == 200
        assert decision['decision'] == 'approved'
        _, _, refreshed = request(base + '/api/projection')
        assert refreshed['needs_ryan'] == []
        assert refreshed['runs'][0]['status'] == 'approved_local_only'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_command_api_rejects_csrf_shaped_requests(tmp_path):
    root = tmp_path / 'ops'
    root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    server = create_server(('127.0.0.1', 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/api/runs'
    cases = [
        {'Content-Type': 'text/plain', 'Origin': 'http://127.0.0.1:3001', 'X-Clay-HQ-Server': '1'},
        {'Content-Type': 'application/json', 'Origin': 'https://evil.example', 'X-Clay-HQ-Server': '1'},
        {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:3001'},
        {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:3001', 'X-Clay-HQ-Server': '1', 'Host': 'evil.example'},
        {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1:3001', 'X-Clay-HQ-Server': '1', 'Host': '127.0.0.1:80,evil.example'},
    ]
    try:
        for headers in cases:
            req = urllib.request.Request(url, data=b'{"brief":"x"}', method='POST', headers=headers)
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req, timeout=10)
            assert exc.value.code == 403 or (headers['Content-Type'] != 'application/json' and exc.value.code == 415)
            assert 'Access-Control-Allow-Origin' not in exc.value.headers
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('origin', ['http://127.0.0.1:3000', 'http://127.0.0.1:9999', 'http://localhost:3001'])
def test_command_api_rejects_non_dashboard_loopback_origins(tmp_path, origin):
    root = tmp_path / 'ops'
    root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    server = create_server(('127.0.0.1', 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/api/runs'
    headers = {'Content-Type': 'application/json', 'Origin': origin, 'X-Clay-HQ-Server': '1'}
    try:
        req = urllib.request.Request(url, data=b'{"brief":"x"}', method='POST', headers=headers)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_read_api_rejects_non_loopback_host(tmp_path):
    root = tmp_path / 'ops'
    root.mkdir()
    store = OperationalStore(root / 'runtime' / 'ops.sqlite3')
    server = create_server(('127.0.0.1', 0), root=root, store=store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/api/projection'
    try:
        req = urllib.request.Request(url, headers={'Host': 'attacker.example'})
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 403
        assert 'Access-Control-Allow-Origin' not in exc.value.headers
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
