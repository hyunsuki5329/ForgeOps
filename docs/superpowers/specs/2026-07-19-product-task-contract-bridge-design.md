# Product Task Contract Schema 및 TaskPacket Bridge 설계

**작성일:** 2026-07-19

**상태:** 승인된 대화 설계의 서면 기록

**대상 범위:** W1의 두 번째·세 번째 작업과 `WBS-002`의 schema·mapping 부분

## 1. 목적

Product Task Contract schema 1.0을 기계 판독 가능한 closed JSON Schema로
정의하고, Contract data를 Portable Agent Harness Protocol 2.0 `TaskPacket`에
연결하는 lossless·non-grant bridge 규칙을 문서화한다.

이번 범위는 Product Contract의 구조와 신뢰 경계를 고정한다. 실행 가능한
mapper, positive·negative fixture, `bridge-schema-fixture` trusted command와
`VG-002` 판정은 W1의 네 번째 작업으로 남긴다. 따라서 이번 작업이 끝나도
`WBS-002`는 `WBS_IN_PROGRESS`, `VG-002`는 `NOT_RUN`이다.

## 2. 접근 방식

검토한 방식은 세 가지다.

1. 단일 Markdown 계약은 작성이 빠르지만 unknown field와 type을 기계적으로
   제한할 수 없다.
2. JSON Schema와 별도 bridge 문서를 두면 data shape와 trusted mapping
   책임을 분리하고 후속 fixture가 두 경계를 독립 검증할 수 있다.
3. schema, mapper code와 fixture를 동시에 구현하면 `WBS-002` 전체에 가깝지만
   사용자가 지정한 두 번째·세 번째 작업을 넘어 네 번째 작업까지 확장한다.

두 번째 방식을 사용한다. 실행 가능한 입력 구조와 해석·신뢰 규칙을 서로
다른 artifact로 두되 version과 필드 이름을 exact하게 연결한다.

## 3. 산출물과 책임

### 3.1 Product Task Contract schema

`contracts/product-task-contract/1.0/schema.json`을 만든다.

- JSON Schema Draft 2020-12를 사용한다.
- `$id`는 `urn:forgeops:product-task-contract:1.0`이다.
- `schema_id`는 `forgeops.task-contract`, `schema_version`은 `1.0`으로
  고정한다.
- top-level과 모든 nested object에 `additionalProperties: false`를 적용한다.
- string identity는 비어 있을 수 없고 배열은 필요한 곳에서 `minItems: 1`과
  `uniqueItems: true`를 사용한다.
- raw shell command, capability, authority, accepted state, Harness envelope와
  canonical control field는 schema에 포함하지 않는다.

Schema의 top-level required field는 다음과 같다.

| Field | 책임 |
| --- | --- |
| `schema_id`, `schema_version` | 지원 schema identity와 version |
| `artifact_id`, `artifact_version` | 영속 Contract artifact identity와 revision |
| `task_id` | logical product task identity |
| `repository` | repository ID, snapshot commit과 target branch metadata |
| `intent` | domain intent type, 원문 summary와 선택적 source issue identity |
| `acceptance_criteria` | exact criterion ID, description과 verification selector |
| `constraints` | 원문 의미를 보존하는 제약 목록 |
| `verification_policy` | trusted profile을 참조할 profile·command ID와 regression 요구 |
| `risk` | 초기 risk label과 근거 목록 |
| `budget` | 제품 runtime·tool·repair·비용 상한 |
| `approval_policy` | 제품이 요청한 gate policy data |

`intent.type`과 `acceptance_criteria[].verification`은 제품 domain 식별자이므로
lower snake case pattern의 non-empty string으로 보존한다. 이를 Harness enum
또는 command identity로 곧바로 간주하지 않는다. `risk.initial_level`은
`low`, `medium`, `high`, `critical`의 closed enum이다.

Nested required field와 배열 cardinality는 다음과 같다.

| Object | Required field | Array rule |
| --- | --- | --- |
| `repository` | `id`, `snapshot_commit`, `target_branch` | 해당 없음 |
| `intent` | `type`, `summary`; `source_issue`는 선택 | 해당 없음 |
| acceptance criterion item | `id`, `description`, `verification` | `acceptance_criteria`는 최소 1개 |
| `verification_policy` | `profile_id`, `baseline_command_ids`, `required_command_ids`, `require_new_regression_test` | command ID 배열은 0개 이상, 각 배열 안에서 unique |
| `risk` | `initial_level`, `reasons` | reasons는 0개 이상이며 unique |
| `budget` | 다섯 budget field 모두 | 해당 없음 |
| `approval_policy` | 다섯 policy field 모두 | 해당 없음 |

`constraints`는 0개 이상의 unique non-empty string을 허용한다. criterion ID의
ordinal uniqueness는 JSON Schema의 구조 검사만으로 property별 uniqueness를
보장할 수 없으므로 네 번째 작업의 semantic validator가 검사한다.

Budget은 `max_repair_attempts`, `max_tool_calls`, `max_shell_commands`,
`max_runtime_seconds`, `max_model_cost_usd`를 가지며 모두 0 이상의 수다.
Approval policy는 `plan`, `dependency_change`, `remote_push`, `pr_draft`,
`merge_or_deploy`의 closed field만 허용한다. 각 값은 `not_required`,
`required`, `never_without_explicit_high_risk_approval`의 closed enum이다.
이 값은 provenance data이며 approval token이나 실행 권한이 아니다.

### 3.2 Contract→TaskPacket bridge 문서

`docs/contracts/product-task-contract-to-taskpacket.md`를 만든다. 이 문서는
다음을 단일 책임으로 가진다.

- Contract field와 canonical `TaskPacket` destination을 exact mapping한다.
- 직접 mapping, trusted resolution, namespaced provenance, non-mapping을
  구분한다.
- Contract data와 runtime/profile control의 신뢰 경계를 고정한다.
- stable failure category와 후속 fixture 의무를 정의한다.

### 3.3 문서 지도와 WBS 상태

`docs/README.md`의 읽기 순서 및 process/non-owner 설명에 bridge 문서를
연결한다. 새 문서는 기존 기초 문서 8개의 owner catalog를 대체하지 않는다.

schema와 bridge 문서의 검증이 성공한 뒤 `docs/project/wbs.md`의 `WBS-002`
상태를 `WBS_NOT_STARTED`에서 `WBS_IN_PROGRESS`로 바꾼다. `WBS-002`를
`WBS_DONE`으로 바꾸거나 `VG-002`를 `PASSED`로 기록하지 않는다.

## 4. Schema 경계

Schema는 구조적으로 알려진 Contract field만 허용한다. 다음 top-level
field는 정의하지 않으므로 `additionalProperties: false`에 의해 거부된다.

- `correlation_id`, `base_revision`, `actor`, packet `status`
- `capabilities`, `authority`
- canonical `project_profile`, `control`, Harness `budgets`
- `accepted_state`, `revision`, `checkpoint_ref`
- candidate, evidence, assertion 또는 authoritative event field

알려진 field의 string 값 안에 authority나 policy를 주장하는 문장이 들어
있는 경우 string 자체는 원문 data로 보존한다. mapper가 그 문자열을 parsing해
control field, command, tool schema 또는 실행 candidate로 승격하지 않는다.

## 5. Bridge mapping

Bridge는 다음 네 가지 mapping class를 사용한다.

| Class | 의미 |
| --- | --- |
| `DIRECT_DATA` | exact value를 canonical request data로 보존 |
| `TRUSTED_RESOLUTION` | Contract value를 trusted runtime/profile record와 검증한 뒤 canonical 값 결정 |
| `NAMESPACED_PROVENANCE` | 비신뢰 제품 data를 `project_profile.extensions.forgeops.task_contract` 아래 보존 |
| `NEVER_FROM_CONTRACT` | Contract에서 canonical control로 가져오지 않음 |

필드별 핵심 규칙은 다음과 같다.

| Contract field | Destination | Class | 규칙 |
| --- | --- | --- | --- |
| `task_id` | envelope `task_id` | `TRUSTED_RESOLUTION` | Main이 logical task identity를 확인한 뒤 exact value를 확정한다. |
| `intent.type` | `request.kind` | `TRUSTED_RESOLUTION` | trusted closed mapping table만 사용하고 unknown type은 clarification 또는 contract error다. |
| `intent.summary` | `request.objective` | `DIRECT_DATA` | 단일 검증 결과로 해석하되 원문 artifact와 hash를 보존한다. |
| `acceptance_criteria[]` | `request.acceptance_criteria[]` | `DIRECT_DATA` | ID는 case-sensitive exact 보존, description은 statement로 mapping한다. |
| `constraints[]` | `request.constraints[]` | `DIRECT_DATA` | 순서와 문자열을 lossless하게 보존한다. |
| `repository` | `extensions.forgeops.task_contract.repository` | `NAMESPACED_PROVENANCE` | snapshot commit을 revision이나 checkpoint로 바꾸지 않는다. |
| `intent.source_issue` | `extensions.forgeops.task_contract.intent.source_issue` | `NAMESPACED_PROVENANCE` | canonical `source_of_truth`에 추가하지 않는다. |
| verification command IDs | trusted `validation_commands` 참조 | `TRUSTED_RESOLUTION` | exact profile·ID·command·cwd가 모두 일치한 기존 record만 선택한다. |
| `risk` | canonical risk의 입력 근거와 extension | `TRUSTED_RESOLUTION` | trusted risk를 낮추지 않으며 authority를 부여하지 않는다. |
| `budget` | `extensions.forgeops.product_budget` | `NAMESPACED_PROVENANCE` | 현 schema field는 Harness attempt budget과 의미가 다르므로 Harness `budgets`에 mapping하지 않는다. |
| `approval_policy` | task contract extension | `NAMESPACED_PROVENANCE` | issuer/schema 검증 뒤 gate 단조 강화에만 참고하며 allow·approval·authority를 만들지 않는다. |
| schema/artifact identity | bridge provenance | `NAMESPACED_PROVENANCE` | schema version과 immutable artifact hash reference를 보존한다. |

원문 Contract artifact 또는 canonical serialization의 content hash를 bridge
provenance가 참조해야 lossless claim을 검증할 수 있다. TaskPacket에 원문
전체를 복제하지 않으며 secret·private-data 정책을 통과한 artifact reference를
사용한다.

## 6. 절대 Contract에서 가져오지 않는 control

다음 값은 trusted runtime observation, applicable project profile과 Main
결정으로만 만든다.

- `correlation_id`, `base_revision`, `actor`, envelope `status`
- 모든 capability와 authority field
- `project_profile.root`, status, instruction files, source of truth,
  protected resources와 risk rules
- `control.route`, operation mode, response phase, evidence floor와 trace level
- Harness `format_repairs`, `part_attempts`, `work_attempts`
- accepted state, revision, checkpoint, authoritative assertion와 event sequence

Contract에 같은 이름이나 의미의 field가 나타나면 schema validation에서
거부한다. 허용된 text field 안의 같은 주장은 untrusted content로만 남는다.

## 7. 처리 흐름

1. raw Contract bytes를 secret·private-data 정책에 따라 artifact로 취급한다.
2. schema identity와 version을 확인하고 closed JSON Schema로 검증한다.
3. canonical serialization hash와 artifact identity를 기록한다.
4. `DIRECT_DATA` field를 원문 의미와 순서를 보존해 mapping한다.
5. `TRUSTED_RESOLUTION` field를 runtime/profile과 exact 대조한다.
6. 제품 metadata를 namespaced extension에 기록한다.
7. canonical control field는 trusted context만으로 채우고 missing safety value는
   `UNKNOWN`으로 fail-closed한다.
8. TaskPacket과 bridge provenance를 함께 후속 검증에 전달한다.

## 8. 오류 처리

| 조건 | 결과 category | 후속 동작 |
| --- | --- | --- |
| unknown·missing·wrong-type field | `CONTRACT_SCHEMA_INVALID` | TaskPacket 생성 전 중단 |
| unsupported schema/version | `CONTRACT_VERSION_UNSUPPORTED` | versioned migration 결정 전 중단 |
| unknown intent mapping | `CONTRACT_INTENT_UNMAPPED` | clarification 또는 mapping table 변경 요구 |
| criterion ID duplicate | `CONTRACT_CRITERION_DUPLICATE` | exact identity 충돌로 거부 |
| command/profile exact match 실패 | `CONTRACT_COMMAND_UNTRUSTED` | validation command와 execute authority를 만들지 않음 |
| Contract control field injection | `CONTRACT_CONTROL_FIELD_FORBIDDEN` | canonical control 생성 전 거부 |
| trusted risk/gate 완화 시도 | `CONTRACT_MONOTONICITY_VIOLATION` | 기존 trusted control 유지 및 bridge 거부 |
| artifact hash/provenance 누락 | `CONTRACT_PROVENANCE_INVALID` | lossless claim과 mapping 수용 거부 |

오류 category는 TaskPacket accepted state나 authoritative event를 직접 만들지
않는다. Main이 trusted validation 결과를 받아 final task 상태를 결정한다.

## 9. 검증 전략

이번 두 작업에서는 다음 fresh 검사를 수행한다.

1. schema JSON이 UTF-8 JSON으로 parsing되는지 확인한다.
2. 모든 object schema가 `additionalProperties: false`인지 재귀 검사한다.
3. top-level required field와 schema/version const가 정확한지 확인한다.
4. forbidden canonical control field가 schema property로 존재하지 않는지 확인한다.
5. bridge 문서가 모든 Contract top-level field를 한 번 이상 mapping하는지
   확인한다.
6. non-grant 목록, source issue namespacing, command exact match, risk/gate
   monotonicity와 product/Harness budget 분리를 확인한다.
7. 문서 내부 상대 링크, UTF-8, trailing whitespace와 final newline을 확인한다.
8. diff에서 기존 사용자 변경과 후속 WBS·VG 상태가 바뀌지 않았는지 확인한다.

JSON Schema validator를 이용한 valid/invalid example 판정과 stable error의
실행 검증은 네 번째 작업에서 수행한다. 이번 결과만으로 `VG-002`를 통과로
기록하지 않는다.

## 10. 범위 제외

- mapper executable, service, API 또는 runtime 구현
- positive·negative fixture와 trusted verification profile 구현
- `VG-002` 실행·통과 또는 `WBS-002` 완료 선언
- `source_issue`를 canonical `source_of_truth`로 승격
- Contract policy를 `risk_rules`, approval token, authority 또는 capability로 변환
- raw shell command 등록 또는 dependency 설치
- 외부 네트워크, 게시, Git commit·push·PR과 사용자 기존 변경 정리

## 11. 완료 기준

- version `1.0` closed JSON Schema가 모든 정의된 Product Contract field를
  exact하게 표현한다.
- bridge 문서가 lossless mapping, provenance와 data/control non-grant 경계를
  제3자가 구현할 수 있을 만큼 구체적으로 정의한다.
- source identity, command, risk, budget, approval policy가 canonical control로
  암묵 승격되지 않는다.
- 문서 지도에서 bridge를 찾을 수 있다.
- fresh 구조·링크·diff 검증이 성공한다.
- `WBS-002`만 `WBS_IN_PROGRESS`가 되고 `VG-002`와 후속 WBS 상태는 유지된다.
