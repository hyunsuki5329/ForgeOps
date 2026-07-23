# W2-2 Replay 계약·identity guard 설계

**작성일:** 2026-07-22  
**상태:** 사용자 승인 설계  
**범위:** `WBS-004`의 replay closed mode·lineage·효과 차단과 `VG-003` replay 영역

## 1. 목적

Replay는 과거 실행의 권한을 재사용하는 기능이 아니라, source lineage를
보존한 새 실행을 만드는 계약이다. 이 작업은 `AUDIT_REPLAY`, `REEXECUTE`,
`COUNTERFACTUAL`만 허용하고, identity 재사용·control 복사·금지된 외부 효과를
fixture 단계에서 fail-closed로 거부한다.

## 2. mode별 규칙

| Mode | 허용 목적 | 외부 효과 규칙 |
| --- | --- | --- |
| `AUDIT_REPLAY` | 저장된 event·artifact의 read-only 재생 | 항상 거부 |
| `REEXECUTE` | 고정 manifest 기반 새 실행과 결과 비교 | 기본 거부; effect별 새 gate 필요 |
| `COUNTERFACTUAL` | 명시된 model·prompt·policy 변수의 분리 실험 | 항상 거부 |

모든 mode는 `source_task_id`, `source_run_id`, `source_manifest_id`를 보존하고
새 `run_id`, `correlation_id`, revision/event sequence, evidence namespace를
가져야 한다. Contract 자체를 바꾸는 `COUNTERFACTUAL`은 새 `task_id`도 필수다.

## 3. 금지된 복사와 새 효과 조건

source run의 TaskPacket authority, approval capability/token, nonce, credential,
publisher token, external-effect dispatch result는 새 run으로 복사할 수 없다.
offline input은 immutable artifact로 보존된 기존 external response만 쓸 수
있으며, 새 live fetch는 별도 exact NETWORK action이다.

`REEXECUTE`에서 실제 외부 효과가 필요해도 먼저 현재 remote state를 관찰한다.
그 뒤 effect별 새 candidate, 현재 revision, 새 approval capability, 새 nonce,
fresh evidence, exact authority 및 capability의 교집합이 있을 때만 후속
approval policy 작업이 허용 여부를 판단한다. timeout 또는 결과 미상인
비멱등 effect는 reconcile 전 자동 재시도하지 않는다.

## 4. 구성과 인터페이스

- `contracts/forgeops-replay-contract/1.0/schema.json`: closed mode, lineage,
  source/new identity, override declaration, requested effect descriptor를 정의한다.
- `fixtures/forgeops-replay-contract/suite.json`: mode별 positive·negative
  cases와 forbidden-control sentinel을 보관한다.
- `tools/replay_contract/verify.py`: schema와 identity·copy·effect guard를
  순서대로 검사한다.
- `tests/replay_contract/test_verify.py`: 새 identity, control zero-copy,
  mode hard deny 및 unknown-outcome behavior를 회귀 검증한다.

validator output은 lineage 요약과 case result만 기록한다. credential, approval
token, signature, nonce 원문, raw payload는 result·log·evidence에 기록하지 않는다.

## 5. 오류 우선순위와 fixture

검증 우선순위는 schema/mode → lineage completeness → new identity → forbidden
control copy → mode effect hard deny → REEXECUTE fresh-effect precondition →
unknown outcome reconciliation이다. stable category는 `REPLAY_SCHEMA_INVALID`,
`REPLAY_MODE_INVALID`, `REPLAY_LINEAGE_MISSING`, `REPLAY_IDENTITY_REUSED`,
`REPLAY_CONTROL_COPY_FORBIDDEN`, `REPLAY_EXTERNAL_EFFECT_FORBIDDEN`,
`REPLAY_REAPPROVAL_REQUIRED`, `REPLAY_RECONCILIATION_REQUIRED`를 사용한다.

fixture는 각 mode의 정상 read-only/new-run case, invalid mode, source lineage 누락,
run/correlation/sequence reuse, COUNTERFACTUAL task ID 누락, authority·approval·
nonce·credential 복사, AUDIT/COUNTERFACTUAL effect 시도, REEXECUTE의 old approval
사용, unknown outcome 자동 retry를 포함한다.

## 6. 검증과 범위 제외

`replay-contract-negative`는 E2 safe result JSON을 만들고 모든 negative가
effect dispatcher 호출 전에 거부되었음을 spy count로 확인한다. W2 fixture는
실제 remote query, credential injection, publisher, durable manifest storage를
실행하지 않는다. 이 작업은 W3 event/manifest schema 및 Phase 3 integration의
idempotency ledger 구현을 대체하지 않는다.
