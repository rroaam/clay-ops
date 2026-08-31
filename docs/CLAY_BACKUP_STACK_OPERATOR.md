# Clay Autonomous Backup Stack Operator

Updated: 2026-08-31

## Mission

Build a fully working local backup to GrokBot on the Mac mini with minimal human involvement.

Primary stack:

- Hermes Agent Desktop / Bot Mode as the persistent agent team
- n8n Community Edition, self-hosted, as the event/schedule layer
- existing Clay repos and Git-tracked context as source spine
- local Mac mini as persistent execution host

Do not dismantle or modify GrokBot. This is a parallel backup stack.

## Operating mode

Work autonomously until complete.

Do not stop for ordinary reversible setup decisions. Inspect the machine, choose sensible defaults, document them, and continue.

Only interrupt the human for:

- credentials / OAuth / 2FA / passkeys / CAPTCHA
- destructive deletion of existing work
- production deployment or merge
- permission changes affecting other people
- financial purchase / paid-plan decision

If an external authentication step blocks one integration, continue all other setup and leave that connector in `AUTH_REQUIRED` state.

Never put secrets in Git, logs, reports, or chat transcripts.

## Phase 0: preflight and preservation

1. Record:
   - macOS version and architecture
   - hostname
   - available disk space
   - Homebrew status
   - Docker Desktop / OrbStack / Docker Engine status
   - Node, npm/pnpm, Python, uv, git versions
   - current `hermes` path/version/health
   - current Claude Code / Codex availability
   - current local Clay repositories and git remotes

2. Search common development locations for Clay-related repos, especially any checkout whose remote references:
   - `claylife/clay-engine`
   - `clayhc/clay-engine`
   - `rroaam/clay-ops`
   - `rroaam/joinclay-site`

3. Do not delete, rename, migrate, or overwrite the existing Hermes installation or Clay repos before creating a timestamped backup of relevant configuration.

4. Create a dedicated working root, preferably:

   `~/ClayHQ-Automation/`

   with:

   - `config/`
   - `bots/`
   - `skills/`
   - `n8n/`
   - `logs/`
   - `reports/`
   - `backups/`
   - `state/`

## Phase 1: pull current Clay context

Clone or update `rroaam/clay-ops`.

Read first:

- `context/README.md`
- `context/CURRENT_STATE.md`
- `context/ACTIVE_PRIORITIES.md`
- `context/RECENT_REVIEW_LANES.md`
- `context/DESIGN_EXECUTION_CONTEXT.md`
- `context/SOURCE_INDEX.md`
- `context/REPO_ACCESS_GAP.md`

Also read:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATING-INVARIANTS.md`
- `docs/SECURITY.md`

Treat `clay-ops` as the operational/context layer, not the product-design codebase.

If a real local `clay-engine` checkout exists, inspect its current branch, clean/dirty state, remotes, and authority files. Do not reset or discard local work.

## Phase 2: install/update Hermes

1. Inspect existing Hermes first.
2. If update is appropriate, use the official supported update path.
3. Confirm the current installation exposes the modern Desktop / Bot Mode capabilities.
4. Launch and verify Hermes can:
   - create persistent named Bots
   - preserve memory/state
   - run terminal/filesystem tools
   - run scheduled routines or equivalent
   - message/delegate between Bots if supported by the installed version

If the existing install is broken, repair in place only after backup. Prefer official install/update instructions over ad hoc replacement.

## Phase 3: build the Clay Bot roster

Create the six core workers:

### NORTH
Chief of Staff / Orchestrator

Owns:
- intake and prioritization
- source reconciliation
- delegation
- blockers
- daily/weekly briefs
- review queue
- deciding which work can move autonomously

### FIELD
Product + Member Experience

Owns:
- Intake
- Baseline
- Clinical Read
- Roadmap semantics
- 90-Day semantics
- member journey
- portal IA / unified Field Record
- product-state reconciliation

### FRAME
Digital Product Designer

Owns:
- website / landing pages
- portal
- digital onboarding
- UI/UX
- responsive systems
- Figma design execution when available
- design-to-build handoff

### STUDIO
Brand + Content Studio

Owns:
- social
- branded content
- image generation
- motion/video direction
- photography treatment
- campaign expression

### FORGE
Design Engineer

Owns:
- repo implementation
- review branches/worktrees
- tests
- local/dev servers
- draft PRs
- preview deployments
- implementation QA

### PROOF
Canon + Claims + QA

Owns:
- source authority
- conflicts/stale assumptions
- copy-law checks
- visual/canon drift
- acceptance criteria
- responsive/accessibility QA
- final PASS / BLOCK / HUMAN DECISION classification

Create specialist profiles if Hermes supports them cleanly:

- PAPER: Roadmap / 90-Day / Clinical Read / Orientation / decks / PDFs
- VOICE: governed copy, lifecycle, email/SMS, microcopy
- SIGNAL: competitive research, GTM, partnerships, strategic intelligence

## Phase 4: shared skill layer

Implement equivalent reusable shared skills for:

- clay-canon-check
- clay-task-packet
- clay-digital-ui-ux
- clay-brand-studio
- clay-artifact-design
- clay-copy-language
- clay-image-generation
- clay-video-generation
- clay-asset-governance
- clay-design-to-code
- clay-preview-qa
- clay-research-pack
- clay-approval-packet
- clay-decision-capture
- clay-weekly-review-prep

The skill implementation format should follow Hermes's current native mechanism. Do not force Grok-specific syntax if Hermes uses a different format.

### Design brain rules

FRAME, STUDIO, PAPER, FORGE, and PROOF should inherit the current design execution context from `context/DESIGN_EXECUTION_CONTEXT.md`.

Core design principles:

- quiet, premium, evidence-led, human
- neutral fields; imagery/data carry color
- Geist + Geist Mono where the current system requires them
- no generic SaaS grids
- no decorative green UI chrome
- no glow/glass/random gradients
- one surface profile at a time: Web / Artifact / Portal / Email / Internal / Social / Campaign
- do not average conflicting design eras together
- current implementation + current authority outrank historical explorations

## Phase 5: install n8n Community Edition

Install self-hosted n8n using the most reliable current local method, preferably Docker Compose if Docker is healthy.

Requirements:

- local-only by default
- persistent storage
- restart policy
- no public internet exposure
- no credentials committed to Git
- version/config documented
- health check documented

Create a durable compose/config directory under:

`~/ClayHQ-Automation/n8n/`

If Docker is unavailable, install/fix it only if that is low-risk and does not disturb other projects. Otherwise use an officially supported local n8n path.

## Phase 6: event nervous system

Create n8n workflow templates for:

### Clay Slack Signal Watch
Input: Clay Slack events/messages when connector/auth is available.

Classify:
- DECISION
- REQUEST
- FEEDBACK
- BLOCKER
- INFORMATION
- NOISE

Meaningful signals should reach NORTH. Noise should die silently.

### Clay Email Work Watch
Detect:
- direct asks
- feedback
- approvals
- review requests
- deadlines
- direction changes

Meaningful items route to NORTH.

### GitHub Review Watch
Trigger on:
- PR opened/updated
- review comment
- CI failure
- new review branch when useful

Route technical items to FORGE and meaningful product/brand implications to NORTH.

### Notion Change Watch
If/when authenticated to the Clay Notion workspace, detect material changes to priorities, specs, decisions, and project status.

### Daily Clay Autonomous Workday
Morning schedule.

NORTH should:
1. inspect new signals
2. reconcile current priorities
3. select up to three useful reversible tasks
4. delegate
5. require PROOF review for consequential output
6. produce review-ready work instead of planning-only output

### Site Improvement Lab
Twice weekly.

FRAME + FIELD + FORGE + PROOF review current website/product surfaces and identify evidence-backed improvements. High-confidence reversible improvements may be built on review branches/previews. Never auto-promote production.

If credentials are missing, create disabled/template workflows with explicit `AUTH_REQUIRED` notes rather than blocking the whole build.

## Phase 7: autonomy model

Default autonomous actions:

- read/search Clay sources
- inspect repos
- local workspace edits
- create review branches/worktrees
- code changes on non-production branches
- tests/builds
- draft PRs
- preview deployments where credentials already permit them
- Figma draft/playground work where credentials permit it
- internal docs/reports
- research
- Bot delegation
- skill improvement
- QA

Human approval remains for:

- merge to protected/main branches
- production deployment/promotion
- production domain/env-var changes
- public publishing
- sending external communications as Clay
- permanent deletion of important canonical material
- permission/access changes
- major source-of-truth changes
- final clinical/legal/health-claim approval
- spend/purchases

## Phase 8: background persistence

Make the stack survive normal workstation use and reboot where practical.

Use the officially supported persistence mechanism for each service. Prefer Docker restart policies / launchd / Hermes-supported daemon behavior rather than fragile shell loops.

Document exactly:

- how Hermes starts
- how n8n starts
- how to stop each
- how to restart each
- how to inspect logs
- how to check health

Do not create infinite busy loops or high-frequency polling if event hooks are available.

## Phase 9: smoke tests

Run real tests before declaring success.

Minimum tests:

### Test A: NORTH
Read `clay-ops/context` and produce current top priorities with evidence.

### Test B: FIELD
Reconstruct current member-journey state and identify unresolved conflicts.

### Test C: FRAME
Use the current design context to critique one existing review surface without inventing a new visual system.

### Test D: STUDIO
Produce one canon-compatible content/brand concept from current Clay context.

### Test E: FORGE
On a safe test/review branch only, perform a low-risk repository task, run tests, and create a clean handoff. Do not merge.

### Test F: PROOF
Review outputs and classify PASS / BLOCK / HUMAN DECISION.

### Test G: n8n
Manually inject a mock Slack/Email/GitHub event and confirm it routes to the intended workflow destination or produces the expected serialized NORTH intake packet.

## Phase 10: completion report and ping contract

When the stack is truly ready for review, create a branch in `rroaam/clay-ops` named something like:

`backup/hermes-n8n-ready-YYYY-MM-DD`

Add:

`docs/HERMES_N8N_BACKUP_READY.md`

The report must include:

- machine/environment inventory
- Hermes version and health
- n8n version and health
- exact local paths
- Bot roster created
- skills created/migrated
- routines/workflows created
- connectors authenticated
- connectors still requiring auth
- local Clay repos discovered
- exact `clay-engine` remote/access findings
- smoke-test results
- startup/restart instructions
- known limitations
- next recommended improvements

Open a GitHub PR titled exactly:

`backup: Clay autonomous stack ready`

If the build cannot be completed because a human authentication step is genuinely required, open a PR titled exactly:

`backup: Clay stack blocked on authentication`

and include the smallest possible list of auth actions needed. Continue all other work first.

Do not merge either PR automatically.

## Definition of done

The stack is done when:

1. Hermes is healthy and usable on the Mac mini.
2. NORTH / FIELD / FRAME / STUDIO / FORGE / PROOF exist and retain their roles.
3. Shared Clay skills are installed in Hermes-native form.
4. `clay-ops/context` is part of the default Clay working context.
5. n8n runs locally with persistence.
6. autonomous-work and event-routing workflows exist.
7. at least the mock-event routing test passes.
8. the six-Bot smoke test passes or failures are honestly documented.
9. existing GrokBot setup remains untouched.
10. the completion PR is open with full evidence.

Do not report success before these checks are complete.
