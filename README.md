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
