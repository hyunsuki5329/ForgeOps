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
- authority: read_scope, read_resources, write_scope, write_resources,
  execute_scope, execute_commands, network_scope, network_hosts,
  destructive_actions, external_side_effects;
- control: route, operation_mode, response_phase, risk_level, evidence_floor,
  trace_level;
- budgets: format_repairs, part_attempts, work_attempts.

Adapter capability_defaults are discovery hints that main normalizes into
TaskPacket.capabilities; they never grant availability. Adapter trace_level
normalizes into TaskPacket.control.trace_level. The listed project_profile
fields are the only active top-level profile fields; adapters must reject an
unknown active top-level field and place project-specific data below a
namespaced project_profile.extensions entry.

Authority validation branches explicitly by scope. read_scope and write_scope
are NONE|PROJECT|NAMED_RESOURCES|UNKNOWN. PROJECT requires an empty companion
list and authorizes a RESOURCE identity only when its canonical resource_ref
resolves inside project_profile.root; named membership is not consulted.
NAMED_RESOURCES requires a non-empty read_resources or write_resources list and
case-sensitive exact membership. execute_scope is
NONE|NAMED_COMMANDS|UNKNOWN, and network_scope is NONE|NAMED_HOSTS|UNKNOWN;
project-wide execute or network authority does not exist. NAMED_COMMANDS and
NAMED_HOSTS require non-empty exact companion lists. NONE and UNKNOWN require an
empty companion list.

Named resource values are canonical project-root-relative literals. Every
authority companion is an original JSON array; null, scalar, or object values
are invalid, even for one item. Items are non-empty strings, ordinal-unique, and
wildcard-free. PROJECT read/write requires an empty list and an original JSON
boolean root_contained=true; NAMED_RESOURCES requires a non-empty list and exact
membership; NONE and UNKNOWN require an empty list.

Command authority names a validation-command ID whose command and
root-relative cwd match exactly. Canonical-NetworkHost is the single validator
for a NETWORK identity and every network_hosts member. It accepts a lower-case
ASCII DNS host of 1 through 253 characters with labels of 1 through 63
characters, optionally followed by one decimal port from 1 through 65535. It
rejects schemes, paths, queries, fragments, userinfo, uppercase, whitespace,
empty labels, edge hyphens, trailing dots, multiple colons, and out-of-range
ports. Empty values, duplicates, absolute paths, parent traversal, wildcard,
glob, regex, prefix/suffix matching, scheme inheritance, redirects, case
folding, trimming, path resolution, default-port expansion, or any other
implicit authority are invalid. An inconsistent scope/list pair is
CONTRACT_ERROR and UNKNOWN fails closed.

Closed-object property names are the original JSON names and are compared with
StringComparer.Ordinal. Case variants are not aliases and fail required-field
or exact-field validation.

Canonical records are:

- validation command: id, command, cwd, evidence_tier, required;
- candidate operation: read|create|update|delete|invoke;
- candidate action_type: READ_RESOURCE|CREATE_RESOURCE|UPDATE_RESOURCE|
  DELETE_RESOURCE|EXECUTE_COMMAND|CALL_NETWORK;
- candidate action_identity: a required discriminated union with identity_kind
  RESOURCE, COMMAND, or NETWORK;
- candidate confidence: JSON number from 0.0 through 1.0;
- acceptance result: criterion_id, status PASSED|FAILED|NOT_RUN,
  evidence_refs, notes;
- evidence: id, tier, type, source, observation, with optional exit_code,
  observed_revision, and observed_at;
- candidate outcome: CANDIDATES_PROPOSED|NO_CANDIDATE|BLOCKED_PROPOSAL|
  CONTRACT_ERROR.

Safety-relevant missing values are UNKNOWN. UNKNOWN never grants mutation,
network, credential access, publication, messaging, or destructive action.

## 8. Role boundaries

### Main

Main alone owns request normalization, including every v1-to-v2 field
normalization, routing, risk and authority evaluation, accepted state,
revisions, authoritative assertions and events, retry and gate decisions,
terminal status, and final user response. Adapters only transport and preserve
legacy input for main; they never rename or restructure it. Main verifies
referenced evidence instead of trusting a sub-agent success claim.

### Part

Part is strictly read-only. It validates TaskPacket, consumes only the canonical
project_profile fields, discovers applicable instructions and sources,
decomposes the objective, and returns CandidatePacket. Every CandidatePacket
has payload.outcome_code set to CANDIDATES_PROPOSED, NO_CANDIDATE,
BLOCKED_PROPOSAL, or CONTRACT_ERROR and has a payload.evidence catalog,
including no-candidate and error outcomes. Each candidate includes candidate_id,
action_type, action_identity, operation, expected effect, scope, rationale,
confidence, evidence references, dependencies, preconditions, proposed
verification, and risk notes. RESOURCE identity contains only resource_ref;
COMMAND contains only command_id, exact command, and exact root-relative cwd;
NETWORK contains only network_host. Part never updates accepted state.

### Work

Work mutates only when the task requests execution, action_type maps to the
required action_identity kind, forbidden identity fields are absent, and the
identity binds to the applicable authority branch. PROJECT read/write uses root
containment only; NAMED_RESOURCES uses exact membership; command and network
actions require exact NAMED_COMMANDS or NAMED_HOSTS authority. Work never
normalizes an identity to manufacture a match. The candidate must also be
approved, base_revision current, and protected-resource and dirty-workspace
checks passing.

WorkResult validation uses only trusted TaskPacket execution context supplied by
main. That context fixes protocol_version, task_id, correlation_id,
base_revision, validator-captured validationAt, approved_candidate_ids,
candidate_evidence_floor, and every required acceptance criterion ID and
evidence floor. WorkResult cannot supply or change this context. All context and
result list fields remain raw JSON arrays. The trusted acceptance criteria stay
as their original array of criterion_id and evidence_floor records; an ordinal
dictionary is only a runtime lookup.

candidate_evidence_floor, every trusted criterion evidence_floor, and every
WorkResult evidence tier are also original non-empty JSON strings. E0|E1|E2|E3
is a closed enum ranked only through a Dictionary constructed with
StringComparer.Ordinal after raw type validation. Arrays, null, and objects fail
with surface-specific *_TYPE_INVALID errors; lowercase, empty, and other
non-enum strings fail with the matching *_VALUE_INVALID errors. The surfaces are
candidate evidence floor, criterion evidence floor, and evidence tier.

WorkResult status is closed to SUCCEEDED|FAILED|PARTIAL|BLOCKED, candidate
decision to ACCEPTED|REJECTED|DEFERRED, acceptance status to
PASSED|FAILED|NOT_RUN, and proposed_transition to
SUCCEEDED|FAILED|PARTIAL|BLOCKED|WAITING_FOR_HUMAN. Exact compatibility is
SUCCEEDED -> SUCCEEDED, FAILED -> FAILED, PARTIAL -> PARTIAL, and
BLOCKED -> BLOCKED|WAITING_FOR_HUMAN.

Every trusted candidate ID, trusted criterion ID, and result candidate_id or
criterion_id is an original non-empty JSON string before any cast or lookup.
Uniqueness, membership, and lookup use HashSet and Dictionary instances with
StringComparer.Ordinal. Case-distinct IDs remain distinct; case folding,
trimming, numeric coercion, and other normalization are invalid.
candidate_results covers every trusted approved candidate exactly once with no
unknown, duplicate, or missing ID. acceptance_results covers every trusted
required criterion exactly once with no unknown, duplicate, or missing ID.
Every candidate and acceptance evidence_refs value retains its raw JSON array
type regardless of status or decision. Every ACCEPTED candidate and PASSED
criterion additionally has non-empty, unique evidence references that resolve
exactly once, are fresh under the closed evidence union, and meet the applicable
evidence floor. validation_summary is exact.
SUCCEEDED additionally requires every candidate ACCEPTED, every criterion
PASSED, zero failed or not_run results, and proposed_transition SUCCEEDED. Work
makes the smallest authorized change and returns WorkResult without updating
accepted state.
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

Every acceptance criterion records PASSED, FAILED, or NOT_RUN. A PASSED
criterion references non-empty fresh evidence at or above its trusted floor.
CandidatePacket payload.evidence is the canonical catalog for every candidate
outcome. Evidence IDs and every evidence_refs value are original JSON arrays of
non-empty ordinal-unique strings, and every evidence_ref resolves to exactly one
catalog entry. payload.evidence, inspected_sources when present or required,
and every nested evidence_refs value retain raw JSON-array type before any
wrapper or cast. Scalar, null, and object substitutes fail with
EVIDENCE_LIST_TYPE_INVALID, INSPECTED_SOURCES_TYPE_INVALID, and
EVIDENCE_REFS_TYPE_INVALID respectively.

Freshness is a closed union. file and diff evidence require only an original
JSON integer observed_revision equal to packet base_revision and forbid
observed_at. command, test, render, runtime, and approval evidence require only
observed_at in strict UTC yyyy-MM-dd'T'HH:mm:ss'Z' form and forbid
observed_revision. Main captures trusted validator-supplied validationAt once;
packet data cannot supply or change it. TIME evidence age is zero through 300
seconds inclusive. Validation uses stable priority: invalid type; missing the
variant's required field before checking a forbidden companion; mode mismatch;
invalid revision or timestamp; then stale or future.

NO_CANDIDATE means diagnostic discovery completed. inspected_sources is
required and is an original non-empty JSON array. Each entry contains exactly
source_ref, observation, and evidence_refs. source_ref is a non-empty canonical
project-root-relative reference, observation is non-empty, and evidence_refs is
an original non-empty JSON array of non-empty ordinal-unique strings. Each
reference resolves exactly once and is fresh. inspected_sources may be absent
only for CANDIDATES_PROPOSED, BLOCKED_PROPOSAL, or CONTRACT_ERROR; when present,
the same closed schema applies.

Every WorkResult candidate and acceptance evidence_refs value is a raw JSON
array regardless of decision or status. payload.evidence contains every ID
referenced by ACCEPTED candidate_results and PASSED acceptance_results; those
reference arrays are additionally non-empty and unique, resolve exactly once,
are fresh relative to trusted base_revision and validationAt, and reach
candidate_evidence_floor or that criterion's evidence_floor. Duplicate,
dangling, stale, future, wrong-mode,
multiply resolving, below-floor, scalar-array, malformed inspected-source, and
empty diagnostic discovery cases are invalid.

Assertions always use a stable status plus violations array. Events are
structured and owned by main; sub-agents return event_suggestions only. Runtime
timestamps are optional and never invented. Secrets and oversized logs are
excluded.
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
| Incompatible protocol | Candidate outcome CONTRACT_ERROR; one safe format repair |
| Missing read capability or authority | Candidate outcome BLOCKED_PROPOSAL; never broaden scope |
| Completed search with no defensible candidate | Candidate outcome NO_CANDIDATE |
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
| last_committed_ref | payload.accepted_state.checkpoint_ref |
| proposal commit | main acceptance and revision increment |
| part/work state_update | proposed_transition only |
| text event_logs | structured events |
| conditional assertion blocks | stable status and violations |
| demo_impact | project_profile.extensions risk rule |
| file-count fast path | post-discovery scope signal only |
| turn-count timeout | runtime-observed timeout metadata |

Adapters may temporarily transport v1 input, but they preserve it unchanged for
main. Main is the sole v1 normalization owner and normalizes directly to the
canonical v2 payload before routing. New outputs are v2 only.

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
- validation: extensions.forgeops.validation_discovery lists project
  configuration files used to discover native commands; while none exist, run
  structural prompt checks and report missing runtime tests;
- network, destructive action, publication, messaging, and external effects:
  UNKNOWN until explicitly granted;
- trace level: QUIET.

Future commands and domain risks belong in this profile, not portable prompts.

## 14. Porting workflow

1. Copy the three prompt files unchanged.
2. Add the target platform instruction entry point.
3. Map roles only to capabilities that really exist.
4. Define only the canonical root, profile_type, profile_status,
   instruction_files, source_of_truth, validation_commands,
   protected_resources, risk_rules, and namespaced extensions fields in
   project_profile.
5. Define all four authority companion lists explicitly and start read-only.
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
6. UNKNOWN fails closed for safety-relevant actions, and authority scope/list
   pairs reject wildcards, duplicates, mismatches, and implicit authority.
7. Every CandidatePacket outcome includes a unique payload.evidence catalog and
   every evidence reference resolves exactly once.
8. PROJECT versus NAMED authority is validated by separate branches and no
   project-wide execute or network scope exists.
9. Every candidate has a valid action_type/action_identity discriminated union;
   closed-object property names use original JSON spelling with
   StringComparer.Ordinal, so case variants, hybrids, missing identities,
   forbidden fields, and normalization attempts fail executable
   positive/negative fixture checks.
10. Canonical-NetworkHost accepts a lower-case DNS host with optional port
    1..65535 and rejects every noncanonical host variant.
11. Authority companion values, payload.evidence, evidence_refs,
    inspected_sources, candidate_results, and acceptance_results retain their
    original JSON array type. payload.evidence, inspected_sources when present
    or required, and nested evidence_refs reject scalar, null, and object
    substitutes before wrapping with EVIDENCE_LIST_TYPE_INVALID,
    INSPECTED_SOURCES_TYPE_INVALID, and EVIDENCE_REFS_TYPE_INVALID; every Work
    candidate and acceptance refs value is checked regardless of decision or
    status.
12. Freshness uses the closed REVISION/TIME union and trusted validationAt; a
    packet cannot choose the clock or mix modes, and missing required metadata
    takes priority over forbidden companion metadata.
13. inspected_sources has exact fields, canonical source_ref, non-empty
    observation and refs, and exact fresh reference resolution.
14. WorkResult requires original non-empty string candidate and criterion IDs,
    plus original non-empty JSON strings for candidate/criterion evidence floors
    and evidence tiers; it applies ordinal uniqueness, membership, lookup, and
    closed E0|E1|E2|E3 ranking so case-distinct IDs stay distinct, covers every
    trusted ID exactly once, closes every result enum, enforces compatibility and
    evidence floors, computes exact summary counts, and rejects inconsistent
    SUCCEEDED.
15. The semantic fixture executes 14 positive and 92 negative cases with zero
    unexpected pass or failure, plus three positive packet examples.
16. Portable prompts contain no ForgeOps paths or domain rules.
17. Both adapters reference all three prompt paths.
18. The guide covers copying, configuration, dry run, failure tests, migration,
    activation, and the complete semantic conformance matrix.
19. Active project_profile fields are canonical; project-only fields are
    namespaced under extensions.
20. Main alone normalizes v1 and owns
    payload.accepted_state.checkpoint_ref.
21. No contradictory event grammar, scoring fast path, implicit permission, or
    turn-count timeout remains.
22. README links to all three prompts and every link resolves.
23. Another project can reuse the harness by copying three prompts and defining
    only its adapter/profile.
## 16. Scope boundary

This change adds repository instructions, three portable prompt contracts, a
porting guide, and README navigation only. It does not add application features,
choose a Python framework, or initialize Git. Repository initialization remains
an explicit operator decision.
