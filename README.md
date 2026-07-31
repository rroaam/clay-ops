> ## clay-ops — ACTIVE OPERATIONS
> **Purpose:** Clay's operational control plane: Hermes workflows, contracts, approvals, run evidence, projections, provider readiness, and execution controls.
> **Authority:** ACTIVE OPERATIONS. The only repository Hermes may modify. Contains no product canon, no deploy code, no credentials, no member data, no PII/PHI.
> **Owner:** Ryan Rosenthal (`rroaam`).
> **Canonical remote:** `https://github.com/rroaam/clay-ops` (HTTPS) — default branch `main`.
> **Deploys to:** not deployed — local-only control plane; generated state confined to `runtime/` and git-ignored.
> **Related:** [`claylife/clay-engine`](https://github.com/claylife/clay-engine) (production canon, read-only reference) — [`rroaam/clay-hq`](https://github.com/rroaam/clay-hq) (operator UI; the dashboard is a projection only).
> **Access:** rroaam (admin). Hermes: modify this repo only, read-only everywhere else. Collaborators by invitation.
> **Protected surfaces:** `main` — Hermes execution depends on it; never force-push.
> **Last verified:** 2026-07-31

# Clay Ops

Clay Ops is Clay's thin, local-only operational control plane. It stores task/result packets, append-only events and approvals, artifact hashes, and pinned read-only references to canonical Clay repositories. It does not contain product canon, deploy code, credentials, member data, PII, or PHI.

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
