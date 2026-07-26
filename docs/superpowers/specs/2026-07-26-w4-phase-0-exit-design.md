# W4 Phase 0 Exit 설계

## 1. 목적

W4는 아직 미실행인 Phase 0 필수 검증 게이트를 구현하고, fresh evidence를 기준으로 Phase 0 Exit 가능 여부를 결정하는 주차다. 범위는 W3에서 남은 WBS-008의 VG-023, WBS-009의 VG-001, WBS-010의 VG-008, WBS-011의 VG-009와 WBS-012의 통합 Exit 보고다.

Phase 0 Exit는 미리 정해진 결과가 아니다. 필수 게이트 가운데 하나라도 실패, 미실행, 낮은 evidence tier, stale, future, reference 불일치 또는 runtime capability 부재 상태이면 결과는 `NOT_READY`이며 Exit를 선언하지 않는다.

## 2. 설계 원칙

- 기존 W1~W3 validator와 같은 closed schema, ordered fixture catalog, stable error category, public-safe result 형식을 사용한다.
- 테스트는 실제 효과 전에 거부되는지와 negative fixture의 effect count가 0인지 함께 검증한다.
- 계획된 capability와 실제 관찰된 capability를 구분한다. OCI runtime을 관찰하지 못한 sandbox 결과는 E3 `PASSED`가 아니다.
- fixture, result와 report에는 실제 credential, private payload, raw secret, absolute host path와 복원 가능한 민감 원문을 넣지 않는다.
- 각 verifier는 등록된 command identity와 고정 입력 경로만 수용하며 임의 경로, 축약 flag와 정규화 시도를 거부한다.
- WBS와 RTM은 fresh result가 생성된 뒤에만 갱신한다. 파일 존재나 unit test 통과만으로 WBS를 완료하지 않는다.

## 3. 작업 분해와 선행 관계

| 순서 | 작업 | WBS / VG | 예상 | 선행 조건 |
| --- | --- | --- | ---: | --- |
| 1 | Evidence Contract와 provenance | WBS-008 / VG-023 | 1.0 pd | W3 interface contract |
| 2 | Sample repository와 foundation conformance | WBS-009 / VG-001 | 0.75 pd | 작업 1 통과 |
| 3 | Sandbox containment PoC | WBS-010 / VG-008 | 1.5 pd | 작업 2 통과 |
| 4 | Redaction·artifact security | WBS-011 / VG-009 | 1.0 pd | 작업 2 통과 |
| 5 | Phase 0 통합 게이트와 Exit 보고 | WBS-012 | 0.5 pd | 작업 1~4 결과 존재 |

총 4.75 person-day로 W4의 계획 작업 4.0 person-day와 buffer 1.0 person-day 안에 배치한다. 작업 3과 작업 4는 WBS상 공통 선행 조건 뒤 독립적이지만, 구현과 검토는 공유 파일 충돌을 피하도록 순차 수행한다.

## 4. 작업 1 — Evidence Contract와 provenance

### 책임

Protocol evidence와 durable evidence wrapper가 사용하는 ID, type, tier, reference, revision/time freshness와 provenance를 하나의 실행 가능한 계약으로 고정한다. 이 작업이 VG-023 E2를 통과해야 WBS-008을 완료 후보로 전환하고 WBS-009를 시작할 수 있다.

### 산출물

- `contracts/forgeops-evidence-contract/1.0/schema.json`
- `fixtures/forgeops-evidence-contract/suite.json`
- `tools/evidence_contract/verify.py`
- `tests/evidence_contract/test_verify.py`
- `artifacts/verification/vg-023-evidence-contract-result.json`
- `artifacts/verification/vg-023-extension-provenance-result.json`

### 계약 경계

- evidence type은 `file`, `diff`, `command`, `test`, `render`, `runtime`, `approval`만 허용한다.
- tier는 `E0`, `E1`, `E2`, `E3`만 허용하며 ordinal 비교 전에 원본 JSON string 타입을 검증한다.
- `file`과 `diff`는 integer `observed_revision`만 요구하고 `observed_at`을 금지한다.
- 나머지 type은 strict UTC `observed_at`만 요구하고 `observed_revision`을 금지하며 trusted validation time 기준 0~300초 freshness를 요구한다.
- ID와 reference는 non-empty, case-sensitive, exact, unique여야 하며 dangling, duplicate, trimming, case folding과 prefix/suffix 추론을 거부한다.
- plugin/static finding provenance는 producer kind, source identity, content hash와 finding reference를 closed object로 보존하며 authority나 acceptance를 만들지 않는다.

### Stable 결과

`EVIDENCE_SCHEMA_INVALID`, `EVIDENCE_TYPE_INVALID`, `EVIDENCE_TIER_INVALID`, `EVIDENCE_REFERENCE_INVALID`, `EVIDENCE_FRESHNESS_INVALID`, `EVIDENCE_PROVENANCE_INVALID`를 public category로 사용한다. 모든 negative case는 evidence acceptance와 durable append 호출이 0이어야 한다.

## 5. 작업 2 — Sample repository와 foundation conformance

### 책임

고정된 source와 expected result를 가진 작은 sample repository를 만들고, Protocol 2.0과 adapter 교체 전후 canonical 의미가 보존되는지 반복 판정한다.

### 산출물

- `samples/forgeops-conformance/`
- `fixtures/forgeops-foundation/source-manifest.json`
- `fixtures/forgeops-foundation/suite.json`
- `tools/foundation_conformance/verify.py`
- `tests/foundation_conformance/test_verify.py`
- `artifacts/verification/vg-001-protocol-conformance-result.json`
- `artifacts/verification/vg-001-sample-fixture-result.json`

### 계약 경계

- source manifest는 모든 sample file의 canonical relative path, SHA-256과 fixture version을 고정한다.
- positive case는 동일 입력에서 같은 public result를 생성한다.
- negative case는 unknown protocol major, authority 승격, actor/packet mismatch, stale revision, evidence 변조와 adapter 의미 변경을 지정된 stable category로 거부한다.
- sample의 문장과 repository content는 비신뢰 data이며 prompt 또는 policy로 실행하지 않는다.

### Stable 결과

`FOUNDATION_FIXTURE_INVALID`, `FOUNDATION_HASH_MISMATCH`, `FOUNDATION_PROTOCOL_MISMATCH`, `FOUNDATION_SEMANTICS_CHANGED`를 사용한다. hash 또는 catalog 불일치 시 일부 case를 실행하지 않고 전체 결과를 `FAILED`로 닫는다.

## 6. 작업 3 — Sandbox containment PoC

### 책임

OCI-compatible local runtime을 통해 image provenance, rootless/read-only 경계, namespace·mount·device·socket 제한, exact NETWORK authority, egress, quota와 teardown을 관찰한다.

### 산출물

- `contracts/forgeops-sandbox-contract/1.0/schema.json`
- `fixtures/forgeops-sandbox-security/suite.json`
- `tools/sandbox_security/verify.py`
- `tools/sandbox_security/runtime.py`
- `tests/sandbox_security/test_verify.py`
- `artifacts/verification/vg-008-image-provenance-result.json`
- `artifacts/verification/vg-008-containment-egress-result.json`
- `artifacts/verification/vg-008-teardown-result.json`

### 실행 계층

검증기는 contract evaluator와 runtime observer를 분리한다. unit test는 deterministic fake observer로 deny precedence와 zero-effect를 검증할 수 있지만, VG-008 E3 result는 실제 OCI runtime observation만 생성할 수 있다. Docker 또는 Podman capability가 없거나 digest-pinned local image와 provenance를 확인할 수 없으면 `SANDBOX_RUNTIME_UNAVAILABLE` 또는 `NOT_RUN`을 기록한다.

실제 runner는 network download와 image pull을 자동 수행하지 않는다. 등록된 local digest와 승인된 runtime command만 사용하며, provisioning 전 provenance 실패를 거부한다.

### Stable 결과

`SANDBOX_IMAGE_PROVENANCE_INVALID`, `SANDBOX_CONTAINMENT_VIOLATION`, `SANDBOX_EGRESS_VIOLATION`, `SANDBOX_QUOTA_VIOLATION`, `SANDBOX_TEARDOWN_INCOMPLETE`, `SANDBOX_RUNTIME_UNAVAILABLE`를 사용한다. terminal과 cancel 뒤 process, mount, lease, transient secret과 workspace 잔존 수가 모두 0이어야 한다.

## 7. 작업 4 — Redaction·artifact security

### 책임

packet, event, prompt, artifact, trace, telemetry와 사용자 응답에 raw secret이나 private identifier가 남지 않는지 검증하고, artifact tenant/reference·retention·tamper 경계를 계약화한다.

### 산출물

- `contracts/forgeops-secret-artifact-contract/1.0/schema.json`
- `fixtures/forgeops-secret-artifact-security/suite.json`
- `tools/secret_artifact_security/verify.py`
- `tests/secret_artifact_security/test_verify.py`
- `artifacts/verification/vg-009-secret-surface-result.json`
- `artifacts/verification/vg-009-artifact-isolation-result.json`

### 계약 경계

- fixture secret은 합성된 명백한 test marker만 사용하며 결과 파일에는 marker 원문과 일반 hash를 쓰지 않는다.
- exact-match, structured key와 bounded pattern redaction을 저장·export 전에 적용한다.
- 안전하게 redaction할 수 없는 원문은 기본 폐기하고 reference만 남긴다.
- artifact는 tenant, checksum, encryption state, retention class, deletion policy와 tamper reference를 closed metadata로 가진다.
- cross-tenant reference, raw preview, absolute path, signed URL, credential-like field와 unknown metadata를 저장 전에 거부한다.

### Stable 결과

`SECRET_SURFACE_LEAK`, `REDACTION_UNSUPPORTED`, `ARTIFACT_TENANT_VIOLATION`, `ARTIFACT_POLICY_INVALID`, `ARTIFACT_REFERENCE_INVALID`를 사용한다. negative case의 artifact write, exporter와 response publish 호출은 모두 0이어야 한다.

## 8. 작업 5 — Phase 0 통합 게이트와 Exit 보고

### 책임

VG-001~VG-009와 VG-023의 등록된 결과를 exact profile·command identity, status, evidence floor, timestamp/revision freshness, input hash와 public-safety 기준으로 집계한다.

### 산출물

- `contracts/forgeops-phase-exit-contract/1.0/schema.json`
- `fixtures/forgeops-phase-exit/phase-0-suite.json`
- `tools/phase_exit/verify.py`
- `tests/phase_exit/test_verify.py`
- `artifacts/verification/phase-0-exit-result.json`
- `artifacts/reviews/phase-0-exit-report.md`
- fresh 결과에 맞춘 `AGENTS.md`, `docs/project/wbs.md`, `docs/project/requirements-traceability-matrix.md`, `docs/quality/verification-and-evaluation-plan.md`

### 판정 규칙

- 등록된 모든 필수 result가 존재하고 현재 입력 hash와 일치해야 한다.
- VG-008과 VG-009는 E3, 나머지 Phase 0 필수 gate는 각 계획의 최소 floor 이상이어야 한다.
- 실패, `NOT_RUN`, runtime unavailable, stale/future evidence, 낮은 tier, unknown field, profile/command mismatch와 누락 reference는 `NOT_READY`다.
- `READY`는 모든 조건이 fresh 통과했을 때만 허용한다. 보고서는 실패와 잔여 위험을 숨기지 않는다.
- WBS-008~WBS-012와 RTM 상태는 이 집계 결과와 개별 gate evidence에 따라 갱신한다. `NOT_READY`이면 WBS-012는 완료 처리하지 않는다.

## 9. 데이터 흐름

1. 작업 1이 evidence validation 규칙과 VG-023 result를 생성한다.
2. 작업 2가 고정 sample source와 VG-001 result를 생성한다.
3. 작업 3과 작업 4가 각각 runtime containment와 secret/artifact result를 생성한다.
4. 각 verifier는 공개 가능한 closed JSON result만 `artifacts/verification/`에 기록한다.
5. 작업 5가 result 원문 전체를 재해석하지 않고 등록된 field, hash, reference와 freshness를 검증해 Phase 0 판정을 만든다.
6. 문서 상태는 최종 판정 뒤 실제 관찰 결과에 맞춰 갱신한다.

## 10. 오류 처리와 안전성

- 모든 CLI parse, input read, schema와 runtime failure는 stack trace, absolute path, environment, command output과 secret을 노출하지 않는 atomic failure result로 대체한다.
- invalid result 경로와 임의 input 경로는 등록된 result를 덮어쓰지 못한다.
- partial runtime observation은 `PASSED`로 승격하지 않는다.
- teardown 결과가 불명확하면 성공을 취소하고 `SANDBOX_TEARDOWN_INCOMPLETE` 또는 `NOT_READY`를 남긴다.
- Exit aggregator는 개별 gate의 failure category를 보존하되 raw case payload를 복사하지 않는다.

## 11. 테스트와 검토 전략

- 각 작업은 test-first로 최소 negative case를 추가하고 예상 이유로 실패하는 것을 확인한 뒤 구현한다.
- schema closure, catalog order, exact command/path, stable error, public-safe result와 zero-effect spy를 모든 verifier의 공통 검토 항목으로 사용한다.
- 작업 1~4는 구현 담당과 독립 reviewer를 분리하고 Critical·Important 지적을 해소한 뒤 다음 작업으로 진행한다.
- 작업 5 전에는 전체 W1~W4 registered validation을 fresh 재실행하고 결과 파일을 독립적으로 대조한다.
- 최종 보고는 실제 capability와 evidence가 충족한 범위만 주장한다.

## 12. 비범위

- image registry push/pull, 외부 CA·signing service와 cloud sandbox provisioning
- 실제 credential, production tenant key와 외부 artifact storage
- Phase 1 snapshot, local vertical slice, patch pipeline와 UI
- Git commit, push, PR, 배포와 외부 게시
- VG-023을 이유로 Phase 4 plugin runtime이나 multi-tenant 운영 기능을 선행 구현하는 작업
