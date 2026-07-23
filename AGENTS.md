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
