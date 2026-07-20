# ForgeOps 시스템 아키텍처

**문서 상태:** 초안
**최종 검토일:** 2026-07-14
**대상 독자:** 1인 개발자, 포트폴리오 검토자
**문서 목적:** ForgeOps 구성요소, 상태·권한 소유권과 실행·증빙 계약의 기준 정의
**문서 범위:** 현재 Harness Foundation과 Phase 0~4 목표 제품 아키텍처
**현재 상태:** Harness Foundation과 Product Task Contract bridge는 IMPLEMENTED, 나머지 제품 계약은 SPECIFIED, 제품 runtime은 PLANNED
**기준 출처:** [ForgeOps 제품 요구사항 문서](../product/prd.md), [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md), [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md)
**관련 문서:** [13. 관련 문서](#13-관련-문서)

## 1. 목적과 범위

이 문서는 ForgeOps의 구성요소, 상태·권한 소유권, Task Contract bridge,
API·event·manifest·evidence 계약과 실행·검증·replay 데이터 흐름을 정의하는
아키텍처 기준 문서다. 제품이 제공해야 하는 결과는 PRD가, 구현 순서와
일정은 WBS가, 보안 통제와 검증 gate는 각각 위협 모델과 검증·평가 계획이
소유한다. 이 문서는 그 요구사항이 서로 다른 계층에서 어떤 책임과
경계를 갖는지를 규정하며 요구 의미나 Protocol 2.0 불변식을 재정의하지
않는다.

범위는 현재 저장소에 존재하는 Portable Harness Foundation과 Phase 0~4의
목표 제품 구조다. 제품 API, UI, database, queue, snapshot service,
sandbox provisioner, Tool Gateway, durable event store 및 외부 publisher는
아직 구현된 runtime으로 간주하지 않는다. 이 문서의 `SPECIFIED`는 계약이
정의됐다는 뜻이고 `PLANNED`는 후속 구현·검증 대상이라는 뜻이며, 어느
표시도 현재 실행 가능성이나 Phase Exit 통과를 주장하지 않는다.

## 2. 현재와 목표 경계

ForgeOps는 **Harness Foundation과 Phase 0 W1 bridge 완료** 상태다. 현재
구현은 Protocol 2.0 prompt·repository adapter/profile 및 Product Task Contract
schema·fixture 검증기에 한정된다. Work가 사용자에게 허용된 현재 project
workspace를 직접 변경할 수 있다는 사실은 제품의 immutable snapshot,
ephemeral workspace, containment, durable recovery 또는 rollback 보장이
아니다.

| 계층 또는 capability | 성숙도 | 이 문서에서 허용하는 주장 | 금지되는 확대 해석 |
| --- | --- | --- | --- |
| Portable Harness Foundation | IMPLEMENTED | Main·Part·Work와 adapter/profile의 prompt 계약 및 fixture가 저장소에 존재한다. | 제품 service, 격리 runtime 또는 durable persistence가 작동한다는 주장 |
| Product Task Contract bridge | IMPLEMENTED | versioned schema와 lossless/non-grant fixture가 fresh VG-002 E2를 통과했다. | bridge 통과를 제품 orchestration 또는 runtime 구현으로 표현 |
| 나머지 product contract layer | SPECIFIED | 제품 상태 mapping, API/event/manifest/replay 계약을 이 문서와 PRD가 정의한다. | 계약 정의를 runtime 구현이나 검증 통과로 표현 |
| Product runtime | PLANNED | Control Plane, Orchestration, Context Engine, Tool Gateway, workspace, verification/recovery/evaluation, artifact 및 publisher를 단계별로 구현한다. | 현재 API, queue, DB, sandbox, rollback, 외부 SCM write가 가능하다는 주장 |

현재와 목표 사이의 bridge는 제품 입력을 canonical TaskPacket으로
정규화하되 권한을 만들지 않고, Harness 결과를 제품 event와 manifest로
투영하되 canonical accepted state의 소유권을 빼앗지 않는다. 제품
`CANCELLED`처럼 현행 Protocol에 없는 의미는 다른 canonical terminal
state에 끼워 맞추지 않는다.

## 3. 시스템 컨텍스트

사용자와 리뷰어는 Control Plane에서 Contract, 상태, 위험, 승인 대상,
diff, 검증 결과와 허용된 다음 행동을 본다. Orchestration Engine은
Main 역할 경계에서 요청을 정규화하고 actor를 route하며, Context Engine,
Tool Gateway, workspace와 검증 계층을 조정한다. repository content,
Issue, log, tool description/output과 model output은 모두 비신뢰 data
plane 입력이고 control plane authority를 만들 수 없다.

외부 SCM에 write하는 유일한 경로는 approval-bound Publisher다. agent,
workspace 또는 일반 Tool Gateway action이 publisher를 우회해 push,
PR, issue, message, deploy 같은 외부 효과를 발생시켜서는 안 된다.

~~~mermaid
flowchart LR
    U["User / Reviewer<br/>PLANNED product interface"]
    CP["Control Plane<br/>ARC-003 · PLANNED"]
    OR["Orchestration Engine<br/>ARC-004 · PLANNED"]
    CE["Repository Context Engine<br/>ARC-005 · PLANNED"]
    TG["Tool Gateway / MCP<br/>ARC-006 · PLANNED"]
    WS["Ephemeral Workspace / Sandbox<br/>ARC-007 · PLANNED"]
    VRE["Verification / Recovery / Evaluation<br/>ARC-008 · PLANNED"]
    TA["Trace / Manifest / Artifact Store<br/>ARC-011~012 · SPECIFIED"]
    PUB["Approval-bound Publisher<br/>ARC-013 · SPECIFIED boundary"]
    SCM["External SCM / CI / Integrations"]
    HF["Main · Part · Work Harness Foundation<br/>ARC-001 · IMPLEMENTED"]

    U --> CP
    CP --> OR
    OR <--> HF
    OR --> CE
    OR --> TG
    TG --> WS
    OR --> VRE
    CE --> TA
    TG --> TA
    WS --> TA
    VRE --> TA
    OR --> TA
    CP -->|"new exact approval capability"| PUB
    OR -->|"approved external-effect candidate"| PUB
    PUB -->|"only external write path"| SCM
    SCM -->|"untrusted input / observed remote state"| TG
~~~

## 4. 논리적 구성요소

아키텍처 catalog의 성숙도는 `IMPLEMENTED`, `SPECIFIED`, `PLANNED`의 closed
set을 사용한다. `IMPLEMENTED`는 실제 prompt 파일이 확인되는 ARC-001과
fresh fixture로 검증된 bridge 범위의 ARC-002·ARC-010에 적용한다. 나머지는 제품 runtime 구현을 주장하지 않으며 각 PRD 연결은
요구사항의 소유권을 복제하지 않는 추적 link다.

| ID | Maturity | Responsibility | Dependencies | Related requirements |
| --- | --- | --- | --- | --- |
| ARC-001 | IMPLEMENTED | Portable Harness Foundation: [Main](../../.github/agents/main_instruction.prompt.md), [Part](../../.github/agents/part_agent.prompt.md), [Work](../../.github/agents/work_agent.prompt.md)와 repository [adapter/profile](../../AGENTS.md) 경계 | 현재 저장소 prompt, adapter, fixture | PRD-NFR-001, PRD-NFR-002, PRD-NFR-009 |
| ARC-002 | IMPLEMENTED | Product layer와 Protocol 2.0 사이의 비약 없는 bridge 경계; 제품 계약이 canonical 의미를 약화하거나 암묵 확장하지 못하게 한다. | ARC-001, versioned bridge schema와 VG-002 fixture | PRD-FR-001, PRD-FR-002, PRD-NFR-009 |
| ARC-003 | PLANNED | Control Plane: task, approval, budget, RBAC, queue와 사용자 가시성 책임 | ARC-002, ARC-012, ARC-013 | PRD-FR-006, PRD-FR-013, PRD-FR-019, PRD-NFR-008, PRD-NFR-011 |
| ARC-004 | PLANNED | Orchestration Engine: normalize, route, state proposal 조정과 MainDecision 제출 책임 | ARC-001, ARC-002, ARC-003, ARC-010 | PRD-FR-001, PRD-FR-010, PRD-FR-013 |
| ARC-005 | PLANNED | Repository Context Engine: immutable snapshot index, retrieval, source-attributed Context Pack 책임 | ARC-007, snapshot provider | PRD-FR-008, PRD-FR-009, PRD-NFR-004 |
| ARC-006 | PLANNED | Tool Gateway와 MCP: catalog, exact policy, short-lived credential, action 효과 분해와 output 제한 책임 | ARC-003, ARC-007, ARC-013 | PRD-FR-020, PRD-NFR-002, PRD-NFR-004, PRD-NFR-012 |
| ARC-007 | PLANNED | Ephemeral Workspace와 sandbox: immutable source 분리, containment, quota, egress, cleanup 책임 | snapshot provider, sandbox provisioner, ARC-006 | PRD-FR-007, PRD-FR-011, PRD-NFR-003, PRD-NFR-005 |
| ARC-008 | PLANNED | Verification, Recovery, Evaluation Engine: trusted verification, failure 분류, bounded repair, deterministic gate와 평가 책임 | ARC-005, ARC-007, ARC-011 | PRD-FR-012, PRD-FR-014, PRD-FR-015, PRD-FR-016, PRD-FR-017, PRD-NFR-001, PRD-NFR-010 |
| ARC-009 | SPECIFIED | Product workflow state와 canonical accepted state의 명시적 mapping 및 `CANCELLED` gap 계약 | ARC-001, ARC-002, versioned state schema | PRD-FR-002, PRD-FR-013, PRD-NFR-005, PRD-NFR-006 |
| ARC-010 | IMPLEMENTED | Product Task Contract와 TaskPacket 사이의 lossless/non-grant bridge 계약과 검증기 | ARC-001, ARC-002, VG-002 fixture | PRD-FR-001, PRD-FR-003, PRD-NFR-002, PRD-NFR-009 |
| ARC-011 | SPECIFIED | Durable event, run manifest, evidence와 artifact provenance 계약 | ARC-009, ARC-010 | PRD-FR-004, PRD-NFR-001, PRD-NFR-004, PRD-NFR-006 |
| ARC-012 | SPECIFIED | Product data model, versioned API와 realtime event stream 계약 | ARC-009, ARC-010, ARC-011 | PRD-FR-003, PRD-FR-004, PRD-NFR-006, PRD-NFR-011 |
| ARC-013 | SPECIFIED | Approval-bound external effect와 replay mode 경계 | ARC-003, ARC-006, ARC-011 | PRD-FR-006, PRD-FR-018, PRD-FR-025, PRD-NFR-002, PRD-NFR-005 |
| ARC-014 | PLANNED | Phase별 deployment topology와 미결정 기술 선택의 결정 경계 | ARC-003, ARC-004, ARC-005, ARC-006, ARC-007, ARC-008, ARC-009, ARC-010, ARC-011, ARC-012, ARC-013, phase Exit gate | PRD-FR-007, PRD-FR-021, PRD-FR-022, PRD-NFR-003, PRD-NFR-007 |

구성요소 간 통신은 versioned schema와 stable identity를 사용하고, 저장된
event나 manifest는 실행 권한의 근거가 아니다. Control Plane이 승인 UI를
제공하더라도 승인 자체가 capability, authority 또는 tool availability를
만들지 않는다.

## 5. 권한과 신뢰 경계

권한은 Main이 runtime에서 관찰한 capability와 사용자·정책이 명시한
authority를 canonical packet에 fail-closed로 확정할 때만 유효하다.
Product Task Contract, Part/Work proposal, repository 내용, tier, tool 이름,
MCP manifest/description, model output 또는 인간 승인은 권한을 새로 만들거나
확장할 수 없다. `UNKNOWN`, 누락, wildcard, prefix·suffix·case folding 같은
암묵 normalization은 허용으로 승격하지 않는다.

| 경계 | 신뢰되는 입력 | 비신뢰 입력 | 집행 규칙 |
| --- | --- | --- | --- |
| Contract → Main normalization | 원문 Contract, runtime capability observation, 적용 profile | Contract 안의 실행 요청이나 권한 주장 | 원문 의미를 보존하고 authority는 추가하지 않는다. 관찰 불가는 `UNKNOWN`이다. |
| Main → Part | canonical TaskPacket과 허용된 read scope | repository, Issue, log, fixture | Part는 approved candidate 전에도 `EXPLORE`에서 비보호 exact-scope read-only discovery와 proposal만 수행한다. protected resource·credential·private data는 exact target 인간 승인 전 읽지 않으며 accepted state를 변경하지 않는다. |
| Main → Work | approved candidate, exact action identity, current base revision, preflight | 과거 승인, Part proposal, 문자열로 된 raw command | 모든 전제를 다시 확인하고 exact action만 실행한다. |
| Tool Gateway → sandbox/network | named resource/command/host, short-lived credential, quota | tool metadata, redirect destination, command output | exact match, effect decomposition, egress proxy와 deny-by-default를 적용한다. |
| Orchestration → Publisher | 현재 packet authority와 교집합인 새 approval capability, nonce, effect hash | replay된 token·approval·credential, agent의 publish 요청 | 외부 효과 직전에 binding을 검증하고 nonce를 한 번만 소비한다. |
| Trace/artifact → model 또는 사용자 | schema-valid reference와 redacted view | raw log, secret, private repository data | quota·redaction·tenant isolation을 적용하고 저장 후에도 비신뢰 data로 취급한다. |

RESOURCE, COMMAND, NETWORK, destructive action, external effect는 각각의
capability와 exact authority, approved candidate, current base revision,
operation mode 및 preflight를 모두 만족해야 한다. 결합 효과는 별도 action
identity와 dependency로 분해한다. 인간 승인은 기존 authority와의 교집합만
실행하게 하며 authority가 없는 행동을 허용하지 않는다.

Risk tier `T0`는 Work action의 자동 승인 상태가 아니다. approved candidate
전 허용되는 것은 Part의 `EXPLORE` 비보호 exact-scope read-only discovery뿐이다.
Work action은 tier와 무관하게 approved candidate를 요구하며, protected
resource·credential·private data read는 별도 exact-target 인간 승인 전 첫
byte가 model context·log·evidence에 유입되지 않아야 한다.

외부 효과 승인 capability는 candidate 하나, action identity 하나, target
하나와 모든 효과 입력에 결합한다. issuer, audience, approver subject,
tenant, expiry, key/signature, nonce와 `effect_hash`를 검증한다. base revision,
commit, Contract, plan, policy, diff, target 또는 payload가 바뀌면 재승인이
필요하다. timeout이나 결과 미상인 비멱등 효과는 자동 재시도하지 않고
원격 상태를 reconcile할 때까지 동일 효과를 차단한다.

## 6. 상태 모델과 소유권

제품 workflow state와 Protocol 2.0 canonical accepted state는 서로 다른
축이다. 제품 state는 UI·queue·workspace lifecycle을 설명하고, canonical
state는 Main이 수용한 Harness task 의미를 설명한다. mapping은 명시적인
bridge 결과이며 문자열 이름의 유사성으로 전이를 추론하지 않는다.

[WBS state](../project/wbs.md)는 `WBS_NOT_STARTED`, `WBS_IN_PROGRESS`,
`WBS_BLOCKED`, `WBS_DONE`을 사용하는 세 번째 독립 축이며 프로젝트 관리
전용이다. WBS state는 product workflow state나 Protocol canonical accepted
state로 직렬화·변환·해석하지 않는다. WBS 문서와 프로젝트 운영만 이 상태를
소유하며 `MainDecision`의 runtime state나 evidence result를 바꾸지 않는다.

| Product workflow state | Protocol 2.0 canonical accepted state 후보 | 소유자와 규칙 |
| --- | --- | --- |
| `CREATED` | `PENDING` | 제품 생성 event는 mapping 입력일 뿐이며 MainDecision 수용 전에는 canonical 확정이 아니다. |
| `TRIAGING`, `SNAPSHOTTING`, `BASELINING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `RECOVERING`, `EVALUATING` | `IN_PROGRESS` | specialist와 runtime은 observation 또는 proposal만 emit한다. |
| `AWAITING_CLARIFICATION`, `AWAITING_PLAN_APPROVAL`, `AWAITING_REPAIR_APPROVAL`, `REVIEW_REQUIRED` | `WAITING_FOR_HUMAN` | 구체적인 사람 결정과 재개 조건을 기록해야 한다. |
| `PARTIAL_RESULT` | 조건부 `PARTIAL` | 관찰된 부분 산출물과 구체적이고 승인된 continuation이 모두 있을 때만 허용한다. |
| `COMPLETED_VERIFIED` | 조건부 `SUCCEEDED` | 모든 필수 criterion이 fresh evidence floor에서 `PASSED`일 때만 허용한다. |
| `POLICY_BLOCKED`, `BASELINE_UNHEALTHY` | 조건부 `BLOCKED` | 새 authority·capability·사람 결정 없이는 진행할 수 없을 때만 허용한다. |
| `FAILED`, `REJECTED` | 조건부 `FAILED` | 실행 또는 검증을 시도했으나 기준을 충족하지 못한 경우다. |
| `BUDGET_EXCEEDED` | `FAILED` 또는 `BLOCKED` | 이미 시도한 실행·검증 실패면 `FAILED`, 새 authority·capability·사람 결정이 필요하면 `BLOCKED`다. |
| `CANCELLED` | **mapping 없음** | 제품 계층 terminal 결과와 `USER_CANCELLED` reason으로만 보존한다. versioned Protocol 변경 전에는 `FAILED`·`BLOCKED` 등으로 강제 변환하거나 Harness accepted state에 통합하지 않는다. |

`MainDecision`만 accepted `state`, `revision`, 단조 증가 `seq`를 확정한다.
Part와 Work는 `proposed_transition`, observation, candidate와 evidence를
emit할 뿐이다. Main은 current revision과 expected next sequence를 검증하고
한 번의 decision에서 revision과 sequence를 함께 전진시킨다. stale base,
out-of-order event, actor에게 허용되지 않은 transition 또는 증빙 부족은
거부한다.

~~~mermaid
flowchart LR
    CREATED["CREATED<br/>PLANNED product state"]
    ACTIVE["TRIAGING · SNAPSHOTTING · BASELINING · PLANNING<br/>EXECUTING · VERIFYING · RECOVERING · EVALUATING<br/>PLANNED product states"]
    WAIT["AWAITING_* · REVIEW_REQUIRED<br/>PLANNED product states"]
    TERMINAL["PARTIAL_RESULT · COMPLETED_VERIFIED<br/>POLICY_BLOCKED · BASELINE_UNHEALTHY<br/>FAILED · REJECTED · BUDGET_EXCEEDED<br/>PLANNED product states"]
    PART["Part proposal<br/>IMPLEMENTED role contract"]
    WORK["Work proposal + evidence<br/>IMPLEMENTED role contract"]
    MD["Explicit mapping validation + MainDecision<br/>only owner of accepted state + revision + event seq<br/>IMPLEMENTED Harness boundary"]
    CAN["PENDING · IN_PROGRESS · WAITING_FOR_HUMAN<br/>PARTIAL · SUCCEEDED · FAILED · BLOCKED<br/>Protocol 2.0 canonical accepted states"]
    CXL["Product CANCELLED<br/>product-only; no current Protocol mapping"]
    VCHG["Future versioned Protocol change<br/>PLANNED; integration blocked until approved"]

    CREATED -->|"candidate PENDING"| MD
    ACTIVE -->|"candidate IN_PROGRESS"| MD
    WAIT -->|"candidate WAITING_FOR_HUMAN"| MD
    TERMINAL -->|"conditional terminal candidate"| MD
    PART -->|"proposed_transition only"| MD
    WORK -->|"proposed_transition + observation only"| MD
    MD -->|"accepted transition"| CAN
    CXL -. "must not coerce" .-> CAN
    CXL -->|"only after explicit version upgrade"| VCHG
    VCHG -.-> CAN
~~~

제품 취소 요청은 새 action dispatch를 중단하고 workspace cleanup을
trigger하며 제품 event·manifest에 취소 사유와 cleanup 결과를 남긴다.
이미 발생했는지 불명확한 외부 효과는 취소만으로 미발생 처리하지 않고
reconciliation 대상으로 남긴다. 현행 Harness 결과가 필요하면 취소 이전의
마지막 유효 `MainDecision`을 그대로 보존하며 `CANCELLED`로 덮어쓰지 않는다.

## 7. 핵심 실행 흐름

핵심 local vertical slice는 Main normalize/route → Part context/plan → Main
candidate decision → Work preflight/execute/verify → Main evidence validation과
accepted state 순서다. 각 역할 호출은 같은 packet을 임의로 수정하는 것이
아니라 input revision을 소비하고 proposal 또는 decision을 반환한다.

~~~mermaid
sequenceDiagram
    autonumber
    actor User
    participant Main as Main / Orchestration<br/>IMPLEMENTED role · PLANNED service
    participant Part as Part Analyst<br/>IMPLEMENTED role
    participant Context as Context Engine<br/>PLANNED
    participant Work as Work Executor<br/>IMPLEMENTED role
    participant Sandbox as Workspace / Gateway<br/>PLANNED
    participant Verify as Verification Engine<br/>PLANNED

    User->>Main: Product Task Contract
    Main->>Main: normalize to TaskPacket; observe capabilities; route
    Main->>Part: canonical packet + exact read scope
    Part->>Context: request source-attributed Context Pack
    Context-->>Part: snapshot-bound paths, hashes, selection reasons
    Part-->>Main: plan + candidates + proposed transition
    Main->>Main: validate base revision; select candidate; MainDecision
    Main->>Work: approved exact candidate + current revision
    Work->>Work: preflight authority, capability, ownership, protected resources
    Work->>Sandbox: execute only approved exact actions
    Sandbox-->>Work: observations, diff, action result
    Work->>Verify: trusted verification_profile_id + exact command_id
    Verify-->>Work: fresh evidence + criterion result
    Work-->>Main: execution proposal + evidence catalog
    Main->>Main: validate evidence floor/freshness and transition
    Main-->>User: accepted state + revision + seq + allowed next actions
~~~

Main은 작업을 실행하지 않고 orchestration decision을 소유한다. Part는
repository-grounded discovery와 후보를 생성하되 mutation이나 최종 수용을
하지 않는다. Work는 승인된 exact action만 preflight 후 수행하고 자신의
성공 서술로 완료를 확정하지 않는다. Verification Engine은 trusted profile의
exact command와 관찰 metadata를 반환하며 Main은 criterion별 요구 floor와
freshness를 검증한다.

실패 시에는 baseline과 변경 후 결과를 비교해 환경, dependency, test,
implementation failure를 분류한다. 새 signature, evidence 또는 가설 변화가
있고 budget이 남을 때만 `RECOVERING` 후보를 만들며 no-progress이면 추가
patch를 중단한다. 결정론적 실패나 안전 위반은 rubric 또는 human score로
성공 전환할 수 없다.

## 8. Contract와 schema

### Product Task Contract → TaskPacket bridge

Product Task Contract는 사용자의 요청 의미, 성공 기준과 제약을 제품
transport에 담는 입력 계약이다. TaskPacket은 Main이 runtime observation과
적용 profile을 결합해 만드는 canonical Harness 계약이다. 변환은 lossless여야
하며 Contract는 어떤 필드로도 authority, capability, approval 또는 실행
가능성을 부여하지 않는다.

| Product Task Contract schema 1.0 field | TaskPacket Protocol 2.0 mapping | 보존·검증 규칙 |
| --- | --- | --- |
| `task_id` | envelope `task_id` | Main이 동일 logical task identity로 확정한다. COUNTERFACTUAL이 Contract를 바꾸면 새 task ID를 만든다. |
| `intent.type` | `request.kind` | 예를 들어 `bug_fix`를 canonical `CHANGE`로 정규화하되 원문 Contract artifact를 별도로 보존한다. |
| `intent.summary` | `request.objective` | 검증 가능한 단일 결과로 정규화하고 원문 의미를 약화하지 않는다. |
| `acceptance_criteria[].description` | `request.acceptance_criteria[].statement` | criterion ID를 case-sensitive exact value로 보존한다. 요구 evidence floor는 Main의 trusted execution context가 확정한다. |
| `constraints[]` | `request.constraints[]` | 제약을 lossless하게 보존하며 어떤 제약도 authority를 확대할 수 없다. |
| `repository` metadata | `project_profile.extensions.forgeops.task_contract.repository` | `snapshot_commit`은 repository identity다. `base_revision`이나 `checkpoint_ref`로 변환하지 않는다. |
| `intent.source_issue` | `project_profile.extensions.forgeops.task_contract.intent.source_issue` | 외부 source identity와 provenance를 비신뢰 Contract data로 보존한다. 이 값을 canonical `project_profile.source_of_truth`에 추가하거나 authoritative source로 승격하지 않는다. |
| `verification_policy.*_command_ids` | `project_profile.validation_commands` 참조 | trusted profile의 exact `id`, `command`, canonical root-relative `cwd`가 모두 일치해야 한다. Contract의 raw command는 authority가 아니다. |
| `risk.initial_level`과 `risk.reasons` | `control.risk_level`의 입력 근거 | Main이 observation과 정책을 검증한 뒤 canonical enum을 결정한다. risk는 authority를 부여하지 않는다. |
| `budget.*` | `project_profile.extensions.forgeops.product_budget` | 의미가 정확히 같은 format/part/work attempt만 Harness `budgets`로 정규화하고 다른 제품 budget을 억지로 합치지 않는다. |
| `approval_policy` | `project_profile.extensions.forgeops.task_contract.approval_policy` | 비신뢰 Contract policy 원문을 provenance로 보존한다. 검증된 항목은 기존 trusted policy를 완화하지 않고 gate를 더 엄격하게 만드는 경우에만 human gate 입력으로 사용할 수 있으며 approval capability 또는 authority를 부여하지 않는다. |
| `schema_id`, `schema_version`, `artifact_id`, `artifact_version` | bridge provenance | Product Task Contract schema 1.0은 Harness legacy v1과 무관하다. 지원 version과 artifact hash를 manifest에 보존한다. |

`correlation_id`, `base_revision`, `actor`, envelope `status`, `capabilities`,
`authority`, `control.route`, `control.evidence_floor`와 Harness attempt budget은
Product Task Contract에서 가져오지 않는다. Main과 실제 runtime observation이
이를 정규화하며 안전 관련 값을 관찰하지 못하면 `UNKNOWN`으로 fail-closed한다.
Canonical `project_profile.source_of_truth`와 `project_profile.risk_rules`도
적용되는 trusted instruction과 project profile만으로 구성한다. Contract의
`source_issue` 또는 `approval_policy`를 이 두 배열에 복사·병합하지 않는다.
Contract policy를 human gate 판단에 반영하려면 schema와 issuer를 검증한 뒤
기존 gate를 추가하거나 강화하는 단조 강화만 허용하며, trusted rule의 삭제,
완화, 우회 또는 기존 deny의 allow 전환은 거부한다.

기존 핸드오프의 `source_issue` mapping과 이 경계의 차이는 알려진 contract
drift이며 [RSK-002](../project/risk-register.md#5-위험-카탈로그)에서 W2
동기화 결정까지 추적한다. 이 기록은 핸드오프 문구를 canonical authority로
승격하거나 현재 Protocol 의미를 변경하지 않는다.

### Versioned API와 closed schema

API request/response, event wrapper와 run manifest는 `schema_version`을
필수로 갖고 unknown, missing, wrong-type field를 결정론적으로 거부한다.
schema 변경은 backward-compatibility와 migration 결과를 기록하며, state,
authority, evidence 의미를 바꾸는 변경은 명시적 Protocol version block을
거친다. raw request payload는 secret·private data 정책을 통과한 경우에만
별도 artifact reference로 보존하고 event에 복제하지 않는다.

| 계약 | 필수 identity·ordering·provenance field |
| --- | --- |
| API command/request | `schema_version`, `task_id`, `run_id`, `correlation_id`, `base_revision`, `idempotency_key`, actor/tenant, requested action reference |
| Durable event wrapper | `schema_version`, `event_id`, `event_type`, `task_id`, `run_id`, `stream_seq`, `state_revision`, proposal의 `base_revision`, source component, payload reference, `recorded_at`; embedded `harness_event`에는 `correlation_id`와 Main 소유 `seq` |
| Run manifest | `schema_version`, `manifest_id`, `task_id`, `run_id`, `correlation_id`, start/final revision, final event sequence, source snapshot, Contract hash, policy/profile version, artifact/evidence references, terminal/cleanup result |
| Replay lineage | `source_task_id`, `source_run_id`, `source_manifest_id`, replay mode, new `run_id`, new `correlation_id`, new event sequence |
| Artifact reference | `artifact_ref`, producer `task_id`/`run_id`, media type, content hash/checksum, provenance와 redaction metadata |
| Product durable evidence wrapper | `schema_version`, `durable_evidence_id`, `task_id`, `run_id`, `correlation_id`, `base_revision`, producer actor, canonical evidence의 `id`를 exact 참조하는 `harness_evidence_ref`, content/result hash와 provenance |

API의 `base_revision` 또는 `expected_revision`은 optimistic concurrency와
stale command 방지에 쓴다. product `stream_seq`는 task stream의 durable
ordering이고, embedded Harness event의 `seq`는 Main이 부여한 canonical
event ordering이다. broker delivery offset, database row version과 이 두
sequence를 서로 혼용하지 않는다. `recorded_at`은 Control Plane 저장 시각이며
evidence `observed_at`을 대체하지 않는다. idempotency key는 중복 request를
식별하지만 외부 효과 승인 nonce나 exact authority를 대체하지 않는다.

## 9. 데이터·event·evidence 흐름

source와 profile은 신뢰 수준이 서로 다르다. repository source는 identity와
hash를 고정해도 내용 자체는 비신뢰이며, verification profile은 운영자나
신뢰된 project profile loader가 등록한 exact record여야 한다. action의
output은 observation이고, evidence는 closed type과 freshness metadata를
검증한 observation reference다. evidence가 acceptance criterion에 연결된
후에도 최종 수용은 `MainDecision`만 수행한다.

~~~mermaid
flowchart LR
    SRC["Snapshot-bound source<br/>identity trusted; content untrusted"]
    PROF["Trusted project / verification profile<br/>exact command records"]
    ACT["Approved exact action<br/>Work / Gateway"]
    OBS["Observation<br/>result · diff · output metadata"]
    EC["Canonical Harness evidence catalog<br/>closed fields + freshness"]
    DEW["Product durable evidence wrapper<br/>harness_evidence_ref → Protocol id"]
    CRIT["Acceptance criterion<br/>required evidence floor"]
    MD["MainDecision<br/>state + revision + seq owner"]
    MAN["Durable manifest / trace<br/>SPECIFIED contract"]

    SRC --> ACT
    PROF --> ACT
    ACT --> OBS
    OBS --> EC
    SRC -->|"snapshot / path / hash provenance"| EC
    PROF -->|"profile_id / command_id provenance"| EC
    EC --> CRIT
    CRIT --> MD
    MD --> MAN
    EC --> DEW
    DEW --> MAN
~~~

### Canonical Harness evidence

Protocol packet 안의 evidence는 다음 closed object다. 필드 이름은 원문
대소문자를 포함해 exact하게 검증하며, 아래 필수·조건부 필드 외의
`evidence_id`, `task_id`, `run_id`, producer, hash, provenance, criterion
reference 같은 product wrapper 필드를 canonical evidence object에 넣지
않는다. unknown field는 보존용 확장으로 해석하지 않고 contract 오류로
거부한다.

| Canonical field | 조건 | 규칙 |
| --- | --- | --- |
| `id` | 필수 | packet evidence catalog 안에서 non-empty, ordinal-unique한 Protocol evidence identity |
| `tier` | 필수 | `E0`, `E1`, `E2`, `E3`의 closed enum이며 authority를 부여하지 않는다. |
| `type` | 필수 | `file`, `diff`, `command`, `test`, `render`, `runtime`, `approval`의 closed enum |
| `source` | 필수 | project-root-relative path 또는 안전한 tool/command identity |
| `observation` | 필수 | secret과 oversized raw log를 제외한 간결한 관찰 결과 |
| `exit_code` | 선택 | 적용 가능한 command 관찰에만 사용하며 실행하지 않은 결과를 만들지 않는다. |
| `observed_revision` | `file`·`diff`에 필수 | 원본 JSON 정수이고 현재 `base_revision`과 exact 일치해야 하며 `observed_at`은 금지한다. |
| `observed_at` | `command`·`test`·`render`·`runtime`·`approval`에 필수 | runtime 공급 strict UTC 값이고 `observed_revision`은 금지한다. trusted `validationAt` 기준 0~300초만 fresh다. |

Contract·metadata observation을 새 evidence type으로 만들지 않고 현재
Protocol에서는 `file`과 canonical source path로 표현한다. evidence tier가
높아도 stale, wrong-source 또는 criterion에 불충분한 evidence를 보완하지
못한다. envelope와 trusted execution context의 `task_id`, `correlation_id`,
`base_revision`은 evidence object에 복제하지 않는다.

### Product durable evidence wrapper

제품 persistence는 canonical evidence object를 변형하지 않고 별도의
versioned wrapper로 저장한다. wrapper의 `harness_evidence_ref`는 같은
packet catalog에 존재하는 Protocol evidence `id`를 case-sensitive exact
value로 참조하며, dangling·duplicate·normalized reference를 거부한다.

| Durable wrapper field | 규칙 |
| --- | --- |
| `schema_version`, `durable_evidence_id` | 제품 wrapper version과 durable identity이며 Protocol `id`를 대체하지 않는다. |
| `task_id`, `run_id`, `correlation_id`, `base_revision`, producer actor | 제품 실행 lineage다. canonical packet/envelope와 대조하지만 evidence object 안에 주입하지 않는다. |
| `harness_evidence_ref` | canonical evidence의 `id`를 exact 참조한다. `evidence_id` alias, case folding, trimming 또는 prefix/suffix matching은 금지한다. |
| content/result hash, provenance, artifact reference, criterion reference | 제품 감사·추적 metadata다. wrapper에만 두고 canonical evidence의 closed schema를 확장하지 않는다. |

raw log와 secret은 어느 계층의 payload에도 넣지 않고 redacted bounded
artifact reference만 사용한다. wrapper의 hash와 provenance는 무결성과
추적 근거일 뿐 authority, approval, freshness 또는 acceptance를 만들지
않는다.

manifest와 trace는 실행을 재구성하는 durable record다. 이들은 accepted
decision, proposal, action, approval, observation, evidence, artifact와
cleanup을 link하지만 저장된 record 자체는 새 실행 권한이 아니다.
tamper-evident hash와 provenance를 보존하고 reference가 해석되지 않으면
manifest completeness를 통과시키지 않는다.

## 10. Snapshot·sandbox·verification

### Snapshot과 revision identity

repository snapshot identity, Git commit SHA, conversation/task revision은
서로 다른 값이다. `snapshot_id`는 retrieval, baseline, workspace clone과
artifact가 동일 source image를 사용했음을 나타낸다. Git SHA는 repository
content identity의 일부이고, dirty state가 있으면 별도 content manifest와
hash가 필요하다. 둘 다 task state의 `revision` 또는 event `seq`가 아니며,
snapshot provider의 restore 결과와 fresh evidence 없이는 rollback 증명이
되지 않는다.

| Identity | 의미 | 대체할 수 없는 것 |
| --- | --- | --- |
| `snapshot_id` + content manifest hash | 한 run이 읽고 복제한 immutable repository source | task revision, approval binding, rollback 성공 |
| Git commit SHA | version-control object identity | dirty worktree 전체, conversation identity, task revision |
| `task_id` / Contract hash | logical request identity와 입력 계약 | source snapshot, run attempt |
| `run_id` / `correlation_id` | 실행 attempt와 분산 trace identity | 원본 task identity, accepted ordering |
| accepted `revision` / Harness event `seq` / product `stream_seq` | MainDecision이 확정한 task state version·canonical event ordering과 product durable stream ordering | Git commit, broker offset, database sequence |

### Sandbox lifecycle

목표 runtime은 immutable digest와 provenance가 검증된 image에서 task별
workspace를 만들고 원본 repository를 write하지 않는다. rootless 또는
non-root, read-only root filesystem, bounded writable workspace/tmp, quota,
capability drop, no-new-privileges, syscall/mandatory access control과 host
namespace·device·socket 차단을 적용한다. 직접 socket/DNS를 허용하지 않고
exact host·port를 검사하는 task egress proxy만 사용한다. terminal 또는
cancel 후 process tree, mount, lease, transient secret과 workspace가 0인지
검증한다.

Docker, stronger isolation(gVisor·Kata·microVM·dedicated worker) 중 무엇을
쓸지는 threat와 단계별 gate를 근거로 결정한다. 외부 또는 악성 가능성이
있는 repository에 Docker만으로 충분하다고 미리 주장하지 않는다. 현행
workspace-write Harness 실행도 이 PLANNED sandbox 보장을 충족한다고
표현하지 않는다.

### Verification과 recovery

baseline과 변경 후 task-specific·regression check는 동일 `snapshot_id`,
Contract, policy와 trusted verification profile에 연결한다. COMMAND는
profile의 `id`, `command`, project-root-relative `cwd`가 case-sensitive
exact match하고 named command authority가 있을 때만 Work가 실행한다.
계획 문서의 raw command나 model이 만든 command는 trust 또는 실행 권한의
근거가 아니다.

verification 결과는 criterion별 `PASSED`, `FAILED`, `NOT_RUN`과 실제
evidence tier/reference를 분리한다. 필수 deterministic check 실패,
baseline unhealthy, inconclusive, freshness 또는 provenance 부족은 성공으로
수용하지 않는다. bounded recovery는 failure signature, 이전 attempt,
diff와 새 evidence를 묶어 별도 candidate로 제안하며 action·command·repair
budget과 no-progress stop을 지킨다. rollback은 provider의 restore action과
복원 후 fresh verification evidence가 모두 있을 때만 성공으로 기록한다.

## 11. Replay와 외부 통합

제품 replay mode는 `AUDIT_REPLAY`, `REEXECUTE`, `COUNTERFACTUAL`의 closed
enum이다. 모든 replay는 원본 lineage를 보존하면서 새 `run_id`,
`correlation_id`, revision sequence와 fresh evidence namespace를 사용한다.
기존 approval, nonce, credential, authority, publisher token을 복사하지
않고 원본 run의 evidence와 새 run evidence를 섞지 않는다.

| Product replay mode | Harness mapping | Task identity | External effect policy | 필수 규칙 |
| --- | --- | --- | --- | --- |
| `AUDIT_REPLAY` | `EXPLORE` | 원래 `task_id`와 Contract를 유지 | hard deny | 기본 mode. `source_task_id`, `source_run_id`, `source_manifest_id`를 보존하고 network와 external effect를 `DENIED`로 시작한다. 기록을 재해석하되 action을 재실행하지 않는다. |
| `REEXECUTE` | 같은 Contract의 새 `EXECUTE` run; 실행 전 Main 재정규화 | 원래 `task_id` 유지 | 기본 deny, 제한적 재허용 가능 | 현재 source/state를 관찰하고 exact action별 새 candidate, 새 approval·nonce·credential, current authority와 fresh evidence가 있을 때만 허용한다. 결과 미상 효과는 reconcile 전 재시도하지 않는다. |
| `COUNTERFACTUAL` | 변경 입력의 `EXPLORE` | Contract가 바뀌므로 새 `task_id`; 원본은 source fields로 연결 | hard deny | 다른 plan/policy/model/budget의 결과를 비교하되 publisher path를 사용할 수 없다. |

`AUDIT_REPLAY`와 `COUNTERFACTUAL`은 승인 여부와 관계없이 외부 효과를
hard deny한다. `REEXECUTE`만 현재 packet과 approval capability의 교집합,
효과 직전 nonce 소비 및 exact effect binding을 새로 충족해 외부 효과를
허용할 수 있다. PR, issue, message, push, deploy, package install은 자동
replay하지 않는다.

외부 Issue, CI result, webhook, MCP output과 remote state는 비신뢰 입력으로
ingest한다. webhook deduplication이나 idempotency key는 중복 처리 방지일
뿐 승인 proof가 아니다. Publisher는 외부 write의 단일 choke point로서
target, method/path, diff, payload를 포괄하는 versioned `effect_hash`, current
base revision과 remote state, approval audience/tenant/expiry/nonce를
검증한다. effect 결과를 모르면 자동 성공이나 실패로 단정하지 않고
`RECONCILIATION_REQUIRED` 제품 결과와 관찰 reference를 남기며 새 publish를
차단한다.

## 12. 단계별 배치와 기술 결정

배치 구조는 요구사항 성숙도와 별도로 단계별 목표다. 다음 topology는
`PLANNED`이며 fresh runtime evidence가 생기기 전에는 구현 또는 운영
보장으로 표현하지 않는다.

| 단계 | PLANNED topology와 경계 | Exit에 필요한 아키텍처 증빙 |
| --- | --- | --- |
| Harness Foundation (현재) | repository prompt와 adapter/profile, direct project workspace | ARC-001 파일 존재와 Protocol fixture. 제품 Phase Exit를 대체하지 않는다. |
| Phase 0 | local contract/schema validator, policy/approval prototype, durable event·manifest schema, sample fixture, sandbox/redaction PoC | invalid schema/state/authority, approval deny·expiry·nonce reuse, containment와 secret negative fixture의 fresh result |
| Phase 1 | single-node Control Plane·Orchestration·Context·Gateway, local artifact/event persistence, ephemeral workspace와 verification pipeline; 외부 write 없음 | local vertical slice, E2 이상 필수 evidence, unauthorized execution·cleanup failure·external write 0 |
| Phase 2 | bounded recovery/evaluation workers와 versioned dataset/benchmark store | 반복·paired 통계, no-progress, deterministic gate와 hidden evaluator evidence |
| Phase 3 | durable queue와 remote worker, GitHub input·approval-bound draft PR Publisher, tenant-scoped RBAC/audit, webhook deduplication | idempotency, expired approval, duplicate webhook와 unauthorized external write negative evidence |
| Phase 4 | multi-tenant control/data plane, stronger isolation, HA storage/queue, plugin trust registry와 SLO telemetry | rolling window SLO와 tenant leakage·sandbox escape·secret·nonce zero-event invariant evidence |

기술 선택은 이 문서 안의 decision record로만 관리하다가 사용자가 승인한
별도 ADR workflow가 생긴 뒤 이관한다. 현재는 다음 선택지를 동시에
default로 확정하지 않는다.

| 결정 주제 | 후보군 | 선택 기준 | 결정 경계 |
| --- | --- | --- | --- |
| Workflow/queue | in-process 또는 DB-backed queue, Celery 계열, Temporal 계열 | crash recovery, idempotency, local 운영 복잡도, 관찰 가능성, 비용 | Phase 0 contract fixture 후, Phase 1 topology 확정 전. Temporal과 Celery를 동시 기본값으로 선택하지 않는다. |
| Artifact/object storage | local content-addressed store, S3-compatible API, managed S3 | provenance·checksum, retention, tenant isolation, backup, 1인 운영 비용 | Phase 1 local evidence 요구부터 단계적으로 결정. S3와 MinIO를 동시 기본값으로 선택하지 않는다. |
| Sandbox isolation | constrained local process, rootless Docker, gVisor/Kata/microVM/dedicated worker | threat 등급, host boundary, cleanup, startup latency, platform portability, 비용 | Phase 0 PoC evidence와 위협 모델을 근거로 단계별 선택. Docker와 stronger isolation을 동시 기본값으로 선택하지 않는다. |
| API/realtime persistence | REST/OpenAPI + polling/SSE/WebSocket, relational event metadata, append-only event store | closed schema, ordering, reconnect, audit, migration, 단일 노드 단순성 | Phase 0 schema를 먼저 고정하고 Phase 1 UI/trace slice에서 최소 조합을 선택한다. |

결정 전 후보는 `PLANNED`이며 제품 요구사항처럼 다루지 않는다. 결정에는
대안, 선택·기각 이유, 적용 단계, migration/rollback 전략, 위협·SLO·비용
영향과 fresh PoC evidence를 남긴다. 기술 이름을 선택했다는 사실만으로
containment, durability, idempotency 또는 rollback을 보장하지 않는다.

## 13. 관련 문서

- [ForgeOps 제품 요구사항 문서](../product/prd.md) — 제품 목표, Phase 0~4 요구사항과 release-level Exit gate
- [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md) — 제품 비전과 Harness Foundation 인수인계 기준선
- [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md) — 문서 책임, 식별자, 성숙도와 추적 설계
- [저장소 기본 지시와 ForgeOps profile](../../AGENTS.md) — repository adapter와 운영 경계
- [Main Orchestrator Protocol 2.0](../../.github/agents/main_instruction.prompt.md) — canonical packet, `MainDecision`, 상태·revision·sequence 소유권
- [Part Analyst 역할 계약](../../.github/agents/part_agent.prompt.md) — read-only discovery와 proposal 경계
- [Work Executor 역할 계약](../../.github/agents/work_agent.prompt.md) — approved exact action, preflight, execution과 evidence 경계
- [Portable Agent Harness 포팅 가이드](../agent-harness/PORTING_GUIDE.md) — adapter capability normalization과 이식 불변식

후속 위협 모델, 검증·평가 계획, WBS, RTM과 위험 등록부는 각 기준 문서가
생성된 뒤 안정적인 ARC/PRD ID로 연결한다. 존재하지 않는 미래 경로나
계획된 검증 명령을 현재 evidence reference로 기록하지 않는다.
