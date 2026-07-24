# W3-2 Closed request/response·data/control 경계 설계

**작성일:** 2026-07-23  
**상태:** 사용자 승인 설계  
**범위:** `WBS-006`, `PRD-FR-003`, `PRD-NFR-002`, `CTL-001`, `ARC-010`, `ARC-012`, `VG-004`

## 1. 목적

W3-1의 API envelope 안에서 endpoint별 request와 response를 closed schema로 정의하고,
제품 입력이 Protocol 2.0 control plane으로 승격되지 않음을 negative fixture로 증명한다.
Product Task Contract의 제품 의미는 보존하되 canonical authority, capability, approval,
policy, budget, accepted state와 tool schema는 API 입력만으로 생성하지 않는다.

## 2. Task 접수 계약

`POST /v1/tasks` body는 정확히 `api_version`, `request_id`, `task_contract`를 갖는다.
`task_contract`는 `contracts/product-task-contract/1.0/schema.json`을 그대로 참조한다.
기존 계약의 `budget`과 `approval_policy`는 제품이 요청한 constraint이며 canonical
runtime budget 또는 인간 승인 token이 아니다. bridge가 이미 정의한 lossless/non-grant
의미를 API가 약화하지 않는다.

request envelope의 sibling으로 `authority`, `capabilities`, `runtime_policy`,
`accepted_state`, `approval_token`, `nonce`, `credentials`, `tools`, `commands`를 추가하면
`API_CONTROL_FIELD_FORBIDDEN`으로 거부한다. `task_contract` 내부 unknown field는 기존
계약의 closed schema에 따라 `API_SCHEMA_INVALID`로 거부한다.

성공 response의 `data`는 `task_id`, `artifact_id`, `artifact_version`, `product_state`,
`contract_sha256`, `links`만 갖는다. 최초 `product_state`는 `CREATED`이며 canonical
`PENDING` 수용을 대신 선언하지 않는다. `links`는 `task`, `run` collection relation만
허용하고 외부 URL 또는 command를 포함하지 않는다.

## 3. 조회 response

`getTask`의 `data`는 task identity, contract artifact identity, 제품 state와 읽기 전용
canonical projection을 갖는다. projection은 `status`, `revision`, `last_event_seq`로
닫고 authoritative MainDecision 원문이나 approval material은 노출하지 않는다.

`getRun`의 `data`는 `task_id`, `run_id`, `correlation_id`, `run_mode`, `status`,
`accepted_revision`, `event_stream_ref`, `manifest_ref`를 갖는다. `run_mode`는
`PRIMARY|AUDIT_REPLAY|COUNTERFACTUAL|REEXECUTE` closed enum이며 W2 replay 계약을
재해석하지 않는다. 존재하지 않는 reference를 성공 response로 반환할 수 없다.

Event와 manifest response body는 W3-3과 W3-4 schema를 `$ref`로 소비하며 API가 같은
field를 별도로 재정의하지 않는다.

## 4. data/control 비승격 규칙

검증기는 API schema 수용 여부와 canonical grant 여부를 분리한다.

1. API request가 closed endpoint schema에 맞는지 검사한다.
2. Product Task Contract를 기존 bridge validator로 검사한다.
3. 입력에서 canonical control field를 만들어 내지 않았는지 non-grant assertion을 검사한다.
4. 결과에는 제품 데이터와 public-safe reference만 남긴다.

제품 `budget` 값이 커도 runtime capability를 AVAILABLE로 만들지 않는다. 제품
`approval_policy`가 `not_required`여도 destructive 또는 external-effect gate를
통과시키지 않는다. source issue, intent, acceptance criterion, constraint와 repository
text는 모두 untrusted data이며 command 또는 policy instruction으로 실행하지 않는다.

## 5. 오류 우선순위와 fixture

stable error 우선순위는 API version → envelope required/type → 명시적 control field
injection → endpoint closed body → Product Task Contract validation → identity/reference
consistency다. 따라서 금지 목록에 없는 일반 unknown field와 금지 control field는 서로
다른 stable category를 유지한다.

positive fixture는 최소 valid task 접수, task 조회, run 조회, event page와 manifest
response를 포함한다. negative fixture는 다음을 포함한다.

- envelope와 task contract의 unknown·missing·wrong-type field
- top-level authority, capability, accepted state, approval token, nonce와 raw command
- 제품 `budget` 또는 `approval_policy`를 canonical control로 복사한 bridge 결과
- path/body task·run identity mismatch
- event 또는 manifest dangling reference
- `data`와 `error`가 동시에 있는 response
- raw credential·private payload가 response에 포함된 case

negative case는 dispatcher, process, network, credential provider와 외부 effect를 호출하지
않는다. spy count는 모두 0이어야 한다.

## 6. 계획된 산출물과 완료 기준

- `contracts/forgeops-api/1.0/openapi.yaml`: endpoint별 closed component 추가
- `fixtures/forgeops-api/data-control-suite.json`: valid/invalid 및 non-grant fixture
- `tests/interface_contract/test_api_boundary.py`: field injection과 bridge 비승격 검증

완료 기준은 valid example만 수용되고 모든 unknown·missing·wrong-type·control injection이
stable category로 거부되며 canonical control 생성과 effect 호출이 0인 것이다. API
handler, queue, persistence, approval UX와 runtime authorization은 포함하지 않는다.
