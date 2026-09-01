"""Clay team access.

A Clay-specific authorization layer, deliberately separate from the ordinary
approval policy in ``policies/approval-policy.json``. That policy governs what
*Clay Ops itself* may do to a work product. This one governs *which human may
ask for it, over which surface*, and who has to approve when the asker does
not carry the authority themselves.

Every mapping lives in ``config/team-access.json``. Nothing in this module
encodes a person, a role, a Slack id, or an approver.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ContractError

SCHEMA_VERSION = "1.0.0"

ALLOW = "allow"
DENY = "deny"
NEEDS_APPROVAL = "needs_approval"

SURFACES = ("dm", "channel", "thread")


class TeamAccessError(ContractError):
    pass


@dataclass(frozen=True)
class Person:
    key: str
    display_name: str
    role: str
    slack_user_id: str
    email: str


@dataclass(frozen=True)
class AccessDecision:
    """The result of one authorization question.

    ``outcome`` is one of ``allow`` / ``deny`` / ``needs_approval``. A
    ``needs_approval`` outcome is not a refusal: the reversible part of the
    request still proceeds, and ``approvers`` names who can clear the rest.
    """

    capability: str
    outcome: str
    code: str
    message: str
    person: str | None = None
    approvers: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.outcome == ALLOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "outcome": self.outcome,
            "code": self.code,
            "message": self.message,
            "person": self.person,
            "approvers": list(self.approvers),
        }


class TeamAccess:
    def __init__(self, path: Path):
        self.path = Path(path)
        try:
            self.document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TeamAccessError([{"code": "TEAM_ACCESS_UNAVAILABLE", "message": str(exc)}]) from None
        if self.document.get("schema_version") != SCHEMA_VERSION:
            raise TeamAccessError([{"code": "SCHEMA_VERSION_MISMATCH", "message": f"Expected {SCHEMA_VERSION}."}])

        self.capabilities: dict[str, dict] = self.document.get("capabilities", {})
        self.roles: dict[str, dict] = self.document.get("roles", {})
        self.approvers: dict[str, list[str]] = self.document.get("approvers", {})
        self.approver_notes: dict[str, str] = self.document.get("approver_notes", {})
        self.conversation: dict[str, Any] = self.document.get("conversation", {})
        self.front_door: dict[str, Any] = self.document.get("front_door", {})

        self._people: dict[str, Person] = {}
        self._by_slack: dict[str, Person] = {}
        for entry in self.document.get("people", []):
            role = entry.get("role")
            if role not in self.roles:
                raise TeamAccessError([{"code": "UNKNOWN_ROLE", "message": f"{entry.get('key')} has unregistered role {role!r}."}])
            person = Person(
                key=str(entry["key"]),
                display_name=str(entry.get("display_name", entry["key"])),
                role=str(role),
                slack_user_id=str(entry.get("slack_user_id", "")).strip(),
                email=str(entry.get("email", "")),
            )
            self._people[person.key] = person
            if person.slack_user_id:
                self._by_slack[person.slack_user_id] = person

        for capability, names in self.approvers.items():
            if capability not in self.capabilities:
                raise TeamAccessError([{"code": "UNKNOWN_CAPABILITY", "message": f"Approver mapping for unregistered capability {capability!r}."}])
            for name in names:
                if name not in self._people:
                    raise TeamAccessError([{"code": "UNKNOWN_APPROVER", "message": f"Approver {name!r} is not a registered person."}])

        for role_name, role in self.roles.items():
            for capability in role.get("grants", []):
                if capability not in self.capabilities:
                    raise TeamAccessError([{"code": "UNKNOWN_CAPABILITY", "message": f"Role {role_name!r} grants unregistered capability {capability!r}."}])
            for surface in role.get("surfaces", []):
                if surface not in SURFACES:
                    raise TeamAccessError([{"code": "UNKNOWN_SURFACE", "message": f"Role {role_name!r} allows unregistered surface {surface!r}."}])

    # ── identity ───────────────────────────────────────────────────────────

    def person_by_slack_id(self, slack_user_id: str) -> Person | None:
        return self._by_slack.get(str(slack_user_id or "").strip())

    def person(self, key: str) -> Person | None:
        return self._people.get(key)

    def people(self) -> list[Person]:
        return list(self._people.values())

    def allowed_slack_user_ids(self) -> list[str]:
        return [p.slack_user_id for p in self._people.values() if p.slack_user_id]

    # ── surfaces ───────────────────────────────────────────────────────────

    def channels(self) -> list[dict]:
        return list(self.document.get("surfaces", {}).get("channels", []))

    def enabled_channels(self) -> list[dict]:
        return [c for c in self.channels() if c.get("enabled") and str(c.get("slack_channel_id", "")).strip()]

    def allowed_channel_ids(self) -> list[str]:
        return [str(c["slack_channel_id"]).strip() for c in self.enabled_channels()]

    def mention_required_channel_ids(self) -> list[str]:
        return [str(c["slack_channel_id"]).strip() for c in self.enabled_channels() if c.get("requires_mention")]

    def free_response_channel_ids(self) -> list[str]:
        return [str(c["slack_channel_id"]).strip() for c in self.enabled_channels() if not c.get("requires_mention")]

    def admits_surface(self, person: Person, surface: str, channel_id: str | None = None) -> AccessDecision | None:
        """Return a denial when the surface is not open to ``person``, else None."""
        if surface not in SURFACES:
            return AccessDecision("*", DENY, "UNKNOWN_SURFACE", f"Unregistered surface {surface!r}.", person.key)
        if surface not in self.roles[person.role].get("surfaces", []):
            return AccessDecision("*", DENY, "SURFACE_NOT_ALLOWED", f"{person.display_name} may not reach NORTH over {surface}.", person.key)
        if surface == "dm" and not self.document.get("surfaces", {}).get("dm", {}).get("enabled", False):
            return AccessDecision("*", DENY, "SURFACE_DISABLED", "Direct messages with NORTH are disabled.", person.key)
        if surface in {"channel", "thread"} and channel_id is not None:
            if str(channel_id).strip() not in self.allowed_channel_ids():
                return AccessDecision("*", DENY, "CHANNEL_NOT_APPROVED", "NORTH does not work in this channel.", person.key)
        return None

    # ── authorization ──────────────────────────────────────────────────────

    def decide(
        self,
        slack_user_id: str,
        capability: str,
        *,
        surface: str = "dm",
        channel_id: str | None = None,
    ) -> AccessDecision:
        person = self.person_by_slack_id(slack_user_id)
        if person is None:
            return AccessDecision(
                capability, DENY, "UNKNOWN_REQUESTER",
                "Not a registered Clay team member.",
            )

        blocked = self.admits_surface(person, surface, channel_id)
        if blocked is not None:
            return AccessDecision(capability, DENY, blocked.code, blocked.message, person.key)

        if capability not in self.capabilities:
            return AccessDecision(
                capability, DENY, "CAPABILITY_UNKNOWN",
                f"Unregistered capability {capability!r}. Default deny.",
                person.key,
            )

        if capability in self.roles[person.role].get("grants", []):
            return AccessDecision(capability, ALLOW, "GRANTED", self.capabilities[capability]["label"], person.key)

        approvers = tuple(self.approvers.get(capability, ()))
        if not approvers:
            return AccessDecision(
                capability, DENY, "NO_APPROVER_AVAILABLE",
                self.approver_notes.get(capability, f"No approver is defined for {capability!r}."),
                person.key,
            )

        return AccessDecision(
            capability, NEEDS_APPROVAL, "APPROVAL_REQUIRED",
            f"{self.capabilities[capability]['label']} requires approval.",
            person.key, approvers,
        )

    def approver_names(self, capability: str) -> list[str]:
        return [self._people[k].display_name for k in self.approvers.get(capability, []) if k in self._people]


def slack_gateway_settings(access):
    """Derive the NORTH Slack gateway settings from config/team-access.json.

    The gateway never gets its own copy of the roster. Everything below is a
    projection of the one config file, so editing that file and re-syncing is
    the only way access changes.
    """
    threading = access.document.get("surfaces", {}).get("threading", {})
    return {
        "platform": "slack",
        "transport": "socket_mode",
        "public_inbound_port": False,
        "config_yaml": {
            "platforms": {
                "slack": {
                    "enabled": True,
                    "reply_to_mode": "first",
                    "gateway_restart_notification": False,
                    "typing_status_text": "NORTH is working",
                    "extra": {
                        "allowed_channels": access.allowed_channel_ids(),
                        "require_mention": True,
                        "require_mention_channels": access.mention_required_channel_ids(),
                        "free_response_channels": access.free_response_channel_ids(),
                        "thread_require_mention": bool(threading.get("thread_requires_mention", False)),
                        "ignore_other_user_mentions": True,
                        "disable_dms": not access.document.get("surfaces", {}).get("dm", {}).get("enabled", False),
                    },
                }
            },
            "unauthorized_dm_behavior": access.document.get("unknown_user_behavior", "ignore"),
            "group_sessions_per_user": True,
            "thread_sessions_per_user": True,
        },
        "env": {
            # The roster. Slack is a built-in platform, so its per-user
            # allowlist is only ever read from the environment, never from
            # config.yaml. Default-deny: an id that is not here is ignored.
            "SLACK_ALLOWED_USERS": ",".join(access.allowed_slack_user_ids()),
            # `hermes config set` coerces the literal string "none" to YAML
            # null, so this control cannot be stated exactly in config.yaml.
            # It is exact here, and the adapter default is "none" either way.
            "SLACK_ALLOW_BOTS": "none",
        },
        "secrets_required": ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"],
    }
