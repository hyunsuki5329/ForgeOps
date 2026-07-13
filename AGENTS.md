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
  validation_commands: []
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
