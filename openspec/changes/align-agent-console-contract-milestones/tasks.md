## 1. Stable Console API

- [x] 1.1 Create the unversioned `obsidian_rag/console_api` package with Core-compatible conversation and capability schemas.
- [x] 1.2 Implement the stable `/console/config` and `/console/conversations/{conversation_id}` routes and dependencies.
- [x] 1.3 Mount the stable Console router in V3.12.1 and remove its version-local Console schema/router duplication.
- [x] 1.4 Add backend contract tests for manifest fields, existing conversations, and empty conversations.

## 2. Current Agent Console Alignment

- [x] 2.1 Rename `frontend/v3_10_1_agent_console` to `frontend/agent_console` and update package metadata and repository path references.
- [x] 2.2 Add typed `console.v1` manifest loading and validation to the production API client.
- [x] 2.3 Add startup compatibility state to `use-agent-console.ts` and prevent normal conversation operations on incompatible backends.
- [x] 2.4 Display a clear backend incompatibility state in the current Console without adding version branches to feature components.
- [x] 2.5 Add frontend unit tests for compatible and incompatible startup manifests.

## 3. Milestone Policy and Developer Experience

- [x] 3.1 Add `frontend/snapshots/README.md` describing milestone admission, authenticity, maintenance, and metadata rules.
- [x] 3.2 Update `.vscode/launch.json` so one current Agent Console entry targets V3.12.1 / 8020 from `frontend/agent_console`.
- [x] 3.3 Update V3.12.1 and roadmap documentation to distinguish Swagger learning versions from UI contract milestones.
- [x] 3.4 Search the repository for stale current-Console paths or launch instructions and align applicable references.

## 4. Verification

- [x] 4.1 Run focused backend Console API tests.
- [x] 4.2 Run frontend unit tests, TypeScript checking, and production build.
- [x] 4.3 Verify OpenSpec tasks and contract artifacts match the implemented behavior.
