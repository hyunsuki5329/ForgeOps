# ForgeOps Product Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 승인된 핸드오프와 문서 체계 설계를 기준으로, 1인 개발 실행 관리와 포트폴리오 증빙에 사용할 한국어 기초 문서 8개를 생성하고 상호 추적성을 검증한다.

**Architecture:** PRD가 제품 요구사항 ID를 먼저 소유하고, 아키텍처·위협 모델·검증 계획이 설계와 통제 및 품질 게이트를 정의한다. WBS와 위험 등록부가 실행 정보를 제공한 뒤 RTM이 모든 ID를 연결하고, docs/README.md가 읽기 순서와 문서 상태를 제공한다.

**Tech Stack:** UTF-8 Markdown, Git, PowerShell 5.1+, ripgrep, Mermaid

## Global Constraints

- 승인된 설계 원본은 docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md다.
- 제품 비전과 현재 기준선의 입력 원본은 docs/handoff/forgeops-full-handoff.md다.
- Protocol 2.0 불변식은 AGENTS.md와 .github/agents/main_instruction.prompt.md, part_agent.prompt.md, work_agent.prompt.md를 따른다.
- 생성 파일은 정확히 docs/README.md와 product, architecture, security, quality, project 역할 폴더의 7개 문서다.
- PRD는 Phase 0~4 전체 요구사항을 정의한다. WBS에서만 Phase 2~4를 상위 마일스톤으로 유지한다.
- WBS는 상대 일정 W1~W10, 주당 5 person-day, 계획 4 person-day, buffer 1 person-day를 사용한다.
- 문서 본문은 한국어로 작성하고 식별자, enum, API 및 Protocol 고유명은 원문 표기를 유지한다.
- 문서 상태는 최초 생성 시 초안이고 최종 검토일은 2026-07-14다.
- 요구사항 성숙도는 IMPLEMENTED, SPECIFIED, PLANNED만 사용한다.
- WBS 상태는 WBS_NOT_STARTED, WBS_IN_PROGRESS, WBS_BLOCKED, WBS_DONE만 사용하며 제품 상태와 혼합하지 않는다.
- 추적 상태는 COVERED, PARTIAL, GAP만 사용한다.
- 검증 결과는 PASSED, FAILED, NOT_RUN만 사용한다.
- raw shell command를 RTM의 evidence나 authority로 기록하지 않는다. 검증 절차는 VG와 trusted command_id가 소유한다.
- SPECIFIED와 PLANNED 요구사항의 초기 검증 결과는 NOT_RUN, 실제 evidence tier와 참조 및 관찰 metadata는 없음으로 기록한다.
- 현재 구현 주장은 fresh E1 file 또는 diff observation으로 확인할 수 있을 때만 IMPLEMENTED로 표시한다.
- 제품 runtime, 코드, 프롬프트, 핸드오프, 기존 설계서는 수정하지 않는다.
- 사용자 소유 변경을 보존하고 태스크 시작과 종료 시 git status --short를 확인한다.
- 새 영구 검증 스크립트는 추가하지 않는다. 문서 검증은 이 계획의 inline PowerShell로 수행한다.
- 현재 승인에는 8개 문서와 이 계획의 Git commit, push, PR, 외부 게시 권한이 없다.
- 각 Git checkpoint는 상태와 제안 commit message만 출력한다. 명시적 Git 승인이 새로 주어진 경우에만 해당 태스크의 정확한 파일을 add와 commit한다.
- 외부 게시와 public portfolio 배포는 별도 승인 대상이다.

---

## File Map

| Path | Action | Responsibility |
| --- | --- | --- |
| docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md | Read only | 승인된 문서 체계와 완료 기준 |
| docs/handoff/forgeops-full-handoff.md | Read only | 제품 비전, 계약, 단계, 지표 |
| docs/product/prd.md | Create | Phase 0~4 제품 요구사항과 성공 기준 |
| docs/architecture/system-architecture.md | Create | 시스템 경계, 상태, 구성요소, 계약, 흐름 |
| docs/security/threat-model.md | Create | 위협, 통제, 잔여 위험, 보안 gate |
| docs/quality/verification-and-evaluation-plan.md | Create | evidence, VG, 평가, 품질 gate |
| docs/project/wbs.md | Create | Phase 0~1 상세 10주 계획과 Phase 2~4 마일스톤 |
| docs/project/risk-register.md | Create | 일정·기술·보안·평가·포트폴리오 위험 |
| docs/project/requirements-traceability-matrix.md | Create | 요구사항에서 증빙까지의 단일 교차 추적표 |
| docs/README.md | Create | 문서 지도, 읽기 순서, 상태, 기준 우선순위 |
| docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md | Create | 이 실행 계획 |

## Shared Document Header

모든 신규 기초 문서는 다음 metadata를 제목 바로 아래에 둔다.

~~~markdown
**문서 상태:** 초안
**최종 검토일:** 2026-07-14
**대상 독자:** 1인 개발자, 포트폴리오 검토자
**기준 출처:** 역할별 기준 출처의 저장소 상대 경로
~~~

각 문서 마지막에는 관련 문서 절을 두고 저장소 상대 링크만 사용한다.

---

### Task 1: Product Requirements Document

**Files:**
- Create: docs/product/prd.md
- Read: docs/handoff/forgeops-full-handoff.md
- Read: docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md

**Interfaces:**
- Consumes: 핸드오프의 제품 정의, 범위, 사용자, 원칙, 평가 지표, SLO, Phase 0~4 로드맵
- Produces: PRD-FR-001~PRD-FR-025, PRD-NFR-001~PRD-NFR-012와 Phase Exit gate

- [ ] **Step 1: Inspect scope and protect existing work**

Run:

~~~powershell
git status --short
$sources = @(
  'docs/handoff/forgeops-full-handoff.md',
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md'
)
foreach ($source in $sources) {
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Missing required source: $source"
  }
}
if (Test-Path -LiteralPath 'docs/product/prd.md') {
  throw 'STOP: docs/product/prd.md already exists; inspect ownership before editing.'
}
~~~

Expected: 두 기준 문서가 존재하고 target은 존재하지 않는다. target 또는 상위 폴더에 사용자 변경이 보이면 중단하고 범위를 확인한다.

- [ ] **Step 2: Create the PRD structure**

Use apply_patch to create docs/product/prd.md with these exact top-level sections:

~~~markdown
# ForgeOps 제품 요구사항 문서

## 1. 문서 목적과 기준
## 2. 제품 정의와 문제
## 3. 목표 사용자와 대표 시나리오
## 4. 목표와 비목표
## 5. 현재 Harness Foundation 기준선
## 6. 기능 요구사항
## 7. 비기능 요구사항
## 8. 단계별 Exit gate
## 9. 성공 지표와 평가 기준
## 10. 제약사항과 가정
## 11. 범위 제외
## 12. 관련 문서
~~~

Include the shared header. State that the PRD owns what and why, while implementation tasks belong to WBS.

- [ ] **Step 3: Add product context, users, scope, and baseline**

Write these facts without copying the entire handoff:

- Product sentence: ForgeOps는 자연어 개발 요청을 구조화된 작업 계약으로 바꾸고, 고정 snapshot과 격리 환경에서 계획·실행·검증·복구한 뒤 근거와 trace를 사람에게 제공하는 self-evaluating AI development workflow platform이다.
- Users: 개발자, 리뷰어 또는 테크 리드, 플랫폼 관리자, AI 또는 플랫폼 엔지니어.
- Supported outcomes: Issue to Patch to Draft PR, dependency/API migration, CI failure repair, targeted refactoring, security/quality remediation, repository maintenance.
- Non-goals: 무승인 production deploy·merge·release·운영 DB 변경, 무제한 host shell, 저장소 밖 임의 접근, 숨은 변경, 검증 없는 성공 선언, 초기 전 언어 동등 지원, 무한 repair, agent 수 자체의 차별화.
- Current baseline: Protocol 2.0, Main/Part/Work, adapters, porting guide는 IMPLEMENTED다. 제품 runtime, immutable snapshot, sandbox, durable persistence, rollback은 구현됐다고 주장하지 않는다.
- Baseline evidence links: ../../AGENTS.md, ../../.github/agents/main_instruction.prompt.md, ../../.github/agents/part_agent.prompt.md, ../../.github/agents/work_agent.prompt.md, ../agent-harness/PORTING_GUIDE.md.

- [ ] **Step 4: Add the functional requirement catalog**

Create one table with columns ID, Phase, Priority, Maturity, Requirement, Acceptance result, Verification. Use exactly this catalog:

| ID | Phase | Priority | Maturity | Requirement and observable acceptance | VG |
| --- | --- | --- | --- | --- | --- |
| PRD-FR-001 | Phase 0 | 필수 | SPECIFIED | Product Task Contract를 TaskPacket으로 lossless 정규화하며 Contract가 authority를 만들지 않는다 | VG-002 |
| PRD-FR-002 | Phase 0 | 필수 | SPECIFIED | 제품 state transition을 검증하고 canonical accepted state와 명시적으로 매핑하며 CANCELLED gap을 강제 변환하지 않는다 | VG-003 |
| PRD-FR-003 | Phase 0 | 필수 | SPECIFIED | versioned OpenAPI와 closed request/response schema가 유효·무효 예제를 판정한다 | VG-004 |
| PRD-FR-004 | Phase 0 | 필수 | SPECIFIED | durable event wrapper와 run manifest schema가 identity, ordering, provenance, reference를 보존한다 | VG-004 |
| PRD-FR-005 | Phase 0 | 필수 | PLANNED | sample repository와 positive/negative fixture가 conformance와 failure path를 재현한다 | VG-001 |
| PRD-FR-006 | Phase 0 | 필수 | SPECIFIED | policy matrix와 approval UX가 exact action, 위험, 만료, 거절, 재승인을 설명한다 | VG-007 |
| PRD-FR-007 | Phase 0 | 필수 | PLANNED | sandbox containment PoC와 redaction/artifact 전략이 금지 경계를 fail-closed한다 | VG-008, VG-009 |
| PRD-FR-008 | Phase 1 | 필수 | PLANNED | repository snapshot, baseline, code retrieval이 고정 source와 변경 전 상태를 보존한다 | VG-010 |
| PRD-FR-009 | Phase 1 | 필수 | PLANNED | Context Pack이 근거 경로를 포함하고 repository prompt injection을 control plane으로 승격하지 않는다 | VG-011 |
| PRD-FR-010 | Phase 1 | 필수 | PLANNED | Main 정규화·라우팅, Part 분석, Work 실행·검증, Main 수용 흐름이 한 local run에서 완료된다 | VG-012 |
| PRD-FR-011 | Phase 1 | 필수 | PLANNED | patch와 diff는 ephemeral workspace에만 적용되고 외부 write는 발생하지 않는다 | VG-013, VG-015 |
| PRD-FR-012 | Phase 1 | 필수 | PLANNED | task test, regression test, lint, typecheck가 trusted profile과 fresh evidence로 판정된다 | VG-013 |
| PRD-FR-013 | Phase 1 | 필수 | PLANNED | budget, cancellation, cleanup, 기본 trace viewer가 terminal path를 설명한다 | VG-014, VG-015 |
| PRD-FR-014 | Phase 2 | 필수 | PLANNED | failure signature와 diagnosis evidence bundle이 환경·의존성·테스트·구현 실패를 분류한다 | VG-016 |
| PRD-FR-015 | Phase 2 | 필수 | PLANNED | bounded repair가 새 evidence가 있을 때만 재시도하고 no-progress에서 중단한다 | VG-016 |
| PRD-FR-016 | Phase 2 | 필수 | PLANNED | execution, rule, rubric, human evaluation이 결정론적 실패를 덮지 않는다 | VG-017 |
| PRD-FR-017 | Phase 2 | 필수 | PLANNED | benchmark runner와 hidden evaluator가 고정 dataset, 반복, paired 통계를 제공한다 | VG-018 |
| PRD-FR-018 | Phase 3 | 필수 | PLANNED | GitHub Issue와 CI를 입력으로 받고 exact approval 후 draft PR만 생성한다 | VG-019 |
| PRD-FR-019 | Phase 3 | 필수 | PLANNED | organization RBAC, approval, audit export가 tenant와 actor 경계를 보존한다 | VG-020 |
| PRD-FR-020 | Phase 3 | 권장 | PLANNED | MCP adapter registry와 trust policy가 allowlist, scope, credential, output을 통제한다 | VG-020 |
| PRD-FR-021 | Phase 3 | 권장 | PLANNED | remote worker, durable queue, webhook deduplication이 idempotent 처리와 상태 복구를 제공한다 | VG-020 |
| PRD-FR-022 | Phase 4 | 필수 | PLANNED | multi-tenant scale과 stronger isolation이 tenant leakage와 sandbox escape를 차단한다 | VG-021, VG-022 |
| PRD-FR-023 | Phase 4 | 권장 | PLANNED | language/framework plugin이 closed trust policy와 compatibility gate를 통과한다 | VG-023 |
| PRD-FR-024 | Phase 4 | 권장 | PLANNED | code graph, richer static analysis, security remediation이 근거와 검증을 제공한다 | VG-023 |
| PRD-FR-025 | Phase 4 | 권장 | PLANNED | replay, experiment, continuous quality loop가 원본 identity와 외부 효과 경계를 보존한다 | VG-017, VG-018, VG-022 |

Keep every ID, phase, priority, maturity, and VG reference exactly as listed. Use the Requirement and observable acceptance text as the normative row content and add one rationale sentence tied to the product problem. Do not add schedule or implementation steps.

- [ ] **Step 5: Add nonfunctional requirements**

Create one table with the same metadata fields and exactly these rows:

| ID | Scope | Priority | Maturity | Requirement and observable acceptance | VG |
| --- | --- | --- | --- | --- | --- |
| PRD-NFR-001 | 전 단계 | 필수 | SPECIFIED | 성공 주장은 요구 floor의 fresh evidence를 가지며 결정론적 실패가 정성 점수로 뒤집히지 않는다 | VG-001, VG-023 |
| PRD-NFR-002 | 전 단계 | 필수 | SPECIFIED | RESOURCE, COMMAND, NETWORK, destructive, external effect authority가 exact match와 fail-closed를 적용한다 | VG-005, VG-006, VG-007 |
| PRD-NFR-003 | Phase 0~4 | 필수 | PLANNED | 원본과 실행 환경을 분리하고 sandbox 종료 후 resource가 남지 않는다 | VG-008, VG-014 |
| PRD-NFR-004 | 전 단계 | 필수 | SPECIFIED | secret, private payload, raw log, artifact가 redaction, encryption, retention, tenant isolation을 따른다 | VG-009 |
| PRD-NFR-005 | Phase 1~4 | 필수 | PLANNED | idempotency, cancellation, replay, cleanup, recovery가 중복 외부 효과와 상태 손실을 막는다 | VG-014, VG-015, VG-019 |
| PRD-NFR-006 | Phase 0~4 | 필수 | SPECIFIED | trace, event, manifest, audit가 task, run, revision, actor, evidence 관계를 해석 가능하게 보존한다 | VG-004, VG-015 |
| PRD-NFR-007 | Phase 4 | 필수 | PLANNED | event p99 2초, cleanup p99 60초·hard max 5분, trace 99.5%, manifest 99.9%, R2 95%, API 99.9% 목표를 측정한다 | VG-022 |
| PRD-NFR-008 | 전 단계 | 필수 | SPECIFIED | 시간, token, tool, command, repair, 비용 budget을 강제하고 초과 시 명시적으로 중단한다 | VG-014 |
| PRD-NFR-009 | 전 단계 | 권장 | SPECIFIED | core contract는 model, host, provider에 독립적이고 adapter가 capability를 정규화한다 | VG-001, VG-023 |
| PRD-NFR-010 | Phase 2~4 | 필수 | SPECIFIED | dataset version/hash, 최소 반복, paired CI, judge version, 이중 판정으로 평가 재현성을 보장한다 | VG-017, VG-018 |
| PRD-NFR-011 | Phase 1~4 | 권장 | PLANNED | 사용자가 상태, 이유, 위험, diff, 검증, 승인, 다음 행동을 한 workflow에서 이해한다 | VG-015, VG-024 |
| PRD-NFR-012 | Phase 3~4 | 필수 | PLANNED | tenant, credential, integration, plugin, worker 경계가 zero-event security invariants를 유지한다 | VG-020, VG-021 |

- [ ] **Step 6: Add Exit gates, metrics, and research success**

Include these exact release-level gates:

- Phase 0: example schema와 Harness conformance 통과, invalid transition/authority와 approval deny/expiry/nonce reuse fail-closed, sandbox containment와 secret fixture 100%.
- Phase 1: 모든 필수 criterion E2 이상, unauthorized execution 0, cleanup failure 0, external write 0.
- Phase 2: 최소 5회 반복과 사전 고정 평가 계약, unauthorized action 0, raw secret 0, critical injection escape 0, task-success paired 95% CI lower bound greater than 0, regression-rate paired 95% CI upper bound less than 0.
- Phase 3: idempotency, expired approval, duplicate webhook, unauthorized external write 시험 통과.
- Phase 4: rolling 30-day SLO 충족과 security invariant 위반 0.

Include the handoff metric definitions for task success, regression, recovery, no-progress, unauthorized action, injection escape, unrelated change, human revert, latency, cost. Mark every SLO as PLANNED target, not current measurement.

- [ ] **Step 7: Validate PRD structure and identifiers**

Run:

~~~powershell
$path = 'docs/product/prd.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding utf8
$fr = [regex]::Matches($text, '(?m)^\|\s*(PRD-FR-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
$nfr = [regex]::Matches($text, '(?m)^\|\s*(PRD-NFR-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
if ($fr.Count -ne 25) { throw "Expected 25 functional requirements, found $($fr.Count)" }
if ($nfr.Count -ne 12) { throw "Expected 12 nonfunctional requirements, found $($nfr.Count)" }
if (($fr | Sort-Object -Unique).Count -ne 25) { throw 'Duplicate functional requirement ID' }
if (($nfr | Sort-Object -Unique).Count -ne 12) { throw 'Duplicate nonfunctional requirement ID' }
foreach ($phase in 0..4) {
  if (-not $text.Contains("Phase $phase")) { throw "Missing Phase $phase" }
}
if ($text.Contains('제품 runtime이 현재 구현됨')) { throw 'Unverified runtime claim' }
'PRD_VALIDATE=PASS'
~~~

Expected: PRD_VALIDATE=PASS.

- [ ] **Step 8: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/product/prd.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps product requirements'
~~~

Expected: only the intended PRD change plus previously known user changes. Do not write .git unless new explicit commit authority exists.

---

### Task 2: System Architecture

**Files:**
- Create: docs/architecture/system-architecture.md
- Read: docs/product/prd.md
- Read: docs/handoff/forgeops-full-handoff.md

**Interfaces:**
- Consumes: PRD-FR-001~025 and PRD-NFR-001~012
- Produces: ARC-001~ARC-014, state mapping, contract and data-flow diagrams

- [ ] **Step 1: Verify the PRD dependency and target**

Run:

~~~powershell
if (-not (Test-Path -LiteralPath 'docs/product/prd.md')) { throw 'PRD dependency missing' }
if (Test-Path -LiteralPath 'docs/architecture/system-architecture.md') {
  throw 'STOP: architecture target already exists; inspect ownership.'
}
git status --short
~~~

Expected: PRD exists and architecture target does not.

- [ ] **Step 2: Create the architecture outline**

Use apply_patch with these sections:

~~~markdown
# ForgeOps 시스템 아키텍처

## 1. 목적과 범위
## 2. 현재와 목표 경계
## 3. 시스템 컨텍스트
## 4. 논리적 구성요소
## 5. 권한과 신뢰 경계
## 6. 상태 모델과 소유권
## 7. 핵심 실행 흐름
## 8. Contract와 schema
## 9. 데이터·event·evidence 흐름
## 10. Snapshot·sandbox·verification
## 11. Replay와 외부 통합
## 12. 단계별 배치와 기술 결정
## 13. 관련 문서
~~~

- [ ] **Step 3: Define the architecture catalog**

Create a table with ID, Maturity, Responsibility, Dependencies, Related requirements. Define exactly:

| ID | Maturity | Responsibility |
| --- | --- | --- |
| ARC-001 | IMPLEMENTED | Portable Harness Foundation의 Main, Part, Work와 adapter/profile 경계 |
| ARC-002 | SPECIFIED | Product layer와 Protocol 2.0 사이의 비약화 경계 |
| ARC-003 | PLANNED | Control Plane의 task, approval, budget, RBAC, queue 책임 |
| ARC-004 | PLANNED | Orchestration Engine의 normalize, route, state, decision 책임 |
| ARC-005 | PLANNED | Repository Context Engine의 snapshot index, retrieval, Context Pack 책임 |
| ARC-006 | PLANNED | Tool Gateway와 MCP의 catalog, policy, credential, action 분해 책임 |
| ARC-007 | PLANNED | Ephemeral Workspace와 sandbox containment 책임 |
| ARC-008 | PLANNED | Verification, Recovery, Evaluation Engine 책임 |
| ARC-009 | SPECIFIED | Product workflow state와 canonical accepted state의 mapping 및 CANCELLED gap |
| ARC-010 | SPECIFIED | Product Task Contract와 TaskPacket bridge |
| ARC-011 | SPECIFIED | durable event, run manifest, evidence, artifact provenance |
| ARC-012 | SPECIFIED | data model, versioned API, realtime event stream |
| ARC-013 | SPECIFIED | approval-bound external effects와 replay modes |
| ARC-014 | PLANNED | Phase별 deployment topology와 기술 결정 경계 |

ARC-001 must link to the implemented prompt files. Every other row must reference one or more PRD IDs without claiming runtime implementation.

- [ ] **Step 4: Add four diagrams**

Add Mermaid diagrams with these nodes and flows:

1. Context: User/Reviewer → Control Plane → Orchestration → Context Engine, Tool Gateway, Sandbox, Verification/Recovery/Evaluation, Trace/Artifact; publisher is the only path to external SCM.
2. Main flow: Main normalize/route → Part context/plan → Main candidate decision → Work preflight/execute/verify → Main evidence validation/accepted state.
3. State ownership: product states map to Protocol statuses; only MainDecision owns accepted state, revision, seq; Part/Work emit proposals; product CANCELLED stays product-only until a versioned Protocol change.
4. Evidence flow: trusted source/profile → action → observation → evidence catalog → acceptance criterion → MainDecision → manifest/trace.

Label IMPLEMENTED, SPECIFIED, PLANNED boundaries directly in diagram nodes or adjacent legends.

- [ ] **Step 5: Add contract and boundary tables**

Include:

- Task Contract to TaskPacket mapping fields and the rule that Contract never grants authority.
- Closed product replay modes AUDIT_REPLAY, REEXECUTE, COUNTERFACTUAL and their Harness mapping.
- API/event/manifest identity fields: task, run, correlation, base revision, event sequence, source task/run/manifest, schema version, hash/provenance.
- Product CANCELLED handling and versioned Protocol integration block.
- Snapshot identity versus conversation/task revision; Git SHA is repository identity, not rollback or task revision proof.
- Technology choices remain decision records inside this document until a later approved ADR workflow; do not select Temporal/Celery, S3/MinIO, Docker/stronger isolation as simultaneous defaults.

- [ ] **Step 6: Validate architecture definitions and boundaries**

Run:

~~~powershell
$path = 'docs/architecture/system-architecture.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding utf8
$ids = [regex]::Matches($text, '(?m)^\|\s*(ARC-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
if ($ids.Count -ne 14) { throw "Expected 14 ARC definitions, found $($ids.Count)" }
if (($ids | Sort-Object -Unique).Count -ne 14) { throw 'Duplicate ARC definition' }
$must = @('MainDecision', 'CANCELLED', 'AUDIT_REPLAY', 'REEXECUTE', 'COUNTERFACTUAL', 'source_manifest_id')
foreach ($term in $must) {
  if (-not $text.Contains($term)) { throw "Missing architecture contract: $term" }
}
$fences = [regex]::Matches($text, '(?m)^~~~').Count
if (($fences % 2) -ne 0) { throw 'Unbalanced Markdown fence' }
'ARCH_VALIDATE=PASS'
~~~

Expected: ARCH_VALIDATE=PASS.

- [ ] **Step 7: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/architecture/system-architecture.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps system architecture'
~~~

Expected: the complete architecture document is visible for review and status shows the intended untracked file.

Do not write .git without new explicit commit authority.

---

### Task 3: Threat Model

**Files:**
- Create: docs/security/threat-model.md
- Read: docs/product/prd.md
- Read: docs/architecture/system-architecture.md

**Interfaces:**
- Consumes: PRD security requirements and ARC trust boundaries
- Produces: THR-001~THR-012, CTL-001~CTL-020, negative-gate mapping

- [ ] **Step 1: Verify dependencies and target ownership**

Run:

~~~powershell
foreach ($path in @('docs/product/prd.md', 'docs/architecture/system-architecture.md')) {
  if (-not (Test-Path -LiteralPath $path)) { throw "Missing dependency: $path" }
}
if (Test-Path -LiteralPath 'docs/security/threat-model.md') {
  throw 'STOP: threat model target already exists; inspect ownership.'
}
git status --short
~~~

- [ ] **Step 2: Create the threat-model outline**

Use these sections:

~~~markdown
# ForgeOps 위협 모델

## 1. 목적과 방법
## 2. 보호 자산
## 3. 공격자와 신뢰 가정
## 4. 신뢰 경계
## 5. 위협 카탈로그
## 6. 보안 통제 카탈로그
## 7. 위협·통제·검증 매핑
## 8. Phase별 보안 gate
## 9. 잔여 위험과 변경 규칙
## 10. 관련 문서
~~~

Assets must include source snapshot, user changes, credentials, approval capability, validation profile, evidence, artifact, event/manifest, tenant data, external effect identity.

- [ ] **Step 3: Add the threat catalog**

Define exactly:

| ID | Threat |
| --- | --- |
| THR-001 | repository, Issue, log, MCP output의 prompt injection이 control instruction으로 승격 |
| THR-002 | path traversal, protected resource 접근, 사용자 변경 덮어쓰기 |
| THR-003 | raw command 주입, command profile 변조, authority normalization |
| THR-004 | SSRF, DNS rebinding, redirect, metadata/private network 접근 |
| THR-005 | sandbox escape, host namespace/device/socket/mount 노출 |
| THR-006 | 무권한 외부 효과, destructive action, approval replay 또는 scope 확대 |
| THR-007 | secret, credential, private payload, raw log 유출 |
| THR-008 | artifact 변조, tenant 간 접근, retention/deletion 실패 |
| THR-009 | replay, retry, webhook 중복으로 비멱등 효과 재실행 |
| THR-010 | forged, stale, future, wrong-revision evidence와 event identity 혼합 |
| THR-011 | test 조작, baseline 오염, verification bypass, rubric override |
| THR-012 | resource exhaustion, budget 우회, no-progress loop, cleanup 잔존 |

Each row includes asset, actor, precondition, attack path, impact, target phase, related PRD-NFR.

- [ ] **Step 4: Add the control catalog**

Every control row has ID, Requirement, Severity, phase_blocking, Target Phase, Related THR, Negative VG, Residual risk. Define:

| ID | Severity | phase_blocking | Control |
| --- | --- | --- | --- |
| CTL-001 | CRITICAL | true | 비신뢰 data와 control plane 분리 및 injection 승격 차단 |
| CTL-002 | CRITICAL | true | RESOURCE canonical root-relative exact authority와 protected-resource preflight |
| CTL-003 | CRITICAL | true | COMMAND id, command, cwd 3중 exact match와 NAMED_COMMANDS |
| CTL-004 | CRITICAL | true | NETWORK canonical host:port exact match와 normalization 금지 |
| CTL-005 | CRITICAL | true | capability AVAILABLE, approved candidate, current revision, preflight 교집합 |
| CTL-006 | CRITICAL | true | destructive_actions와 external_side_effects 별도 hard gate |
| CTL-007 | CRITICAL | true | approval signature, issuer/audience/tenant, all-input hash binding, atomic nonce |
| CTL-008 | CRITICAL | true | replay mode hard deny, 새 identity, unknown outcome reconcile |
| CTL-009 | CRITICAL | true | signed digest-pinned image와 provenance 검증 |
| CTL-010 | CRITICAL | true | rootless, read-only rootfs, namespace/mount/device/socket hardening |
| CTL-011 | CRITICAL | true | CPU/memory/PID/disk/log/time quota와 verified teardown |
| CTL-012 | CRITICAL | true | egress proxy, forbidden address ranges, rebinding/TOCTOU, redirect deny |
| CTL-013 | CRITICAL | true | pre-storage/export secret redaction, raw secret hash 금지 |
| CTL-014 | CRITICAL | true | encrypted quarantine, tenant isolation, retention, tamper-evident artifact |
| CTL-015 | CRITICAL | true | closed evidence type와 revision/time freshness validation |
| CTL-016 | HIGH | true | trusted baseline, test anti-tamper, deterministic result precedence |
| CTL-017 | HIGH | true | bounded budget, failure signature, no-progress stop |
| CTL-018 | HIGH | true | MCP allowlist, scoped credential, schema/size/timeout/redaction |
| CTL-019 | CRITICAL | true | idempotency key, webhook dedup, non-idempotent retry block |
| CTL-020 | CRITICAL | true | complete audit trace와 zero-event security invariant release block |

Severity downgrade requires changed threat premise, substitute control, verification evidence, RTM and risk updates in one change.

- [ ] **Step 5: Add exact threat-to-control mapping**

Use this minimum mapping:

| THR | CTL | Negative VG |
| --- | --- | --- |
| THR-001 | CTL-001, CTL-018 | VG-011, VG-020 |
| THR-002 | CTL-002, CTL-005 | VG-005 |
| THR-003 | CTL-003, CTL-005 | VG-006 |
| THR-004 | CTL-004, CTL-012 | VG-006, VG-008 |
| THR-005 | CTL-009, CTL-010, CTL-011 | VG-008 |
| THR-006 | CTL-005, CTL-006, CTL-007 | VG-007 |
| THR-007 | CTL-013, CTL-014 | VG-009 |
| THR-008 | CTL-014, CTL-020 | VG-009, VG-021 |
| THR-009 | CTL-008, CTL-019 | VG-019, VG-020 |
| THR-010 | CTL-015, CTL-020 | VG-003, VG-023 |
| THR-011 | CTL-016, CTL-020 | VG-013, VG-017 |
| THR-012 | CTL-011, CTL-017 | VG-014, VG-016 |

State that any orphan THR, CTL, or negative VG blocks document baselining.

- [ ] **Step 6: Validate security closure**

Run:

~~~powershell
$path = 'docs/security/threat-model.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding utf8
$thr = [regex]::Matches($text, '(?m)^\|\s*(THR-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
$ctl = [regex]::Matches($text, '(?m)^\|\s*(CTL-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
if (($thr | Sort-Object -Unique).Count -ne 12) { throw 'Threat catalog must define 12 unique IDs' }
if (($ctl | Sort-Object -Unique).Count -ne 20) { throw 'Control catalog must define 20 unique IDs' }
foreach ($id in ($thr | Sort-Object -Unique)) {
  if (([regex]::Matches($text, [regex]::Escape($id))).Count -lt 2) { throw "Unmapped threat: $id" }
}
foreach ($id in ($ctl | Sort-Object -Unique)) {
  if (([regex]::Matches($text, [regex]::Escape($id))).Count -lt 2) { throw "Unmapped control: $id" }
}
'SECURITY_VALIDATE=PASS'
~~~

Expected: SECURITY_VALIDATE=PASS.

- [ ] **Step 7: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/security/threat-model.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps threat model'
~~~

Expected: the full threat model is visible and no out-of-scope modification was made.

Do not write .git without new explicit commit authority.

---

### Task 4: Verification and Evaluation Plan

**Files:**
- Create: docs/quality/verification-and-evaluation-plan.md
- Read: docs/product/prd.md
- Read: docs/architecture/system-architecture.md
- Read: docs/security/threat-model.md

**Interfaces:**
- Consumes: 37 PRD requirements and THR/CTL catalogs
- Produces: VG-001~VG-024, evidence contract, phase gates, evaluation rules

- [ ] **Step 1: Verify dependencies**

Run:

~~~powershell
foreach ($path in @(
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md'
)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing dependency: $path" }
}
if (Test-Path -LiteralPath 'docs/quality/verification-and-evaluation-plan.md') {
  throw 'STOP: quality target already exists; inspect ownership.'
}
git status --short
~~~

Expected: both dependencies exist, quality target is absent, and current user changes are reviewed.

- [ ] **Step 2: Create the quality-plan outline**

Use:

~~~markdown
# ForgeOps 검증 및 평가 계획

## 1. 목적과 범위
## 2. 검증 원칙
## 3. Evidence 계약
## 4. 검증 계층
## 5. 품질 게이트 카탈로그
## 6. Phase별 Exit 판정
## 7. 평가 지표와 실행 계약
## 8. 실패·NOT_RUN·baseline unhealthy 처리
## 9. 포트폴리오 증빙 패키지
## 10. 문서 자체 검증
## 11. 관련 문서
~~~

- [ ] **Step 3: Define evidence and verdict semantics**

State exactly:

- Evidence type is file, diff, command, test, render, runtime, approval.
- file/diff require observed_revision equal to base_revision and forbid observed_at.
- command/test/render/runtime/approval require runtime-supplied strict UTC observed_at, forbid observed_revision, and must be 0~300 seconds old relative to trusted validationAt.
- E0 < E1 < E2 < E3; requirement success needs evidence at or above its floor.
- verification_profile_id and trusted command_id identify planned execution; raw command text is not evidence or authority.
- PASSED requires resolved fresh evidence refs; FAILED preserves evidence; NOT_RUN has no evidence tier/ref/time and records a reason.
- deterministic verification failure and security violation cannot be overridden by rubric or overall score.
- baseline_blocked, policy_blocked, inconclusive stay distinct from pass.

- [ ] **Step 4: Add the VG catalog**

Each row has ID, Target Phase, Scope, Method or trusted profile, Evidence floor, Pass condition, Fail-closed result, Related PRD/CTL. Define:

| ID | Phase | Gate | Floor |
| --- | --- | --- | --- |
| VG-001 | Foundation/0 | Harness conformance and sample fixture | E2 |
| VG-002 | Phase 0 | Contract to TaskPacket bridge schema and non-grant rule | E2 |
| VG-003 | Phase 0 | state transition, revision, event sequence, CANCELLED mapping | E2 |
| VG-004 | Phase 0 | OpenAPI, event wrapper, manifest schema and reference resolution | E2 |
| VG-005 | Phase 0 | RESOURCE scope, path, protected resource negative cases | E2 |
| VG-006 | Phase 0 | COMMAND/NETWORK exact identity and normalization negative cases | E2 |
| VG-007 | Phase 0 | destructive/external gate and approval binding/expiry/nonce negative cases | E2 |
| VG-008 | Phase 0/1 | sandbox containment, hardening, egress, teardown negative cases | E3 |
| VG-009 | Phase 0/1 | secret leakage across packet/event/artifact/trace/exporter and artifact isolation | E3 |
| VG-010 | Phase 1 | snapshot identity, baseline, retrieval reproducibility | E2 |
| VG-011 | Phase 1 | Context Pack provenance and injection escape suite | E2 |
| VG-012 | Phase 1 | local Main→Part→Work→Main vertical flow | E2 |
| VG-013 | Phase 1 | patch/diff, test/lint/typecheck, regression and anti-tamper | E2 |
| VG-014 | Phase 1 | budget, cancellation, process-tree cleanup, no-progress | E2 |
| VG-015 | Phase 1 | trace/manifest completeness and unauthorized external write 0 | E2 |
| VG-016 | Phase 2 | failure classification and bounded repair stop | E2 |
| VG-017 | Phase 2 | evaluation contract, judge anchoring, double rating, deterministic precedence | E3 |
| VG-018 | Phase 2 | repeated benchmark and paired go/no-go statistics | E3 |
| VG-019 | Phase 3 | GitHub effect approval, idempotency, unknown outcome reconcile | E3 |
| VG-020 | Phase 3 | RBAC, audit, MCP trust, webhook dedup, remote worker boundary | E3 |
| VG-021 | Phase 4 | multi-tenant isolation and stronger sandbox | E3 |
| VG-022 | Phase 4 | rolling 30-day SLO and zero-event security invariants | E3 |
| VG-023 | 전 단계 | closed evidence type, tier, freshness, reference integrity | E2 |
| VG-024 | Phase 1 Exit | public-safe portfolio package and redaction/license scan | E2 |

For every CRITICAL CTL, link at least one negative VG and state that PARTIAL, GAP, NOT_RUN, or failed evidence blocks its target Phase Exit.

- [ ] **Step 5: Add metrics and phase decisions**

Copy the formulas, not only metric names, for task success, regression, recovery, no-progress, unauthorized action, injection escape, unrelated changes, human revert, latency, and cost. Include:

- dev/test/hidden split with schema version and content hash.
- same snapshot, Contract, input, image, policy, verification profile, tool schema, and budgets per variant.
- at least 5 stochastic repeats; infrastructure failures remain reported.
- power analysis and target confidence width determine sample size.
- paired delta with stratified bootstrap 95% CI.
- fixed anonymous 1~5 rubric; at least 20% double rating; weighted kappa below 0.6 forces rubric revision and re-rating.
- exact Phase 2 go/no-go inequalities from PRD.

- [ ] **Step 6: Define the public-safe evidence package**

Require public-safe demo fixture, reproduction steps, redacted trace and diff, metrics, manifest hash. Forbid credentials, private repository content, tenant identifiers, raw logs, and unclear-license code. State that passing the package gate does not authorize external publication.

- [ ] **Step 7: Validate VG coverage**

Run:

~~~powershell
$path = 'docs/quality/verification-and-evaluation-plan.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding utf8
$ids = [regex]::Matches($text, '(?m)^\|\s*(VG-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
if (($ids | Sort-Object -Unique).Count -ne 24) { throw 'Expected 24 unique VG definitions' }
foreach ($term in @('observed_revision', 'observed_at', 'validationAt', '0~300', 'weighted kappa', 'public-safe')) {
  if (-not $text.Contains($term)) { throw "Missing quality contract: $term" }
}
'QUALITY_VALIDATE=PASS'
~~~

Expected: QUALITY_VALIDATE=PASS.

- [ ] **Step 8: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/quality/verification-and-evaluation-plan.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps verification and evaluation plan'
~~~

Expected: the full quality plan is visible and the status contains only intended work plus preserved user changes.

Do not write .git without new explicit commit authority.

---

### Task 5: Ten-Week WBS

**Files:**
- Create: docs/project/wbs.md
- Read: docs/product/prd.md
- Read: docs/architecture/system-architecture.md
- Read: docs/security/threat-model.md
- Read: docs/quality/verification-and-evaluation-plan.md

**Interfaces:**
- Consumes: PRD requirements and VG-001~024
- Produces: WBS-001~WBS-035, W1~W10 capacity plan, dependencies, Definition of Done

- [ ] **Step 1: Verify dependencies and target**

Run:

~~~powershell
foreach ($path in @(
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md'
)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing dependency: $path" }
}
if (Test-Path -LiteralPath 'docs/project/wbs.md') {
  throw 'STOP: WBS target already exists; inspect ownership.'
}
git status --short
~~~

Expected: PRD and quality plan exist, WBS target is absent, and current changes are reviewed.

- [ ] **Step 2: Create the WBS outline**

Use:

~~~markdown
# ForgeOps 작업 분해 구조

## 1. 계획 목적과 기준
## 2. 일정과 용량 가정
## 3. 상태와 변경 규칙
## 4. W1~W10 작업 패키지
## 5. Phase 2~4 상위 마일스톤
## 6. Critical path
## 7. 주간 운영과 재계획 trigger
## 8. 포트폴리오 checkpoint
## 9. 관련 문서
~~~

Every detailed item has ID, Phase, Week, Status, person-day, Predecessor, PRD IDs, Deliverable, Definition of Done, VG IDs, Expected evidence type.

- [ ] **Step 3: Add W1~W4 Phase 0 packages**

| ID | Week | pd | Predecessor | Deliverable |
| --- | --- | --- | --- | --- |
| WBS-001 | W1 | 1.0 | 없음 | Harness baseline inventory and evidence links |
| WBS-002 | W1 | 2.0 | WBS-001 | Product Contract schema and TaskPacket bridge |
| WBS-003 | W1 | 1.0 | WBS-002 | bridge review and portfolio checkpoint |
| WBS-004 | W2 | 2.0 | WBS-002 | state transition validator and mapping fixture |
| WBS-005 | W2 | 2.0 | WBS-004 | authority/approval policy matrix and negative fixture |
| WBS-006 | W3 | 1.5 | WBS-002 | versioned OpenAPI schema |
| WBS-007 | W3 | 1.0 | WBS-004 | durable event wrapper schema |
| WBS-008 | W3 | 1.5 | WBS-006, WBS-007 | run manifest schema and reference rules |
| WBS-009 | W4 | 1.0 | WBS-006, WBS-008 | sample repository and benchmark fixture |
| WBS-010 | W4 | 1.5 | WBS-005, WBS-009 | sandbox containment PoC |
| WBS-011 | W4 | 1.0 | WBS-005, WBS-009 | redaction and artifact fixture |
| WBS-012 | W4 | 0.5 | WBS-009, WBS-010, WBS-011 | Phase 0 Exit report |

Use WBS_NOT_STARTED for every initial status. Each week totals exactly 4.0 planned person-day.

- [ ] **Step 4: Add W5~W7 core workflow packages**

| ID | Week | pd | Predecessor | Deliverable |
| --- | --- | --- | --- | --- |
| WBS-013 | W5 | 1.5 | WBS-012 | immutable snapshot provider |
| WBS-014 | W5 | 1.5 | WBS-013 | baseline runner and baseline artifact |
| WBS-015 | W5 | 1.0 | WBS-013 | code retrieval and Context Pack |
| WBS-016 | W6 | 1.0 | WBS-014, WBS-015 | Main normalization and routing |
| WBS-017 | W6 | 1.0 | WBS-016 | Part context and plan proposal |
| WBS-018 | W6 | 1.0 | WBS-017 | Work preflight, execute, verify |
| WBS-019 | W6 | 1.0 | WBS-018 | Main evidence validation and accepted decision |
| WBS-020 | W7 | 1.5 | WBS-019 | patch and diff pipeline |
| WBS-021 | W7 | 1.5 | WBS-014, WBS-020 | trusted test/lint/typecheck profiles |
| WBS-022 | W7 | 1.0 | WBS-021 | regression and test anti-tamper guard |

- [ ] **Step 5: Add W8~W10 reliability and Exit packages**

| ID | Week | pd | Predecessor | Deliverable |
| --- | --- | --- | --- | --- |
| WBS-023 | W8 | 1.0 | WBS-019 | budget enforcement |
| WBS-024 | W8 | 1.5 | WBS-019, WBS-023 | cancellation and verified cleanup |
| WBS-025 | W8 | 1.5 | WBS-019, WBS-024 | basic trace viewer |
| WBS-026 | W9 | 1.5 | WBS-010, WBS-011, WBS-024 | security negative suite |
| WBS-027 | W9 | 1.5 | WBS-021, WBS-022, WBS-026 | required E2 criterion evidence run |
| WBS-028 | W9 | 1.0 | WBS-024, WBS-025, WBS-027 | Phase 1 safety gate |
| WBS-029 | W10 | 1.5 | WBS-028 | local vertical slice demonstration |
| WBS-030 | W10 | 1.0 | WBS-029 | regression run and Phase 1 Exit report |
| WBS-031 | W10 | 1.0 | WBS-030 | public-safe portfolio package |
| WBS-032 | W10 | 0.5 | WBS-030, WBS-031 | retrospective and next-phase decision record |

- [ ] **Step 6: Add high-level Phase 2~4 milestones**

Define without confirmed week or person-day:

| ID | Phase | Predecessor | Exit |
| --- | --- | --- | --- |
| WBS-033 | Phase 2 | WBS-032 | bounded repair and benchmark go/no-go |
| WBS-034 | Phase 3 | WBS-033 | controlled GitHub integration, RBAC, audit, dedup gates |
| WBS-035 | Phase 4 | WBS-034 | rolling SLO, zero security violations, plugin maturity |

Use N/A (상위 마일스톤) for week and person-day. Do not add a detailed sprint or fixed date.

- [ ] **Step 7: Add capacity, critical path, and replan rules**

State:

- Weekly capacity is 5 person-day: 4 planned, 1 buffer.
- Replan when planned load exceeds 4, a Phase gate misses its week, a security invariant fails, or carry-over occurs for two consecutive weeks.
- Do not pull future work forward automatically after a failed gate.
- Critical path starts WBS-001→002→004→005→010→012→013→014→016→017→018→019→020→021→022→026→027→028→029→030.
- Every Definition of Done names a deliverable and VG, but expected evidence is not recorded as current fresh evidence.

- [ ] **Step 8: Validate WBS counts and capacity**

Run:

~~~powershell
$path = 'docs/project/wbs.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding utf8
$ids = [regex]::Matches($text, '(?m)^\|\s*(WBS-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
if (($ids | Sort-Object -Unique).Count -ne 35) { throw 'Expected 35 unique WBS definitions' }
foreach ($week in 1..10) {
  if (-not $text.Contains("W$week")) { throw "Missing W$week" }
}
foreach ($term in @('주당 5 person-day', '4 person-day', '1 person-day', 'WBS_NOT_STARTED')) {
  if (-not $text.Contains($term)) { throw "Missing WBS rule: $term" }
}
'WBS_VALIDATE=PASS'
~~~

Expected: WBS_VALIDATE=PASS.

- [ ] **Step 9: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/project/wbs.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps ten-week WBS'
~~~

Expected: the full WBS is visible, including W1~W10 and WBS-033~035.

Do not write .git without new explicit commit authority.

---

### Task 6: Risk Register

**Files:**
- Create: docs/project/risk-register.md
- Read: docs/product/prd.md
- Read: docs/project/wbs.md
- Read: docs/security/threat-model.md
- Read: docs/quality/verification-and-evaluation-plan.md

**Interfaces:**
- Consumes: requirements, schedule, threats, controls
- Produces: RSK-001~RSK-014 with trigger, response, target week, linked IDs

- [ ] **Step 1: Verify dependencies and create the outline**

Run:

~~~powershell
foreach ($path in @(
  'docs/product/prd.md',
  'docs/project/wbs.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md'
)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing dependency: $path" }
}
if (Test-Path -LiteralPath 'docs/project/risk-register.md') {
  throw 'STOP: risk target already exists; inspect ownership.'
}
git status --short
~~~

Expected: all dependencies exist and the risk-register target is absent.

Use apply_patch to create:

~~~markdown
# ForgeOps 위험 등록부

## 1. 목적과 운영 규칙
## 2. 점수와 상태
## 3. 위험 카탈로그
## 4. 주간 검토 절차
## 5. Escalation과 Phase gate
## 6. 관련 문서
~~~

Probability and impact each use 1~5; score is their product. Status is OPEN, MITIGATING, MONITORING, CLOSED.

- [ ] **Step 2: Add the risk catalog**

Every row has ID, Category, Probability, Impact, Score, Trigger, Prevention, Contingency, Related PRD/THR/CTL/WBS, Target review, Status. Use:

| ID | P | I | Score | Risk | Target |
| --- | --- | --- | --- | --- | --- |
| RSK-001 | 4 | 4 | 16 | 10주 범위 확장과 Phase 2~4 상세화 | W1, weekly |
| RSK-002 | 3 | 5 | 15 | Product와 Protocol 2.0 contract drift | W2 |
| RSK-003 | 3 | 5 | 15 | product state, replay, run identity 혼합 | W2 |
| RSK-004 | 4 | 5 | 20 | host에서 요구 sandbox 격리 달성 불가 | W4 |
| RSK-005 | 3 | 5 | 15 | exact authority 또는 approval policy 오구성 | W2, W4 |
| RSK-006 | 3 | 5 | 15 | secret, raw log, artifact, tenant 정보 유출 | W4, W10 |
| RSK-007 | 3 | 4 | 12 | baseline 불건전, test 조작, stale evidence | W5, W7, W9 |
| RSK-008 | 3 | 4 | 12 | benchmark 표본 부족, judge bias, 통계 오해 | Phase 2 entry |
| RSK-009 | 2 | 5 | 10 | 외부 effect 중복, unknown outcome, webhook replay | Phase 3 entry |
| RSK-010 | 3 | 3 | 9 | 기술 선택과 운영 복잡도가 Exit gate를 초과 | each Phase entry |
| RSK-011 | 4 | 4 | 16 | 1인 개발 용량 부족과 연속 carry-over | weekly |
| RSK-012 | 3 | 4 | 12 | 문서 간 ID drift와 orphan trace | every document change |
| RSK-013 | 2 | 5 | 10 | 포트폴리오 공개 시 privacy, secret, license 위반 | W10 |
| RSK-014 | 2 | 4 | 8 | dependency, API, cloud 사용의 material cost | before any paid service |

Set all initial statuses to OPEN. Use these exact prevention and contingency anchors:

| Risk | Prevention | Contingency |
| --- | --- | --- |
| RSK-001 | lock PRD scope and WBS capacity | move only Phase 2~4 detail to successor plan |
| RSK-002 | ARC-002/009/010 and VG-001~003 conformance review | block merge and restore the last compatible contract |
| RSK-003 | ARC-009/013 identity matrix and VG-003/019 | stop replay and require a versioned identity decision |
| RSK-004 | WBS-010 early containment PoC and CTL-009~012 | require gVisor, Kata, microVM, or dedicated worker before continuation |
| RSK-005 | CTL-002~007 negative fixtures | deny action, invalidate approval, and reopen WBS-005 |
| RSK-006 | CTL-013/014 and VG-009/024 | quarantine or delete artifact, revoke credential, open security incident |
| RSK-007 | trusted baseline profile and CTL-015/016 | mark BASELINE_UNHEALTHY or NOT_RUN and block success |
| RSK-008 | fixed dataset/hash, power analysis, paired CI | report insufficient evidence and expand the predeclared evaluation |
| RSK-009 | CTL-008/019 and remote reconcile | stop retries and reconcile external state before a new candidate |
| RSK-010 | one default per decision with exit criteria | defer the component rather than shipping simultaneous defaults |
| RSK-011 | 4 pd plan plus 1 pd buffer | replan after two carry-over weeks and protect the Phase gate |
| RSK-012 | Task 7 cross-validator on every document change | mark trace GAP and block document baselining |
| RSK-013 | VG-024 public-safe review | remove unsafe material and keep publication unapproved |
| RSK-014 | local-first design and cost approval gate | stop before paid usage and request material-cost authority |

Do not repeat the full threat narrative.

- [ ] **Step 3: Add risk response and escalation rules**

Require:

- Score 17~25: release/phase blocking, immediate mitigation.
- Score 10~16: weekly review and named mitigation task.
- Score 5~9: monitor at phase checkpoint.
- Score 1~4: monitor when trigger changes.
- Any CRITICAL CTL failure is phase blocking regardless of numeric project-risk score.
- Cost, publication, new credentials, destructive action, and scope expansion require new human authority.
- Severity downgrade and risk closure require evidence or a changed premise, not calendar passage.

- [ ] **Step 4: Validate risk arithmetic and count**

Run:

~~~powershell
$path = 'docs/project/risk-register.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding utf8
$ids = [regex]::Matches($text, '(?m)^\|\s*(RSK-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value }
if (($ids | Sort-Object -Unique).Count -ne 14) { throw 'Expected 14 unique risk definitions' }
foreach ($state in @('OPEN', 'MITIGATING', 'MONITORING', 'CLOSED')) {
  if (-not $text.Contains($state)) { throw "Missing risk state: $state" }
}
'RISK_VALIDATE=PASS'
~~~

Expected: RISK_VALIDATE=PASS.

- [ ] **Step 5: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/project/risk-register.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps risk register'
~~~

Expected: all 14 risks, scores, triggers, and response anchors are visible.

Do not write .git without new explicit commit authority.

---

### Task 7: Requirements Traceability Matrix

**Files:**
- Create: docs/project/requirements-traceability-matrix.md
- Read: all six role documents created in Tasks 1~6

**Interfaces:**
- Consumes: 37 PRD, 14 ARC, 12 THR, 20 CTL, 24 VG, 35 WBS, 14 RSK definitions
- Produces: one RTM row per PRD requirement and orphan/coverage summary

- [ ] **Step 1: Verify all definition owners**

Run:

~~~powershell
$owners = @(
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/project/wbs.md',
  'docs/project/risk-register.md'
)
foreach ($path in $owners) {
  if (-not (Test-Path -LiteralPath $path)) { throw "Missing RTM owner: $path" }
}
if (Test-Path -LiteralPath 'docs/project/requirements-traceability-matrix.md') {
  throw 'STOP: RTM target already exists; inspect ownership.'
}
~~~

- [ ] **Step 2: Create the RTM structure**

Use:

~~~markdown
# ForgeOps 요구사항 추적성 매트릭스

## 1. 목적과 추적 규칙
## 2. 상태와 evidence 표현
## 3. 요구사항 추적표
## 4. Coverage 요약
## 5. Orphan 검사 결과
## 6. 갱신 규칙
## 7. 관련 문서
~~~

The main table columns are Requirement, Phase/Priority, Maturity, ARC, THR, CTL, RSK, WBS, VG, Required floor, Result, Actual tier, Evidence ref, Observation metadata, Trace status, Gap/action.

Initial result for every requirement is NOT_RUN. Actual tier, evidence ref, and observation metadata are 없음. Trace status is COVERED only after every planned relationship in the row exists.

- [ ] **Step 3: Add Phase 0 and Phase 1 mappings**

Use these planned links:

| Requirement | ARC | THR/CTL | RSK | WBS | VG/Floor |
| --- | --- | --- | --- | --- | --- |
| PRD-FR-001 | ARC-002, ARC-010 | THR-003 / CTL-005 | RSK-002 | WBS-002, WBS-003 | VG-002 / E2 |
| PRD-FR-002 | ARC-009 | THR-009, THR-010 / CTL-008, CTL-015 | RSK-003 | WBS-004 | VG-003 / E2 |
| PRD-FR-003 | ARC-012 | THR-001, THR-010 / CTL-001, CTL-015 | RSK-002 | WBS-006 | VG-004 / E2 |
| PRD-FR-004 | ARC-011 | THR-008, THR-010 / CTL-014, CTL-015, CTL-020 | RSK-003, RSK-012 | WBS-007, WBS-008 | VG-004 / E2 |
| PRD-FR-005 | ARC-008 | THR-011 / CTL-016 | RSK-007 | WBS-009 | VG-001 / E2 |
| PRD-FR-006 | ARC-003, ARC-013 | THR-006 / CTL-006, CTL-007 | RSK-005, RSK-009 | WBS-005 | VG-007 / E2 |
| PRD-FR-007 | ARC-007, ARC-011 | THR-004, THR-005, THR-007 / CTL-009, CTL-010, CTL-011, CTL-012, CTL-013 | RSK-004, RSK-006 | WBS-010, WBS-011, WBS-012 | VG-008, VG-009 / E3 |
| PRD-FR-008 | ARC-005, ARC-007 | THR-002, THR-011 / CTL-002, CTL-016 | RSK-007 | WBS-013, WBS-014 | VG-010 / E2 |
| PRD-FR-009 | ARC-005 | THR-001 / CTL-001 | RSK-005 | WBS-015 | VG-011 / E2 |
| PRD-FR-010 | ARC-003, ARC-004, ARC-009 | THR-010 / CTL-005, CTL-015 | RSK-003 | WBS-016, WBS-017, WBS-018, WBS-019 | VG-012 / E2 |
| PRD-FR-011 | ARC-006, ARC-007 | THR-002, THR-005, THR-006 / CTL-002, CTL-006, CTL-010 | RSK-004, RSK-005 | WBS-020 | VG-013, VG-015 / E2 |
| PRD-FR-012 | ARC-008 | THR-011 / CTL-016 | RSK-007 | WBS-021, WBS-022 | VG-013 / E2 |
| PRD-FR-013 | ARC-003, ARC-004, ARC-011 | THR-010, THR-012 / CTL-011, CTL-017, CTL-020 | RSK-011 | WBS-023, WBS-024, WBS-025, WBS-026, WBS-027, WBS-028 | VG-014, VG-015 / E2 |

- [ ] **Step 4: Add Phase 2~4 mappings**

| Requirement | ARC | THR/CTL | RSK | WBS | VG/Floor |
| --- | --- | --- | --- | --- | --- |
| PRD-FR-014 | ARC-008 | THR-010, THR-012 / CTL-015, CTL-017 | RSK-007 | WBS-033 | VG-016 / E2 |
| PRD-FR-015 | ARC-008 | THR-012 / CTL-017 | RSK-001 | WBS-033 | VG-016 / E2 |
| PRD-FR-016 | ARC-008 | THR-011 / CTL-016 | RSK-008 | WBS-033 | VG-017 / E3 |
| PRD-FR-017 | ARC-008, ARC-011 | THR-010, THR-011 / CTL-015, CTL-016 | RSK-008 | WBS-033 | VG-018 / E3 |
| PRD-FR-018 | ARC-013 | THR-006, THR-009 / CTL-006, CTL-007, CTL-019 | RSK-009 | WBS-034 | VG-019 / E3 |
| PRD-FR-019 | ARC-003, ARC-013 | THR-006, THR-008 / CTL-007, CTL-014, CTL-020 | RSK-009 | WBS-034 | VG-020 / E3 |
| PRD-FR-020 | ARC-006 | THR-001, THR-003, THR-004, THR-007 / CTL-001, CTL-003, CTL-004, CTL-013, CTL-018 | RSK-005, RSK-006 | WBS-034 | VG-020 / E3 |
| PRD-FR-021 | ARC-003, ARC-012, ARC-014 | THR-009, THR-012 / CTL-011, CTL-019 | RSK-009, RSK-010 | WBS-034 | VG-020 / E3 |
| PRD-FR-022 | ARC-007, ARC-011, ARC-014 | THR-005, THR-008 / CTL-009, CTL-010, CTL-014 | RSK-004, RSK-010 | WBS-035 | VG-021, VG-022 / E3 |
| PRD-FR-023 | ARC-006, ARC-014 | THR-001, THR-003, THR-011 / CTL-001, CTL-003, CTL-016, CTL-018 | RSK-010 | WBS-035 | VG-023 / E3 |
| PRD-FR-024 | ARC-005, ARC-008, ARC-014 | THR-001, THR-011 / CTL-001, CTL-016 | RSK-010 | WBS-035 | VG-023 / E3 |
| PRD-FR-025 | ARC-008, ARC-011, ARC-013 | THR-006, THR-009, THR-010 / CTL-007, CTL-008, CTL-015, CTL-019 | RSK-003, RSK-008, RSK-009 | WBS-035 | VG-017, VG-018, VG-022 / E3 |

- [ ] **Step 5: Add nonfunctional mappings**

| Requirement | ARC | THR/CTL | RSK | WBS | VG/Floor |
| --- | --- | --- | --- | --- | --- |
| PRD-NFR-001 | ARC-008, ARC-011 | THR-010, THR-011 / CTL-015, CTL-016 | RSK-007 | WBS-001, WBS-021, WBS-027 | VG-001, VG-023 / E2 |
| PRD-NFR-002 | ARC-006, ARC-007, ARC-010 | THR-002, THR-003, THR-004, THR-006 / CTL-002, CTL-003, CTL-004, CTL-005, CTL-006, CTL-007, CTL-012 | RSK-005 | WBS-005, WBS-010, WBS-026 | VG-005, VG-006, VG-007, VG-008 / E3 |
| PRD-NFR-003 | ARC-007 | THR-005 / CTL-009, CTL-010, CTL-011 | RSK-004 | WBS-010, WBS-013, WBS-024, WBS-028 | VG-008, VG-010, VG-014 / E3 |
| PRD-NFR-004 | ARC-006, ARC-011 | THR-007, THR-008 / CTL-013, CTL-014 | RSK-006 | WBS-011, WBS-028, WBS-031 | VG-009, VG-024 / E3 |
| PRD-NFR-005 | ARC-003, ARC-011, ARC-013 | THR-009, THR-012 / CTL-008, CTL-011, CTL-017, CTL-019 | RSK-003, RSK-009 | WBS-024, WBS-030, WBS-034 | VG-014, VG-015, VG-019 / E3 |
| PRD-NFR-006 | ARC-011, ARC-012 | THR-008, THR-010 / CTL-014, CTL-015, CTL-020 | RSK-012 | WBS-007, WBS-008, WBS-025, WBS-031 | VG-004, VG-015 / E2 |
| PRD-NFR-007 | ARC-014 | THR-012 / CTL-011 | RSK-010 | WBS-035 | VG-022 / E3 |
| PRD-NFR-008 | ARC-003, ARC-008 | THR-012 / CTL-011, CTL-017 | RSK-001, RSK-011, RSK-014 | WBS-023, WBS-032 | VG-014 / E2 |
| PRD-NFR-009 | ARC-001, ARC-006, ARC-014 | THR-001, THR-003 / CTL-001, CTL-003, CTL-018 | RSK-010 | WBS-001, WBS-035 | VG-001, VG-023 / E2 |
| PRD-NFR-010 | ARC-008 | THR-011 / CTL-016 | RSK-008 | WBS-032, WBS-033 | VG-017, VG-018 / E3 |
| PRD-NFR-011 | ARC-003, ARC-012 | THR-006, THR-008 / CTL-007, CTL-014, CTL-020 | RSK-013 | WBS-003, WBS-025, WBS-029, WBS-031, WBS-032 | VG-015, VG-024 / E2 |
| PRD-NFR-012 | ARC-007, ARC-013, ARC-014 | THR-005, THR-008, THR-009 / CTL-009, CTL-010, CTL-014, CTL-019, CTL-020 | RSK-004, RSK-009 | WBS-035 | VG-021, VG-022 / E3 |

- [ ] **Step 6: Validate all definitions and orphan closure**

Run this exact cross-document validator:

~~~powershell
$definitions = [ordered]@{
  PRD = @{ Path = 'docs/product/prd.md'; Pattern = '(?m)^\|\s*(PRD-(?:FR|NFR)-\d{3})\s*\|'; Count = 37 }
  ARC = @{ Path = 'docs/architecture/system-architecture.md'; Pattern = '(?m)^\|\s*(ARC-\d{3})\s*\|'; Count = 14 }
  THR = @{ Path = 'docs/security/threat-model.md'; Pattern = '(?m)^\|\s*(THR-\d{3})\s*\|'; Count = 12 }
  CTL = @{ Path = 'docs/security/threat-model.md'; Pattern = '(?m)^\|\s*(CTL-\d{3})\s*\|'; Count = 20 }
  VG = @{ Path = 'docs/quality/verification-and-evaluation-plan.md'; Pattern = '(?m)^\|\s*(VG-\d{3})\s*\|'; Count = 24 }
  WBS = @{ Path = 'docs/project/wbs.md'; Pattern = '(?m)^\|\s*(WBS-\d{3})\s*\|'; Count = 35 }
  RSK = @{ Path = 'docs/project/risk-register.md'; Pattern = '(?m)^\|\s*(RSK-\d{3})\s*\|'; Count = 14 }
}
$catalogs = @{}
foreach ($entry in $definitions.GetEnumerator()) {
  $text = Get-Content -LiteralPath $entry.Value.Path -Raw -Encoding utf8
  $ids = @([regex]::Matches($text, $entry.Value.Pattern) | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
  if ($ids.Count -ne $entry.Value.Count) {
    throw "$($entry.Key) count expected $($entry.Value.Count), got $($ids.Count)"
  }
  $catalogs[$entry.Key] = $ids
}
$rtmPath = 'docs/project/requirements-traceability-matrix.md'
$rtm = Get-Content -LiteralPath $rtmPath -Raw -Encoding utf8
$matrixStart = $rtm.IndexOf('## 3. 요구사항 추적표', [System.StringComparison]::Ordinal)
$matrixEnd = $rtm.IndexOf('## 4. Coverage 요약', [System.StringComparison]::Ordinal)
if ($matrixStart -lt 0 -or $matrixEnd -le $matrixStart) { throw 'RTM matrix boundaries missing' }
$matrix = $rtm.Substring($matrixStart, $matrixEnd - $matrixStart)
$rtmRequirements = @([regex]::Matches($matrix, '(?m)^\|\s*(PRD-(?:FR|NFR)-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
if ($rtmRequirements.Count -ne 37) { throw "RTM must contain 37 requirement rows, got $($rtmRequirements.Count)" }
foreach ($catalog in $catalogs.GetEnumerator()) {
  foreach ($id in $catalog.Value) {
    if (-not $matrix.Contains($id)) { throw "Orphan $($catalog.Key): $id" }
  }
}
if (([regex]::Matches($matrix, '\bNOT_RUN\b')).Count -lt 37) { throw 'Every initial RTM row must be NOT_RUN' }
'RTM_VALIDATE=PASS'
~~~

Expected: RTM_VALIDATE=PASS.

- [ ] **Step 7: Add coverage summary**

Report exact counts: PRD 37, ARC 14, THR 12, CTL 20, VG 24, WBS 35, RSK 14. State orphan count 0 only after Step 6 passes. Explain that COVERED means planned links are complete, not that runtime verification passed.

- [ ] **Step 8: Run the Git checkpoint**

Run:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/project/requirements-traceability-matrix.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps requirements traceability matrix'
~~~

Expected: 37 requirement rows and the coverage/orphan summary are visible.

Do not write .git without new explicit commit authority.

---

### Task 8: Documentation Index and Final Verification

**Files:**
- Create: docs/README.md
- Verify: all 8 new documents
- Preserve: docs/handoff/forgeops-full-handoff.md and all existing repository files

**Interfaces:**
- Consumes: final seven role documents and approved design
- Produces: navigable documentation index and final verification evidence

- [ ] **Step 1: Create the documentation index**

Use:

~~~markdown
# ForgeOps 문서 지도

## 1. 목적
## 2. 권장 읽기 순서
## 3. 문서 책임과 상태
## 4. 기준 출처 우선순위
## 5. 상태와 식별자 규칙
## 6. 변경 및 동기화 규칙
~~~

Reading order:

1. handoff/forgeops-full-handoff.md
2. product/prd.md
3. architecture/system-architecture.md
4. security/threat-model.md
5. quality/verification-and-evaluation-plan.md
6. project/wbs.md
7. project/risk-register.md
8. project/requirements-traceability-matrix.md

Add a table with responsibility, state 초안, last reviewed 2026-07-14, and relative link for every new role document. Link the approved design and this plan as process artifacts, not product authority.

- [ ] **Step 2: Define source and synchronization rules**

State:

- Initial precedence: direct user/scoped instructions → Protocol and fresh repository observation → handoff → derived docs.
- After user baselines the suite, each role document owns its domain and handoff becomes vision/handoff summary.
- A normative change updates RTM and affected docs in the same change.
- If handoff cannot be synchronized, create a RSK entry with reason and target week.
- No document can weaken exact authority, approval, fail-closed, fresh evidence, protected resource, or publication gates.

- [ ] **Step 3: Run file, encoding, fence, and incomplete-marker checks**

Run:

~~~powershell
$targets = @(
  'docs/README.md',
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/project/wbs.md',
  'docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md'
)
$forbidden = @('T' + 'ODO', 'T' + 'BD', 'F' + 'IXME', 'X' + 'XX')
foreach ($path in $targets) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing document: $path" }
  $text = Get-Content -LiteralPath $path -Raw -Encoding utf8
  if ([string]::IsNullOrWhiteSpace($text)) { throw "Empty document: $path" }
  $fenceCount = [regex]::Matches($text, '(?m)^~~~').Count
  if (($fenceCount % 2) -ne 0) { throw "Unbalanced fence: $path" }
  $lineNumber = 0
  foreach ($line in (Get-Content -LiteralPath $path -Encoding utf8)) {
    $lineNumber++
    if ($line -match '[ \t]+$') { throw "Trailing whitespace: $path line $lineNumber" }
  }
  foreach ($marker in $forbidden) {
    if ($text.Contains($marker)) { throw "Incomplete marker in $path" }
  }
}
'DOC_STRUCTURE=PASS'
~~~

Expected: DOC_STRUCTURE=PASS.

- [ ] **Step 4: Validate relative Markdown links**

Run:

~~~powershell
$targets = @(
  'docs/README.md',
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/project/wbs.md',
  'docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md'
)
$linkPattern = [regex]'\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)'
foreach ($path in $targets) {
  $text = Get-Content -LiteralPath $path -Raw -Encoding utf8
  foreach ($match in $linkPattern.Matches($text)) {
    $relative = $match.Groups[1].Value
    if ($relative -match '^[a-zA-Z]+://') { continue }
    $base = Split-Path -Parent $path
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $base $relative))
    $root = [System.IO.Path]::GetFullPath((Get-Location).Path)
    $rootPrefix = $root.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
    if ($candidate -ne $root -and -not $candidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Link escapes repository: $path -> $relative"
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
      throw "Broken Markdown link: $path -> $relative"
    }
  }
}
'DOC_LINKS=PASS'
~~~

Expected: DOC_LINKS=PASS.

- [ ] **Step 5: Re-run the RTM closure validator**

Run:

~~~powershell
$definitions = [ordered]@{
  PRD = @{ Path = 'docs/product/prd.md'; Pattern = '(?m)^\|\s*(PRD-(?:FR|NFR)-\d{3})\s*\|'; Count = 37 }
  ARC = @{ Path = 'docs/architecture/system-architecture.md'; Pattern = '(?m)^\|\s*(ARC-\d{3})\s*\|'; Count = 14 }
  THR = @{ Path = 'docs/security/threat-model.md'; Pattern = '(?m)^\|\s*(THR-\d{3})\s*\|'; Count = 12 }
  CTL = @{ Path = 'docs/security/threat-model.md'; Pattern = '(?m)^\|\s*(CTL-\d{3})\s*\|'; Count = 20 }
  VG = @{ Path = 'docs/quality/verification-and-evaluation-plan.md'; Pattern = '(?m)^\|\s*(VG-\d{3})\s*\|'; Count = 24 }
  WBS = @{ Path = 'docs/project/wbs.md'; Pattern = '(?m)^\|\s*(WBS-\d{3})\s*\|'; Count = 35 }
  RSK = @{ Path = 'docs/project/risk-register.md'; Pattern = '(?m)^\|\s*(RSK-\d{3})\s*\|'; Count = 14 }
}
$catalogs = @{}
foreach ($entry in $definitions.GetEnumerator()) {
  $text = Get-Content -LiteralPath $entry.Value.Path -Raw -Encoding utf8
  $ids = @([regex]::Matches($text, $entry.Value.Pattern) | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
  if ($ids.Count -ne $entry.Value.Count) {
    throw "$($entry.Key) count expected $($entry.Value.Count), got $($ids.Count)"
  }
  $catalogs[$entry.Key] = $ids
}
$rtmPath = 'docs/project/requirements-traceability-matrix.md'
$rtm = Get-Content -LiteralPath $rtmPath -Raw -Encoding utf8
$matrixStart = $rtm.IndexOf('## 3. 요구사항 추적표', [System.StringComparison]::Ordinal)
$matrixEnd = $rtm.IndexOf('## 4. Coverage 요약', [System.StringComparison]::Ordinal)
if ($matrixStart -lt 0 -or $matrixEnd -le $matrixStart) { throw 'RTM matrix boundaries missing' }
$matrix = $rtm.Substring($matrixStart, $matrixEnd - $matrixStart)
$rtmRequirements = @([regex]::Matches($matrix, '(?m)^\|\s*(PRD-(?:FR|NFR)-\d{3})\s*\|') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
if ($rtmRequirements.Count -ne 37) { throw "RTM must contain 37 requirement rows, got $($rtmRequirements.Count)" }
foreach ($catalog in $catalogs.GetEnumerator()) {
  foreach ($id in $catalog.Value) {
    if (-not $matrix.Contains($id)) { throw "Orphan $($catalog.Key): $id" }
  }
}
if (([regex]::Matches($matrix, '\bNOT_RUN\b')).Count -lt 37) { throw 'Every initial RTM row must be NOT_RUN' }
'RTM_VALIDATE=PASS'
~~~

Expected: RTM_VALIDATE=PASS with PRD 37, ARC 14, THR 12, CTL 20, VG 24, WBS 35, RSK 14, orphan 0.

- [ ] **Step 6: Check scope and repository diff**

Run:

~~~powershell
$allowed = @(
  'docs/README.md',
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/project/wbs.md',
  'docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md'
)
# Untracked 역할 디렉터리를 파일 단위로 비교하기 위해 전체 파일을 열거한다.
$statusLines = @(git status --porcelain=v1 --untracked-files=all)
foreach ($line in $statusLines) {
  if ($line.Length -lt 4) { continue }
  $path = $line.Substring(3).Trim('"')
  if ($allowed -notcontains $path) {
    throw "Out-of-scope change detected: $path"
  }
}
git diff --check
git status --short
'SCOPE_CHECK=PASS'
~~~

Expected: only the 8 documents and this plan appear as new/modified work. The earlier committed design spec does not appear as a working-tree change.

- [ ] **Step 7: Perform semantic review**

Check line by line and record PASS/FAIL for:

1. PRD contains Phase 0~4 requirements and no WBS task details.
2. WBS details only Phase 0~1 and keeps Phase 2~4 as milestones.
3. Architecture separates product state, WBS state, canonical accepted state.
4. Threat model contains RESOURCE, COMMAND, NETWORK, destructive and external-effect gates.
5. Quality plan separates planned method from actual fresh evidence.
6. RTM uses NOT_RUN and 없음 for unexecuted product checks.
7. Every THR has CTL and negative VG; every CTL links PRD-NFR, WBS, VG through RTM.
8. Portfolio package is public-safe but external publication remains unapproved.
9. Current Harness claims link to files; product runtime is not labeled IMPLEMENTED.
10. Handoff and Protocol files are unchanged.

If any item fails, fix the owning document and rerun Steps 3~6.

- [ ] **Step 8: Run the final Git checkpoint**

Run:

~~~powershell
git status --short --branch
$targets = @(
  'docs/README.md',
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/project/wbs.md',
  'docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md'
)
$targets | ForEach-Object {
  $item = Get-Item -LiteralPath $_
  [pscustomobject]@{ Path = $_; Bytes = $item.Length }
} | Format-Table -AutoSize
'PROPOSED_COMMIT_SET=8 foundational docs plus the execution plan'
'PROPOSED_COMMIT=docs: add ForgeOps product planning foundation'
~~~

Do not stage, commit, push, create a PR, or publish without new explicit user authority.

---

## Completion Evidence

The executor may report completion only when all of these fresh results exist in the same execution:

- PRD_VALIDATE=PASS
- ARCH_VALIDATE=PASS
- SECURITY_VALIDATE=PASS
- QUALITY_VALIDATE=PASS
- WBS_VALIDATE=PASS
- RISK_VALIDATE=PASS
- RTM_VALIDATE=PASS
- DOC_STRUCTURE=PASS
- DOC_LINKS=PASS
- SCOPE_CHECK=PASS
- Semantic review 10/10 PASS

If a command cannot run, report the exact reason and leave the affected criterion NOT_RUN. Do not replace missing evidence with narrative confidence.
