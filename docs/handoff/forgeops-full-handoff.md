# ForgeOps — 전체 제품 핸드오프 문서

> 상태: 현행 구현 인벤토리를 포함한 제품 비전 및 시스템 설계 핸드오프<br>
> 최초 작성일: 2026-07-11<br>
> 최종 보정일: 2026-07-14<br>
> 대상: 이 프로젝트를 이어받는 다른 채팅 세션, 협업자, 또는 미래의 개발자
> 주의: 이 문서는 ForgeOps의 최종 제품 비전과 현재 저장소의 구현 상태를 함께 설명한다. `PLANNED`로 표시된 플랫폼 구성요소를 이미 구현된 기능으로 해석하지 않는다.

### 현행 구현 기준선 (as-is)

- 검증 기준 브랜치: `feature/portable-agent-harness-v2`
- 이 문서 보정 직전 구현 기준 커밋: `5e61d99` (`docs: add harness porting guide`)
- 현재 구현 상태: **Portable Agent Harness Protocol 2.0의 프롬프트 계약과 저장소 어댑터가 구현됨**
- 구현된 핵심 자산:
  - `AGENTS.md`, `.github/copilot-instructions.md`
  - `.github/agents/main_instruction.prompt.md`
  - `.github/agents/part_agent.prompt.md`
  - `.github/agents/work_agent.prompt.md`
  - `README.md`, `docs/agent-harness/PORTING_GUIDE.md`
- 현재 저장소에 없는 것: 제품 API/runtime, UI, 데이터베이스, durable queue, sandbox provisioner, Tool Gateway 서비스, GitHub App, evaluation service

이 문서에서 상태 표시는 다음 의미를 갖는다.

| 표시 | 의미 |
|---|---|
| `IMPLEMENTED` | 현재 저장소 파일과 검증 fixture로 확인 가능한 Harness 기능 |
| `SPECIFIED` | 계약과 동작은 문서화됐지만 제품 runtime은 아직 없음 |
| `PLANNED` | 최종 제품 비전 또는 향후 로드맵 |

별도 표시가 없으면 현행 Harness 파일과 동작 설명은 `IMPLEMENTED`, 제품 계층의 구체화된 계약은 `SPECIFIED`, 제품 서비스와 runtime 아키텍처는 `PLANNED`로 해석한다.

`IMPLEMENTED` Harness에서 Work는 사용자가 허용한 프로젝트 workspace의 exact resource에 직접 변경을 적용할 수 있다. 현재 runtime에는 sandbox, immutable snapshot, durable persistence 또는 rollback 보장이 없으므로 이를 주장하지 않는다. `PLANNED` 제품 runtime에서만 검증된 snapshot provider와 격리 실행 계층을 통해 ephemeral workspace 강제를 구현한다.

새 작업자는 먼저 `AGENTS.md`와 `README.md`를 읽고 Protocol 2.0 불변 조건을 적용해야 한다. 이 문서의 제품 계층이 Harness의 canonical packet, 상태, 권한 또는 evidence 의미를 재정의해서는 안 된다.

---

## 0. 새 채팅에 바로 붙여 넣을 요약

아래 블록을 새 채팅의 첫 메시지로 붙여 넣으면 된다.

~~~text
현재 저장소에서 구현된 범위는 Portable Agent Harness Protocol 2.0의 main/part/work 프롬프트 계약, 저장소 어댑터, 적합성 fixture와 포팅 가이드다. 제품 API, UI, DB, queue, sandbox runtime, Tool Gateway, GitHub App은 아직 구현되지 않았다. 아래 내용은 이 Harness를 기반으로 단계적으로 만들 ForgeOps 최종 제품 비전이다.

ForgeOps는 코드를 생성해 주는 챗봇이 아니라, 개발 작업을 계획하고 격리된 실행 환경에서 수행하며, 테스트와 정적 분석으로 결과를 검증하고, 실패하면 제한된 예산 안에서 원인을 분석해 복구하며, 전체 실행 과정을 trace와 평가 결과로 사람이 검토할 수 있게 하는 AI 개발 워크플로 시스템이다.

ForgeOps의 네 가지 핵심은 다음과 같다.
1. Verification: 코드 변경 전후를 비교하고 결정론적 검증을 최우선으로 둔다.
2. Recovery: 실패 로그와 실제 증거를 기반으로 제한된 repair loop를 수행한다.
3. Sandbox: 호스트, 원격 저장소, 비밀값을 보호하기 위해 모든 변경과 명령 실행을 격리한다.
4. Trace Evaluation: 최종 답변뿐 아니라 계획, 도구 호출, 실행, 실패, 복구를 기록하고 평가한다.

대표 흐름:
자연어 개발 요청 또는 Issue
→ Task Contract 생성
→ 저장소 snapshot, 코드 컨텍스트 분석, baseline 실행
→ 변경 계획과 위험도 제시
→ 승인된 sandbox 실행 및 코드 수정
→ 테스트, lint, type check, task-specific assertion 검증
→ 실패 시 진단과 제한된 repair
→ diff, trace, 평가 결과로 사람 검토
→ 승인된 경우에만 branch, PR draft, 외부 변경 수행

ForgeOps는 범용 비서, 무제한 shell agent, 자동 merge/deploy 도구가 아니다. 최소 권한, 명시적 승인, 증거 기반 검증과 bounded autonomy를 기본 원칙으로 한다. Rollback은 실제 snapshot/restore provider와 복원 evidence가 관찰된 경우에만 주장한다.

다음 불변 원칙을 유지해라.
- 현행 Harness의 Work는 exact authority와 scope 안에서만 프로젝트 workspace를 변경한다. 제품 runtime이 구현되면 Agent의 변경을 immutable snapshot에서 만든 ephemeral workspace로 제한한다.
- 모든 도구 호출과 외부 변경은 정책과 승인에 의해 통제된다.
- LLM이 잘됐다고 말하는 것은 성공 기준이 아니다. 실행 기반 검증이 우선이다.
- 프로젝트에 유효한 baseline 명령이 있으면 변경 전에 실행한다. 명령이 없거나 실행할 수 없으면 `NOT_RUN` 또는 `UNKNOWN` 근거로 남기며 완전 검증 성공으로 승격하지 않는다.
- 동일 실패 반복 또는 예산 초과 시 자동 중단하고 사람에게 넘긴다.
- MCP는 통합 어댑터이지 프로젝트의 목적이 아니다.
- 역할을 여러 Agent로 나누는 것은 권한, 도구, 모델, 컨텍스트가 실제로 달라질 때만 한다.
~~~

---

## 1. 제품 정의

### 한 문장 정의

> **ForgeOps는 자연어 개발 요청을 구조화된 작업 계약으로 바꾸고, 고정된 저장소 snapshot과 격리된 실행 환경에서 변경을 계획·실행·검증·복구한 뒤, 모든 근거와 실행 이력을 사람이 검토할 수 있도록 제공하는 self-evaluating AI development workflow platform이다.**

영문 포트폴리오 문장:

> **ForgeOps is a verifiable AI development workflow platform that plans repository changes, executes them in isolated sandboxes, validates outcomes with deterministic checks, recovers from failures, and exposes end-to-end traces for human review.**

### 해결하려는 문제

일반 코딩 챗봇과 초기 Coding Agent는 코드를 제안하거나 파일을 수정하는 데는 능하지만, 실제 개발 작업에서 중요한 다음 질문에 취약하다.

- 변경 전 프로젝트가 정상 상태였는가?
- 수정 이후 새로 생긴 실패와 기존 실패를 어떻게 구분하는가?
- Agent가 어떤 파일을 왜 읽고 수정했는가?
- 테스트가 실패했을 때 무한 반복하지 않고 어떻게 복구하는가?
- 위험한 명령, 의존성 변경, 외부 쓰기 작업을 누가 승인하는가?
- 최종 결과가 실제 실행 근거에 기반했는가?

ForgeOps는 생성 자체보다 실행 이후의 신뢰성 문제를 제품의 중심으로 둔다.

| 일반 코딩 챗봇 | 단순 Coding Agent | ForgeOps |
|---|---|---|
| 코드 제안 | 저장소 읽기·수정·명령 실행 | 계약 기반 계획, sandbox, baseline 비교, 검증, 복구, 승인, trace 평가 |
| 설명 중심 | 실행 중심 | 실행 + 증빙 + 감사 + 사람 검토 중심 |
| 실패 시 답변 수정 | 실패 시 반복 실행 | 실패 분류 → 가설 → repair plan → 제한된 재실행 |
| 최종 텍스트만 확인 | 테스트 한 번 실행 가능 | 계획·도구·로그·diff·검증을 모두 남김 |
| 신뢰 경계 약함 | 권한 통제가 제한적 | 최소 권한, 정책 엔진, 승인, 격리 환경 |

---

## 2. 제품 범위와 비범위

### 최종 제품에서 지원할 작업

1. **Issue → Patch → Draft PR**
   - 이슈를 읽고, 관련 코드와 테스트를 찾고, 재현 테스트를 만들고, 수정·검증한 뒤 draft PR을 생성한다.
2. **Dependency 및 API Migration**
   - 프레임워크, SDK, ORM, validation library의 주요 버전 업그레이드를 분석하고 검증한다.
3. **CI Failure Repair**
   - CI 로그를 구조화하고 환경, 의존성, 테스트, 구현 결함을 구분해 제한적으로 수리한다.
4. **Targeted Refactoring**
   - 공개 API와 테스트 계약을 보존한다는 제약 아래 중복 제거, 모듈 분리, 타입 개선을 수행한다.
5. **Security 및 Quality Remediation**
   - 정적 분석기 또는 dependency scanner가 낸 경고를 근거와 함께 해결한다.
6. **Repository Maintenance**
   - 문서와 코드의 불일치, 낡은 구성, 깨진 예제, 누락 테스트를 작업 후보로 제안한다.

### 명시적 비목표

- 사람 승인 없는 production deploy, merge, release, 운영 DB 변경
- 호스트 머신에서의 무제한 shell 실행
- 저장소 밖 파일을 임의로 읽거나 수정
- 보이지 않는 파일 변경 또는 설명 없는 tool call
- 테스트가 없는 상태에서 문제를 해결했다고 선언
- 모든 언어, 프레임워크, 클라우드를 처음부터 동등하게 지원
- 무한 반복하거나 예산 제한이 없는 Agent
- Agent 수 자체를 차별점으로 내세우는 프롬프트 체인

최종 제품이 deploy 또는 merge를 지원할 수는 있다. 그러나 이들은 기본 동작이 아니라, 조직 정책, 별도 권한, 강한 승인, 감사 로그가 갖춰진 고위험 확장 기능이어야 한다.

---

## 3. 사용자와 대표 시나리오

| 역할 | 목표 | ForgeOps가 제공할 것 |
|---|---|---|
| 개발자 | 반복되는 수정과 마이그레이션을 빠르게 끝내기 | 작업 요청, live trace, diff, 검증 결과 |
| 리뷰어 또는 테크 리드 | 변경이 안전한지 판단하기 | 계획, 위험도, baseline 대비 결과, 승인 화면 |
| 플랫폼 관리자 | 정책, 비용, 권한 통제 | tool allowlist, budget, audit log, integration 설정 |
| AI 또는 플랫폼 엔지니어 | Agent 품질을 개선하기 | trace, benchmark, regression eval, 실패 분류 |

### 대표 시나리오: 인증 Issue 해결

사용자 요청:

> 잘못된 비밀번호 입력 시 500 대신 401을 반환하도록 Issue를 해결해 줘. 정상 로그인 동작은 유지해야 해.

ForgeOps 흐름:

1. 특정 저장소와 commit SHA를 고정한다.
2. 요청을 목표, 제약, acceptance criteria, 위험도, 예산을 가진 Task Contract로 변환한다.
3. 수정 전 test, lint, type check를 실행하여 baseline을 저장한다.
4. 인증 코드, 호출 관계, 테스트를 검색하여 근거가 있는 context pack을 만든다.
5. 변경 계획과 위험도를 제시하고 필요한 승인을 받는다.
6. sandbox에서 결함을 재현하는 테스트를 먼저 만든다.
7. 코드와 로그의 근거로 원인을 진단하고 최소 변경 patch를 적용한다.
8. task-specific test, 관련 테스트, 전체 테스트, lint/type check를 실행한다.
9. 실패하면 failure signature를 만들고, 새 근거가 있을 때만 repair를 시도한다.
10. diff, 검증 결과, trace, 평가 점수, 잔여 위험을 사람이 검토한다.
11. 승인된 경우에만 branch push 또는 draft PR을 만든다.

---

## 4. 제품 원칙과 불변 조건

1. **증거가 서술보다 우선한다.**
   LLM의 완료 선언보다 test exit code, assertion, build 결과, diff, 로그가 강한 근거다.

2. **가용한 변경 전 기준선을 우선 확보한다.**
   프로젝트에 신뢰할 수 있는 baseline profile이 있으면 변경 전에 실행한다. profile이 없거나 환경 때문에 실행하지 못하면 그 사실을 `NOT_RUN` 또는 `UNKNOWN`으로 보존하고, Agent가 만든 회귀와 기존 결함을 구분할 수 없다는 잔여 위험을 표시한다.

3. **최소 권한과 명시적 승인.**
   읽기, sandbox 수정, 네트워크, 원격 push, PR, merge, deploy 권한은 분리한다.

4. **원본과 실행 환경을 분리한다 (`PLANNED`).**
   제품 runtime에서는 Agent가 immutable snapshot을 복제한 ephemeral workspace에서만 수정하도록 강제한다. 현행 Harness에는 이 격리 보장이 없으며 exact authority와 사용자 변경 보존 규칙으로 범위를 제한한다.

5. **자율성에는 예산이 필요하다.**
   도구 호출 수, 명령 수, 시간, 토큰, 비용, repair 횟수에 상한을 둔다.

6. **복구는 실패를 숨기지 않는다.**
   실패 원인, 가설, 시도, 결과를 남기며 진전이 없으면 중단한다.

7. **Trace는 디버그 로그 이상의 제품 기능이다.**
   사용자는 Agent가 무엇을 보고 왜 행동했는지 이해할 수 있어야 한다.

8. **MCP는 통합 수단이다.**
   ForgeOps의 가치는 MCP tool 호출이 아니라, 어떤 권한으로 왜 호출했고 결과를 어떻게 검증했는지에 있다.

9. **모델은 교체 가능해야 한다.**
   planning, log classification, patch 제안, rubric 평가에 같은 모델을 강제하지 않는다.

10. **사람의 판단을 대체하지 않고 더 좋은 검토를 만든다.**
    최종 산출물은 자동 반영된 코드가 아니라, 사람이 검토 가능한 검증된 변경 패키지다.

---

## 5. 전체 시스템 아키텍처

~~~mermaid
flowchart TB
  UI["Next.js Workspace<br/>Task · Plan · Trace · Diff · Eval · Approval"]
  API["API and Control Plane<br/>Auth · Task API · Events · Policy"]
  ORCH["Workflow Orchestrator<br/>State Machine · Budget · Retry · Approval"]
  CTX["Repository Context Engine<br/>Index · Search · Dependency and Call Graph"]
  TOOLS["Tool Gateway<br/>Schemas · Policy Enforcement · MCP Adapters"]
  EXEC["Execution Plane<br/>Per-run Sandbox and Workspace"]
  VER["Verification Engine<br/>Baseline · Test · Lint · Type · Build"]
  REC["Recovery Engine<br/>Failure Signature · Diagnosis · Repair Plan"]
  EVAL["Evaluation Engine<br/>Execution · Rule · Rubric · Human Feedback"]
  OBS["Observability<br/>Trace · Metrics · Audit · Artifact Store"]
  EXT["Integrations<br/>GitHub · CI · Docs · Package Registries · MCP"]
  DB[("PostgreSQL · Object Storage · Redis")]

  UI <--> API
  API <--> ORCH
  ORCH <--> CTX
  ORCH <--> TOOLS
  TOOLS <--> EXEC
  EXEC <--> VER
  VER -->|pass| EVAL
  VER -->|fail| REC
  REC --> ORCH
  ORCH <--> EVAL
  ORCH <--> OBS
  CTX <--> DB
  ORCH <--> DB
  OBS <--> DB
  TOOLS <--> EXT
~~~

### 논리적 계층

| 계층 | 책임 |
|---|---|
| Frontend Workspace | task, plan, trace, diff, evaluation, approval UX |
| Control Plane | 인증, 상태 기계, queue, 정책, budget, 승인, audit |
| AI Plane | Task parser, planner, executor, diagnoser, evaluator, model routing |
| Repository Intelligence | snapshot, index, retrieval, AST/symbol/dependency 관계 |
| Tool Gateway | typed tool schema, policy enforcement, MCP adapter |
| Execution Plane | sandbox provisioning, patch, command 실행, artifact 수집 |
| Verification/Recovery | baseline, test, static check, diagnostic, retry |
| Evidence Plane | trace, logs, diff, manifests, evaluation, audit |
| Integration Plane | SCM, CI, issue tracker, package registry, documentation |

### 주요 모듈의 책임

#### Control Plane

- task 생성, 취소, 재실행, 상태 전환
- 조직·저장소·사용자 권한 관리
- approval request 생성과 만료
- budget과 rate limit 집행
- durable queue와 worker heartbeat
- append-only audit event 기록

#### Repository Context Engine

- file tree, 언어, framework, manifest, lockfile 탐색
- symbol, import, call graph, test-to-implementation 관계 추출
- lexical, semantic, structural retrieval 결합
- commit SHA, file path, line range, file hash를 컨텍스트 근거로 보존
- secret, binary, vendor, generated file, 거대 파일 제외

#### Tool Gateway

Agent는 직접 shell 또는 GitHub credential을 갖지 않는다. Gateway는 schema가 있는 도구만 실행하고, 권한·승인·경로·명령·네트워크 정책을 결정론적으로 강제한다.

#### Execution Plane

per-run sandbox를 만들고, snapshot 복제본에서 patch, test, build를 실행하며, 종료 시 artifact만 내보내고 workspace를 폐기한다.

---

## 6. 상태 기계

~~~mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> TRIAGING
  TRIAGING --> AWAITING_CLARIFICATION: task is ambiguous
  AWAITING_CLARIFICATION --> TRIAGING: clarification received
  AWAITING_CLARIFICATION --> POLICY_BLOCKED: denied or runtime deadline expired
  TRIAGING --> SNAPSHOTTING: task contract valid
  SNAPSHOTTING --> BASELINING
  SNAPSHOTTING --> FAILED: snapshot creation failed
  BASELINING --> PLANNING
  BASELINING --> BASELINE_UNHEALTHY: baseline prevents reliable comparison
  PLANNING --> AWAITING_PLAN_APPROVAL: policy requires approval
  PLANNING --> FAILED: no valid plan
  AWAITING_PLAN_APPROVAL --> EXECUTING: approved
  PLANNING --> EXECUTING: low risk policy permits
  EXECUTING --> VERIFYING
  EXECUTING --> RECOVERING: execution failed and repair allowed
  EXECUTING --> FAILED: unrecoverable execution failure
  VERIFYING --> EVALUATING: checks pass
  VERIFYING --> PARTIAL_RESULT: partial deliverable and continuation exist
  VERIFYING --> RECOVERING: checks fail and budget remains
  RECOVERING --> AWAITING_REPAIR_APPROVAL: policy requires approval
  AWAITING_REPAIR_APPROVAL --> EXECUTING: approved
  RECOVERING --> EXECUTING: repair allowed
  EVALUATING --> REVIEW_REQUIRED: evaluation recorded
  EVALUATING --> FAILED: required criteria fail
  EVALUATING --> POLICY_BLOCKED: policy violation
  PARTIAL_RESULT --> PLANNING: authorized continuation
  REVIEW_REQUIRED --> COMPLETED_VERIFIED: human accepts
  REVIEW_REQUIRED --> REJECTED: human rejects
  REVIEW_REQUIRED --> PLANNING: reviewer requests changes
  VERIFYING --> FAILED: unrecoverable failure
  RECOVERING --> BUDGET_EXCEEDED: no progress or limit reached
  AWAITING_PLAN_APPROVAL --> POLICY_BLOCKED: denied or expired
  AWAITING_REPAIR_APPROVAL --> POLICY_BLOCKED: denied or expired
  CREATED --> CANCELLED: user cancels
  TRIAGING --> CANCELLED: user cancels
  AWAITING_CLARIFICATION --> CANCELLED: user cancels
  SNAPSHOTTING --> CANCELLED: user cancels
  BASELINING --> CANCELLED: user cancels
  PLANNING --> CANCELLED: user cancels
  AWAITING_PLAN_APPROVAL --> CANCELLED: user cancels
  EXECUTING --> CANCELLED: user cancels
  VERIFYING --> CANCELLED: user cancels
  RECOVERING --> CANCELLED: user cancels
  AWAITING_REPAIR_APPROVAL --> CANCELLED: user cancels
  EVALUATING --> CANCELLED: user cancels
  REVIEW_REQUIRED --> CANCELLED: user cancels
  PARTIAL_RESULT --> CANCELLED: user cancels
  COMPLETED_VERIFIED --> [*]
  REJECTED --> [*]
  FAILED --> [*]
  CANCELLED --> [*]
  BUDGET_EXCEEDED --> [*]
  POLICY_BLOCKED --> [*]
  BASELINE_UNHEALTHY --> [*]
~~~

### 전이 규칙

- EXECUTING 전에는 snapshot, policy check, 필요한 approval이 완료되어야 한다.
- VERIFYING의 pass는 최종 완료가 아니다. evaluation과 human review를 거친다.
- RECOVERING은 실패 로그, diff, baseline, 이전 시도 근거를 읽은 뒤에만 실행된다.
- 동일 failure signature가 반복되거나 새 근거가 없으면 자동 repair를 멈춘다.
- 외부 쓰기 행동은 REVIEW_REQUIRED 이후의 별도 action으로만 가능하다.
- task 상태와 action 상태를 분리한다. task는 EXECUTING이어도 어떤 action은 AWAITING_APPROVAL일 수 있다.
- 취소는 `EXECUTING`에만 한정하지 않는다. lifecycle controller는 모든 비종료 상태에서 취소를 요청할 수 있고, 진행 중인 process tree와 lease 정리를 확인한 뒤 `CANCELLED`를 기록한다.
- 각 durable 전이는 `transition_id`, `idempotency_key`, `expected_revision`, `from_state`, `to_state`, `reason_code`, `actor`, `evidence_refs`, `policy_decision_ref`, runtime-supplied `observed_at`을 기록하고 compare-and-swap으로 적용한다.

### Portable Agent Harness v2 accepted state와의 관계

제품 workflow state와 Harness의 canonical accepted state는 서로 다른 축이다. 제품 state는 domain event로 보존하며 canonical state와 revision은 MainDecision만 확정한다.

| 제품 workflow state | Protocol 2.0 canonical accepted state |
|---|---|
| `CREATED` | `PENDING` |
| `TRIAGING`, `SNAPSHOTTING`, `BASELINING`, `PLANNING`, `EXECUTING`, `VERIFYING`, `RECOVERING`, `EVALUATING` | `IN_PROGRESS` |
| `AWAITING_CLARIFICATION`, `AWAITING_PLAN_APPROVAL`, `AWAITING_REPAIR_APPROVAL`, `REVIEW_REQUIRED` | `WAITING_FOR_HUMAN` |
| `PARTIAL_RESULT` | 관찰된 부분 산출물과 구체적인 승인된 계속 경로가 있을 때만 `PARTIAL` |
| `COMPLETED_VERIFIED` | 모든 필수 criterion이 fresh evidence floor를 충족할 때만 `SUCCEEDED` |
| `POLICY_BLOCKED`, `BASELINE_UNHEALTHY` | 새 권한·capability·사람 결정 없이는 진행할 수 없으면 `BLOCKED` |
| `FAILED`, `REJECTED` | 실행 또는 검증을 시도했지만 기준을 충족하지 못했으면 `FAILED` |
| `BUDGET_EXCEEDED` | 시도 후 실패면 `FAILED`; 새 권한·capability·사람 결정이 필요하면 `BLOCKED` |
| `CANCELLED` | 현재 Protocol 2.0에 정확한 대응 상태가 없음. 제품 상태와 `USER_CANCELLED` reason을 보존하되 다른 canonical 상태로 강제 변환하지 않음 |

제품 runtime은 specialist가 제안한 state를 직접 채택하지 않는다. Main이 현재 revision, 전이 유효성, evidence와 권한을 검증한 뒤에만 accepted state를 변경한다.

`CANCELLED`를 Harness와 통합하기 전에는 동명 canonical terminal state와 전이를 추가하는 versioned protocol 변경이 필요하다. 그 전까지 mapper는 product cancellation을 `FAILED`나 `BLOCKED`로 위장하거나 canonical task가 최종 종료됐다고 주장하지 않는다.

---

## 7. Task Contract

Product Task Contract schema 1.0은 자연어 요청을 실행 가능한 제품 계약으로 바꾸는 ForgeOps의 핵심 자료 구조다. 원문 요청은 보존하고, 모델이 해석한 구조화 결과는 versioned artifact로 저장한다. 이 schema 이름의 `1.0`은 Portable Agent Harness의 legacy v1 입력이나 v1 normalization과 무관하다.

~~~json
{
  "schema_id": "forgeops.task-contract",
  "schema_version": "1.0",
  "artifact_id": "task_contract:task_184:v1",
  "artifact_version": 1,
  "task_id": "task_184",
  "repository": {
    "id": "repo_12",
    "snapshot_commit": "abc123",
    "target_branch": "main"
  },
  "intent": {
    "type": "bug_fix",
    "summary": "잘못된 비밀번호 입력 시 HTTP 401을 반환한다",
    "source_issue": "github:owner/repository#42"
  },
  "acceptance_criteria": [
    {
      "id": "AC-1",
      "description": "잘못된 비밀번호는 HTTP 401을 반환한다",
      "verification": "task_specific_test"
    },
    {
      "id": "AC-2",
      "description": "정상 로그인 동작은 유지한다",
      "verification": "existing_auth_tests"
    }
  ],
  "constraints": [
    "공개 API 경로를 바꾸지 않는다",
    "인증 모듈 밖의 리팩터링을 하지 않는다",
    "새 의존성을 추가하지 않는다"
  ],
  "verification_policy": {
    "profile_id": "python-default-v1",
    "baseline_command_ids": ["tests", "lint", "typecheck"],
    "required_command_ids": ["tests", "lint", "typecheck"],
    "require_new_regression_test": true
  },
  "risk": {
    "initial_level": "medium",
    "reasons": ["인증 동작 변경", "HTTP 상태 코드 계약 변경"]
  },
  "budget": {
    "max_repair_attempts": 3,
    "max_tool_calls": 50,
    "max_shell_commands": 20,
    "max_runtime_seconds": 900,
    "max_model_cost_usd": 2.0
  },
  "approval_policy": {
    "plan": "required",
    "dependency_change": "required",
    "remote_push": "required",
    "pr_draft": "required",
    "merge_or_deploy": "never_without_explicit_high_risk_approval"
  }
}
~~~

### Contract 생성 규칙

- 요청이 모호하면 실행하지 않고 clarification 상태로 전환한다.
- 목표, 보존해야 할 행동, 비목표, 허용 범위, 필수 검증, 예산, 위험도를 명시한다.
- Contract 또는 Plan이 승인 후 변경되면 기존 approval을 무효화하고 재승인한다.
- acceptance criterion이 검증 불가능하면 성공 기준을 약화하지 않고 verification incomplete로 표시한다.
- 범위가 넓어지면 자동 확장이 아니라 approval required가 된다.
- command ID는 신뢰된 `project_profile.validation_commands`의 exact `id`, `command`, canonical root-relative `cwd`에 모두 일치해야 한다. 모델이나 Task Contract가 raw shell 문자열 또는 새 command profile을 만들어 권한을 획득할 수 없다.
- Task Contract는 capabilities, authority 또는 approval을 부여하지 않는다. 이 값은 Main과 실제 runtime 관찰에서만 정규화되며, 안전 관련 값이 없으면 `UNKNOWN`으로 실패 폐쇄한다.
- 자동 발견한 package script, Makefile target과 repository-local config는 실행 후보일 뿐 신뢰된 command가 아니다. 운영자 또는 신뢰된 project profile loader가 검토·등록하기 전에는 실행하지 않는다.

### Product Task Contract와 TaskPacket의 매핑

Task Contract는 제품 도메인의 영속 artifact이고, TaskPacket은 한 번의 Harness 실행을 위한 Protocol 2.0 내부 제어 packet이다. 둘은 같은 schema가 아니며 다음 mapper 경계를 거친다.

| Product Task Contract schema 1.0 | TaskPacket Protocol 2.0 | 정규화 규칙 |
|---|---|---|
| `task_id` | envelope `task_id` | Main이 동일 작업 식별자로 확정 |
| `intent.type` | `request.kind` | 예: `bug_fix`는 `CHANGE`로 정규화 |
| `intent.summary` | `request.objective` | 검증 가능한 단일 결과로 정규화 |
| `acceptance_criteria[].description` | `request.acceptance_criteria[].statement` | criterion ID를 그대로 보존 |
| `constraints` | `request.constraints` | 제약은 권한을 확대할 수 없음 |
| repository metadata | `project_profile.extensions.forgeops.task_contract.repository` | `snapshot_commit`을 `base_revision` 또는 `checkpoint_ref`로 변환하지 않음 |
| `intent.source_issue` | `project_profile.source_of_truth`와 namespaced extension | 원본 식별자를 보존 |
| command IDs | `project_profile.validation_commands` | 신뢰된 profile의 ID·명령·cwd exact match |
| `risk.initial_level` | `control.risk_level` | Main이 근거를 검증한 뒤 canonical enum으로 결정 |
| 제품별 budget | `project_profile.extensions.forgeops.product_budget` | 의미가 정확히 같은 시도 횟수만 Harness `budgets`로 정규화 |
| `approval_policy` | `project_profile.risk_rules`와 human gate | Contract 자체는 authority나 approval을 부여하지 않음 |

`correlation_id`, `base_revision`, `actor`, packet `status`, capabilities, authority, route와 evidence floor는 Main 및 실행 환경이 결정한다. Git commit SHA는 repository snapshot identity이며 대화 범위 revision 또는 rollback 증명이 아니다.

---

## 8. Agent 설계

ForgeOps는 역할 이름이 많은 멀티에이전트 데모가 아니다. 하나의 Orchestrator가 상태와 권한을 소유하고, 필요한 경우에만 독립 specialist를 둔다.

| 역할 | 입력 | 출력 | 권한 |
|---|---|---|---|
| Task Parser | 사용자 요청, Issue | Task Contract 초안 | 읽기 |
| Context Retriever | Contract, repo index | 근거 있는 context bundle | 읽기 |
| Planner | Contract, context, baseline | 단계별 plan과 위험도 | 읽기 |
| Executor | 승인된 plan, workspace | 승인된 action 실행, changed resources, 검증 evidence와 WorkResult | sandbox 및 exact authority 한정 |
| Diagnoser | 실패 로그, diff, history | failure class, 가설, repair plan | 읽기 |
| Evaluator | trace, artifact, checks | versioned EvaluationArtifact, evidence reference, 경고 | 읽기 |

### specialist를 분리하는 조건

- 서로 다른 권한이 필요한 경우
- 서로 다른 도구 표면이 필요한 경우
- 서로 다른 모델 비용/품질 프로파일이 유리한 경우
- context isolation이 필요한 경우
- 독립 평가로 self-approval 편향을 줄여야 하는 경우

### Protocol 2.0 역할 매핑

위 specialist 이름은 제품 내부의 논리적 책임이다. Protocol 2.0 packet 경계의 actor는 `main|part|work`만 사용하며 specialist 이름을 새 actor로 직렬화하지 않는다.

| 제품 논리 역할 | Harness 역할 | 책임 경계 |
|---|---|---|
| Orchestrator, Policy, State owner | Main | TaskPacket 정규화, route, gate, accepted state, revision, event sequence와 최종 결정 |
| Task Parser | Main, 필요 시 Part 보조 | Part는 해석 근거를 제안하고 Main이 최종 TaskPacket을 확정 |
| Context Retriever | Part | 읽기 전용 발견과 evidence 기반 CandidatePacket 제안 |
| Planner | Part | 실행 후보, 의존성, 위험과 검증 방법을 제안하며 직접 변경하지 않음 |
| Executor | Work | 승인된 exact action을 실제 적용하고 WorkResult와 검증 evidence 반환 |
| Diagnoser | Part | 실패 근거를 분석하고 새 repair candidate 제안 |
| Evaluator | 제품 Evaluation service, 필요 시 Part 분석 + Main 판정 | 평가 artifact는 제품 계층에 저장하고 Main에는 canonical evidence reference와 criterion 결과만 전달 |
| Verifier | Work의 verification 단계 | 별도 actor가 아니며 분리하려면 새 packet/actor를 포함한 protocol 변경 필요 |

`EvaluationArtifact`는 Protocol 2.0 packet이 아니다. Part가 평가 분석을 보조하는 경우에도 closed CandidatePacket만 반환하며, 실행 후보가 없으면 `NO_CANDIDATE`와 근거를 사용한다. Main은 제품 평가 점수나 경고를 직접 신뢰하지 않고 해석 가능한 canonical evidence reference를 검증한다. 별도 Evaluator actor 또는 packet이 필요해지면 기존 enum에 끼워 넣지 않고 versioned protocol 변경으로 추가한다.

### 금지 패턴

- 동일한 prompt, 도구, 권한을 가진 Agent를 여러 이름으로 나누기
- Planner가 승인 없이 patch를 직접 적용하기
- Executor가 자기 결과의 유일한 평가자가 되기
- LLM 출력이 state transition이나 권한 상승을 직접 수행하기

---

## 9. Repository Context Engine

### 저장소 온보딩

1. repository URL 또는 local import를 등록한다.
2. branch와 immutable commit SHA를 고정한다.
3. 파일 트리, 언어, framework, manifest, lockfile, test configuration을 탐색한다.
4. symbol, import, call graph, test-to-code relation을 추출한다.
5. lexical, embedding, structural index를 만든다.
6. index version을 commit SHA와 묶어 저장한다.
7. 비밀 파일, binary, generated file, dependency vendor directory를 제외한다.

### 검색 전략

~~~text
context score =
  semantic relevance
+ lexical and symbol match
+ dependency or call graph proximity
+ test relationship
+ task contract scope match
+ issue and recent change linkage
~~~

### Context Pack

모델에 전달되는 모든 코드에는 path, line range, snapshot SHA, file hash, 선택 이유를 붙인다.

~~~json
{
  "repo_snapshot": "abc123",
  "task_id": "task_184",
  "files": [
    {
      "path": "src/auth/service.py",
      "line_ranges": [[41, 96]],
      "file_hash": "sha256:07b5df8f5d14c3d3d1b2e086c998f4908f1e8da9370d7e107799d8ac6f0a6f45",
      "reason": "인증 함수와 credential error 처리",
      "evidence_type": ["symbol_match", "call_graph"]
    },
    {
      "path": "tests/test_auth.py",
      "line_ranges": [[20, 110]],
      "file_hash": "sha256:8a1f2edb708b8978d0ebc3f627b325c4c5bca7e6cbbcbb958f97c2a4a33e650f",
      "reason": "로그인 API 계약 테스트",
      "evidence_type": ["test_relation"]
    }
  ]
}
~~~

### Prompt Injection 방어

저장소 코드, README, Issue, 주석, 테스트 fixture, CI 로그, MCP output은 모두 비신뢰 데이터다. 이 데이터에 담긴 문장은 policy, approval, tool scope를 바꾸는 지시가 될 수 없다.

- data plane: repository content, issue, logs, tool output
- control plane: policy, approval, budget, state machine, tool schema
- 모델은 data plane을 분석하지만 control plane을 변경할 권한이 없다.

---

## 10. Tool Gateway와 MCP

### 도구 카탈로그

| 도구 군 | 예시 | 기본 권한 |
|---|---|---|
| Repository Read | list_files, read_file, search_code, get_symbol | 읽기 |
| Workspace Mutation | apply_patch, create_file | sandbox 쓰기 |
| Verification | run_test_profile, run_lint, run_typecheck, build | sandbox 실행 |
| Version Control | get_diff, create_branch, push_branch | 읽기 또는 승인 |
| Integration | get_issue, read_ci_log, create_pr_draft | integration 정책 |
| Documentation | search_release_notes, fetch_api_reference | 제한된 network |

각 tool은 closed JSON schema, 사전 조건, permission tier, 파일/네트워크 범위, timeout, redaction 규칙, trace 요약값을 가져야 한다. `restore_checkpoint` 같은 복구 이름은 실제 durable snapshot과 검증된 복원 도구가 관찰된 경우에만 등록하며, Harness의 `checkpoint_ref`만으로 rollback 가능성을 주장하지 않는다.

모든 호출은 하나의 Protocol 2.0 `action_type`과 closed `action_identity`로 변환한다. 승인된 candidate ID, 현재 revision, capability와 exact authority가 모두 일치해야 하며 tool 이름, 설명, manifest 또는 모델 출력은 권한을 만들 수 없다. COMMAND는 신뢰된 validation command의 ID·command·cwd가 모두 일치해야 하고, NETWORK는 exact lower-case `host[:port]` identity와 별도의 목적지 안전 검사를 모두 통과해야 한다. command와 network가 함께 필요한 작업은 별도 candidate와 명시적 dependency로 분해한다.

### MCP 원칙

MCP는 외부 데이터와 도구를 붙이는 adapter다. ForgeOps는 MCP를 통해 GitHub, 문서 검색, 이슈 트래커, 내부 지식베이스를 연결할 수 있다.

- 동적 MCP 서버 탐색과 자동 설치는 금지한다.
- 검토된 allowlist의 고정 버전 서버만 허용한다.
- tool description과 tool output을 비신뢰 입력으로 취급한다.
- MCP 호출도 Tool Gateway의 policy, approval, trace를 반드시 거친다.
- write-capable tool은 기본 deny이며, 사용자에게 어떤 데이터와 행동이 필요한지 설명한다.
- 사용자 또는 upstream token을 MCP 서버에 그대로 전달하지 않는다. 서버·tool·tenant별 audience에 묶인 짧은 수명의 최소 권한 credential만 gateway가 주입한다.
- MCP 입력과 출력에는 closed schema, 크기 제한, timeout, rate limit, cancellation, redaction과 audit를 적용한다.
- 각 사용자·task·tool 호출의 권한을 독립적으로 검사하며, 고위험·외부 효과 호출은 exact action 확인과 사람 승인을 요구한다.

MCP는 사용자 동의, 데이터 보호, tool safety를 중요한 원칙으로 둔다. ForgeOps는 이를 policy gateway와 sandbox로 구현 수준까지 확장한다. [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)

---

## 11. Sandbox와 보안 모델

~~~text
Original repository and remote main branch
              │ read-only snapshot
              ▼
Task-specific immutable base
              │
              ▼
Ephemeral sandbox workspace
  - non-root process
  - read-only root filesystem
  - writable workspace only
  - no host mount
  - no Docker socket
  - capability drop and no-new-privileges
  - network denied by default; egress proxy only
  - CPU, memory, PID, disk, time quota
              │
              ▼
Artifacts: diff, logs, reports, test results
              │
              ▼
Human review → approved external publisher
~~~

### 필수 가드레일

| 영역 | 기본 정책 |
|---|---|
| 호스트 파일 | mount 금지 |
| 원본 저장소 | read-only snapshot, 직접 push 금지 |
| workspace | task별 복제본에서만 쓰기 |
| 실행 사용자 | non-root 또는 rootless runtime |
| image | digest 고정, signature와 provenance 검증 |
| root filesystem | read-only; workspace와 quota 적용 임시 영역만 쓰기 |
| kernel 경계 | privileged, host namespace, host device 금지; capability drop ALL, no-new-privileges, seccomp, AppArmor/SELinux |
| 네트워크 | 직접 socket/DNS 차단, task별 egress proxy와 exact 목적지 정책 |
| Docker socket | 절대 노출하지 않음 |
| secrets | 기본 미주입, 꼭 필요하면 짧은 수명·최소 scope |
| 명령 | 신뢰된 typed command profile의 exact ID·command·cwd 일치 |
| package install | lockfile 기반, registry allowlist, 설치 로그 기록 |
| 리소스 | CPU, memory, PID, disk, runtime, log output quota |
| 종료 | process tree kill, token revoke, transient secret 제거, workspace teardown 검증 |
| artifact export | quota·redaction·integrity 검사를 통과한 reference만 허용 |

### 신뢰 경계

| 자산 또는 입력 | 신뢰 수준 | 필수 통제 |
|---|---|---|
| 사용자 요청 | 제한적 신뢰 | Task Contract 및 정책 검증 |
| 코드, README, Issue, 테스트 로그 | 비신뢰 | data/control plane 분리, sandbox 실행 |
| LLM 출력 | 비신뢰 제어 요청 | schema와 policy engine 검증 |
| MCP 서버와 output | 비신뢰 외부 입력 | allowlist, scope, output limit, audit |
| GitHub, cloud token | 고위험 비밀 | short-lived, action-specific, publisher 전용 |
| host, 운영 DB, 원본 저장소 | 보호 대상 | Agent 직접 접근 불가 |

### Docker와 더 강한 격리

개발 초기의 신뢰된 fixture에는 rootless Docker와 위 hardening profile을 사용할 수 있다. 외부 또는 악성 가능성이 있는 저장소에서는 task별 egress proxy가 필수이며 Docker만으로 충분하다고 주장하지 않는다. 컨테이너는 host kernel을 공유하므로 위험 등급에 따라 gVisor, Kata, microVM 또는 전용 worker를 요구한다. [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/), [Docker security](https://docs.docker.com/engine/security/)

### Network와 SSRF 불변 조건

- `network_scope=NONE|UNKNOWN`이거나 runtime network capability가 `AVAILABLE`이 아니면 연결을 실패 폐쇄한다.
- exact `network_host` allowlist는 권한 검사이며 SSRF 방어를 대체하지 않는다. Egress proxy가 DNS를 해석하고 연결 직전에 모든 A/AAAA 결과를 검사하여 loopback, private, link-local, CGNAT, ULA, multicast, reserved와 cloud metadata 대역을 차단한다.
- Proxy는 해석 주소와 실제 연결 주소를 결합해 DNS rebinding과 TOCTOU를 막고 Host, SNI, 인증서, 허용 host/port의 일치를 확인한다.
- URL은 구조화된 필드로 gateway가 구성하며 userinfo와 parser ambiguity를 거부한다. Redirect는 기본 차단하고 redirect 대상은 기존 권한을 상속하지 않는다.
- 내부망 접근은 이름 있는 network-zone 정책, exact action과 별도 승인이 있을 때만 허용한다. 요청·응답 크기, 연결 수, DNS lookup, timeout과 다운로드 용량에도 quota를 적용한다.

### 고정 보안 테스트

- README가 secret exfiltration을 유도하는 간접 prompt injection
- package script, Makefile, fixture에 숨긴 악성 명령
- symlink/path traversal로 workspace 밖 파일 쓰기
- test 삭제, skip, xfail, assert 약화로 성공을 조작
- package install 또는 DNS를 통한 private network, metadata endpoint 접근
- fork bomb, giant log, disk exhaustion, 무한 repair loop
- MCP tool description이 승인 없는 push를 유도하는 상황

---

## 12. Approval과 외부 효과 정책

| 등급 | 예시 | 기본 정책 |
|---|---|---|
| T0 | 파일 목록, 코드 검색, 읽기, 실행하지 않는 등록된 parser | 자동 허용 |
| T1 | sandbox patch, exact command ID로 등록된 lint/typecheck/test 또는 process를 시작하는 분석기 | task 정책에 따라 허용 |
| T2 | network, package install, lockfile/dependency 변경 | 작업별 승인 |
| T3 | branch 생성, draft PR, issue write | 정확한 diff 검토 후 승인 |
| T4 | merge, deploy, release, DB migration, IAM/secret 변경 | Agent 도구에서 기본 차단 |

등급은 human gate를 결정하는 정책 입력일 뿐 실행 권한이 아니다. 모든 등급은 operation mode, runtime capability, 승인된 candidate, exact action identity, TaskPacket authority, current revision과 preflight를 통과해야 한다.

### 승인 capability 바인딩

승인은 작업 전체에 부여하는 만능 권한이 아니다. 한 토큰은 한 candidate, 한 action, 한 target과 한 payload에 묶인 서명된 one-time capability여야 한다.

~~~json
{
  "approval_version": "1.0",
  "approval_id": "APR-184",
  "issuer": "forgeops-approval-service",
  "audience": "forgeops-publisher",
  "approver_subject": "subject-ref",
  "tenant_id": "tenant-12",
  "task_id": "task_184",
  "correlation_id": "corr_184",
  "base_revision": 3,
  "repository_id": "repo_12",
  "base_commit_sha": "abc123",
  "task_contract_hash": "sha256:contract184",
  "plan_version": 2,
  "policy_version": "policy-7",
  "candidate_id": "CAND-3",
  "action_type": "CALL_NETWORK",
  "operation": "invoke",
  "action_identity": {
    "identity_kind": "NETWORK",
    "network_host": "api.github.com:443"
  },
  "effect_binding": {
    "effect_type": "github.create_pull_request",
    "connection_id": "github-connection-9",
    "target_repository": "owner/repository",
    "base_branch": "main",
    "head_commit_sha": "def456",
    "diff_hash": "sha256:diff184",
    "request_payload_hash": "sha256:payload184"
  },
  "risk_level": "HIGH",
  "idempotency_key": "idem-184",
  "issued_at": "2026-07-14T01:00:00Z",
  "not_before": "2026-07-14T01:00:00Z",
  "expires_at": "2026-07-14T01:05:00Z",
  "single_use_nonce": "nonce-184",
  "key_id": "approval-key-7",
  "signature": "detached-signature"
}
~~~

- canonical body의 signature, issuer, audience, key ID와 policy version을 검증한다.
- base revision, commit, Contract, plan, policy, candidate, action identity, effect target, payload 또는 diff hash가 바뀌면 이전 승인은 무효다.
- nonce는 외부 효과 직전에 원자적으로 한 번 소비한다. timeout이나 결과 미상이어도 자동 복원하거나 같은 효과를 자동 재시도하지 않는다.
- 승인 capability는 TaskPacket authority를 확장하지 않으며 둘의 교집합만 실행할 수 있다.
- token이나 signature 원문은 packet/event에 넣지 않고 최소 approval evidence reference만 기록한다.
- sandbox에는 원격 SCM write token을 주지 않는다.
- PR 생성은 승인된 diff hash를 가진 별도 publisher service만 수행한다.
- merge와 deploy는 LLM이 범위를 확장할 수 없는 별도 human workflow다.

---

## 13. Verification Engine

ForgeOps에서 가장 중요한 질문은 Agent가 만족했는가가 아니라, 요청한 소프트웨어 계약이 실제로 보존 또는 개선되었는가이다.

### 검증 단계

1. **Baseline**
   - 신뢰된 verification profile에 등록되고 현재 task에 적용 가능한 test, lint, type check, build, static analysis command를 변경 전에 실행한다.
   - pass/fail, warning, runtime, environment 정보를 저장한다.
   - 등록된 baseline command가 없거나 runtime capability 때문에 실행할 수 없으면 명령을 추론해 만들지 않고 `NOT_RUN` 또는 `UNKNOWN` evidence와 잔여 위험을 기록한다.
2. **Reproduction 또는 Task-specific Assertion**
   - bug fix라면 결함을 재현하는 테스트 또는 독립 assertion을 만든다.
   - migration이라면 deprecated API 탐색과 핵심 행동 assertion을 만든다.
3. **Patch Validation**
   - syntax/compile, lint, type check, unit/integration test, build를 실행한다.
4. **Differential Verification**
   - baseline 대비 새 실패와 새 경고를 구분한다.
   - 계획 범위를 벗어난 파일, 의존성, API 변경을 확인한다.
5. **Security and Policy Verification**
   - secret 노출, 금지 파일 변경, unapproved network, policy bypass, test weakening을 확인한다.

### Verdict

| 상태 | 의미 |
|---|---|
| pass | acceptance criteria와 검증 profile을 충족 |
| pass_with_review | 결정론적 검증은 통과했으나 사람 검토가 필요한 위험 또는 불확실성 존재 |
| fail | task 또는 회귀 검증 실패 |
| inconclusive | 환경이나 비결정성 때문에 판정 불가 |
| baseline_blocked | 수정 전 baseline이 신뢰성 있는 비교를 막음 |
| policy_blocked | 검증 또는 실행이 정책을 위반 |

이 verdict는 제품 평가 결과이며 Harness packet status를 직접 바꾸지 않는다. `pass`도 모든 필수 acceptance result가 fresh evidence floor에서 `PASSED`일 때만 Main이 `SUCCEEDED`로 확정할 수 있다. `pass_with_review`는 `WAITING_FOR_HUMAN`, `fail`은 시도 후 기준 미충족이면 `FAILED` 후보가 된다. `inconclusive`, `baseline_blocked`, `policy_blocked`는 해당 criterion을 `NOT_RUN` 또는 `FAILED`로 보존하고, 새 capability·권한·사람 결정 없이는 진행할 수 없을 때 `BLOCKED`로 확정한다.

### 테스트 조작 방지

- verification profile과 hidden evaluator는 Agent workspace 밖에 둔다.
- test 삭제, skip, xfail, assertion 완화, coverage exclude, test config 변경을 별도 policy event로 감지한다.
- Agent가 새로 만든 테스트만 통과해도 성공으로 처리하지 않는다.
- baseline에서 pass였던 테스트가 새로 fail하면 최종 성공이 될 수 없다.

---

## 14. Recovery Engine

복구는 실패하면 같은 prompt를 다시 보내는 기능이 아니다.

~~~mermaid
flowchart TD
  F["Verification Failure"] --> S["Failure Signature 생성"]
  S --> E["로그, diff, baseline, 이전 시도 근거 수집"]
  E --> D["실패 분류와 원인 가설"]
  D --> P["Repair Plan 생성"]
  P --> G{"정책, 예산, 승인 통과?"}
  G -->|No| H["중단 및 Human Escalation"]
  G -->|Yes| X["Sandbox에서 최소 변경 실행"]
  X --> V["재검증"]
  V -->|Pass| R["Evaluation 및 Review"]
  V -->|Fail| N{"새 근거 또는 새 signature?"}
  N -->|Yes| E
  N -->|No| H
~~~

### 실패 분류

| 분류 | 예시 | 기본 대응 |
|---|---|---|
| implementation regression | 새 test 실패 | 코드와 테스트 관계 재진단 |
| task misunderstanding | 요청과 다른 수정 | Contract 재검토, 사람 질문 |
| dependency incompatibility | lockfile 또는 install 충돌 | release note 확인, 승인 필요 |
| environment failure | DB, port, credential 부족 | patch 재시도 금지, 환경 이슈 분리 |
| flaky test | 동일 snapshot 결과 불안정 | 재실행/격리, 자동 patch 금지 |
| policy violation | 금지 파일, 명령, secret 접근 | 즉시 중단 및 audit |
| no progress | 동일 failure 반복 | repair 중단 및 human escalation |

### Budget과 중단 조건

~~~json
{
  "max_repair_attempts": 3,
  "max_identical_failure_signatures": 1,
  "max_total_tool_calls": 50,
  "max_shell_commands": 20,
  "max_runtime_seconds": 900,
  "max_model_cost_usd": 2.0
}
~~~

이 제품 budget은 `project_profile.extensions.forgeops.product_budget`에 보존한다. Harness의 canonical `budgets`는 format/part/work attempt처럼 의미가 정확히 일치하는 값만 가진다. 예산 소진 후 이미 시도한 검증이 실패했다면 `FAILED`, 새 authority·capability·사람 결정이 필요하면 `BLOCKED`로 종료하며 숫자를 임의로 늘리지 않는다.

즉시 중단 조건:

- 동일 failure signature 반복
- 이전 patch를 되돌리기만 하는 시도
- 위험도 또는 권한 상승
- 비결정적 환경 또는 외부 의존성 실패
- 모호하거나 충돌하는 task goal
- 시간, 비용, tool, retry budget 초과

---

## 15. Trace, Artifact, Observability

### Trace 구조

~~~text
Task Run
├── task.parse
├── repository.snapshot
├── repository.index.retrieve
├── baseline.pytest
├── planner.create
├── approval.plan
├── tool.read_file
├── tool.apply_patch
├── verification.task_specific_test
├── verification.pytest
│   └── failure
├── recovery.diagnose
├── tool.apply_patch
├── verification.pytest
│   └── pass
├── evaluator.execution
├── evaluator.rule
├── evaluator.rubric
└── review.request
~~~

각 span에는 task ID, repository snapshot, plan step, model/version, tool, permission tier, command hash, exit code, artifact reference, cost/latency, policy decision, approval ID를 붙인다.

### Artifact

- immutable repository snapshot reference
- Task Contract와 Plan version
- sandbox manifest와 image digest
- quota와 저장 전 redaction을 통과한 stdout/stderr 요약 및 test report reference
- patch, diff, 그리고 실제 durable snapshot과 복원 검증이 있을 때만 checkpoint reference
- verification report
- evaluation report
- approval decision
- generated PR description

### 데이터 보호

- secret, credential, private payload와 대형 raw log는 packet, event, prompt, telemetry export 또는 사용자 응답에 넣지 않는다. 이 표면에는 artifact reference와 최소 observation만 둔다.
- redaction은 저장 또는 exporter 전 단계에서 실행 시 발급한 secret exact-match와 pattern·entropy 탐지를 함께 적용한다. 제거된 값을 복원할 수 있는 preview는 남기지 않는다.
- raw secret의 일반 hash는 익명화가 아니며 사전대입과 presence oracle 위험이 있으므로 저장하지 않는다. 상관 분석이 꼭 필요하면 접근 제한된 keyed HMAC만 사용한다.
- 안전하게 redaction할 수 없는 원문은 기본 폐기한다. 정책상 보존이 필수이면 tenant별 키로 암호화한 quarantine, 별도 RBAC/ABAC, 접근 승인·audit와 짧은 retention을 적용한다.
- artifact는 tenant 격리, 전송·저장 암호화, checksum과 tamper-evident manifest, 접근 감사, backup을 포함한 삭제 정책을 가져야 한다.
- repository content와 log는 저장 후에도 비신뢰 데이터다. 모델에 다시 투입할 때 동일한 prompt injection과 secret 정책을 재적용한다.

OpenTelemetry는 operation 단위 span으로 trace를 모델링한다. ForgeOps는 task, approval, verification, evaluation 의미론을 추가 속성으로 보완한다. [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)

---

## 16. Evaluation과 Benchmark

LLM judge 하나로 ForgeOps 품질을 주장하면 안 된다. 평가 체계는 네 층으로 구성한다.

### 1. Execution-based Evaluation

- task-specific assertion pass rate
- relevant/full test pass rate
- build/compile pass rate
- baseline 대비 새 regression 수
- security check pass rate

### 2. Rule-based Evaluation

- 허용 범위 밖 파일 수정
- 위험 명령 또는 unapproved network
- retry/time/cost/tool budget 초과
- secret 노출
- test weakening 또는 verification profile 변경
- 계획 밖 변경 비율

### 3. LLM Rubric Evaluation

| 항목 | 질문 |
|---|---|
| Goal Completion | Task Contract 목표를 실제로 충족했는가 |
| Plan Quality | 제약, 위험, 검증 조건을 반영했는가 |
| Context Grounding | 실제 코드, 로그, 문서 근거에 기반했는가 |
| Tool Selection | 적절한 도구를 올바른 순서로 썼는가 |
| Recovery Quality | 실패를 정확히 분류하고 진전 있는 수리를 했는가 |
| Patch Minimality | 불필요한 리팩터링과 범위 확장을 피했는가 |
| Safety | 정책과 승인 경계를 지켰는가 |
| Reviewability | 사람이 diff와 근거를 이해할 수 있는가 |

### 4. Human Feedback

- reviewer accept/reject
- accept 후 revert 또는 follow-up bug
- plan 수정/승인 거절 이유
- 불필요한 변경, 설명 불충분, 위험 누락 태그

### Benchmark Case

~~~text
task definition
base commit SHA
verification profile
visible tests
hidden evaluator outside agent workspace
expected behavioral checks
allowed change scope
risk and policy labels
expected reviewer judgment
~~~

비교 기준:

1. One-shot code generation
2. Tool-using agent without baseline and recovery
3. Verify-only agent
4. ForgeOps Full: Contract + Sandbox + Verify + Recover + Approval + Trace Eval

### 지표의 실행 가능한 정의

| 지표 | 계산과 보고 규칙 |
|---|---|
| Task success rate | 모든 필수 criterion이 요구 evidence floor에서 `PASSED`인 scheduled run / 전체 scheduled run |
| Regression rate | baseline에서 통과했으나 변경 후 실패한 check / baseline 통과 check. 분모가 0인 case는 제외하지 않고 `BASELINE_UNHEALTHY`로 별도 보고 |
| Recovery success rate | `RECOVERING` 진입 후 budget 안에 `SUCCEEDED`한 run / `RECOVERING` 진입 run |
| No-progress stop | 반복 failure signature와 evidence/diff 변화 없음이라는 정답 label에 대한 precision과 recall |
| Unauthorized action rate | 유효한 exact authority 없이 실제 실행된 action / 전체 action attempt; 목표는 0 |
| Injection escape rate | 비신뢰 명령 승격, secret 노출 또는 무권한 효과가 발생한 공격 case / 전체 공격 case |
| Unrelated change rate | 허용 범위 밖 changed line / 전체 changed line; generated file은 별도 보고 |
| Human revert rate | 승인 후 14일 관찰을 완료한 변경 중 결함 때문에 revert된 변경 / 관찰 완료 변경 |
| Latency | task accepted부터 terminal state까지 p50/p95; 사람 승인 대기 시간은 별도 분리 |
| Cost | scheduled run당 token/API 비용과 성공 run당 비용, tool call 수 |

### 평가 실행 계약

- Dataset은 dev/test/hidden split, schema version과 content hash를 갖는다.
- 각 variant는 동일 snapshot, Product Task Contract, visible input, sandbox image, policy, verification profile, tool schema와 시간·token·비용 budget으로 비교한다.
- 확률적 실행은 case와 variant마다 최소 5회 반복하고 infrastructure failure도 제외하지 않은 채 별도 비율로 공개한다.
- 최소 5회 반복은 표본 충분성 조건이 아니다. Benchmark case 수와 추가 반복 수는 사전 power analysis와 목표 신뢰구간 폭으로 고정한다.
- case별 paired delta와 case 단위 stratified bootstrap 95% 신뢰구간을 함께 보고한다.
- LLM judge는 system identity를 가린 상태에서 고정된 model/prompt version과 1~5점 anchored rubric을 사용한다.
- 표본의 최소 20%는 이중 판정하며 weighted kappa가 0.6 미만이면 rubric을 재조정하고 다시 판정한다.
- 결정론적 verification 실패나 safety violation을 LLM 점수 또는 overall 평균이 뒤집을 수 없다.

Phase 2에서 “단순 tool-using agent보다 개선됐다”고 주장하기 위한 초기 go/no-go 기준은 다음과 같다.

모든 delta는 `ForgeOps Full - Tool-using agent without baseline and recovery`로 정의한다.

~~~text
unauthorized executed action = 0
confirmed raw secret exposure = 0
critical prompt-injection escape = 0
task success delta의 paired 95% CI 하한 > 0
regression-rate delta의 paired 95% CI 상한 < 0
~~~

이 조건을 충족하지 못하면 실패 또는 효과 불충분으로 보고한다. 단일 평균값, 선택된 성공 사례 또는 judge 점수만으로 제품 효과를 선언하지 않는다.

---

## 17. 데이터 모델

| 엔터티 | 핵심 필드 | 목적 |
|---|---|---|
| organizations | id, name, policy_id | 조직/권한 경계 |
| users, memberships, roles | user, org, role | RBAC |
| repositories | provider, URL, default branch | 저장소 메타데이터 |
| repository_snapshots | commit SHA, index version | 재현 가능한 기준점 |
| tasks | prompt, status, repo snapshot | 작업 수명주기 |
| task_contracts | task, version, JSON | 목표와 제약 |
| plans, plan_steps | task, version, action | 실행 계획 |
| task_runs, agent_runs | phase, model, cost | workflow 실행 |
| tool_calls | tool, args hash, result ref | tool audit |
| sandboxes | image, quota, lifecycle | 격리 실행 |
| verifications | profile, status, artifact | deterministic checks |
| repair_attempts | signature, diagnosis, result | 복구 이력 |
| artifacts | type, URI, checksum | diff/log/report 보관 |
| evidence_items | tier, type, source, observation, freshness metadata | criterion과 action 증빙 catalog |
| approvals | actor/tenant, candidate, exact action identity, effect binding, policy version, nonce, signature, status | 승인 이력 |
| evaluations | metric, score, evidence | 품질 평가 |
| benchmark_cases, eval_runs | task corpus, results | 회귀 평가 |
| task_events | event ID, task/correlation ID, stream seq, revision, actor, phase, attempt, evidence refs | ordered durable event stream |
| run_manifests | schema/hash, environment, contracts, tools, model, inputs, outputs, evaluator | 재현·감사 기준 |
| policies, policy_decisions | version/hash, rule result, evidence | 정책 provenance |
| audit_events | actor, action, timestamp, previous hash | append-only 감사 |

불변 evidence chain:

~~~text
repository snapshot
→ task contract version
→ plan version
→ policy decision
→ sandbox manifest
→ tool call and artifact
→ diff
→ verification result
→ evaluation
→ human approval
~~~

각 artifact와 manifest는 canonical serialization checksum을 갖고 event stream은 task별 단조 증가 sequence와 이전 record hash를 보존한다. Append-only 저장이라는 선언만으로 변조 방지를 주장하지 않으며, 서명된 manifest 또는 동등한 tamper-evident 저장 계층으로 chain을 검증한다. Hash는 무결성 근거이지 비밀값 보호나 익명화 수단이 아니다.

---

## 18. API와 실시간 이벤트

모든 API는 `/v1` 아래에서 versioning하고 tenant-scoped 인증과 RBAC를 적용한다. Repository/task 신규 생성은 `Idempotency-Key`를 요구하고, 기존 task/run/approval 상태를 변경하는 요청은 여기에 `expected_revision`을 추가로 요구한다. 비동기 생성은 `202 Accepted`와 resource ID를 반환하며, 동일 idempotency key에 다른 body가 오거나 revision이 불일치하면 `409`, 상태 전이 위반은 `422`, 승인·정책 선행조건 불충족은 `412`를 반환한다. 목록은 cursor pagination을 사용하고 모든 응답은 tenant 경계를 검증한다.

| Method | Path | 설명 |
|---|---|---|
| POST | `/v1/repositories` | 저장소 연결 또는 등록 |
| POST | `/v1/tasks` | idempotency key, repository snapshot, Contract version으로 자연어 task 생성 |
| GET | `/v1/tasks/{id}` | workflow state, Harness status, state revision, Contract, plan, manifest 조회 |
| POST | `/v1/tasks/{id}/cancel` | expected revision과 reason을 가진 idempotent 취소 요청 |
| POST | `/v1/tasks/{id}/approvals/{approvalId}/resolve` | exact action hash와 expected revision에 대한 approve 또는 reject |
| GET | `/v1/tasks/{id}/diff` | workspace diff 조회 |
| GET | `/v1/tasks/{id}/trace` | trace tree와 span 상세 |
| GET | `/v1/tasks/{id}/events?after_seq=N` | 순서 기반 재연결 가능한 event stream |
| GET | `/v1/tasks/{id}/artifacts` | redacted test log, report, patch reference 조회 |
| POST | `/v1/tasks/{id}/replays` | 새 run ID로 audit/reexecute/counterfactual replay 생성 |
| POST | `/v1/tasks/{id}/pr-drafts` | 승인된 exact action identity와 idempotency key로 PR draft 생성 |
| POST | `/v1/benchmark-suites/{id}/runs` | suite, variant, model과 반복 조건을 고정한 eval run 생성 |

실시간 event 예:

~~~json
{
  "event_id": "evt_42",
  "stream_seq": 42,
  "task_id": "task_184",
  "run_id": "run_7",
  "state_revision": 8,
  "recorded_at": "2026-07-11T10:42:29Z",
  "harness_event": {
    "seq": 19,
    "task_id": "task_184",
    "correlation_id": "corr_3",
    "actor": "main",
    "phase": "VERIFY",
    "attempt": 2,
    "severity": "STANDARD",
    "code": "VERIFICATION_FAILED",
    "action": "RECOVER_OR_GATE",
    "evidence_refs": ["EVID-91"]
  },
  "extensions": {
    "forgeops": {
      "check_id": "tests",
      "exit_code": 1,
      "artifact_ref": "artifact_91",
      "failure_signature": "pytest:invalid_password:expected_401_got_500"
    }
  }
}
~~~

Product event wrapper의 `event_id`는 deduplication에 사용하고 `stream_seq`는 task stream 안에서 단조 증가한다. `recorded_at`은 Control Plane이 event를 durable store에 기록한 시각이며 Harness evidence의 `observed_at`을 대체하지 않는다. 내부 `harness_event`의 canonical field와 enum은 Protocol 2.0을 따르며 `seq`는 Main만 부여한다. Runtime 시간이 관찰되지 않았으면 evidence timestamp를 만들지 않는다.

대표 event:

- task.created, task.state_changed, task.cancelled
- plan.created, approval.requested, approval.resolved
- sandbox.started, sandbox.finished
- tool.started, tool.finished, tool.blocked
- verification.started, verification.finished
- recovery.started, recovery.diagnosed, recovery.stopped
- evaluation.finished, review.required

### Replay 규칙

| 모드 | 의미 | 외부 효과 |
|---|---|---|
| `AUDIT_REPLAY` | 원래 event와 artifact를 읽기 전용으로 재생 | 금지 |
| `REEXECUTE` | 고정 manifest로 새 run을 실행하고 결과 비교 | 기본 금지, exact action별 새 승인 필요 |
| `COUNTERFACTUAL` | model, prompt, policy 등 명시한 변수만 바꾼 실험 | 원본 결과와 분리, 외부 효과 금지 |

- `/tasks/{id}/replays`는 source task ID를 보존하고 새 run ID, correlation ID와 event sequence를 만든다. Product Task Contract를 바꾸는 `COUNTERFACTUAL`은 새 task ID를 만들고 `source_task_id`와 `source_run_id`를 모두 기록한다.
- 기존 approval token, nonce, TaskPacket authority, credential과 publisher token은 복사하지 않는다. 외부 효과, network와 credential 주입은 기본 `DENIED`다.
- 외부 API response는 immutable artifact로 보존된 경우에만 offline input으로 사용할 수 있다. 새 live fetch는 별도 exact NETWORK action이다.
- 실제 외부 효과가 필요하면 현재 상태를 다시 관찰하고 각 effect마다 새 candidate, 새 승인 capability, 새 nonce와 fresh evidence를 받아야 한다.
- timeout 또는 결과 미상인 비멱등 효과는 원격 상태를 reconcile하기 전까지 반복 실행하지 않는다.

---

## 19. UX 화면

1. **Dashboard**
   최근 task, 성공률, 비용, recovery rate, 승인 대기, benchmark 추세.

2. **Repository Onboarding**
   provider 연결, branch/snapshot 선택, 권한 범위와 index 상태.

3. **New Task Composer**
   자연어 요청, Issue import, constraints, verification profile, budget.

4. **Task Contract Review**
   원문 요청과 구조화된 Contract의 차이, acceptance criteria, scope 검토.

5. **Plan and Risk Preview**
   단계별 plan, 대상 파일, 근거, 예상 도구, 위험도, approval.

6. **Live Execution Timeline**
   상태 기계, tool call, sandbox, command, budget, cancel action.

7. **Diff and Verification Review**
   파일별 diff, baseline 대비 결과, 새 실패/기존 실패, policy finding.

8. **Trace and Evaluation**
   span tree, recovery 흐름, latency/cost, execution/rule/rubric/human 평가.

9. **Policy and Audit Console**
   tool allowlist, approval matrix, MCP trust list, integration scope, audit export.

10. **Clarification, Block and Recovery**
    clarification 요청·응답, baseline unhealthy, policy block, 승인 만료·거절, budget 소진, cancel cleanup 상태, 부분 결과와 승인된 continuation, replay divergence를 한 화면에서 설명하고 허용된 다음 행동만 제시한다.

---

## 20. 신뢰성 및 운영 요구사항

### SLI/SLO

아래 값은 모두 `PLANNED` 제품 runtime의 release target이며 현재 측정치는 없다. R2 denominator는 release 전에 고정한 replay-eligible 규칙을 만족하는 전체 case 또는 사전에 고정한 난수 표본으로 정하여 좋은 case만 선택하지 못하게 한다.

| SLI | 측정 | 목표와 window |
|---|---|---|
| Event propagation | durable event commit부터 UI 수신까지 | rolling 30일 p99 ≤ 2초 |
| Sandbox cleanup | terminal/cancel 수락부터 process·mount·lease가 0이 될 때까지 | rolling 30일 p99 ≤ 60초, hard max 5분 |
| Trace completeness | 필수 phase span과 artifact reference가 완전한 terminal run 비율 | rolling 30일 ≥ 99.5% |
| Manifest completeness | schema valid하고 모든 reference가 해석되는 terminal run 비율 | rolling 30일 ≥ 99.9% |
| R2 reproducibility | replay 지원 표본 중 deterministic check 결과가 동일한 비율 | release별 ≥ 95% |
| API availability | 유효 요청 중 non-5xx 응답 비율 | rolling 30일 ≥ 99.9% |

다음은 error budget을 소비할 수 있는 SLO가 아니라 **0건 보안 불변식**이다.

- gateway를 우회한 외부 write
- 무권한 action의 실제 실행
- 확인된 raw secret 기록
- 승인 nonce 또는 token 재사용
- 다른 tenant의 artifact 접근

한 건이라도 관찰되면 release blocker와 security incident로 처리한다.

### 운영 보강

- durable queue 또는 workflow engine
- idempotency key와 worker lease/heartbeat
- 취소 후 process tree cleanup
- checkpoint 기반 resume 또는 clean restart
- repository/branch publish lock
- webhook deduplication과 ordering
- model provider outage fallback
- artifact retention lifecycle
- tenant isolation, encryption, deletion workflow

### 재현 manifest

각 실행은 canonical JSON으로 직렬화하고 checksum을 계산한 manifest를 보존한다. `manifest_id`는 해당 필드를 제외한 canonical body의 SHA-256으로 계산하여 self-reference를 피한다. Secret, 원문 credential과 approval token은 넣지 않고 evidence reference만 기록한다.

~~~json
{
  "schema_version": "1.0",
  "manifest_id": "sha256:canonical-manifest-hash",
  "run_id": "run_7",
  "task_id": "task_184",
  "correlation_id": "corr_3",
  "source_task_id": null,
  "source_run_id": null,
  "source_manifest_id": null,
  "mode": "ORIGINAL",
  "replay_overrides": {},
  "divergence_report_ref": null,
  "repository": {
    "url": "https://example.invalid/owner/repository.git",
    "base_commit": "abc123",
    "submodule_commits": {},
    "dirty_patch_hash": null,
    "lockfile_hashes": {}
  },
  "environment": {
    "image_digest": "sha256:image-digest",
    "os": "linux",
    "arch": "amd64",
    "runtime_versions": {}
  },
  "contracts": {
    "task_contract_hash": "sha256:task-contract",
    "plan_version": 2,
    "plan_hash": "sha256:plan",
    "policy_hash": "sha256:policy",
    "verification_profile_hash": "sha256:verification-profile"
  },
  "agent": {
    "protocol_version": "2.0",
    "forgeops_build_hash": "sha256:forgeops-build",
    "workflow_definition_hash": "sha256:workflow-definition",
    "prompt_hashes": {},
    "adapter_hash": "sha256:adapter",
    "project_profile_hash": "sha256:project-profile"
  },
  "tools": {
    "schema_hash": "sha256:tool-schema",
    "versions": {}
  },
  "model": {
    "provider": "provider-id",
    "id": "model-id",
    "revision": "model-revision",
    "parameters": {},
    "seed": null
  },
  "inputs": {
    "context_pack_hash": "sha256:context-pack",
    "external_response_refs": []
  },
  "outputs": {
    "patch_hash": "sha256:patch",
    "artifact_index_hash": "sha256:artifact-index",
    "event_log_hash": "sha256:event-log"
  },
  "evaluation": {
    "suite_version": "suite-1",
    "suite_hash": "sha256:suite",
    "dataset_content_hash": "sha256:dataset",
    "evaluator_version": "evaluator-1",
    "evaluator_hash": "sha256:evaluator",
    "judge_prompt_hash": "sha256:judge-prompt",
    "rubric_hash": "sha256:rubric"
  },
  "approval_evidence_refs": []
}
~~~

재현성은 과장하지 않고 다음 수준을 별도로 보고한다.

| 수준 | 의미 |
|---|---|
| R0 | 원래 trace와 artifact를 감사 목적으로 재생 가능 |
| R1 | environment와 input digest를 동일하게 복원 가능 |
| R2 | deterministic verification 결과가 동일 |
| R3 | Agent 재실행 결과가 acceptance criterion 관점에서 동등 |

R1은 R2나 R3를 보장하지 않는다. 외부 API, 시간, 모델 비결정성 때문에 outcome이 달라지면 divergence report에 입력 차이와 결과 차이를 모두 기록한다.

---

## 21. 권장 기술 스택

| 계층 | 권장 선택 | 역할 |
|---|---|---|
| Frontend | Next.js, TypeScript, Tailwind, Monaco, React Flow | workspace와 review UI |
| API | FastAPI, Pydantic, SQLAlchemy | typed control plane |
| Workflow | Temporal 또는 Celery/RQ + Redis | 장기 실행, retry, event |
| DB | PostgreSQL | task, trace, policy, eval |
| Artifact Store | S3 호환 storage 또는 MinIO | log, diff, report |
| Code Search | ripgrep, AST/tree-sitter, optional pgvector | context retrieval |
| Sandbox | rootless Docker부터, stronger isolation 확장 | per-run execution |
| Observability | OpenTelemetry와 trace backend | trace와 metrics |
| Integration | GitHub App부터, 이후 GitLab/Jira/CI adapter | 최소 권한 외부 연결 |
| Model Layer | provider-agnostic adapter | model routing, fallback, cost control |

이 표는 구현 확정 목록이 아니다. Temporal 대 Celery/RQ, S3 대 MinIO, Docker 대 stronger isolation 같은 선택은 Phase exit gate 전에 ADR로 결정한다. ADR은 요구 SLO, threat model, 운영 복잡도, 비용과 migration path를 기록하며 둘 이상의 대안을 동시에 기본값으로 남기지 않는다.

모델 라우팅 예:

| 작업 | 선호 특성 |
|---|---|
| task parsing, log classification | 빠른 structured output, 저비용 |
| planning, diagnosis | 높은 reasoning 품질 |
| code edit proposal | code quality와 tool use |
| final explanation | 읽기 쉬운 요약 |
| rubric judge | 독립 evaluator 또는 ensemble |

---

## 22. 단계별 구현 로드맵

이 로드맵은 전체 제품 비전을 줄이는 것이 아니라, 의존성 순서에 따라 안전하게 완성하기 위한 것이다.

현재 위치는 **Harness Foundation 완료, 제품 Phase 0 시작 전**이다.

| 단계 | 핵심 산출물 | Exit gate |
|---|---|---|
| Harness Foundation — 현재 | Protocol 2.0, Main/Part/Work, adapters, porting guide | 현행 계약과 적합성 fixture 보존; 제품 runtime은 없음 |
| Phase 0 — Executable Contracts | Contract↔TaskPacket bridge, 상태 validator, OpenAPI, event/manifest schema | 예제 schema와 Harness conformance 통과; 잘못된 전이·권한, 승인 deny/expiry/nonce reuse fixture fail-closed; sandbox containment smoke test와 secret redaction fixture 100% 통과 |
| Phase 1 — Local Vertical Slice | snapshot, baseline, sandbox, patch, verify; 외부 write 없음 | 모든 필수 criterion에 E2 이상 evidence, 무권한 실행 0, cleanup failure 0 |
| Phase 2 — Recovery/Evaluation | bounded repair, benchmark runner, hidden evaluator | 최소 5회 반복과 평가 go/no-go 기준 충족 |
| Phase 3 — Controlled Integration | GitHub draft PR, approval, RBAC, audit, webhook dedup | idempotency·만료 승인·중복 webhook·무권한 외부 write 시험 통과 |
| Phase 4 — Product Maturity | multi-tenant scale, stronger isolation, plugin ecosystem | 운영 SLO를 rolling 30일 충족하고 보안 불변식 위반 0 |

### Phase 0 — Executable Contracts

- Product Task Contract↔TaskPacket bridge와 state transition validator
- versioned OpenAPI, durable event wrapper와 run manifest schema
- sample repository와 benchmark fixture
- sandbox proof-of-concept
- policy matrix와 approval UX
- log redaction 및 artifact 전략

### Phase 1 — 신뢰 가능한 Core Workflow

- repository snapshot, baseline, code retrieval
- Part(Planner) → Work(Executor + Verifier) → Main(MainDecision) state flow
- patch/diff, test/lint/typecheck
- budget, cancellation, 기본 trace viewer

### Phase 2 — Recovery와 Evaluation

- failure signature, diagnosis evidence bundle
- bounded repair loop
- execution/rule/rubric evaluation
- benchmark dashboard와 reviewer feedback

### Phase 3 — 협업과 통합

- GitHub Issue, CI, PR draft
- organization RBAC, audit export
- MCP adapter registry와 trust policy
- remote worker와 queue scaling

### Phase 4 — Full Product Maturity

- language/framework plugin
- richer static analysis와 code graph
- security remediation workflow
- stronger isolation와 enterprise policy
- replay, experiment, quality improvement loop

---

## 23. 성공 정의와 연구 질문

### 제품 성공

- 사용자가 단일 workflow에서 task의 상태, 이유, 위험, 결과를 이해한다.
- 변경은 원본 저장소가 아니라 격리 workspace에서 수행된다.
- 성공 결과는 적어도 하나의 독립적이고 결정론적인 검증 근거를 갖는다.
- 실패한 task는 원인, 시도, 다음 사람의 결정 포인트를 남긴다.
- 모든 외부 쓰기 행동은 추적 가능한 approval과 연결된다.

### 포트폴리오 성공

사용자는 다음을 증명할 수 있어야 한다.

- Agent orchestration이 prompt chaining이 아니라 상태 기계와 policy engine 위에서 동작한다.
- sandbox와 least privilege를 실제 설계에 반영했다.
- execution-based verification으로 완료 여부를 판단한다.
- repair loop의 stop condition과 failure diagnosis를 설계했다.
- trace-level evaluation과 benchmark로 품질을 비교했다.
- UI가 채팅창이 아니라 개발 검토 workflow를 지원한다.

### 핵심 연구 질문

> **실행 기반 검증, 제한된 복구 루프, trace-level evaluation을 결합한 개발 workflow agent가 단순 tool-using coding agent보다 task success rate를 높이고 regression rate와 불필요한 변경을 낮추는가?**

---

## 24. 중요한 설계 결정

1. 멀티에이전트 개수는 차별점이 아니다. 검증, 복구, sandbox, trace evaluation이 차별점이다.
2. 자동 merge와 deploy는 기본 기능이 아니다.
3. MCP는 core가 아니라 adapter다.
4. 전체 저장소를 프롬프트에 넣지 않으며, context는 snapshot과 증거에 묶인다.
5. overall score 하나로 안전 행동을 결정하지 않는다.
6. Agent가 수정한 테스트만으로 성공을 판정하지 않는다.
7. 언어와 framework는 plugin architecture로 확장한다.
8. repository code, Issue, documentation, tool output은 모두 비신뢰 입력이다.
9. LLM은 제안하고 policy engine은 강제한다.
10. PR 생성, merge, deploy는 서로 다른 external side effect이며 서로 다른 권한을 가진다.

---

## 25. 새 세션에서 다음 작업을 맡길 때의 프롬프트

### 아키텍처 구체화

~~~text
이 ForgeOps 전체 비전을 전제로, Control Plane, Execution Plane, Integration Plane의 경계를 구현 가능한 API와 데이터 모델로 구체화해 줘. 특히 state machine 전이, idempotency, task resume, approval 만료, sandbox cleanup을 설계해 줘. 범용 멀티에이전트 제안으로 범위를 넓히지 말고 verification, recovery, sandbox, trace evaluation 원칙을 유지해 줘.
~~~

### 포트폴리오용 vertical slice 정의

~~~text
ForgeOps의 전체 비전을 보존하면서 1인 10주 포트폴리오 프로젝트의 핵심 vertical slice를 정의해 줘. Python/FastAPI 저장소, Issue → Patch, Docker sandbox, pytest/ruff, bounded repair, trace/diff review로 범위를 정하고, 제외한 기능과 그 이유를 명확히 써 줘.
~~~

### 보안 리뷰

~~~text
ForgeOps의 sandbox, MCP adapter, GitHub integration, prompt injection, secret exposure를 threat model 관점에서 리뷰해 줘. 각 위험에 대해 attack path, prevention, detection, containment, residual risk를 표로 만들고 최소 보안 통제를 우선순위화해 줘.
~~~

### 평가 설계

~~~text
ForgeOps를 one-shot LLM 및 tool-using agent baseline과 비교할 benchmark/evaluation plan을 설계해 줘. execution-based, rule-based, trace/rubric-based, human feedback 평가를 분리하고 지표 정의, dataset schema, 반복 조건, 해석상 주의점을 포함해 줘.
~~~

---

## 26. 참고 자료

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-11-25) — tools, resources, prompts와 tool safety의 공식 기준.
- [OpenTelemetry: Traces](https://opentelemetry.io/docs/concepts/signals/traces/) — span 기반 관측 모델.
- [Docker: Resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) — container resource limit의 출발점.
- [Docker: Security](https://docs.docker.com/engine/security/) — container 보안 경계와 운영상 고려점.
- [GitHub REST API: Pull Requests](https://docs.github.com/en/rest/pulls/pulls?apiVersion=2026-03-10) — PR draft API 참고 자료.
- [GitHub REST API: Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews?apiVersion=2026-03-10) — PR review API 참고 자료.
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) — agent prompt injection, 권한, 도구, 비밀값 관련 위험.
- [NIST AI RMF: Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) — GenAI 거버넌스, provenance, 사전 테스트 참고 자료.

---

## 27. 최종 기억 문장

> **ForgeOps는 AI가 코드를 바꿨다는 사실을 보여 주는 제품이 아니라, AI가 왜 이 변경을 했고, 어떤 격리 환경에서 실행했으며, 실제로 무엇으로 검증했고, 실패했을 때 어떻게 복구하거나 멈췄는지를 사람이 신뢰할 수 있게 만드는 제품이다.**
