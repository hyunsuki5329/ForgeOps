# W2-5 승인·파괴적/외부 효과 gate 설계

**작성일:** 2026-07-22  
**상태:** 사용자 승인 설계  
**범위:** `WBS-005`의 approval policy, destructive/external gate 및 `VG-007`

## 1. 목적

승인은 authority를 만드는 token이 아니라, 이미 허용된 한 candidate의 한
closed action identity와 모든 effect input에 결합하는 추가 gate다. 이 작업은
`DENIED`·`UNKNOWN`, 만료·거절·wrong audience, 입력 변경, nonce reuse가 실제
효과 전에 거부되고 dispatcher 호출이 0임을 fixture로 검증한다.

## 2. dispatch 교집합

dispatch 허용 조건은 다음 모두다: `EXECUTE` operation mode, 대응 capability
`AVAILABLE`, current authority의 exact match, approved candidate, current base
revision, closed action identity, protected/ownership/idempotency preflight.
하나라도 누락되거나 불일치하면 approval이 있어도 deny한다.

destructive action은 `destructive_actions=ALLOWED`를, external effect는 runtime
`external_side_effects=AVAILABLE`와 authority `external_side_effects=ALLOWED`를
각각 별도로 요구한다. 둘은 서로 대체하지 않으며, 외부 효과의 approval은
RESOURCE·COMMAND·NETWORK exact authority 검사를 생략하게 하지 않는다.

## 3. approval binding과 nonce

approval record는 candidate ID, action identity, target, tenant, issuer,
audience, approver subject, policy/key version, not-before, expiry, nonce,
signature reference와 canonical `effect_hash`를 가진다. `effect_hash`는
revision, Contract/plan/policy identity, target, diff, payload와 effect inputs를
모두 결합한다. 이 중 하나라도 바뀌면 새 승인이 필요하다.

nonce는 effect 직전에 atomic consume interface로 한 번만 소비한다. fixture는
in-memory deterministic nonce ledger를 dependency injection으로 사용해 첫
성공 뒤 동일 nonce의 두 번째 dispatch가 반드시 거부됨을 확인한다. token과
signature 원문은 fixture result, event, log, evidence에 저장하지 않는다.

## 4. 구성과 데이터 흐름

- `fixtures/forgeops-approval-policy/suite.json`: public-safe policy, action,
  approval metadata, nonce-ledger scenario를 정의한다.
- `tools/policy_contract/verify.py approval`: W2-3의 common envelope를 읽어
  hard gate → authority intersection → approval binding → temporal/tenant
  checks → atomic nonce → spy dispatcher 순서로 검사한다.
- `tests/policy_contract/test_approval.py`: mutation of every bound input,
  negative priority, nonce atomicity, zero-dispatch assertion을 검증한다.

실제 cryptographic key store나 external approval UI를 만들지 않는다. signature
검증은 fixture-local trusted verifier interface와 public-safe key identifier로
계약만 검증한다.

## 5. 오류와 fixture

stable category는 `EFFECT_GATE_DENIED`, `AUTHORITY_CAPABILITY_DENIED`,
`APPROVAL_MISSING`, `APPROVAL_REJECTED`, `APPROVAL_EXPIRED`,
`APPROVAL_AUDIENCE_INVALID`, `APPROVAL_TENANT_INVALID`,
`APPROVAL_BINDING_MISMATCH`, `APPROVAL_SIGNATURE_INVALID`,
`APPROVAL_NONCE_REUSED`, `APPROVAL_NONCE_CONSUME_FAILED`를 사용한다.

fixture는 valid non-destructive local action, destructive gate missing, external
runtime/authority gate missing, authority `DENIED|UNKNOWN` with otherwise valid
approval, reject/expiry/not-before/wrong issuer/audience/tenant/signature,
candidate/action/target/revision/diff/payload/policy change, nonce reuse,
concurrent consume simulation, replayed approval, spy-dispatch zero assertion을
포함한다.

## 6. 검증과 범위 제외

`approval-negative-fixture`는 E2 result에 case verdict, stable category,
nonce outcome, dispatcher count, schema/suite hash와 strict UTC observation만
기록한다. Phase 0 결과는 approval UI, real key management, actual destructive
operation, network publish 또는 external integration을 구현·승인하지 않는다.
