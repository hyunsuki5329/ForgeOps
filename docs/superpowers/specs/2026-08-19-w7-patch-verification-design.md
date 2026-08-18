# W7 Patch, Trusted Verification, and Anti-Tamper Design

**상태:** APPROVED DESIGN
**작성일:** 2026-08-19
**범위:** WBS-020~WBS-022, VG-013

## 1. 목적

W7은 W5의 immutable snapshot/baseline과 W6의 Main→Part→Work→Main local flow 다음에 위치한다. 목표는 승인된 변경을 원본이 아닌 ephemeral workspace에만 적용하고, 변경 전 baseline과 변경 후 trusted checks를 비교하며, 검증 자산을 약화하는 조작을 결정론적으로 차단하는 것이다.

W7 완료는 다음만 증명한다.

- exact resource에 대한 bounded patch와 canonical unified diff
- source tree 불변성과 verifier-owned workspace 경계
- task test, regression, lint, typecheck의 trusted exact profile 실행
- baseline failure와 changed-task regression의 분리
- test 삭제, skip, xfail, assertion 완화, coverage 제외, profile 변경 탐지
- registered VG-013 세 command의 fresh E2 evidence

W7은 VG-015 trace/manifest, gateway-level external-write proof, W8 lifecycle/budget/cleanup, Phase 1 safety gate 또는 Phase 1 Exit를 완료로 주장하지 않는다.

## 2. 승인된 범위 결정

### 2.1 기준 브랜치와 실행 위치

W7은 W6 최종 브랜치 `feature/w6-local-vertical`의 `bc4bc57`에서 분기한다. 구현은 `feature/w7-patch-verification`의 외부 임시 linked worktree에서 수행한다.

### 2.2 WBS-020 재범위화

현재 WBS-020은 VG-013과 VG-015를 함께 참조하지만 VG-015의 trace, gateway 우회와 external-write manifest는 W8 WBS-025 및 후속 Phase 1 통합 범위다. W7에서 VG-015 전체를 조기 완료하면 W8 trace/lifecycle 책임을 침범한다.

따라서 WBS-020의 완료 gate는 VG-013으로 한정한다. W7은 local patch adapter가 source와 verifier-owned workspace 경계를 지키며 remote publisher를 호출하지 않았다는 E2 관찰만 기록한다. OS 전체와 gateway-level 외부 write absence, terminal trace completeness는 계속 VG-015 `NOT_RUN`이다.

PRD-FR-011은 local patch/diff implementation을 `IMPLEMENTED`로 갱신하되 RTM 설명에서 VG-013 E2의 관찰 경계를 명시하고 VG-015가 남아 있음을 유지한다. PRD-FR-012는 VG-013 통과 뒤 `IMPLEMENTED`/`PASSED`로 갱신한다.

### 2.3 의존성

새 third-party dependency를 추가하지 않는다. Python 3 standard library, 현재 사용 중인 `jsonschema`, `unittest`, W5 snapshot primitives와 기존 atomic-result 패턴만 사용한다.

## 3. 접근 방식 비교

### 3.1 선택: 표준 라이브러리 deterministic verifier kernel

trusted profile은 raw shell 문자열이 아니라 코드에 등록된 closed command/check identity로 구성한다. verifier code는 agent workspace 밖의 repository tool package에서 실행되며 workspace는 입력 데이터로만 읽는다. task/regression/lint/typecheck는 고정 fixture와 exact callable registry로 평가한다.

장점은 dependency download가 없고 Windows/Linux 결과가 안정적이며, profile mutation과 raw shell injection을 구조적으로 차단한다는 점이다. 단점은 실제 Ruff/mypy 전체 의미를 증명하지 않고 W7 fixture adapter의 lint/type contract만 증명한다는 점이다. 이 한계는 결과와 문서에 명시한다.

### 3.2 미선택: Ruff/mypy/pytest subprocess toolchain

실제 생태계 도구에 가깝지만 새 dependency, version pin, network 설치와 플랫폼 차이를 도입한다. W7의 핵심인 exact identity, baseline differential과 anti-tamper보다 도구 설치 문제가 커지므로 사용하지 않는다.

### 3.3 미선택: raw git apply와 shell profile

developer workflow와 유사하지만 raw patch/shell text를 authority로 오인할 위험이 있고 quoting, path normalization과 Windows 차이가 커진다. W7은 structured patch intent와 registered callable만 허용한다.

## 4. 구성요소

### 4.1 Contract와 fixture

새 contract:

- `contracts/forgeops-patch-verification/1.0/schema.json`

새 fixture:

- `fixtures/forgeops-patch-verification/suite.json`

schema는 Draft 2020-12이며 suite, base fixture, profile declarations, cases와 public result object를 재귀적으로 닫는다. 모든 배열은 raw JSON array여야 하고 ID는 ordinal unique여야 한다.

base fixture는 다음 public-safe 파일을 정의한다.

- `src/calculator.py`: typed `total` 함수의 잘못된 연산과 변하지 않는 `identity` 함수
- `tests/test_calculator.py`: task expectation과 baseline regression expectation
- `.coveragerc`: exact include/omit baseline
- `verification-profile.json`: untrusted workspace companion; trusted registry의 authority가 아님

허용된 patch resource는 `src/calculator.py` 하나다. patch intent는 `resource_ref`, exact `before_sha256`, exact `after_bytes_sha256`, UTF-8 replacement identity와 maximum diff bytes/lines를 포함한다. raw unified diff나 raw shell은 입력 authority가 아니다.

### 4.2 Patch pipeline

새 package:

- `tools/patch_verification/model.py`
- `tools/patch_verification/patch.py`

`model.py`는 `PatchVerificationError`, canonical root-relative path, strict UTC, SHA-256, tree hash, atomic JSON write와 public-safe value helpers를 소유한다.

`patch.py`의 공개 interface:

```python
apply_bounded_patch(
    source_root: Path,
    workspace_root: Path,
    intent: Mapping[str, object],
    *,
    audit: EffectAudit,
) -> dict[str, object]
```

처리 순서는 고정한다.

1. source/workspace root가 서로 다르고 기존 directory인지 확인
2. intent exact fields와 canonical resource 확인
3. resource가 allowlist exact member인지 확인
4. source와 workspace target을 resolve하되 symlink/reparse/traversal 거부
5. source와 workspace before bytes/hash가 fixture baseline과 일치하는지 확인
6. UTF-8 replacement bytes와 after hash 확인
7. sibling temporary file과 `os.replace`로 workspace target만 변경
8. exact after bytes 재읽기
9. `difflib.unified_diff`로 path-stable bounded diff 생성
10. source tree hash와 outside-workspace audit 재확인

diff header는 `a/src/calculator.py`, `b/src/calculator.py`로 고정하며 absolute path, timestamp와 host separator를 포함하지 않는다. diff text, changed line count와 byte count가 configured bound를 넘으면 artifact를 수용하지 않는다.

### 4.3 Trusted profile과 baseline differential

새 module:

- `tools/patch_verification/profiles.py`

trusted profile ID는 `forgeops-w7-fixture-checks`다. 정확한 ordered check identity는 다음 네 개다.

1. `TASK_TEST`
2. `REGRESSION_TEST`
3. `LINT`
4. `TYPECHECK`

workspace의 `verification-profile.json`은 provenance 비교용 untrusted companion일 뿐 실행 profile을 변경하지 못한다. 실제 profile은 module constant에서 canonical JSON digest로 고정한다.

공개 interface:

```python
run_trusted_profile(
    workspace_root: Path,
    *,
    profile_id: str,
    profile_digest: str,
    observed_at: str,
) -> dict[str, object]
```

각 check는 raw stdout/stderr를 보존하지 않고 status, stable reason, duration-free result fingerprint와 public-safe evidence만 반환한다.

- `TASK_TEST`: `total(2, 3) == 5`를 검사한다.
- `REGRESSION_TEST`: `identity` behavior와 protected test fixture expectation을 검사한다.
- `LINT`: UTF-8, LF, trailing whitespace 없음, Python AST parse를 검사한다.
- `TYPECHECK`: `total(left: int, right: int) -> int`와 `identity(value: int) -> int` exact annotation contract를 AST에서 검사한다.

baseline에서는 task check의 exact known failure만 허용하고 regression/lint/typecheck는 통과해야 한다. baseline regression 또는 infrastructure check가 실패하면 `BASELINE_UNHEALTHY`이며 changed-task success를 계산하지 않는다. patch 이후에는 네 check가 모두 통과해야 하며 baseline에서 통과한 check가 실패하면 `NEW_REGRESSION`이다.

모든 evidence는 strict UTC `observed_at`, E2 tier, profile ID/digest, snapshot/workspace identity와 source hash를 포함한다. command result timestamp는 verifier가 한 번 캡처한 anchor에서 0~300초 범위여야 한다.

### 4.4 Anti-tamper guard

새 module:

- `tools/patch_verification/anti_tamper.py`

guard manifest는 protected test, `.coveragerc`, workspace companion profile의 path, type, SHA-256와 semantic fingerprint를 가진다. trusted profile digest는 별도 field로 고정한다.

공개 interface:

```python
build_guard_manifest(workspace_root: Path, trusted_profile_digest: str) -> dict[str, object]
verify_guard_manifest(
    workspace_root: Path,
    manifest: Mapping[str, object],
    *,
    trusted_profile_digest: str,
) -> dict[str, object]
```

검사는 다음 precedence를 따른다.

1. manifest와 trusted digest exact shape
2. protected path existence, regular-file, root containment
3. symlink/reparse와 path substitution
4. file hash와 UTF-8 parse
5. test 삭제/rename/addition
6. skip/xfail decorator 또는 call
7. assertion count/operator/expected-value weakening
8. coverage include/omit 변경
9. workspace profile 변경 또는 trusted digest mismatch

exact protected file hash mismatch만으로도 거부하지만 stable reason은 더 구체적인 semantic category를 우선한다. 검증 실패는 test를 실행하지 않고 workspace/source에 추가 effect를 만들지 않는다.

### 4.5 Registered VG-013 verifier

새 module:

- `tools/patch_verification/verify.py`

verification profile ID는 `forgeops-patch-verification`이고 ordered registered commands는 다음과 같다.

1. `task-checks`
2. `regression-checks`
3. `verification-anti-tamper`

각 command는 동일 schema/suite를 exact registered path로 읽고 별도 result를 atomic replace한다.

- `artifacts/verification/vg-013-task-checks-result.json`
- `artifacts/verification/vg-013-regression-checks-result.json`
- `artifacts/verification/vg-013-verification-anti-tamper-result.json`

command/result pair, schema path, suite path와 command ID가 하나라도 다르면 기존 result를 보존하고 exit 2를 반환한다. valid suite의 case failure는 closed `FAILED` result와 exit 1, 전부 통과는 `PASSED`와 exit 0이다.

## 5. Exact case catalog

suite는 command별 9개, 총 27개 case를 다음 순서로 가진다.

### 5.1 `task-checks`

1. `POSITIVE_BOUNDED_PATCH`
2. `NEGATIVE_ABSOLUTE_RESOURCE`
3. `NEGATIVE_TRAVERSAL_RESOURCE`
4. `NEGATIVE_UNKNOWN_RESOURCE`
5. `NEGATIVE_BEFORE_HASH_MISMATCH`
6. `NEGATIVE_SOURCE_AS_WORKSPACE`
7. `NEGATIVE_WORKSPACE_SYMLINK_ESCAPE`
8. `NEGATIVE_DIFF_LIMIT`
9. `NEGATIVE_RAW_PATCH_INPUT`

### 5.2 `regression-checks`

1. `POSITIVE_TRUSTED_CHECKS`
2. `NEGATIVE_TASK_CHECK_FAILURE`
3. `NEGATIVE_NEW_REGRESSION`
4. `NEGATIVE_BASELINE_UNHEALTHY`
5. `NEGATIVE_LINT_FAILURE`
6. `NEGATIVE_TYPECHECK_FAILURE`
7. `NEGATIVE_UNKNOWN_PROFILE`
8. `NEGATIVE_PROFILE_DIGEST_MISMATCH`
9. `NEGATIVE_STALE_EVIDENCE`

### 5.3 `verification-anti-tamper`

1. `POSITIVE_GUARDS_UNCHANGED`
2. `NEGATIVE_TEST_DELETE`
3. `NEGATIVE_SKIP_INJECTION`
4. `NEGATIVE_XFAIL_INJECTION`
5. `NEGATIVE_ASSERTION_WEAKEN`
6. `NEGATIVE_COVERAGE_EXCLUSION`
7. `NEGATIVE_PROFILE_CHANGE`
8. `NEGATIVE_TEST_SYMLINK`
9. `NEGATIVE_TEST_RENAME`

각 negative case는 별도 `TemporaryDirectory`에서 같은 baseline을 materialize하고 named mutation 하나만 적용한다. expected stable category와 실제 category가 같더라도 source hash 변화, 허용되지 않은 workspace effect, remote adapter invocation 또는 raw-secret occurrence가 있으면 case는 실패한다.

## 6. Result와 effect audit

public result의 exact top-level fields:

```text
result_version
gate_id
profile_id
command_id
status
evidence_tier
observed_at
input_hashes
profile_digest
summary
effect_counters
cases
```

`summary`는 bool을 제외한 non-negative integer `total`, `passed`, `failed`를 가진다. `cases`는 suite 순서를 보존하고 `id`, `kind`, `expected`, `actual`만 노출한다.

E2 effect counters:

- `source_tree_hash_unchanged`: 직접 hash 비교한 boolean
- `unauthorized_workspace_effects`: case-aware expected file set/bytes와 비교한 integer
- `outside_workspace_write_attempts`: patch adapter에서 관찰한 integer
- `remote_write_attempts`: publisher/network adapter 호출 계수 integer
- `result_artifact_raw_secret_occurrences`: serialized result scan integer
- `host_external_writes`: OS 전체를 관찰하지 않으므로 `null`
- `network_calls`: OS 전체를 관찰하지 않으므로 `null`

앞의 다섯 observed invariant 중 하나라도 실패하면 result status는 `FAILED`이고 exit는 nonzero다. `null`을 0으로 바꾸지 않는다.

## 7. 오류와 zero-effect 규칙

stable error category는 최소 다음을 포함한다.

```text
PATCH_INPUT_INVALID
PATCH_RESOURCE_INVALID
PATCH_RESOURCE_UNAUTHORIZED
PATCH_BASE_MISMATCH
PATCH_CONTAINMENT_VIOLATION
PATCH_DIFF_LIMIT_EXCEEDED
PROFILE_IDENTITY_INVALID
PROFILE_DIGEST_INVALID
BASELINE_UNHEALTHY
TASK_CHECK_FAILED
NEW_REGRESSION
LINT_FAILED
TYPECHECK_FAILED
EVIDENCE_FRESHNESS_INVALID
TEST_DELETED
TEST_SKIP_INJECTED
TEST_XFAIL_INJECTED
ASSERTION_WEAKENED
COVERAGE_POLICY_CHANGED
VERIFICATION_PROFILE_CHANGED
TEST_PATH_INVALID
```

validation과 effect precedence는 path/identity → containment → baseline → mutation → guard → profile → evidence → result audit 순이다. mutation 이전 오류는 source와 workspace 모두 unchanged여야 한다. mutation 이후 검증 실패는 workspace의 expected patch effect만 허용하고 source/outside/remote effect는 0이어야 한다.

## 8. 문서와 상태 갱신

세 registered command가 fresh E2 `PASSED`한 뒤에만 다음을 갱신한다.

- WBS-020~WBS-022 → `WBS_DONE`
- WBS-020 VG mapping → VG-013 only, W8/VG-015 retention acceptance note 추가
- PRD-FR-011/012 → `IMPLEMENTED`
- RTM에 각 VG-013 result path, observed_at, actual E2와 local proof boundary 기록
- ARC-006/007/008에 local patch/trusted verification subset 기록하되 W8/runtime maturity는 과장하지 않음
- verification plan에 VG-013 세 command actual result 기록
- README에 W7 capability와 VG-015/Phase 1 미완료 경계 기록

WBS-023 이후, VG-014/VG-015/VG-024, Phase 1 safety gate와 Exit는 그대로 `WBS_NOT_STARTED` 또는 `NOT_RUN`이다.

## 9. 구현 작업 5개 매핑

1. Contract, exact catalog, registration과 WBS re-scope
2. Bounded patch/diff pipeline
3. Trusted profiles와 baseline differential
4. Anti-tamper guard
5. Registered VG-013 execution, evidence와 documentation closure

각 작업은 RED → 최소 구현 → GREEN → 회귀 검증 → commit 순서로 진행한다. 최종 완료 전 전체 unittest, 세 registered VG-013 command, linked VG-010/VG-012/VG-023, input hash, public-safe scan, RTM timestamp와 whole-diff check를 fresh 실행한다.

## 10. 명시적 비범위

- 실제 Ruff, mypy, pytest dependency 설치
- arbitrary repository profile 또는 raw shell 실행
- git apply, commit, push, PR과 remote publisher
- OS-level process/network/mount containment의 E3 주장
- cancellation, cleanup, budget, trace viewer
- VG-015와 Phase 1 safety gate/Exit

## 11. 설계 자체 검토

- Placeholder 없음: `TBD`, `TODO`, unnamed check 없음
- WBS-020~022와 VG-013 요구를 작업 1~5에 모두 매핑함
- registered profile/command/result path를 exact하게 정의함
- W5/W6 interface를 재사용하며 새 protocol packet을 추가하지 않음
- E2 observed counter와 unobserved `null`을 분리함
- W8/VG-015와 Phase 1 Exit를 조기 완료하지 않음
- external dependency와 network 설치를 추가하지 않음
