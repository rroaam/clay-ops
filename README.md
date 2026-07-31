> ## clay-ops — ACTIVE OPERATIONS
> **Purpose:** Clay's operational control plane: Hermes workflows, contracts, approvals, run evidence, projections, provider readiness, and execution controls.
> **Authority:** ACTIVE OPERATIONS. Automation policy: Hermes may write only to this repository unless Ryan explicitly authorizes another target. Other repositories are read-only references by default.
> **Data policy:** credentials, member data, PII, and PHI must not be stored in this repository. Generated runtime state belongs in the git-ignored `runtime/` directory.
> **Owner:** Ryan Rosenthal (`rroaam`).
> **Canonical remote:** `https://github.com/rroaam/clay-ops` (HTTPS) — default branch `main`.
> **Intended runtime:** intended for local operation. Current deployment status must be verified separately.
> **Related:** [`claylife/clay-engine`](https://github.com/claylife/clay-engine) (product canon; read-only reference) — [`rroaam/clay-hq`](https://github.com/rroaam/clay-hq) (operator UI; the dashboard is a projection only).
> **Access:** Write access is restricted to authorized collaborators. Repository visibility is governed through GitHub settings.
> **Policy:** Do not force-push or rewrite `main`.
> **Last verified:** 2026-07-31

# Clay Ops

Clay Ops is Clay's thin, local-only operational control plane. It stores task/result packets, append-only events and approvals, artifact hashes, and pinned read-only references to canonical Clay repositories. It is not a home for product canon or deploy code, and credentials, member data, PII, and PHI must not be stored here (see the data policy above).

## Local use

```bash
uv sync --extra test
uv run clay-ops doctor
uv run clay-ops validate
uv run clay-ops workflow list
uv run clay-ops run copy-review --text "<non-sensitive proposed copy>" --target homepage --acceptance "No unsupported claims" --canon brand-design-law --canon copy-language-law
```

Generated state is confined to `runtime/` and ignored by Git. The dashboard is a projection only. Approval records acceptance or rejection of a review; no command edits, sends, publishes, or deploys content.

The loopback command API requires JSON plus `Origin` and `X-Clay-HQ-Server: 1` headers from the Clay HQ server proxy. Artifact preview URLs in projections are Clay Ops-relative `/api/artifacts/...` paths.

Creative OS Phase 2A adds the local asset/gallery/image foundation. See [Creative OS Phase 2A](docs/CREATIVE-OS-PHASE-2A.md) for architecture, provider approval lifecycle, safe byte imports, projection routes, and roadmap status.
