# ForgeOps README Introduction Design

## Goal

Make the repository's top-level README explain, in Korean, that ForgeOps is a safety-first framework for specifying, validating, and operating AI agent workflows.

## Audience and message

The primary audience is developers and evaluators opening the repository for the first time. The opening must state that ForgeOps separates product data from execution control and makes authority, approval, state transitions, evidence, and verification explicit and testable.

## Content design

Insert a concise `ForgeOps란?` section immediately below the title. It will contain:

1. A two-sentence plain-language definition.
2. Four short bullets for the Main/Part/Work role boundary, explicit authority and approval, durable event/run-manifest records, and executable verification gates.
3. A `현재 구현 범위` note that links the WBS and accurately says W1-W3 contract work is implemented while WBS-008 remains in progress pending VG-023.

The existing `Portable Agent Harness` section and its links remain unchanged and directly follow the introduction.

## Constraints

- Keep the document in Korean and use repository-relative Markdown links.
- Do not claim Phase 0 Exit, WBS-008 completion, deployment, or external integration.
- Do not alter protocol, contract, fixture, code, or Git state.

## Verification

Review the rendered Markdown source to confirm that the introduction is directly below the title, links resolve to existing repository paths, and all status wording matches `docs/project/wbs.md`.

## Scope revision: full README rewrite

The user authorized replacing the existing top-level README rather than preserving its prior standalone line or section layout. The rewritten document remains Korean and developer-facing, but now has one coherent flow: project definition, safety principles, Main/Part/Work responsibilities, current implementation status, verification entry point, and documentation map. It retains only repository-relative links to existing resources and keeps the WBS-008/VG-023 status limitation explicit.
