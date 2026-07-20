# Portable Agent Harness 기준선 인벤토리

**문서 상태:** 검토됨

**관찰 기준일:** 2026-07-19

**대상 독자:** ForgeOps 개발자, Harness Foundation 및 Phase 0 검토자

**문서 목적:** 현재 저장소에 존재하는 Portable Agent Harness Protocol 2.0,
Main·Part·Work 역할, repository adapter/profile 및 적용 가이드의 경계를
파일 근거로 연결하고 `VG-001` 검토 입력을 식별

## 1. 범위와 상태 의미

이 인벤토리에서 `PRESENT`는 대상 파일을 현재 working tree에서 직접
확인했다는 뜻이다. `IMPLEMENTED`는 prompt와 repository adapter/profile에
표현된 Harness Foundation 계약에만 적용한다. `SPECIFIED`와 `PLANNED`는
제품 계약 또는 후속 구현 대상을 뜻한다. 파일 존재와 이 상태들은 제품
runtime 실행, Phase Exit, 검증 통과 또는 외부 게시 권한을 의미하지 않는다.

현재 기준 출처의 우선순위는 직접 사용자 요청과 적용 지시, 현행 Protocol
2.0 및 fresh repository observation, 제품 핸드오프, 파생 제품 문서 순이다.
하위 역할·adapter·제품 문서는 상위 Protocol의 canonical 의미와 안전
불변식을 약화할 수 없다.

## 2. Harness Foundation 파일 인벤토리

| 파일 | 상태 | 현재 책임 | 확인 근거 | 금지되는 확대 해석 |
| --- | --- | --- | --- | --- |
| [Main 역할 프롬프트](../../.github/agents/main_instruction.prompt.md) | PRESENT | Protocol 2.0 정규화, route, accepted state, revision, authoritative event sequence와 최종 결정 | `TaskPacket normalization`, `Routing`, `Accepted state`, `Human gate and security` | 제품 orchestration service 또는 durable state가 구현됐다는 주장 |
| [Part 역할 프롬프트](../../.github/agents/part_agent.prompt.md) | PRESENT | 읽기 전용 discovery, 해석·분해와 `CandidatePacket` 제안 | `Boundary`, `Discovery order`, candidate contract | mutation 또는 accepted state 변경 권한 |
| [Work 역할 프롬프트](../../.github/agents/work_agent.prompt.md) | PRESENT | 승인된 exact candidate 재검증, 실행·검증과 `WorkResult` 제안 | `Boundary`, `Preflight`, `Execution` | 사용자 승인, 최종 상태 또는 authoritative event 소유권 |
| [ForgeOps repository adapter/profile](../../AGENTS.md) | PRESENT | project root, source of truth, protected resource, risk 및 validation discovery 설정 | `ForgeOps project profile`, `Repository operating rules` | `UNKNOWN` capability 승격 또는 외부 효과 허용 |
| [Copilot adapter](../../.github/copilot-instructions.md) | PRESENT | Copilot 역할 mapping, loading precedence와 v1 전달 경계 | `Role mapping`, `Loading and precedence`, `Adapter rules` | Main 이전의 v1 normalization 또는 unavailable delegation 모의 실행 |
| [Portable Harness 적용 가이드](PORTING_GUIDE.md) | PRESENT | 필요한 파일, adapter 예시, capability·authority, evidence 및 conformance 도입 안내 | `복사할 파일`, `Capability와 authority`, `적합성 시나리오`, `운영 규칙` | 제품 runtime, VG 통과 또는 특정 host capability 보장 |

## 3. 역할과 adapter 경계

| 주체 | 허용된 책임 | 소유하지 않는 것 |
| --- | --- | --- |
| Main | 요청 정규화, route, proposal·evidence 검증, accepted state·revision·authoritative sequence와 최종 사용자 결과 | 관찰되지 않은 capability, 암묵 권한과 fabricated evidence |
| Part | 허용된 범위의 읽기 전용 discovery와 `CandidatePacket` 제안 | 파일·외부 시스템 변경, accepted state와 authoritative event |
| Work | 승인된 exact candidate의 preflight·변경·검증과 `WorkResult` 제안 | 사용자 승인, 최종 상태, revision increment와 authoritative event |
| Repository adapter/profile | host 진입점과 ForgeOps 제약을 canonical Protocol 입력으로 제공 | Protocol 불변식 약화, 권한 생성과 제품 runtime 구현 |

Part와 Work의 state·assertion·event는 제안이다. Main만 검증된 evidence를
근거로 accepted state, revision과 authoritative event sequence를 확정한다.
사용자 승인도 capability나 `TaskPacket` authority를 새로 만들지 않는다.
실제 행동은 관찰된 capability, exact authority, 필요한 승인, current
revision과 preflight의 교집합으로 제한된다.

## 4. Harness Foundation과 제품 runtime 경계

| 계층 | 현재 성숙도 | 현재 확인 가능한 것 | 아직 주장할 수 없는 것 |
| --- | --- | --- | --- |
| Portable Harness Foundation | IMPLEMENTED | Protocol 2.0, Main·Part·Work prompt 계약과 repository adapter/profile | 실행 service, immutable snapshot, sandbox, durable persistence와 rollback |
| Product Task Contract bridge | IMPLEMENTED | versioned schema, lossless/non-grant mapper 검증기와 fresh VG-002 E2 결과 | 제품 orchestration 또는 실행 service |
| 나머지 product contract layer | SPECIFIED | PRD와 아키텍처에 정의된 state, API, event 및 manifest 요구 | 해당 executable schema와 fixture 통과 |
| ForgeOps Product runtime | PLANNED | 후속 WBS에 배치된 Control Plane, orchestration, context, gateway, workspace, verification 및 publisher 목표 | 현재 API·queue·database·sandbox 또는 SCM write가 작동한다는 주장 |

세부 경계와 성숙도 근거는 [시스템 아키텍처](../architecture/system-architecture.md)의
`현재와 목표 경계` 및 `ARC-001`~`ARC-014`에서 확인한다. 현재 workspace를
변경할 수 있다는 host capability는 제품의 immutable snapshot, ephemeral
workspace, containment, durable recovery 또는 rollback 보장이 아니다.

## 5. VG-001 검토 입력

[검증 및 평가 계획의 VG-001](../quality/verification-and-evaluation-plan.md)은
`forgeops-foundation-conformance` profile에서 `protocol-conformance`와
`sample-fixture` command를 요구하는 E2 검증이다. WBS-001은 다음 검토
입력만 식별하며 `VG-001`을 실행하거나 통과 처리하지 않는다.

| 검토 입력 | 확인 관점 |
| --- | --- |
| Main·Part·Work 역할 프롬프트 | canonical packet, actor, state·evidence 소유권과 fail-closed 의미 |
| root `AGENTS.md`와 Copilot adapter | adapter 교체 전후 Protocol 의미와 ForgeOps profile 제약 보존 |
| Porting Guide의 적합성 시나리오 | positive·negative fixture 범위와 stable rejection 기대값 |
| [제품 요구사항](../product/prd.md), [시스템 아키텍처](../architecture/system-architecture.md), [WBS](../project/wbs.md) | `PRD-NFR-001`·`PRD-NFR-009`, `ARC-001`·`ARC-002`·`ARC-010`과 `WBS-001`·`WBS-002`의 추적 경계 |
| [요구사항 추적성 매트릭스](../project/requirements-traceability-matrix.md) | 관련 요구사항의 현재 검증 결과와 evidence reference |

현재 `VG-001` 결과는 요구사항 추적성 매트릭스에 `NOT_RUN`으로 기록돼
있다. sample fixture와 trusted validation command의 fresh E2 결과가 생기기
전에는 `VG-001` 또는 관련 criterion을 `PASSED`로 바꾸지 않는다. 별도
`VG-002` 결과는 Product Task Contract bridge 범위에만 적용된다.

## 6. 알려진 제한과 후속 연결

- 현재 저장소는 제품 Phase 0의 W1 계약 bridge까지 완료된 경계이며
  WBS-001 인벤토리 자체는 Product Task Contract schema 구현이 아니다.
- `WBS-002`는 versioned Product Task Contract schema, lossless TaskPacket
  bridge와 non-grant fixture를 구현했고 fresh `VG-002` E2를 통과했다.
- `WBS-003`은 bridge schema, 경계 설명과 공개 가능한 검토 요약을 확인했다.
- `public-safe` 또는 검토 완료 상태는 외부 게시, push, PR, upload나 메시지
  전송 권한이 아니다.

## 7. 관련 문서

- [ForgeOps 문서 지도](../README.md)
- [ForgeOps 제품 요구사항](../product/prd.md)
- [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md)
- [ForgeOps 검증 및 평가 계획](../quality/verification-and-evaluation-plan.md)
- [ForgeOps 작업 분해 구조](../project/wbs.md)
- [ForgeOps 요구사항 추적성 매트릭스](../project/requirements-traceability-matrix.md)
- [Portable Agent Harness v2 적용 가이드](PORTING_GUIDE.md)
