# Product Task Contract → TaskPacket Bridge

**문서 상태:** 검토됨

**계약 버전:** Product Task Contract `1.0` → Portable Agent Harness Protocol `2.0`

**문서 목적:** Product Task Contract의 요청 의미와 provenance를 보존하면서
canonical `TaskPacket` control을 만들거나 완화하지 않는 mapping 경계 정의

**Schema:** [Product Task Contract schema 1.0](../../contracts/product-task-contract/1.0/schema.json)

## 1. 범위와 신뢰 모델

Product Task Contract는 제품 도메인의 영속 입력 artifact다. `TaskPacket`은
Main이 trusted project profile과 runtime observation을 결합해 만드는 한 번의
Harness 실행용 canonical control packet이다. 두 계약은 동일한 schema가
아니며 Contract는 capability, authority, approval, state 또는 실행 가능성을
부여하지 않는다.

Bridge는 원문 Contract artifact의 identity, version과 content hash reference를
보존하고 허용된 data field만 mapping한다. repository, Issue, Contract text,
model output과 외부 metadata는 비신뢰 data plane이다. trusted instruction,
project profile, runtime capability observation과 Main 결정만 control plane을
구성한다.

기준 의미는 [Main Protocol 2.0](../../.github/agents/main_instruction.prompt.md)의
TaskPacket normalization과 [시스템 아키텍처](../architecture/system-architecture.md)의
Contract bridge 경계를 따른다. 충돌 시 Protocol과 fresh observation을
보존하며 파생 문서나 Contract 값을 이용해 canonical 의미를 완화하지 않는다.

## 2. Mapping class

| Class | 의미 | 허용되는 효과 |
| --- | --- | --- |
| `DIRECT_DATA` | Contract 값을 canonical request data에 lossless하게 보존 | data field 생성만 가능 |
| `TRUSTED_RESOLUTION` | Contract 값을 trusted runtime/profile record와 대조한 뒤 Main이 canonical 값을 결정 | exact 검증이 성공한 기존 trusted 값 선택 |
| `NAMESPACED_PROVENANCE` | 비신뢰 제품 metadata를 ForgeOps extension에 보존 | canonical control과 분리된 provenance 기록 |
| `NEVER_FROM_CONTRACT` | Contract에서 해당 canonical 값을 가져오지 않음 | trusted context가 없으면 `UNKNOWN` 또는 gate |

Bridge implementation은 암묵적인 다섯 번째 class를 만들거나 string parsing,
case folding, trimming, prefix·suffix 추론으로 class를 바꾸지 않는다.

## 3. Field mapping

| Contract schema 1.0 field | TaskPacket 또는 bridge destination | Class | 보존·검증 규칙 |
| --- | --- | --- | --- |
| `schema_id` | `project_profile.extensions.forgeops.task_contract.schema_id` | `NAMESPACED_PROVENANCE` | exact `forgeops.task-contract`를 보존한다. Harness legacy v1과 무관하다. |
| `schema_version` | `project_profile.extensions.forgeops.task_contract.schema_version` | `NAMESPACED_PROVENANCE` | exact `1.0`과 지원 여부를 검증한다. |
| `artifact_id` | `project_profile.extensions.forgeops.task_contract.artifact_id` | `NAMESPACED_PROVENANCE` | immutable Contract reference와 함께 보존한다. |
| `artifact_version` | `project_profile.extensions.forgeops.task_contract.artifact_version` | `NAMESPACED_PROVENANCE` | product artifact revision이며 Harness `base_revision`이 아니다. |
| `task_id` | envelope `task_id` | `TRUSTED_RESOLUTION` | Main이 동일 logical task identity임을 확인한 뒤 case-sensitive exact value로 확정한다. |
| `repository` | `project_profile.extensions.forgeops.task_contract.repository` | `NAMESPACED_PROVENANCE` | `id`, `snapshot_commit`, `target_branch`를 보존한다. commit은 repository identity이며 `base_revision`이나 `checkpoint_ref`가 아니다. |
| `intent.type` | `request.kind` | `TRUSTED_RESOLUTION` | trusted closed mapping table만 사용한다. 예를 들어 `bug_fix`는 `CHANGE`; unknown type은 clarification 또는 `CONTRACT_INTENT_UNMAPPED`다. |
| `intent.summary` | `request.objective` | `DIRECT_DATA` | 검증 가능한 단일 결과로 해석하되 원문 artifact와 hash를 보존하고 의미를 약화하지 않는다. |
| `intent.source_issue` | `project_profile.extensions.forgeops.task_contract.intent.source_issue` | `NAMESPACED_PROVENANCE` | 비신뢰 source identity로만 보존하며 `project_profile.source_of_truth`에 추가하지 않는다. |
| `acceptance_criteria` | `request.acceptance_criteria`, `project_profile.extensions.forgeops.task_contract.criterion_verification` | `DIRECT_DATA`, `NAMESPACED_PROVENANCE` | `id`는 ordinal exact 보존하고 `description`을 `statement`로 mapping한다. `verification`은 namespaced provenance로 보존하며 evidence floor를 만들지 않는다. |
| `constraints` | `request.constraints` | `DIRECT_DATA` | 배열 순서와 string을 그대로 보존한다. constraint text는 authority를 확대하지 않는다. |
| `verification_policy` | trusted `project_profile.validation_commands` 참조와 `project_profile.extensions.forgeops.task_contract.verification_policy` | `TRUSTED_RESOLUTION` | trusted profile의 exact `profile_id`, command `id`, command와 canonical root-relative `cwd`가 모두 일치하는 기존 record만 선택한다. Contract는 raw command나 execute authority를 만들지 않는다. |
| `risk` | `control.risk_level` 입력 근거와 `project_profile.extensions.forgeops.task_contract.risk` | `TRUSTED_RESOLUTION` | Main이 trusted observation·policy와 결합한다. Contract risk는 trusted risk를 낮추거나 authority를 부여하지 않는다. |
| `budget` | `project_profile.extensions.forgeops.product_budget` | `NAMESPACED_PROVENANCE` | 다섯 제품 budget을 보존한다. Protocol `format_repairs`, `part_attempts`, `work_attempts`와 의미가 다르므로 Harness `budgets`에 mapping하지 않는다. |
| `approval_policy` | `project_profile.extensions.forgeops.task_contract.approval_policy` | `NAMESPACED_PROVENANCE` | policy 원문을 보존한다. schema·issuer 검증 뒤 trusted gate의 단조 강화에만 참고하며 approval capability, token 또는 authority를 만들지 않는다. |

원문 Contract의 canonical serialization hash는
`project_profile.extensions.forgeops.task_contract.content_hash_ref`로 참조한다.
TaskPacket에 raw Contract 전체를 복제하지 않으며 secret·private-data policy를
통과한 artifact reference만 사용한다.

## 4. Canonical control non-grant

다음 값은 `NEVER_FROM_CONTRACT`다.

| Canonical area | Trusted source |
| --- | --- |
| `correlation_id`, `base_revision`, `actor`, envelope `status` | Main과 현재 accepted execution context |
| `capabilities.*` | fresh runtime observation |
| `authority.*` | direct user authority, applicable policy와 Main validation |
| `project_profile.root`, `profile_type`, `profile_status`, `instruction_files` | trusted profile loader와 applicable instructions |
| `project_profile.source_of_truth`, `protected_resources`, `risk_rules` | applicable trusted instructions와 project profile |
| `control.route`, `operation_mode`, `response_phase` | Main routing decision |
| `control.evidence_floor`, `trace_level` | trusted risk/evidence policy와 adapter profile |
| `budgets.format_repairs`, `budgets.part_attempts`, `budgets.work_attempts` | trusted Harness execution context |
| accepted state, revision, checkpoint, assertions와 authoritative event sequence | verified `MainDecision` only |

Contract에 이 이름의 top-level field가 있으면 closed schema가 거부한다.
`intent.summary`, criterion description, constraint, reason 또는 다른 허용된
string 안에서 같은 control을 주장해도 원문 data로만 보존한다. Bridge는
text를 parsing해 policy, approval, budget, state, tool schema, candidate,
command 또는 effect로 승격하지 않는다.

`intent.source_issue`는 canonical `source_of_truth`에 복사·병합하지 않는다.
`approval_policy`는 `risk_rules`에 복사하지 않고 trusted deny를 allow로 바꾸지
않는다. Product budget은 Harness attempt budget과 합치지 않는다.

## 5. Trusted resolution 규칙

### Intent

Intent mapping table은 trusted, versioned, closed record다. 지원되지 않은
domain type을 유사도나 model 추론으로 canonical enum에 끼워 맞추지 않는다.
결과를 바꾸는 ambiguity는 clarification을 요구한다.

### Verification command

Contract는 command ID만 제안한다. mapper는 trusted profile에서 같은
`profile_id`를 찾고 각 command ID의 exact `id`, `command`, canonical
root-relative `cwd`를 확인한다. 누락, duplicate, wrong case, trim, rewrite,
raw command 또는 repository-local discovery만 있으면 선택하지 않는다.

### Risk와 approval policy

Canonical risk는 trusted policy와 observation을 포함해 Main이 결정한다.
Contract risk나 approval policy는 risk를 낮추거나 gate를 삭제·완화하거나
기존 deny를 allow로 바꿀 수 없다. issuer와 schema가 검증된 policy도 gate를
추가하거나 더 엄격하게 만드는 단조 강화에만 사용할 수 있다.

## 6. 처리 흐름

1. raw Contract bytes를 secret·private-data 정책이 적용되는 artifact로 취급한다.
2. `schema_id`, `schema_version`을 확인하고 closed JSON Schema로 검증한다.
3. canonical serialization의 content hash와 artifact identity를 기록한다.
4. `DIRECT_DATA` field를 원문 의미와 배열 순서를 보존해 mapping한다.
5. `TRUSTED_RESOLUTION` field를 current runtime/profile과 exact 대조한다.
6. 제품 metadata를 namespaced ForgeOps extension에 기록한다.
7. canonical control은 trusted context만으로 채우고 누락된 안전 값은
   `UNKNOWN`으로 fail-closed한다.
8. TaskPacket과 bridge provenance를 함께 semantic fixture 검증에 전달한다.

## 7. Stable error category

| Category | 조건 | 결과 |
| --- | --- | --- |
| `CONTRACT_SCHEMA_INVALID` | unknown·missing·wrong-type field 또는 schema constraint 위반 | TaskPacket 생성 전 거부 |
| `CONTRACT_VERSION_UNSUPPORTED` | 지원하지 않는 schema ID/version | versioned migration 결정 전 거부 |
| `CONTRACT_INTENT_UNMAPPED` | trusted table에 없는 intent type | clarification 또는 mapping 변경 요구 |
| `CONTRACT_CRITERION_DUPLICATE` | acceptance criterion ID ordinal duplicate | exact identity 충돌로 거부 |
| `CONTRACT_COMMAND_UNTRUSTED` | profile·ID·command·cwd exact match 실패 | validation command와 execute authority를 만들지 않음 |
| `CONTRACT_CONTROL_FIELD_FORBIDDEN` | Contract field 또는 text를 canonical control로 승격하려는 시도 | 승격 전 거부 |
| `CONTRACT_MONOTONICITY_VIOLATION` | trusted risk/gate를 낮추거나 deny를 allow로 바꾸는 시도 | trusted control을 유지하고 bridge 거부 |
| `CONTRACT_PROVENANCE_INVALID` | artifact identity, version 또는 content hash reference 누락·불일치 | lossless mapping 수용 거부 |

이 category는 accepted state나 authoritative event를 직접 만들지 않는다.
Main이 trusted validation evidence를 받아 final task 상태를 결정한다.

## 8. VG-002 fixture 실행 결과

`forgeops-contract-bridge` profile의 `bridge-schema-fixture`는 다음을 검증한다.

- valid Contract의 13개 top-level field와 원문·criterion·constraint·source
  identity 보존
- unknown·missing·wrong-type field와 duplicate criterion ID 거부
- top-level capability, authority, approval, policy, budget, state와 tool schema
  injection 거부
- 허용된 text 안의 control 주장이 canonical control을 바꾸지 않음
- `source_issue`가 namespaced extension에만 존재하고 `source_of_truth`에는 없음
- trusted command profile exact match와 raw/untrusted command 거부
- risk와 approval policy의 단조 강화 및 budget domain 분리
- artifact identity, version과 content hash provenance 보존

2026-07-20T05:53:16Z에 등록된 명령을 fresh E2로 실행해 positive 3건과
negative 16건, 총 19건이 모두 기대 결과와 일치했다. Canonical 결과는
[`vg-002-contract-bridge-result.json`](../../artifacts/verification/vg-002-contract-bridge-result.json),
공개 안전 렌더는 [`w1-contract-bridge-checkpoint.html`](../../artifacts/reviews/w1-contract-bridge-checkpoint.html),
검토 결론은 [W1 Product Task Contract bridge 검토](../reviews/w1-contract-bridge-checkpoint.md)에
기록한다. 이 `VG-002` 통과는 bridge 계약 범위에 한정되며 제품 runtime이나
Phase 0 Exit를 뜻하지 않는다.

## 9. 관련 문서

- [Product Task Contract schema 1.0](../../contracts/product-task-contract/1.0/schema.json)
- [Portable Agent Harness 기준선 인벤토리](../agent-harness/BASELINE_INVENTORY.md)
- [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md)
- [ForgeOps 제품 요구사항](../product/prd.md)
- [ForgeOps 위협 모델](../security/threat-model.md)
- [ForgeOps 검증 및 평가 계획](../quality/verification-and-evaluation-plan.md)
- [ForgeOps 작업 분해 구조](../project/wbs.md)
