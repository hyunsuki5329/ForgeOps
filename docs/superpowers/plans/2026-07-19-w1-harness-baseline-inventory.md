# W1 Harness Baseline Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete WBS-001 with a source-linked Harness baseline inventory, documentation-map registration, and verified status closure.

**Architecture:** Keep the inventory beside the existing Harness porting guide. The inventory records current files and role boundaries without claiming product runtime or VG passage; `docs/README.md` exposes it, and `docs/project/wbs.md` remains the execution-status owner.

**Tech Stack:** Markdown, PowerShell, read-only Git status/diff inspection

## Global Constraints

- Preserve all pre-existing user changes in the dirty worktree.
- Do not access protected resources, credentials, private data, `.env*`, or `.git` internals.
- Do not perform network, publication, messaging, deployment, destructive, cost-incurring, staging, or commit operations.
- Protocol 2.0 and fresh repository observations outrank derived product documents.
- Do not claim Product runtime implementation, VG-001 passage, Phase 0 Exit, or publication authority.
- Set only WBS-001 to `WBS_DONE`, and only after all verification succeeds.

---

## File Structure

- Create `docs/agent-harness/BASELINE_INVENTORY.md`: current Harness files, role/adapter boundaries, product non-claims, and VG-001 inputs.
- Modify `docs/README.md`: register the inventory without changing ownership of the eight foundation documents.
- Modify `docs/project/wbs.md`: close only WBS-001 after verification.

### Task 1: Create the Harness Baseline Inventory

**Files:**

- Create: `docs/agent-harness/BASELINE_INVENTORY.md`

**Interfaces:**

- Consumes: `.github/agents/main_instruction.prompt.md`, `.github/agents/part_agent.prompt.md`, `.github/agents/work_agent.prompt.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `docs/agent-harness/PORTING_GUIDE.md`, and VG-001.
- Produces: `docs/agent-harness/BASELINE_INVENTORY.md` as the WBS-002/WBS-003 source entry point.

- [x] **Step 1: Verify the file is absent**

```powershell
if (Test-Path 'docs/agent-harness/BASELINE_INVENTORY.md') { throw 'Inventory already exists' }
'BASELINE_INVENTORY_ABSENT'
```

Expected: `BASELINE_INVENTORY_ABSENT`.

- [x] **Step 2: Create the inventory**

Create the file with this exact structure and content obligations:

```markdown
# Portable Agent Harness 기준선 인벤토리

**문서 상태:** 검토됨
**관찰 기준일:** 2026-07-19
**대상:** ForgeOps 개발자와 Foundation·Phase 0 검토자
**목적:** 현재 Protocol 2.0, Main·Part·Work, repository adapter/profile 및 적용 가이드의 경계를 파일 근거로 연결하고 VG-001 검토 입력을 식별한다.

## 1. 범위와 상태 의미

`PRESENT`는 파일 존재의 fresh 관찰, `IMPLEMENTED`는 prompt·adapter에 표현된 Harness Foundation 계약, `SPECIFIED`와 `PLANNED`는 제품 계약 또는 후속 구현 대상을 뜻한다. 어느 상태도 runtime 실행이나 VG 통과를 뜻하지 않는다.

## 2. Harness Foundation 파일 인벤토리

| 파일 | 상태 | 현재 책임 | 금지되는 확대 해석 |
| --- | --- | --- | --- |
| [Main 역할 프롬프트](../../.github/agents/main_instruction.prompt.md) | PRESENT | Protocol 2.0 정규화, route, accepted state, revision, authoritative event sequence와 최종 결정 | 제품 orchestration service 또는 durable state 구현 |
| [Part 역할 프롬프트](../../.github/agents/part_agent.prompt.md) | PRESENT | 읽기 전용 discovery, 분해와 CandidatePacket 제안 | mutation 또는 accepted state 변경 권한 |
| [Work 역할 프롬프트](../../.github/agents/work_agent.prompt.md) | PRESENT | 승인된 exact candidate 재검증, 실행, 검증과 WorkResult 제안 | 사용자 승인 또는 최종 상태 소유권 |
| [ForgeOps repository adapter/profile](../../AGENTS.md) | PRESENT | root, source of truth, protected resource, risk와 validation discovery 설정 | UNKNOWN capability 승격 또는 외부 효과 허용 |
| [Copilot adapter](../../.github/copilot-instructions.md) | PRESENT | Copilot 역할 mapping, precedence와 v1 전달 경계 | Main 이전 v1 normalization 또는 unavailable delegation 모의 실행 |
| [Portable Harness 적용 가이드](PORTING_GUIDE.md) | PRESENT | 설치 파일, adapter, capability·authority, evidence와 conformance 안내 | 제품 runtime, VG 통과 또는 host capability 보장 |

## 3. 역할과 adapter 경계

| 주체 | 허용된 책임 | 소유하지 않는 것 |
| --- | --- | --- |
| Main | 정규화, route, proposal·evidence 검증, accepted state·revision·authoritative event와 최종 결정 | 관찰되지 않은 capability, 암묵 권한과 fabricated evidence |
| Part | 허용된 범위의 읽기 전용 discovery와 CandidatePacket 제안 | 파일·외부 시스템 변경과 accepted state |
| Work | 승인된 exact candidate의 preflight·변경·검증과 WorkResult 제안 | 사용자 승인, 최종 상태와 revision increment |
| Repository adapter/profile | host 진입점과 ForgeOps 제약 제공 | Protocol 불변식 약화, 권한 생성과 제품 runtime 구현 |

하위 역할과 adapter는 Main Protocol을 확장해 권한을 만들 수 없다. 사용자 승인도 capability나 TaskPacket authority를 만들지 않으며 행동은 관찰된 capability, exact authority, 필요한 승인, current revision과 preflight의 교집합으로 제한된다.

## 4. Harness Foundation과 제품 runtime 경계

| 계층 | 현재 성숙도 | 현재 확인 가능한 것 | 아직 주장할 수 없는 것 |
| --- | --- | --- | --- |
| Portable Harness Foundation | IMPLEMENTED | Protocol 2.0, 역할 prompt, repository adapter/profile | service, snapshot, sandbox, durable persistence, rollback |
| Product contract layer | SPECIFIED | PRD·아키텍처의 Contract→TaskPacket 요구 | executable schema와 bridge fixture 통과 |
| ForgeOps Product runtime | PLANNED | 후속 WBS의 제품 component 목표 | 현재 API·queue·database·sandbox·SCM write 작동 |

## 5. VG-001 검토 입력

VG-001은 `forgeops-foundation-conformance` profile의 `protocol-conformance`와 `sample-fixture` command를 요구하는 E2 검증이다. WBS-001은 다음 입력만 식별하며 VG-001을 실행하거나 통과 처리하지 않는다.

| 검토 입력 | 확인 관점 |
| --- | --- |
| Main·Part·Work 역할 프롬프트 | canonical packet, actor, state·evidence 소유권과 fail-closed 의미 |
| root AGENTS.md와 Copilot adapter | adapter 교체 전후 Protocol 의미와 ForgeOps profile 제약 보존 |
| Porting Guide 적합성 시나리오 | positive·negative fixture 범위와 stable rejection 기대값 |
| PRD·시스템 아키텍처·WBS | PRD-NFR-001·009, ARC-001·002·010과 WBS-001·002의 추적 경계 |

현재 `VG-001` 결과는 `NOT_RUN`이며 sample fixture와 trusted validation command의 fresh E2 결과 전에는 `PASSED`로 바꾸지 않는다.

## 6. 알려진 제한과 후속 연결

WBS-001은 Product Task Contract schema를 구현하지 않는다. WBS-002가 schema·bridge·fixture를 구현하고 WBS-003이 검토한다. `public-safe`는 외부 게시 권한이 아니다.

## 7. 관련 문서

[ForgeOps 문서 지도](../README.md), [작업 분해 구조](../project/wbs.md), [검증 및 평가 계획](../quality/verification-and-evaluation-plan.md), [시스템 아키텍처](../architecture/system-architecture.md), [제품 요구사항](../product/prd.md)와 [Portable Agent Harness v2 적용 가이드](PORTING_GUIDE.md)를 연결한다.
```

- [x] **Step 3: Verify required terms and every local link**

```powershell
$path='docs/agent-harness/BASELINE_INVENTORY.md'
$text=Get-Content -LiteralPath $path -Raw -Encoding utf8
foreach($term in @('main_instruction.prompt.md','part_agent.prompt.md','work_agent.prompt.md','../../AGENTS.md','copilot-instructions.md','PORTING_GUIDE.md','VG-001','IMPLEMENTED','SPECIFIED','PLANNED','NOT_RUN')){if(-not $text.Contains($term)){throw "Missing term: $term"}}
$base=Split-Path -Parent (Resolve-Path $path)
[regex]::Matches($text,'\]\(([^)#]+)(?:#[^)]+)?\)') | ForEach-Object {$link=$_.Groups[1].Value;if(-not(Test-Path -LiteralPath (Join-Path $base $link))){throw "Broken link: $link"}}
'BASELINE_INVENTORY_OK'
```

Expected: `BASELINE_INVENTORY_OK`.

### Task 2: Register the Inventory in the Documentation Map

**Files:**

- Modify: `docs/README.md`

**Interfaces:**

- Consumes: the Task 1 inventory.
- Produces: two discoverability links while retaining the eight-document owner catalog.

- [x] **Step 1: Verify no existing registration**

```powershell
if(Select-String -LiteralPath 'docs/README.md' -SimpleMatch 'agent-harness/BASELINE_INVENTORY.md' -Quiet){throw 'Link already exists'}
'INVENTORY_LINK_ABSENT'
```

Expected: `INVENTORY_LINK_ABSENT`.

- [x] **Step 2: Add the reading-order entry and ownership note**

Insert after the current first reading item and renumber the remaining list:

```markdown
2. [Portable Agent Harness 기준선 인벤토리](agent-harness/BASELINE_INVENTORY.md) — 현재 Protocol·역할·adapter 파일 경계와 VG-001 검토 입력을 확인한다.
```

Append after the process-artifact explanation:

```markdown
[Portable Agent Harness 기준선 인벤토리](agent-harness/BASELINE_INVENTORY.md)는
기초 문서 8개의 owner catalog에 추가되는 아홉 번째 owner 문서가 아니라,
현재 Harness Foundation 파일과 VG-001 검토 입력을 연결하는 WBS-001
산출물이다.
```

- [x] **Step 3: Verify exactly two map links and the owner boundary**

```powershell
$text=Get-Content -LiteralPath 'docs/README.md' -Raw -Encoding utf8
if(([regex]::Matches($text,[regex]::Escape('agent-harness/BASELINE_INVENTORY.md'))).Count-ne 2){throw 'Expected two inventory links'}
if(-not $text.Contains('기초 문서 8개의 owner catalog에 추가되는 아홉 번째 owner 문서가 아니라')){throw 'Missing owner boundary'}
'DOCS_MAP_OK'
```

Expected: `DOCS_MAP_OK`.

### Task 3: Close WBS-001 and Verify

**Files:**

- Modify: `docs/project/wbs.md`

**Interfaces:**

- Consumes: verified inventory and map registration.
- Produces: WBS-001 `WBS_DONE`; WBS-002 and WBS-003 remain `WBS_NOT_STARTED`.

- [x] **Step 1: Verify the pre-closure states**

```powershell
$text=Get-Content -LiteralPath 'docs/project/wbs.md' -Raw -Encoding utf8
foreach($id in @('WBS-001','WBS-002','WBS-003')){if($text -notmatch "(?m)^\| $id \|[^\r\n]*\| WBS_NOT_STARTED \|"){throw "$id pre-state mismatch"}}
'WBS001_PRECLOSURE_OK'
```

Expected: `WBS001_PRECLOSURE_OK`.

- [x] **Step 2: Change only WBS-001 to WBS_DONE**

Change the WBS-001 row's status cell from `WBS_NOT_STARTED` to `WBS_DONE`. Do not change another row or any VG result.

- [x] **Step 3: Run final content, link, whitespace, newline, and state verification**

```powershell
$inventory='docs/agent-harness/BASELINE_INVENTORY.md';$map='docs/README.md';$wbs='docs/project/wbs.md'
$i=Get-Content -LiteralPath $inventory -Raw -Encoding utf8;$m=Get-Content -LiteralPath $map -Raw -Encoding utf8;$w=Get-Content -LiteralPath $wbs -Raw -Encoding utf8
if($w -notmatch '(?m)^\| WBS-001 \| Phase 0 \| W1 \| WBS_DONE \|'){throw 'WBS-001 closure missing'}
foreach($id in @('WBS-002','WBS-003')){if($w -notmatch "(?m)^\| $id \|[^\r\n]*\| WBS_NOT_STARTED \|"){throw "$id changed"}}
if(-not $i.Contains('NOT_RUN') -or -not $m.Contains('agent-harness/BASELINE_INVENTORY.md')){throw 'Boundary or map missing'}
foreach($path in @($inventory,$map,$wbs)){$lines=Get-Content -LiteralPath $path -Encoding utf8;if($lines|Where-Object{$_ -match '[ \t]+$'}){throw "Trailing whitespace: $path"};$bytes=[IO.File]::ReadAllBytes((Resolve-Path $path));if($bytes[-1]-ne 10){throw "Missing final newline: $path"}}
'WBS001_FINAL_VERIFICATION_OK'
```

Expected: `WBS001_FINAL_VERIFICATION_OK`.

- [x] **Step 4: Inspect the scoped diff and full status**

```powershell
git diff -- docs/agent-harness/BASELINE_INVENTORY.md docs/README.md docs/project/wbs.md
git status --short
```

Expected: only the inventory, two map additions/list renumbering, and WBS-001 status are in the scoped implementation diff; unrelated user changes remain untouched.

- [x] **Step 5: Hand off without Git mutation**

Do not stage or commit. Report changed resources, fresh verification output, preserved pre-existing changes, and the fact that VG-001 remains `NOT_RUN`.
