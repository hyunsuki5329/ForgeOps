# ForgeOps 제품 문서 구현 계획

> **에이전트 작업자용:** 필수 하위 스킬: 이 계획을 작업별로 구현할 때 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans를 사용한다. 단계 추적에는 체크박스(- [ ]) 구문을 사용한다.

**목표:** 승인된 핸드오프와 문서 체계 설계를 기준으로, 1인 개발 실행 관리와 포트폴리오 증빙에 사용할 한국어 기초 문서 8개를 생성하고 상호 추적성을 검증한다.

**아키텍처:** PRD가 제품 요구사항 ID를 먼저 소유하고, 아키텍처·위협 모델·검증 계획이 설계와 통제 및 품질 게이트를 정의한다. WBS와 위험 등록부가 실행 정보를 제공한 뒤 RTM이 모든 ID를 연결하고, docs/README.md가 읽기 순서와 문서 상태를 제공한다.

**기술 스택:** UTF-8 Markdown, Git, PowerShell 5.1+, ripgrep, Mermaid

## 전역 제약 조건

- 승인된 설계 원본은 docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md다.
- 제품 비전과 현재 기준선의 입력 원본은 docs/handoff/forgeops-full-handoff.md다.
- Protocol 2.0 불변식은 AGENTS.md와 .github/agents/main_instruction.prompt.md, part_agent.prompt.md, work_agent.prompt.md를 따른다.
- 생성 파일은 정확히 docs/README.md와 product, architecture, security, quality, project 역할 폴더의 7개 문서다.
- PRD는 Phase 0~4 전체 요구사항을 정의한다. WBS에서만 Phase 2~4를 상위 마일스톤으로 유지한다.
- WBS는 상대 일정 W1~W10, 주당 5인일, 계획 4인일, 여유분 1인일을 사용한다.
- 문서 본문은 한국어로 작성하고 식별자, 열거형, API 및 Protocol 고유명은 원문 표기를 유지한다.
- 문서 상태는 최초 생성 시 초안이고 최종 검토일은 2026-07-14다.
- 요구사항 성숙도는 IMPLEMENTED, SPECIFIED, PLANNED만 사용한다.
- WBS 상태는 WBS_NOT_STARTED, WBS_IN_PROGRESS, WBS_BLOCKED, WBS_DONE만 사용하며 제품 상태와 혼합하지 않는다.
- 추적 상태는 COVERED, PARTIAL, GAP만 사용한다.
- 검증 결과는 PASSED, FAILED, NOT_RUN만 사용한다.
- 원시 셸 command(명령)을 RTM의 증빙이나 권한으로 기록하지 않는다. 검증 절차는 VG와 신뢰된 command_id가 소유한다.
- SPECIFIED와 PLANNED 요구사항의 초기 검증 결과는 NOT_RUN, 실제 증빙 등급과 참조 및 관찰 메타데이터는 없음으로 기록한다.
- 현재 구현 주장은 최신 E1 file 또는 diff 관찰로 확인할 수 있을 때만 IMPLEMENTED로 표시한다.
- 제품 runtime(런타임), 코드, 프롬프트, 핸드오프, 기존 설계서는 수정하지 않는다.
- 사용자 소유 변경을 보존하고 태스크 시작과 종료 시 git status --short를 확인한다.
- 새 영구 검증 스크립트는 추가하지 않는다. 문서 검증은 이 계획의 인라인 PowerShell로 수행한다.
- 현재 승인에는 8개 문서와 이 계획의 Git 커밋, 푸시, PR, 외부 게시 권한이 없다.
- 각 Git 체크포인트는 상태와 제안 커밋 메시지만 출력한다. 명시적 Git 승인이 새로 주어진 경우에만 해당 작업의 정확한 파일을 추가하고 커밋한다.
- 외부 게시와 공개 포트폴리오 배포는 별도 승인 대상이다.

---

## 파일 맵

| 경로 | 동작 | 책임 |
| --- | --- | --- |
| docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md | 읽기 전용 | 승인된 문서 체계와 완료 기준 |
| docs/handoff/forgeops-full-handoff.md | 읽기 전용 | 제품 비전, 계약, 단계, 지표 |
| docs/product/prd.md | 생성 | Phase 0~4 제품 요구사항과 성공 기준 |
| docs/architecture/system-architecture.md | 생성 | 시스템 경계, 상태, 구성요소, 계약, 흐름 |
| docs/security/threat-model.md | 생성 | 위협, 통제, 잔여 위험, 보안 게이트 |
| docs/quality/verification-and-evaluation-plan.md | 생성 | 증빙, VG, 평가, 품질 게이트 |
| docs/project/wbs.md | 생성 | Phase 0~1 상세 10주 계획과 Phase 2~4 마일스톤 |
| docs/project/risk-register.md | 생성 | 일정·기술·보안·평가·포트폴리오 위험 |
| docs/project/requirements-traceability-matrix.md | 생성 | 요구사항에서 증빙까지의 단일 교차 추적표 |
| docs/README.md | 생성 | 문서 지도, 읽기 순서, 상태, 기준 우선순위 |
| docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md | 생성 | 이 실행 계획 |

## 공통 문서 머리글

모든 신규 기초 문서는 다음 메타데이터를 제목 바로 아래에 둔다.

~~~markdown
**문서 상태:** 초안
**최종 검토일:** 2026-07-14
**대상 독자:** 1인 개발자, 포트폴리오 검토자
**기준 출처:** 역할별 기준 출처의 저장소 상대 경로
~~~

각 문서 마지막에는 관련 문서 절을 두고 저장소 상대 링크만 사용한다.

---

### 작업 1: 제품 요구사항 문서

**파일:**
- 생성: docs/product/prd.md
- 읽기: docs/handoff/forgeops-full-handoff.md
- 읽기: docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md

**인터페이스:**
- 입력: 핸드오프의 제품 정의, 범위, 사용자, 원칙, 평가 지표, SLO, Phase 0~4 로드맵
- 출력: PRD-FR-001~PRD-FR-025, PRD-NFR-001~PRD-NFR-012와 Phase 종료 게이트

- [ ] **단계 1: 범위를 점검하고 기존 작업 보호**

실행:

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

예상 결과: 두 기준 문서가 존재하고 대상은 존재하지 않는다. 대상 또는 상위 폴더에 사용자 변경이 보이면 중단하고 범위를 확인한다.

- [ ] **단계 2: PRD 구조 생성**

다음의 정확한 최상위 절로 docs/product/prd.md를 생성할 때 apply_patch를 사용한다.

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

공통 머리글을 포함한다. PRD는 무엇과 왜를 소유하고 구현 작업은 WBS에 속한다고 명시한다.

- [ ] **단계 3: 제품 배경, 사용자, 범위, 기준선 추가**

핸드오프 전체를 복사하지 않고 다음 사실을 작성한다.

- 제품 문장: ForgeOps는 자연어 개발 요청을 구조화된 작업 계약으로 바꾸고, 고정 스냅샷과 격리 환경에서 계획·실행·검증·복구한 뒤 근거와 추적을 사람에게 제공하는 자체 평가형 AI 개발 워크플로 플랫폼이다.
- 사용자: 개발자, 리뷰어 또는 테크 리드, 플랫폼 관리자, AI 또는 플랫폼 엔지니어.
- 지원 결과: 이슈에서 패치와 초안 PR로 이어지는 흐름, 의존성/API 마이그레이션, CI 실패 복구, 대상이 지정된 리팩터링, 보안/품질 개선, 저장소 유지관리.
- 비목표: 무승인 프로덕션 배포·병합·릴리스·운영 DB 변경, 무제한 호스트 셸, 저장소 밖 임의 접근, 숨은 변경, 검증 없는 성공 선언, 초기 전 언어 동등 지원, 무한 복구, 에이전트 수 자체의 차별화.
- 현재 기준선: Protocol 2.0, Main/Part/Work, 어댑터, 이식 가이드는 IMPLEMENTED다. 제품 runtime(런타임), 변경 불가능한 스냅샷, 샌드박스, 영속 저장, 롤백은 구현됐다고 주장하지 않는다.
- 기준선 증빙 링크: ../../AGENTS.md, ../../.github/agents/main_instruction.prompt.md, ../../.github/agents/part_agent.prompt.md, ../../.github/agents/work_agent.prompt.md, ../agent-harness/PORTING_GUIDE.md.

- [ ] **단계 4: 기능 요구사항 카탈로그 추가**

ID, Phase, 우선순위, 성숙도, 요구사항, 수용 결과, 검증 열을 가진 표 하나를 만든다. 다음 카탈로그를 정확히 사용한다.

| ID | Phase | 우선순위 | 성숙도 | 요구사항 및 관찰 가능한 수용 | VG |
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

모든 ID, 단계, 우선순위, 성숙도, VG 참조를 나열된 그대로 유지한다. 요구사항과 관찰 가능한 수용 텍스트를 규범 행 내용으로 사용하고 제품 문제에 연결된 근거 문장 하나를 추가한다. 일정이나 구현 단계를 추가하지 않는다.

- [ ] **단계 5: 비기능 요구사항 추가**

동일한 메타데이터 필드를 가진 표 하나를 만들고 다음 행을 정확히 사용한다.

| ID | 범위 | 우선순위 | 성숙도 | 요구사항 및 관찰 가능한 수용 | VG |
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

- [ ] **단계 6: 종료 게이트, 지표, 연구 성공 조건 추가**

다음의 정확한 릴리스 수준 게이트를 포함한다.

- Phase 0: 예제 스키마와 Harness 적합성 통과, 유효하지 않은 전이/권한과 approval(승인) 거부/만료/nonce 재사용 실패 시 차단, 샌드박스 격리와 비밀 검증 데이터 100%.
- Phase 1: 모든 필수 기준 E2 이상, 무권한 실행 0건, 정리 실패 0건, 외부 쓰기 0건.
- Phase 2: 최소 5회 반복과 사전 고정 평가 계약, 무권한 작업 0건, 원시 비밀 0건, 심각한 주입 탈출 0건, 작업 성공률의 쌍별 95% CI 하한이 0보다 큼, 회귀율의 쌍별 95% CI 상한이 0보다 작음.
- Phase 3: 멱등성, 만료된 approval(승인), 중복 웹훅, 무권한 외부 쓰기 시험 통과.
- Phase 4: 최근 30일 SLO 충족과 보안 불변식 위반 0건.

작업 성공, 회귀, 복구, 진전 없음, 무권한 작업, 주입 탈출, 무관한 변경, 사람의 되돌림, 지연 시간, 비용에 대한 핸드오프 지표 정의를 포함한다. 모든 SLO를 현재 측정값이 아닌 PLANNED 목표로 표시한다.

- [ ] **단계 7: PRD 구조와 식별자 검증**

실행:

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

예상 결과: PRD_VALIDATE=PASS.

- [ ] **단계 8: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/product/prd.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps product requirements'
~~~

예상 결과: 의도한 PRD 변경과 이전에 파악된 사용자 변경만 나타난다. 새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 2: 시스템 아키텍처

**파일:**
- 생성: docs/architecture/system-architecture.md
- 읽기: docs/product/prd.md
- 읽기: docs/handoff/forgeops-full-handoff.md

**인터페이스:**
- 입력: PRD-FR-001~025와 PRD-NFR-001~012
- 출력: ARC-001~ARC-014, 상태 매핑, 계약 및 데이터 흐름 다이어그램

- [ ] **단계 1: PRD 의존성과 대상 검증**

실행:

~~~powershell
if (-not (Test-Path -LiteralPath 'docs/product/prd.md')) { throw 'PRD dependency missing' }
if (Test-Path -LiteralPath 'docs/architecture/system-architecture.md') {
  throw 'STOP: architecture target already exists; inspect ownership.'
}
git status --short
~~~

예상 결과: PRD는 존재하고 아키텍처 대상은 존재하지 않는다.

- [ ] **단계 2: 아키텍처 개요 생성**

apply_patch를 사용해 다음 절을 작성한다.

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

- [ ] **단계 3: 아키텍처 카탈로그 정의**

ID, 성숙도, 책임, 의존성, 관련 요구사항 열을 가진 표를 만든다. 다음과 같이 정확히 정의한다.

| ID | 성숙도 | 책임 |
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

ARC-001은 구현된 프롬프트 파일에 연결해야 한다. 다른 모든 행은 runtime(런타임) 구현을 주장하지 않고 하나 이상의 PRD ID를 참조해야 한다.

- [ ] **단계 4: 다이어그램 4개 추가**

다음 노드와 흐름을 가진 Mermaid 다이어그램을 추가한다.

1. 배경: 사용자/검토자 → 제어 플레인 → 오케스트레이션 → 컨텍스트 엔진, 도구 게이트웨이, 샌드박스, 검증/복구/평가, 추적/산출물. 게시자는 외부 SCM으로 가는 유일한 경로다.
2. Main 흐름: Main 정규화/라우팅 → Part 컨텍스트/계획 → Main 후보 결정 → Work 사전 점검/실행/검증 → Main 증빙 검증/인수 상태.
3. 상태 소유권: 제품 상태를 Protocol 상태에 매핑한다. MainDecision만 인수 상태, revision, 시퀀스를 소유한다. Part/Work는 제안을 내보낸다. 제품 CANCELLED는 버전이 지정된 Protocol 변경 전까지 제품 계층에만 둔다.
4. 증빙 흐름: 신뢰된 출처/프로필 → 작업 → 관찰 → 증빙 카탈로그 → 수용 기준 → MainDecision → 매니페스트/추적.

IMPLEMENTED, SPECIFIED, PLANNED 경계를 다이어그램 노드 또는 인접 범례에 직접 표시한다.

- [ ] **단계 5: 계약 및 경계 표 추가**

다음을 포함한다.

- Task Contract와 TaskPacket 매핑 필드 및 Contract가 권한을 부여하지 않는다는 규칙.
- 폐쇄형 제품 리플레이 모드 AUDIT_REPLAY, REEXECUTE, COUNTERFACTUAL과 각 Harness 매핑.
- API/이벤트/매니페스트 식별 필드: 작업, 실행, 상관관계, base revision, 이벤트 시퀀스, 원본 작업/실행/매니페스트, 스키마 버전, 해시/출처.
- 제품 CANCELLED 처리와 버전이 지정된 Protocol 통합 차단.
- 스냅샷 식별 정보와 대화/작업 revision의 구분. Git SHA는 저장소 식별 정보이며 롤백이나 작업 revision의 증명이 아니다.
- 이후 승인된 ADR 워크플로가 마련되기 전까지 기술 선택은 이 문서 안의 결정 기록으로 유지한다. Temporal/Celery, S3/MinIO, Docker/강화된 격리를 동시에 기본값으로 선택하지 않는다.

- [ ] **단계 6: 아키텍처 정의와 경계 검증**

실행:

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

예상 결과: ARCH_VALIDATE=PASS.

- [ ] **단계 7: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/architecture/system-architecture.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps system architecture'
~~~

예상 결과: 검토할 수 있도록 전체 아키텍처 문서가 보이고 상태에는 의도한 미추적 file(파일)이 나타난다.

새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 3: 위협 모델

**파일:**
- 생성: docs/security/threat-model.md
- 읽기: docs/product/prd.md
- 읽기: docs/architecture/system-architecture.md

**인터페이스:**
- 입력: PRD 보안 요구사항과 ARC 신뢰 경계
- 출력: THR-001~THR-012, CTL-001~CTL-020, 실패 경로 검증 게이트 매핑

- [ ] **단계 1: 의존성과 대상 소유권 검증**

실행:

~~~powershell
foreach ($path in @('docs/product/prd.md', 'docs/architecture/system-architecture.md')) {
  if (-not (Test-Path -LiteralPath $path)) { throw "Missing dependency: $path" }
}
if (Test-Path -LiteralPath 'docs/security/threat-model.md') {
  throw 'STOP: threat model target already exists; inspect ownership.'
}
git status --short
~~~

- [ ] **단계 2: 위협 모델 개요 생성**

다음 절을 사용한다.

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

자산에는 소스 스냅샷, 사용자 변경, 자격 증명, approval(승인) 기능, 검증 프로필, 증빙, 산출물, 이벤트/매니페스트, 테넌트 데이터, 외부 효과 식별 정보가 포함되어야 한다.

- [ ] **단계 3: 위협 카탈로그 추가**

다음과 같이 정확히 정의한다.

| ID | 위협 |
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

각 행에는 자산, 행위자, 사전 조건, 공격 경로, 영향, 대상 단계, 관련 PRD-NFR을 포함한다.

- [ ] **단계 4: 통제 카탈로그 추가**

모든 통제 행은 ID, 요구사항, 심각도, phase_blocking, 대상 단계, 관련 THR, 부정 검증 VG, 잔여 위험을 갖는다. 다음과 같이 정의한다.

| ID | 심각도 | phase_blocking | 통제 |
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

심각도를 낮추려면 변경된 위협 전제, 대체 통제, 검증 증빙, RTM과 위험 갱신을 하나의 변경에 포함해야 한다.

- [ ] **단계 5: 정확한 위협-통제 매핑 추가**

다음 최소 매핑을 사용한다.

| THR | CTL | 부정 검증 VG |
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

고립된 THR, CTL 또는 부정 검증 VG가 하나라도 있으면 문서 기준선 확정을 차단한다고 명시한다.

- [ ] **단계 6: 보안 폐쇄성 검증**

실행:

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

예상 결과: SECURITY_VALIDATE=PASS.

- [ ] **단계 7: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/security/threat-model.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps threat model'
~~~

예상 결과: 전체 위협 모델이 보이고 범위 밖 수정은 없다.

새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 4: 검증 및 평가 계획

**파일:**
- 생성: docs/quality/verification-and-evaluation-plan.md
- 읽기: docs/product/prd.md
- 읽기: docs/architecture/system-architecture.md
- 읽기: docs/security/threat-model.md

**인터페이스:**
- 입력: PRD 요구사항 37개와 THR/CTL 카탈로그
- 출력: VG-001~VG-024, 증빙 계약, 단계 게이트, 평가 규칙

- [ ] **단계 1: 의존성 검증**

실행:

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

예상 결과: 모든 의존성이 존재하고 품질 문서 대상은 없으며 현재 사용자 변경을 검토했다.

- [ ] **단계 2: 품질 계획 개요 생성**

다음을 사용한다.

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

- [ ] **단계 3: 증빙과 판정 의미론 정의**

다음을 정확히 명시한다.

- 증빙 유형은 file, diff, command, test, render, runtime, approval이다.
- file/diff는 observed_revision이 base_revision과 같아야 하고 observed_at을 금지한다.
- command/test/render/runtime/approval은 runtime(런타임)이 공급한 엄격한 UTC observed_at을 요구하고 observed_revision을 금지하며, 신뢰된 validationAt을 기준으로 0~300초 이내여야 한다.
- E0 < E1 < E2 < E3이며, 요구사항 성공에는 요구 수준 이상의 증빙이 필요하다.
- verification_profile_id와 신뢰된 command_id는 계획된 실행을 식별하며, 원시 command(명령) 텍스트는 증빙이나 권한이 아니다.
- PASSED는 해석된 최신 증빙 참조를 요구한다. FAILED는 증빙을 보존한다. NOT_RUN에는 증빙 등급/참조/시각이 없으며 이유를 기록한다.
- 결정론적 검증 실패와 보안 위반은 평가 기준이나 전체 점수로 뒤집을 수 없다.
- baseline_blocked, policy_blocked, inconclusive은 통과와 구분해 유지한다.

- [ ] **단계 4: VG 카탈로그 추가**

각 행은 ID, 대상 단계, 범위, 방법 또는 신뢰된 프로필, 증빙 수준, 통과 조건, 실패 시 차단 결과, 관련 PRD/CTL을 갖는다. 다음과 같이 정의한다.

| ID | Phase | 게이트 | 수준 |
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

모든 CRITICAL CTL에 부정 검증 VG를 하나 이상 연결하고 PARTIAL, GAP, NOT_RUN 또는 실패한 증빙이 대상 Phase 종료를 차단한다고 명시한다.

- [ ] **단계 5: 지표와 단계 결정 추가**

작업 성공, 회귀, 복구, 진전 없음, 무권한 작업, 주입 탈출, 무관한 변경, 사람의 되돌림, 지연 시간, 비용에 대해 지표 이름뿐 아니라 계산식도 복사한다. 다음을 포함한다.

- 스키마 버전과 콘텐츠 해시를 가진 dev/test/hidden(개발/테스트/비공개) 분할.
- 변형별 동일한 스냅샷, Contract, 입력, 이미지, 정책, 검증 프로필, 도구 스키마, 예산.
- 최소 5회의 확률적 반복. 인프라 실패도 계속 보고한다.
- 검정력 분석과 목표 신뢰구간 폭으로 표본 크기를 결정한다.
- 층화 부트스트랩 95% CI를 사용한 쌍별 차이.
- 고정 익명 1~5 평가 기준, 최소 20% 이중 평가. 가중 카파가 0.6 미만이면 평가 기준을 개정하고 재평가한다.
- PRD의 정확한 Phase 2 진행/중단 부등식.

- [ ] **단계 6: 공개에 안전한 증빙 패키지 정의**

공개에 안전한 데모 검증 데이터, 재현 단계, 비밀정보를 삭제한 추적과 diff, 지표, 매니페스트 해시를 요구한다. 자격 증명, 비공개 저장소 내용, 테넌트 식별자, 원시 로그, 라이선스가 불명확한 코드를 금지한다. 패키지 게이트 통과가 외부 게시 권한을 부여하지 않는다고 명시한다.

- [ ] **단계 7: VG 적용 범위 검증**

실행:

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

예상 결과: QUALITY_VALIDATE=PASS.

- [ ] **단계 8: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/quality/verification-and-evaluation-plan.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps verification and evaluation plan'
~~~

예상 결과: 전체 품질 계획이 보이고 상태에는 의도한 작업과 보존된 사용자 변경만 나타난다.

새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 5: 10주 WBS

**파일:**
- 생성: docs/project/wbs.md
- 읽기: docs/product/prd.md
- 읽기: docs/architecture/system-architecture.md
- 읽기: docs/security/threat-model.md
- 읽기: docs/quality/verification-and-evaluation-plan.md

**인터페이스:**
- 입력: PRD 요구사항과 VG-001~024
- 출력: WBS-001~WBS-035, W1~W10 용량 계획, 의존성, 완료 정의

- [ ] **단계 1: 의존성과 대상 검증**

실행:

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

예상 결과: PRD와 품질 계획이 존재하고 WBS 대상은 없으며 현재 변경을 검토했다.

- [ ] **단계 2: WBS 개요 생성**

다음을 사용한다.

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

모든 상세 항목은 ID, 단계, 주차, 상태, 인일, 선행 작업, PRD ID, 산출물, 완료 정의, VG ID, 예상 증빙 유형을 갖는다.

- [ ] **단계 3: W1~W4 Phase 0 패키지 추가**

| ID | 주차 | 인일 | 선행 작업 | 산출물 |
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

모든 초기 상태에 WBS_NOT_STARTED를 사용한다. 주별 계획 작업 합계는 정확히 4.0인일이다.

- [ ] **단계 4: W5~W7 핵심 워크플로 패키지 추가**

| ID | 주차 | 인일 | 선행 작업 | 산출물 |
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

- [ ] **단계 5: W8~W10 신뢰성과 종료 패키지 추가**

| ID | 주차 | 인일 | 선행 작업 | 산출물 |
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

- [ ] **단계 6: Phase 2~4 상위 마일스톤 추가**

확정된 주차나 인일 없이 정의한다.

| ID | Phase | 선행 작업 | 종료 |
| --- | --- | --- | --- |
| WBS-033 | Phase 2 | WBS-032 | bounded repair and benchmark go/no-go |
| WBS-034 | Phase 3 | WBS-033 | controlled GitHub integration, RBAC, audit, dedup gates |
| WBS-035 | Phase 4 | WBS-034 | rolling SLO, zero security violations, plugin maturity |

주차와 인일에는 N/A(상위 마일스톤)를 사용한다. 상세 스프린트나 고정 날짜를 추가하지 않는다.

- [ ] **단계 7: 용량, 주 경로, 재계획 규칙 추가**

다음을 명시한다.

- 주간 용량은 5인일이며 계획 4인일과 여유분 1인일로 구성한다.
- 계획 부하가 4인일을 초과하거나, Phase 게이트가 목표 주차를 지키지 못하거나, 보안 불변식이 실패하거나, 2주 연속 이월이 발생하면 재계획한다.
- 게이트 실패 후 미래 작업을 자동으로 앞당기지 않는다.
- 주 경로는 WBS-001→002→004→005→010→012→013→014→016→017→018→019→020→021→022→026→027→028→029→030에서 시작한다.
- 모든 완료 정의는 산출물과 VG를 명시하지만, 예상 증빙을 현재의 최신 증빙으로 기록하지 않는다.

- [ ] **단계 8: WBS 개수와 용량 검증**

실행:

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

예상 결과: WBS_VALIDATE=PASS.

- [ ] **단계 9: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/project/wbs.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps ten-week WBS'
~~~

예상 결과: W1~W10과 WBS-033~035를 포함한 전체 WBS가 보인다.

새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 6: 위험 등록부

**파일:**
- 생성: docs/project/risk-register.md
- 읽기: docs/product/prd.md
- 읽기: docs/project/wbs.md
- 읽기: docs/security/threat-model.md
- 읽기: docs/quality/verification-and-evaluation-plan.md

**인터페이스:**
- 입력: 요구사항, 일정, 위협, 통제
- 출력: 조건, 대응, 목표 주차, 연결된 ID를 가진 RSK-001~RSK-014

- [ ] **단계 1: 의존성을 검증하고 개요 생성**

실행:

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

예상 결과: 모든 의존성이 존재하고 위험 등록부 대상은 없다.

apply_patch를 사용해 다음을 생성한다.

~~~markdown
# ForgeOps 위험 등록부

## 1. 목적과 운영 규칙
## 2. 점수와 상태
## 3. 위험 카탈로그
## 4. 주간 검토 절차
## 5. Escalation과 Phase gate
## 6. 관련 문서
~~~

확률과 영향은 각각 1~5를 사용하고 점수는 둘의 곱이다. 상태는 OPEN, MITIGATING, MONITORING, CLOSED다.

- [ ] **단계 2: 위험 카탈로그 추가**

모든 행은 ID, 범주, 확률, 영향, 점수, 조건, 예방, 비상 대책, 관련 PRD/THR/CTL/WBS, 목표 검토, 상태를 갖는다. 다음을 사용한다.

| ID | 확률 | 영향 | 점수 | 위험 | 목표 |
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

모든 초기 상태를 OPEN으로 설정한다. 다음의 정확한 예방 및 비상 대책 기준점을 사용한다.

| 위험 | 예방 | 비상 대책 |
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

전체 위협 설명을 반복하지 않는다.

- [ ] **단계 3: 위험 대응과 상향 보고 규칙 추가**

다음을 요구한다.

- 점수 17~25: 릴리스/단계 차단, 즉시 완화.
- 점수 10~16: 주간 검토와 이름이 지정된 완화 작업.
- 점수 5~9: 단계 체크포인트에서 모니터링.
- 점수 1~4: 조건 변경 시 모니터링.
- 모든 CRITICAL CTL 실패는 프로젝트 위험 점수와 무관하게 단계를 차단한다.
- 비용, 게시, 새 자격 증명, 파괴적 작업, 범위 확장에는 새로운 사람 권한이 필요하다.
- 심각도 하향과 위험 종료에는 단순한 시간 경과가 아니라 증빙 또는 변경된 전제가 필요하다.

- [ ] **단계 4: 위험 산술과 개수 검증**

실행:

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

예상 결과: RISK_VALIDATE=PASS.

- [ ] **단계 5: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/project/risk-register.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps risk register'
~~~

예상 결과: 위험 14개와 점수, 조건, 대응 기준점이 모두 보인다.

새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 7: 요구사항 추적성 매트릭스

**파일:**
- 생성: docs/project/requirements-traceability-matrix.md
- 읽기: 작업 1~6에서 생성한 역할 문서 6개 모두

**인터페이스:**
- 입력: PRD 37개, ARC 14개, THR 12개, CTL 20개, VG 24개, WBS 35개, RSK 14개 정의
- 출력: PRD 요구사항별 RTM 행 하나와 고립/적용 범위 요약

- [ ] **단계 1: 모든 정의 소유자 검증**

실행:

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

- [ ] **단계 2: RTM 구조 생성**

다음을 사용한다.

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

주 표의 열은 요구사항, 단계/우선순위, 성숙도, ARC, THR, CTL, RSK, WBS, VG, 요구 수준, 결과, 실제 등급, 증빙 참조, 관찰 메타데이터, 추적 상태, 누락/조치다.

모든 요구사항의 초기 결과는 NOT_RUN이다. 실제 등급, 증빙 참조, 관찰 메타데이터는 없음이다. 행에 계획된 모든 관계가 존재할 때만 추적 상태를 COVERED로 설정한다.

- [ ] **단계 3: Phase 0 및 Phase 1 매핑 추가**

다음의 계획된 연결을 사용한다.

| 요구사항 | ARC | THR/CTL | RSK | WBS | VG/수준 |
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

- [ ] **단계 4: Phase 2~4 매핑 추가**

| 요구사항 | ARC | THR/CTL | RSK | WBS | VG/수준 |
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

- [ ] **단계 5: 비기능 매핑 추가**

| 요구사항 | ARC | THR/CTL | RSK | WBS | VG/수준 |
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

- [ ] **단계 6: 모든 정의와 고립 항목 해소 검증**

다음의 정확한 문서 간 검증기를 실행한다.

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

예상 결과: RTM_VALIDATE=PASS.

- [ ] **단계 7: 적용 범위 요약 추가**

정확한 개수를 보고한다. PRD 37, ARC 14, THR 12, CTL 20, VG 24, WBS 35, RSK 14다. 단계 6이 통과한 후에만 고립 항목 수가 0이라고 명시한다. COVERED는 계획된 연결이 완전하다는 뜻이며 runtime(런타임) 검증 통과를 의미하지 않는다고 설명한다.

- [ ] **단계 8: Git 체크포인트 실행**

실행:

~~~powershell
git status --short
Get-Content -LiteralPath 'docs/project/requirements-traceability-matrix.md' -Raw -Encoding utf8
'PROPOSED_COMMIT=docs: add ForgeOps requirements traceability matrix'
~~~

예상 결과: 요구사항 행 37개와 적용 범위/고립 항목 요약이 보인다.

새로운 명시적 커밋 권한이 없으면 .git에 쓰지 않는다.

---

### 작업 8: 문서 색인 및 최종 검증

**파일:**
- 생성: docs/README.md
- 검증: 신규 문서 8개 모두
- 보존: docs/handoff/forgeops-full-handoff.md와 기존 저장소 파일 모두

**인터페이스:**
- 입력: 최종 역할 문서 7개와 승인된 설계
- 출력: 탐색 가능한 문서 색인과 최종 검증 증빙

- [ ] **단계 1: 문서 색인 생성**

다음을 사용한다.

~~~markdown
# ForgeOps 문서 지도

## 1. 목적
## 2. 권장 읽기 순서
## 3. 문서 책임과 상태
## 4. 기준 출처 우선순위
## 5. 상태와 식별자 규칙
## 6. 변경 및 동기화 규칙
~~~

읽기 순서:

1. handoff/forgeops-full-handoff.md
2. product/prd.md
3. architecture/system-architecture.md
4. security/threat-model.md
5. quality/verification-and-evaluation-plan.md
6. project/wbs.md
7. project/risk-register.md
8. project/requirements-traceability-matrix.md

모든 신규 역할 문서에 대해 책임, 상태 초안, 최종 검토일 2026-07-14, 상대 링크를 가진 표를 추가한다. 승인된 설계와 이 계획은 제품 권한이 아닌 프로세스 산출물로 연결한다.

- [ ] **단계 2: 출처 및 동기화 규칙 정의**

다음을 명시한다.

- 초기 우선순위: 직접 사용자/범위 지시 → Protocol과 최신 저장소 관찰 → 핸드오프 → 파생 문서.
- 사용자가 문서 세트를 기준선으로 확정한 후에는 각 역할 문서가 담당 영역을 소유하고 핸드오프는 비전/인수인계 요약이 된다.
- 규범 변경에서는 RTM과 영향을 받는 문서를 같은 변경으로 갱신한다.
- 핸드오프를 동기화할 수 없으면 이유와 목표 주차가 있는 RSK 항목을 생성한다.
- 어떤 문서도 정확한 권한, approval(승인), 실패 시 차단, 최신 증빙, 보호 리소스, 게시 게이트를 약화할 수 없다.

- [ ] **단계 3: file(파일), 인코딩, 코드 블록 경계, 미완료 표식 검사 실행**

실행:

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

예상 결과: DOC_STRUCTURE=PASS.

- [ ] **단계 4: 상대 Markdown 링크 검증**

실행:

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

예상 결과: DOC_LINKS=PASS.

- [ ] **단계 5: RTM 폐쇄성 검증기 재실행**

실행:

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

예상 결과: PRD 37, ARC 14, THR 12, CTL 20, VG 24, WBS 35, RSK 14, 고립 항목 0으로 RTM_VALIDATE=PASS.

- [ ] **단계 6: 범위와 저장소 diff 확인**

실행:

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

예상 결과: 문서 8개와 이 계획만 신규/수정 작업으로 나타난다. 이전에 커밋된 설계 명세는 작업 트리 변경으로 나타나지 않는다.

- [ ] **단계 7: 의미 검토 수행**

다음 항목을 줄 단위로 확인하고 PASS/FAIL을 기록한다.

1. PRD는 Phase 0~4 요구사항을 포함하고 WBS 작업 세부사항은 포함하지 않는다.
2. WBS는 Phase 0~1만 상세화하고 Phase 2~4는 마일스톤으로 유지한다.
3. 아키텍처는 제품 상태, WBS 상태, 정규 인수 상태를 분리한다.
4. 위협 모델은 RESOURCE, COMMAND, NETWORK, 파괴적 작업, 외부 효과 게이트를 포함한다.
5. 품질 계획은 계획된 방법과 실제 최신 증빙을 분리한다.
6. RTM은 실행하지 않은 제품 검사에 NOT_RUN과 없음을 사용한다.
7. 모든 THR은 CTL과 부정 검증 VG를 갖는다. 모든 CTL은 RTM을 통해 PRD-NFR, WBS, VG에 연결된다.
8. 포트폴리오 패키지는 공개에 안전하지만 외부 게시는 여전히 승인되지 않았다.
9. 현재 Harness 주장은 파일에 연결된다. 제품 runtime(런타임)은 IMPLEMENTED로 표시하지 않는다.
10. 핸드오프와 Protocol 파일은 변경되지 않았다.

항목이 하나라도 실패하면 소유 문서를 수정하고 단계 3~6을 다시 실행한다.

- [ ] **단계 8: 최종 Git 체크포인트 실행**

실행:

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

새로운 명시적 사용자 권한이 없으면 스테이징, 커밋, 푸시, PR 생성, 게시를 수행하지 않는다.

---

## 완료 증빙

실행자는 동일한 실행에서 다음 최신 결과가 모두 있을 때만 완료를 보고할 수 있다.

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
- 의미 검토 10/10 PASS

command(명령)을 실행할 수 없으면 정확한 이유를 보고하고 영향을 받은 기준을 NOT_RUN으로 둔다. 누락된 증빙을 서술형 확신으로 대체하지 않는다.
