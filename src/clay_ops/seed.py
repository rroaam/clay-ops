"""Idempotent demo seed for Clay HQ.

Seeded on every `clay-ops serve` startup. Safe to re-run — every record is
keyed on a deterministic ID so duplicates are skipped rather than rewritten.

Nothing here fabricates an execution, a provider connection, or a result.
Each record is either (a) a truthful brief / description of an actual
workspace, or (b) a real saved draft / pending approval tied to the local
loopback only. Every seeded approval stays `pending` and every seeded
generation draft stays un-submitted — that is the truthful demo state.
"""
from __future__ import annotations

from .store import OperationalStore, utc_now

CLAY_PROJECTS = [
    {
        "schema_version": "1.0.0",
        "project_id": "project-clay-image-system",
        "name": "Clay Image System",
        "brief": (
            "Deterministic local image-generation scaffold: prompt composition, "
            "reference imports, approval gate, provider registry, and archival. "
            "No external provider is configured; the unavailable registry is a "
            "truthful admission, not a demo state."
        ),
        "tags": ["image", "local", "approval-gated"],
    },
    {
        "schema_version": "1.0.0",
        "project_id": "project-clay-landing-page",
        "name": "Clay Landing Page",
        "brief": (
            "Responsive landing-page workflow built on the Clay image-archive "
            "context. Delays execution until both the image provider and a "
            "local website builder report readiness — neither is currently configured."
        ),
        "tags": ["landing", "web", "planned"],
    },
    {
        "schema_version": "1.0.0",
        "project_id": "project-clay-campaign-studio",
        "name": "Clay Campaign Studio",
        "brief": (
            "Campaign-scale creative brief and asset-archive workspace. Reuses "
            "projects, brand contexts, and image requests from the studio; "
            "currently relies on the local loopback only because no external "
            "delivery adapter is configured."
        ),
        "tags": ["campaign", "studio", "planned"],
    },
    {
        "schema_version": "1.0.0",
        "project_id": "project-clay-brand-system",
        "name": "Clay Brand System",
        "brief": (
            "Design tokens, typography, provenance, and brand context that Clay "
            "Image System and Clay Campaign Studio reference during prompt "
            "enhancement. Stores the shared truth used by the dashboard "
            "generation view."
        ),
        "tags": ["brand", "tokens", "references"],
    },
    {
        "schema_version": "1.0.0",
        "project_id": "project-clay-morning-demo",
        "name": "Clay Morning Demo",
        "brief": (
            "Stakeholder briefing workspace that rolls up the Clay HQ operating "
            "system into a single truthful surface: objective, brand-brain "
            "context status, verified source references, active creative "
            "projects, available assets, generation drafts, pending approvals, "
            "functional vs. planned workflows, provider status, known "
            "blockers, and recommended next action. Nothing in this project is "
            "fabricated — every field mirrors what the local projection "
            "actually reports."
        ),
        "tags": ["demo", "briefing", "morning"],
    },
]


BRAND_SYSTEM_CONTEXT = {
    "schema_version": "1.0.0",
    "context_id": "context-clay-brand-system",
    "project_id": "project-clay-brand-system",
    "name": "Clay brand brain",
    "brand_name": "Clay",
    "brand_description": (
        "Clay is a sculptural product studio working in matte, earth-toned "
        "objects for modern interiors."
    ),
    "positioning": (
        "Quiet, confident, understated — designed for adults who value "
        "material honesty over novelty."
    ),
    "audience": "Design-forward adults, 28-55, slow-living and modernist interiors.",
    "voice_and_tone": (
        "Confident, understated, material-first. Never shouty, never cute, "
        "never hype-y."
    ),
    "design_principles": (
        "Brutalist, restrained. Negative space over decoration. One accent "
        "color per composition."
    ),
    "image_direction": (
        "Studio-lit product portrait, shallow depth of field, single warm key "
        "light from upper-left. No props beyond the object."
    ),
    "campaign_context": "Launch collection still life — hero and detail frames.",
    "product_context": "Matte ceramic vessel, 14cm tall. Oat / clay / stone.",
    "color_tokens": ["#C8FF00", "#1A1A1A", "#E8DCC4"],
    "typography_references": ["Bebas Neue", "Instrument Serif", "Inter"],
    "prohibited_claims": [
        "No unverified health claims",
        "No \"best on the market\" language",
        "No fabricated sustainability certifications",
    ],
    "source_reference_ids": [],
    "provenance": {"kind": "manual", "source": "operator_entry", "audited": True},
}


DEMO_DRAFT = {
    "schema_version": "1.0.0",
    "request_id": "request-clay-morning-demo-draft",
    "project_id": "project-clay-image-system",
    "run_id": "run-clay-morning-demo-draft",
    "prompt": (
        "A sculptural matte-ceramic vessel photographed on a clay backdrop. "
        "Quiet studio lighting from upper-left, shallow depth of field, one "
        "accent tone (#C8FF00) only."
    ),
    "references": [],
    "style": "clay",
    "aspect_ratio": "4:5",
    "variant_count": 3,
    "provider": "unavailable",
    "model": None,
    "status": "awaiting_approval",
    "attempt_status": "not_attempted",
    "error": None,
    "approval_id": "approval-clay-morning-demo-draft",
    "created_at": "2026-07-28T06:30:00Z",
}


DEMO_RUN = {
    "run_id": "run-clay-morning-demo-draft",
    "task_id": "task-clay-morning-demo-draft",
    "workflow_id": "image-generation",
    "execution_mode": "structured",
}


DEMO_APPROVAL = {
    "approval_id": "approval-clay-morning-demo-draft",
    "run_id": "run-clay-morning-demo-draft",
    "action": "execute_image_provider",
    "scope": {
        "action": "execute_image_provider",
        "project_id": "project-clay-image-system",
        "request_id": "request-clay-morning-demo-draft",
        "run_id": "run-clay-morning-demo-draft",
        "provider": "unavailable",
    },
    "reason": (
        "Saved generation draft for morning demo. Provider is currently "
        "unavailable — approving this would have no effect. Approval is held "
        "open so stakeholder can see the shape of an approval-gated request "
        "without a real execution path."
    ),
}


def seed_clay_projects(store: OperationalStore) -> list[dict]:
    """Idempotently create the five Clay workspaces and supporting records.

    Returns the full project list (created or existing). Safe to re-run at
    every server startup during development and demos.
    """
    projects_out: list[dict] = []

    for template in CLAY_PROJECTS:
        existing = store.get_project(template["project_id"])
        if existing is not None:
            projects_out.append(existing)
            continue
        document = {**template, "created_at": utc_now()}
        store.create_project(document)
        created = store.get_project(document["project_id"])
        if created is not None:
            projects_out.append(created)

    # Brand context on the Brand System project — truthful, provenance-tagged.
    if store.get_context(BRAND_SYSTEM_CONTEXT["context_id"]) is None:
        context_doc = dict(BRAND_SYSTEM_CONTEXT)
        context_doc.setdefault("created_at", utc_now())
        context_doc.setdefault("updated_at", utc_now())
        if store.get_project(context_doc["project_id"]) is not None:
            store.create_context(context_doc)

    # Saved generation draft — a real awaiting-approval request with no
    # external provider call. The run + approval are linked so Today shows
    # it in the "Needs Ryan" queue.
    if store.get_generation_request(DEMO_DRAFT["request_id"]) is None:
        store.save_task({
            "task_id": DEMO_RUN["task_id"],
            "workflow_id": DEMO_RUN["workflow_id"],
            "brief": (
                "Saved draft: matte-ceramic product portrait for morning demo."
            ),
            "prompt": DEMO_DRAFT["prompt"],
        })
        store.create_run(
            DEMO_RUN["run_id"],
            DEMO_RUN["task_id"],
            DEMO_RUN["workflow_id"],
            DEMO_RUN["execution_mode"],
        )
        store.append_event(
            DEMO_RUN["run_id"],
            "run.created",
            "queued",
            {"project_id": DEMO_DRAFT["project_id"], "request_id": DEMO_DRAFT["request_id"]},
        )
        store.create_approval(
            DEMO_APPROVAL["approval_id"],
            DEMO_APPROVAL["run_id"],
            DEMO_APPROVAL["action"],
            DEMO_APPROVAL["scope"],
            DEMO_APPROVAL["reason"],
        )
        store.append_event(
            DEMO_RUN["run_id"],
            "approval.requested",
            "awaiting_approval",
            {
                "approval_id": DEMO_APPROVAL["approval_id"],
                "scope": DEMO_APPROVAL["scope"],
                "external_action": False,
                "demo_record": True,
            },
        )
        draft_doc = dict(DEMO_DRAFT)
        draft_doc.setdefault("created_at", utc_now())
        store.save_generation_request(draft_doc)

    return projects_out
