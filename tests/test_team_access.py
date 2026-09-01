"""The eight team-access scenarios, driven end to end against the real
config file and a real (temporary) operational store.

Nothing here mocks the authorization layer. The only thing standing in for
Slack is the event payload.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clay_ops.store import OperationalStore
from clay_ops.team_access import TeamAccess
from clay_ops.work_items import (
    BLOCKED,
    DONE,
    NEEDS_DECISION,
    READY_FOR_REVIEW,
    WorkItemLedger,
    render_reply,
)

RYAN = "U0BH7234V9R"
ALEX = "U0BJ6DUR2RF"
JUSTIN = "U0BHA0L3C85"
DEVEN = "U0BHB9CDL22"
STRANGER = "U0NOTATEAMMEMBER"
CLAY_STUDIOS = "C0BH6TA333M"


@pytest.fixture
def access(repo_root) -> TeamAccess:
    return TeamAccess(repo_root / "config/team-access.json")


@pytest.fixture
def ledger(access, tmp_path) -> WorkItemLedger:
    return WorkItemLedger(access, OperationalStore(tmp_path / "clay-ops.sqlite3"))


# ── 1. Ryan asks a broad project question ──────────────────────────────────

def test_ryan_broad_project_question(ledger):
    intake = ledger.receive(
        slack_user_id=RYAN, text="Where does the JoinClay landing page actually stand?",
        surface="dm", channel_id="D0RYAN", thread_id="1756700000.000100",
    )
    assert intake["admitted"] is True
    assert intake["requester"] == "ryan"

    assert ledger.acknowledge(intake["work_item_id"]) == "I'm on it. I'll bring the finished work back here."
    ledger.delegate(intake["work_item_id"], ["SIGNAL", "FIELD", "PROOF"])

    result = ledger.complete(
        intake["work_item_id"], DONE,
        "The landing page is on a review branch and has not merged.",
        artifacts=["https://github.com/claylife/clay-engine/tree/review/instrument-brand-delta-2026-08-26"],
    )
    assert result["reply"].startswith("DONE")
    assert result["requester"] == "ryan"
    # One coherent answer. No specialist ever appears in what Slack receives.
    for specialist in ("SIGNAL", "FIELD", "PROOF"):
        assert specialist not in result["reply"]


# ── 2. Alex requests a product/design change ───────────────────────────────

def test_alex_requests_design_change(ledger):
    intake = ledger.receive(
        slack_user_id=ALEX, text="Can we tighten the spacing on the purchase flow?",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700100.000200",
        capability="request_work",
    )
    assert intake["admitted"] is True
    assert intake["requester"] == "alex"
    assert intake["decision"]["outcome"] == "allow"

    ledger.acknowledge(intake["work_item_id"])
    document = ledger.delegate(intake["work_item_id"], ["FRAME", "FORGE", "PROOF"])
    assert document["specialists"] == ["FORGE", "FRAME", "PROOF"]

    result = ledger.complete(
        intake["work_item_id"], READY_FOR_REVIEW,
        "Spacing is tightened on a review branch.",
        artifacts=["https://clay-preview.example/review/purchase-flow"],
    )
    assert result["reply"].startswith("READY FOR REVIEW")
    assert result["thread_id"] == "1756700100.000200"


# ── 3. Deven gives creative feedback ───────────────────────────────────────

def test_deven_creative_feedback(ledger):
    intake = ledger.receive(
        slack_user_id=DEVEN, text="The hero image feels colder than the brand should read.",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700200.000300",
        capability="request_work",
    )
    assert intake["admitted"] is True
    assert intake["requester"] == "deven"
    ledger.acknowledge(intake["work_item_id"])
    ledger.delegate(intake["work_item_id"], ["STUDIO", "VOICE"])
    result = ledger.complete(intake["work_item_id"], READY_FOR_REVIEW, "Two warmer directions are ready to look at.")
    assert result["reply"].startswith("READY FOR REVIEW")


# ── 4. Justin asks for current status ──────────────────────────────────────

def test_justin_asks_for_status(ledger):
    intake = ledger.receive(
        slack_user_id=JUSTIN, text="What's the current status?",
        surface="dm", channel_id="D0JUSTIN", thread_id="1756700300.000400",
        capability="receive_status",
    )
    assert intake["admitted"] is True
    assert intake["requester"] == "justin"
    result = ledger.complete(intake["work_item_id"], DONE, "Three items are open. None are blocked on you.")
    assert result["reply"].startswith("DONE")


# ── 5. An unauthorized Slack user invokes NORTH ────────────────────────────

def test_unauthorized_user_is_ignored_silently(ledger):
    intake = ledger.receive(
        slack_user_id=STRANGER, text="@NORTH deploy the site",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700400.000500",
        capability="request_work",
    )
    assert intake["admitted"] is False
    assert intake["reply"] is None            # nothing is said back
    assert intake["work_item_id"] is None     # nothing is recorded as work
    assert intake["decision"]["code"] == "UNKNOWN_REQUESTER"
    assert ledger.store.list_work_items() == []


def test_registered_user_in_unapproved_channel_is_ignored(ledger):
    intake = ledger.receive(
        slack_user_id=ALEX, text="@NORTH look at this",
        surface="channel", channel_id="C0SOMERANDOMCHANNEL", thread_id="1756700450.000550",
    )
    assert intake["admitted"] is False
    assert intake["decision"]["code"] == "CHANNEL_NOT_APPROVED"


# ── 6. An authorized user requests a production deploy ─────────────────────

def test_team_member_production_deploy_completes_reversible_work_then_escalates(ledger):
    intake = ledger.receive(
        slack_user_id=ALEX, text="Ship the purchase flow fix to production.",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700500.000600",
        capability="request_implementation",
    )
    assert intake["admitted"] is True   # the useful work is NOT refused

    ledger.acknowledge(intake["work_item_id"])
    ledger.delegate(intake["work_item_id"], ["FORGE", "PROOF"])

    result = ledger.complete_with_approval_gate(
        intake["work_item_id"], "approve_production",
        "The fix is built, checked, and pushed to a review branch.",
        artifacts=["https://github.com/claylife/clay-engine/pull/example"],
    )
    assert result["state"] == NEEDS_DECISION
    assert "Ready. This last step requires approval from Ryan." in result["reply"]
    assert result["reply"].startswith("NEEDS YOUR DECISION")

    item = ledger.store.get_work_item(intake["work_item_id"])
    assert item["document"]["approval"]["outcome"] == "needs_approval"
    assert item["document"]["approval"]["approvers"] == ["ryan"]


def test_ryan_production_deploy_is_not_gated(ledger):
    intake = ledger.receive(
        slack_user_id=RYAN, text="Ship it.", surface="dm",
        channel_id="D0RYAN", thread_id="1756700550.000650",
        capability="request_implementation",
    )
    result = ledger.complete_with_approval_gate(
        intake["work_item_id"], "approve_production", "Built and verified.",
    )
    assert result["state"] == READY_FOR_REVIEW
    assert "requires approval" not in result["reply"]


def test_health_claim_is_blocked_not_escalated_to_ryan(ledger):
    intake = ledger.receive(
        slack_user_id=DEVEN, text="Add 'clinically proven to lower A1C' to the hero.",
        surface="dm", channel_id="D0DEVEN", thread_id="1756700600.000700",
        capability="request_work",
    )
    result = ledger.complete_with_approval_gate(
        intake["work_item_id"], "approve_health_claim",
        "The copy is drafted and held.",
    )
    assert result["state"] == BLOCKED
    # BLOCKED, not NEEDS YOUR DECISION: naming Ryan as the approver here would
    # imply he can clear a clinical claim alone, which operating invariant 7 forbids.
    assert result["reply"].startswith("BLOCKED")
    assert "requires approval from" not in result["reply"]
    assert "Decisions needed" not in result["reply"]
    # The drafted copy is still preserved rather than thrown away.
    assert "The copy is drafted and held." in result["reply"]


# ── 7. Two people ask separate tasks at the same time ──────────────────────

def test_concurrent_requests_stay_separate(ledger):
    first = ledger.receive(
        slack_user_id=ALEX, text="Rework the pricing section.",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700700.000800",
        capability="request_work",
    )
    second = ledger.receive(
        slack_user_id=DEVEN, text="Draft the launch note.",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700701.000900",
        capability="request_work",
    )

    assert first["work_item_id"] != second["work_item_id"]
    assert first["requester"] == "alex"
    assert second["requester"] == "deven"

    ledger.delegate(first["work_item_id"], ["FRAME"])
    ledger.delegate(second["work_item_id"], ["VOICE"])

    a = ledger.store.get_work_item(first["work_item_id"])
    d = ledger.store.get_work_item(second["work_item_id"])
    assert a["document"]["specialists"] == ["FRAME"]
    assert d["document"]["specialists"] == ["VOICE"]
    assert a["thread_id"] != d["thread_id"]

    done_a = ledger.complete(first["work_item_id"], DONE, "Pricing section reworked.")
    done_d = ledger.complete(second["work_item_id"], DONE, "Launch note drafted.")
    assert done_a["thread_id"] == "1756700700.000800"
    assert done_d["thread_id"] == "1756700701.000900"
    assert len(ledger.store.list_work_items()) == 2
    assert len(ledger.store.list_work_items(requester="alex")) == 1


# ── 8. A follow-up lands inside the original thread ────────────────────────

def test_follow_up_in_thread_continues_the_same_work_item(ledger):
    intake = ledger.receive(
        slack_user_id=ALEX, text="Rework the pricing section.",
        surface="channel", channel_id=CLAY_STUDIOS, thread_id="1756700800.001000",
        capability="request_work",
    )
    follow_up = ledger.receive(
        slack_user_id=ALEX, text="Actually make the middle tier the default.",
        surface="thread", channel_id=CLAY_STUDIOS, thread_id="1756700800.001000",
        capability="request_work",
    )
    assert follow_up["continuation"] is True
    assert follow_up["work_item_id"] == intake["work_item_id"]
    assert len(ledger.store.list_work_items()) == 1

    events = ledger.store.list_work_item_events(intake["work_item_id"])
    assert [e["event_type"] for e in events] == ["received", "follow_up"]
    assert events[1]["previous_hash"] == events[0]["record_hash"]


def test_top_level_message_never_joins_an_older_work_item(ledger):
    ledger.receive(
        slack_user_id=ALEX, text="First ask.", surface="channel",
        channel_id=CLAY_STUDIOS, thread_id="1756700900.001100", capability="request_work",
    )
    fresh = ledger.receive(
        slack_user_id=ALEX, text="Unrelated second ask.", surface="channel",
        channel_id=CLAY_STUDIOS, thread_id="", capability="request_work",
    )
    assert fresh.get("continuation") is False
    assert len(ledger.store.list_work_items()) == 2


# ── Cross-cutting guarantees ───────────────────────────────────────────────

def test_specialists_are_never_named_in_a_slack_reply(ledger, access):
    intake = ledger.receive(
        slack_user_id=JUSTIN, text="Status?", surface="dm",
        channel_id="D0JUSTIN", thread_id="1756701000.001200", capability="receive_status",
    )
    ledger.delegate(intake["work_item_id"], access.front_door["specialists"])
    reply = ledger.complete(intake["work_item_id"], DONE, "Everything reversible is moving.")["reply"]
    for specialist in access.front_door["specialists"]:
        assert specialist not in reply


def test_forbidden_vocabulary_never_appears_in_a_reply(access):
    reply = render_reply(DONE, "The work is finished.", artifacts=["https://example/preview"])
    lowered = reply.lower()
    for word in access.conversation["never_expose"]:
        assert word.lower() not in lowered


def test_every_work_item_records_the_full_provenance(ledger):
    intake = ledger.receive(
        slack_user_id=DEVEN, text="Refresh the brand deck.", surface="channel",
        channel_id=CLAY_STUDIOS, thread_id="1756701100.001300", capability="request_work",
    )
    ledger.delegate(intake["work_item_id"], ["PAPER", "STUDIO"])
    ledger.complete(
        intake["work_item_id"], READY_FOR_REVIEW, "Deck refreshed.",
        artifacts=["https://example/deck.pdf"], decisions=["Confirm the cover claim"],
    )
    item = ledger.store.get_work_item(intake["work_item_id"])
    document = item["document"]
    assert document["requester"] == "deven"
    assert item["channel_id"] == CLAY_STUDIOS and item["thread_id"] == "1756701100.001300"
    assert document["requested_outcome"] == "Refresh the brand deck."
    assert document["specialists"] == ["PAPER", "STUDIO"]
    assert item["status"] == READY_FOR_REVIEW
    assert document["artifacts"] == ["https://example/deck.pdf"]
    assert document["decisions_required"] == ["Confirm the cover claim"]


def test_work_item_history_is_append_only(ledger):
    from clay_ops.store import ImmutableRecordError

    intake = ledger.receive(
        slack_user_id=ALEX, text="Anything.", surface="dm",
        channel_id="D0ALEX", thread_id="1756701200.001400",
    )
    events = ledger.store.list_work_item_events(intake["work_item_id"])
    with pytest.raises(ImmutableRecordError):
        ledger.store._execute(
            "UPDATE work_item_events SET status=? WHERE work_item_event_id=?",
            ("tampered", events[0]["work_item_event_id"]),
        )
    with pytest.raises(ImmutableRecordError):
        ledger.store._execute(
            "DELETE FROM work_item_events WHERE work_item_event_id=?",
            (events[0]["work_item_event_id"],),
        )


def test_unregistered_specialist_is_rejected(ledger):
    intake = ledger.receive(
        slack_user_id=ALEX, text="Anything.", surface="dm",
        channel_id="D0ALEX", thread_id="1756701300.001500",
    )
    from clay_ops.work_items import WorkItemError

    with pytest.raises(WorkItemError):
        ledger.delegate(intake["work_item_id"], ["HERMES"])


def test_front_door_opens_no_public_inbound_port(access):
    assert access.front_door["transport"] == "slack-socket-mode"
    assert access.front_door["public_inbound_port"] is False
    assert access.front_door["specialists_slack_visible"] is False
    assert access.front_door["bot"] == "NORTH"


def test_only_north_is_a_slack_surface(access):
    """The eight specialists are internal. None of them is a Slack identity."""
    slack_identities = {p.slack_user_id for p in access.people()}
    assert len(slack_identities) == 4
    assert access.front_door["specialists"] == ["FIELD", "FRAME", "STUDIO", "FORGE", "PROOF", "PAPER", "VOICE", "SIGNAL"]


def test_team_members_hold_no_dangerous_authority(access):
    dangerous = ["approve_production", "approve_publish_send", "change_permissions", "credential_access", "authorize_spend", "destructive"]
    for person in access.people():
        if person.role == "operator":
            continue
        for capability in dangerous:
            decision = access.decide(person.slack_user_id, capability, surface="dm")
            assert decision.outcome != "allow", f"{person.key} must not hold {capability}"


def test_ryan_retains_operator_authority(access):
    for capability in ["approve_production", "approve_publish_send", "change_permissions", "credential_access", "authorize_spend", "destructive"]:
        assert access.decide(RYAN, capability, surface="dm").outcome == "allow"


# ── Gateway derivation ─────────────────────────────────────────────────────

def test_gateway_settings_use_socket_mode_and_no_inbound_port(access):
    from clay_ops.team_access import slack_gateway_settings

    settings = slack_gateway_settings(access)
    assert settings["transport"] == "socket_mode"
    assert settings["public_inbound_port"] is False
    assert set(settings["secrets_required"]) == {"SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"}
    blob = repr(settings).lower()
    for tunnel in ("ngrok", "pinggy", "cloudflare", "tailscale", "request_url", "webhook"):
        assert tunnel not in blob


def test_gateway_allowlist_is_exactly_the_four_registered_people(access):
    from clay_ops.team_access import slack_gateway_settings

    ids = slack_gateway_settings(access)["env"]["SLACK_ALLOWED_USERS"].split(",")
    assert ids == [RYAN, ALEX, JUSTIN, DEVEN]
    assert STRANGER not in ids


def test_gateway_denies_bot_senders(access):
    from clay_ops.team_access import slack_gateway_settings

    # Delivered via env because `hermes config set` coerces "none" to null.
    assert slack_gateway_settings(access)["env"]["SLACK_ALLOW_BOTS"] == "none"


def test_gateway_channels_match_the_config_file(access):
    from clay_ops.team_access import slack_gateway_settings

    extra = slack_gateway_settings(access)["config_yaml"]["platforms"]["slack"]["extra"]
    assert extra["allowed_channels"] == access.allowed_channel_ids()
    assert extra["require_mention"] is True
    # A channel that is not enabled in the config file is not reachable.
    disabled = [c["slack_channel_id"] for c in access.channels() if not c.get("enabled")]
    for channel_id in disabled:
        assert channel_id not in extra["allowed_channels"]


def test_unknown_senders_are_ignored_not_offered_pairing(access):
    from clay_ops.team_access import slack_gateway_settings

    assert slack_gateway_settings(access)["config_yaml"]["unauthorized_dm_behavior"] == "ignore"


def test_sessions_are_separated_per_user_and_thread(access):
    from clay_ops.team_access import slack_gateway_settings

    cfg = slack_gateway_settings(access)["config_yaml"]
    assert cfg["group_sessions_per_user"] is True
    assert cfg["thread_sessions_per_user"] is True


def test_published_manifest_is_socket_mode_and_carries_no_engine_vocabulary(repo_root):
    import json

    manifest_path = repo_root / "integrations/slack/north-app-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["settings"]["socket_mode_enabled"] is True
    assert "request_url" not in json.dumps(manifest)
    assert "slash_commands" not in manifest["features"]
    assert manifest["display_information"]["name"] == "NORTH"
    lowered = json.dumps(manifest).lower()
    for word in ("hermes", "cron", "n8n", "worktree", "mcp", "profile"):
        assert word not in lowered, f"{word!r} leaked into the Slack manifest"


# ── Gateway sync fail-safe ─────────────────────────────────────────────────

def _load_sync_script(repo_root):
    import importlib.util

    path = repo_root / "bin/clay-north-gateway-sync"
    spec = importlib.util.spec_from_loader("clay_north_gateway_sync", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__dict__["__file__"] = str(path)
    source = path.read_text(encoding="utf-8")
    # Skip the __main__ guard; we only want the helpers.
    exec(compile(source.split('if __name__ ==')[0], str(path), "exec"), module.__dict__)
    return module


def test_slack_is_not_enabled_until_its_tokens_exist(repo_root, tmp_path, monkeypatch, access):
    """Enabling Slack with no token is not harmless.

    The gateway treats a missing SLACK_BOT_TOKEN as a non-retryable startup
    conflict and exits, which also stops the Clay scheduled work NORTH runs.
    The sync must stage the settings and leave Slack off until the secrets
    are present.
    """
    from clay_ops.team_access import slack_gateway_settings

    module = _load_sync_script(repo_root)
    settings = slack_gateway_settings(access)

    profile = tmp_path / "profile"
    profile.mkdir()
    monkeypatch.setattr(module, "PROFILE_HOME", profile)

    # No .env at all.
    ready, missing = module.tokens_present(settings)
    assert ready is False
    assert set(missing) == {"SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"}

    # Template placeholders do not count as configured.
    (profile / ".env").write_text("SLACK_BOT_TOKEN=<paste from the Slack app>\nSLACK_APP_TOKEN=\n")
    ready, missing = module.tokens_present(settings)
    assert ready is False
    assert set(missing) == {"SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"}

    # Both really set.
    (profile / ".env").write_text("SLACK_BOT_TOKEN=xoxb-not-a-real-token\nSLACK_APP_TOKEN=xapp-not-a-real-token\n")
    ready, missing = module.tokens_present(settings)
    assert ready is True
    assert missing == []


def test_gateway_sync_reports_drift(repo_root):
    module = _load_sync_script(repo_root)
    # A YAML block sequence and a JSON list are the same configuration.
    assert module.normalize(["C1", "C2"]) == module.normalize_reported("- C1\n- C2")
    assert module.normalize(True) == module.normalize_reported("True")
    assert module.normalize([]) == module.normalize_reported("")
    # Real drift is still drift.
    assert module.normalize(["C1", "C2"]) != module.normalize_reported("- C1")
    assert module.normalize(True) != module.normalize_reported("False")


def test_channel_surface_without_a_channel_id_is_denied(access):
    """An unidentified channel is not an approved channel.

    Regression: `channel_id is not None` meant a caller that omitted the id
    skipped the allowlist and was granted, inverting default-deny. An empty
    string was correctly denied while `None` was allowed, so the hole was
    reachable only through the one path most likely to be taken by mistake.
    """
    ryan = "U0BH7234V9R"
    for surface in ("channel", "thread"):
        for missing in (None, "", "   "):
            decision = access.decide(ryan, "ask", surface=surface, channel_id=missing)
            assert decision.outcome == "deny", f"{surface} with {missing!r} should deny"
            assert decision.code == "CHANNEL_NOT_APPROVED"

    # The approved channels still work, and DMs are unaffected.
    assert access.decide(ryan, "ask", surface="channel", channel_id="C0BH6TA333M").allowed
    assert access.decide(ryan, "ask", surface="thread", channel_id="C0BH6TA333M").allowed
    assert access.decide(ryan, "ask", surface="dm").allowed


def test_disabled_channel_is_not_reachable(access):
    """#clay-north ships enabled=false with an empty id and must stay closed."""
    names = {c["name"]: c for c in access.channels()}
    north = names["#clay-north"]
    assert north["enabled"] is False and not north["slack_channel_id"].strip()
    assert "" not in access.allowed_channel_ids()
    assert len(access.allowed_channel_ids()) == 2
