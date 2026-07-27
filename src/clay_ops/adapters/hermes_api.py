from __future__ import annotations

import ipaddress
import json
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit


class HermesOffline(RuntimeError):
    pass


class CapabilityMismatch(RuntimeError):
    pass


class HTTPTransport:
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def request(self, method, url, headers=None, json_body=None, stream=False):
        data = json.dumps(json_body).encode() if json_body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(request, timeout=10) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    return response.status, body.decode("utf-8", errors="replace")
                return response.status, json.loads(body or b"{}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HermesOffline("Hermes API is offline or unreachable.") from None


class HermesAPIAdapter:
    _STATIC = {"/v1/capabilities", "/v1/runs", "/api/sessions"}
    _DYNAMIC = re.compile(r"^/(?:v1/runs/[^/]+(?:/events|/approval|/stop)?|api/sessions/[^/]+(?:/messages)?)$")

    def __init__(self, base_url: str, token: str, transport=None):
        if not token:
            raise ValueError("A runtime bearer token is required.")
        parsed = urlsplit(base_url)
        try:
            is_loopback = parsed.hostname == "localhost" or (parsed.hostname is not None and ipaddress.ip_address(parsed.hostname).is_loopback)
            _ = parsed.port
        except ValueError:
            is_loopback = False
        if (parsed.scheme != "http" or not is_loopback or parsed.username is not None or parsed.password is not None or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError("CLAY_HERMES_URL must be an HTTP loopback origin with no userinfo, query, fragment, or path.")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.transport = transport or HTTPTransport()
        self._idempotent_runs: dict[str, dict] = {}

    def __repr__(self):
        return f"HermesAPIAdapter(base_url={self.base_url!r}, token='[REDACTED]')"

    def _url(self, path: str) -> str:
        if path not in self._STATIC and not self._DYNAMIC.fullmatch(path):
            raise ValueError("Endpoint is not in the Clay Ops Hermes allowlist.")
        return self.base_url + path

    def _headers(self, idempotency_key=None):
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json", "Accept": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _payload(response):
        status, payload = response
        if isinstance(payload, bytes):
            payload = json.loads(payload or b"{}")
        if isinstance(payload, str) and not payload.startswith("data:"):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass
        if status >= 400:
            raise RuntimeError(f"Hermes API request failed with HTTP {status}.")
        return payload

    def _request(self, method, path, body=None, *, stream=False, idempotency_key=None):
        try:
            return self._payload(self.transport.request(method, self._url(path), headers=self._headers(idempotency_key), json_body=body, stream=stream))
        except HermesOffline:
            raise
        except (OSError, TimeoutError, urllib.error.URLError):
            raise HermesOffline("Hermes API is offline or unreachable.") from None
        except Exception as exc:
            message = str(exc).replace(self._token, "[REDACTED]")
            if "HTTP" in message:
                raise RuntimeError(message) from None
            raise HermesOffline("Hermes API is offline or unreachable.") from None

    def capabilities(self) -> dict:
        payload = self._request("GET", "/v1/capabilities")
        if not isinstance(payload, dict):
            raise HermesOffline("Hermes capabilities response was invalid.")
        return payload

    def _require(self, *names: str):
        caps = self.capabilities()
        raw_features = caps.get("features", [])
        if isinstance(raw_features, dict):
            features = {name for name, enabled in raw_features.items() if enabled is True}
        else:
            features = set(raw_features or [])
        endpoints = caps.get("endpoints", {})
        if not any(name in features or name in endpoints for name in names):
            raise CapabilityMismatch(f"Hermes capability unavailable: {names[0]}")
        return caps

    def create_run(self, input_text: str, *, idempotency_key: str, session_id=None, instructions=None, conversation_history=None, previous_response_id=None, model=None, provider=None, model_options=None):
        if idempotency_key in self._idempotent_runs:
            return self._idempotent_runs[idempotency_key]
        self._require("run_submission", "runs")
        body: dict[str, Any] = {"input": input_text, "metadata": {"source": "structured"}}
        for key, value in {"session_id": session_id, "instructions": instructions, "conversation_history": conversation_history, "previous_response_id": previous_response_id, "model": model, "provider": provider, "model_options": model_options}.items():
            if value is not None:
                body[key] = value
        result = self._request("POST", "/v1/runs", body, idempotency_key=idempotency_key)
        if not isinstance(result, dict) or not result.get("run_id"):
            raise HermesOffline("Hermes returned no structured run identifier.")
        result = {**result, "execution_mode": "structured"}
        self._idempotent_runs[idempotency_key] = result
        return result

    def create_demo_run(self, input_text: str, *, idempotency_key: str) -> dict:
        """Submit only when Hermes advertises enforceable per-run toolset constraints."""
        caps = self._require("run_submission", "runs")
        raw_features = caps.get("features", {})
        supported = raw_features.get("run_toolset_constraints") is True if isinstance(raw_features, dict) else "run_toolset_constraints" in raw_features
        if not supported:
            raise CapabilityMismatch("Hermes capability unavailable: run_toolset_constraints")
        if idempotency_key in self._idempotent_runs:
            return self._idempotent_runs[idempotency_key]
        body = {"input": input_text, "metadata": {"source": "structured", "policy": "clay-hq-local-no-tools"}, "enabled_toolsets": []}
        result = self._request("POST", "/v1/runs", body, idempotency_key=idempotency_key)
        if not isinstance(result, dict) or not result.get("run_id"):
            raise HermesOffline("Hermes returned no structured run identifier.")
        result = {**result, "execution_mode": "structured"}
        self._idempotent_runs[idempotency_key] = result
        return result

    def get_run(self, run_id: str) -> dict:
        try:
            self._require("run_status")
            result = self._request("GET", f"/v1/runs/{run_id}")
            return {**result, "execution_mode": "structured"}
        except HermesOffline:
            return {"run_id": run_id, "status": "degraded", "execution_mode": "structured", "reason": "Hermes disconnected; no activity was fabricated."}

    def get_run_events(self, run_id: str):
        self._require("run_events_sse", "run_events")
        return self._request("GET", f"/v1/runs/{run_id}/events", stream=True)

    def resolve_run_approval(self, run_id: str, approve: bool) -> dict:
        self._require("run_approval_response", "run_approval", "run_approval_response")
        return self._request("POST", f"/v1/runs/{run_id}/approval", {"choice": "once" if approve else "deny"})

    def stop_run(self, run_id: str) -> dict:
        self._require("run_stop")
        return self._request("POST", f"/v1/runs/{run_id}/stop", {})

    def list_sessions(self, *, limit=50, offset=0) -> dict:
        self._require("session_resources", "session_list", "sessions")
        return self._request("GET", f"/api/sessions")

    def get_session(self, session_id: str) -> dict:
        self._require("session_resources", "session_read", "session")
        return self._request("GET", f"/api/sessions/{session_id}")

    def get_session_messages(self, session_id: str) -> dict:
        self._require("session_resources", "session_read", "session_messages")
        return self._request("GET", f"/api/sessions/{session_id}/messages")

    @staticmethod
    def classify_existing_session(session: dict) -> dict:
        return {**session, "execution_mode": session.get("execution_mode", "manual/unstructured")}
