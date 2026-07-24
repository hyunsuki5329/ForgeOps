# W3-1 OpenAPI 버전·공통 envelope 설계

**작성일:** 2026-07-23  
**상태:** 사용자 승인 설계  
**범위:** `WBS-006`, `PRD-FR-003`, `PRD-NFR-006`, `ARC-012`, `VG-004`

## 1. 목적

ForgeOps의 제품 API를 OpenAPI 3.1 계약으로 고정하고 URI major version, 문서
version, 공통 identifier와 오류 envelope의 단일 의미를 정의한다. 이 작업은 API
서버를 구현하지 않으며, 이후 request/response·event·manifest 계약이 공유할 최소
인터페이스만 소유한다.

API 계약은 제품 data plane이다. 요청에 포함된 제품 계약은 authority, capability,
approval, accepted state 또는 tool 실행 권한을 만들 수 없다. canonical control은 기존
Protocol 2.0 Main 경계에서만 결정된다.

## 2. 버전과 문서 경계

- OpenAPI 문서 version은 `3.1.0`으로 고정한다.
- 제품 API major는 URI의 `/v1`로 표현하고 `info.version`은 `1.0.0`으로 고정한다.
- 계약 파일은 `contracts/forgeops-api/1.0/openapi.yaml`에 둔다.
- API body의 `api_version`은 `1.0` literal이며 URI major와 교차 검증한다.
- 알 수 없는 URI major 또는 body version은 `API_VERSION_UNSUPPORTED`로 거부한다.
- 같은 major에서 필드 의미를 바꾸거나 enum 값을 재해석하지 않는다. required 필드,
  error 의미 또는 security boundary를 바꾸는 변경은 새 major를 요구한다.

OpenAPI component schema는 JSON Schema 2020-12 의미를 사용하며 모든 object에
`additionalProperties: false`를 적용한다. 조합 schema는 상위 object의 미평가 필드가
열리지 않도록 `unevaluatedProperties: false`까지 검사한다.

## 3. 최소 API surface

W3는 다음 operation의 계약만 정의한다.

| operationId | Method/path | 책임 |
| --- | --- | --- |
| `createTask` | `POST /v1/tasks` | Product Task Contract 접수 결과 반환 |
| `getTask` | `GET /v1/tasks/{task_id}` | 제품 task와 현재 projection 조회 |
| `getRun` | `GET /v1/runs/{run_id}` | run identity와 상태 projection 조회 |
| `listRunEvents` | `GET /v1/runs/{run_id}/events` | durable event wrapper 목록 조회 |
| `getRunManifest` | `GET /v1/runs/{run_id}/manifest` | versioned run manifest 조회 |

이 operation은 runtime 저장소, pagination 성능, 인증 방식, streaming transport를
약속하지 않는다. `listRunEvents`는 W3에서 유한 JSON page 계약만 정의하며 SSE 또는
WebSocket은 후속 runtime 설계가 별도로 결정한다.

## 4. 공통 envelope와 identifier

모든 operation은 required `X-Request-ID` header를 받고 response는 그 값을
`request_id`로 되돌린다. mutation request는 `api_version`, `request_id`, endpoint별
body를 가지며 body의 `request_id`도 header와 exact match해야 한다. read request는
header와 path identity만 사용하지만 response envelope 규칙은 같다. response는
`api_version`, `request_id`, endpoint별 `data` 또는 `error` 중 정확히 하나를 갖는다.

identifier는 trim·case-fold·재작성하지 않는 non-empty ASCII literal이다.
`task_id`, `run_id`, `correlation_id`, `request_id`, `event_id`, `manifest_id`는 서로
대체할 수 없으며 schema field도 공유하지 않는다. path의 identity와 반환 body의 같은
identity가 ordinal exact match하지 않으면 `API_IDENTITY_MISMATCH`다.

오류 response는 `code`, public-safe `message`, `request_id`만 갖는다. stack trace,
원문 request, header, credential, private payload와 내부 validator message는 포함하지
않는다. 공통 stable error는 다음과 같다.

- `API_VERSION_UNSUPPORTED`
- `API_SCHEMA_INVALID`
- `API_IDENTITY_MISMATCH`
- `API_CONTROL_FIELD_FORBIDDEN`
- `API_REFERENCE_INVALID`
- `API_RESOURCE_NOT_FOUND`

## 5. 계획된 산출물과 의존성

- `contracts/forgeops-api/1.0/openapi.yaml`: version, operation, 공통 component schema
- `fixtures/forgeops-api/version-envelope-suite.json`: version·envelope positive/negative
- `tests/interface_contract/test_openapi_version.py`: closed schema와 identity 교차 검증

W3-2는 이 문서의 request/response envelope와 stable error를 소비한다. W3-3과 W3-4는
각각 event와 manifest component를 제공하고 W3-5가 OpenAPI reference 해석과 전체
`VG-004`를 집계한다.

## 6. 실패 처리와 검증 기준

검증 순서는 문서 경로·OpenAPI schema 유효성 → URI/body version → 공통 envelope의
required/type → 명시적 control claim scan → endpoint closed object → identity exact match
→ component reference 순서다. 일반 unknown field는 `API_SCHEMA_INVALID`이고 금지된
control field literal은 `API_CONTROL_FIELD_FORBIDDEN`이다. 한 case에는 첫 번째 stable
error 하나만 기록한다.

최소 fixture는 supported version, 다섯 operation의 valid envelope, unknown major,
body version mismatch, unknown field, missing required, wrong type, path/body identity
mismatch, response의 data/error 동시 존재를 포함한다. 결과 artifact에는 schema와 suite
hash, case ID, expected/actual category, count와 runtime UTC 시각만 기록한다.

완료 기준은 OpenAPI document가 자체 검증을 통과하고 모든 positive/negative case가
결정론적인 verdict를 내는 것이다. API runtime, 인증, database, network listener와 WBS
상태 변경은 이 설계 범위가 아니다.
