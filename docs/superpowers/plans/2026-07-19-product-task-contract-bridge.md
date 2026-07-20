# Product Task Contract Schema and TaskPacket Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement W1 tasks 2 and 3 as a closed Product Task Contract schema 1.0 and a precise non-grant Contract→TaskPacket bridge contract.

**Architecture:** Store the executable data shape under `contracts/product-task-contract/1.0/` and keep trust/mapping semantics in a focused document under `docs/contracts/`. Register the contract in the document map and mark WBS-002 in progress, while leaving mapper execution, fixtures, VG-002 and WBS completion to task 4.

**Tech Stack:** JSON Schema Draft 2020-12, Markdown, PowerShell JSON and structural validation

## Global Constraints

- Preserve all pre-existing user changes in the dirty worktree.
- Do not perform dependency installation, network, publication, destructive, staging, commit, push, or PR operations.
- Schema ID is `urn:forgeops:product-task-contract:1.0`; `schema_id` is `forgeops.task-contract`; `schema_version` is `1.0`.
- Every object schema is closed with `additionalProperties: false`.
- Contract data never grants capability, authority, approval, accepted state, route, evidence floor, Harness budget, or execution.
- `intent.source_issue` remains namespaced untrusted provenance and never enters canonical `source_of_truth`.
- Set WBS-002 to `WBS_IN_PROGRESS`; do not set WBS-002 done or VG-002 passed.

---

### Task 1: Product Task Contract Schema 1.0

**Files:**

- Create: `contracts/product-task-contract/1.0/schema.json`

**Interfaces:**

- Consumes: Product Task Contract fields in `docs/handoff/forgeops-full-handoff.md` and bridge constraints in `docs/architecture/system-architecture.md`.
- Produces: JSON Schema `$id=urn:forgeops:product-task-contract:1.0` for task 3 documentation and task 4 fixtures.

- [x] **Step 1: Verify the schema target is absent**

Run: `if(Test-Path 'contracts/product-task-contract/1.0/schema.json'){throw 'Schema already exists'};'SCHEMA_TARGET_ABSENT'`

Expected: `SCHEMA_TARGET_ABSENT`.

- [x] **Step 2: Create the closed schema**

Create `contracts/product-task-contract/1.0/schema.json` with the approved top-level fields and these exact rules:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:forgeops:product-task-contract:1.0",
  "title": "ForgeOps Product Task Contract 1.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_id", "schema_version", "artifact_id", "artifact_version", "task_id", "repository", "intent", "acceptance_criteria", "constraints", "verification_policy", "risk", "budget", "approval_policy"],
  "properties": {
    "schema_id": {"const": "forgeops.task-contract"},
    "schema_version": {"const": "1.0"},
    "artifact_id": {"type": "string", "minLength": 1},
    "artifact_version": {"type": "integer", "minimum": 1},
    "task_id": {"type": "string", "minLength": 1},
    "repository": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "snapshot_commit", "target_branch"],
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "snapshot_commit": {"type": "string", "minLength": 1},
        "target_branch": {"type": "string", "minLength": 1}
      }
    },
    "intent": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "summary"],
      "properties": {
        "type": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "summary": {"type": "string", "minLength": 1},
        "source_issue": {"type": "string", "minLength": 1}
      }
    },
    "acceptance_criteria": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "description", "verification"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "description": {"type": "string", "minLength": 1},
          "verification": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}
        }
      }
    },
    "constraints": {"type": "array", "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
    "verification_policy": {
      "type": "object",
      "additionalProperties": false,
      "required": ["profile_id", "baseline_command_ids", "required_command_ids", "require_new_regression_test"],
      "properties": {
        "profile_id": {"type": "string", "minLength": 1},
        "baseline_command_ids": {"type": "array", "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
        "required_command_ids": {"type": "array", "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
        "require_new_regression_test": {"type": "boolean"}
      }
    },
    "risk": {
      "type": "object",
      "additionalProperties": false,
      "required": ["initial_level", "reasons"],
      "properties": {
        "initial_level": {"enum": ["low", "medium", "high", "critical"]},
        "reasons": {"type": "array", "uniqueItems": true, "items": {"type": "string", "minLength": 1}}
      }
    },
    "budget": {
      "type": "object",
      "additionalProperties": false,
      "required": ["max_repair_attempts", "max_tool_calls", "max_shell_commands", "max_runtime_seconds", "max_model_cost_usd"],
      "properties": {
        "max_repair_attempts": {"type": "integer", "minimum": 0},
        "max_tool_calls": {"type": "integer", "minimum": 0},
        "max_shell_commands": {"type": "integer", "minimum": 0},
        "max_runtime_seconds": {"type": "integer", "minimum": 0},
        "max_model_cost_usd": {"type": "number", "minimum": 0}
      }
    },
    "approval_policy": {
      "type": "object",
      "additionalProperties": false,
      "required": ["plan", "dependency_change", "remote_push", "pr_draft", "merge_or_deploy"],
      "properties": {
        "plan": {"$ref": "#/$defs/approval_requirement"},
        "dependency_change": {"$ref": "#/$defs/approval_requirement"},
        "remote_push": {"$ref": "#/$defs/approval_requirement"},
        "pr_draft": {"$ref": "#/$defs/approval_requirement"},
        "merge_or_deploy": {"$ref": "#/$defs/approval_requirement"}
      }
    }
  },
  "$defs": {
    "approval_requirement": {"enum": ["not_required", "required", "never_without_explicit_high_risk_approval"]}
  }
}
```

- [x] **Step 3: Parse and structurally validate the schema**

Run a PowerShell recursive walk that asserts JSON parsing, exact IDs, all 13 top-level required fields, absence of canonical control properties, and `additionalProperties=false` for every object schema.

Expected: `PRODUCT_TASK_CONTRACT_SCHEMA_OK` with zero open object schemas.

### Task 2: Contract→TaskPacket Bridge Contract

**Files:**

- Create: `docs/contracts/product-task-contract-to-taskpacket.md`

**Interfaces:**

- Consumes: Task 1 schema properties and Protocol 2.0 TaskPacket canonical fields.
- Produces: exact `DIRECT_DATA`, `TRUSTED_RESOLUTION`, `NAMESPACED_PROVENANCE`, and `NEVER_FROM_CONTRACT` rules for task 4 mapper fixtures.

- [x] **Step 1: Verify the bridge target is absent**

Run: `if(Test-Path 'docs/contracts/product-task-contract-to-taskpacket.md'){throw 'Bridge already exists'};'BRIDGE_TARGET_ABSENT'`

Expected: `BRIDGE_TARGET_ABSENT`.

- [x] **Step 2: Create the bridge contract**

The document must contain: scope/version; trust model; the four mapping classes; a row for every schema top-level field; the exact namespaced destinations; the never-from-Contract canonical control list; eight-step processing flow; stable errors `CONTRACT_SCHEMA_INVALID`, `CONTRACT_VERSION_UNSUPPORTED`, `CONTRACT_INTENT_UNMAPPED`, `CONTRACT_CRITERION_DUPLICATE`, `CONTRACT_COMMAND_UNTRUSTED`, `CONTRACT_CONTROL_FIELD_FORBIDDEN`, `CONTRACT_MONOTONICITY_VIOLATION`, `CONTRACT_PROVENANCE_INVALID`; and task-4 verification obligations.

The field table must map `intent.source_issue` only to `project_profile.extensions.forgeops.task_contract.intent.source_issue`, `budget` only to `project_profile.extensions.forgeops.product_budget`, and `approval_policy` only to `project_profile.extensions.forgeops.task_contract.approval_policy`. It must explicitly forbid copying these values into `source_of_truth`, `risk_rules`, Harness budgets, authority, capability, approval, or state.

- [x] **Step 3: Verify schema/bridge coverage and non-grant text**

Parse schema top-level properties and assert that each name appears in the bridge document. Assert all four mapping classes, eight stable errors, canonical non-grant fields, source issue namespacing, command exact-match and risk/gate monotonicity.

Expected: `PRODUCT_TASK_CONTRACT_BRIDGE_OK` with 13/13 schema fields covered.

### Task 3: Documentation Registration and Partial WBS State

**Files:**

- Modify: `docs/README.md`
- Modify: `docs/project/wbs.md`

**Interfaces:**

- Consumes: verified schema and bridge documents.
- Produces: discoverable bridge documentation and WBS-002 `WBS_IN_PROGRESS`, while WBS-003 remains not started and VG-002 remains not run.

- [x] **Step 1: Add bridge discoverability without adding an owner document**

Add the bridge document immediately after the Harness baseline inventory in the recommended reading order. Add a paragraph beside the existing baseline-inventory non-owner note stating that the bridge is a WBS-002 contract artifact, not a ninth owner document or runtime implementation.

- [x] **Step 2: Change only WBS-002 to WBS_IN_PROGRESS**

Replace the WBS-002 row status cell `WBS_NOT_STARTED` with `WBS_IN_PROGRESS`. Preserve WBS-001 `WBS_DONE`, WBS-003 `WBS_NOT_STARTED`, and every VG result.

- [x] **Step 3: Run complete verification and inspect diff**

Verify JSON structure, every bridge link, 13/13 mapping coverage, two README bridge links, WBS state boundaries, UTF-8, no trailing whitespace, final newlines, and exact scoped diff rows.

Expected: `PRODUCT_TASK_CONTRACT_TASKS_2_3_OK`; `VG-002` remains `NOT_RUN` in RTM; no Git mutation or unrelated file change.
