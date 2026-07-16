## ADDED Requirements

### Requirement: Stable Console contract manifest
The system SHALL expose a `GET /console/config` manifest containing `contract_version`, `backend_version`, feature flags, stable endpoint paths, and the default memory window for the current Agent Console.

#### Scenario: Compatible V3.12.1 backend
- **WHEN** the Agent Console requests `/console/config` from the V3.12.1 service
- **THEN** the service returns HTTP 200 with `contract_version` equal to `console.v1` and endpoints for ask, stream, conversations, and runs

### Requirement: Stable Core conversation response
The Console API SHALL return conversation snapshots using the unversioned Core `MemorySnapshot` contract and SHALL NOT require Pydantic models imported from historical learning versions.

#### Scenario: Existing MySQL conversation
- **WHEN** the client requests an existing conversation with a valid memory window
- **THEN** the service returns HTTP 200 with the persisted recent turns in a Core-compatible `memory_snapshot`

#### Scenario: Conversation has not been persisted
- **WHEN** the client requests a conversation ID that has no persisted turns
- **THEN** the service returns HTTP 200 with an empty `memory_snapshot` instead of 404 or 500

### Requirement: Frontend startup compatibility check
The Agent Console MUST load the Console manifest before enabling conversation operations and MUST present an explicit incompatibility state when the backend does not implement `console.v1`.

#### Scenario: Supported contract
- **WHEN** startup receives a valid `console.v1` manifest
- **THEN** the existing conversation, SSE, Run, and Memory interactions are enabled

#### Scenario: Unsupported or missing contract
- **WHEN** startup receives 404, malformed data, or a contract version other than `console.v1`
- **THEN** the UI displays the detected backend problem and does not issue normal conversation requests against that backend

### Requirement: Single current Agent Console target
The repository SHALL provide one currently maintained Agent Console launch configuration targeting V3.12.1 on port 8020.

#### Scenario: Launch current UI
- **WHEN** a developer selects the Agent Console launch configuration
- **THEN** Vite starts from `frontend/agent_console` with `VITE_API_TARGET=http://127.0.0.1:8020`

### Requirement: UI snapshots follow contract milestones
The repository SHALL freeze a frontend snapshot only when a backend milestone materially changes the user-facing request, response, event, or interaction contract, and SHALL NOT create a frontend solely because a new Swagger learning version exists.

#### Scenario: Backend-only learning version
- **WHEN** a new Swagger version changes an internal tool, parser, planner, or protocol experiment without changing the Console contract
- **THEN** no new frontend snapshot is required

#### Scenario: Breaking UI contract milestone
- **WHEN** a future version introduces an incompatible user-facing Console contract
- **THEN** the prior current Console is frozen under `frontend/snapshots/` with its backend version, contract version, and verification commit documented

### Requirement: Historical snapshots are authentic
The repository MUST NOT label current evolved frontend code as a historical UI snapshot unless it can be tied to the actual milestone implementation.

#### Scenario: Historical source is unavailable
- **WHEN** a trustworthy milestone commit or source tree is not selected during this change
- **THEN** the snapshots directory contains policy documentation but no fabricated V3.10.1, V3.10.2, or V3.11 application copy
