# ForgeOps 문서 지도

**문서 상태:** 초안

**최종 검토일:** 2026-07-20

**대상 독자:** 1인 개발자, 포트폴리오 검토자

**문서 목적:** ForgeOps 기초 문서의 읽기 순서, 책임, 상태, 식별자와 동기화 규칙 안내

**문서 범위:** 기존 제품 핸드오프와 Phase 0~4 기초 문서 8개의 탐색 및 변경 관리

**현재 상태:** 기초 문서 8개는 모두 `초안`; 문서 간 planned linkage는 runtime 검증이나 Phase Exit를 뜻하지 않음

**기준 출처:** [저장소 지시와 ForgeOps profile](../AGENTS.md), [Portable Agent Harness Protocol 2.0](../.github/agents/main_instruction.prompt.md), [ForgeOps 전체 제품 핸드오프](handoff/forgeops-full-handoff.md), [승인된 문서 체계 설계](superpowers/specs/2026-07-14-forgeops-product-documentation-design.md)

**관련 문서:** [2. 권장 읽기 순서](#2-권장-읽기-순서), [3. 문서 책임과 상태](#3-문서-책임과-상태)

## 1. 목적

이 문서는 ForgeOps의 제품 요구사항, 아키텍처, 보안, 검증, 일정, 위험과
추적성 문서를 찾기 위한 지도다. 상세 요구사항이나 실행 일정을 반복하지
않고 각 문서가 무엇을 소유하는지, 어떤 순서로 읽고 함께 갱신해야 하는지를
정의한다.

현재 제품 runtime, sandbox, durable persistence와 외부 publisher는 구현된
것으로 간주하지 않는다. VG-002를 제외한 제품 검증 결과도 통과된 것으로
간주하지 않는다. 문서에 정의된
계획, 통제, gate, `COVERED` linkage와 `public-safe` 조건은 capability,
authority, approval, fresh evidence, Phase Exit 또는 게시 권한을 만들지
않는다.

## 2. 권장 읽기 순서

1. [ForgeOps 전체 제품 핸드오프](handoff/forgeops-full-handoff.md) — 제품 비전과 현재 Harness Foundation 기준선을 먼저 확인한다.
2. [Portable Agent Harness 기준선 인벤토리](agent-harness/BASELINE_INVENTORY.md) — 현재 Protocol·역할·adapter 파일 경계와 VG-001 검토 입력을 확인한다.
3. [Product Task Contract → TaskPacket bridge](contracts/product-task-contract-to-taskpacket.md) — Product Contract schema, field mapping과 non-grant 경계를 확인한다.
4. [W1 Product Task Contract bridge 검토](reviews/w1-contract-bridge-checkpoint.md) — VG-002의 fresh E2 결과와 공개 가능한 체크포인트를 확인한다.
5. [제품 요구사항 문서](product/prd.md) — Phase 0~4의 목표, 범위, 요구사항과 release-level 수용 결과를 읽는다.
6. [시스템 아키텍처](architecture/system-architecture.md) — 제품과 Protocol 경계, 구성요소, 상태·계약·흐름을 확인한다.
7. [위협 모델](security/threat-model.md) — 보호 자산, 위협, 보안 통제와 phase-blocking gate를 확인한다.
8. [검증 및 평가 계획](quality/verification-and-evaluation-plan.md) — evidence 계약, VG, 평가와 Phase Exit 판정 방법을 읽는다.
9. [작업 분해 구조](project/wbs.md) — Phase 0~1의 W1~W10 상세 계획과 Phase 2~4 상위 마일스톤을 확인한다.
10. [위험 등록부](project/risk-register.md) — 일정·제품·기술·보안·평가·포트폴리오 위험과 대응 시점을 검토한다.
11. [요구사항 추적성 매트릭스](project/requirements-traceability-matrix.md) — 요구사항에서 설계·통제·작업·검증까지의 planned linkage와 공백을 확인한다.

이 순서는 이해를 돕기 위한 탐색 순서이며 authority 우선순위나 실행
승인 순서가 아니다.

## 3. 문서 책임과 상태

아래 표는 이번 기초 문서 세트의 8개 문서를 나타낸다. 기존 핸드오프는
제품 비전과 인수인계 요약이며 이 표의 영역별 기준 소유 문서를 대체하지
않는다.

| 문서 | 단일 책임 | 소유 식별자 또는 관계 | 상태 | 최종 검토일 |
| --- | --- | --- | --- | --- |
| [문서 지도](README.md) | 읽기 순서, 문서 책임·상태, 출처와 동기화 규칙 | 새 catalog ID 없음 | 초안 | 2026-07-14 |
| [제품 요구사항 문서](product/prd.md) | 제품 목표, 범위, 요구사항, 성공 기준 | `PRD-FR-###`, `PRD-NFR-###` | 초안 | 2026-07-14 |
| [시스템 아키텍처](architecture/system-architecture.md) | 구성요소, 상태 소유권, 계약과 데이터 흐름 | `ARC-###` | 초안 | 2026-07-14 |
| [위협 모델](security/threat-model.md) | 위협, 보안 통제, 잔여 위험과 보안 gate | `THR-###`, `CTL-###` | 초안 | 2026-07-14 |
| [검증 및 평가 계획](quality/verification-and-evaluation-plan.md) | 검증 방법, evidence 계약, 평가와 품질 gate | `VG-###` | 초안 | 2026-07-14 |
| [작업 분해 구조](project/wbs.md) | 일정, 의존성, 산출물과 완료 정의 | `WBS-###` | 초안 | 2026-07-14 |
| [위험 등록부](project/risk-register.md) | 프로젝트 위험, trigger, 예방·대응과 검토 시점 | `RSK-###` | 초안 | 2026-07-14 |
| [요구사항 추적성 매트릭스](project/requirements-traceability-matrix.md) | owner catalog 간 exact 관계, coverage와 orphan 관리 | PRD 요구사항별 교차 추적 행; 새 catalog ID 없음 | 초안 | 2026-07-14 |

[승인된 문서 체계 설계](superpowers/specs/2026-07-14-forgeops-product-documentation-design.md)와
[실행 계획](superpowers/plans/2026-07-14-forgeops-product-documentation.md)은
문서 세트가 만들어진 절차와 검증 의도를 설명하는 process artifact다.
두 파일은 제품 요구사항, Protocol, runtime 상태, authority 또는 evidence의
기준 소유 문서가 아니다.

[Portable Agent Harness 기준선 인벤토리](agent-harness/BASELINE_INVENTORY.md)는
기초 문서 8개의 owner catalog에 추가되는 아홉 번째 owner 문서가 아니라,
현재 Harness Foundation 파일과 VG-001 검토 입력을 연결하는 WBS-001
산출물이다.

[Product Task Contract → TaskPacket bridge](contracts/product-task-contract-to-taskpacket.md)는
기초 문서 8개의 owner catalog를 대체하거나 추가하는 문서가 아니라,
schema와 non-grant mapping을 고정하는 WBS-002 계약 산출물이다. 해당 bridge는
fresh VG-002 E2를 통과했지만 제품 orchestration runtime이나 Phase 0 Exit를 뜻하지 않는다.

[W1 Product Task Contract bridge 검토](reviews/w1-contract-bridge-checkpoint.md)는
WBS-003의 공개 가능한 내부 체크포인트다. `public-safe`는 외부 게시, upload,
push, PR 또는 메시지 전송 권한을 부여하지 않는다.

## 4. 기준 출처 우선순위

초기 문서 세트를 작성하고 검토할 때 충돌은 다음 순서로 해소한다.

1. 직접 사용자 요청과 적용 범위의 지시 파일
2. 현행 Protocol 2.0 계약과 fresh repository observation 또는 새로 실행한 검증 결과
3. [ForgeOps 전체 제품 핸드오프](handoff/forgeops-full-handoff.md)
4. 이 세트의 파생 문서

저장소 지시는 [AGENTS.md](../AGENTS.md)를 시작점으로 하며, Protocol의
orchestration·accepted-state 계약은 [Main 역할 프롬프트](../.github/agents/main_instruction.prompt.md),
읽기 전용 분석 경계는 [Part 역할 프롬프트](../.github/agents/part_agent.prompt.md),
승인된 실행 경계는 [Work 역할 프롬프트](../.github/agents/work_agent.prompt.md)를
따른다. 파생 문서의 설명이 이 상위 계약과 충돌하면 상위 계약과 fresh
observation을 보존하고 충돌을 추적 공백 또는 위험으로 기록한다.

사용자가 문서 세트를 기준선으로 승인한 뒤에는 제3절의 각 역할 문서가
자기 영역의 규범을 소유하고 핸드오프는 제품 비전과 인수인계 요약으로
사용한다. 기준선 이후에도 직접 사용자 요청, 적용 지시, Protocol 2.0
불변식과 fresh repository evidence는 계속 상위이며, 기준선이라는 상태가
실행이나 게시 authority를 만들지는 않는다.

## 5. 상태와 식별자 규칙

### 문서와 요구사항 상태

- 문서 상태는 `초안`, `검토됨`, `기준선`만 사용한다. 상태 변경에는 해당 검토와 동기화 결과가 필요하다.
- 요구사항 성숙도는 `IMPLEMENTED`, `SPECIFIED`, `PLANNED`만 사용한다. `IMPLEMENTED`는 현재 저장소와 최소 fresh E1 file 또는 diff evidence로 확인될 때만 쓴다.
- 제품 검증 결과는 `PASSED`, `FAILED`, `NOT_RUN`만 사용한다. `PASSED`는 요구 floor를 충족하는 fresh evidence가 있을 때만 가능하다.
- WBS 실행 상태는 `WBS_NOT_STARTED`, `WBS_IN_PROGRESS`, `WBS_BLOCKED`, `WBS_DONE`만 사용한다.
- 위험 상태는 `OPEN`, `MITIGATING`, `MONITORING`, `CLOSED`만 사용한다.
- 추적 상태는 `COVERED`, `PARTIAL`, `GAP`만 사용한다. `COVERED`는 planned link의 완전성이지 구현·검증 완료가 아니다.

제품 workflow state, WBS 상태와 Protocol canonical accepted state는 서로
다른 영역이다. Part와 Work의 transition은 제안이며 `MainDecision`만
accepted state, revision과 authoritative event sequence를 확정한다. 제품
`CANCELLED`를 versioned Protocol 변경 없이 canonical 상태로 강제 변환하지
않는다.

### 식별자

- 모든 catalog ID는 대문자 prefix와 3자리 숫자를 사용하고 owner 문서 안에서 유일해야 한다.
- `PRD-FR`, `PRD-NFR`, `ARC`, `THR`, `CTL`, `VG`, `WBS`, `RSK`의 의미와 번호는 각 owner 문서가 관리한다.
- RTM과 다른 문서는 ID를 case-sensitive exact literal로 참조한다. trimming, case folding, wildcard, prefix·suffix 추론이나 유사 ID 대체를 허용하지 않는다.
- 추적에 사용된 ID의 의미를 바꾸거나 다른 항목에 재사용하지 않는다. 항목을 제거할 때는 폐기 상태와 변경 근거를 남겨 기존 링크의 의미를 보존한다.
- ID, 상태, score, 계획된 command 또는 문서 링크는 capability, authority, approval, 실제 실행이나 fresh evidence의 대체물이 아니다.

## 6. 변경 및 동기화 규칙

1. 요구사항, 아키텍처, 위협·통제, 검증 gate, WBS 또는 위험의 규범적 변경은 owner 문서, RTM과 영향을 받는 모든 문서를 같은 변경에서 갱신한다.
2. owner 문서가 바뀌어 핸드오프 요약과 달라지면 같은 변경에서 핸드오프를 동기화한다. 즉시 동기화할 수 없으면 이유와 책임, 목표 주차를 가진 `RSK-###` 항목을 만들거나 갱신한다.
3. 새 ID, 상태 또는 link를 추가한 변경은 전체 catalog count, orphan, 상대 경로, Markdown, UTF-8과 whitespace 검사를 다시 실행한다. 검사를 실행하지 못하면 성공으로 간주하지 않고 `NOT_RUN` 또는 추적 공백과 이유를 기록한다.
4. current implementation, Phase Exit, 위험 closure와 검증 성공은 fresh evidence로만 갱신한다. 계획, 달력 경과, 정성 점수나 사용자 침묵으로 성공 또는 승인을 추론하지 않는다.
5. 어떤 문서도 exact RESOURCE·COMMAND·NETWORK authority, destructive·external-effect hard gate, approval binding, fail-closed, fresh evidence, protected resource, secret·tenant 또는 publication gate를 약화할 수 없다.
6. 인간 승인은 capability나 TaskPacket authority를 새로 만들지 않는다. 허용되는 실행은 현재 capability, exact authority, approval, revision, preflight와 evidence 조건의 교집합으로 제한한다.
7. `public-safe` 검증이나 포트폴리오 준비 완료는 외부 게시, upload, push, PR, message 또는 공개 링크 생성 권한이 아니다. 외부 publication은 exact artifact, destination과 audience에 대한 새 인간 권한이 있어야 한다.
8. 변경은 사용자 소유 작업과 protected resource를 보존한다. 비용, 새 credential, destructive action, 외부 효과, scope expansion과 게시에는 각각 적용되는 새 인간 권한을 별도로 확인한다.

동기화할 수 없는 충돌, 누락된 source, 실패한 validator 또는 미확인
runtime 상태는 숨기지 않는다. 영향을 받는 문서는 `초안` 또는 적절한
`PARTIAL`·`GAP`·`NOT_RUN` 상태로 남기고, 근거가 생기기 전에는 기준선,
검증 완료, Phase 통과 또는 게시 가능으로 올리지 않는다.
