# ForgeOps 작업 분해 구조

**문서 상태:** 초안

**최종 검토일:** 2026-07-14

**대상 독자:** 1인 개발자, 포트폴리오 검토자

**기준 출처:** [ForgeOps 제품 요구사항 문서](../product/prd.md), [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md), [ForgeOps 위협 모델](../security/threat-model.md), [ForgeOps 검증 및 평가 계획](../quality/verification-and-evaluation-plan.md), [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md), [ForgeOps 제품 기초 문서 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md)

**계획 범위:** W1~W10의 Phase 0~1 상세 작업과 Phase 2~4 상위 마일스톤

## 1. 계획 목적과 기준

이 문서는 ForgeOps의 Phase 0 Executable Contracts와 Phase 1 Local Vertical Slice를 1인 개발자가 상대 일정 10주 안에서 실행·검토할 수 있도록 작업 패키지, 의존성, 용량, 완료 정의와 검증 연결로 분해한다. 제품이 무엇을 왜 제공하는지는 PRD가 소유하고, 이 WBS는 구현 순서와 산출물 및 완료 조건을 소유한다. 요구사항, Protocol 2.0 불변식, 보안 통제와 품질 게이트의 의미를 재정의하지 않는다.

현재 기준선은 Harness Foundation 완료, 제품 Phase 0 시작 전이다. 아래 Status와 evidence type은 모두 계획값이다. 예상 evidence type은 향후 관찰 형식을 지정할 뿐 현재 fresh evidence, PASSED 결과 또는 Phase Exit 달성 주장이 아니다. 실제 fresh evidence reference와 관찰 revision 또는 시각은 RTM이 소유한다.

## 2. 일정과 용량 가정

- 계획 주체는 1인 개발자이며 병렬 실행을 전제로 하지 않는다.
- 기본 가용량은 주당 5 person-day다. 이 중 최대 4 person-day만 계획 작업에 배정하고 1 person-day는 검토, 실패 복구, 문서화와 재계획 buffer로 보존한다.
- W1~W10의 계획 작업은 총 40.0 person-day, buffer는 총 10.0 person-day다.
- person-day는 상대 추정치이며 달력 날짜, 확정 납기 또는 Phase 2~4 일정 약속이 아니다.

| Week | Phase focus | 계획 person-day | Buffer person-day | 총 capacity |
| --- | --- | ---: | ---: | ---: |
| W1 | Phase 0 | 4.0 | 1.0 | 5.0 |
| W2 | Phase 0 | 4.0 | 1.0 | 5.0 |
| W3 | Phase 0 | 4.0 | 1.0 | 5.0 |
| W4 | Phase 0 Exit | 4.0 | 1.0 | 5.0 |
| W5 | Phase 1 | 4.0 | 1.0 | 5.0 |
| W6 | Phase 1 | 4.0 | 1.0 | 5.0 |
| W7 | Phase 1 | 4.0 | 1.0 | 5.0 |
| W8 | Phase 1 | 4.0 | 1.0 | 5.0 |
| W9 | Phase 1 safety gate | 4.0 | 1.0 | 5.0 |
| W10 | Phase 1 Exit | 4.0 | 1.0 | 5.0 |
| 합계 | Phase 0~1 | 40.0 | 10.0 | 50.0 |

## 3. 상태와 변경 규칙

WBS Status는 다음 closed enum만 사용한다. 제품 workflow state, 요구사항 Maturity, 검증 결과와 Protocol 2.0 canonical accepted state로 직렬화하거나 변환하지 않는다.

| Status | 의미 |
| --- | --- |
| WBS_NOT_STARTED | 선행 조건이나 실행이 아직 시작되지 않음 |
| WBS_IN_PROGRESS | 승인된 범위에서 작업과 검증이 진행 중 |
| WBS_BLOCKED | 선행 작업, capability, authority, 보안 gate 또는 외부 결정 때문에 진행 불가 |
| WBS_DONE | Deliverable이 존재하고 Definition of Done과 연결된 VG 조건을 fresh evidence로 충족 |

최초 계획의 모든 항목은 WBS_NOT_STARTED다. 허용 전이는 WBS_NOT_STARTED에서 WBS_IN_PROGRESS 또는 WBS_BLOCKED로, WBS_IN_PROGRESS에서 WBS_DONE 또는 WBS_BLOCKED로, WBS_BLOCKED에서 차단 근거가 해소된 뒤 WBS_IN_PROGRESS로 제한한다. PASSED, FAILED, NOT_RUN과 evidence tier는 검증 계획의 값이며 WBS Status 열에 사용하지 않는다.

범위, person-day, 선행 작업, PRD 또는 VG 연결을 바꾸면 변경 이유와 영향 주차를 기록하고 capacity를 다시 계산한다. 작업을 완료로 표시할 때는 Deliverable 이름, 적용한 VG, 실제 결과와 fresh evidence가 RTM에서 추적되어야 한다.

## 4. W1~W10 작업 패키지

Expected evidence type은 Protocol 2.0의 closed evidence type 중 향후 생성될 형식을 적은 계획값이다.

| ID | Phase | Week | Status | person-day | Predecessor | PRD IDs | Deliverable | Definition of Done | VG IDs | Expected evidence type |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| WBS-001 | Phase 0 | W1 | WBS_NOT_STARTED | 1.0 | 없음 | PRD-NFR-001, PRD-NFR-009 | Harness baseline inventory and evidence links | Harness baseline inventory and evidence links가 Protocol 2.0, Main/Part/Work, adapters와 porting guide의 현재 경계를 링크하고 제품 runtime과 구분되며 VG-001 검토 입력을 식별한다. | VG-001 | file |
| WBS-002 | Phase 0 | W1 | WBS_NOT_STARTED | 2.0 | WBS-001 | PRD-FR-001, PRD-NFR-002, PRD-NFR-009 | Product Contract schema and TaskPacket bridge | Product Contract schema and TaskPacket bridge가 원문·criterion·constraint·source identity를 보존하고 Contract와 비신뢰 source의 authority·approval·policy·budget·state·tool schema 주장이 canonical control을 만들지 않는 positive/negative case로 VG-002 조건을 충족한다. | VG-002 | file, test |
| WBS-003 | Phase 0 | W1 | WBS_NOT_STARTED | 1.0 | WBS-002 | PRD-FR-001, PRD-NFR-006, PRD-NFR-011 | bridge review and portfolio checkpoint | bridge review and portfolio checkpoint가 bridge schema, 경계 설명과 공개 가능한 검토 요약을 포함하고 발견된 VG-002 위반이 해소되어 있다. | VG-002 | file, render |
| WBS-004 | Phase 0 | W2 | WBS_NOT_STARTED | 2.0 | WBS-002 | PRD-FR-002, PRD-NFR-001, PRD-NFR-006 | state transition validator and mapping fixture | state transition validator and mapping fixture가 유효 전이만 허용하고 stale revision과 out-of-order sequence를 거부하며 CANCELLED를 강제 변환하지 않는다. replay closed mode·새 identity를 강제하고 과거 authority·approval·nonce·credential 복사 및 `AUDIT_REPLAY`·`COUNTERFACTUAL` external effect를 계약에서 거부해 VG-003 조건을 충족한다. | VG-003 | file, test |
| WBS-005 | Phase 0 | W2 | WBS_NOT_STARTED | 2.0 | WBS-004 | PRD-FR-006, PRD-NFR-002, PRD-NFR-005, PRD-NFR-012 | authority/approval policy matrix and negative fixture | authority/approval policy matrix and negative fixture가 RESOURCE, COMMAND, NETWORK, destructive와 external effect의 exact gate 및 deny·expiry·nonce reuse를 다룬다. protected resource·credential·private data는 exact target 인간 승인 전 첫 byte read와 model context·log·evidence 유입이 0임을 확인해 VG-005, VG-006, VG-007 조건을 충족한다. | VG-005, VG-006, VG-007 | file, test |
| WBS-006 | Phase 0 | W3 | WBS_NOT_STARTED | 1.5 | WBS-002 | PRD-FR-003, PRD-NFR-006 | versioned OpenAPI schema | versioned OpenAPI schema가 version과 closed request/response를 정의하고 valid/invalid example을 결정론적으로 판정한다. 비신뢰 field가 policy·authority·budget·state·tool schema로 승격되는 example을 stable error로 거부해 VG-004의 API와 data/control 경계 조건을 충족한다. | VG-004 | file, test |
| WBS-007 | Phase 0 | W3 | WBS_NOT_STARTED | 1.0 | WBS-004 | PRD-FR-004, PRD-NFR-006 | durable event wrapper schema | durable event wrapper schema가 task/run identity, actor, ordering, revision과 provenance를 보존하고 VG-003 및 VG-004의 event 조건을 충족한다. | VG-003, VG-004 | file, test |
| WBS-008 | Phase 0 | W3 | WBS_NOT_STARTED | 1.5 | WBS-006, WBS-007 | PRD-FR-004, PRD-NFR-004, PRD-NFR-006 | run manifest schema and reference rules | run manifest schema and reference rules가 identity, ordering, provenance, artifact/evidence reference를 closed schema로 검증하고 dangling·duplicate·wrong-mode reference를 거부해 VG-004와 VG-023 조건을 충족한다. | VG-004, VG-023 | file, test |
| WBS-009 | Phase 0 | W4 | WBS_NOT_STARTED | 1.0 | WBS-006, WBS-008 | PRD-FR-005, PRD-NFR-001, PRD-NFR-009 | sample repository and benchmark fixture | sample repository and benchmark fixture가 고정 source/hash와 positive/negative expected result를 가지며 반복 conformance에서 VG-001 조건을 판정할 수 있다. | VG-001 | file, test |
| WBS-010 | Phase 0 | W4 | WBS_NOT_STARTED | 1.5 | WBS-005, WBS-009 | PRD-FR-007, PRD-NFR-002, PRD-NFR-003, PRD-NFR-012 | sandbox containment PoC | sandbox containment PoC가 signed image, rootless/read-only 경계, exact NETWORK authority를 포함한 egress, quota와 teardown negative case를 실행하고 금지 surface·authority 우회·잔존 resource가 0이어야 하는 VG-008 조건을 충족한다. | VG-008 | file, test, runtime |
| WBS-011 | Phase 0 | W4 | WBS_NOT_STARTED | 1.0 | WBS-005, WBS-009 | PRD-FR-007, PRD-NFR-004, PRD-NFR-006, PRD-NFR-012 | redaction and artifact fixture | redaction and artifact fixture가 packet, event, prompt, artifact, trace, telemetry와 응답 surface를 검사하고 raw secret 0 및 tenant/reference 규칙으로 VG-009 조건을 충족한다. | VG-009 | file, test |
| WBS-012 | Phase 0 Exit | W4 | WBS_NOT_STARTED | 0.5 | WBS-009, WBS-010, WBS-011 | PRD-FR-001, PRD-FR-002, PRD-FR-003, PRD-FR-004, PRD-FR-005, PRD-FR-006, PRD-FR-007, PRD-NFR-001, PRD-NFR-002, PRD-NFR-003, PRD-NFR-004, PRD-NFR-005, PRD-NFR-006, PRD-NFR-009, PRD-NFR-012 | Phase 0 Exit report | Phase 0 Exit report가 VG-001~VG-009와 VG-023의 결과, floor, 실패와 잔여 위험을 집계하고 모든 phase-blocking 조건이 fresh 통과하지 않으면 Exit를 선언하지 않는다. | VG-001, VG-002, VG-003, VG-004, VG-005, VG-006, VG-007, VG-008, VG-009, VG-023 | file, test, runtime |
| WBS-013 | Phase 1 | W5 | WBS_NOT_STARTED | 1.5 | WBS-012 | PRD-FR-008, PRD-FR-011, PRD-NFR-003, PRD-NFR-005 | immutable snapshot provider | immutable snapshot provider가 source identity와 content manifest를 고정하고 dirty state를 보존하며 원본 write 없이 ephemeral workspace를 제공해 VG-008과 VG-010 조건을 충족한다. | VG-008, VG-010 | file, test, runtime |
| WBS-014 | Phase 1 | W5 | WBS_NOT_STARTED | 1.5 | WBS-013 | PRD-FR-008, PRD-FR-012, PRD-NFR-001 | baseline runner and baseline artifact | baseline runner and baseline artifact가 trusted profile을 같은 snapshot에서 실행하고 기존 실패와 변경 회귀를 구분할 수 있는 결과를 보존해 VG-010과 VG-013 조건을 충족한다. | VG-010, VG-013 | test, runtime |
| WBS-015 | Phase 1 | W5 | WBS_NOT_STARTED | 1.0 | WBS-013 | PRD-FR-008, PRD-FR-009, PRD-NFR-004 | code retrieval and Context Pack | code retrieval and Context Pack이 path, snapshot, hash와 선택 이유를 포함하고 비신뢰 instruction을 control plane으로 승격하지 않아 VG-010과 VG-011 조건을 충족한다. | VG-010, VG-011 | file, test |
| WBS-016 | Phase 1 | W6 | WBS_NOT_STARTED | 1.0 | WBS-014, WBS-015 | PRD-FR-001, PRD-FR-010, PRD-NFR-009 | Main normalization and routing | Main normalization and routing이 Product Contract를 canonical TaskPacket으로 비약 없이 정규화하고 capability·authority에 따라 역할을 라우팅해 VG-002와 VG-012 조건을 충족한다. | VG-002, VG-012 | file, test |
| WBS-017 | Phase 1 | W6 | WBS_NOT_STARTED | 1.0 | WBS-016 | PRD-FR-009, PRD-FR-010, PRD-NFR-002 | Part context and plan proposal | Part context and plan proposal가 approved candidate 전 `EXPLORE`에서 비보호 exact-scope read-only discovery만 수행하고 source-attributed context를 사용한다. protected resource·credential·private data는 exact target 인간 승인 전 읽지 않으며 candidate를 exact identity와 근거로 제안해 VG-005, VG-011, VG-012 조건을 충족한다. | VG-005, VG-011, VG-012 | file, test |
| WBS-018 | Phase 1 | W6 | WBS_NOT_STARTED | 1.0 | WBS-017 | PRD-FR-010, PRD-FR-011, PRD-FR-012, PRD-NFR-002, PRD-NFR-003 | Work preflight, execute, verify | Work preflight, execute, verify가 approved candidate, current revision, exact authority와 workspace containment를 재검증하고 trusted check evidence만 제출해 VG-005, VG-006, VG-012, VG-013 조건을 충족한다. | VG-005, VG-006, VG-012, VG-013 | file, test, runtime |
| WBS-019 | Phase 1 | W6 | WBS_NOT_STARTED | 1.0 | WBS-018 | PRD-FR-010, PRD-NFR-001, PRD-NFR-006 | Main evidence validation and accepted decision | Main evidence validation and accepted decision이 evidence type, reference, freshness와 floor를 검증하고 MainDecision만 final state, revision과 canonical sequence를 확정해 VG-003, VG-012, VG-023 조건을 충족한다. | VG-003, VG-012, VG-023 | file, test |
| WBS-020 | Phase 1 | W7 | WBS_NOT_STARTED | 1.5 | WBS-019 | PRD-FR-011, PRD-NFR-003, PRD-NFR-005 | patch and diff pipeline | patch and diff pipeline이 ephemeral workspace에만 changed resource를 만들고 원본·host 외부·remote write 없이 bounded diff를 생성해 VG-013과 VG-015 조건을 충족한다. | VG-013, VG-015 | diff, test, runtime |
| WBS-021 | Phase 1 | W7 | WBS_NOT_STARTED | 1.5 | WBS-014, WBS-020 | PRD-FR-012, PRD-NFR-001 | trusted test/lint/typecheck profiles | trusted test/lint/typecheck profiles가 agent workspace 밖에서 exact command identity로 등록되고 적용 가능한 task, regression, lint와 typecheck를 fresh 실행해 VG-013 조건을 충족한다. | VG-013 | test |
| WBS-022 | Phase 1 | W7 | WBS_NOT_STARTED | 1.0 | WBS-021 | PRD-FR-012, PRD-NFR-001, PRD-NFR-010 | regression and test anti-tamper guard | regression and test anti-tamper guard가 test 삭제, skip, xfail, assertion 완화, coverage 제외와 profile 변경을 탐지하고 deterministic failure를 보존해 VG-013 조건을 충족한다. | VG-013 | test |
| WBS-023 | Phase 1 | W8 | WBS_NOT_STARTED | 1.0 | WBS-019 | PRD-FR-013, PRD-NFR-008 | budget enforcement | budget enforcement가 시간, token, tool, command, repair와 비용 사용량을 추적하고 한도 초과 뒤 추가 dispatch를 막아 VG-014 조건을 충족한다. | VG-014 | test, runtime |
| WBS-024 | Phase 1 | W8 | WBS_NOT_STARTED | 1.5 | WBS-019, WBS-023 | PRD-FR-013, PRD-NFR-003, PRD-NFR-005 | cancellation and verified cleanup | cancellation and verified cleanup이 cancel과 terminal path에서 process tree, mount, lease, transient secret과 workspace 잔존 0을 관찰해 VG-008과 VG-014 조건을 충족한다. | VG-008, VG-014 | test, runtime |
| WBS-025 | Phase 1 | W8 | WBS_NOT_STARTED | 1.5 | WBS-019, WBS-024 | PRD-FR-013, PRD-NFR-006, PRD-NFR-011 | basic trace viewer | basic trace viewer가 terminal reason, actor, ordering, evidence, artifact, budget, cleanup과 허용된 다음 행동을 해석 가능한 흐름으로 표시해 VG-015 조건을 충족한다. | VG-015 | render, runtime |
| WBS-026 | Phase 1 | W9 | WBS_NOT_STARTED | 1.5 | WBS-010, WBS-011, WBS-024 | PRD-FR-007, PRD-FR-009, PRD-FR-011, PRD-NFR-002, PRD-NFR-003, PRD-NFR-004, PRD-NFR-005, PRD-NFR-012 | security negative suite | security negative suite가 Phase 1의 authority, approval, containment, egress, injection, secret, cleanup, evidence와 external-write negative case를 실행하고 VG-005~VG-009, VG-011, VG-013~VG-015, VG-023의 zero-event 조건을 충족한다. | VG-005, VG-006, VG-007, VG-008, VG-009, VG-011, VG-013, VG-014, VG-015, VG-023 | test, runtime |
| WBS-027 | Phase 1 | W9 | WBS_NOT_STARTED | 1.5 | WBS-021, WBS-022, WBS-026 | PRD-FR-008, PRD-FR-009, PRD-FR-010, PRD-FR-011, PRD-FR-012, PRD-FR-013, PRD-NFR-001, PRD-NFR-003, PRD-NFR-004, PRD-NFR-005, PRD-NFR-006, PRD-NFR-008, PRD-NFR-009, PRD-NFR-011 | required E2 criterion evidence run | required E2 criterion evidence run이 모든 필수 criterion을 최소 E2와 각 VG의 더 높은 floor에서 fresh 실행하고 실패·미실행을 숨기지 않으며 VG-008~VG-015와 VG-023 결과를 완전하게 남긴다. | VG-008, VG-009, VG-010, VG-011, VG-012, VG-013, VG-014, VG-015, VG-023 | test, runtime |
| WBS-028 | Phase 1 | W9 | WBS_NOT_STARTED | 1.0 | WBS-024, WBS-025, WBS-027 | PRD-FR-008, PRD-FR-009, PRD-FR-010, PRD-FR-011, PRD-FR-012, PRD-FR-013, PRD-NFR-001, PRD-NFR-002, PRD-NFR-003, PRD-NFR-004, PRD-NFR-005, PRD-NFR-006, PRD-NFR-008, PRD-NFR-011 | Phase 1 safety gate | Phase 1 safety gate가 immutable source, E2 이상 필수 evidence, unauthorized execution 0, cleanup failure 0, external write 0과 관련 VG-008~VG-015 및 VG-023 결과를 확인하고 하나라도 미충족이면 W10 통합을 차단한다. | VG-008, VG-009, VG-010, VG-011, VG-012, VG-013, VG-014, VG-015, VG-023 | file, test, runtime |
| WBS-029 | Phase 1 Exit | W10 | WBS_NOT_STARTED | 1.5 | WBS-028 | PRD-FR-008, PRD-FR-009, PRD-FR-010, PRD-FR-011, PRD-FR-012, PRD-FR-013, PRD-NFR-001, PRD-NFR-003, PRD-NFR-005, PRD-NFR-006, PRD-NFR-008, PRD-NFR-011 | local vertical slice demonstration | local vertical slice demonstration이 한 고정 snapshot에서 Main→Part→Work→Main, patch, trusted verification, cancellation/cleanup과 trace를 외부 write 없이 재현해 VG-010~VG-015 조건을 충족한다. | VG-010, VG-011, VG-012, VG-013, VG-014, VG-015 | test, runtime, render |
| WBS-030 | Phase 1 Exit | W10 | WBS_NOT_STARTED | 1.0 | WBS-029 | PRD-FR-008, PRD-FR-009, PRD-FR-010, PRD-FR-011, PRD-FR-012, PRD-FR-013, PRD-NFR-001, PRD-NFR-003, PRD-NFR-005, PRD-NFR-006 | regression run and Phase 1 Exit report | regression run and Phase 1 Exit report가 VG-008~VG-015와 VG-023의 fresh 결과 및 잔여 위험을 집계하고 VG-024는 WBS-031 완료 전 선행 미충족으로 명시하여 조기 Exit를 선언하지 않는다. | VG-008, VG-009, VG-010, VG-011, VG-012, VG-013, VG-014, VG-015, VG-023 | file, test, runtime |
| WBS-031 | Phase 1 Exit | W10 | WBS_NOT_STARTED | 1.0 | WBS-030 | PRD-NFR-004, PRD-NFR-006, PRD-NFR-011 | public-safe portfolio package | public-safe portfolio package가 공개 fixture, 재현 절차, redacted trace/diff, metrics, manifest hash와 license provenance를 포함하고 금지 정보 0으로 VG-024 조건을 충족하며 외부 게시 권한은 만들지 않는다. | VG-024 | file, diff, render, test |
| WBS-032 | Phase 1 Exit | W10 | WBS_NOT_STARTED | 0.5 | WBS-030, WBS-031 | PRD-NFR-006, PRD-NFR-011 | retrospective and next-phase decision record | retrospective and next-phase decision record가 WBS-030과 WBS-031 결과, VG-024 포트폴리오 gate, carry-over와 잔여 위험을 근거로 Phase 1 Exit 또는 재계획을 명시하고 Phase 2는 상위 마일스톤으로만 연결한다. | VG-024 | file |

## 5. Phase 2~4 상위 마일스톤

아래 항목은 전체 제품 비전을 보존하기 위한 상위 마일스톤이다. 확정 주차, 상세 sprint, person-day 또는 구현 순서를 추가하지 않는다.

| ID | Phase | Week | Status | person-day | Predecessor | PRD IDs | Exit | VG IDs | Expected evidence type |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WBS-033 | Phase 2 | N/A (상위 마일스톤) | WBS_NOT_STARTED | N/A (상위 마일스톤) | WBS-032 | PRD-FR-014, PRD-FR-015, PRD-FR-016, PRD-FR-017, PRD-FR-025, PRD-NFR-001, PRD-NFR-005, PRD-NFR-008, PRD-NFR-010 | bounded repair and benchmark go/no-go | VG-016, VG-017, VG-018 | test, runtime |
| WBS-034 | Phase 3 | N/A (상위 마일스톤) | WBS_NOT_STARTED | N/A (상위 마일스톤) | WBS-033 | PRD-FR-018, PRD-FR-019, PRD-FR-020, PRD-FR-021, PRD-NFR-002, PRD-NFR-004, PRD-NFR-005, PRD-NFR-006, PRD-NFR-012 | controlled GitHub integration, RBAC, audit, dedup gates | VG-019, VG-020 | test, runtime, approval |
| WBS-035 | Phase 4 | N/A (상위 마일스톤) | WBS_NOT_STARTED | N/A (상위 마일스톤) | WBS-034 | PRD-FR-022, PRD-FR-023, PRD-FR-024, PRD-FR-025, PRD-NFR-003, PRD-NFR-004, PRD-NFR-006, PRD-NFR-007, PRD-NFR-009, PRD-NFR-010, PRD-NFR-011, PRD-NFR-012 | rolling SLO, zero security violations, plugin maturity | VG-021, VG-022, VG-023 | test, runtime |

## 6. Critical path

### 브리프 지정 관리상 critical sequence (DAG path 아님)

WBS-001 → WBS-002 → WBS-004 → WBS-005 → WBS-010 → WBS-012 → WBS-013 → WBS-014 → WBS-016 → WBS-017 → WBS-018 → WBS-019 → WBS-020 → WBS-021 → WBS-022 → WBS-026 → WBS-027 → WBS-028 → WBS-029 → WBS-030

위 문자열은 브리프가 지정한 관리상 sequence를 정확히 보존한 것이며 predecessor DAG path가 아니다. WBS-022→WBS-026은 WBS-026 행의 direct predecessor edge가 아니므로 새 의존성을 뜻하지 않는다. exact Predecessor 표에 따라 WBS-022와 WBS-026의 결과는 WBS-027에서 합류한다.

### DAG-valid critical path

WBS-001~WBS-032의 exact Predecessor를 directed edge로, 각 작업의 person-day를 node weight로 사용해 위상 순서에서 누적 weight가 가장 큰 경로를 계산한다. 동률이면 전체 WBS ID sequence를 ordinal 오름차순으로 비교해 첫 경로를 선택한다.

WBS-001 → WBS-002 → WBS-004 → WBS-007 → WBS-008 → WBS-009 → WBS-010 → WBS-012 → WBS-013 → WBS-014 → WBS-016 → WBS-017 → WBS-018 → WBS-019 → WBS-020 → WBS-021 → WBS-022 → WBS-027 → WBS-028 → WBS-029 → WBS-030 → WBS-031 → WBS-032

이 DAG-valid critical path의 총 weight는 **28.0 person-day**다. 모든 화살표의 source는 target 행의 direct Predecessor이며 cycle과 미래 주차를 향한 역방향 의존성이 없다. 이 경로 밖 작업도 phase-blocking VG 또는 보안 불변식을 담당하면 생략하거나 병렬 완료로 추정할 수 없다. 특히 WBS-005, WBS-011, WBS-024, WBS-025와 WBS-026은 critical path 밖에서도 각 합류점과 Phase gate의 필수 선행 조건이다.

### Phase 2~4 후속 상위 마일스톤

WBS-032 → WBS-033 → WBS-034 → WBS-035는 Phase 1 이후의 direct predecessor chain이다. WBS-033~WBS-035의 person-day는 N/A (상위 마일스톤)이므로 Phase 0~1 longest weighted path 계산에는 포함하지 않는다.

## 7. 주간 운영과 재계획 trigger

주간 운영은 다음 순서를 사용한다.

1. 주초에 선행 작업의 WBS Status, 전주 carry-over, 보안 gate와 이번 주 계획 부하를 확인한다.
2. WBS_IN_PROGRESS 전환 전 Deliverable, 적용 PRD/VG, required floor와 검증 가능성을 확인한다.
3. 주중에는 계획 4 person-day를 넘지 않고 1 person-day buffer를 검토, 실패 진단, 문서화와 bounded rework에 우선 사용한다.
4. 주말에는 Deliverable, DoD, VG 결과와 실제 fresh evidence 연결을 검토하고 WBS Status 또는 차단 이유를 갱신한다.

다음 중 하나라도 발생하면 이후 작업을 자동으로 당기지 않고 WBS를 재계획한다.

- 한 주의 계획 부하가 4 person-day를 초과한다.
- Phase gate가 목표 주차에 충족되지 않는다.
- zero-event security invariant 또는 phase-blocking 보안 통제가 실패한다.
- carry-over가 2주 연속 발생한다.

재계획 시 실패 evidence와 잔여 위험을 보존하고, 영향받은 선행 관계·주차·person-day·PRD/VG mapping을 함께 갱신한다. 실패한 gate 뒤의 미래 작업은 자동으로 앞당기지 않으며 buffer를 신규 scope의 암묵적 용량으로 사용하지 않는다.

## 8. 포트폴리오 checkpoint

| Week | 관련 WBS | Checkpoint | 수용 기준 |
| --- | --- | --- | --- |
| W1 | WBS-003 | Contract bridge review | Contract→TaskPacket mapping, non-grant 경계와 검토 결과를 제3자가 따라갈 수 있다. |
| W4 | WBS-012 | Phase 0 evidence review | schema, authority/approval, sandbox와 redaction fixture의 gate 결과 및 미충족 조건이 명시된다. |
| W6 | WBS-019 | Orchestration ownership review | Main/Part/Work 경계와 MainDecision의 state/evidence 소유권을 한 흐름으로 설명한다. |
| W9 | WBS-028 | Safety and evidence scorecard | 필수 evidence floor와 unauthorized execution, cleanup, external write zero 조건을 재현 가능한 결과로 제시한다. |
| W10 | WBS-029, WBS-030, WBS-031 | Local vertical slice package | 공개 fixture, redacted trace/diff, regression 결과, manifest hash와 잔여 위험이 VG-024 기준으로 완전하다. |

Checkpoint 산출물은 공개 가능성을 검증하는 내부 package다. 외부 게시, 업로드, push, PR 생성 또는 메시지 전송은 별도 명시적 권한 없이는 수행하지 않는다.

## 9. 관련 문서

- [ForgeOps 제품 요구사항 문서](../product/prd.md) — Phase 0~4 요구사항과 release-level Exit gate
- [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md) — 구성요소, 상태 소유권, snapshot·sandbox·verification 경계
- [ForgeOps 위협 모델](../security/threat-model.md) — THR/CTL과 phase-blocking 보안 통제
- [ForgeOps 검증 및 평가 계획](../quality/verification-and-evaluation-plan.md) — VG-001~VG-024, evidence floor와 Phase Exit 판정
- [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md) — 문서 책임, 상태, 10주 배치와 용량 원칙
- [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md) — 제품 원칙, 구현 로드맵과 포트폴리오 성공 기준
- [ForgeOps 제품 기초 문서 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md) — WBS-001~WBS-035의 exact 일정, 의존성, 용량과 검증 절차
- [저장소 기본 지시와 ForgeOps profile](../../AGENTS.md) — 권한, protected resource와 evidence 운영 규칙
