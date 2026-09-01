"""Clay work items.

One Slack request becomes one work item. The work item is what makes NORTH a
chief of staff rather than a chat box: it remembers who asked, where they
asked, what they wanted, which specialists touched it, and what NORTH owes
them back.

Nothing here renders a specialist transcript. The only thing that reaches
Slack is the synthesized NORTH reply built by :func:`render_reply`.
"""

from __future__ import annotations

import uuid
from typing import Any, Iterable

from .team_access import ALLOW, DENY, NEEDS_APPROVAL, AccessDecision, TeamAccess
from .store import OperationalStore

RECEIVED = "received"
ACKNOWLEDGED = "acknowledged"
IN_PROGRESS = "in_progress"
DONE = "done"
READY_FOR_REVIEW = "ready_for_review"
NEEDS_DECISION = "needs_decision"
BLOCKED = "blocked"

TERMINAL = {DONE, READY_FOR_REVIEW, NEEDS_DECISION, BLOCKED}

HEADLINES = {
    DONE: "DONE",
    READY_FOR_REVIEW: "READY FOR REVIEW",
    NEEDS_DECISION: "NEEDS YOUR DECISION",
    BLOCKED: "BLOCKED",
}


class WorkItemError(RuntimeError):
    pass


def render_reply(
    state: str,
    summary: str,
    *,
    artifacts: Iterable[str] = (),
    decisions: Iterable[str] = (),
    next_steps: Iterable[str] = (),
) -> str:
    """Build the one message NORTH sends back into the thread.

    Deliberately narrow: a headline, a synthesis, links, and open decisions.
    There is no parameter for internal chatter because internal chatter never
    ships.
    """
    if state not in HEADLINES:
        raise WorkItemError(f"{state!r} is not a terminal state.")
    lines = [HEADLINES[state], "", str(summary).strip()]
    artifacts = [a for a in artifacts if str(a).strip()]
    decisions = [d for d in decisions if str(d).strip()]
    next_steps = [n for n in next_steps if str(n).strip()]
    if artifacts:
        lines += ["", "Links"] + [f"- {a}" for a in artifacts]
    if decisions:
        lines += ["", "Decisions needed"] + [f"- {d}" for d in decisions]
    if next_steps:
        lines += ["", "NEXT"] + [f"- {n}" for n in next_steps]
    return "\n".join(lines).strip()


class WorkItemLedger:
    def __init__(self, access: TeamAccess, store: OperationalStore):
        self.access = access
        self.store = store

    # ── intake ─────────────────────────────────────────────────────────────

    def receive(
        self,
        *,
        slack_user_id: str,
        text: str,
        surface: str = "dm",
        channel_id: str = "",
        thread_id: str = "",
        capability: str = "ask",
    ) -> dict[str, Any]:
        """Admit or refuse one inbound Slack message.

        Returns a dict with ``admitted``. When admitted and the message
        continues an existing thread, ``work_item_id`` points at the original
        item and ``continuation`` is True, so one task stays one task.
        """
        decision = self.access.decide(slack_user_id, capability, surface=surface, channel_id=channel_id)

        if decision.outcome == DENY and decision.code in {"UNKNOWN_REQUESTER", "SURFACE_NOT_ALLOWED", "SURFACE_DISABLED", "CHANNEL_NOT_APPROVED"}:
            # No work item, no ledger entry, no reply. An unregistered sender
            # never learns that NORTH is listening.
            return {"admitted": False, "decision": decision.to_dict(), "reply": None, "work_item_id": None}

        person = self.access.person(decision.person) if decision.person else None
        if person is None:
            return {"admitted": False, "decision": decision.to_dict(), "reply": None, "work_item_id": None}

        existing = self.store.find_work_item_by_thread(channel_id, thread_id)
        if existing is not None:
            self.store.append_work_item_event(
                existing["work_item_id"], "follow_up", existing["status"],
                {"requester": person.key, "surface": surface, "capability": capability},
                actor=f"slack:{person.key}",
            )
            return {
                "admitted": True, "continuation": True,
                "work_item_id": existing["work_item_id"],
                "decision": decision.to_dict(),
                "reply": None,
                "requester": person.key,
            }

        work_item_id = f"work-{uuid.uuid4().hex[:12]}"
        document = {
            "schema_version": "1.0.0",
            "requester": person.key,
            "requester_display_name": person.display_name,
            "requester_slack_id": person.slack_user_id,
            "surface": surface,
            "channel_id": channel_id,
            "thread_id": thread_id,
            "requested_outcome": str(text).strip(),
            "capability": capability,
            "specialists": [],
            "artifacts": [],
            "decisions_required": [],
            "approval": None,
        }
        self.store.create_work_item(
            work_item_id, person.key, person.slack_user_id, surface,
            channel_id, thread_id, text, document, status=RECEIVED,
        )
        self.store.append_work_item_event(
            work_item_id, "received", RECEIVED,
            {"requester": person.key, "surface": surface, "channel_id": channel_id, "thread_id": thread_id, "capability": capability},
            actor=f"slack:{person.key}",
        )
        return {
            "admitted": True, "continuation": False,
            "work_item_id": work_item_id,
            "decision": decision.to_dict(),
            "reply": None,
            "requester": person.key,
        }

    # ── progress ───────────────────────────────────────────────────────────

    def acknowledge(self, work_item_id: str) -> str:
        """Move to acknowledged and return the immediate Slack reply."""
        self._require(work_item_id)
        message = self.access.conversation.get("acknowledgement", "I'm on it. I'll bring the finished work back here.")
        self.store.set_work_item_status(work_item_id, ACKNOWLEDGED)
        self.store.append_work_item_event(work_item_id, "acknowledged", ACKNOWLEDGED, {"message": message})
        return message

    def delegate(self, work_item_id: str, specialists: Iterable[str]) -> dict[str, Any]:
        """Record which specialists NORTH used. Internal only; never rendered."""
        item = self._require(work_item_id)
        document = item["document"]
        known = set(self.access.front_door.get("specialists", []))
        chosen = [str(s).upper() for s in specialists]
        unknown = [s for s in chosen if s not in known]
        if unknown:
            raise WorkItemError(f"Unregistered specialist(s): {', '.join(unknown)}")
        document["specialists"] = sorted(set(document.get("specialists", [])) | set(chosen))
        self.store.set_work_item_status(work_item_id, IN_PROGRESS, document)
        self.store.append_work_item_event(work_item_id, "delegated", IN_PROGRESS, {"specialists": chosen})
        return document

    def check(self, work_item_id: str, capability: str) -> AccessDecision:
        """Ask whether the requester carries the authority for ``capability``."""
        item = self._require(work_item_id)
        return self.access.decide(
            item["requester_slack_id"], capability,
            surface=item["surface"], channel_id=item["channel_id"],
        )

    # ── completion ─────────────────────────────────────────────────────────

    def complete(
        self,
        work_item_id: str,
        state: str,
        summary: str,
        *,
        artifacts: Iterable[str] = (),
        decisions: Iterable[str] = (),
        next_steps: Iterable[str] = (),
    ) -> dict[str, Any]:
        item = self._require(work_item_id)
        if state not in TERMINAL:
            raise WorkItemError(f"{state!r} is not a terminal state.")
        document = item["document"]
        document["artifacts"] = list(artifacts)
        document["decisions_required"] = list(decisions)
        reply = render_reply(state, summary, artifacts=artifacts, decisions=decisions, next_steps=next_steps)
        self.store.set_work_item_status(work_item_id, state, document)
        self.store.append_work_item_event(work_item_id, "completed", state, {"summary": summary, "artifacts": list(artifacts)})
        return {
            "work_item_id": work_item_id,
            "state": state,
            "reply": reply,
            "channel_id": item["channel_id"],
            "thread_id": item["thread_id"],
            "requester": item["requester"],
        }

    def complete_with_approval_gate(
        self,
        work_item_id: str,
        capability: str,
        summary: str,
        *,
        artifacts: Iterable[str] = (),
        next_steps: Iterable[str] = (),
    ) -> dict[str, Any]:
        """Finish everything reversible, then name the approver for the rest.

        The useful work is never thrown away because the asker lacks the
        authority for the final step.
        """
        decision = self.check(work_item_id, capability)
        item = self._require(work_item_id)
        document = item["document"]
        document["approval"] = decision.to_dict()

        if decision.outcome == ALLOW:
            self.store.set_work_item_status(work_item_id, item["status"], document)
            return self.complete(work_item_id, READY_FOR_REVIEW, summary, artifacts=artifacts, next_steps=next_steps)

        label = self.access.capabilities.get(capability, {}).get("label", capability)

        if decision.outcome == NEEDS_APPROVAL:
            approvers = self.access.approver_names(capability)
            joined = " or ".join(approvers) if approvers else "an approver"
            gate = f"Ready. This last step requires approval from {joined}."
            self.store.set_work_item_status(work_item_id, NEEDS_DECISION, document)
            self.store.append_work_item_event(work_item_id, "approval_required", NEEDS_DECISION, {"capability": capability, "approvers": list(decision.approvers)})
            return self.complete(
                work_item_id, NEEDS_DECISION, f"{summary}\n\n{gate}",
                artifacts=artifacts, decisions=[f"{label}: {joined}"], next_steps=next_steps,
            )

        self.store.set_work_item_status(work_item_id, BLOCKED, document)
        self.store.append_work_item_event(work_item_id, "blocked", BLOCKED, {"capability": capability, "code": decision.code})
        return self.complete(
            work_item_id, BLOCKED, f"{summary}\n\n{decision.message}",
            artifacts=artifacts, next_steps=next_steps,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _require(self, work_item_id: str) -> dict[str, Any]:
        item = self.store.get_work_item(work_item_id)
        if item is None:
            raise WorkItemError(f"Unknown work item {work_item_id!r}.")
        return item
