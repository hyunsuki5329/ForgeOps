# Contract Bridge Fixture 및 W1 Checkpoint 설계

**작성일:** 2026-07-20

**상태:** 승인된 W1 작업 4·5 범위의 서면 설계

**대상 범위:** W1 네 번째·다섯 번째 작업, `WBS-002`, `WBS-003`, `VG-002`

## 1. 목적

Product Task Contract schema 1.0과 Contract→TaskPacket bridge의 lossless 및
non-grant 규칙을 executable positive·negative fixture로 검증한다. 검증 결과를
fresh E2 evidence와 public-safe HTML render로 보존하고, 제3자가 schema,
경계, 결과와 제한을 따라갈 수 있는 W1 checkpoint를 만든다.

이번 작업은 실제 ForgeOps product service나 general-purpose mapper API를
구현하지 않는다. fixture runner는 Phase 0 contract conformance validator다.
외부 publication, push, PR, message 또는 deploy authority를 만들지 않는다.

## 2. 접근 방식

검토한 방식은 다음 세 가지다.

1. Markdown·PowerShell 구조 검사만 수행하면 dependency는 없지만 JSON Schema
   semantics, stable error와 non-grant mapping을 충분히 실행 검증할 수 없다.
2. Python 3.11, 설치된 `jsonschema`와 stdlib를 사용하는 독립 fixture runner는
   현재 환경에서 Draft 2020-12를 검증하고 safe evidence·render를 만들 수 있다.
3. production mapper service와 API까지 구현하면 장기 재사용성은 높지만 W1
   네 번째·다섯 번째 작업을 넘어 product runtime 범위를 앞당긴다.

두 번째 방식을 사용한다. `jsonschema`가 없거나 Draft 2020-12 validator를
사용할 수 없으면 dependency를 자동 설치하지 않고 command를 실패시켜
`VG-002`를 `NOT_RUN` 또는 `FAILED`로 남긴다.

## 3. 구성요소

### 3.1 Fixture suite

`fixtures/product-task-contract-bridge/suite.json`을 만든다. 하나의 public-safe
base Contract, trusted context와 mutation 기반 case catalog를 포함한다.

Suite의 closed top-level field는 다음과 같다.

| Field | 책임 |
| --- | --- |
| `suite_id`, `suite_version` | exact fixture identity와 version |
| `schema_ref` | project-root-relative Product Contract schema path |
| `bridge_ref` | project-root-relative bridge 문서 path |
| `base_contract` | public-safe canonical positive input |
| `trusted_context` | intent mapping, validation profile, canonical control과 gate 기준 |
| `cases` | case ID, kind, mutation, parameter와 expected result |

Fixture는 secret, credential, tenant ID, private repository, raw log 또는 실제
외부 target을 포함하지 않는다. repository와 issue identity는
`public-example/forgeops-fixture` 같은 명시적 public fixture 값만 사용한다.

### 3.2 Validator와 mapper harness

`tools/contract_bridge/verify.py`를 만든다. 단일 command가 다음을 수행한다.

1. CLI path를 project root 아래 canonical relative path로 확인한다.
2. Product Contract schema를 `Draft202012Validator.check_schema`로 검사한다.
3. suite structure, unique case ID와 supported mutation을 검사한다.
4. 각 case에 base Contract와 trusted context의 deep copy를 만든다.
5. case mutation을 하나만 적용한다.
6. stable priority에 따라 schema와 semantic bridge를 검증한다.
7. 성공 case는 TaskPacket-shaped mapping과 provenance를 생성한다.
8. expected result와 actual result를 exact 비교한다.
9. public-safe JSON evidence와 HTML checkpoint render를 원자적으로 쓴다.
10. 모든 case가 일치하면 exit 0, 하나라도 다르면 exit 1을 반환한다.

`tests/contract_bridge/test_verify.py`는 exact 19-case catalog 변조 거부,
unexpected mapper error의 safe `RUNNER_ERROR` 변환, suite/runner contract
실패 시 이전 PASSED artifact를 FAILED artifact로 교체하는 동작을 검증한다.

Runner는 production MainDecision이나 authoritative event를 만들지 않는다.
mapped output은 fixture-local observation이며 result artifact에는 raw Contract,
trusted context, mapped packet 또는 secret-bearing value를 넣지 않는다.

### 3.3 Trusted validation profile

root `AGENTS.md`의 `project_profile.validation_commands`에 다음 exact record를
등록한다.

```yaml
- id: bridge-schema-fixture
  command: python tools/contract_bridge/verify.py --schema contracts/product-task-contract/1.0/schema.json --suite fixtures/product-task-contract-bridge/suite.json --result artifacts/verification/vg-002-contract-bridge-result.json --report artifacts/reviews/w1-contract-bridge-checkpoint.html
  cwd: "."
  evidence_tier: E2
  required: true
```

`verification_profile_id=forgeops-contract-bridge`는 ForgeOps extension 아래
이 command ID를 묶는 profile identity로 기록한다. 이 등록은 현재 runtime의
`command_execute=AVAILABLE` 관찰이나 execute authority를 자동으로 만들지
않는다. 실제 command 실행은 현재 task authority와 preflight가 별도로 필요하다.

### 3.4 Evidence와 render

Runner는 다음 두 generated artifact를 만든다.

- `artifacts/verification/vg-002-contract-bridge-result.json`
- `artifacts/reviews/w1-contract-bridge-checkpoint.html`

Result JSON은 profile ID, command ID, `E2`, `PASSED|FAILED`, strict UTC
`observed_at`, Python·jsonschema version, schema/suite SHA-256, case count와
각 case의 ID·kind·status·expected/actual error만 포함한다. Raw input이나
mapped packet은 포함하지 않는다.

HTML은 동일 safe summary, case table, non-grant invariant와 현재 제한만
표시한다. HTML escape를 적용하며 remote script, stylesheet, image, URL 또는
active content를 포함하지 않는다.

### 3.5 Review 문서

`docs/reviews/w1-contract-bridge-checkpoint.md`를 작성한다. schema, bridge,
fixture, runner, trusted command, result JSON과 HTML render를 연결하고 다음을
명시한다.

- fresh 실행 결과와 case 수
- lossless·non-grant criterion별 증빙 연결
- 발견된 위반과 해소 결과
- `VG-002` 판정 근거
- product runtime, Phase 0 Exit, VG-001과 publication authority 비주장

## 4. Fixture catalog

Suite는 3 positive와 16 negative, 총 19 case를 가진다.

### Positive

| ID | 검증 목적 |
| --- | --- |
| `POSITIVE_LOSSLESS_BASELINE` | summary, criterion, constraint, repository와 source issue exact 보존 |
| `POSITIVE_EMBEDDED_CONTROL_TEXT` | 허용된 string 안의 authority·state·tool 주장이 data로만 남고 canonical control 불변 |
| `POSITIVE_VERIFIED_GATE_STRENGTHENING` | 검증된 Contract policy가 trusted gate를 required 방향으로만 강화하며 authority는 불변 |

### Negative

| ID 또는 group | Expected error |
| --- | --- |
| `NEGATIVE_VERSION_UNSUPPORTED` | `CONTRACT_VERSION_UNSUPPORTED` |
| `NEGATIVE_CONTROL_*` 7개: `authority`, `capabilities`, `approval`, `policy`, `budgets`, `accepted_state`, `tools` | `CONTRACT_CONTROL_FIELD_FORBIDDEN` |
| `NEGATIVE_UNKNOWN_FIELD`, `NEGATIVE_MISSING_REQUIRED`, `NEGATIVE_WRONG_TYPE` | `CONTRACT_SCHEMA_INVALID` |
| `NEGATIVE_DUPLICATE_CRITERION` | `CONTRACT_CRITERION_DUPLICATE` |
| `NEGATIVE_UNMAPPED_INTENT` | `CONTRACT_INTENT_UNMAPPED` |
| `NEGATIVE_UNTRUSTED_COMMAND` | `CONTRACT_COMMAND_UNTRUSTED` |
| `NEGATIVE_VERIFIED_GATE_RELAXATION` | `CONTRACT_MONOTONICITY_VIOLATION` |
| `NEGATIVE_PROVENANCE_HASH` | `CONTRACT_PROVENANCE_INVALID` |

Case order는 stable하고 ID는 ordinal unique다. 각 negative case는 한 mutation만
사용해 failure attribution을 분명히 한다.

## 5. Stable validation priority

여러 오류가 동시에 존재해도 다음 첫 오류만 반환한다.

1. suite/runner contract error
2. `CONTRACT_VERSION_UNSUPPORTED`
3. `CONTRACT_CONTROL_FIELD_FORBIDDEN`
4. `CONTRACT_SCHEMA_INVALID`
5. `CONTRACT_CRITERION_DUPLICATE`
6. `CONTRACT_INTENT_UNMAPPED`
7. `CONTRACT_COMMAND_UNTRUSTED`
8. `CONTRACT_MONOTONICITY_VIOLATION`
9. `CONTRACT_PROVENANCE_INVALID`

Schema validation error의 세부 path와 message는 local diagnostic에만 사용하고
public evidence에는 stable category만 기록한다.

## 6. Lossless와 non-grant assertion

Positive mapping은 다음을 자동 확인한다.

- `intent.summary == request.objective`
- criterion ID와 description→statement의 ordinal exact 보존
- constraints 배열의 순서와 값 exact 보존
- repository, source issue, product budget와 approval policy의 exact namespaced
  extension 보존
- schema/artifact identity와 canonical content SHA-256 provenance 보존
- command ID가 trusted profile의 exact `id`, `command`, `cwd` record만 선택
- capabilities, authority, source of truth, risk rules, Harness budgets, state와
  tool schema가 trusted context 밖의 Contract data로 바뀌지 않음
- verified policy는 gate를 강화할 수 있지만 authority, capability 또는
  approval token을 만들지 않음

## 7. Checkpoint와 상태 갱신

Fresh command가 exit 0이고 result JSON이 `PASSED`일 때만 다음을 수행한다.

1. bridge 문서의 future Task 4 설명을 실제 fixture/evidence link로 갱신한다.
2. baseline inventory의 Product contract layer를 `IMPLEMENTED`로 갱신한다.
3. PRD-FR-001 및 ARC-002·ARC-010의 maturity를 fresh evidence 범위에서
   `IMPLEMENTED`로 갱신한다.
4. RTM의 PRD-FR-001을 `PASSED`, actual tier `E2`, evidence/result path와
   runtime-supplied `observed_at`으로 갱신한다.
5. `WBS-002`를 `WBS_DONE`으로 갱신한다.
6. review 문서와 HTML render 검증 뒤 `WBS-003`을 `WBS_DONE`으로 갱신한다.
7. 문서 지도에 review checkpoint를 연결한다.

`VG-001`과 다른 VG 결과, WBS-004 이후 상태, product runtime과 Phase 0 Exit는
변경하지 않는다. Command가 실패하면 result를 보존하고 `WBS-002`를
`WBS_IN_PROGRESS`, `WBS-003`을 `WBS_NOT_STARTED`로 유지한다.

## 8. 검증

최종 검증은 다음을 포함한다.

- exact registered command를 새 process에서 다시 실행
- result JSON의 profile·command·tier·timestamp·hash·19/19 case 확인
- positive 3/3, negative 16/16과 stable error exact match 확인
- generated HTML의 safe field allowlist, HTML escape, active/remote content 0
- review Markdown과 모든 상대 링크 확인
- schema, bridge, baseline inventory, PRD, architecture, RTM, WBS의 상태·ID
  consistency 확인
- `VG-001`과 WBS-004 이후가 변하지 않았는지 확인
- UTF-8, trailing whitespace, final newline과 scoped diff 확인

## 9. 범위 제외

- production mapper API, service, database, queue 또는 durable state
- 외부 repository, Issue, network, credential 또는 private data 사용
- package install, dependency upgrade 또는 material cost
- Phase 0 Exit와 다른 VG의 실행·통과
- 외부 publication, upload, message, deploy, Git commit·merge·push·PR
- 기존 사용자 변경의 정리·되돌리기·재format

## 10. 완료 기준

- 19개 fixture가 exact expected result와 일치한다.
- `VG-002` fresh E2 result가 safe JSON evidence로 해석된다.
- lossless와 non-grant assertion이 모두 통과한다.
- public-safe HTML과 review Markdown에서 결과·제한을 제3자가 따라갈 수 있다.
- 동기화된 owner·trace·WBS 문서가 evidence 범위를 과장하지 않는다.
- `WBS-002`, `WBS-003`만 완료되고 다른 WBS·VG 상태는 유지된다.
