"""Supervised-workflow governance records for Clay HQ.

Truthful, static, provider-neutral records that mirror the Clay Ops
recovery/handoff documents already on disk. Nothing here fabricates an
execution, a provider connection, or an approval decision — this module
only *describes* the current active-build ownership, source-of-truth
registry, and advisor-review roster so the dashboard can render one
composite "Supervised Workflow" operator page.

Source documents mirrored (read-only, not re-parsed at runtime):
  - ~/Downloads/CLAY_ACTIVE_BUILD_HANDOFF.md
  - ~/Downloads/CLAY_HQ_CURRENT_SOURCE_MAP.yaml
  - ~/Downloads/CLAY_LATEST_WORK_SOURCE_RECONCILIATION.md

If those documents change, this module must be updated to match — it is
a projection of their content into the Clay Ops API, not an independent
claim.
"""
from __future__ import annotations


ACTIVE_BUILD: dict = {
    "build_id": "build-claude-code-three-surface",
    "name": "Claude Code three-surface build (landing recoat, Blueprint preview, dark post-visit/body-composition)",
    "owner": "Claude Code",
    "branch": "clayhc-clay-engine @ edits/seed-recoat",
    "status": "ready_for_review",
    "locked_files": [
        "clayhc-clay-engine/components/landing-v5/index.tsx",
        "clayhc-clay-engine/components/blueprint/BlueprintDoc.tsx",
        "clayhc-clay-engine/components/blueprint/ClayScore.tsx",
        "clayhc-clay-engine/lib/blueprint/fixtures.ts",
        "clayhc-clay-engine/lib/blueprint/schema.ts",
        "clayhc-clay-engine/scripts/blueprint-pdf.mjs",
        "clayhc-clay-engine/scripts/shots.mjs",
        "clayhc-clay-engine/app/post-visit/page.tsx",
        "clayhc-clay-engine/components/post-visit/index.tsx",
        "clayhc-clay-engine/components/system/BodyComposition.tsx",
        "clayhc-clay-engine/components/system/structure.tsx",
        "clayhc-clay-engine/docs/DESIGN_MIGRATION_PROPOSAL.md",
        "clayhc-clay-engine/docs/source-artifacts/Clay_Justin_Deck_alt.original.html",
        "Downloads/DESIGN.md",
        "clayhc-clay-engine/DESIGN.md",
    ],
    "changed_files_verified": [
        "M components/blueprint/BlueprintDoc.tsx",
        "M components/blueprint/ClayScore.tsx",
        "M components/landing-v5/index.tsx",
        "M lib/blueprint/fixtures.ts",
        "M lib/blueprint/schema.ts",
        "M scripts/blueprint-pdf.mjs",
        "?? app/post-visit/ (new dark post-visit/body-composition route)",
        "?? components/post-visit/ (new)",
        "?? components/system/ (new — BodyComposition.tsx, structure.tsx)",
        "?? docs/DESIGN_MIGRATION_PROPOSAL.md (new — proposal only, no code)",
        "?? docs/source-artifacts/ (new — original Justin deck HTML archived)",
        "?? scripts/shots.mjs (new — screenshot harness)",
    ],
    "preview_routes": [
        "landing-v5 (recoat)",
        "blueprint-preview (light Blueprint preview)",
        "post-visit (dark post-visit / body-composition experience)",
        "justin-deck-original (archived reference, unmodified)",
    ],
    "evidence_paths": [
        "clayhc-clay-engine/output/seed-recoat/before/MANIFEST.md (+ 12 PNGs at 390/768/1280/1440px)",
        "clayhc-clay-engine/output/seed-recoat/after/MANIFEST.md (+ 16 PNGs at 390/768/1280/1440px)",
    ],
    "typescript_qa": "Reported clean by Claude Code; not independently re-run by Hermes this slice (read-only ingestion only).",
    "known_limitations": [
        "Narrow-viewport (390/768px) screenshot-harness limitation: Chrome on macOS enforces a minimum window width, so narrow shots are captured wider then cropped — this reads as overflow where none exists. Per MANIFEST.md: 'Read 1280 and 1440 as truth. 390 and 768 are indicative only... Verify narrow layouts against the DOM, not these files.'",
        "Missing care-team photography — post-visit/body-composition experience references clinician imagery not yet sourced.",
        "Experimental token approval still pending: docs/DESIGN_MIGRATION_PROPOSAL.md documents two competing 'canonical' DESIGN.md documents (repo DESIGN.md vs Downloads DESIGN.md dated 2026-07-26) with incompatible foundations (Geist vs Host Grotesk; different color grounds). Proposal explicitly states 'No code written. Needs Deven and Justin sign off before anything moves.' Three proposed tokens (clay.forest #1C3A13, clay.canvas #FCFCF7, clay.signal #D3FA99) are flagged as byte-identical to Seed's own tokens — a brand-risk finding, not yet resolved.",
    ],
    "expected_evidence": [
        "final report (Markdown)",
        "files changed list",
        "git status --short + git diff --stat on edits/seed-recoat",
        "screenshots of the three surfaces",
        "preview URLs (Vercel branch or localhost)",
        "design-token deltas (Forest/Canvas/Signal usage locations)",
    ],
    "last_updated": "2026-07-28",
}


SOURCE_REGISTRY: list[dict] = [
    {
        "domain": "visual_design_canon",
        "current_implementation_baseline": "clayhc-clay-engine/DESIGN.md (13 KB in-tree, 2026-07-27)",
        "proposed_future_canon": "Downloads/DESIGN.md (47 KB, 2026-07-26 — candidate_design_law, NOT approved)",
        "reference_sources": ["Downloads/SEED-UI-STYLING-GUIDE.md (structural reference only)"],
        "conflict_status": "split_brain",
        "active_editor": "Claude Code (may read both; may not migrate without approval)",
        "latest_working_source": "Downloads/DESIGN.md (candidate only, not repo canon)",
    },
    {
        "domain": "landing_page",
        "current_implementation_baseline": "clayhc-clay-engine/components/landing-v5/index.tsx (edits/recoat-v2)",
        "proposed_future_canon": "Downloads/DESIGN.md (candidate_design_law)",
        "reference_sources": ["dev/clay-engine/gallery-01-landing-v5.png"],
        "conflict_status": "clean",
        "active_editor": "Claude Code",
        "latest_working_source": "landing-v5/index.tsx (2026-07-27, commit 98b08d1)",
    },
    {
        "domain": "justin_post_visit_body_composition",
        "current_implementation_baseline": (
            "components/blueprint/{BlueprintDoc.tsx, ClayScore.tsx} + "
            "app/lab/{home-v2,elements,plan,team,data} + "
            "Desktop/Clay-Roadmap/{Clay_Roadmap.html, Clay_Justin_Deck_alt.html}"
        ),
        "proposed_future_canon": "Downloads/DESIGN.md (candidate_design_law)",
        "reference_sources": [
            "dev/clay-engine/justin-alt-full.png",
            "dev/clay-engine/gallery-04-roadmap-full.png",
        ],
        "conflict_status": "split_brain",
        "active_editor": "Claude Code",
        "latest_working_source": "distributed across 6 artifacts — no single file (see reconciliation report)",
    },
    {
        "domain": "clay_ops_hq_infrastructure",
        "current_implementation_baseline": "clay-ops + clay-engine/dashboard (this Hermes slice)",
        "proposed_future_canon": "n/a — Clay Ops is the operator-owned infra layer, not a design surface",
        "reference_sources": ["clay-ops/schemas/*.json", "dashboard/lib/clay-hq/types.ts"],
        "conflict_status": "clean",
        "active_editor": "Hermes",
        "latest_working_source": "this repository, branch feat/creative-os-phase-2b",
    },
]


ADVISOR_BOARD: list[dict] = [
    {
        "role": "Hermes",
        "review_status": "reviewed",
        "decision": "approve_with_conditions",
        "evidence_or_reason": (
            "Provenance verified: prompt + brand context match request-clay-morning-demo-draft. "
            "Provider remains unavailable — execution cannot proceed regardless of this review."
        ),
        "required": True,
    },
    {
        "role": "Brand Steward",
        "review_status": "reviewed",
        "decision": "approve",
        "evidence_or_reason": "Prompt matches context-clay-brand-system color tokens (#C8FF00) and image_direction.",
        "required": True,
    },
    {
        "role": "Creative Director",
        "review_status": "reviewed",
        "decision": "approve",
        "evidence_or_reason": "Composition brief (studio-lit, shallow DOF, single accent) is on-brief for the Clay Image System.",
        "required": True,
    },
    {
        "role": "Copy and Claims",
        "review_status": "not_applicable",
        "decision": "n/a",
        "evidence_or_reason": "Request is an image draft with no copy/claims payload to review.",
        "required": False,
    },
    {
        "role": "Systems and QA",
        "review_status": "reviewed",
        "decision": "approve_with_conditions",
        "evidence_or_reason": "Approval-gate tests (28 Python + 5 TypeScript) confirm no provider call can occur before exact approval.",
        "required": True,
    },
    {
        "role": "Ryan",
        "review_status": "pending",
        "decision": "pending",
        "evidence_or_reason": "Final operator decision required — approval-clay-morning-demo-draft is still status=pending.",
        "required": True,
    },
]


def describe_active_build() -> dict:
    return dict(ACTIVE_BUILD)


def describe_source_registry() -> list[dict]:
    return [dict(item) for item in SOURCE_REGISTRY]


def describe_advisor_board() -> list[dict]:
    return [dict(item) for item in ADVISOR_BOARD]
