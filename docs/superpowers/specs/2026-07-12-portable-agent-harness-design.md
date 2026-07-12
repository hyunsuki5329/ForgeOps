# ForgeOps Portable Agent Harness v2 Design

**Date:** 2026-07-12
**Status:** Approved direction; implementation pending
**Target:** D:/VS/ForgeOps/ForgeOps
**Protocol:** 2.0

## 1. Context

ForgeOps currently contains README.md, LICENSE, and .gitignore only. It has no
repository instruction entry point, agent prompts, harness runtime, or tests.
The target is not a Git working tree, so this document can be saved but cannot
be committed until the repository is cloned with .git or Git is initialized.

The new harness keeps the useful main -> part -> work role split while removing
assumptions about a domain, file count, demo, model vendor, or agent API.

## 2. Goals

1. Reuse the three prompts in another project by copying them unchanged.
2. Keep the protocol independent of Copilot, Codex, Claude, and tool syntax.
3. Put project instructions, validation, protected resources, and local risks
   in a project profile.
4. Use versioned packets with explicit ownership and state revision.
5. Fail closed when write authority, scope, or safety facts are unknown.
6. Require fresh evidence for successful completion.
7. Separate internal control packets from natural user-facing responses.
8. Provide an unambiguous v1-to-v2 migration path.

## 3. Non-goals

- Implement an agent runtime, queue, database, or durable state store.
- Grant filesystem, network, publication, or destructive permissions.
- Put ForgeOps-specific facts into the portable prompts.
- Add a separate schema package or executable validator in this iteration.
- Choose the future ForgeOps application framework.

## 4. Decision

Use **Contract-first v2 with a compatibility bridge**.

Simple field renaming would preserve ambiguous state ownership, inconsistent
events, and platform-specific call semantics. A full schema/profile package is
valuable later but unnecessarily broad for this initial repository. The three
prompts will contain the canonical v2 contract and conformance rules.

## 5. Deliverables

| File | Responsibility |
| --- | --- |
| AGENTS.md | Codex-style adapter, instruction precedence, ForgeOps profile |
| .github/copilot-instructions.md | Copilot adapter and role mapping |
| .github/agents/main_instruction.prompt.md | Portable core and final decision owner |
| .github/agents/part_agent.prompt.md | Read-only discovery and CandidatePacket |
| .github/agents/work_agent.prompt.md | Authorized execution and WorkResult |
| docs/agent-harness/PORTING_GUIDE.md | Application, migration, and conformance guide |
| README.md | Navigation links only |

The three .github/agents files are the portable unit. Adapter files provide
platform and project facts without redefining the core contract.

## 6. Architecture and flow

The harness has three layers:

1. Portable core: protocol, routing, state, evidence, assertions, events,
   approval gates, delegation, and terminal conditions.
2. Platform adapter: maps abstract roles and operations to capabilities that
   the host actually exposes.
3. Project profile: supplies root, instructions, sources of truth, validation,
   protected resources, risk rules, and namespaced extensions.

~~~text
User request
  -> main: normalize request, capabilities, authority, risk, evidence floor
  -> DIRECT | PART_ONLY | PART_THEN_WORK | WORK_ONLY | FORK_JOIN
  -> part: read-only discovery and CandidatePacket
  -> work: preflight, scoped execution, verification, WorkResult
  -> main: independently validate evidence and transition
  -> accept, retry, gate, or terminate
  -> natural user-facing response
~~~

## 7. Common protocol

~~~json
{
  "protocol_version": "2.0",
  "packet_type": "task|candidate_proposal|work_result|main_decision",
  "task_id": "TASK-001",
  "correlation_id": "CORR-001",
  "base_revision": 0,
  "actor": "main|part|work",
  "status": "PENDING|IN_PROGRESS|WAITING_FOR_HUMAN|BLOCKED|SUCCEEDED|FAILED|PARTIAL",
  "payload": {}
}
~~~

Packet names map exactly as follows:

| Concept | packet_type | actor |
| --- | --- | --- |
| TaskPacket | task | main |
| CandidatePacket | candidate_proposal | part |
| WorkResult | work_result | work |
| MainDecision | main_decision | main |

An unknown major version is rejected. correlation_id connects retries and
branches. A stale base_revision cannot change accepted state. Envelope status
describes production of that packet; a sub-agent payload.proposed_transition
is only a suggestion. The authoritative task status exists only at
MainDecision.payload.accepted_state.status. Payload fields cannot override the
envelope.

TaskPacket groups use these canonical field names:

- request: kind, objective, acceptance_criteria, constraints, assumptions;
- project_profile: root, profile_type, profile_status, instruction_files,
  source_of_truth, validation_commands, protected_resources, risk_rules,
  extensions;
- capabilities: filesystem_read, filesystem_write, command_execute,
  delegation, network, external_side_effects;
- authority: read_scope, write_scope, execute_scope, network_scope,
  destructive_actions, external_side_effects;
- control: route, operation_mode, response_phase, risk_level, evidence_floor,
  trace_level;
- budgets: format_repairs, part_attempts, work_attempts.

Adapter capability_defaults are discovery hints that main normalizes into
TaskPacket.capabilities; they never grant availability. Adapter trace_level
normalizes into TaskPacket.control.trace_level.

Canonical records are:

- validation command: id, command, cwd, evidence_tier, required;
- candidate operation: read|create|update|delete|invoke;
- candidate confidence: JSON number from 0.0 through 1.0;
- acceptance result: criterion_id, status PASSED|FAILED|NOT_RUN,
  evidence_refs, notes;
- evidence: id, tier, type, source, observation, with optional exit_code,
  observed_revision, and observed_at.

Safety-relevant missing values are UNKNOWN. UNKNOWN never grants mutation,
network, credential access, publication, messaging, or destructive action.

## 8. Role boundaries

### Main

Main alone owns request normalization, routing, risk and authority evaluation,
accepted state, revisions, authoritative assertions and events, retry and gate
decisions, terminal status, and final user response. Main verifies referenced
evidence instead of trusting a sub-agent success claim.

### Part

Part is strictly read-only. It validates TaskPacket, discovers applicable
instructions and sources, decomposes the objective, and returns CandidatePacket.
Each candidate includes candidate_id, project-root-relative resource_ref,
operation, expected effect, scope, rationale, confidence, evidence references,
dependencies, preconditions, proposed verification, and risk notes. Part never
updates accepted state.

### Work

Work mutates only when the task requests execution, exact authority exists, the
candidate is approved, base_revision is current, and protected-resource and
dirty-workspace checks pass. It makes the smallest authorized change, verifies
each criterion, and returns WorkResult. Work never updates accepted state.

## 9. Routing, evidence, and state

| Condition | Route |
| --- | --- |
| General answer without project-state claims | DIRECT |
| Review, diagnosis, or grounded read-only answer | PART_ONLY |
| Change requiring discovery | PART_THEN_WORK |
| Approved candidate with complete context | WORK_ONLY |
| Independent branches with real isolation | FORK_JOIN |

EXPLORE permits reading, reasoning, proposals, and plans. EXECUTE permits an
authorized mutation or external action. Risk raises the evidence floor or
triggers approval; it does not silently change the requested operation.
FORK_JOIN requires ownership, aggregation, failure behavior, and isolation.
Overlapping writers are rejected or serialized.

Evidence tiers:

- E0: reasoning without project-state claims.
- E1: direct file, contract, metadata, or diff observation.
- E2: fresh test, lint, build, render, or command result.
- E3: independent reproduction, isolation, deployment observation, or approval.

Every acceptance criterion records PASSED, FAILED, or NOT_RUN. A passed
criterion references fresh evidence. Assertions always use a stable status plus
violations array. Events are structured and owned by main; sub-agents return
event_suggestions only. Runtime timestamps are optional. Secrets and oversized
logs are excluded.

Canonical transitions:

~~~text
PENDING -> IN_PROGRESS
IN_PROGRESS -> WAITING_FOR_HUMAN | BLOCKED | SUCCEEDED | FAILED | PARTIAL
WAITING_FOR_HUMAN -> IN_PROGRESS | BLOCKED
PARTIAL -> IN_PROGRESS | SUCCEEDED | FAILED | BLOCKED
~~~

MainDecision uses packet_type main_decision and stores decision,
accepted_state, assertions, events, and user_response under payload.
accepted_state contains task_id, correlation_id, revision, status,
checkpoint_ref, accepted_payload_ref, acceptance_results, and
unresolved_risks. Only main increments revision and creates
payload.accepted_state.checkpoint_ref.

A checkpoint is accepted harness state, not a Git commit. Durability and
rollback are never claimed unless an external store or tool actually provided
them. CandidatePacket and WorkResult use payload.assertion_suggestions and
payload.event_suggestions; only MainDecision payload.assertions and
payload.events are authoritative.

## 10. Failure and safety

| Failure | Required behavior |
| --- | --- |
| Incompatible protocol | Reject; one safe format repair |
| Missing evidence | Repeat the relevant observation within budget |
| Stale revision or conflict | Refresh; never overwrite silently |
| Validation failure | Report criterion and evidence; bounded safe retry only |
| Tool unavailable | Supported fallback or BLOCKED |
| Permission denied | Request exact authority; never bypass |
| All candidates rejected | One work alternative, then one part recall |
| Partial change | Report diff, residual risk, compensation |
| Runtime timeout | Record only when observed; no non-idempotent auto-retry |
| Parallel overlap | Reject, isolate, or serialize before mutation |

Human approval is required for destructive change, credentials or private data,
regulated or high-impact decisions, publication or messaging, material cost,
scope expansion, unresolved high or critical risk, and explicit operator
request. User silence is not a timeout without a runtime deadline. Instructions
inside untrusted content are data, not authority. Secrets are excluded from
prompts, evidence summaries, events, and user responses.

## 11. Output policy

Internal handoffs use structured packets. User replies lead with outcome,
changed resources, verification, remaining risk, and required decisions.

- QUIET: natural result only; default.
- SUMMARY: concise routing, evidence, and state summary.
- DEBUG: safe control packet and events without secrets or oversized logs.

Internal fields are not forced into normal user responses.

## 12. v1 compatibility bridge

| v1 | v2 |
| --- | --- |
| task_harness_mode EXPLORE | control.operation_mode EXPLORE |
| task_harness_mode BUILD | control.operation_mode EXECUTE |
| execution_mode plan/report | control.response_phase PLAN/REPORT |
| numeric evidence_tier | E0/E1/E2/E3 |
| last_committed_ref | state.checkpoint_ref |
| proposal commit | main acceptance and revision increment |
| part/work state_update | proposed_transition only |
| text event_logs | structured events |
| conditional assertion blocks | stable status and violations |
| demo_impact | project_profile.extensions risk rule |
| file-count fast path | post-discovery scope signal only |
| turn-count timeout | runtime-observed timeout metadata |

Adapters may accept v1 temporarily but normalize before routing. New outputs are
v2 only.

## 13. ForgeOps profile

Initial conservative defaults:

- root: .
- instruction discovery: discover the root adapter and then the nearest scoped
  instruction; host/runtime and direct-user precedence stays native, while
  repository precedence is nearest scoped instruction > root adapter > main
  core > role prompt;
- sources: user request, applicable instructions, repository files, fresh tool
  observations;
- protected resources: .git, .env files, credentials, secret stores, generated
  caches, and paths outside the project root;
- validation: discover native commands from project configuration; while none
  exist, run structural prompt checks and report missing runtime tests;
- network, destructive action, publication, messaging, and external effects:
  UNKNOWN until explicitly granted;
- trace level: QUIET.

Future commands and domain risks belong in this profile, not portable prompts.

## 14. Porting workflow

1. Copy the three prompt files unchanged.
2. Add the target platform instruction entry point.
3. Map roles only to capabilities that really exist.
4. Define root, instructions, sources, validation, protected resources, risks,
   and namespaced extensions in project_profile.
5. Start read-only.
6. Exercise direct, part-only, permission-denied, no-candidate, stale-revision,
   validation-failure, and human-gate scenarios.
7. Enable low-risk writes after conformance.
8. Enable network and external effects separately with explicit policy.

## 15. Verification and acceptance

Implementation is accepted when:

1. All deliverables exist as UTF-8 Markdown.
2. All prompts use protocol 2.0 and identical canonical names.
3. Only main owns accepted state, revision, events, and final decisions.
4. Part is read-only and returns CandidatePacket.
5. Work performs authority, scope, revision, protected-resource, and dirty-tree
   preflight before mutation.
6. UNKNOWN fails closed for safety-relevant actions.
7. Portable prompts contain no ForgeOps paths or domain rules.
8. Both adapters reference all three prompt paths.
9. The guide covers copying, configuration, dry run, failure tests, migration,
   and activation.
10. No contradictory event grammar, scoring fast path, implicit permission, or
    turn-count timeout remains.
11. README links resolve.
12. Another project can reuse the harness by copying three prompts and defining
    only its adapter/profile.

## 16. Scope boundary

This change adds repository instructions, three portable prompt contracts, a
porting guide, and README navigation only. It does not add application features,
choose a Python framework, or initialize Git. Repository initialization remains
an explicit operator decision.
