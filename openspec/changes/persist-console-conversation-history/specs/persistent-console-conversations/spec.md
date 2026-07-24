## ADDED Requirements

### Requirement: Server-backed conversation list
The Console API SHALL list persisted conversations from the configured Memory Store in descending update order and include a stable ID, display title, Turn count, creation time, and update time.

#### Scenario: Existing persisted conversations
- **WHEN** the client requests `GET /console/conversations`
- **THEN** the response contains MySQL-backed conversations ordered by most recently updated first

#### Scenario: No persisted conversations
- **WHEN** the configured Memory Store contains no conversations
- **THEN** the response is HTTP 200 with an empty conversations array

### Requirement: Conversation title derived from persisted content
The system SHALL derive the initial conversation title from the first persisted user message without requiring a new database column.

#### Scenario: First question is short
- **WHEN** a conversation's first user message fits within the title limit
- **THEN** the list response uses that message as the title

#### Scenario: First question is long
- **WHEN** a conversation's first user message exceeds the title limit
- **THEN** the list response returns a deterministic truncated title with an ellipsis

### Requirement: Transactional conversation deletion
The Memory Store MUST delete a Conversation and all of its associated Turns within one transaction.

#### Scenario: Delete an existing conversation
- **WHEN** the client deletes a persisted conversation
- **THEN** the Conversation and every Turn referencing its ID are removed and the API reports the deleted Turn count

#### Scenario: Delete a missing conversation
- **WHEN** the client deletes a conversation ID that does not exist
- **THEN** the API returns HTTP 404 and no other Conversation or Turn is modified

### Requirement: Frontend history uses the Console API as source of truth
The Agent Console MUST load persisted conversation history from the Console API and MUST NOT depend on `localStorage` to recover the session list or messages.

#### Scenario: Browser storage is empty
- **WHEN** the page starts with empty or cleared `localStorage` and MySQL contains conversations
- **THEN** the left sidebar displays the persisted conversations returned by the API

#### Scenario: Browser storage contains obsolete sessions
- **WHEN** legacy localStorage contains sessions that are absent from MySQL
- **THEN** those obsolete sessions are not displayed as persisted history

### Requirement: Temporary new conversation
The Agent Console SHALL support one or more in-memory temporary sessions that are not persisted until an Agent Turn is successfully written.

#### Scenario: User creates a conversation before asking
- **WHEN** the user selects New Conversation
- **THEN** the UI immediately activates a temporary empty session without creating a database row

#### Scenario: First answer is persisted
- **WHEN** an Agent request for a temporary session succeeds and writes Memory
- **THEN** the Console refreshes the server list and represents that conversation as persisted

### Requirement: Delete conversation interaction
The conversation sidebar SHALL expose an accessible delete action for each session and SHALL prevent deletion while the active Agent request is running.

#### Scenario: Delete the active persisted conversation
- **WHEN** the user deletes the currently selected persisted conversation
- **THEN** the UI directly calls the delete API, waits for success, removes it, and selects the next persisted conversation or creates a temporary session

#### Scenario: Delete a non-active persisted conversation
- **WHEN** the user deletes a persisted conversation that is not active
- **THEN** the active conversation and its visible messages remain unchanged

#### Scenario: Delete request fails
- **WHEN** the delete API returns an error
- **THEN** the session remains visible and the UI displays the error

### Requirement: Conversation display history is independent of Agent Memory Window
The Console SHALL request a dedicated display window for conversation hydration and SHALL continue sending the user-selected Memory Window only as an Agent execution parameter.

#### Scenario: Memory Window is smaller than display history
- **WHEN** the user configures an Agent Memory Window of 1 and selects an existing conversation
- **THEN** the Console may display up to the configured history display limit while the next Agent request still carries `memory_window=1`
