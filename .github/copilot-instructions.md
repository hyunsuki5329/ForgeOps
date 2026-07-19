# ForgeOps Copilot Adapter

This file is the GitHub Copilot entry point for the Portable Agent Harness v2.
Read and apply the root AGENTS.md project profile before selecting a role.

## Role mapping

- .github/agents/main_instruction.prompt.md: required orchestrator and accepted-state owner
- .github/agents/part_agent.prompt.md: read-only discovery and CandidatePacket
- .github/agents/work_agent.prompt.md: authorized execution and WorkResult

## Loading and precedence

1. Preserve host and direct-user precedence.
2. Apply the nearest scoped repository instruction.
3. Apply AGENTS.md as the canonical ForgeOps profile.
4. Apply main_instruction.prompt.md.
5. Apply part_agent.prompt.md for discovery or work_agent.prompt.md for approved
   execution.

Never load part or work without the main protocol. If AGENTS.md is unavailable,
mark project_profile.profile_status MISSING and fail closed for mutation and
external effects.

## Adapter rules

- Preserve and transport legacy v1 input unchanged to main.
- Main is the sole v1 normalization owner; this adapter never renames,
  restructures, or normalizes v1 fields.
- Emit protocol 2.0 internal packets only after main normalization.
- Map delegation only to tools actually exposed by the current Copilot runtime.
- Use sequential fallback when parallel isolation is unavailable.
- Do not expose internal packets in normal user replies; ForgeOps defaults to
  QUIET.
- Keep ForgeOps-specific values in AGENTS.md, not in the portable prompts.
- When main protocol changes, update this role mapping and
  docs/agent-harness/PORTING_GUIDE.md in the same change.
