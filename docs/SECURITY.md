# Security

Default deny: no credential access, deployment, publishing, email sending, canon mutation, member data, PII, PHI, or writes outside the configured runtime root. Bearer tokens are accepted only as runtime constructor/environment values and are never persisted, logged, serialized, or included in exceptions. Secret-shaped output is redacted before storage.

The command API is loopback-only and intentionally emits no CORS headers. Every POST must have a loopback `Host`, a loopback HTTP(S) `Origin`, `Content-Type: application/json`, and the non-simple server marker `X-Clay-HQ-Server: 1`. The Clay HQ Next.js server proxy must add that marker and forward its own loopback origin; browsers must never call Clay Ops directly. Projection `preview_url` values are relative to Clay Ops itself and use `/api/artifacts/<relative-path>`; a dashboard proxy may map that path under its own namespace.

`CLAY_HERMES_URL` accepts only a root HTTP loopback origin: no TLS, userinfo, query, fragment, or arbitrary path. Hermes redirects are not followed, so bearer authorization cannot cross a redirect. Demo Runs API submission is fail-closed unless Hermes advertises enforceable `run_toolset_constraints`; supported demo runs receive an empty enabled-toolset list. Image generation is capability-checked only and is never requested through Hermes.

Canon files remain read-only pointers pinned by repository path, relative path, commit, Git blob, SHA-256 content hash, and authority class. The dashboard cannot be registered as authority. Healthcare context is explicitly insufficient until a named approved clinical claims authority exists.
