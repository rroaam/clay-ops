from __future__ import annotations
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from clay_ops.adapters.hermes_api import HermesAPIAdapter, HermesOffline, CapabilityMismatch, HTTPTransport

class FakeTransport:
    def __init__(self,responses): self.responses=list(responses); self.calls=[]
    def request(self,method,url,headers=None,json_body=None,stream=False):
        self.calls.append((method,url,headers or {},json_body,stream))
        item=self.responses.pop(0)
        if isinstance(item,Exception): raise item
        return item

CAPS={"object":"hermes.api_server.capabilities","features":{"run_submission":True,"run_status":True,"run_events_sse":True,"run_approval":True,"run_stop":True,"session_list":True,"session_read":True}}

def test_capability_detection_precedes_run_submission():
    t=FakeTransport([(200,CAPS),(202,{"run_id":"r1","status":"started"})])
    a=HermesAPIAdapter("http://127.0.0.1:8642","runtime-token",transport=t)
    a.create_run("hello",idempotency_key="task-1")
    assert t.calls[0][1].endswith("/v1/capabilities") and t.calls[1][1].endswith("/v1/runs")
    assert t.calls[1][3]["metadata"]["source"] == "structured"


def test_capability_mismatch_blocks_feature():
    t=FakeTransport([(200,{"features":{"run_submission":False}})])
    with pytest.raises(CapabilityMismatch): HermesAPIAdapter("http://127.0.0.1:8642","t",transport=t).create_run("x",idempotency_key="k")


def test_disconnect_returns_offline_not_fabricated():
    t=FakeTransport([OSError("network down")])
    with pytest.raises(HermesOffline): HermesAPIAdapter("http://127.0.0.1:8642","runtime-token",transport=t).capabilities()


def test_disconnect_during_run_is_degraded():
    t=FakeTransport([(200,CAPS),(202,{"run_id":"r1","status":"started"}),(200,CAPS),OSError("lost")])
    a=HermesAPIAdapter("http://127.0.0.1:8642","runtime-token",transport=t); a.create_run("x",idempotency_key="k")
    assert a.get_run("r1")["status"] == "degraded"


def test_duplicate_submission_is_idempotent():
    t=FakeTransport([(200,CAPS),(202,{"run_id":"r1","status":"started"})])
    a=HermesAPIAdapter("http://127.0.0.1:8642","runtime-token",transport=t)
    assert a.create_run("x",idempotency_key="same")==a.create_run("x",idempotency_key="same")
    assert len([c for c in t.calls if c[1].endswith("/v1/runs")])==1


def test_token_never_appears_in_repr_or_errors():
    a=HermesAPIAdapter("http://127.0.0.1:8642","runtime-token",transport=FakeTransport([OSError("runtime-token leaked")]))
    assert "runtime-token" not in repr(a)
    with pytest.raises(HermesOffline) as exc: a.capabilities()
    assert "runtime-token" not in str(exc.value)


def test_only_allowlisted_endpoints_are_constructed():
    a=HermesAPIAdapter("http://127.0.0.1:8642","t",transport=FakeTransport([]))
    with pytest.raises(ValueError): a._url("/api/config")


@pytest.mark.parametrize('url', [
    'https://127.0.0.1:8642',
    'http://example.com:8642',
    'http://user:pass@127.0.0.1:8642',
    'http://127.0.0.1:8642/api',
    'http://127.0.0.1:8642/?x=1',
])
def test_base_url_must_be_plain_http_loopback_root(url):
    with pytest.raises(ValueError):
        HermesAPIAdapter(url, 't', transport=FakeTransport([]))


def test_constrained_demo_submission_requires_advertised_support():
    unsupported = FakeTransport([(200, CAPS)])
    adapter = HermesAPIAdapter('http://127.0.0.1:8642', 't', transport=unsupported)
    with pytest.raises(CapabilityMismatch):
        adapter.create_demo_run('local copy only', idempotency_key='k')
    assert not any(call[1].endswith('/v1/runs') for call in unsupported.calls)

    caps = {**CAPS, 'features': {**CAPS['features'], 'run_toolset_constraints': True}}
    supported = FakeTransport([(200, caps), (202, {'run_id': 'safe-1'})])
    adapter = HermesAPIAdapter('http://127.0.0.1:8642', 't', transport=supported)
    adapter.create_demo_run('local copy only', idempotency_key='safe')
    body = supported.calls[-1][3]
    assert body['enabled_toolsets'] == []
    assert 'image' not in body['input'].lower()


def test_http_transport_does_not_follow_redirect_with_authorization():
    observed = []
    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append(self.headers.get('Authorization'))
            self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        def log_message(self, *args): pass
    target = ThreadingHTTPServer(('127.0.0.1', 0), Target)
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', f'http://127.0.0.1:{target.server_port}/capture')
            self.end_headers()
        def log_message(self, *args): pass
    source = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (source, target)]
    for thread in threads: thread.start()
    try:
        with pytest.raises(HermesOffline):
            HTTPTransport().request('GET', f'http://127.0.0.1:{source.server_port}/redirect', headers={'Authorization': 'Bearer secret'})
        assert observed == []
    finally:
        for server in (source, target): server.shutdown(); server.server_close()
        for thread in threads: thread.join(timeout=5)
