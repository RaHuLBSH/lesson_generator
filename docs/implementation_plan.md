# Implementation plan

## Phase 1 — Architecture and planning (current)
Inspect repository; establish package layout and durable project instructions; define architecture, implementation plan, dependencies, environment template, initial Pydantic contracts and graph state; add minimal pytest configuration. No generation, evaluation or persistence behavior.

## Phase 2 — Generation and grounding
Implement configurable OpenAI-compatible client setup, curated RAG reference document, lesson generation prompt and generator. Keep API access isolated and injectable for offline tests.

## Phase 3 — Evaluation and retry graph
Implement independent strict evaluator and structured output parsing. Build LangGraph Generate/Evaluate/Route flow, feedback-driven retries and attempt cap. Cover rubric validation and routing with deterministic stubs.

## Phase 4 — Persistence, outputs and completion
Implement SQLite run/failure/feedback/correction memory and approved/rejected output management. Add end-to-end offline tests and usage documentation, then review the complete assessment workflow.
