# ADR 0001: Start With a Schema-Driven Pipeline

## Status

Accepted

## Context

LogiSpace needs credible mystery reports with source-backed claims and spoiler control. The first version should prove the report value before adding autonomous agents, large graph infrastructure, or recommendation models.

## Decision

Use a Python-first backend with FastAPI and Pydantic for domain contracts. Keep the research pipeline observable and deterministic at first. Use TypeScript and Next.js for the web surface.

## Consequences

- Domain schema remains owned by LogiSpace.
- Agent-Reach, Cognee, and model providers are adapters, not the architecture center.
- Evaluation can run against stable Pydantic objects before real collectors are connected.
