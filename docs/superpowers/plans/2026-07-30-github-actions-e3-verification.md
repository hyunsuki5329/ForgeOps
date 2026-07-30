# GitHub Actions 2-job E3 Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보호된 기본 브랜치의 수동 GitHub Actions 실행에서 signed digest 이미지를 별도 rootless Docker runner로 검증하고, VG-008 세 command와 Phase 0 Exit가 사용할 수 있는 서명된 E3 증빙을 생성한다.

**Architecture:** `build-sign` job은 이미지를 GHCR에 push하고 GitHub OIDC로 digest를 서명한다. 새 runner의 `verify-e3` job은 exact workflow identity와 digest signature를 확인하고, 고정 helper process로 rootless runtime probe를 수행한 뒤 attestation을 서명한다. ForgeOps importer와 기존 evaluator는 서명·schema·hash·freshness를 다시 검증하며, 불확실한 입력은 기존 `NOT_RUN` 경로로 닫는다.

**Tech Stack:** Python 3 표준 라이브러리, `jsonschema`, `unittest`, Docker Engine rootless mode, GitHub Actions, GHCR, Cosign 3.0.6

## Global Constraints

- 외부 E3는 `.github/workflows/vg-008-e3.yml`이 저장소의 보호된 기본 브랜치에 존재하고 `workflow_dispatch`로 실행된 경우에만 발급한다.
- `github.ref`는 저장소 기본 브랜치의 정확한 ref여야 하고 `github.ref_protected`는 `true`여야 한다.
- OIDC issuer는 정확히 `https://token.actions.githubusercontent.com`이고 certificate identity는 해당 저장소, workflow 경로, 기본 브랜치 ref의 정확한 조합이어야 한다.
- 이미지는 `ghcr.io`의 단일 repository package로만 push하며 실행·검증은 image name 뒤에 `@sha256:`와 64자리 lowercase hex digest가 붙은 형태만 허용한다.
- `build-sign` 권한은 `contents: read`, `packages: write`, `id-token: write`이고 `verify-e3` 권한은 `contents: read`, `packages: read`, `id-token: write`이다.
- GHCR package visibility를 변경하거나 공개 전환하지 않는다. 현재 repository token으로 private package를 사용할 수 없으면 권한을 넓히지 않고 실패한다.
- 모든 외부 Action은 이 계획에 기록된 full commit SHA로 고정한다.
- rootless, cgroup v2/systemd quota, signature, identity, digest, cleanup 중 하나라도 관찰되지 않으면 E3 `PASSED`를 만들지 않는다.
- helper는 caller 정의 command, Docker flag, mount, device, socket 또는 network destination을 받지 않는다. 허용 입력은 exact digest image reference와 검증된 GitHub run identity뿐이다.
- 위험한 negative configuration은 provisioning 전에 거부하며, host mount/device/socket을 실제로 노출하지 않는다.
- raw Docker output, environment, token, certificate 원문, host absolute path, container log와 source payload는 public artifact에 포함하지 않는다.
- 기존 300초 freshness window를 유지한다. 오래된 signed artifact를 fresh `READY`로 재생하지 않는다.
- workflow는 commit, push, PR, release, deployment 또는 repository 파일 자동 수정을 하지 않는다.
- 현재 dirty worktree의 사용자 변경을 보존한다. Git commit 단계는 사용자가 Git 변경을 별도로 승인한 경우에만 실행한다.

## File Structure

- `contracts/forgeops-e3-attestation/1.0/schema.json`: 외부 E3 attestation, capability, observation, terminal residue의 closed JSON Schema.
- `fixtures/forgeops-e3-attestation/suite.json`: importer의 positive/negative deterministic fixture catalog.
- `tools/sandbox_security/e3_attestation.py`: Cosign bundle 검증, exact identity 검증, atomic import와 public manifest 생성.
- `tools/sandbox_security/e3_helper.py`: rootless Docker에 대해 네 가지 고정 lifecycle을 수행하고 closed attestation을 생성하는 별도 process entry point.
- `tools/sandbox_security/e3_probe.py`: probe image 내부에서 containment, egress, quota 사실만 JSON으로 출력하는 고정 entry point.
- `tools/sandbox_security/e3_image/Dockerfile`: 최종 digest 서명 대상인 최소 probe image.
- `tools/sandbox_security/setup_rootless.sh`: GitHub Linux runner의 rootless daemon과 cgroup capability를 fail-closed로 설정·확인.
- `tools/sandbox_security/e3_artifact.py`: 업로드 allowlist, public manifest, 다운로드 artifact import를 담당.
- `tools/sandbox_security/runtime.py`: 검증된 imported observation만 제공하는 sealed `AttestedRuntimeObserver` 추가.
- `tools/sandbox_security/verify.py`: signed import가 있으면 E3 결과를 만들고, 없거나 유효하지 않으면 기존 `NOT_RUN`을 유지.
- `contracts/forgeops-sandbox-contract/1.0/schema.json`: runtime observation에 `observation_mode`를 추가.
- `fixtures/forgeops-sandbox-security/suite.json`: pre-provision denial case의 expected effect count를 0으로 정정.
- `.github/workflows/vg-008-e3.yml`: 승인된 두 job workflow.
- `tests/sandbox_security/test_e3_attestation.py`: schema, identity, Cosign argv, tamper, freshness, import tests.
- `tests/sandbox_security/test_e3_helper.py`: fixed command graph, safe negative denial, cleanup, public projection tests.
- `tests/sandbox_security/test_e3_workflow.py`: workflow trigger, permissions, job count, Action pin, artifact allowlist tests.
- `tests/sandbox_security/test_verify.py`: imported observer와 successful VG-008 CLI regression tests.
- `AGENTS.md`: 세 VG-008 validation command와 `forgeops-sandbox-security` profile 등록.
- `docs/quality/verification-and-evaluation-plan.md`, `docs/project/wbs.md`, `docs/project/requirements-traceability-matrix.md`: 외부 E3가 실제 통과한 뒤에만 W4 완료 증빙으로 갱신.

---

### Task 1: Signed E3 Attestation Contract and Importer

**Files:**
- Create: `contracts/forgeops-e3-attestation/1.0/schema.json`
- Create: `fixtures/forgeops-e3-attestation/suite.json`
- Create: `tools/sandbox_security/e3_attestation.py`
- Create: `tests/sandbox_security/test_e3_attestation.py`

**Interfaces:**
- Consumes: exact GitHub repository/run identity, `e3-attestation.json`, Cosign bundle, sandbox schema and suite hashes.
- Produces: `ExpectedIdentity`, `verify_signed_attestation`, `import_signed_attestation`, `artifacts/runtime/sandbox-runtime-profile.json`, `artifacts/runtime/sandbox-runtime-observations.json`, `artifacts/runtime/sandbox-e3-import-receipt.json`.

- [ ] **Step 1: Write failing closed-schema and identity tests**

Create `tests/sandbox_security/test_e3_attestation.py` with fixtures that contain no real owner, token or path. Use this exact public identity model:

```python
identity = ExpectedIdentity(
    repository="example/forgeops",
    repository_id="123456",
    default_branch="main",
    source_sha="a" * 40,
    workflow_sha="b" * 40,
    run_id="1001",
    run_attempt=1,
    image_ref="ghcr.io/example/forgeops-e3@sha256:" + "c" * 64,
    image_digest="sha256:" + "c" * 64,
)
assert identity.certificate_identity == (
    "https://github.com/example/forgeops/.github/workflows/"
    "vg-008-e3.yml@refs/heads/main"
)
```

Tests must assert:

- every object schema has `additionalProperties: false`;
- exactly 23 registered case observations are present once each;
- issuer, repository, repository ID, source/workflow SHA, run ID/attempt, image ref/digest and certificate identity are exact;
- malformed digest, uppercase SHA, duplicate case ID, extra property, stale/future timestamp and non-zero terminal residue are rejected;
- raw keys matching `token`, `secret`, `credential`, `environment`, `stdout`, `stderr`, `log`, `certificate_pem`, `certificate_chain`, `private_path` are rejected from the public document; the closed `certificate_identity` field remains allowed;
- tampering with either attestation or bundle after verification is detected by the receipt hashes.

- [ ] **Step 2: Run the tests and confirm the intended failure**

Run:

```powershell
python -m unittest tests.sandbox_security.test_e3_attestation -v
```

Expected: import failure because `tools.sandbox_security.e3_attestation` and its schema do not exist.

- [ ] **Step 3: Add the closed attestation schema and fixture catalog**

The top-level schema must require exactly these fields:

```python
ATTESTATION_REQUIRED = (
    "attestation_version",
    "repository",
    "repository_id",
    "workflow_ref",
    "workflow_sha",
    "source_sha",
    "run_id",
    "run_attempt",
    "issuer",
    "certificate_identity",
    "image_ref",
    "image_digest",
    "observed_at",
    "capabilities",
    "input_hashes",
    "observations",
    "terminal_residue",
)

CAPABILITY_REQUIRED = (
    "rootless",
    "cgroup_version",
    "cgroup_driver",
    "memory_controller",
    "pids_controller",
    "cpu_controller",
)

INPUT_HASH_REQUIRED = (
    "sandbox_schema_sha256",
    "sandbox_suite_sha256",
    "runtime_profile_sha256",
    "helper_sha256",
    "probe_sha256",
)

RESIDUE_REQUIRED = (
    "processes",
    "mounts",
    "leases",
    "transient_secrets",
    "workspaces",
)
```

Set `attestation_version` to const `1.0`, `issuer` to const `https://token.actions.githubusercontent.com`, SHA fields to 40 lowercase hex, hash fields to 64 lowercase hex, `run_attempt` to an integer of at least 1, `observations` to exactly 23 items and every terminal residue field to const `0`. `runtime_profile_sha256` is the SHA-256 of the canonical runtime profile deterministically derived from the attestation identity, capability and time fields. The positive fixture supplies the 23 observation objects by the exact case order in `fixtures/forgeops-sandbox-security/suite.json`; it must not use an empty observation array.

`observations` uses the existing `RuntimeObservation` field names plus required `observation_mode`, whose enum is `RUNTIME_EXECUTED|PREPROVISION_DENIED`. The schema enforces 23 items, unique `case_id`, public-safe strings, exact timestamp format and non-negative counters. Uniqueness across case IDs is also checked in Python because JSON Schema `uniqueItems` cannot express property uniqueness.

- [ ] **Step 4: Implement exact identity and Cosign verification**

Implement these public interfaces in `tools/sandbox_security/e3_attestation.py`. `ProcessRunner` is a module-local protocol whose call parameters exactly match the `subprocess.run` keyword arguments used below, and `DEFAULT_PROCESS_RUNNER` is captured from `subprocess.run` at import time:

```python
OIDC_ISSUER = "https://token.actions.githubusercontent.com"

@dataclass(frozen=True)
class ExpectedIdentity:
    repository: str
    repository_id: str
    default_branch: str
    source_sha: str
    workflow_sha: str
    run_id: str
    run_attempt: int
    image_ref: str
    image_digest: str

    @property
    def workflow_ref(self) -> str:
        return f"refs/heads/{self.default_branch}"

    @property
    def certificate_identity(self) -> str:
        return (
            f"https://github.com/{self.repository}/.github/workflows/"
            f"vg-008-e3.yml@{self.workflow_ref}"
        )


verify_signed_attestation(
    attestation_path: Path,
    bundle_path: Path,
    expected: ExpectedIdentity,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
) -> dict[str, Any]

import_signed_attestation(
    attestation_path: Path,
    bundle_path: Path,
    expected: ExpectedIdentity,
    output_root: Path,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
) -> dict[str, Path]
```

`verify_signed_attestation` validates bytes before invoking exactly:

```python
[
    "cosign", "verify-blob",
    "--bundle", str(bundle_path),
    "--certificate-identity", expected.certificate_identity,
    "--certificate-oidc-issuer", OIDC_ISSUER,
    str(attestation_path),
]
```

Invoke with `shell=False`, `check=False`, `capture_output=True`, `text=True`, `timeout=30`. Never include subprocess output in errors or artifacts. Non-zero exit maps to `E3_SIGNATURE_INVALID`; identity mismatch maps to `E3_IDENTITY_INVALID`; schema/hash/freshness mismatch maps to stable `E3_ATTESTATION_INVALID`, `E3_HASH_MISMATCH` or `E3_EVIDENCE_STALE`.

- [ ] **Step 5: Implement atomic import**

`import_signed_attestation` writes only the three fixed files below, using temporary files in the destination directory followed by `os.replace`:

```python
outputs = {
    "profile": output_root / "artifacts/runtime/sandbox-runtime-profile.json",
    "observations": output_root / "artifacts/runtime/sandbox-runtime-observations.json",
    "receipt": output_root / "artifacts/runtime/sandbox-e3-import-receipt.json",
}
```

The profile keeps the existing schema. Its `provenance_ref` is a `sha256:` value over the canonical public provenance tuple `(image_ref, image_digest, issuer, certificate_identity)`; `runtime_profile_sha256` must equal the bytes atomically written by the importer. This avoids a self-referential attestation hash while binding the profile to the verified image identity. The receipt contains only `receipt_version`, `attestation_sha256`, `bundle_sha256`, exact public identity fields, `observed_at`, `verification_kind` and output hashes. `verification_kind` is `runtime` only when the unmodified default `subprocess.run` executed Cosign; an injected test runner produces `test` and can never support E3.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m unittest tests.sandbox_security.test_e3_attestation -v
```

Expected: all tests pass without invoking network, Docker or a real Cosign binary.

- [ ] **Step 7: Prepare the task commit only if Git authority was granted**

```powershell
git add -- contracts/forgeops-e3-attestation/1.0/schema.json fixtures/forgeops-e3-attestation/suite.json tools/sandbox_security/e3_attestation.py tests/sandbox_security/test_e3_attestation.py
git diff --cached --check
git commit -m "feat: add signed E3 attestation importer"
```

Without explicit Git authority, do not execute these commands.

---

### Task 2: Fixed Rootless Runtime Helper and Probe Image

**Files:**
- Create: `tools/sandbox_security/e3_helper.py`
- Create: `tools/sandbox_security/e3_probe.py`
- Create: `tools/sandbox_security/e3_image/Dockerfile`
- Create: `tools/sandbox_security/setup_rootless.sh`
- Create: `tests/sandbox_security/test_e3_helper.py`
- Modify: `contracts/forgeops-sandbox-contract/1.0/schema.json`
- Modify: `fixtures/forgeops-sandbox-security/suite.json`

**Interfaces:**
- Consumes: `ExpectedIdentity`, exact digest image ref, sandbox schema and suite.
- Produces: `collect_e3_attestation(identity, schema_path, suite_path, output_path) -> int` and a closed `e3-attestation.json`.

- [ ] **Step 1: Write failing command-graph and zero-effect tests**

Create tests that inject a recording runner and assert:

```python
commands = fixed_command_graph(
    image_ref="ghcr.io/example/forgeops-e3@sha256:" + "c" * 64,
    resource_token="1001-1",
)
serialized = "\n".join(" ".join(command) for command in commands)
assert "--privileged" not in serialized
assert "/var/run/docker.sock" not in serialized
assert "--device" not in serialized
assert "--pid=host" not in serialized
assert "--network=host" not in serialized
```

Also assert every command is an immutable sequence of strings, uses `docker` without a shell, has a 1–30 second timeout, and operates only on resource names beginning `forgeops-e3-1001-1-`. Unknown image form, resource token, case ID or injected flag is rejected before runner call count changes.

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
python -m unittest tests.sandbox_security.test_e3_helper -v
```

Expected: import failure because the helper and probe files do not exist.

- [ ] **Step 3: Add observation mode and correct pre-provision effect counts**

Extend `RuntimeObservation` with:

```json
"observation_mode": {
  "enum": ["RUNTIME_EXECUTED", "PREPROVISION_DENIED"]
}
```

For image provenance denials, forbidden host mount/device/socket, privileged/host namespace requests and quota-disable requests, set expected provision/network/write calls to `0`. Positive containment, internal-proxy egress and teardown canary cases retain observed non-zero counts. Update catalog tests to assert that every `PREPROVISION_DENIED` negative has all three effects at zero.

- [ ] **Step 4: Implement the probe image**

Use this Dockerfile shape:

```dockerfile
FROM python:3.13.5-alpine3.22
RUN addgroup -g 1000 forgeops && adduser -D -u 1000 -G forgeops forgeops
COPY tools/sandbox_security/e3_probe.py /opt/forgeops/e3_probe.py
USER 1000:1000
ENTRYPOINT ["python3", "/opt/forgeops/e3_probe.py"]
```

`e3_probe.py` accepts only `containment`, `egress-client`, `egress-proxy`, `quota` and `teardown-canary` from the fixed `FORGEOPS_PROBE_MODE` environment value. It writes one compact JSON object to stdout. It never prints environment variables, request payloads or exception text. Unknown mode exits `2` with the single public code `E3_PROBE_MODE_INVALID` on stderr.

- [ ] **Step 5: Implement four bounded helper lifecycles**

Implement the following exact interfaces, using the `ProcessRunner` protocol from Task 1:

```python
fixed_command_graph(
    image_ref: str,
    resource_token: str,
) -> Sequence[Sequence[str]]

collect_e3_attestation(
    identity: ExpectedIdentity,
    schema_path: Path,
    suite_path: Path,
    output_path: Path,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
) -> int
```

The four lifecycles are:

1. preflight: verify digest-only ref, rootless security option, cgroup v2/systemd and memory/pids/cpu controllers; project dangerous negative configurations as `PREPROVISION_DENIED` with zero effects;
2. containment/quota: one non-root, read-only, cap-drop ALL, no-new-privileges container with exact PID 64, memory 128 MiB, CPU 0.5 and tmpfs 16 MiB limits;
3. egress: one `--internal` network, one fixed local proxy container and one client container; direct external DNS/socket/redirect/private/metadata attempts cannot leave the internal network;
4. teardown: bounded canary container/network/volume objects are observed, removed in `finally`, then checked a second time for zero terminal residue.

The helper may map these four lifecycles to all 23 suite cases, but may not invent runtime success: each projected field must originate from a parsed Docker inspect/probe result or a pre-provision deny decision. Malformed or missing output yields `available=false` and `SANDBOX_RUNTIME_UNAVAILABLE`; cleanup uncertainty yields `SANDBOX_TEARDOWN_INCOMPLETE`.

- [ ] **Step 6: Add fail-closed rootless setup**

`setup_rootless.sh` must use `set -euo pipefail`, refuse root execution, require `dockerd-rootless-setuptool.sh`, `newuidmap`, `newgidmap`, subordinate UID/GID ranges and cgroup v2, then run:

```bash
dockerd-rootless-setuptool.sh install --force
systemctl --user start docker
docker context use rootless
docker info --format '{{json .SecurityOptions}}'
docker info --format '{{.CgroupVersion}} {{.CgroupDriver}}'
```

It succeeds only when security options contain rootless and the second observation is exactly `2 systemd`. It must not disable the system daemon, edit `/etc`, expose a TCP Docker socket or install from an unverified curl script.

- [ ] **Step 7: Run focused tests**

Run:

```powershell
python -m unittest tests.sandbox_security.test_e3_helper tests.sandbox_security.test_verify.SandboxSchemaTests tests.sandbox_security.test_verify.SandboxCatalogTests -v
```

Expected: all tests pass; no real Docker command runs on the local Windows host.

- [ ] **Step 8: Prepare the task commit only if Git authority was granted**

```powershell
git add -- tools/sandbox_security/e3_helper.py tools/sandbox_security/e3_probe.py tools/sandbox_security/e3_image/Dockerfile tools/sandbox_security/setup_rootless.sh tests/sandbox_security/test_e3_helper.py contracts/forgeops-sandbox-contract/1.0/schema.json fixtures/forgeops-sandbox-security/suite.json
git diff --cached --check
git commit -m "feat: add fixed rootless E3 probes"
```

Without explicit Git authority, do not execute these commands.

---

### Task 3: Imported E3 Observer and VG-008 Result Generation

**Files:**
- Modify: `tools/sandbox_security/runtime.py`
- Modify: `tools/sandbox_security/verify.py`
- Modify: `tests/sandbox_security/test_verify.py`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: imported profile, observations and receipt from Task 1.
- Produces: `AttestedRuntimeObserver`, three closed VG-008 result artifacts with `e3_runtime_assertion=true`, and registered validation commands.

- [ ] **Step 1: Write failing imported-observer tests**

Add tests that construct temporary imported files and assert:

```python
observer = runtime.AttestedRuntimeObserver.from_imported_files(
    profile_path=profile_path,
    observations_path=observations_path,
    receipt_path=receipt_path,
    validation_at="2026-07-30T00:04:00Z",
)
assert runtime.has_attested_e3_construction(observer)
assert observer.observe({"id": "positive-rootless-readonly"})["evidence_kind"] == "runtime"
```

Negative tests cover receipt `verification_kind=test`, stale/future time, output hash mismatch, unknown/duplicate/missing case, instance method shadowing, mutated class methods, malformed profile and non-zero terminal residue. Each must fail before returning an observation.

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
python -m unittest tests.sandbox_security.test_verify.DockerObserverTests tests.sandbox_security.test_verify.SandboxCliTests -v
```

Expected: failure because `AttestedRuntimeObserver` and the success CLI path do not exist.

- [ ] **Step 3: Implement the sealed imported observer**

Add:

```python
class AttestedRuntimeObserver(TrustedRuntimeObserver):
    @classmethod
    from_imported_files(
        cls,
        profile_path: Path,
        observations_path: Path,
        receipt_path: Path,
        validation_at: str,
    ) -> "AttestedRuntimeObserver"

    observe(self, case: dict) -> dict


has_attested_e3_construction(observer: object) -> bool
```

Construction requires exact file hashes from the runtime receipt, `verification_kind=runtime`, exact issuer, digest consistency, rootless profile, 0–300 second freshness and the complete 23-case catalog. Deep-copy observations on return. Preserve the existing `VerifiedDockerRuntimeObserver` tests and fail-closed behavior; do not broaden its hardcoded local test trust anchor.

Keep the trust domains separate:

```python
LOCAL_TEST_ISSUER = "forgeops-test-issuer"
EXTERNAL_E3_ISSUER = "https://token.actions.githubusercontent.com"
```

The existing fake/local fixture path continues to validate only `LOCAL_TEST_ISSUER`. The imported observer path validates only `EXTERNAL_E3_ISSUER`; neither branch accepts a caller-supplied issuer string.

- [ ] **Step 4: Add the successful CLI projection**

Keep the current six CLI literals unchanged. `run_cli` derives the two additional fixed inputs internally:

```python
ATTESTED_OBSERVATIONS = "artifacts/runtime/sandbox-runtime-observations.json"
ATTESTED_RECEIPT = "artifacts/runtime/sandbox-e3-import-receipt.json"
```

If either file is missing or invalid, write the existing `safe_not_run` result and return `2`. If the observer is trusted, run the registered cases, select the catalog groups for the requested command, and write only this existing public envelope:

```python
{
    "result_version": "1.0",
    "command_id": command_id,
    "runtime": "docker",
    "status": "PASSED",
    "category": "PASSED",
    "time": validation_at,
    "input_hashes": input_hashes,
    "counts": {"cases_total": total, "passed": total, "failed": 0, "not_run": 0},
    "e3_runtime_assertion": True,
    "effect_counters": effect_counters,
    "residue_counters": terminal_residue,
}
```

Do not add case arrays or identity metadata to this Phase 0-facing artifact; those remain in the signed external artifact.

Before evaluation, derive an in-memory copy of the four image provenance cases from the verified imported profile: unchanged profile for `positive-signed-digest`, tag-only image ref for `negative-tag-only`, `signature_verified=false` for `negative-signature-unverified`, and `issuer=untrusted-issuer` for `negative-issuer-mismatch`. Do not rewrite the source suite file. Catalog ownership is exact: `image-provenance-negative` evaluates 4 image cases, `containment-egress-negative` evaluates 5 containment + 7 egress + 2 quota cases, and `teardown-negative` evaluates 5 teardown cases. Capture one `validation_at` and use it for profile validation, observation validation and the result `time`.

- [ ] **Step 5: Register the three VG-008 commands**

Add to `AGENTS.md` using the existing exact command strings:

```yaml
- id: image-provenance-negative
  command: python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-image-provenance-result.json --command-id image-provenance-negative
  cwd: "."
  evidence_tier: E3
  required: true
```

Add all three complete records and their profile mapping:

```yaml
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

- id: forgeops-sandbox-security
  command_ids:
    - image-provenance-negative
    - containment-egress-negative
    - teardown-negative
```

Preserve all existing user changes in `AGENTS.md`.

- [ ] **Step 6: Run focused and phase adapter tests**

Run:

```powershell
python -m unittest tests.sandbox_security.test_verify tests.phase_exit.test_verify -v
```

Expected: all tests pass, including legacy no-attestation `NOT_RUN` behavior and new imported E3 success behavior.

- [ ] **Step 7: Prepare the task commit only if Git authority was granted**

```powershell
git add -- tools/sandbox_security/runtime.py tools/sandbox_security/verify.py tests/sandbox_security/test_verify.py AGENTS.md
git diff --cached --check
git commit -m "feat: consume attested VG-008 runtime evidence"
```

Without explicit Git authority, do not execute these commands.

---

### Task 4: Minimal Two-Job GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/vg-008-e3.yml`
- Create: `tools/sandbox_security/e3_artifact.py`
- Create: `tests/sandbox_security/test_e3_workflow.py`
- Modify: `tests/sandbox_security/test_e3_attestation.py`

**Interfaces:**
- Consumes: Tasks 1–3 CLIs and GitHub runtime metadata.
- Produces: `forgeops-e3-evidence-${run_id}-${run_attempt}` artifact containing only allowlisted signed evidence and Phase 0 results.

- [ ] **Step 1: Write failing workflow policy tests**

Read workflow YAML as UTF-8 text without adding a YAML dependency. Assert:

- only `workflow_dispatch` triggers it;
- job keys are exactly `build-sign` and `verify-e3`;
- `verify-e3` has `needs: build-sign` and a fresh `ubuntu-latest` runner;
- both jobs require exact default ref and protected ref before effects;
- job permissions exactly match Global Constraints;
- `actions: write`, `contents: write`, `pull-requests: write`, `deployments: write`, `secrets: inherit`, `pull_request`, `push` and `schedule` are absent;
- no `git commit`, `git push`, `gh pr`, release or deploy command exists;
- all `uses:` values contain a full 40-character SHA;
- artifact name includes run ID and attempt, `if-no-files-found: error`, `include-hidden-files: false`, `retention-days: 7`.

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
python -m unittest tests.sandbox_security.test_e3_workflow -v
```

Expected: failure because the workflow does not exist.

- [ ] **Step 3: Add the public artifact builder**

Implement fixed allowlists:

```python
E3_PAYLOAD_FILES = (
    "artifacts/runtime/e3-attestation.json",
    "artifacts/runtime/e3-attestation.bundle.json",
    "artifacts/runtime/sandbox-runtime-profile.json",
    "artifacts/runtime/sandbox-runtime-observations.json",
    "artifacts/runtime/sandbox-e3-import-receipt.json",
    "artifacts/verification/vg-008-image-provenance-result.json",
    "artifacts/verification/vg-008-containment-egress-result.json",
    "artifacts/verification/vg-008-teardown-result.json",
    "artifacts/verification/phase-0-exit-result.json",
    "artifacts/reviews/phase-0-exit-report.md",
)

E3_MANIFEST_FILE = "artifacts/runtime/e3-artifact-manifest.json"
E3_ARTIFACT_FILES = E3_PAYLOAD_FILES + (E3_MANIFEST_FILE,)
```

`build_manifest(root, output)` hashes exactly `E3_PAYLOAD_FILES` and writes `E3_MANIFEST_FILE`; the manifest never hashes itself. It rejects missing, extra, absolute, symlink, secret-like or oversized entries. `verify_downloaded_artifact(source, expected_repository, expected_repository_id, expected_default_branch, expected_run_id, expected_run_attempt, expected_source_sha)` validates the manifest and signed attestation against caller-supplied GitHub API facts. `import_downloaded_artifact(source, root, expected_identity)` atomically copies only these known targets. A downloaded artifact older than 300 seconds may be archived as historical evidence but may not replace current runtime/result files or declare `READY`.

- [ ] **Step 4: Create the two-job workflow with full Action pins**

Use these reviewed pins:

```yaml
actions/checkout: de0fac2e4500dabe0009e67214ff5f5447ce83dd
actions/upload-artifact: 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
docker/login-action: b45d80f862d83dbcd57f89517bcf500b2ab88fb2
docker/setup-buildx-action: 4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd
docker/build-push-action: f9f3042f7e2789586610d6e8b85c8f03e5195baf
sigstore/cosign-installer: 6f9f17788090df1f26f669e9d70d6ae9567deba6
```

At workflow top level set `permissions: {}` and `concurrency: vg-008-e3-${{ github.repository_id }}` with `cancel-in-progress: false`.

`build-sign` performs, in order:

1. exact `github.ref == format('refs/heads/{0}', github.event.repository.default_branch)` and `github.ref_protected == true` assertion;
2. checkout `ref: ${{ github.sha }}`, `fetch-depth: 1`, `persist-credentials: false`;
3. compute lower-case `ghcr.io/${GITHUB_REPOSITORY_OWNER}/forgeops-e3` without accepting workflow input;
4. GHCR login with `github.actor` and `github.token`;
5. build/push the fixed Dockerfile, output registry digest;
6. reject any non-`sha256` digest and set only `image_ref`, `image_digest`, `source_sha`, `workflow_ref`, `workflow_sha` job outputs;
7. `cosign sign --yes` the exact digest reference.

`verify-e3` performs, in order:

1. repeat exact ref, protection, repository and output-format assertions;
2. checkout the same `${{ needs.build-sign.outputs.source_sha }}` with credentials disabled;
3. install Cosign and log in to GHCR with read-only package permission;
4. verify exact image digest with exact certificate identity and OIDC issuer before Docker provisioning;
5. run `setup_rootless.sh`, select its Unix socket and confirm rootless/cgroup observations;
6. pull and inspect the exact digest;
7. run `e3_helper.py` in a separate Python process;
8. sign with `cosign sign-blob --yes --bundle artifacts/runtime/e3-attestation.bundle.json artifacts/runtime/e3-attestation.json`;
9. invoke `e3_attestation.py import` to verify the bundle and create imported runtime files;
10. run all 18 Phase 0 required commands from `AGENTS.md` in declared order, including the three VG-008 commands, so every result is inside the same 300-second freshness window;
11. require 18/18 `PASSED`, blockers 0 and `READY` before marking the manifest successful;
12. build the public manifest and upload the exact allowlist.

- [ ] **Step 5: Add workflow and artifact negative tests**

Test wrong ref, unprotected ref, tag image, uppercase digest, issuer/identity near miss, missing result, symlink, extra file, secret-like key, over-age artifact and `NOT_READY` phase result. Each must stop before upload or produce a failure artifact without a success manifest.

- [ ] **Step 6: Run workflow policy tests**

Run:

```powershell
python -m unittest tests.sandbox_security.test_e3_workflow tests.sandbox_security.test_e3_attestation -v
```

Expected: all tests pass without contacting GitHub, GHCR or Sigstore.

- [ ] **Step 7: Prepare the task commit only if Git authority was granted**

```powershell
git add -- .github/workflows/vg-008-e3.yml tools/sandbox_security/e3_artifact.py tests/sandbox_security/test_e3_workflow.py tests/sandbox_security/test_e3_attestation.py
git diff --cached --check
git commit -m "ci: add two-job VG-008 E3 verification"
```

Without explicit Git authority, do not execute these commands.

---

### Task 5: Local Regression, External Run Gate, and W4 Closure

**Files:**
- Modify after a successful external run only: `docs/quality/verification-and-evaluation-plan.md`
- Modify after a successful external run only: `docs/project/wbs.md`
- Modify after a successful external run only: `docs/project/requirements-traceability-matrix.md`
- Regenerate after a successful external run: `artifacts/runtime/sandbox-runtime-profile.json`
- Regenerate after a successful external run: `artifacts/verification/vg-008-image-provenance-result.json`
- Regenerate after a successful external run: `artifacts/verification/vg-008-containment-egress-result.json`
- Regenerate after a successful external run: `artifacts/verification/vg-008-teardown-result.json`
- Regenerate after a successful external run: `artifacts/verification/phase-0-exit-result.json`
- Regenerate after a successful external run: `artifacts/reviews/phase-0-exit-report.md`

**Interfaces:**
- Consumes: locally verified implementation and one approved protected-default-branch GitHub Actions run.
- Produces: immutable external run/artifact reference and, only on 18/18 success, WBS-010/WBS-012 completion evidence.

- [ ] **Step 1: Run all local tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all tests pass. A Windows-only symlink privilege skip remains acceptable only if it is the existing expected skip and no new test is skipped.

- [ ] **Step 2: Run local registered validation commands**

Run the 15 non-VG-008 required commands exactly as recorded in `AGENTS.md`, then run these three local commands:

```powershell
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-image-provenance-result.json --command-id image-provenance-negative
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-containment-egress-result.json --command-id containment-egress-negative
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-teardown-result.json --command-id teardown-negative
```

The three VG-008 commands are expected to remain truthful `NOT_RUN` locally unless a fresh signed import is present; this does not authorize claiming W4 complete. All other required gates must pass.

- [ ] **Step 3: Inspect the final local change set**

Run:

```powershell
git status --short
git diff --check
git diff -- .github/workflows/vg-008-e3.yml contracts/forgeops-e3-attestation tools/sandbox_security tests/sandbox_security AGENTS.md
```

Expected: no whitespace errors, no secret-like value, no unrelated file modification and no staged change unless Git authority was granted.

- [ ] **Step 4: Stop for one batched external-action approval**

Before any live run, request one approval covering exactly:

- protected-default-branch GitHub Actions `workflow_dispatch` execution;
- GitHub OIDC token issuance;
- GHCR private package push/pull;
- Sigstore Fulcio/Rekor and GitHub/GHCR network access;
- Cosign image and blob signature/attestation storage;
- Actions artifact upload and download.

The request explicitly excludes commit, push, PR, release, deployment, repository settings changes, package visibility changes, general messaging and long-lived credentials. Because the workflow must already exist on the protected default branch, the user performs or separately authorizes that Git integration before this step.

- [ ] **Step 5: Run and watch the approved workflow**

If GitHub CLI is available and authenticated, discover the default branch without guessing and run:

```powershell
$repoInfo = gh repo view --json nameWithOwner,defaultBranchRef | ConvertFrom-Json
$defaultRef = $repoInfo.defaultBranchRef.name
gh workflow run vg-008-e3.yml --ref $defaultRef
$runId = gh run list --workflow vg-008-e3.yml --branch $defaultRef --event workflow_dispatch --limit 1 --json databaseId | ConvertFrom-Json | Select-Object -ExpandProperty databaseId
gh run watch $runId --exit-status
```

If `gh` is unavailable, use the GitHub Actions UI to run `VG-008 E3 Verification` on the displayed default branch and download the named evidence artifact. Do not install another verifier on the user's machine; all cryptographic/runtime verification remains in the workflow.

- [ ] **Step 6: Download and verify the public artifact**

For CLI operation:

```powershell
$repoApi = gh api ("repos/" + $repoInfo.nameWithOwner) | ConvertFrom-Json
$runApi = gh api ("repos/" + $repoInfo.nameWithOwner + "/actions/runs/" + $runId) | ConvertFrom-Json
$downloadRoot = Join-Path $env:TEMP ("forgeops-e3-" + $runId)
New-Item -ItemType Directory -Path $downloadRoot | Out-Null
gh run download $runId --name ("forgeops-e3-evidence-" + $runId + "-" + $runApi.run_attempt) --dir $downloadRoot
python tools/sandbox_security/e3_artifact.py verify-download --source $downloadRoot --expected-repository $repoInfo.nameWithOwner --expected-repository-id ([string]$repoApi.id) --expected-default-branch $repoInfo.defaultBranchRef.name --expected-run-id ([string]$runId) --expected-run-attempt ([int]$runApi.run_attempt) --expected-source-sha $runApi.head_sha
```

The tool reports only public identity, hashes, status and immutable run reference. If the artifact is older than 300 seconds, preserve it as historical evidence and rerun the workflow instead of importing it as fresh.

- [ ] **Step 7: Import fresh results and close W4 only on observed success**

When the artifact is still fresh and its signed manifest reports 18/18 `PASSED`, blockers 0 and `READY`, import it with the fixed importer and update:

- WBS-010 from `WBS_BLOCKED` to `WBS_DONE` with the immutable GitHub run/artifact and three VG-008 E3 result references;
- WBS-012 from `WBS_BLOCKED` to `WBS_DONE` with Phase 0 18/18 `READY` evidence;
- RTM rows currently blocked by VG-008 with the observed result paths and run reference;
- the Phase 0 quality-plan summary from 15/18 `NOT_READY` to the exact observed 18/18 result.

If any check is `FAILED`, `NOT_RUN`, stale or unavailable, keep WBS-010/WBS-012 blocked and record the stable reason. Do not edit documentation to claim completion from unit tests alone.

- [ ] **Step 8: Re-run final verification immediately after a fresh import**

Run the three VG-008 commands followed by:

```powershell
python tools/phase_exit/verify.py --schema contracts/forgeops-phase-exit-contract/1.0/schema.json --suite fixtures/forgeops-phase-exit/phase-0-suite.json --result artifacts/verification/phase-0-exit-result.json --report artifacts/reviews/phase-0-exit-report.md --command-id phase0-exit-gate
python -m unittest discover -s tests -p "test_*.py" -v
git diff --check
```

Expected: VG-008 three commands return `0` with E3 `PASSED`; Phase 0 returns `0`, 18/18 `PASSED`, blockers 0 and `READY`; all tests pass.

- [ ] **Step 9: Prepare the final commit only if Git authority was granted**

Stage only the reviewed E3 implementation, generated public artifacts and W4 documentation paths. Inspect `git diff --cached --stat` and `git diff --cached --check` before:

```powershell
git commit -m "feat: complete W4 with attested VG-008 evidence"
```

Without explicit Git authority, leave all changes uncommitted and report the exact successful run/artifact reference.
