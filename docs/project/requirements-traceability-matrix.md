# ForgeOps 요구사항 추적성 매트릭스

**문서 상태:** 초안

**최종 검토일:** 2026-07-14

**대상 독자:** 1인 개발자, 포트폴리오 검토자

**문서 목적:** ForgeOps의 37개 제품 요구사항을 아키텍처, 위협·통제, 위험, 작업, 검증 gate와 exact ID로 추적

**문서 범위:** PRD 37개, ARC 14개, THR 12개, CTL 20개, RSK 14개, WBS 35개, VG 24개의 planned linkage와 초기 검증 상태

**현재 상태:** 37개 요구사항의 planned linkage는 `COVERED`; PRD-FR-001은 fresh VG-002 E2로 `PASSED`, 나머지는 `NOT_RUN`

**기준 출처:** [제품 요구사항](../product/prd.md), [시스템 아키텍처](../architecture/system-architecture.md), [위협 모델](../security/threat-model.md), [검증 및 평가 계획](../quality/verification-and-evaluation-plan.md), [WBS](wbs.md), [위험 등록부](risk-register.md), [ForgeOps 제품 기초 문서 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md)

**관련 문서:** [7. 관련 문서](#7-관련-문서)

## 1. 목적과 추적 규칙

이 문서는 PRD의 각 기능·비기능 요구사항을 한 행으로 유지하고, 그 요구사항을 실현·검증·통제하는 owner catalog의 exact ID를 연결한다. PRD가 요구 의미와 Phase/Priority/Maturity를 소유하고, architecture·threat model·risk register·WBS·quality plan이 각각 책임 경계, 위협·통제, 잔여 위험, 구현 작업, 검증 gate를 소유한다. RTM은 이 의미를 재정의하지 않는다.

- ID는 owner 문서의 case-sensitive exact literal로만 연결한다. trimming, case folding, prefix·suffix 추론 또는 유사 ID 대체를 허용하지 않는다.
- 한 요구사항의 `Trace status`는 행에 계획된 ARC, THR, CTL, RSK, WBS, VG가 모두 해당 owner catalog에 존재할 때만 `COVERED`다.
- `COVERED`는 **planned linkage가 완전하다**는 뜻일 뿐 구현, runtime 검증, `PASSED`, Phase Exit 또는 외부 게시 권한을 뜻하지 않는다.
- `Required floor`는 향후 성공 판정에 필요한 최소 evidence tier다. 계획된 ID나 floor 자체는 current evidence 또는 authority가 아니다.
- owner catalog에 없는 참조, 빈 필수 관계 또는 새 orphan이 생기면 `PARTIAL` 또는 `GAP`으로 낮추고 관련 Phase Exit를 차단한다.

## 2. 상태와 evidence 표현

요구사항의 검증 Result는 `PASSED`, `FAILED`, `NOT_RUN`만 사용한다. PRD-FR-001의 Product Task Contract bridge는 `IMPLEMENTED`이고 trusted VG-002 실행 결과를 가진다. 나머지 요구사항은 `SPECIFIED` 또는 `PLANNED`이며 아직 `NOT_RUN`이다.

| Maturity | 초기 표현 | 다음 갱신 조건 |
| --- | --- | --- |
| `IMPLEMENTED` | 해당 요구 범위 산출물이 존재하며 Result는 fresh mapped VG 결과를 따른다. | 계약 또는 fixture 변경 시 trusted VG 재실행과 evidence 갱신 |
| `SPECIFIED` | 계약은 정의됐지만 Result=`NOT_RUN`, Actual tier·Evidence ref·Observation metadata=`없음` | mapped WBS 구현과 trusted VG 실행 후 fresh evidence로 판정 |
| `PLANNED` | 향후 산출물이므로 Result=`NOT_RUN`, Actual tier·Evidence ref·Observation metadata=`없음` | mapped WBS 산출물 구현 후 trusted VG 실행과 RTM evidence 연결 |

`NOT_RUN`은 evidence reference가 없고 actual tier, `observed_revision`, `observed_at`도 없는 상태다. 향후 `PASSED`는 요구 floor 이상의 fresh evidence reference가 정확히 해석될 때만 기록한다. `FAILED` evidence는 보존하며 `NOT_RUN`으로 바꾸지 않는다. file/diff evidence는 현재 base revision과 일치하는 `observed_revision`을, command/test/render/runtime/approval evidence는 trusted `validationAt` 기준 fresh strict UTC `observed_at`을 사용한다.

Raw shell text, 문서의 예시 명령, 계획된 `verification_profile_id` 또는 `command_id`는 evidence나 authority로 기록하지 않는다. 실제 실행 관찰과 canonical evidence reference만 향후 Result 갱신 근거가 된다.

## 3. 요구사항 추적표

| Requirement | Phase/Priority | Maturity | ARC | THR | CTL | RSK | WBS | VG | Required floor | Result | Actual tier | Evidence ref | Observation metadata | Trace status | Gap/action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PRD-FR-001 | Phase 0 / 필수 | IMPLEMENTED | ARC-002, ARC-010 | THR-001, THR-003 | CTL-001, CTL-005 | RSK-002 | WBS-002, WBS-003 | VG-002 | E2 | PASSED | E2 | artifacts/verification/vg-002-contract-bridge-result.json | observed_at=2026-07-20T05:53:16Z | COVERED | VG-002 fixture와 WBS-003 review 완료 |
| PRD-FR-002 | Phase 0 / 필수 | IMPLEMENTED | ARC-009 | THR-009, THR-010 | CTL-008, CTL-015 | RSK-003 | WBS-004 | VG-003 | E2 | PASSED | E2 | artifacts/verification/vg-003-state-transition-result.json; artifacts/verification/vg-003-event-order-result.json; artifacts/verification/vg-003-replay-contract-result.json | observed_at=2026-07-23T03:57:12Z; 2026-07-23T03:57:13Z; 2026-07-23T03:57:14Z | COVERED | state transition, event order, replay fixture E2 PASSED |
| PRD-FR-003 | Phase 0 / 필수 | SPECIFIED | ARC-012 | THR-001, THR-010 | CTL-001, CTL-015 | RSK-002 | WBS-006 | VG-004 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | 계약 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-004 | Phase 0 / 필수 | SPECIFIED | ARC-011 | THR-008, THR-010 | CTL-014, CTL-015, CTL-020 | RSK-003, RSK-012 | WBS-007, WBS-008 | VG-004 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | 계약 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-005 | Phase 0 / 필수 | PLANNED | ARC-008 | THR-011 | CTL-016 | RSK-007 | WBS-009 | VG-001 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-006 | Phase 0 / 필수 | SPECIFIED | ARC-003, ARC-013 | THR-006 | CTL-006, CTL-007 | RSK-005, RSK-009 | WBS-005 | VG-007 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | VG-007 policy fixture E2 PASSED; approval UX는 Phase 0 범위에서 구현하지 않아 요구사항 전체 Result는 NOT_RUN 유지 |
| PRD-FR-007 | Phase 0 / 필수 | PLANNED | ARC-007, ARC-011 | THR-004, THR-005, THR-007 | CTL-009, CTL-010, CTL-011, CTL-012, CTL-013 | RSK-004, RSK-006 | WBS-010, WBS-011, WBS-012 | VG-008, VG-009 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-008 | Phase 1 / 필수 | PLANNED | ARC-005, ARC-007 | THR-002, THR-011 | CTL-002, CTL-016 | RSK-007 | WBS-013, WBS-014 | VG-010 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-009 | Phase 1 / 필수 | PLANNED | ARC-005 | THR-001 | CTL-001 | RSK-005 | WBS-015 | VG-011 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-010 | Phase 1 / 필수 | PLANNED | ARC-003, ARC-004, ARC-009 | THR-010 | CTL-005, CTL-015 | RSK-003 | WBS-016, WBS-017, WBS-018, WBS-019 | VG-012 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-011 | Phase 1 / 필수 | PLANNED | ARC-006, ARC-007 | THR-002, THR-005, THR-006 | CTL-002, CTL-006, CTL-010 | RSK-004, RSK-005 | WBS-020 | VG-013, VG-015 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-012 | Phase 1 / 필수 | PLANNED | ARC-008 | THR-011 | CTL-016 | RSK-007 | WBS-021, WBS-022 | VG-013 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-013 | Phase 1 / 필수 | PLANNED | ARC-003, ARC-004, ARC-011 | THR-010, THR-012 | CTL-011, CTL-017, CTL-020 | RSK-011 | WBS-023, WBS-024, WBS-025, WBS-026, WBS-027, WBS-028 | VG-014, VG-015 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-014 | Phase 2 / 필수 | PLANNED | ARC-008 | THR-010, THR-012 | CTL-015, CTL-017 | RSK-007 | WBS-033 | VG-016 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-015 | Phase 2 / 필수 | PLANNED | ARC-008 | THR-012 | CTL-017 | RSK-001 | WBS-033 | VG-016 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-016 | Phase 2 / 필수 | PLANNED | ARC-008 | THR-011 | CTL-016 | RSK-008 | WBS-033 | VG-017 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-017 | Phase 2 / 필수 | PLANNED | ARC-008, ARC-011 | THR-010, THR-011 | CTL-015, CTL-016 | RSK-008 | WBS-033 | VG-018 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-018 | Phase 3 / 필수 | PLANNED | ARC-013 | THR-006, THR-009 | CTL-006, CTL-007, CTL-019 | RSK-009 | WBS-034 | VG-019 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-019 | Phase 3 / 필수 | PLANNED | ARC-003, ARC-013 | THR-006, THR-008 | CTL-007, CTL-014, CTL-020 | RSK-009 | WBS-034 | VG-020 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-020 | Phase 3 / 권장 | PLANNED | ARC-006 | THR-001, THR-003, THR-004, THR-007 | CTL-001, CTL-003, CTL-004, CTL-013, CTL-018 | RSK-005, RSK-006 | WBS-034 | VG-020 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-021 | Phase 3 / 권장 | PLANNED | ARC-003, ARC-012, ARC-014 | THR-009, THR-012 | CTL-011, CTL-019 | RSK-009, RSK-010 | WBS-034 | VG-020 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-022 | Phase 4 / 필수 | PLANNED | ARC-007, ARC-011, ARC-014 | THR-005, THR-008 | CTL-009, CTL-010, CTL-014 | RSK-004, RSK-010 | WBS-035 | VG-021, VG-022 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-023 | Phase 4 / 권장 | PLANNED | ARC-006, ARC-014 | THR-001, THR-003, THR-011 | CTL-001, CTL-003, CTL-016, CTL-018 | RSK-010 | WBS-035 | VG-023 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-024 | Phase 4 / 권장 | PLANNED | ARC-005, ARC-008, ARC-014 | THR-001, THR-011 | CTL-001, CTL-016 | RSK-010 | WBS-035 | VG-023 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-FR-025 | Phase 4 / 권장 | PLANNED | ARC-008, ARC-011, ARC-013 | THR-006, THR-009, THR-010 | CTL-007, CTL-008, CTL-015, CTL-019 | RSK-003, RSK-008, RSK-009 | WBS-035 | VG-017, VG-018, VG-022 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-001 | 전 단계 / 필수 | SPECIFIED | ARC-008, ARC-011 | THR-010, THR-011 | CTL-015, CTL-016 | RSK-007 | WBS-001, WBS-021, WBS-027 | VG-001, VG-023 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | 계약 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-002 | 전 단계 / 필수 | SPECIFIED | ARC-006, ARC-007, ARC-010 | THR-002, THR-003, THR-004, THR-006 | CTL-002, CTL-003, CTL-004, CTL-005, CTL-006, CTL-007, CTL-012 | RSK-005 | WBS-002, WBS-005, WBS-010, WBS-026 | VG-002, VG-005, VG-006, VG-007, VG-008 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | VG-002·VG-005·VG-006·VG-007 E2 범위 PASSED; required E3와 VG-008 sandbox gate 미실행 |
| PRD-NFR-003 | Phase 0~4 / 필수 | PLANNED | ARC-007 | THR-005 | CTL-009, CTL-010, CTL-011 | RSK-004 | WBS-010, WBS-013, WBS-024, WBS-028 | VG-008, VG-010, VG-014 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-004 | 전 단계 / 필수 | SPECIFIED | ARC-006, ARC-011 | THR-007, THR-008 | CTL-013, CTL-014 | RSK-006 | WBS-011, WBS-028, WBS-031 | VG-009, VG-024 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | 계약 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-005 | Phase 1~4 / 필수 | PLANNED | ARC-003, ARC-011, ARC-013 | THR-009, THR-012 | CTL-008, CTL-011, CTL-017, CTL-019 | RSK-003, RSK-009 | WBS-024, WBS-030, WBS-034 | VG-014, VG-015, VG-019 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | VG-003 replay와 VG-007 atomic nonce E2 범위 PASSED; mapped VG-014·VG-015·VG-019 E3 미실행 |
| PRD-NFR-006 | Phase 0~4 / 필수 | SPECIFIED | ARC-011, ARC-012 | THR-008, THR-010 | CTL-014, CTL-015, CTL-020 | RSK-012 | WBS-003, WBS-007, WBS-008, WBS-025, WBS-031 | VG-004, VG-015 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | WBS-003 bridge review 완료; VG-004·VG-015 미실행 |
| PRD-NFR-007 | Phase 4 / 필수 | PLANNED | ARC-014 | THR-012 | CTL-011 | RSK-010 | WBS-035 | VG-022 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | mapped WBS 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-008 | 전 단계 / 필수 | SPECIFIED | ARC-003, ARC-008 | THR-012 | CTL-011, CTL-017 | RSK-001, RSK-011, RSK-014 | WBS-023, WBS-032 | VG-014 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | 계약 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-009 | 전 단계 / 권장 | SPECIFIED | ARC-001, ARC-002, ARC-006, ARC-010, ARC-014 | THR-001, THR-003 | CTL-001, CTL-003, CTL-018 | RSK-010 | WBS-001, WBS-002, WBS-035 | VG-001, VG-002, VG-023 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | VG-002 bridge 범위 PASSED; VG-001·VG-023 미실행 |
| PRD-NFR-010 | Phase 2~4 / 필수 | SPECIFIED | ARC-008 | THR-011 | CTL-016 | RSK-008 | WBS-032, WBS-033 | VG-017, VG-018 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | 계약 구현 후 mapped VG 실행·RTM 갱신 |
| PRD-NFR-011 | Phase 1~4 / 권장 | PLANNED | ARC-003, ARC-012 | THR-006, THR-008 | CTL-007, CTL-014, CTL-020 | RSK-013 | WBS-003, WBS-025, WBS-029, WBS-031, WBS-032 | VG-015, VG-024 | E2 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | WBS-003 public-safe review 완료; VG-015·VG-024 미실행 |
| PRD-NFR-012 | Phase 3~4 / 필수 | PLANNED | ARC-007, ARC-013, ARC-014 | THR-005, THR-008, THR-009 | CTL-009, CTL-010, CTL-014, CTL-019, CTL-020 | RSK-004, RSK-009 | WBS-035 | VG-020, VG-021, VG-022 | E3 | NOT_RUN | 없음 | 없음 | 없음 | COVERED | VG-007 tenant·nonce·zero-effect E2 범위 PASSED; mapped integration·tenant VG-020·VG-021·VG-022 E3 미실행 |

## 4. Coverage 요약

| Catalog | Owner | 정의 수 | RTM 참조 수 | 상태 |
| --- | --- | ---: | ---: | --- |
| PRD | `docs/product/prd.md` | 37 | 37 | COVERED — validator PASS |
| ARC | `docs/architecture/system-architecture.md` | 14 | 14 | COVERED — validator PASS |
| THR | `docs/security/threat-model.md` | 12 | 12 | COVERED — validator PASS |
| CTL | `docs/security/threat-model.md` | 20 | 20 | COVERED — validator PASS |
| VG | `docs/quality/verification-and-evaluation-plan.md` | 24 | 24 | COVERED — validator PASS |
| WBS | `docs/project/wbs.md` | 35 | 35 | COVERED — validator PASS |
| RSK | `docs/project/risk-register.md` | 14 | 14 | COVERED — validator PASS |

37개 요구사항 행은 모두 `COVERED`로 계획돼 있다. 이 상태는 ID linkage의 완전성만 나타낸다. Fresh success coverage는 VG-002가 연결된 PRD-FR-001의 1/37이며 나머지 36개는 `NOT_RUN`이다.

## 5. Orphan 검사 결과

Task 7 exact cross-document validator가 `RTM_VALIDATE=PASS`로 통과했다. 확인된 definition count는 PRD 37, ARC 14, THR 12, CTL 20, VG 24, WBS 35, RSK 14이고, 37개 requirement row에서 모든 definition ID가 적어도 한 번 exact 참조된다.

**Orphan count: 0.** 이 수치는 planned cross-document linkage의 orphan이 없다는 뜻이다. Product Task Contract bridge의 VG-002만 fresh E2 `PASSED`이며 나머지 36개 Result는 계속 `NOT_RUN`이다. 이 결과로 제품 runtime이나 Phase 0 Exit를 주장하지 않는다.

## 6. 갱신 규칙

1. PRD의 Phase, Priority, Maturity 또는 requirement ID가 바뀌면 같은 변경에서 RTM 행을 갱신하고 37행 cardinality를 다시 검증한다.
2. ARC, THR, CTL, RSK, WBS 또는 VG가 추가·변경·폐기되면 모든 영향 행과 Coverage/Orphan 요약을 함께 갱신한다. owner 문서에 없는 ID를 임시 placeholder로 만들지 않는다.
3. 계획 관계가 빠졌거나 owner에서 삭제된 참조가 있으면 `COVERED`를 유지하지 않고 `PARTIAL` 또는 `GAP`과 구체적인 owner/action을 기록한다.
4. Result 갱신은 trusted 실행에서 생성된 exact evidence reference가 요구 floor와 freshness를 충족할 때만 한다. `NOT_RUN`에는 Actual tier, Evidence ref, Observation metadata를 기록하지 않는다.
5. `FAILED`, stale, floor 미달, `PARTIAL`, `GAP`과 orphan은 평균 점수나 계획 상태로 상쇄하지 않으며 관련 Phase Exit를 차단한다.
6. Raw shell text, 예시 명령, 계획 profile/command ID는 evidence나 authority로 승격하지 않는다. 외부 게시·PR·push·메시지·배포는 RTM 상태와 별개의 명시적 권한이 필요하다.
7. 모든 갱신 뒤 Task 7 exact validator와 링크·UTF-8·whitespace 검사를 fresh 실행하고 관찰 결과만 보고한다.

## 7. 관련 문서

- [ForgeOps 제품 요구사항 문서](../product/prd.md) — 37개 requirement와 Phase/Priority/Maturity owner
- [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md) — ARC-001~ARC-014 owner
- [ForgeOps 위협 모델](../security/threat-model.md) — THR-001~THR-012와 CTL-001~CTL-020 owner
- [ForgeOps 검증 및 평가 계획](../quality/verification-and-evaluation-plan.md) — VG-001~VG-024, evidence floor와 Result 의미 owner
- [ForgeOps 작업 분해 구조](wbs.md) — WBS-001~WBS-035 owner
- [ForgeOps 위험 등록부](risk-register.md) — RSK-001~RSK-014 owner
- [ForgeOps 제품 기초 문서 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md) — exact RTM mapping과 cross-document validator
- [저장소 기본 지시와 ForgeOps profile](../../AGENTS.md) — authority, protected resource와 evidence 운영 경계
