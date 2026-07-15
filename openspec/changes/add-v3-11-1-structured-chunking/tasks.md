## 1. Docling shared integration

- [x] 1.1 Remove the custom DocumentTree/chunker work and keep Docling as the only shared ingest path
- [x] 1.2 Add Docling dependencies, configuration and a thin converter/HybridChunker adapter
- [x] 1.3 Route shared V0 ingest directly through Docling without a legacy backend selector

## 2. V3.11.1 learning version

- [x] 2.1 Add documented schemas and service for convert, chunks, ingest and search
- [x] 2.2 Add FastAPI app/routes, Swagger examples and runtime boundary endpoint
- [x] 2.3 Add `documents-v3-11-1` CLI commands and launch configurations

## 3. Verification and learning material

- [x] 3.1 Add adapter, service, API and CLI tests with framework fakes
- [x] 3.2 Add guide, file responsibilities, payloads, branches, breakpoint table and SVG
- [x] 3.3 Update roadmap, verify focused checks and reconcile line numbers

## 4. Production parent-child migration

- [x] 4.1 Add generic heading-path grouping, small-block merge and recursive parent/child splitting
- [x] 4.2 Persist child vectors with parent metadata and expand dense/keyword/hybrid results after ranking
- [x] 4.3 Add regression tests, VueUse real-document validation, updated guide and SVG
