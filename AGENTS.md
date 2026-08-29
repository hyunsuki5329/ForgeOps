# ForgeOps Agent Instructions

## Scope

These instructions apply to the entire ForgeOps repository unless a nearer
AGENTS.md narrows the scope.

Host/system instructions and direct user instructions retain native precedence.
Within this repository, precedence is:

1. nearest scoped AGENTS.md;
2. this root adapter and project profile;
3. .github/agents/main_instruction.prompt.md;
4. the selected part or work role prompt.

A lower layer cannot weaken a higher layer. The project profile may tighten,
but not weaken, protocol 2.0 safety invariants.

## Harness entry points

- Main/orchestration: .github/agents/main_instruction.prompt.md
- Part/read-only analysis: .github/agents/part_agent.prompt.md
- Work/authorized execution: .github/agents/work_agent.prompt.md

Use main for every task. Use part for repository-grounded discovery, review, or
diagnosis. Use work only for explicitly authorized changes or operations.

## ForgeOps project profile

~~~yaml
protocol_version: "2.0"
project_profile:
  root: "."
  profile_type: software
  profile_status: LOADED
  instruction_files:
    - AGENTS.md
    - .github/copilot-instructions.md
    - .github/agents/main_instruction.prompt.md
    - .github/agents/part_agent.prompt.md
    - .github/agents/work_agent.prompt.md
  source_of_truth:
    - direct_user_request
    - applicable_instruction_files
    - repository_files
    - fresh_tool_observations
  validation_commands:
    - id: bridge-schema-fixture
      command: python tools/contract_bridge/verify.py --schema contracts/product-task-contract/1.0/schema.json --suite fixtures/product-task-contract-bridge/suite.json --result artifacts/verification/vg-002-contract-bridge-result.json --report artifacts/reviews/w1-contract-bridge-checkpoint.html
      cwd: "."
      evidence_tier: E2
      required: true
    - id: state-transition-fixture
      command: python tools/state_contract/verify.py --schema contracts/forgeops-state-contract/1.0/schema.json --suite fixtures/forgeops-state-contract/state-suite.json --result artifacts/verification/vg-003-state-transition-result.json --command-id state-transition-fixture
      cwd: "."
      evidence_tier: E2
      required: true
    - id: event-order-fixture
      command: python tools/state_contract/verify.py --schema contracts/forgeops-state-contract/1.0/schema.json --suite fixtures/forgeops-state-contract/state-suite.json --result artifacts/verification/vg-003-event-order-result.json --command-id event-order-fixture
      cwd: "."
      evidence_tier: E2
      required: true
    - id: replay-contract-negative
      command: python tools/replay_contract/verify.py --schema contracts/forgeops-replay-contract/1.0/schema.json --suite fixtures/forgeops-replay-contract/suite.json --result artifacts/verification/vg-003-replay-contract-result.json
      cwd: "."
      evidence_tier: E2
      required: true
    - id: resource-authority-negative
      command: python tools/policy_contract/verify.py resource --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-authority-resource/suite.json --result artifacts/verification/vg-005-resource-authority-result.json --command-id resource-authority-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: protected-read-negative
      command: python tools/policy_contract/verify.py resource --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-authority-resource/suite.json --result artifacts/verification/vg-005-protected-read-result.json --command-id protected-read-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: command-network-negative
      command: python tools/policy_contract/verify.py command-network --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-authority-command-network/suite.json --result artifacts/verification/vg-006-command-network-result.json --command-id command-network-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: approval-negative-fixture
      command: python tools/policy_contract/verify.py approval --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-approval-policy/suite.json --result artifacts/verification/vg-007-approval-policy-result.json --command-id approval-negative-fixture
      cwd: "."
      evidence_tier: E2
      required: true
    - id: interface-contract-fixture
      command: python tools/interface_contract/verify.py --openapi contracts/forgeops-api/1.0/openapi.yaml --event-schema contracts/forgeops-event/1.0/schema.json --manifest-schema contracts/forgeops-run-manifest/1.0/schema.json --api-version-suite fixtures/forgeops-api/version-envelope-suite.json --api-boundary-suite fixtures/forgeops-api/data-control-suite.json --event-suite fixtures/forgeops-event-contract/suite.json --manifest-suite fixtures/forgeops-run-manifest/suite.json --result artifacts/verification/vg-004-interface-contract-result.json --command-id interface-contract-fixture
      cwd: "."
      evidence_tier: E2
      required: true
    - id: evidence-positive-negative
      command: python tools/evidence_contract/verify.py --schema contracts/forgeops-evidence-contract/1.0/schema.json --suite fixtures/forgeops-evidence-contract/suite.json --result artifacts/verification/vg-023-evidence-contract-result.json --command-id evidence-positive-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: extension-provenance
      command: python tools/evidence_contract/verify.py --schema contracts/forgeops-evidence-contract/1.0/schema.json --suite fixtures/forgeops-evidence-contract/suite.json --result artifacts/verification/vg-023-extension-provenance-result.json --command-id extension-provenance
      cwd: "."
      evidence_tier: E2
      required: true
    - id: protocol-conformance
      command: python tools/foundation_conformance/verify.py --manifest fixtures/forgeops-foundation/source-manifest.json --suite fixtures/forgeops-foundation/suite.json --result artifacts/verification/vg-001-protocol-conformance-result.json --command-id protocol-conformance
      cwd: "."
      evidence_tier: E2
      required: true
    - id: sample-fixture
      command: python tools/foundation_conformance/verify.py --manifest fixtures/forgeops-foundation/source-manifest.json --suite fixtures/forgeops-foundation/suite.json --result artifacts/verification/vg-001-sample-fixture-result.json --command-id sample-fixture
      cwd: "."
      evidence_tier: E2
      required: true
    - id: secret-surface-negative
      command: python tools/secret_artifact_security/verify.py --schema contracts/forgeops-secret-artifact-contract/1.0/schema.json --suite fixtures/forgeops-secret-artifact-security/suite.json --result artifacts/verification/vg-009-secret-surface-result.json --command-id secret-surface-negative
      cwd: "."
      evidence_tier: E3
      required: true
    - id: artifact-isolation-negative
      command: python tools/secret_artifact_security/verify.py --schema contracts/forgeops-secret-artifact-contract/1.0/schema.json --suite fixtures/forgeops-secret-artifact-security/suite.json --result artifacts/verification/vg-009-artifact-isolation-result.json --command-id artifact-isolation-negative
      cwd: "."
      evidence_tier: E3
      required: true
    - id: phase0-exit-gate
      command: python tools/phase_exit/verify.py --schema contracts/forgeops-phase-exit-contract/1.0/schema.json --suite fixtures/forgeops-phase-exit/phase-0-suite.json --result artifacts/verification/phase-0-exit-result.json --report artifacts/reviews/phase-0-exit-report.md --command-id phase0-exit-gate
      cwd: "."
      evidence_tier: E3
      required: true
    - id: image-provenance-negative
      command: python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-image-provenance-result.json --command-id image-provenance-negative
      cwd: "."
      evidence_tier: E3
      required: true
    - id: containment-egress-negative
      command: python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-containment-egress-result.json --command-id containment-egress-negative
      cwd: "."
      evidence_tier: E3
      required: true
    - id: teardown-negative
      command: python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-teardown-result.json --command-id teardown-negative
      cwd: "."
      evidence_tier: E3
      required: true
    - id: snapshot-identity
      command: python tools/snapshot_context/verify.py snapshot-baseline --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-snapshot-baseline/suite.json --result artifacts/verification/vg-010-snapshot-identity-result.json --command-id snapshot-identity
      cwd: "."
      evidence_tier: E2
      required: true
    - id: baseline-retrieval-repeat
      command: python tools/snapshot_context/verify.py snapshot-baseline --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-snapshot-baseline/suite.json --result artifacts/verification/vg-010-baseline-retrieval-result.json --command-id baseline-retrieval-repeat
      cwd: "."
      evidence_tier: E2
      required: true
    - id: context-provenance
      command: python tools/snapshot_context/verify.py context --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-context-security/suite.json --result artifacts/verification/vg-011-context-provenance-result.json --command-id context-provenance
      cwd: "."
      evidence_tier: E2
      required: true
    - id: injection-negative
      command: python tools/snapshot_context/verify.py context --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-context-security/suite.json --result artifacts/verification/vg-011-injection-negative-result.json --command-id injection-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: main-part-work-main
      command: python tools/local_vertical/verify.py --schema contracts/forgeops-local-vertical/1.0/schema.json --product-schema contracts/product-task-contract/1.0/schema.json --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-local-vertical/suite.json --result artifacts/verification/vg-012-local-vertical-result.json --command-id main-part-work-main
      cwd: "."
      evidence_tier: E2
      required: true
    - id: task-checks
      command: python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-task-checks-result.json --command-id task-checks
      cwd: "."
      evidence_tier: E2
      required: true
    - id: budget-cancel-negative
      command: python tools/lifecycle_trace/verify.py --schema contracts/forgeops-lifecycle-trace/1.0/schema.json --suite fixtures/forgeops-lifecycle-trace/suite.json --result artifacts/verification/vg-014-budget-cancel-result.json --command-id budget-cancel-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: no-progress-stop
      command: python tools/lifecycle_trace/verify.py --schema contracts/forgeops-lifecycle-trace/1.0/schema.json --suite fixtures/forgeops-lifecycle-trace/suite.json --result artifacts/verification/vg-014-no-progress-result.json --command-id no-progress-stop
      cwd: "."
      evidence_tier: E2
      required: true
    - id: trace-manifest-completeness
      command: python tools/lifecycle_trace/verify.py --schema contracts/forgeops-lifecycle-trace/1.0/schema.json --suite fixtures/forgeops-lifecycle-trace/suite.json --result artifacts/verification/vg-015-trace-manifest-result.json --command-id trace-manifest-completeness
      cwd: "."
      evidence_tier: E2
      required: true
    - id: external-write-negative
      command: python tools/lifecycle_trace/verify.py --schema contracts/forgeops-lifecycle-trace/1.0/schema.json --suite fixtures/forgeops-lifecycle-trace/suite.json --result artifacts/verification/vg-015-external-write-result.json --command-id external-write-negative
      cwd: "."
      evidence_tier: E2
      required: true
    - id: regression-checks
      command: python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-regression-checks-result.json --command-id regression-checks
      cwd: "."
      evidence_tier: E2
      required: true
    - id: verification-anti-tamper
      command: python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-verification-anti-tamper-result.json --command-id verification-anti-tamper
      cwd: "."
      evidence_tier: E2
      required: true
    - id: phase1-security-negative
      command: python tools/phase1_safety/verify.py --schema contracts/forgeops-phase1-safety/1.0/schema.json --suite fixtures/forgeops-phase1-safety/suite.json --result artifacts/verification/phase-1-security-negative-result.json --command-id phase1-security-negative
      cwd: "."
      evidence_tier: E3
      required: true
    - id: phase1-evidence-freshness
      command: python tools/phase1_safety/verify.py --schema contracts/forgeops-phase1-safety/1.0/schema.json --suite fixtures/forgeops-phase1-safety/suite.json --result artifacts/verification/phase-1-evidence-freshness-result.json --command-id phase1-evidence-freshness
      cwd: "."
      evidence_tier: E3
      required: true
    - id: phase1-safety-gate
      command: python tools/phase1_safety/verify.py --schema contracts/forgeops-phase1-safety/1.0/schema.json --suite fixtures/forgeops-phase1-safety/suite.json --result artifacts/verification/phase-1-safety-gate-result.json --report-md artifacts/reviews/phase-1-safety-scorecard.md --report-html artifacts/reviews/phase-1-safety-scorecard.html --command-id phase1-safety-gate
      cwd: "."
      evidence_tier: E3
      required: true
  protected_resources:
    - .git/**
    - .env
    - .env.*
    - "**/*credential*"
    - "**/*secret*"
    - paths_outside_project_root
  risk_rules:
    - destructive_changes_require_approval
    - credentials_and_private_data_require_approval
    - publication_and_messaging_require_approval
    - material_cost_requires_approval
    - scope_expansion_requires_approval
  extensions:
    forgeops:
      verification_profiles:
        - id: forgeops-contract-bridge
          command_ids:
            - bridge-schema-fixture
        - id: forgeops-state-contract
          command_ids:
            - state-transition-fixture
            - event-order-fixture
            - replay-contract-negative
        - id: forgeops-authority-resource
          command_ids:
            - resource-authority-negative
            - protected-read-negative
        - id: forgeops-authority-command-network
          command_ids:
            - command-network-negative
        - id: forgeops-approval-policy
          command_ids:
            - approval-negative-fixture
        - id: forgeops-interface-contract
          command_ids:
            - interface-contract-fixture
        - id: forgeops-evidence-contract
          command_ids:
            - evidence-positive-negative
            - extension-provenance
        - id: forgeops-foundation-conformance
          command_ids:
            - protocol-conformance
            - sample-fixture
        - id: forgeops-secret-artifact-security
          command_ids:
            - secret-surface-negative
            - artifact-isolation-negative
        - id: forgeops-phase0-exit
          command_ids:
            - phase0-exit-gate
        - id: forgeops-sandbox-security
          command_ids:
            - image-provenance-negative
            - containment-egress-negative
            - teardown-negative
        - id: forgeops-snapshot-baseline
          command_ids:
            - snapshot-identity
            - baseline-retrieval-repeat
        - id: forgeops-context-security
          command_ids:
            - context-provenance
            - injection-negative
        - id: forgeops-local-vertical
          command_ids:
            - main-part-work-main
        - id: forgeops-patch-verification
          command_ids:
            - task-checks
            - regression-checks
            - verification-anti-tamper
        - id: forgeops-lifecycle-budget
          command_ids:
            - budget-cancel-negative
            - no-progress-stop
        - id: forgeops-trace-manifest
          command_ids:
            - trace-manifest-completeness
            - external-write-negative
        - id: forgeops-phase1-safety
          command_ids:
            - phase1-security-negative
            - phase1-evidence-freshness
            - phase1-safety-gate
      validation_discovery:
        - pyproject.toml
        - uv.lock
        - requirements.txt
        - setup.cfg
        - tox.ini
        - noxfile.py
        - package.json
        - Makefile
capability_defaults:
  filesystem_read: UNKNOWN
  filesystem_write: UNKNOWN
  command_execute: UNKNOWN
  delegation: UNKNOWN
  network: UNKNOWN
  external_side_effects: UNKNOWN
trace_level: QUIET
~~~

Capabilities are discovered from the active runtime for each task.
capability_defaults are discovery hints only; main normalizes observed values
into TaskPacket.capabilities and UNKNOWN never becomes AVAILABLE by default.
The adapter trace_level maps to TaskPacket.control.trace_level.

An empty validation_commands list means discover project-native commands from
project_profile.extensions.forgeops.validation_discovery; it does not mean
validation is optional. A populated validation command record uses id, command,
cwd, evidence_tier, and required. The only active project_profile top-level
fields are root, profile_type, profile_status, instruction_files,
source_of_truth, validation_commands, protected_resources, risk_rules, and
extensions. Unknown active fields are rejected; project-specific values are
namespaced below extensions.

## Repository operating rules

- Use project-root-relative paths in internal packets.
- Preserve user changes and inspect repository status before mutation.
- Do not modify .git internals except for an explicit Git operation requested by
  the user.
- Do not expose .env, credentials, secrets, or private data.
- Do not use destructive reset or force push unless the user explicitly names
  that exact operation and its target.
- Do not publish, message, deploy, or create cost without explicit authority.
- Report successful completion only with fresh evidence at the assigned floor.
- Keep internal harness packets hidden at QUIET trace level.
