## 1. Memory Store Conversation Management

- [x] 1.1 Add shared Conversation summary and delete result models plus deterministic title generation.
- [x] 1.2 Implement ordered list and transactional delete in SQLiteConversationMemoryStore.
- [x] 1.3 Implement ordered list and cascading transactional delete in MySQLConversationMemoryStore.
- [x] 1.4 Add focused Store tests for ordering, title generation, Turn counts, deletion, and missing IDs.

## 2. Console API Contract

- [x] 2.1 Add conversation list/delete Pydantic schemas with Chinese Swagger field descriptions.
- [x] 2.2 Add GET collection and DELETE resource routes to `console.v1`.
- [x] 2.3 Extend `/console/config` features and endpoints for conversation management.
- [x] 2.4 Add API tests for list, delete cascade, missing IDs, and manifest compatibility.

## 3. Agent Console State and API Client

- [x] 3.1 Add TypeScript list/delete contracts and production client methods.
- [x] 3.2 Replace localStorage session history with server list loading and temporary-session merging.
- [x] 3.3 Separate the conversation display history window from Agent `memory_window`.
- [x] 3.4 Refresh persisted conversations after a successful Memory write.
- [x] 3.5 Implement delete state, error handling, and deterministic selection after deletion.

## 4. Sidebar Interaction

- [x] 4.1 Add an accessible delete event/button to ConversationSidebar with running/deleting disabled states.
- [x] 4.2 Wire App.vue props/events without moving state logic into the component.
- [x] 4.3 Add frontend tests for server-backed startup, legacy localStorage isolation, temporary sessions, and delete behavior.

## 5. Documentation and Verification

- [x] 5.1 Document the new `console.v1` endpoints, hard-delete behavior, and source-of-truth boundary.
- [x] 5.2 Run focused backend Store/API tests.
- [x] 5.3 Run frontend tests, TypeScript checking, and production build.
- [x] 5.4 Run strict OpenSpec validation and confirm all tasks match implementation.
