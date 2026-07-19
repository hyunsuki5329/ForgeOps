# ForgeOps 위험 등록부

**문서 상태:** 초안

**최종 검토일:** 2026-07-14

**대상 독자:** 1인 개발자, 포트폴리오 검토자

**문서 목적:** ForgeOps의 일정·제품·기술·보안·평가·포트폴리오 위험을 관찰 가능한 trigger, 대응과 검토 시점으로 관리

**문서 범위:** Harness Foundation 이후 Phase 0~4의 RSK-001~RSK-014와 W1~W10 주간 운영·Phase gate escalation

**현재 상태:** 제품 Phase 0 시작 전이며 모든 위험은 초기 계획 상태 `OPEN`; 예방·contingency는 실행 완료나 위험 수용을 뜻하지 않음

**기준 출처:** [제품 요구사항](../product/prd.md), [시스템 아키텍처](../architecture/system-architecture.md), [위협 모델](../security/threat-model.md), [WBS](wbs.md), [검증 및 평가 계획](../quality/verification-and-evaluation-plan.md), [승인된 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md), [ForgeOps 제품 기초 문서 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md)

**관련 문서:** [6. 관련 문서](#6-관련-문서)

**알려진 초기 drift:** 기존 핸드오프는 `intent.source_issue`를 canonical
`project_profile.source_of_truth`에도 매핑하지만, 현행 Protocol 2.0과
아키텍처는 이를 namespaced untrusted provenance로만 보존한다. 이번 작업은
핸드오프 변경 권한을 포함하지 않으므로 `RSK-002`를 `OPEN`으로 유지하며
WBS-002·WBS-004 책임 아래 W2에 별도 승인된 동기화 여부를 검토한다.

## 1. 목적과 운영 규칙

이 문서는 위험의 조기 신호, 예방, contingency, 관련 요구사항·통제·작업과
다음 검토 시점을 한 곳에서 관리한다. PRD의 요구 의미, 위협 모델의 severity,
WBS 일정 또는 VG 판정을 재정의하지 않는다. 위험 행의 대응 문구는 계획이며
실제 action, 비용, credential, 외부 효과 또는 승인이 관찰됐다는 주장이 아니다.

운영 규칙은 다음과 같다.

1. Probability와 Impact는 각각 1~5의 원본 정수이고 Score는 두 값의 곱이다.
2. Status는 `OPEN`, `MITIGATING`, `MONITORING`, `CLOSED`만 사용한다.
3. trigger는 관찰 가능한 조건으로 기록하고 충족되면 목표 검토일까지
   기다리지 않고 즉시 재평가한다.
4. 예방과 contingency는 기존 authority 안의 계획이다. 이 문서나 숫자
   score는 capability, authority, approval 또는 외부 효과 권한을 만들지 않는다.
5. 1인 개발자 계획이므로 병렬 완료를 가정하지 않고 WBS의 4 person-day
   계획과 1 person-day buffer를 보존한다.
6. 보안 통제 severity와 `phase_blocking`은 project risk score보다 우선한다.
   중대한 보안 불변식 위반을 일정 위험으로 수용하거나 평균 score로 상쇄하지 않는다.
7. risk closure와 downgrade에는 fresh evidence 또는 변경된 premise가 필요하다.
   달력 경과, 일정 압박, 정성 점수 또는 사용자 침묵만으로 닫지 않는다.

## 2. 점수와 상태

### 점수 산정

| 값 | Probability | Impact |
| ---: | --- | --- |
| 1 | 현재 전제에서 드물며 명확한 선행 사건이 필요 | 문서 또는 단일 비차단 작업의 작은 재작업 |
| 2 | 발생 가능성이 낮지만 알려진 경로가 존재 | 제한된 작업 재계획 또는 국소 품질 저하 |
| 3 | 계획 기간에 발생할 수 있는 현실적 가능성 | 주차·component 또는 검증 결과에 중간 영향 |
| 4 | 현재 제약에서 발생 가능성이 높음 | Phase gate, 보안 경계 또는 핵심 산출물에 큰 영향 |
| 5 | 이미 발생 중이거나 거의 확실 | 안전·privacy·외부 효과·release에 치명적 영향 |

`Score = Probability × Impact`이며 허용 범위는 1~25다. Probability나
Impact를 바꾸면 관찰 근거와 변경 이유를 같은 검토 기록에 남긴다.

| Score | 처리 |
| --- | --- |
| 17~25 | release/Phase blocking; 즉시 mitigation을 시작하고 해소 evidence 전에는 다음 gate로 진행하지 않음 |
| 10~16 | weekly review와 named mitigation task가 필수이며 관련 gate 전 미해소 상태를 명시 |
| 5~9 | 각 Phase checkpoint에서 monitor하고 trigger 변화 시 즉시 재평가 |
| 1~4 | trigger가 변할 때 monitor하며 값이 낮다는 이유로 안전 gate를 생략하지 않음 |

### 상태 enum

| Status | 의미 |
| --- | --- |
| `OPEN` | 위험과 trigger가 식별됐지만 예방·mitigation의 완료 evidence가 없음 |
| `MITIGATING` | named mitigation task가 승인된 범위에서 진행 중이며 결과를 아직 검토하지 않음 |
| `MONITORING` | 예방 또는 mitigation 결과를 관찰했고 closure 전 trigger와 잔여 위험을 추적 중 |
| `CLOSED` | 변경된 premise 또는 요구 floor의 fresh evidence로 closure 결정을 기록했으며 재개 trigger가 명시됨 |

초기 14개 위험은 모두 `OPEN`이다. 일반 전이는 `OPEN → MITIGATING →
MONITORING → CLOSED`이며, trigger 재발이나 전제 변경 시 `CLOSED` 또는
`MONITORING`에서 `OPEN`·`MITIGATING`으로 다시 연다. 위험 Status는 WBS
Status, requirement Maturity, VG result 또는 Protocol accepted state가 아니다.

## 3. 위험 카탈로그

Related IDs는 추적 link이며 각 기준 문서의 본문을 반복하지 않는다.

| ID | Category | Risk | Probability | Impact | Score | Trigger | Prevention | Contingency | Related PRD / THR / CTL / WBS | Target review | Status |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |
| RSK-001 | 범위·일정 | 10주 범위 확장과 Phase 2~4 상세화 | 4 | 4 | 16 | Phase 0~1 밖의 상세 sprint·확정 주차가 추가되거나 한 주 계획이 4pd를 넘고 buffer가 신규 scope에 배정됨 | `lock PRD scope and WBS capacity`; Phase 0~1 baseline과 주간 4pd 한도를 변경 통제로 고정 | `move only Phase 2~4 detail to successor plan`; 상세를 후속 계획으로 옮기고 새 scope는 별도 human authority 전 진행하지 않음 | PRD: PRD-FR-014, PRD-FR-015, PRD-FR-016, PRD-FR-017, PRD-FR-018, PRD-FR-019, PRD-FR-020, PRD-FR-021, PRD-FR-022, PRD-FR-023, PRD-FR-024, PRD-FR-025, PRD-NFR-008; THR: THR-012; CTL: CTL-017; WBS: WBS-033, WBS-034, WBS-035 | W1, weekly | OPEN |
| RSK-002 | 제품·계약 | Product와 Protocol 2.0 contract drift | 3 | 5 | 15 | 제품 schema·adapter가 canonical state, authority, evidence field를 누락·완화하거나 implicit normalization을 추가하거나, 핸드오프의 `intent.source_issue` mapping과 trusted Protocol 경계가 불일치한 채 기준선·구현됨 | `ARC-002/009/010 and VG-001~003 conformance review`; 현행 Protocol을 우선해 `source_issue`는 namespaced untrusted provenance로만 보존하고 WBS-002·WBS-004 owner가 bridge와 핸드오프 차이를 대조 | `block merge and restore the last compatible contract`; 별도 승인으로 핸드오프를 동기화하거나 versioned Protocol 결정을 내리기 전까지 bridge 통합과 문서 기준선을 차단 | PRD: PRD-FR-001, PRD-FR-002, PRD-NFR-001, PRD-NFR-009; THR: THR-010; CTL: CTL-015, CTL-020; WBS: WBS-001, WBS-002, WBS-004, WBS-007, WBS-008, WBS-016, WBS-019 | W2 (WBS-002·WBS-004 owner) | OPEN |
| RSK-003 | 제품·identity | product state, replay, run identity 혼합 | 3 | 5 | 15 | `CANCELLED`를 임의 canonical terminal로 바꾸거나 snapshot·task/run·revision·seq·stream_seq를 대체하고 replay에 과거 authority를 복사함 | `ARC-009/013 identity matrix and VG-003/019`; identity와 replay mode를 versioned matrix로 검토 | `stop replay and require a versioned identity decision`; replay를 중단하고 명시적 version decision 전 mapping을 만들지 않음 | PRD: PRD-FR-002, PRD-FR-004, PRD-FR-018, PRD-FR-025, PRD-NFR-005, PRD-NFR-006; THR: THR-009, THR-010; CTL: CTL-008, CTL-015, CTL-019, CTL-020; WBS: WBS-004, WBS-007, WBS-008, WBS-019, WBS-034, WBS-035 | W2 | OPEN |
| RSK-004 | 기술·보안 | host에서 요구 sandbox 격리 달성 불가 | 4 | 5 | 20 | WBS-010 PoC가 image provenance, namespace·mount·device·socket, egress, quota 또는 teardown negative case를 차단하지 못함 | `WBS-010 early containment PoC and CTL-009~012`; Phase 0에서 host 제약과 공격 fixture를 먼저 관찰 | `require gVisor, Kata, microVM, or dedicated worker before continuation`; 적합한 stronger isolation 결정과 fresh evidence 전 이후 실행을 차단 | PRD: PRD-FR-007, PRD-FR-011, PRD-FR-022, PRD-NFR-003, PRD-NFR-012; THR: THR-004, THR-005, THR-012; CTL: CTL-009, CTL-010, CTL-011, CTL-012; WBS: WBS-010, WBS-013, WBS-024, WBS-026, WBS-028, WBS-035 | W4 | OPEN |
| RSK-005 | 보안·권한 | exact authority·approval policy 오구성 또는 비신뢰 입력의 control 승격 | 3 | 5 | 15 | wildcard·normalization·`UNKNOWN`, wrong target·expiry·nonce reuse가 허용되거나 destructive/external hard gate가 빠지거나 repository·Issue·log·MCP description/output의 비신뢰 입력이 policy·approval·budget·tool schema를 바꾸는 control instruction으로 승격됨 | `CTL-002~007 negative fixtures`; data/control plane을 분리하고 `CTL-001/VG-011 injection fixture`와 Context Pack path·snapshot·hash·selection provenance를 확인하며 effect 전에 RESOURCE·COMMAND·NETWORK·approval 거부 경로를 실행 | `deny action, invalidate approval, and reopen WBS-005`; affected run을 정지하고 injected input을 격리하며 authority·approval을 무효화하고 WBS-005·WBS-015·WBS-017을 재검토 | PRD: PRD-FR-006, PRD-FR-009, PRD-FR-018, PRD-NFR-002, PRD-NFR-005, PRD-NFR-012; THR: THR-001, THR-002, THR-003, THR-004, THR-006; CTL: CTL-001, CTL-002, CTL-003, CTL-004, CTL-005, CTL-006, CTL-007; WBS: WBS-005, WBS-015, WBS-017, WBS-018, WBS-026, WBS-034 | W2, W4 | OPEN |
| RSK-006 | 보안·privacy | secret, raw log, artifact, tenant 정보 유출 | 3 | 5 | 15 | packet·event·artifact·trace·exporter·응답에 raw secret이 나타나거나 cross-tenant reference·retention·redaction 검사가 실패함 | `CTL-013/014 and VG-009/024`; 저장·export 전 redaction과 public-safe·artifact isolation gate를 적용 | `quarantine or delete artifact, revoke credential, open security incident`; artifact를 격리·삭제하고 credential을 회수하며 incident를 개시 | PRD: PRD-FR-007, PRD-FR-019, PRD-FR-022, PRD-NFR-004, PRD-NFR-006, PRD-NFR-012; THR: THR-007, THR-008; CTL: CTL-013, CTL-014, CTL-020; WBS: WBS-011, WBS-026, WBS-031, WBS-034, WBS-035 | W4, W10 | OPEN |
| RSK-007 | 품질·evidence | baseline 불건전, test 조작, stale evidence | 3 | 4 | 12 | baseline이 실패·flaky·분모 0이거나 trusted profile 변경, test 약화, wrong-revision·stale·future·dangling evidence가 발견됨 | `trusted baseline profile and CTL-015/016`; baseline과 evaluator를 workspace 밖에서 고정하고 evidence freshness를 검증 | `mark BASELINE_UNHEALTHY or NOT_RUN and block success`; 실패를 정성 점수로 상쇄하지 않고 관련 criterion과 Exit를 차단 | PRD: PRD-FR-008, PRD-FR-012, PRD-FR-016, PRD-NFR-001, PRD-NFR-006, PRD-NFR-010; THR: THR-010, THR-011; CTL: CTL-015, CTL-016, CTL-020; WBS: WBS-014, WBS-021, WBS-022, WBS-027, WBS-028, WBS-030 | W5, W7, W9 | OPEN |
| RSK-008 | 평가·통계 | benchmark 표본 부족, judge bias, 통계 오해 | 3 | 4 | 12 | 최소 반복·power·목표 CI width를 충족하지 않거나 split/hash 변경, infra failure 제외, weighted kappa 미달, paired CI 오해가 발생함 | `fixed dataset/hash, power analysis, paired CI`; 평가 계약과 표본 결정을 실행 전에 고정 | `report insufficient evidence and expand the predeclared evaluation`; 효과를 선언하지 않고 사전 정의된 평가 범위만 확장 | PRD: PRD-FR-016, PRD-FR-017, PRD-FR-025, PRD-NFR-010; THR: THR-011, THR-012; CTL: CTL-016, CTL-017, CTL-020; WBS: WBS-033 | Phase 2 entry | OPEN |
| RSK-009 | 통합·외부 효과 | 외부 effect 중복, unknown outcome, webhook replay | 2 | 5 | 10 | 동일 logical effect가 중복 처리되거나 timeout·unknown outcome 뒤 자동 retry, duplicate webhook, approval·nonce 재사용이 관찰됨 | `CTL-008/019 and remote reconcile`; replay hard deny, idempotency ledger와 현재 remote state 관찰을 결합 | `stop retries and reconcile external state before a new candidate`; 결과가 확인될 때까지 같은 effect와 새 publish를 차단 | PRD: PRD-FR-018, PRD-FR-021, PRD-FR-025, PRD-NFR-005, PRD-NFR-006, PRD-NFR-012; THR: THR-006, THR-009; CTL: CTL-007, CTL-008, CTL-019, CTL-020; WBS: WBS-034, WBS-035 | Phase 3 entry | OPEN |
| RSK-010 | 기술·운영 | 기술 선택과 운영 복잡도가 Exit gate를 초과 | 3 | 3 | 9 | 동일 결정에 복수 default를 유지하거나 PoC가 SLO·보안·운영·비용 기준을 충족하지 못하고 선택이 Phase capacity를 넘음 | `one default per decision with exit criteria`; 대안·선택·기각 기준과 단계별 gate를 고정 | `defer the component rather than shipping simultaneous defaults`; 미결정 component는 PLANNED로 남기고 동시 default를 배포하지 않음 | PRD: PRD-FR-007, PRD-FR-021, PRD-FR-022, PRD-FR-023, PRD-NFR-003, PRD-NFR-007, PRD-NFR-009; THR: THR-005, THR-008, THR-012; CTL: CTL-009, CTL-010, CTL-011, CTL-014, CTL-017, CTL-018; WBS: WBS-010, WBS-033, WBS-034, WBS-035 | each Phase entry | OPEN |
| RSK-011 | 일정·용량 | 1인 개발 용량 부족과 연속 carry-over | 4 | 4 | 16 | 주간 계획이 4pd를 넘거나 buffer가 계획 작업에 소진되고 carry-over가 2주 연속 발생하거나 Phase gate가 목표 주차에 미달함 | `4 pd plan plus 1 pd buffer`; 병렬 완료를 가정하지 않고 buffer를 실패·검토에 보존 | `replan after two carry-over weeks and protect the Phase gate`; 미래 작업을 자동으로 당기지 않고 의존성과 목표 주차를 재계산 | PRD: PRD-FR-013, PRD-NFR-008; THR: THR-012; CTL: CTL-011, CTL-017; WBS: WBS-012, WBS-028, WBS-032 | weekly | OPEN |
| RSK-012 | 문서·추적성 | 문서 간 ID drift와 orphan trace | 3 | 4 | 12 | duplicate·unknown ID, broken link, orphan PRD·THR·CTL·WBS·VG 또는 문서 변경 뒤 교차 검증 누락이 발견됨 | `Task 7 cross-validator on every document change`; ID와 reference를 변경마다 전체 교차 검사 | `mark trace GAP and block document baselining`; 누락 owner와 목표 시점을 기록하고 baselining을 차단 | PRD: PRD-NFR-001, PRD-NFR-006, PRD-NFR-009; THR: THR-010; CTL: CTL-015, CTL-020; WBS: WBS-001, WBS-008, WBS-012, WBS-019, WBS-027, WBS-030, WBS-032 | every document change | OPEN |
| RSK-013 | 포트폴리오·compliance | 포트폴리오 공개 시 privacy, secret, license 위반 | 2 | 5 | 10 | package에 credential, private repository, tenant ID, raw log, 복원 가능한 secret, 불명확 license가 포함되거나 승인 없이 게시가 요청됨 | `VG-024 public-safe review`; 공개 fixture, redaction, license provenance와 manifest hash를 점검 | `remove unsafe material and keep publication unapproved`; unsafe material을 제거하고 exact publication authority 전 package를 내부 상태로 유지 | PRD: PRD-NFR-004, PRD-NFR-006, PRD-NFR-011; THR: THR-007, THR-008; CTL: CTL-013, CTL-014, CTL-020; WBS: WBS-003, WBS-031, WBS-032 | W10 | OPEN |
| RSK-014 | 비용·dependency | dependency, API, cloud 사용의 material cost | 2 | 4 | 8 | paid API·service·cloud resource, billing account, 새 credential 또는 승인 budget 밖 비용이 구현·검증에 필요해짐 | `local-first design and cost approval gate`; 무료·local 대안을 먼저 검토하고 비용 상한 전에는 외부 사용을 시작하지 않음 | `stop before paid usage and request material-cost authority`; provider·대상·상한·기간을 제시하고 새 human decision 전 호출하지 않음 | PRD: PRD-FR-020, PRD-FR-021, PRD-FR-022, PRD-NFR-008, PRD-NFR-009; THR: THR-012; CTL: CTL-017, CTL-018; WBS: WBS-023, WBS-033, WBS-034, WBS-035 | before any paid service | OPEN |

## 4. 주간 검토 절차

W1~W10에는 주 1회 정기 검토를 수행하고 trigger가 충족되면 즉시 임시
검토를 연다. `Phase 2 entry`, `Phase 3 entry`, `each Phase entry`,
`every document change`, `before any paid service` 항목은 달력 주차보다 해당
event가 우선한다.

1. **입력 고정:** 적용 PRD, THR/CTL, WBS, VG와 지난 검토의 risk Status,
   Probability, Impact, trigger observation을 읽는다.
2. **trigger 확인:** 실제 관찰과 WBS carry-over, Phase gate, zero-event
   security invariant, 비용·publication·credential 요청을 대조한다.
3. **점수 재계산:** P와 I를 근거 없이 낮추지 않고 `P × I`를 다시 계산한다.
   score와 처리 band가 불일치하면 Status 변경 전에 바로잡는다.
4. **named mitigation:** score 10~16은 관련 WBS 또는 승인된 successor task를
   named mitigation으로 지정하고 owner, 목표 검토, 필요한 VG/evidence를
   기록한다. 위험 행 자체는 작업 실행 권한이 아니다.
5. **Phase 영향:** score 17~25, CRITICAL CTL failure, zero-event 위반,
   phase-blocking VG의 `FAILED`·`NOT_RUN`·stale·floor 미달과 추적
   `PARTIAL`·`GAP`을 release/Phase block으로 표시한다.
6. **상태 결정:** 실제 mitigation 진행 여부와 fresh observation으로만
   `OPEN`, `MITIGATING`, `MONITORING`, `CLOSED`를 선택하고 다음 review와
   reopen trigger를 기록한다.
7. **변경 통제:** WBS capacity, PRD scope, CTL severity, VG floor 또는 human
   gate가 바뀌면 관련 기준 문서와 RTM을 같은 변경에서 갱신하거나 추적
   `GAP`으로 남긴다.

주간 검토는 위험이 없다는 선언이 아니다. `MONITORING`은 잔여 위험이
존재한다는 뜻이고, `CLOSED`도 새 trigger가 관찰되면 다시 연다.

## 5. Escalation과 Phase gate

### 숫자 score와 보안 gate

- Score 17~25는 release/Phase blocking이며 immediate mitigation이 필요하다.
- Score 10~16은 weekly review와 named mitigation task가 필요하다.
- Score 5~9는 Phase checkpoint에서 monitor한다.
- Score 1~4는 trigger 변화 시 monitor한다.
- 어떤 `CRITICAL` CTL failure도 숫자 project-risk score와 관계없이
  phase blocking이다. `FAILED`, `NOT_RUN`, stale, 추적 `PARTIAL`·`GAP`인
  phase-blocking 통제는 fresh `PASSED` evidence 전 다음 Phase로 넘기지 않는다.
- gateway 우회 write, 무권한 action 실행, raw secret 기록, nonce/token 재사용,
  cross-tenant artifact 접근은 한 건만 있어도 즉시 security incident와
  release blocker다.
- severity downgrade와 risk closure는 fresh evidence 또는 변경된 threat
  premise, 대체 통제와 추적 갱신이 필요하며 calendar passage로 승인하지 않는다.

### 새 human authority가 필요한 gate

Cost, publication, new credentials, destructive action, scope expansion은
각각 **새 human authority**를 요구한다. 여기서 새 authority는 현재 관찰을
근거로 exact action·target·scope·effect와 제한을 명시한 직접 결정이다.
과거 승인, 다른 target의 승인, 사용자 침묵, risk score, 문서 Status 또는
portfolio gate는 재사용 가능한 포괄 권한이 아니다. human approval도
runtime capability나 TaskPacket authority를 만들지 않으며 현재 authority와의
교집합만 실행할 수 있다.

| Gate | 새 human authority에 포함할 최소 내용 | 승인 전 fail-closed 처리 |
| --- | --- | --- |
| Material cost | provider/service, billing 대상, exact 최대 금액·통화, 기간, 사용 목적과 중단 조건 | paid API·service·cloud resource 생성과 호출을 시작하지 않음 |
| Publication | exact artifact/version/hash, destination·audience, redacted payload, privacy·secret·license scan 결과 | upload, push, PR, message, 공개 링크 생성과 게시를 수행하지 않음 |
| New credential | provider, tenant/audience, 최소 scope, 주입 경계, expiry·retention·revocation 계획; secret 원문은 기록하지 않음 | credential 생성·요청·주입·전달과 이를 요구하는 action을 수행하지 않음 |
| Destructive action | exact resource와 operation, before-state, 비가역 영향, 대안, compensation/recovery plan, 별도 `destructive_actions=ALLOWED` 전제 | delete, overwrite, force, irreversible migration을 수행하지 않음 |
| Scope expansion | 추가 PRD/WBS 산출물, Phase·주차·person-day·buffer·의존성·VG 영향과 successor plan 여부 | 기존 buffer나 approval을 암묵적으로 전용하지 않고 현재 scope 밖 작업을 시작하지 않음 |

둘 이상의 gate가 한 action에 적용되면 각 gate를 모두 충족해야 한다. 예를
들어 paid external publication은 cost와 publication authority를 각각 요구하며,
credential이 추가되면 credential gate도 별도 충족한다. 새 authority가
관찰돼도 exact capability, approval binding, nonce, current revision,
preflight와 evidence 조건은 그대로 유지된다.

## 6. 관련 문서

- [ForgeOps 제품 요구사항 문서](../product/prd.md) — Phase 0~4 요구사항, scope, budget과 release-level Exit gate
- [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md) — ARC-002·009·010·013 contract, identity와 external-effect 경계
- [ForgeOps 위협 모델](../security/threat-model.md) — THR, CTL severity, phase-blocking 통제와 잔여 위험
- [ForgeOps 작업 분해 구조](wbs.md) — W1~W10 capacity, WBS-001~WBS-035, 의존성과 재계획 trigger
- [ForgeOps 검증 및 평가 계획](../quality/verification-and-evaluation-plan.md) — VG, evidence floor, Phase Exit와 public-safe gate
- [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md) — 문서 책임, ID, 위험 상태와 완료 기준
- [ForgeOps 제품 기초 문서 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md) — RSK-001~RSK-014 점수, response anchor와 검증 절차
- [저장소 기본 지시와 ForgeOps profile](../../AGENTS.md) — protected resource, human gate, 비용·게시·credential·파괴·scope 권한 경계
