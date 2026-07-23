# W2-1 상태 전이·매핑 계약 설계

**작성일:** 2026-07-22  
**상태:** 사용자 승인 설계  
**범위:** `WBS-004`의 상태 매핑, revision·sequence 검증 및 `VG-003` 상태 영역

## 1. 목적

제품 workflow state, Protocol 2.0 canonical accepted state, WBS 상태를 서로
독립된 축으로 유지한다. fixture-local validator는 제품 state 후보가 Protocol
전이 규칙과 Main 소유권을 만족하는지만 판정하며, 제품 runtime·queue·durable
event store를 구현하지 않는다.

특히 `CANCELLED`는 현재 Protocol accepted state에 매핑하지 않는다. 취소는
제품 계층의 terminal 결과와 `USER_CANCELLED` reason으로 보존하고, 이전의
유효한 MainDecision을 덮어쓰지 않는다.

## 2. 계약 경계

입력은 versioned state-contract fixture와 trusted current snapshot이다.
snapshot은 `task_id`, `correlation_id`, 현재 canonical `status`, `revision`,
다음 canonical `seq`와 actor를 가진다. proposal은 product workflow state,
후보 canonical state, `base_revision`, `expected_seq`, actor 및 필요한
evidence reference만 가진다.

출력은 `ACCEPT` 또는 하나의 stable error category다. 성공 결과는 다음
revision과 seq만 요약해 기록하며 raw packet, evidence 본문, secret 또는
private data를 결과 artifact에 복제하지 않는다. authoritative accepted state를
실제로 생성하거나 변경하는 것은 항상 MainDecision이며, validator의 성공은
fixture-local 관찰일 뿐이다.

## 3. 매핑과 전이 규칙

| 제품 workflow state | 후보 canonical state | 추가 조건 |
| --- | --- | --- |
| `CREATED` | `PENDING` | Main의 최초 수용만 가능 |
| `TRIAGING`~`EVALUATING`의 active states | `IN_PROGRESS` | Part/Work는 proposal만 제출 |
| `AWAITING_*`, `REVIEW_REQUIRED` | `WAITING_FOR_HUMAN` | 사람 결정과 재개 조건 필요 |
| `PARTIAL_RESULT` | `PARTIAL` | 관찰된 산출물과 승인된 continuation 필요 |
| `COMPLETED_VERIFIED` | `SUCCEEDED` | 모든 필수 criterion의 fresh evidence 필요 |
| `POLICY_BLOCKED`, `BASELINE_UNHEALTHY` | `BLOCKED` | 새 authority·capability·사람 결정 필요 |
| `FAILED`, `REJECTED` | `FAILED` | 실행 또는 검증 시도 실패가 확인됨 |
| `BUDGET_EXCEEDED` | `FAILED` 또는 `BLOCKED` | 실패 원인 또는 새 결정 필요 여부로 명시 |
| `CANCELLED` | 없음 | 강제 변환 금지 |

canonical transition은 `PENDING → IN_PROGRESS`, `IN_PROGRESS →
WAITING_FOR_HUMAN|BLOCKED|SUCCEEDED|FAILED|PARTIAL`, `WAITING_FOR_HUMAN →
IN_PROGRESS|BLOCKED`, `PARTIAL → IN_PROGRESS|SUCCEEDED|FAILED|BLOCKED`만
허용한다. `BLOCKED`, `SUCCEEDED`, `FAILED`는 terminal이며 `PARTIAL`은 구체적이고
승인된 continuation이 있을 때만 non-terminal이다.

## 4. 구성과 데이터 흐름

예정 산출물은 아래와 같다.

- `contracts/forgeops-state-contract/1.0/schema.json`: closed fixture input
  schema와 product-state enum, actor·revision·sequence field를 정의한다.
- `fixtures/forgeops-state-contract/state-suite.json`: positive와 negative
  mapping·transition case를 보관한다.
- `tools/state_contract/verify.py`: schema 검사 뒤 semantic state validation을
  수행하고 safe result JSON을 생성한다.
- `tests/state_contract/test_verify.py`: case catalog, stable error priority,
  failed-run artifact 보존을 회귀 검증한다.

검증 순서는 schema/closed enum → task·correlation identity → Main actor
ownership → base revision exact match → expected next sequence exact match →
canonical transition → product-to-canonical mapping 조건 → evidence 조건이다.
한 case에는 가장 앞선 위반 하나만 기록한다.

## 5. 오류와 fixture

stable category는 `STATE_SCHEMA_INVALID`, `STATE_OWNER_INVALID`,
`STATE_REVISION_STALE`, `STATE_SEQUENCE_OUT_OF_ORDER`,
`STATE_TRANSITION_INVALID`, `STATE_MAPPING_INVALID`,
`STATE_CANCELLED_COERCION_FORBIDDEN`, `STATE_EVIDENCE_INSUFFICIENT`으로
설계한다. 세부 validator message는 local diagnostic에만 쓰고 public-safe
result에는 category만 쓴다.

최소 fixture는 정상 생성·진행·대기·부분·성공·차단 전이, stale revision,
sequence skip/reuse, Part 또는 Work의 authoritative state 시도, terminal
state 재개, evidence 없는 success, `CANCELLED → FAILED|BLOCKED` coercion을
포함한다. `event-order-fixture`는 durable `stream_seq`를 구현하지 않고
Main canonical `seq`만 검사한다. durable wrapper와 `stream_seq`는 W3
`WBS-007`의 소유 범위다.

## 6. 검증과 완료 기준

`state-transition-fixture`와 `event-order-fixture`는 같은 E2 profile 아래
실행하되 결과는 command ID별로 식별한다. result에는 schema/suite hash,
case ID, 기대·실제 category, case count, strict UTC `observed_at`만 기록한다.

완료 기준은 모든 positive가 accepted mapping을 보이고 모든 negative가 exact
stable category로 effect 전에 거부되는 것이다. 이 작업은 `VG-003`의 상태
영역만 다루며 replay contract, 권한 정책, API/event wrapper, runtime 상태
저장소 및 WBS 상태 변경은 포함하지 않는다.
