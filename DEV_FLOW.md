**Development Flow**

```mermaid
flowchart TD
  A[Requirements & Compliance] --> B[System Architecture]
  B --> C[Auth & Onboarding]
  C --> D[Post Management Core]
  D --> E[Drafts & Scheduling]
  D --> F[Bulk-generation Workflow]
  D --> G[Duplicate Detection]
  B --> H[Adaptive UI Handlers]
  B --> I[AI Training Pipeline]
  I --> J[Model Integration]
  H --> K[Self-healing & Monitoring]
  K --> L[Error Auto-fix Loop]
  B --> M[Admin Dashboard & Licensing]
  M --> N[Installer & Packaging]
  N --> O[Security & Anti-clone]
  O --> P[QA, Testing, CI/CD]
  P --> Q[Deployment & Monitoring]

  style A fill:#ffffff,stroke:#000,stroke-width:1px
  style B fill:#ffffff,stroke:#000
  style M fill:#ffecec,stroke:#e60000
```

Short flow steps:
- Requirements & Compliance: document legal, platform TOS, and risk controls.
- Architecture: service boundaries, DB, queue, worker, UI, AI components.
- Auth: license checks, device binding, RBAC.
- Core: CRUD for posts, groups, pages, account types.
- Drafts/Scheduling: save, queue, cron workers, timezone handling.
- Bulk-safe: prepare batches, preview, hold-and-fire publish.
- Handlers: DOM field discovery, resilient selectors, selector store.
- AI: seed-data training, incremental learning, inference service.
- Self-healing: runtime detection of UI changes, auto-repair handlers.
- Admin: license mgmt, package tiers, device limits, audit logs.
- Installer: cross-platform packaging, silent install, updater.
- Security: code obfuscation, tamper detection, server-side checks.
- QA/CI: unit, integration, e2e, simulated FB sandbox runs.
- Deploy: monitoring, alerts, rollback, telemetry (non-sensitive).
