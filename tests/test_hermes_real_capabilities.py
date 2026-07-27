from clay_ops.adapters.hermes_api import HermesAPIAdapter


class ListFeatureTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers=None, json_body=None, stream=False):
        self.calls.append((method, url, json_body, stream))
        if url.endswith('/v1/capabilities'):
            return 200, {
                'features': ['run_submission', 'run_status', 'run_events_sse', 'run_approval_response', 'run_stop'],
                'endpoints': {
                    'runs': {'method': 'POST', 'path': '/v1/runs'},
                    'run_status': {'method': 'GET', 'path': '/v1/runs/{run_id}'},
                    'run_events': {'method': 'GET', 'path': '/v1/runs/{run_id}/events'},
                    'run_approval': {'method': 'POST', 'path': '/v1/runs/{run_id}/approval'},
                    'run_stop': {'method': 'POST', 'path': '/v1/runs/{run_id}/stop'},
                },
            }
        if method == 'POST' and url.endswith('/v1/runs'):
            return 202, {'run_id': 'hermes-run-real'}
        if method == 'GET' and url.endswith('/v1/runs/hermes-run-real'):
            return 200, {'run_id': 'hermes-run-real', 'status': 'completed', 'output': 'done'}
        if url.endswith('/events'):
            return 200, 'data: {"type":"run.completed"}\n\n'
        raise AssertionError((method, url))


def test_real_capability_shape_uses_feature_list():
    transport = ListFeatureTransport()
    adapter = HermesAPIAdapter('http://127.0.0.1:8642', 'runtime-secret', transport)
    created = adapter.create_run('local-only brief', idempotency_key='demo-1')
    assert created['run_id'] == 'hermes-run-real'
    assert adapter.get_run('hermes-run-real')['status'] == 'completed'
    assert 'run.completed' in adapter.get_run_events('hermes-run-real')
