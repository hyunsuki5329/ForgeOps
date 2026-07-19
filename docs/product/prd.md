# ForgeOps 제품 요구사항 문서

**문서 상태:** 초안
**최종 검토일:** 2026-07-14
**대상 독자:** 1인 개발자, 포트폴리오 검토자
**기준 출처:** [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md), [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md)

## 1. 문서 목적과 기준

이 문서는 ForgeOps가 해결할 제품 문제와 Phase 0~4에서 충족해야 할 기능·비기능 요구사항, 성공 지표, release-level Exit gate를 정의한다. PRD는 제품이 **무엇을** 제공하고 **왜** 필요한지의 기준 소유 문서다. 구현 작업, 의존성, 일정, 완료 정의는 `docs/project/wbs.md`가 소유하며 이 문서에서 구현 순서나 상세 일정을 정하지 않는다.

요구사항은 다음 성숙도만 사용한다.

| Maturity | 의미 |
| --- | --- |
| IMPLEMENTED | 현재 저장소 파일과 fresh evidence로 확인 가능한 구현 |
| SPECIFIED | 계약과 기대 동작은 정의됐지만 제품 runtime은 아직 없음 |
| PLANNED | 향후 제품 비전 또는 로드맵 |

요구사항 표의 `Acceptance result`는 관찰되어야 할 수용 결과이며 현재 검증 상태가 아니다. `SPECIFIED`와 `PLANNED` 요구사항의 현재 검증 결과는 실제 실행과 fresh evidence가 생길 때까지 `NOT_RUN`이다. 성공 선언과 Phase Exit에는 관련 검증 계획이 요구하는 evidence floor의 `PASSED` 결과가 필요하다.

## 2. 제품 정의와 문제

ForgeOps는 자연어 개발 요청을 구조화된 작업 계약으로 바꾸고, 고정 snapshot과 격리 환경에서 계획·실행·검증·복구한 뒤 근거와 trace를 사람에게 제공하는 self-evaluating AI development workflow platform이다.

일반 코딩 도구는 코드 생성이나 파일 수정 자체에는 강하지만 변경 전 기준선, 새 회귀와 기존 실패의 구분, 행동의 권한과 이유, 실패 후 중단 조건, 실제 검증 근거를 한 workflow에서 보장하기 어렵다. ForgeOps는 생성량보다 다음 신뢰 문제를 제품 중심에 둔다.

- 변경 전 상태와 변경 후 결과를 비교할 수 있어야 한다.
- 계획, tool call, diff, 실패, repair, 검증이 근거와 함께 추적되어야 한다.
- 위험한 명령과 외부 효과는 exact authority와 명시적 승인 경계를 지켜야 한다.
- repair는 새 evidence가 있을 때만 제한적으로 수행되고 no-progress에서 중단되어야 한다.
- 최종 성공은 LLM의 서술이 아니라 deterministic check와 fresh evidence로 판정되어야 한다.

## 3. 목표 사용자와 대표 시나리오

| 사용자 | 핵심 필요 | 기대 결과 |
| --- | --- | --- |
| 개발자 | 반복 수정과 migration을 안전하게 완료 | 요청, diff, 검증 결과, 잔여 위험을 한 흐름에서 확인 |
| 리뷰어 또는 테크 리드 | 변경 안전성과 근거를 판단 | 계획, 위험, baseline 대비 결과, 승인 대상을 검토 |
| 플랫폼 관리자 | 권한, 비용, 통합을 통제 | allowlist, budget, approval, audit 경계를 집행 |
| AI 또는 플랫폼 엔지니어 | agent 품질을 비교하고 개선 | trace, benchmark, regression, 실패 분류를 분석 |

지원 결과는 다음과 같다.

- Issue to Patch to Draft PR
- dependency/API migration
- CI failure repair
- targeted refactoring
- security/quality remediation
- repository maintenance

대표 시나리오에서 ForgeOps는 자연어 요청이나 Issue를 검증 가능한 Contract로 만들고, 고정 source와 baseline을 확보하며, 승인된 범위에서 변경과 검증을 수행한다. 실패하면 failure evidence를 분류해 bounded repair를 적용하고, 최종 diff·trace·평가·잔여 위험을 사람이 검토할 수 있게 한다. 외부 write는 해당 Phase와 정책이 허용하고 exact approval이 존재할 때만 별도 효과로 수행한다.

## 4. 목표와 비목표

제품 목표는 다음과 같다.

1. 자연어 요청을 원문 의미와 제약을 보존하는 검증 가능한 작업 계약으로 바꾼다.
2. 원본과 실행 환경을 분리하고 최소 권한과 fail-closed 정책으로 변경을 통제한다.
3. baseline, task-specific check, regression check로 성공과 실패를 증명한다.
4. 실패를 숨기지 않고 evidence 기반의 bounded recovery와 명시적 중단을 제공한다.
5. 계획부터 검토까지의 trace, diff, artifact, approval 관계를 사람이 이해할 수 있게 보존한다.
6. 고정된 평가 계약으로 단순 tool-using agent 대비 효과와 안전성을 비교한다.

제품 비목표의 구체적 경계는 [11. 범위 제외](#11-범위-제외)에 정의한다. 특히 agent 수 자체가 차별점이 아니며 verification, recovery, sandbox, trace evaluation이 제품 가치의 중심이다.

## 5. 현재 Harness Foundation 기준선

현재 위치는 **Harness Foundation 완료, 제품 Phase 0 시작 전**이다. 현재 저장소에서 확인 가능한 구현과 향후 제품 runtime을 다음처럼 구분한다.

| 자산 또는 capability | Maturity | 현재 기준선 |
| --- | --- | --- |
| Portable Agent Harness Protocol 2.0 계약 | IMPLEMENTED | canonical packet, 상태, authority, evidence, fail-closed 불변식이 프롬프트 계약과 fixture에 정의됨 |
| Main / Part / Work 역할 | IMPLEMENTED | Main은 accepted state·revision·event sequence를 소유하고, Part는 읽기 전용 제안, Work는 승인된 exact action의 실행·검증을 담당 |
| 저장소 adapters | IMPLEMENTED | 루트 지시와 플랫폼 adapter가 Protocol 2.0 역할 및 저장소 profile을 연결 |
| Porting guide | IMPLEMENTED | 다른 harness로 계약을 옮길 때의 경계와 검증 지침이 존재 |
| 제품 API, UI, DB, queue, Tool Gateway service | PLANNED | 현재 제품 runtime 구현으로 간주하지 않음 |
| immutable snapshot과 ephemeral workspace 강제 | PLANNED | 현재 Harness의 직접 workspace 변경과 구분하며 격리 보장을 주장하지 않음 |
| sandbox provisioner와 durable persistence | PLANNED | containment, lifecycle, durable recovery는 향후 검증 대상 |
| rollback | PLANNED | 실제 snapshot/restore provider와 복원 evidence 없이는 가능하다고 주장하지 않음 |

현행 Harness의 Work는 사용자가 허용한 프로젝트 workspace의 exact resource를 직접 변경할 수 있다. 따라서 현재 기준선에 제품 runtime, immutable snapshot, sandbox, durable persistence 또는 rollback 보장을 포함하지 않는다.

## 6. 기능 요구사항

각 `Requirement` 셀의 첫 문장은 규범 요구사항이며 브리프의 ID, Phase, Priority, Maturity, 문구, VG 매핑을 보존한다. 이어지는 근거는 해당 요구사항이 해결하는 제품 문제를 설명한다.

| ID | Phase | Priority | Maturity | Requirement | Acceptance result | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| PRD-FR-001 | Phase 0 | 필수 | SPECIFIED | Product Task Contract를 TaskPacket으로 lossless 정규화하며 Contract가 authority를 만들지 않는다.<br>근거: 자연어 해석 손실과 계약을 통한 암묵적 권한 확대를 차단해야 한다. | 원문, criterion, constraint, source identity가 매핑 후 보존되고 authority는 runtime 관찰과 Main 결정 밖에서 추가되지 않는다. | VG-002 |
| PRD-FR-002 | Phase 0 | 필수 | SPECIFIED | 제품 state transition을 검증하고 canonical accepted state와 명시적으로 매핑하며 CANCELLED gap을 강제 변환하지 않는다.<br>근거: 제품 상태와 Harness 상태의 혼합은 거짓 terminal 결과와 복구 오류를 만든다. | 유효 전이만 수용되고 Main만 canonical state를 확정하며 CANCELLED는 versioned protocol 변경 전 제품 상태로 보존된다. | VG-003 |
| PRD-FR-003 | Phase 0 | 필수 | SPECIFIED | versioned OpenAPI와 closed request/response schema가 유효·무효 예제를 판정한다.<br>근거: 느슨한 API 계약은 잘못된 필드와 권한 의미가 runtime으로 유입되게 한다. | schema version에 맞는 예제는 수용되고 unknown, missing, wrong-type 필드가 있는 예제는 결정론적으로 거부된다. | VG-004 |
| PRD-FR-004 | Phase 0 | 필수 | SPECIFIED | durable event wrapper와 run manifest schema가 identity, ordering, provenance, reference를 보존한다.<br>근거: 실행 이력의 출처와 순서를 잃으면 감사와 재현이 불가능하다. | task와 run identity, 단조 순서, actor와 source provenance, artifact와 evidence reference가 schema 검증 후 해석된다. | VG-004 |
| PRD-FR-005 | Phase 0 | 필수 | PLANNED | sample repository와 positive/negative fixture가 conformance와 failure path를 재현한다.<br>근거: 성공 사례만으로는 fail-closed와 회귀 방지를 증명할 수 없다. | 고정 fixture를 반복 실행하면 positive case는 통과하고 지정된 negative case는 같은 실패 분류로 거부된다. | VG-001 |
| PRD-FR-006 | Phase 0 | 필수 | SPECIFIED | policy matrix와 approval UX가 exact action, 위험, 만료, 거절, 재승인을 설명한다.<br>근거: 사용자는 승인 범위와 변경 시 무효화 조건을 이해해야 안전하게 판단할 수 있다. | 승인 화면과 정책 결과가 candidate, action identity, target, 위험, expiry, deny 사유와 재승인 필요 조건을 일치시킨다. | VG-007 |
| PRD-FR-007 | Phase 0 | 필수 | PLANNED | sandbox containment PoC와 redaction/artifact 전략이 금지 경계를 fail-closed한다.<br>근거: host, 원본 저장소, secret과 raw log가 agent 실행에서 보호되어야 한다. | containment와 secret fixture에서 금지 접근·외부 유출·원문 기록이 0이고 불확실한 경로는 거부된다. | VG-008, VG-009 |
| PRD-FR-008 | Phase 1 | 필수 | PLANNED | repository snapshot, baseline, code retrieval이 고정 source와 변경 전 상태를 보존한다.<br>근거: 고정 기준이 없으면 agent가 만든 회귀와 기존 실패를 구분할 수 없다. | 모든 context와 baseline 결과가 동일 snapshot identity에 연결되고 변경 전 상태가 후속 diff와 비교 가능하다. | VG-010 |
| PRD-FR-009 | Phase 1 | 필수 | PLANNED | Context Pack이 근거 경로를 포함하고 repository prompt injection을 control plane으로 승격하지 않는다.<br>근거: 코드와 Issue의 비신뢰 문장이 정책이나 승인으로 오인되어서는 안 된다. | 선택한 context마다 path·snapshot·hash·선택 이유가 있고 비신뢰 지시는 authority, policy, budget을 바꾸지 못한다. | VG-011 |
| PRD-FR-010 | Phase 1 | 필수 | PLANNED | Main 정규화·라우팅, Part 분석, Work 실행·검증, Main 수용 흐름이 한 local run에서 완료된다.<br>근거: 역할 분리는 이름이 아니라 상태·권한·검증 소유권으로 입증되어야 한다. | local run 하나에서 각 actor 경계가 보존되고 필수 evidence를 검증한 MainDecision만 최종 결과를 확정한다. | VG-012 |
| PRD-FR-011 | Phase 1 | 필수 | PLANNED | patch와 diff는 ephemeral workspace에만 적용되고 외부 write는 발생하지 않는다.<br>근거: local vertical slice가 원본과 원격 시스템을 손상시키지 않아야 한다. | 모든 changed resource가 run workspace에 한정되고 원본 저장소, host 외부 경로, remote에는 write가 관찰되지 않는다. | VG-013, VG-015 |
| PRD-FR-012 | Phase 1 | 필수 | PLANNED | task test, regression test, lint, typecheck가 trusted profile과 fresh evidence로 판정된다.<br>근거: 모델의 완료 서술이나 agent가 만든 테스트만으로 성공을 판정할 수 없다. | 적용 가능한 trusted command가 exact profile로 실행되고 각 필수 criterion이 요구 floor의 fresh evidence에 연결된다. | VG-013 |
| PRD-FR-013 | Phase 1 | 필수 | PLANNED | budget, cancellation, cleanup, 기본 trace viewer가 terminal path를 설명한다.<br>근거: bounded autonomy는 중단과 자원 정리 및 다음 행동이 사용자에게 보여야 한다. | 정상·취소·예산 초과·실패 경로에서 terminal 이유, resource cleanup, 사용 budget, 허용된 다음 행동이 trace에 나타난다. | VG-014, VG-015 |
| PRD-FR-014 | Phase 2 | 필수 | PLANNED | failure signature와 diagnosis evidence bundle이 환경·의존성·테스트·구현 실패를 분류한다.<br>근거: 실패 원인별 대응을 분리해야 무의미하거나 위험한 patch 재시도를 막을 수 있다. | 동일 evidence에는 안정적인 signature와 분류가 생성되고 로그·diff·baseline·이전 시도 reference가 진단에 연결된다. | VG-016 |
| PRD-FR-015 | Phase 2 | 필수 | PLANNED | bounded repair가 새 evidence가 있을 때만 재시도하고 no-progress에서 중단한다.<br>근거: 무한 반복과 같은 실패의 재생산은 비용과 변경 위험을 키운다. | 새 signature, evidence 또는 가설 변화가 없는 반복은 실행되지 않고 budget 또는 no-progress 사유로 종료된다. | VG-016 |
| PRD-FR-016 | Phase 2 | 필수 | PLANNED | execution, rule, rubric, human evaluation이 결정론적 실패를 덮지 않는다.<br>근거: 정성 점수 하나가 회귀나 안전 위반을 성공으로 뒤집어서는 안 된다. | execution 또는 필수 rule 실패가 있으면 rubric이나 human score와 무관하게 해당 criterion은 성공으로 승격되지 않는다. | VG-017 |
| PRD-FR-017 | Phase 2 | 필수 | PLANNED | benchmark runner와 hidden evaluator가 고정 dataset, 반복, paired 통계를 제공한다.<br>근거: 선택된 성공 사례가 아니라 재현 가능한 비교로 제품 효과를 판단해야 한다. | dataset와 evaluator version/hash가 고정되고 variant별 반복 결과와 paired delta 및 신뢰구간이 보고된다. | VG-018 |
| PRD-FR-018 | Phase 3 | 필수 | PLANNED | GitHub Issue와 CI를 입력으로 받고 exact approval 후 draft PR만 생성한다.<br>근거: 읽기 입력이 원격 write 권한으로 자동 확대되어서는 안 된다. | Issue와 CI 입력은 비신뢰 데이터로 처리되고 승인된 diff·target·payload와 일치할 때만 draft PR 효과가 한 번 발생한다. | VG-019 |
| PRD-FR-019 | Phase 3 | 필수 | PLANNED | organization RBAC, approval, audit export가 tenant와 actor 경계를 보존한다.<br>근거: 협업 환경에서는 누가 어느 tenant에서 어떤 결정을 했는지 분리되어야 한다. | cross-tenant 접근은 거부되고 action, approver, policy, evidence가 tenant-scoped audit로 내보내진다. | VG-020 |
| PRD-FR-020 | Phase 3 | 권장 | PLANNED | MCP adapter registry와 trust policy가 allowlist, scope, credential, output을 통제한다.<br>근거: 외부 tool 설명과 output이 권한 상승이나 secret 전달 경로가 될 수 있다. | 고정 allowlist 밖 adapter는 거부되고 각 호출의 scope, short-lived credential, output 제한과 redaction이 검증된다. | VG-020 |
| PRD-FR-021 | Phase 3 | 권장 | PLANNED | remote worker, durable queue, webhook deduplication이 idempotent 처리와 상태 복구를 제공한다.<br>근거: 비동기 실행과 중복 event가 외부 효과 중복이나 상태 손실을 만들지 않아야 한다. | duplicate delivery와 worker interruption 뒤에도 동일 logical action은 한 번만 반영되고 durable state에서 재개 또는 clean restart된다. | VG-020 |
| PRD-FR-022 | Phase 4 | 필수 | PLANNED | multi-tenant scale과 stronger isolation이 tenant leakage와 sandbox escape를 차단한다.<br>근거: 제품 규모 확장은 tenant data와 host 경계를 약화하지 않아야 한다. | 공격 fixture와 운영 관찰에서 tenant 간 artifact 접근, credential leakage, sandbox escape가 0이다. | VG-021, VG-022 |
| PRD-FR-023 | Phase 4 | 권장 | PLANNED | language/framework plugin이 closed trust policy와 compatibility gate를 통과한다.<br>근거: 생태계 확장이 core contract와 검증 의미를 임의로 바꾸지 않아야 한다. | plugin은 선언된 capability·schema·version 검사를 통과해야 활성화되고 unknown 또는 incompatible plugin은 거부된다. | VG-023 |
| PRD-FR-024 | Phase 4 | 권장 | PLANNED | code graph, richer static analysis, security remediation이 근거와 검증을 제공한다.<br>근거: 고급 분석도 출처 없는 제안이나 검증 없는 수정으로 끝나서는 안 된다. | finding과 remediation이 snapshot source, 분석 근거, changed resource, 독립 검증 결과에 연결된다. | VG-023 |
| PRD-FR-025 | Phase 4 | 권장 | PLANNED | replay, experiment, continuous quality loop가 원본 identity와 외부 효과 경계를 보존한다.<br>근거: 품질 실험이 원본 실행을 오염시키거나 과거 승인을 재사용해서는 안 된다. | source task/run/manifest가 보존되고 새 run identity와 evidence가 분리되며 기본 replay에서 외부 효과와 기존 authority 재사용이 0이다. | VG-017, VG-018, VG-022 |

## 7. 비기능 요구사항

| ID | Scope | Priority | Maturity | Requirement | Acceptance result | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| PRD-NFR-001 | 전 단계 | 필수 | SPECIFIED | 성공 주장은 요구 floor의 fresh evidence를 가지며 결정론적 실패가 정성 점수로 뒤집히지 않는다.<br>근거: 검증되지 않은 성공 선언은 제품 신뢰의 핵심 실패다. | 모든 성공 criterion이 요구 tier와 freshness를 충족하고 deterministic failure가 하나라도 있으면 성공 결과가 생성되지 않는다. | VG-001, VG-023 |
| PRD-NFR-002 | 전 단계 | 필수 | SPECIFIED | RESOURCE, COMMAND, NETWORK, destructive, external effect authority가 exact match와 fail-closed를 적용하고 protected resource·credential·private data read는 별도 인간 승인 전 금지한다.<br>근거: 암묵적 정규화, 부분 일치와 승인 전 read는 권한 범위를 넓히고 민감 bytes를 model context에 유출한다. | 모든 action이 closed identity와 exact authority를 충족하며 missing, UNKNOWN, wildcard, normalization attempt는 effect 전에 거부되고 protected/secret 대상은 승인 전 model context·log·evidence에 읽힌 byte가 0이다. | VG-005, VG-006, VG-007, VG-008 |
| PRD-NFR-003 | Phase 0~4 | 필수 | PLANNED | immutable 원본과 실행 환경을 분리하고 sandbox 종료 후 resource가 남지 않는다.<br>근거: agent 실행이 source identity를 바꾸거나 host와 다음 run에 상태나 권한을 남기지 않아야 한다. | baseline·retrieval·workspace가 같은 snapshot/hash에 묶이고 원본 write가 0이며 terminal 또는 cancel 뒤 process, mount, lease, transient secret, workspace 잔존이 0이다. | VG-008, VG-010, VG-014 |
| PRD-NFR-004 | 전 단계 | 필수 | SPECIFIED | secret, private payload, raw log, artifact가 redaction, encryption, retention, tenant isolation을 따른다.<br>근거: evidence와 관찰성 계층 및 포트폴리오 package가 민감정보 유출 경로가 되어서는 안 된다. | packet, event, artifact, trace, telemetry, 사용자 응답과 public-safe package에서 확인된 raw secret·private identifier가 0이고 저장 데이터가 정책과 tenant 경계를 지킨다. | VG-009, VG-024 |
| PRD-NFR-005 | Phase 1~4 | 필수 | PLANNED | idempotency, cancellation, replay, cleanup, recovery가 중복 외부 효과와 상태 손실을 막는다.<br>근거: retry와 비동기 failure가 같은 효과를 반복하거나 accepted state를 잃게 할 수 있다. | duplicate request, timeout, cancel, worker interruption, replay에서 effect 중복이 없고 상태 전이와 정리 결과가 복구된다. | VG-014, VG-015, VG-019 |
| PRD-NFR-006 | Phase 0~4 | 필수 | SPECIFIED | trace, event, manifest, audit가 task, run, revision, actor, evidence 관계를 해석 가능하게 보존한다.<br>근거: 사람이 변경 이유와 책임 및 검증 근거를 재구성할 수 있어야 한다. | terminal run에서 필수 identity와 reference가 해석되고 event ordering과 evidence provenance에 단절이 없다. | VG-004, VG-015 |
| PRD-NFR-007 | Phase 4 | 필수 | PLANNED | event p99 2초, cleanup p99 60초·hard max 5분, trace 99.5%, manifest 99.9%, R2 95%, API 99.9% 목표를 측정한다.<br>근거: 제품 성숙도는 검토 가능성과 격리 lifecycle의 운영 신뢰성으로 확인되어야 한다. | 정의된 window와 denominator로 모든 SLI가 측정되고 목표 미달과 표본 제외가 숨겨지지 않는다. | VG-022 |
| PRD-NFR-008 | 전 단계 | 필수 | SPECIFIED | 시간, token, tool, command, repair, 비용 budget을 강제하고 초과 시 명시적으로 중단한다.<br>근거: 자율 실행이 무한 반복과 예측 불가능한 비용으로 이어져서는 안 된다. | 각 budget 사용량이 trace에 남고 한도 초과 전 추가 실행이 차단되며 terminal reason이 사용자에게 표시된다. | VG-014 |
| PRD-NFR-009 | 전 단계 | 권장 | SPECIFIED | core contract는 model, host, provider에 독립적이고 adapter가 capability를 정규화한다.<br>근거: 특정 실행 표면이 제품 권한과 evidence 의미를 재정의하면 이식성과 안전성이 깨진다. | adapter 교체 후에도 canonical enum과 불변식이 유지되고 관찰하지 못한 capability는 UNKNOWN으로 처리된다. | VG-001, VG-023 |
| PRD-NFR-010 | Phase 2~4 | 필수 | SPECIFIED | dataset version/hash, 최소 반복, paired CI, judge version, 이중 판정으로 평가 재현성을 보장한다.<br>근거: 모델 비결정성과 평가 편향을 통제하지 않으면 연구 주장을 재현할 수 없다. | 동일 평가 계약에서 version/hash, 반복 수, paired 통계, judge identity, agreement가 모두 보고된다. | VG-017, VG-018 |
| PRD-NFR-011 | Phase 1~4 | 권장 | PLANNED | 사용자가 상태, 이유, 위험, diff, 검증, 승인, 다음 행동을 한 workflow에서 이해한다.<br>근거: trace가 있어도 사람이 결정에 필요한 맥락을 찾지 못하면 제품 가치가 없다. | 대표 사용자 검토에서 terminal 상태의 원인과 허용된 다음 행동을 별도 로그 해석 없이 식별한다. | VG-015, VG-024 |
| PRD-NFR-012 | Phase 3~4 | 필수 | PLANNED | tenant, credential, integration, plugin, worker 경계가 zero-event security invariants를 유지한다.<br>근거: 통합과 확장이 늘어도 보호 자산의 경계 위반은 허용할 수 없다. | controlled integration, multi-tenant isolation과 rolling 운영 관찰에서 무권한 action, gateway 우회 write, raw secret, nonce 재사용, cross-tenant artifact 접근이 모두 0이다. | VG-020, VG-021, VG-022 |

## 8. 단계별 Exit gate

아래 gate는 release-level 수용 결과다. 현재 제품 runtime이 없으므로 Phase 0~4의 현재 결과는 모두 `NOT_RUN`이며, gate 문구는 현재 달성 주장이나 일정 약속이 아니다.

| Phase | Release-level Exit gate | 현재 결과 |
| --- | --- | --- |
| Phase 0 | example schema와 Harness conformance 통과, invalid transition/authority와 approval deny/expiry/nonce reuse fail-closed, sandbox containment와 secret fixture 100%. | NOT_RUN — PLANNED 제품 산출물과 실행 증빙이 아직 없음 |
| Phase 1 | 모든 필수 criterion E2 이상, unauthorized execution 0, cleanup failure 0, external write 0. | NOT_RUN — PLANNED local vertical slice가 아직 없음 |
| Phase 2 | 최소 5회 반복과 사전 고정 평가 계약, unauthorized action 0, raw secret 0, critical injection escape 0, task-success paired 95% CI lower bound greater than 0, regression-rate paired 95% CI upper bound less than 0. | NOT_RUN — PLANNED recovery와 evaluation runtime이 아직 없음 |
| Phase 3 | idempotency, expired approval, duplicate webhook, unauthorized external write 시험 통과. | NOT_RUN — PLANNED controlled integration이 아직 없음 |
| Phase 4 | rolling 30-day SLO 충족과 security invariant 위반 0. | NOT_RUN — PLANNED 운영 window 측정이 아직 없음 |

Harness Foundation의 `IMPLEMENTED` 상태는 위 제품 Phase gate를 대신하지 않는다. 필수 요구사항과 phase-blocking 통제의 `FAILED` 또는 `NOT_RUN`은 해당 Phase Exit를 차단한다.

## 9. 성공 지표와 평가 기준

### 9.1 제품·평가 지표

| 지표 | 계산과 보고 규칙 |
| --- | --- |
| Task success rate | 모든 필수 criterion이 요구 evidence floor에서 `PASSED`인 scheduled run / 전체 scheduled run |
| Regression rate | baseline에서 통과했으나 변경 후 실패한 check / baseline 통과 check. 분모가 0인 case는 제외하지 않고 `BASELINE_UNHEALTHY`로 별도 보고 |
| Recovery success rate | `RECOVERING` 진입 후 budget 안에 `SUCCEEDED`한 run / `RECOVERING` 진입 run |
| No-progress stop | 반복 failure signature와 evidence/diff 변화 없음이라는 정답 label에 대한 precision과 recall |
| Unauthorized action rate | 유효한 exact authority 없이 실제 실행된 action / 전체 action attempt. 목표는 0 |
| Injection escape rate | 비신뢰 명령 승격, secret 노출 또는 무권한 효과가 발생한 공격 case / 전체 공격 case |
| Unrelated change rate | 허용 범위 밖 changed line / 전체 changed line. generated file은 별도 보고 |
| Human revert rate | 승인 후 14일 관찰을 완료한 변경 중 결함 때문에 revert된 변경 / 관찰 완료 변경 |
| Latency | task accepted부터 terminal state까지 p50/p95. 사람 승인 대기 시간은 별도 분리 |
| Cost | scheduled run당 token/API 비용과 성공 run당 비용, tool call 수 |

Phase 2의 핵심 연구 질문은 실행 기반 검증, bounded recovery, trace-level evaluation을 결합한 ForgeOps가 단순 tool-using agent보다 task success rate를 높이고 regression rate와 불필요한 변경을 낮추는지다. 비교 delta는 `ForgeOps Full - Tool-using agent without baseline and recovery`로 정의하며 다음 조건을 모두 만족해야 개선을 주장할 수 있다.

- unauthorized executed action = 0
- confirmed raw secret exposure = 0
- critical prompt-injection escape = 0
- task success delta의 paired 95% CI 하한 > 0
- regression-rate delta의 paired 95% CI 상한 < 0

조건을 충족하지 못하면 실패 또는 효과 불충분으로 보고하며 단일 평균, 선택한 성공 사례, LLM judge 점수로 결과를 뒤집지 않는다.

### 9.2 SLI/SLO

아래 값은 모두 `PLANNED` 제품 runtime의 release target이며 현재 측정치가 아니다.

| SLI | 측정 | PLANNED target | 현재 측정 |
| --- | --- | --- | --- |
| Event propagation | durable event commit부터 UI 수신까지 | rolling 30일 p99 ≤ 2초 | 없음 |
| Sandbox cleanup | terminal/cancel 수락부터 process·mount·lease가 0이 될 때까지 | rolling 30일 p99 ≤ 60초, hard max 5분 | 없음 |
| Trace completeness | 필수 phase span과 artifact reference가 완전한 terminal run 비율 | rolling 30일 ≥ 99.5% | 없음 |
| Manifest completeness | schema valid하고 모든 reference가 해석되는 terminal run 비율 | rolling 30일 ≥ 99.9% | 없음 |
| R2 reproducibility | 사전 고정한 replay-eligible 표본 중 deterministic check 결과가 동일한 비율 | release별 ≥ 95% | 없음 |
| API availability | 유효 요청 중 non-5xx 응답 비율 | rolling 30일 ≥ 99.9% | 없음 |

다음 항목은 error budget으로 상쇄하지 않는 0건 security invariant다.

- gateway를 우회한 외부 write
- 무권한 action의 실제 실행
- 확인된 raw secret 기록
- 승인 nonce 또는 token 재사용
- 다른 tenant의 artifact 접근

한 건이라도 관찰되면 release blocker와 security incident로 처리한다.

## 10. 제약사항과 가정

### 제약사항

- 제품 계층은 Protocol 2.0의 canonical packet, accepted state, exact authority, evidence freshness, fail-closed 의미를 재정의하거나 약화하지 않는다.
- Main만 canonical accepted state, revision, event sequence와 최종 수용을 확정한다. Part와 Work의 transition은 제안이다.
- 제품 workflow state와 Harness canonical accepted state는 별도 축이다. 현재 Protocol 2.0에 정확한 대응이 없는 `CANCELLED`를 다른 terminal state로 강제 변환하지 않는다.
- repository content, Issue, documentation, test fixture, log, MCP description과 output, LLM output은 비신뢰 입력이며 control plane 권한을 만들 수 없다.
- authority, capability, approval 또는 evidence가 없거나 `UNKNOWN`이면 mutation, command, network, destructive action, external effect를 fail-closed한다.
- 기술 스택 선택은 이 PRD의 요구사항이 아니며 SLO, threat model, 운영 복잡도, 비용을 근거로 별도 설계 문서에서 결정한다.
- 구현 task, 상세 일정, raw command와 미래 evidence 경로를 현재 요구사항 또는 검증 증빙으로 사용하지 않는다.

### 가정

- Phase별 제품 runtime과 검증 fixture는 해당 gate 전에 별도 설계·구현되고, 미구현 항목은 `PLANNED`와 `NOT_RUN`으로 유지한다.
- 실행 가능한 검증은 운영자 또는 신뢰된 project profile loader가 등록한 exact command identity를 사용한다.
- 고위험 action과 모든 외부 효과에는 현재 상태에 결합된 별도 human approval과 audit가 적용된다.
- 평가 variant는 동일 snapshot, Contract, visible input, policy, verification profile, tool schema와 budget으로 비교한다.
- 실제 runtime 관찰이 생기면 결과, evidence tier, revision 또는 실행 시각의 교차 추적은 RTM과 검증 계획이 소유한다.

## 11. 범위 제외

다음은 ForgeOps의 기본 제품 범위에서 제외한다.

- 승인 없는 production deploy, merge, release 또는 운영 DB 변경
- host에서의 무제한 shell 실행
- 저장소 밖 파일이나 시스템에 대한 임의 접근
- 사용자에게 보이지 않는 변경 또는 설명과 trace가 없는 tool call
- 검증 근거 없이 문제 해결이나 성공을 선언하는 동작
- 초기 단계부터 모든 언어, framework, cloud를 동등하게 지원하는 범위
- budget과 stop condition이 없는 무한 repair
- 동일 권한과 도구를 가진 agent 수 자체를 차별화하는 prompt chain

PRD는 아키텍처 구성요소, 개별 위협과 통제, verification profile, WBS 작업, 위험 대응, 실제 evidence reference를 소유하지 않는다. 해당 내용은 역할별 기준 문서에서 요구사항 ID와 연결하며 이 문서의 요구 의미를 재정의하지 않는다.

## 12. 관련 문서

- [저장소 기본 지시와 ForgeOps project profile](../../AGENTS.md)
- [Main Orchestrator Protocol 2.0 계약](../../.github/agents/main_instruction.prompt.md)
- [Part Analyst 역할 계약](../../.github/agents/part_agent.prompt.md)
- [Work Executor 역할 계약](../../.github/agents/work_agent.prompt.md)
- [Portable Agent Harness 포팅 가이드](../agent-harness/PORTING_GUIDE.md)
- [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md)
- [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md)
