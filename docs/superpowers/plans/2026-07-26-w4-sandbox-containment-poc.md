# W4-3 Sandbox Containment PoC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the VG-008 sandbox contract and a Docker-backed E3 PoC that fails closed on image provenance, containment, egress, quota, or teardown uncertainty.

**Architecture:** A pure evaluator consumes closed runtime observations and is tested with a deterministic fake observer. A separate Docker observer may produce E3 evidence only after an approved local capability preflight and a digest-pinned, signature/provenance-verified local image; unavailable capability produces `NOT_RUN`, never a simulated pass.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `argparse`/`dataclasses`/`ipaddress`/`json`/`subprocess`/`tempfile`/`unittest`, Docker CLI as an optional approved local runtime

## Global Constraints

- WBS-009 and both registered VG-001 commands must be fresh PASSED before WBS-010 can complete.
- Contract tests may use `FakeRuntimeObserver`, but only the exact `VerifiedDockerRuntimeObserver` type with `evidence_kind="runtime"` and a closed local verifier provenance object can produce E3 VG-008 PASSED results.
- Do not pull, build, sign, push, download, or discover images automatically. Use one pre-provisioned local digest-pinned image and a separately observed runtime profile.
- Every Docker invocation uses an argument list with `shell=False`, bounded timeout, exact executable `docker`, exact image reference, and no inherited authority through redirects or discovered destinations.
- Provisioning is denied before `docker run` when digest, signature, issuer, provenance, rootless mode, or required runtime capability is missing or unknown.
- The sandbox must deny privileged mode, host PID/IPC/network, device mounts, Docker socket, live host mounts, direct DNS/socket egress, forbidden address ranges, redirects, and quota escape.
- Terminal and cancel observations require zero process, mount, lease, transient-secret, and workspace residue.
- Raw Docker output, environment, host paths, image labels, secrets, and stack traces never enter public results.
- Do not Git add/commit/push/PR, publish, access the network, or run Docker commands until one batched user approval covers the exact preflight and registered runtime commands.

---

## File Structure

- Create `contracts/forgeops-sandbox-contract/1.0/schema.json`: closed runtime profile, case, and observation schema.
- Create `fixtures/forgeops-sandbox-security/suite.json`: exact image, containment/egress, quota, and teardown catalogs.
- Create `fixtures/forgeops-sandbox-security/runtime-profile.example.json`: public-safe unavailable profile template.
- Create `tools/sandbox_security/__init__.py`, `tools/sandbox_security/runtime.py`, and `tools/sandbox_security/verify.py`.
- Create `tests/sandbox_security/__init__.py` and `tests/sandbox_security/test_verify.py`.
- Modify `AGENTS.md`: register three E3 commands and `forgeops-sandbox-security` profile.
- Generate `artifacts/runtime/sandbox-runtime-profile.json` only from approved local observation.
- Generate three VG-008 result artifacts.
- Modify WBS/RTM/quality documents only after all three registered commands pass at E3.

### Task 1: Define closed runtime observations and a deterministic fake observer

**Files:**

- Create: `contracts/forgeops-sandbox-contract/1.0/schema.json`
- Create: `fixtures/forgeops-sandbox-security/suite.json`
- Create: `fixtures/forgeops-sandbox-security/runtime-profile.example.json`
- Create: `tools/sandbox_security/__init__.py`
- Create: `tools/sandbox_security/runtime.py`
- Create: `tests/sandbox_security/__init__.py`
- Create: `tests/sandbox_security/test_verify.py`

**Interfaces:**

- `RuntimeProfile`: `runtime`, `available`, `rootless`, `image_ref`, `image_digest`, `signature_verified`, `issuer`, `provenance_ref`, `observed_at`.
- `RuntimeObservation`: `case_id`, `evidence_kind`, `provision_calls`, `network_calls`, `write_calls`, `root_uid`, `rootfs_read_only`, `cap_drop_all`, `no_new_privileges`, `forbidden_mounts`, `forbidden_devices`, `direct_socket_calls`, `direct_dns_calls`, `proxy_calls`, `connected_addresses`, `redirects`, `quota_exceeded`, `residue`.
- `RuntimeObserver.observe(case: dict) -> RuntimeObservation`.
- `FakeRuntimeObserver(observations: dict[str, RuntimeObservation])` returns only preloaded observations and never calls a process.

- [ ] **Step 1: Write failing schema and fake-observer tests**

```python
class SandboxSchemaTests(unittest.TestCase):
    def test_every_object_is_closed(self):
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))

class FakeObserverTests(unittest.TestCase):
    def test_unknown_case_never_falls_back_to_runtime(self):
        observer = runtime.FakeRuntimeObserver({})
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_RUNTIME_UNAVAILABLE"):
            observer.observe({"id": "unknown"})
        self.assertEqual(0, observer.process_calls)
```

- [ ] **Step 2: Run focused tests and observe RED**

Run: `python -m unittest tests.sandbox_security.test_verify.SandboxSchemaTests tests.sandbox_security.test_verify.FakeObserverTests -v`

Expected: FAIL because schema and runtime module do not exist.

- [ ] **Step 3: Create the closed schema**

Use exact enums:

```json
{
  "runtime": ["docker"],
  "evidence_kind": ["test", "runtime"],
  "case_kind": ["image_provenance", "containment", "egress", "quota", "teardown"],
  "result_status": ["PASSED", "FAILED", "NOT_RUN"]
}
```

`residue` must contain exactly non-negative integer fields `processes`, `mounts`, `leases`, `transient_secrets`, and `workspaces`. `connected_addresses` is an array of unique IP address strings; `forbidden_mounts` and `forbidden_devices` are non-negative integers.

- [ ] **Step 4: Create exact ordered case catalogs**

```python
IMAGE_CASES = (
    ("positive-signed-digest", "PASSED"),
    ("negative-tag-only", "SANDBOX_IMAGE_PROVENANCE_INVALID"),
    ("negative-signature-unverified", "SANDBOX_IMAGE_PROVENANCE_INVALID"),
    ("negative-issuer-mismatch", "SANDBOX_IMAGE_PROVENANCE_INVALID"),
)
CONTAINMENT_CASES = (
    ("positive-rootless-readonly", "PASSED"),
    ("negative-root-user", "SANDBOX_CONTAINMENT_VIOLATION"),
    ("negative-rootfs-writable", "SANDBOX_CONTAINMENT_VIOLATION"),
    ("negative-docker-socket", "SANDBOX_CONTAINMENT_VIOLATION"),
    ("negative-host-device", "SANDBOX_CONTAINMENT_VIOLATION"),
)
EGRESS_CASES = (
    ("positive-exact-proxy-destination", "PASSED"),
    ("negative-direct-dns", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-direct-socket", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-loopback", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-private-address", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-metadata-address", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-redirect", "SANDBOX_EGRESS_VIOLATION"),
)
QUOTA_CASES = (("positive-within-quota", "PASSED"), ("negative-quota-escape", "SANDBOX_QUOTA_VIOLATION"))
TEARDOWN_CASES = (
    ("positive-zero-residue", "PASSED"),
    ("negative-process-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
    ("negative-mount-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
    ("negative-secret-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
    ("negative-workspace-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
)
```

Every negative case declares exact expected `provision_calls`, `network_calls`, and `write_calls`; pre-provision failures require all three zero.

- [ ] **Step 5: Implement `FakeRuntimeObserver` and run focused tests**

```python
class FakeRuntimeObserver:
    def __init__(self, observations):
        self._observations = observations
        self.process_calls = 0

    def observe(self, case):
        if case["id"] not in self._observations:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        return copy.deepcopy(self._observations[case["id"]])
```

Run: `python -m unittest tests.sandbox_security.test_verify.SandboxSchemaTests tests.sandbox_security.test_verify.FakeObserverTests -v`

Expected: PASS.

### Task 2: Implement fail-closed sandbox evaluation

**Files:**

- Create: `tools/sandbox_security/verify.py`
- Modify: `tests/sandbox_security/test_verify.py`

**Interfaces:**

- `class SandboxError(Exception)` exposes `.code` only.
- `validate_runtime_profile(profile: dict, validation_at: str) -> None`.
- `evaluate_observation(case: dict, observation: dict) -> None`.
- `is_forbidden_address(value: str) -> bool` uses `ipaddress.ip_address` without DNS resolution.
- `run_cases(command_id: str, suite: dict, observer: RuntimeObserver) -> list[dict]`.

- [ ] **Step 1: Write failing deny-precedence and zero-effect tests**

```python
def test_bad_signature_precedes_provisioning(self):
    profile = valid_profile()
    profile["signature_verified"] = False
    with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_IMAGE_PROVENANCE_INVALID"):
        verify.validate_runtime_profile(profile, "2026-07-26T00:01:00Z")
    self.assertEqual(0, self.observer.process_calls)

def test_private_connected_address_is_egress_violation(self):
    case = egress_case("negative-private-address")
    observation = valid_observation(case["id"])
    observation["connected_addresses"] = ["10.0.0.1"]
    with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_EGRESS_VIOLATION"):
        verify.evaluate_observation(case, observation)
```

- [ ] **Step 2: Run evaluator tests and observe RED**

Run: `python -m unittest tests.sandbox_security.test_verify.SandboxEvaluatorTests -v`

Expected: FAIL until profile and observation validators exist.

- [ ] **Step 3: Implement stable evaluation order**

```python
def evaluate_observation(case, observation):
    validate_observation_schema(observation)
    if observation["root_uid"] == 0 or not observation["rootfs_read_only"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")
    if not observation["cap_drop_all"] or not observation["no_new_privileges"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")
    if observation["forbidden_mounts"] or observation["forbidden_devices"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")
    if observation["direct_dns_calls"] or observation["direct_socket_calls"]:
        raise SandboxError("SANDBOX_EGRESS_VIOLATION")
    if observation["redirects"] or any(is_forbidden_address(v) for v in observation["connected_addresses"]):
        raise SandboxError("SANDBOX_EGRESS_VIOLATION")
    if observation["quota_exceeded"]:
        raise SandboxError("SANDBOX_QUOTA_VIOLATION")
    if any(observation["residue"].values()):
        raise SandboxError("SANDBOX_TEARDOWN_INCOMPLETE")
```

For image-provenance cases, validate the runtime profile before requesting an observation. Do not use DNS or sockets in the evaluator.

- [ ] **Step 4: Enforce E3 provenance and observed-effect contracts**

A case may be public `PASSED` in a registered VG-008 result only when `observation["evidence_kind"] == "runtime"`. Fake/test observations remain valid unit-test evidence but the CLI must return `NOT_RUN` with `SANDBOX_RUNTIME_UNAVAILABLE` when no runtime observer is available.

- [ ] **Step 5: Run all pure sandbox tests**

Run: `python -m unittest tests.sandbox_security.test_verify -v`

Expected: PASS without invoking Docker; all negative categories and zero-effect expectations match.

### Task 3: Implement the approved Docker observer and capability preflight

**Files:**

- Modify: `tools/sandbox_security/runtime.py`
- Modify: `tests/sandbox_security/test_verify.py`
- Generate after approval: `artifacts/runtime/sandbox-runtime-profile.json`

**Interfaces:**

- `DockerRuntimeObserver(executable: str, image_ref: str, timeout_seconds: int = 30)` is injectable and never E3-trusted.
- `VerifiedDockerRuntimeObserver(executable: str, image_ref: str, verifier: LocalImageVerifier, timeout_seconds: int = 30)` is the exact E3 candidate type; `LocalImageVerifier.verify()` returns a closed `LocalVerificationProvenance` object, never a callback mapping or image-label claim.
- `_run(arguments: list[str]) -> subprocess.CompletedProcess[str]` always uses `shell=False`, `capture_output=True`, `text=True`, `check=False`, and an integer timeout from 1 through 30 seconds inclusive.
- `inspect_capability() -> dict` returns the closed runtime profile without raw command output.
- `observe(case: dict) -> dict` runs only registered probe kinds.

- [ ] **Step 1: Write failing subprocess-boundary tests using an injected runner**

```python
def test_docker_observer_uses_argument_list_and_never_shell(self):
    calls = []
    def runner(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return completed(stdout="{}", returncode=0)
    observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=runner)
    observer.inspect_capability()
    self.assertIsInstance(calls[0][0], list)
    self.assertFalse(calls[0][1]["shell"])
    self.assertEqual(30, calls[0][1]["timeout"])

def test_non_digest_image_is_rejected_before_runner(self):
    observer = runtime.DockerRuntimeObserver("docker", "forgeops/sandbox:latest", runner=fail_if_called)
    with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_IMAGE_PROVENANCE_INVALID"):
        observer.inspect_capability()
```

- [ ] **Step 2: Run Docker boundary tests and observe RED**

Run: `python -m unittest tests.sandbox_security.test_verify.DockerObserverTests -v`

Expected: FAIL until the Docker observer exists.

- [ ] **Step 3: Implement the exact Docker command allowlist**

Allow only these argument prefixes:

```python
ALLOWED_PREFIXES = (
    ("docker", "version", "--format", "{{json .Server}}"),
    ("docker", "image", "inspect"),
    ("docker", "run", "--rm"),
    ("docker", "inspect"),
    ("docker", "rm", "-f"),
)
```

E3 eligibility is bound once at construction in private state: the exact
`VerifiedDockerRuntimeObserver` type, immutable digest image reference and
validated provenance hash, the original `subprocess.run` identity, exact
closed `LocalImageVerifier` class, frozen full probe argv, and original class
`observe`/preflight helper identities must all still match at evaluation.
Any instance shadow or mutation of image, verifier, probe, allowlist, or run
helpers denies E3. A timeout during the detached probe marks teardown residue
uncertain and returns a closed non-success result before any E3 claim.

The `docker run` branch must append fixed hardening flags: `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--pids-limit=64`, `--memory=128m`, `--cpus=0.5`, `--network=none`, one bounded tmpfs, and the exact digest ref. Reject any case-supplied raw flag or command.

- [ ] **Step 4: Request one batched approval before local runtime commands**

The approval request must list: `docker version`, `docker image inspect <exact-digest-ref>`, and the three registered Python VG-008 commands that may invoke bounded `docker run/inspect`. It must state that no image pull/build/push, network access, privileged mode, host mount, device, or external publication is authorized.

- [ ] **Step 5: Observe capability or record `NOT_RUN`**

If approval is denied, Docker is missing, rootless mode is false, the digest image is absent, signature/provenance cannot be verified, or runtime output is malformed, write a closed runtime profile with `available=false` and public failure category only. Do not fabricate an observed profile or continue to provisioning.

- [ ] **Step 6: Run Docker boundary tests**

Run: `python -m unittest tests.sandbox_security.test_verify.DockerObserverTests -v`

Expected: PASS entirely with injected subprocess results.

### Task 4: Register three VG-008 commands, generate evidence, and synchronize WBS-010

**Files:**

- Modify: `tools/sandbox_security/verify.py`
- Modify: `tests/sandbox_security/test_verify.py`
- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-008-image-provenance-result.json`
- Generate: `artifacts/verification/vg-008-containment-egress-result.json`
- Generate: `artifacts/verification/vg-008-teardown-result.json`
- Modify: `docs/project/wbs.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`

**Interfaces:**

- Profile ID: `forgeops-sandbox-security`.
- Command IDs: `image-provenance-negative`, `containment-egress-negative`, `teardown-negative`.
- CLI flags: `--schema`, `--suite`, `--runtime-profile`, `--runtime`, `--result`, `--command-id`; `--runtime` is exactly `docker`.
- Result status: `PASSED|FAILED|NOT_RUN`; E3 claims require runtime observations.

- [ ] **Step 1: Write failing registered path and unavailable-runtime result tests**

```python
def test_missing_runtime_profile_is_not_run_not_passed(self):
    result = verify.safe_not_run("teardown-negative", "SANDBOX_RUNTIME_UNAVAILABLE")
    self.assertEqual("NOT_RUN", result["status"])
    self.assertNotIn("cases", result)

def test_command_result_pair_is_exact(self):
    args = registered_namespace(command_id="teardown-negative", result=IMAGE_RESULT)
    with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_RUNNER_CONTRACT_INVALID"):
        verify.validate_registered_paths(args)
```

- [ ] **Step 2: Implement exact CLI/result mapping and atomic writes**

```python
TRUSTED_RESULTS = {
    "image-provenance-negative": "artifacts/verification/vg-008-image-provenance-result.json",
    "containment-egress-negative": "artifacts/verification/vg-008-containment-egress-result.json",
    "teardown-negative": "artifacts/verification/vg-008-teardown-result.json",
}
```

Public results contain only gate/profile/command/status/time, schema/suite/runtime-profile hashes, counts, public case categories, E3 assertion, and residue/effect counters.

- [ ] **Step 3: Register the exact E3 commands only after capability preflight succeeds**

Do not add these commands to active required validation in `AGENTS.md` while the Docker capability profile is absent or records `available=false`. In that state, retain the planned command definitions in the quality plan, emit closed `NOT_RUN` evidence, and keep WBS-010 incomplete. Register the commands and profile atomically only after the approved preflight proves that all runtime prerequisites are available.

```text
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-image-provenance-result.json --command-id image-provenance-negative
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-containment-egress-result.json --command-id containment-egress-negative
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-teardown-result.json --command-id teardown-negative
```

- [ ] **Step 4: Run unit tests before runtime execution**

Run: `python -m unittest discover -s tests/sandbox_security -p "test_*.py" -v`

Expected: PASS with fake/injected observers and no Docker process call outside explicit Docker observer tests.

- [ ] **Step 5: Run the three commands only under the batched approval**

Expected when prerequisites are satisfied: exit 0, `PASSED`, E3 runtime assertion true, all negative effects zero, and teardown residue all zero.

Expected when prerequisites are absent: non-zero or designated not-ready exit, closed `NOT_RUN` result with `SANDBOX_RUNTIME_UNAVAILABLE`; no WBS completion.

- [ ] **Step 6: Synchronize evidence-backed documents**

Set WBS-010 to `WBS_DONE` only if all three registered artifacts are fresh `PASSED` at E3 and their hashes match current inputs. Otherwise leave it `WBS_IN_PROGRESS` or `WBS_BLOCKED` with the exact capability/evidence reason. Update only mapped RTM/quality rows; do not modify WBS-011/012.

- [ ] **Step 7: Run final checks**

Run full sandbox tests, inspect all three JSON results, independently verify hashes and zero-residue assertions, then run `git diff --check` and `git status --short`.

Expected: unit tests pass; runtime results truthfully reflect observed capability; no staged, committed, published, or unrelated changes.
