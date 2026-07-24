# W3-5 VG-004 통합 conformance fixture·검증기 설계

**작성일:** 2026-07-23  
**상태:** 사용자 승인 설계  
**범위:** `WBS-006`~`WBS-008`, `PRD-FR-003`, `PRD-FR-004`, `PRD-NFR-006`, `VG-004`

## 1. 목적

W3-1~4의 OpenAPI, data/control boundary, durable event와 run manifest를 한 번의
재현 가능한 E2 검증으로 연결한다. component별 schema 통과만으로 완료를 선언하지
않고 cross-contract identity, provenance와 reference resolution까지 검증한다.

## 2. 검증기 구성

계획된 검증기는 `tools/interface_contract/verify.py`이며 다음 trusted input만 받는다.

- `contracts/forgeops-api/1.0/openapi.yaml`
- `contracts/forgeops-event/1.0/schema.json`
- `contracts/forgeops-run-manifest/1.0/schema.json`
- `fixtures/forgeops-api/version-envelope-suite.json`
- `fixtures/forgeops-api/data-control-suite.json`
- `fixtures/forgeops-event-contract/suite.json`
- `fixtures/forgeops-run-manifest/suite.json`

CLI의 schema, suite와 result path는 AGENTS에 등록된 exact literal만 허용한다. 임의
result path에는 쓰지 않고 failure artifact도 등록된
`artifacts/verification/vg-004-interface-contract-result.json`에만 기록한다.

검증기는 HTTP server, process, DNS, socket, filesystem artifact read, credential
provider와 external store를 호출하지 않는다. 모든 dispatch surface는 in-memory spy이고
negative case의 호출 수는 0이어야 한다.

## 3. 검증 순서와 cross-contract 규칙

검증 순서는 다음과 같다.

1. exact input/result path와 suite catalog identity
2. OpenAPI·JSON Schema 자체 유효성
3. version과 closed object
4. API data/control non-grant
5. task/run/correlation identity exact match
6. canonical seq와 durable stream ordering
7. revision과 provenance hash
8. manifest catalog uniqueness
9. artifact/evidence reference resolution과 freshness union
10. public-safe result assertion

API의 run response가 가리키는 `event_stream_ref`와 `manifest_ref`는 fixture의 같은
task/run에서 해석되어야 한다. event의 evidence reference는 manifest catalog에서 정확히
한 번 해석되고 producer sequence 범위에 있어야 한다. manifest terminal status와 최종
Main event의 canonical status·accepted revision이 일치해야 한다.

## 4. Case catalog와 stable failure

component suite는 exact ordered case catalog를 사용한다. case 추가·삭제·rename은 suite
version 변경과 reviewer 확인 없이는 허용하지 않는다. 최소 통합 negative는 다음이다.

- 지원하지 않는 API/schema version
- API control field injection과 canonical grant 시도
- API/task/run/event/manifest identity 혼합
- canonical seq와 stream_seq reuse·skip
- stale accepted revision과 잘못된 source hash
- duplicate artifact/evidence ID
- dangling, cross-run, producer-range 밖 reference
- revision/time freshness wrong-mode
- raw credential/private payload가 public result로 유입되는 case
- 임의 result path와 변조된 suite catalog

component stable error는 각 설계의 category를 유지한다. runner 자체 계약 위반은
`INTERFACE_RUNNER_CONTRACT_INVALID`, cross-contract 관계 위반은
`INTERFACE_CROSS_REFERENCE_INVALID`, public-safe assertion 위반은
`INTERFACE_RESULT_UNSAFE`로 구분한다.

## 5. Result artifact와 등록 profile

result artifact는 다음만 기록한다.

- `gate_id="VG-004"`, `profile_id`, `command_id`, `status`
- OpenAPI/schema/suite SHA-256
- strict UTC `observed_at`
- component별 total/passed/failed
- case ID, kind, expected, actual, status
- negative zero-spy-call과 no-sensitive-content assertion

raw request/response/event/manifest, 내부 exception, token, credential, private identifier와
absolute host path는 기록하지 않는다. 모든 required component가 100% 통과하고 runner
assertion이 참일 때만 result가 `PASSED`다.

구현 시 AGENTS에는 하나의 required command `interface-contract-fixture`와 하나의
verification profile `forgeops-interface-contract`를 추가한다. 설계 문서 작성만으로는
등록하거나 WBS·RTM Result를 변경하지 않는다.

## 6. 테스트와 완료 기준

계획된 unit test는 다음으로 분리한다.

- `tests/interface_contract/test_openapi_version.py`
- `tests/interface_contract/test_api_boundary.py`
- `tests/interface_contract/test_event_wrapper.py`
- `tests/interface_contract/test_run_manifest.py`
- `tests/interface_contract/test_verify.py`

완료 기준은 unit test와 registered `interface-contract-fixture`가 fresh E2로 통과하고,
schema/suite hash가 현재 파일과 일치하며, negative spy call과 sensitive-content count가
0인 것이다. 그 이후에만 WBS-006~008과 RTM의 mapped requirement 상태를 evidence
순서에 맞춰 검토할 수 있다. 실제 API service, durable store, streaming transport,
artifact storage와 W4 sample repository는 이 설계 범위가 아니다.

## 7. W3 설계 자체 검토 결과

| 검토 항목 | 결과 | 확인 내용 |
| --- | --- | --- |
| 요구사항 coverage | 통과 | W3-1·2가 WBS-006/PRD-FR-003, W3-3이 WBS-007, W3-4가 WBS-008/PRD-FR-004, W3-5가 VG-004 통합을 소유한다. |
| placeholder | 통과 | 다섯 문서에 미결정 placeholder와 빈 section이 없다. |
| interface 일관성 | 통과 | API `task_id/run_id`, event `seq/stream_seq`, manifest run mode와 reference 이름이 문서 간 일치한다. |
| control boundary | 통과 | Product Task Contract의 제품 budget/approval policy를 보존하지만 canonical control grant로 해석하지 않는다. |
| ownership | 통과 | Main만 canonical event `seq`를 확정하고 durable wrapper는 MainDecision source만 수용한다. |
| reference·hash | 통과 | manifest 자기 hash 제외 범위, evidence freshness union과 cross-run 거부 규칙이 명시돼 있다. |
| scope | 통과 | API/store/runtime 구현, W4 fixture, WBS·RTM 상태 변경은 제외되어 설계 작업이 W3 계약 범위에 머문다. |

자체 검토에서 수정한 사항은 공통 request ID header, control-field 오류 우선순위,
Part/Work event suggestion의 Main 정규화 경계, `PRIMARY` run mode와 manifest 자기 hash
계산 범위다. 현재 설계를 구현 계획으로 전환하는 데 필요한 blocking ambiguity는 없다.
