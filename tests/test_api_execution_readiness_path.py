"""API-path coverage for execution readiness.

The provider-readiness unit tests in test_execution_readiness.py call
evaluate_execution_readiness() directly. That left the request handler in
api.py uncovered, and a real defect lived there: the handler merged the image
registry with the known-provider slots using a "name" key, while both
ImageProviderRegistry.describe() and describe_known_providers() key their
records on "provider_id". The lookup raised KeyError('name'), which the handler
returned as HTTP 400, so the endpoint never reached the readiness evaluator.
Every unit test still passed.

These tests drive a real loopback server over HTTP so the handler itself is
exercised, including the merge. Note that api.py always constructs a default
ImageProviderRegistry when none is supplied, so the merge branch runs on the
production path too; passing image_registry=None does not skip it.

No provider is configured or called anywhere in this module. The spy provider
below fails the test if generate() is ever reached.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from clay_ops.api import create_server
from clay_ops.images import ImageCapabilities, ImageProviderRegistry
from clay_ops.provider_capabilities import describe_known_providers
from clay_ops.seed import seed_clay_projects
from clay_ops.store import OperationalStore

DEMO_APPROVAL = "approval-clay-morning-demo-draft"


class ProviderCallRecorder:
    """Registered like a real provider, but records any attempt to generate.

    Nothing in the readiness path may invoke a provider. If generate() is ever
    called, `called` flips and the assertion at the end of the test fails.
    """

    provider_id = "recording-stub"

    def __init__(self, available=False):
        self._available = available
        self.called = False

    def capabilities(self):
        return ImageCapabilities(
            available=self._available,
            models=("stub-v1",),
            aspect_ratios=("1:1", "4:5"),
            max_variants=4,
            supports_references=False,
        )

    def generate(self, request):
        self.called = True
        raise AssertionError("A provider was called during readiness evaluation.")


def _get(url):
    """GET returning (status, payload) without raising on 4xx/5xx."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


@pytest.fixture
def server(tmp_path, request):
    """A real loopback Clay Ops server seeded exactly as production startup does."""
    registry = getattr(request, "param", None)
    root = tmp_path / "ops"
    root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    seed_clay_projects(store)

    httpd = create_server(("127.0.0.1", 0), root=root, store=store, image_registry=registry)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield base
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        store.db.close()


def _assert_no_name_key(payload):
    """No provider record in the response may carry a legacy 'name' key."""
    for bucket in ("eligible_providers", "ineligible_providers"):
        for provider in payload[bucket]:
            assert "provider_id" in provider, f"{bucket} record missing provider_id"
            assert "name" not in provider, f"{bucket} record still carries a legacy name key"


def test_execution_readiness_endpoint_merges_providers_by_provider_id(server):
    """The handler merges registry and known slots without a KeyError.

    Regression guard for the 'name' lookup. A 400 carrying "'name'" is the exact
    signature of the original defect.
    """
    status, payload = _get(f"{server}/api/approvals/{DEMO_APPROVAL}/execution-readiness")

    assert status == 200, f"expected 200, got {status}: {payload}"
    assert payload.get("message") != "'name'", "KeyError('name') regression in the provider merge"

    # A complete, well-formed ReadinessResult rather than an error envelope.
    for field in (
        "ready_to_execute",
        "eligible_providers",
        "ineligible_providers",
        "envelope",
        "cost",
        "blocking_reasons",
        "approval_valid",
        "approval_expired",
        "hash_mismatch",
    ):
        assert field in payload, f"readiness payload missing {field}"

    _assert_no_name_key(payload)


def test_readiness_merge_covers_every_known_provider_slot_exactly_once(server):
    """Every known slot plus the registry's own providers, with no duplicates."""
    _status, payload = _get(f"{server}/api/approvals/{DEMO_APPROVAL}/execution-readiness")

    seen = [p["provider_id"] for p in payload["eligible_providers"] + payload["ineligible_providers"]]
    assert len(seen) == len(set(seen)), f"provider merged more than once: {seen}"

    # The default registry contributes 'unavailable'; describe_known_providers
    # contributes the named slots. The merge must lose neither.
    assert "unavailable" in seen, "registry-supplied provider was dropped by the merge"
    for slot in (p["provider_id"] for p in describe_known_providers()):
        assert slot in seen, f"known provider slot {slot} was dropped by the merge"


def test_readiness_reports_provider_availability_truthfully(server):
    """No provider is eligible, and every exclusion carries a real reason."""
    _status, payload = _get(f"{server}/api/approvals/{DEMO_APPROVAL}/execution-readiness")

    assert payload["ready_to_execute"] is False
    assert payload["eligible_providers"] == [], "no provider is configured; none may be eligible"
    assert payload["ineligible_providers"], "providers must be reported, not silently omitted"

    for provider in payload["ineligible_providers"]:
        assert provider["eligible"] is False
        reason = provider["exclusion_reason"]
        assert isinstance(reason, str) and reason.strip(), (
            f"{provider['provider_id']} was excluded without a truthful reason"
        )

    # Cost stays honestly unknown rather than defaulting to a number.
    assert payload["cost"]["estimated_total_usd"] is None
    assert payload["cost"]["unknown_reason"], "unknown cost must carry an explicit reason"

    # Execution stays blocked, with specific reasons rather than a generic flag.
    assert payload["blocking_reasons"], "a blocked result must explain itself"
    assert payload["envelope"]["provider"] is None
    assert payload["envelope"]["model"] is None


@pytest.mark.parametrize(
    "server", [ImageProviderRegistry([ProviderCallRecorder()])], indirect=True
)
def test_readiness_merge_handles_a_registry_supplied_provider(server):
    """A registry provider flows through the merge and is reported truthfully."""
    status, payload = _get(f"{server}/api/approvals/{DEMO_APPROVAL}/execution-readiness")

    assert status == 200
    _assert_no_name_key(payload)

    seen = {
        p["provider_id"]: p
        for p in payload["eligible_providers"] + payload["ineligible_providers"]
    }
    assert "recording-stub" in seen, "registry provider was dropped by the merge"
    assert "unavailable" in seen, "default registry provider was dropped by the merge"

    stub = seen["recording-stub"]
    assert stub["eligible"] is False
    assert stub["exclusion_reason"], "an unavailable registry provider needs a reason"
    assert payload["ready_to_execute"] is False


def test_readiness_never_calls_a_provider(tmp_path):
    """Evaluating readiness must not reach provider.generate()."""
    recorder = ProviderCallRecorder()
    root = tmp_path / "ops"
    root.mkdir()
    store = OperationalStore(root / "runtime" / "ops.sqlite3")
    seed_clay_projects(store)

    httpd = create_server(
        ("127.0.0.1", 0),
        root=root,
        store=store,
        image_registry=ImageProviderRegistry([recorder]),
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, _payload = _get(f"{base}/api/approvals/{DEMO_APPROVAL}/execution-readiness")
        assert status == 200
        # Repeat: a call on a second evaluation would be just as wrong.
        _get(f"{base}/api/approvals/{DEMO_APPROVAL}/execution-readiness")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        store.db.close()

    assert recorder.called is False, "readiness evaluation invoked a real provider"


def test_projection_endpoint_reports_providers_keyed_by_provider_id(server):
    """The projection uses the same provider vocabulary as the readiness merge."""
    status, payload = _get(f"{server}/api/projection")

    assert status == 200
    assert "providers" in payload, "projection must expose the provider registry"
    assert payload["providers"], "provider list must not be empty"

    for provider in payload["providers"]:
        assert "provider_id" in provider, "projection provider record missing provider_id"
        assert "name" not in provider, "projection provider record carries a legacy name key"
        assert provider["status"] != "available", (
            f"{provider['provider_id']} reported available with no adapter configured"
        )

    # The projection the UI actually renders is present and well-formed.
    for key in ("summary", "runs", "needs_ryan", "providers", "supervised_workflow"):
        assert key in payload, f"projection missing {key}"


def test_unknown_approval_is_a_clean_404_not_a_merge_crash(server):
    """A missing approval must 404, not surface as a handler exception."""
    status, payload = _get(f"{server}/api/approvals/approval-does-not-exist/execution-readiness")

    assert status == 404
    assert payload.get("message") != "'name'", "unknown approval must not reach the provider merge"
