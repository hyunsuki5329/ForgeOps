# W2 COMMAND and NETWORK Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VG-006 preflight coverage for COMMAND id/command/cwd triples and NETWORK host[:port] identities without executing commands or opening sockets.

**Architecture:** This plan extends the W2 shared authority-policy runner with separate COMMAND and NETWORK branches. Public-safe trusted catalogs and a spy adapter show that all normalization and destination-safety failures stop before a process or network action.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, JSON

## Global Constraints

- COMMAND requires case-sensitive exact `id`, `command`, canonical root-relative `cwd`; raw command and `PROJECT` execute are forbidden.
- NETWORK permits only lower-case ASCII DNS `host[:port]` exact named membership; no scheme, path, query, userinfo, whitespace, uppercase, wildcard, default-port expansion or redirect inheritance.
- Private, loopback, link-local and metadata destinations deny even when a host literal is otherwise authorized.
- The fixture never launches a process, resolves DNS, opens a socket or follows redirects.

---

### Task 1: Add command/network suite and failing preflight tests

**Files:**

- Create: `fixtures/forgeops-authority-command-network/suite.json`
- Create: `tests/policy_contract/test_command_network.py`

**Interfaces:**

- COMMAND identity: `{identity_kind: "COMMAND", command_id, command, cwd}`.
- NETWORK identity: `{identity_kind: "NETWORK", network_host}`.
- `evaluate_command_network(request: dict) -> tuple[str, SpyAdapter]`.

- [ ] **Step 1: Write the failing no-dispatch tests**

```python
def test_raw_command_and_private_network_are_denied_before_adapter(self):
    for request, code in [(raw_command_request(), "COMMAND_RAW_FORBIDDEN"), (private_host_request(), "NETWORK_DESTINATION_FORBIDDEN")]:
        result, adapter = VERIFY.evaluate_command_network(request)
        self.assertEqual(code, result)
        self.assertEqual(0, adapter.calls)
```

- [ ] **Step 2: Run tests and define the catalog**

Run: `python -m unittest tests/policy_contract/test_command_network.py -v`  
Expected: FAIL before the command-network branch exists. Add valid triple/host cases plus ID, command, cwd mismatch, raw command, PROJECT execute, all forbidden host syntax, redirect inheritance and prohibited destination cases.

### Task 2: Implement exact COMMAND and NETWORK branches

**Files:**

- Modify: `tools/policy_contract/verify.py`
- Modify: `tests/policy_contract/test_command_network.py`

**Interfaces:**

- `validate_command(request: dict, catalog: dict) -> str`.
- `validate_network(request: dict, catalog: dict) -> str`.

- [ ] **Step 1: Add exact-triple and host-syntax tests**

```python
def test_command_requires_all_three_exact_values(self):
    with self.assertRaisesRegex(VERIFY.PolicyError, "COMMAND_IDENTITY_MISMATCH"):
        VERIFY.validate_command(command_request(cwd="./"), trusted_catalog())

def test_network_rejects_url_not_host_literal(self):
    with self.assertRaisesRegex(VERIFY.PolicyError, "NETWORK_IDENTITY_INVALID"):
        VERIFY.validate_network(network_request("https://api.example.com"), trusted_catalog())
```

- [ ] **Step 2: Implement validators before the adapter call**

```python
def validate_command(request, catalog):
    require_named_command_scope(request)
    record = catalog["commands"].get(request["identity"]["command_id"])
    if record is None or (record["command"], record["cwd"]) != (request["identity"]["command"], request["identity"]["cwd"]):
        raise PolicyError("COMMAND_IDENTITY_MISMATCH")
    return "PASSED"

def validate_network(request, catalog):
    host = request["identity"]["network_host"]
    require_canonical_host_port_literal(host)
    require_exact_named_host(host, request["authority"])
    require_safe_destination(host, request["destination_class"])
    return "PASSED"
```

- [ ] **Step 3: Run the full policy regression set**

Run: `python -m unittest tests/policy_contract/test_resource.py tests/policy_contract/test_command_network.py -v`  
Expected: PASS; all negative command/network cases report adapter count `0`.

### Task 3: Register and execute VG-006

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-006-command-network-result.json`

- [ ] **Step 1: Register `command-network-negative` under profile `forgeops-authority-command-network`**

Use the exact shared runner path, command ID, E2 tier and required flag in `AGENTS.md`.

- [ ] **Step 2: Execute the registered command verbatim**

Expected: exit 0; each expected stable category matches and no process/network adapter call is observed.

- [ ] **Step 3: Inspect the scoped diff**

Run `git diff --check` and `git status --short`. Do not modify WBS-005, stage, commit, push or use network.
