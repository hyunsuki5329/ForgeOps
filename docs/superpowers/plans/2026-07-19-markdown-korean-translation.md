# ForgeOps 일반 Markdown 한국어 번역 실행 계획

> **에이전트 작업자용:** 필수 하위 스킬로 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`를 사용해 이 계획을 태스크별로 실행한다. 진행 상태는 checkbox(`- [ ]`)로 추적한다.

**목표:** 실행 계약을 제외한 ForgeOps 일반 Markdown 15개의 영어 자연어를 기술 한국어로 번역하고 코드·식별자·링크·Protocol 의미를 보존한다.

**아키텍처:** Git `HEAD`의 원문을 번역 전 기준선으로 사용한다. 영어 비중이 높은 설계서·계획서를 먼저 번역하고, 프로세스 문서와 사용자용 문서, 한국어 중심 제품 문서의 잔여 영어를 차례로 정리한다. 파일 묶음마다 구조 검증을 수행하고 마지막에 fenced code, inline code, 링크 목적지, catalog와 제외 파일 hash를 교차 검증한다.

**기술 스택:** UTF-8 Markdown, Git, PowerShell 5.1+, ripgrep

## 전체 제약

- 번역 설계 기준은 `docs/superpowers/specs/2026-07-19-markdown-korean-translation-design.md`다.
- 번역 대상은 이 계획에 열거된 Git 추적 일반 Markdown 15개로 한정한다.
- 이미 한국어인 자연어는 불필요하게 다시 쓰지 않는다.
- fenced code block과 그 안의 내용은 byte 의미와 줄 순서를 바꾸지 않는다.
- backtick inline code, 경로, URL, Git SHA, 명령, schema field, enum, stable error와 catalog ID는 원문 철자와 case를 보존한다.
- Main, Part, Work, TaskPacket, CandidatePacket, WorkResult와 Protocol 고유명은 번역하지 않는다.
- 코드나 계약 문자열을 한국어처럼 보이게 바꾸지 않는다.
- 상대 Markdown 링크의 표시 문구는 번역할 수 있지만 link destination은 바꾸지 않는다.
- 새 dependency, 번역 API, 외부 network, 비용, credential 또는 외부 게시를 사용하지 않는다.
- 사용자 소유 변경을 보존하고 out-of-scope 변경을 만들지 않는다.
- 이 계획은 Git add, commit, push, PR 또는 게시 권한을 부여하지 않는다.
- 각 checkpoint는 상태와 제안 commit message만 출력한다.

## 파일 구조와 책임

| 묶음 | 파일 | 번역 책임 |
| --- | --- | --- |
| Harness 설계 | `docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md` | 영어 설계 배경·목표·계약 설명을 한국어로 번역 |
| Harness 계획 | `docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md` | 영어 실행 지시·검증 설명을 한국어로 번역하되 명령과 기대 출력 보존 |
| 제품 문서 프로세스 | `docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md`, `docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md` | 남은 영어 자연어 지시와 표 설명 번역 |
| 문서 진입점·가이드 | `README.md`, `docs/README.md`, `docs/agent-harness/PORTING_GUIDE.md` | 독자용 설명과 안내 문구 번역 |
| 제품·프로젝트 문서 | `docs/handoff/forgeops-full-handoff.md`, `docs/product/prd.md`, `docs/architecture/system-architecture.md`, `docs/security/threat-model.md`, `docs/quality/verification-and-evaluation-plan.md`, `docs/project/wbs.md`, `docs/project/risk-register.md`, `docs/project/requirements-traceability-matrix.md` | 한국어 본문에 남은 독립 영어 자연어만 번역 |

다음 실행 계약은 read-only 제외 파일이다.

| 파일 | 기준 Git object hash |
| --- | --- |
| `AGENTS.md` | `4eb7469ba8f31e1d08e442eb8e947e13ab100cfb` |
| `.github/copilot-instructions.md` | `8a905165f665eeefbb1e8922d24dc220dac38f77` |
| `.github/agents/main_instruction.prompt.md` | `5c5b332215192069d6e9ccc4c5cade2d16a4b902` |
| `.github/agents/part_agent.prompt.md` | `4c67abdc314a9d411a4a05a1f7ec0c6ad3944275` |
| `.github/agents/work_agent.prompt.md` | `ab884ceedc59ab6c4e7a6c0c123f1fec85ce3b19` |

---

### Task 1: 번역 기준선과 범위 검증

**파일:**
- Read: `docs/superpowers/specs/2026-07-19-markdown-korean-translation-design.md`
- Read: 이 계획의 일반 Markdown 15개
- Preserve: 실행 계약 5개와 모든 비대상 파일

**인터페이스:**
- 입력: 현재 `HEAD`, working tree 상태, 대상·제외 파일 목록
- 출력: 후속 태스크가 사용할 검증된 번역 범위와 원문 기준선

- [ ] **Step 1: working tree와 기준 revision을 확인한다**

실행:

~~~powershell
git status --short --branch --untracked-files=all
git rev-parse HEAD
~~~

기대 결과: 번역 대상 15개에는 기존 tracked 변경이 없고, 승인된 번역 설계서와 이 계획만 알려진 untracked 파일로 나타난다. 다른 변경이 있으면 소유권을 확인하기 전 번역을 시작하지 않는다.

- [ ] **Step 2: 대상 파일 목록을 exact 비교한다**

실행:

~~~powershell
$excluded = @(
  'AGENTS.md',
  '.github/copilot-instructions.md',
  '.github/agents/main_instruction.prompt.md',
  '.github/agents/part_agent.prompt.md',
  '.github/agents/work_agent.prompt.md'
)
$expected = @(
  'README.md',
  'docs/README.md',
  'docs/agent-harness/PORTING_GUIDE.md',
  'docs/architecture/system-architecture.md',
  'docs/handoff/forgeops-full-handoff.md',
  'docs/product/prd.md',
  'docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md',
  'docs/project/wbs.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/security/threat-model.md',
  'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md',
  'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md',
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md'
) | Sort-Object
$actual = @(git ls-files '*.md' | Where-Object { $_ -notin $excluded } | Sort-Object)
if (($actual -join "`n") -cne ($expected -join "`n")) {
  throw "Markdown target drift`nExpected:`n$($expected -join "`n")`nActual:`n$($actual -join "`n")"
}
'TRANSLATION_SCOPE=PASS targets=15 excluded=5'
~~~

기대 결과: `TRANSLATION_SCOPE=PASS targets=15 excluded=5`.

- [ ] **Step 3: 제외 계약의 기준 hash를 확인한다**

실행:

~~~powershell
$expectedHashes = [ordered]@{
  'AGENTS.md' = '4eb7469ba8f31e1d08e442eb8e947e13ab100cfb'
  '.github/copilot-instructions.md' = '8a905165f665eeefbb1e8922d24dc220dac38f77'
  '.github/agents/main_instruction.prompt.md' = '5c5b332215192069d6e9ccc4c5cade2d16a4b902'
  '.github/agents/part_agent.prompt.md' = '4c67abdc314a9d411a4a05a1f7ec0c6ad3944275'
  '.github/agents/work_agent.prompt.md' = 'ab884ceedc59ab6c4e7a6c0c123f1fec85ce3b19'
}
foreach ($entry in $expectedHashes.GetEnumerator()) {
  $actual = (git hash-object -- $entry.Key).Trim()
  if ($actual -cne $entry.Value) { throw "Excluded contract drift: $($entry.Key)" }
}
'EXCLUDED_BASELINE=PASS files=5'
~~~

기대 결과: `EXCLUDED_BASELINE=PASS files=5`.

- [ ] **Step 4: 번역 checkpoint를 기록한다**

실행:

~~~powershell
'PROPOSED_COMMIT=docs: translate ForgeOps general documentation into Korean'
git status --short
~~~

Git add 또는 commit은 수행하지 않는다.

---

### Task 2: Portable Agent Harness 설계서 번역

**파일:**
- Modify: `docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md`
- Read: `.github/agents/main_instruction.prompt.md`

**인터페이스:**
- 입력: 승인된 Harness v2 영어 설계와 현행 Protocol 2.0 계약
- 출력: 코드·schema·enum을 보존한 한국어 Harness 설계서

- [ ] **Step 1: 영어 자연어 영역을 분류한다**

다음 항목을 번역 대상으로 표시한다: 문서 제목의 `Design`, metadata label과 값, Context·Goals·Non-goals·Architecture·Protocol·Security·Evidence·Portability·Validation 절의 제목과 설명 문장, 표의 자연어 열 이름과 설명 셀.

다음 항목은 번역하지 않는다: fenced schema/example, inline code, packet field, enum, error code, path, command, Protocol version과 역할 이름.

- [ ] **Step 2: 설계서 자연어를 기술 한국어로 번역한다**

용어는 다음 기준으로 통일한다.

| 영어 자연어 | 한국어 표현 |
| --- | --- |
| Context | 배경 |
| Goals | 목표 |
| Non-goals | 비목표 |
| Scope and precedence | 범위와 우선순위 |
| Authority | 권한 |
| Evidence | 증빙 또는 문맥상 evidence |
| Protected resource | 보호 리소스 |
| Fail closed | 실패 시 차단 또는 `fail-closed` |

고유 계약어 `TaskPacket`, `CandidatePacket`, `WorkResult`, `MainDecision`, `EXPLORE`, `EXECUTE`, `AVAILABLE`, `UNKNOWN`은 그대로 둔다.

- [ ] **Step 3: 파일 구조를 검증한다**

실행:

~~~powershell
$path = 'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md'
$utf8 = [System.Text.UTF8Encoding]::new($false, $true)
$text = $utf8.GetString([System.IO.File]::ReadAllBytes((Resolve-Path $path)))
if ([string]::IsNullOrWhiteSpace($text)) { throw 'Empty translated design' }
if (([regex]::Matches($text, '(?m)^(```|~~~)').Count % 2) -ne 0) { throw 'Unbalanced fence' }
if ([regex]::IsMatch($text, '(?m)[ \t]+$')) { throw 'Trailing whitespace' }
foreach ($term in @('**프로토콜:** 2.0','TaskPacket','CandidatePacket','WorkResult','MainDecision','UNKNOWN')) {
  if (-not $text.Contains($term)) { throw "Missing preserved term: $term" }
}
'HARNESS_DESIGN_TRANSLATION=PASS'
~~~

기대 결과: `HARNESS_DESIGN_TRANSLATION=PASS`.

- [ ] **Step 4: checkpoint를 확인한다**

실행:

~~~powershell
git diff --check -- 'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md'
git status --short
'PROPOSED_COMMIT=docs: translate portable harness design into Korean'
~~~

Git add 또는 commit은 수행하지 않는다.

---

### Task 3: Portable Agent Harness 구현 계획 번역

**파일:**
- Modify: `docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md`
- Preserve: 파일 안의 모든 fenced command, packet example, expected literal과 Git SHA

**인터페이스:**
- 입력: 영어 Harness 구현 계획과 Task 2 한국어 용어 기준
- 출력: 실행 가능한 명령과 기대 결과가 변하지 않은 한국어 구현 계획

- [ ] **Step 1: fenced block 경계를 먼저 확인한다**

실행:

~~~powershell
$path = 'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md'
$text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
$count = [regex]::Matches($text, '(?m)^(```|~~~)').Count
if (($count % 2) -ne 0) { throw 'Unbalanced source fences' }
"HARNESS_PLAN_SOURCE_FENCES=PASS markers=$count"
~~~

- [ ] **Step 2: 실행 지시 자연어를 번역한다**

제목, Goal·Architecture·Tech Stack·Global Constraints, Task와 Step 제목, Files·Interfaces·Run·Expected 설명, 검토·checkpoint 설명을 한국어로 번역한다. PowerShell, JSON, YAML, Markdown example, `git` 명령, hash, 경로, expected output 문자열은 바꾸지 않는다.

`Main`, `Part`, `Work`, `TaskPacket`, `CandidatePacket`, `WorkResult`, `MainDecision`, field와 enum은 원문을 유지한다. 명령 블록 안의 주석은 실행 의미 보존을 위해 번역하지 않는다.

- [ ] **Step 3: incomplete marker와 구조를 검증한다**

실행:

~~~powershell
$path = 'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md'
$utf8 = [System.Text.UTF8Encoding]::new($false, $true)
$text = $utf8.GetString([System.IO.File]::ReadAllBytes((Resolve-Path $path)))
foreach ($marker in @('T' + 'ODO','T' + 'BD','F' + 'IXME','X' + 'XX')) {
  if ($text.Contains($marker)) { throw "Incomplete marker: $marker" }
}
if (([regex]::Matches($text, '(?m)^(```|~~~)').Count % 2) -ne 0) { throw 'Unbalanced translated fences' }
if ([regex]::IsMatch($text, '(?m)[ \t]+$')) { throw 'Trailing whitespace' }
foreach ($term in @('1e2478918e1c44ef6980843fb9876e84d508a0d7','feature/portable-agent-harness-v2','Protocol: 2.0','TaskPacket','MainDecision')) {
  if (-not $text.Contains($term)) { throw "Missing preserved plan term: $term" }
}
'HARNESS_PLAN_TRANSLATION=PASS'
~~~

기대 결과: `HARNESS_PLAN_TRANSLATION=PASS`.

- [ ] **Step 4: checkpoint를 확인한다**

실행:

~~~powershell
git diff --check -- 'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md'
git status --short
'PROPOSED_COMMIT=docs: translate portable harness plan into Korean'
~~~

Git add 또는 commit은 수행하지 않는다.

---

### Task 4: ForgeOps 제품 문서 설계·계획 번역

**파일:**
- Modify: `docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md`

**인터페이스:**
- 입력: 한국어 중심 제품 문서 설계·계획과 Task 2~3 용어 기준
- 출력: 영어 실행 설명이 한국어로 정리되고 exact catalog·validator가 보존된 프로세스 문서

- [ ] **Step 1: 남은 독립 영어 자연어를 찾는다**

실행:

~~~powershell
$paths = @(
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md'
)
rg -n '^[[:space:]>#*+-]*[A-Za-z][A-Za-z ]{15,}' $paths
~~~

결과를 line-by-line으로 분류한다. 자연어 지시·설명은 번역하고 ID, 표의 exact catalog 값, fenced code, 명령과 expected literal은 유지한다.

- [ ] **Step 2: 설계서와 계획서의 자연어를 번역한다**

`Goal`, `Architecture`, `Tech Stack`, `Global Constraints`, `Files`, `Interfaces`, `Consumes`, `Produces`, `Run`, `Expected`, `Create`, `Modify`, `Read`, `Preserve`, `Step`, `Task`처럼 독자에게 주는 영어 label과 문장을 한국어로 바꾼다. 경로와 exact row content는 바꾸지 않는다.

- [ ] **Step 3: catalog와 validator token을 확인한다**

실행:

~~~powershell
$paths = @(
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md'
)
foreach ($path in $paths) {
  $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  if ([regex]::IsMatch($text, '(?m)[ \t]+$')) { throw "Trailing whitespace: $path" }
  if (([regex]::Matches($text, '(?m)^(```|~~~)').Count % 2) -ne 0) { throw "Unbalanced fence: $path" }
}
$plan = Get-Content -LiteralPath $paths[1] -Raw -Encoding UTF8
foreach ($term in @('PRD-FR-001','PRD-NFR-012','ARC-014','THR-012','CTL-020','VG-024','WBS-035','RSK-014','RTM_VALIDATE=PASS')) {
  if (-not $plan.Contains($term)) { throw "Missing exact plan token: $term" }
}
'PRODUCT_PROCESS_TRANSLATION=PASS'
~~~

기대 결과: `PRODUCT_PROCESS_TRANSLATION=PASS`.

- [ ] **Step 4: checkpoint를 확인한다**

실행:

~~~powershell
git diff --check -- 'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md' 'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md'
git status --short
'PROPOSED_COMMIT=docs: translate ForgeOps documentation process artifacts'
~~~

Git add 또는 commit은 수행하지 않는다.

---

### Task 5: README와 이식 가이드 번역

**파일:**
- Modify if needed: `README.md`
- Modify if needed: `docs/README.md`
- Modify: `docs/agent-harness/PORTING_GUIDE.md`

**인터페이스:**
- 입력: 사용자 진입점과 Harness 이식 안내
- 출력: 링크 목적지와 복사 가능한 계약 예제를 보존한 한국어 안내 문서

- [ ] **Step 1: 독자용 영어 자연어를 번역한다**

제목·역할명처럼 고유명인 `Portable Agent Harness`, `Main orchestrator`, `Part analyst`, `Work executor`는 유지할 수 있다. 독자에게 설명하는 영어 문장, 표 제목, 주의문과 단계 설명은 한국어로 번역한다. 링크 label은 번역할 수 있지만 괄호 안 destination은 유지한다.

- [ ] **Step 2: 이식 가이드의 복사 영역을 보존한다**

`PORTING_GUIDE.md`의 YAML, JSON, prompt, command와 schema block은 번역하지 않는다. block 앞뒤의 설명과 절 제목만 번역한다. `AVAILABLE`, `UNAVAILABLE`, `UNKNOWN`, `NONE`, `PROJECT`, `NAMED_RESOURCES`, `NAMED_COMMANDS`, `NAMED_HOSTS`는 그대로 둔다.

- [ ] **Step 3: 세 문서의 링크를 검증한다**

실행:

~~~powershell
$paths = @('README.md','docs/README.md','docs/agent-harness/PORTING_GUIDE.md')
$root = [System.IO.Path]::GetFullPath((Get-Location).Path)
$prefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$pattern = [regex]'\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)'
foreach ($path in $paths) {
  $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  foreach ($match in $pattern.Matches($text)) {
    $relative = $match.Groups[1].Value
    if ($relative -match '^[A-Za-z]+://') { continue }
    $candidate = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $path) $relative))
    if (-not $candidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Link escapes root: $path -> $relative" }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Broken link: $path -> $relative" }
  }
}
'ENTRY_GUIDE_LINKS=PASS'
~~~

기대 결과: `ENTRY_GUIDE_LINKS=PASS`.

- [ ] **Step 4: checkpoint를 확인한다**

실행:

~~~powershell
git diff --check -- 'README.md' 'docs/README.md' 'docs/agent-harness/PORTING_GUIDE.md'
git status --short
'PROPOSED_COMMIT=docs: translate ForgeOps entry documentation'
~~~

Git add 또는 commit은 수행하지 않는다.

---

### Task 6: 제품·아키텍처·보안·품질·프로젝트 문서 번역

**파일:**
- Modify if needed: `docs/handoff/forgeops-full-handoff.md`
- Modify if needed: `docs/product/prd.md`
- Modify if needed: `docs/architecture/system-architecture.md`
- Modify if needed: `docs/security/threat-model.md`
- Modify if needed: `docs/quality/verification-and-evaluation-plan.md`
- Modify if needed: `docs/project/wbs.md`
- Modify if needed: `docs/project/risk-register.md`
- Modify if needed: `docs/project/requirements-traceability-matrix.md`

**인터페이스:**
- 입력: 이미 한국어 중심인 8개 기준 문서
- 출력: 계약 고유어를 유지하면서 독립 영어 자연어가 정리된 한국어 문서 세트

- [ ] **Step 1: 번역 후보를 보수적으로 식별한다**

실행:

~~~powershell
$paths = @(
  'docs/handoff/forgeops-full-handoff.md',
  'docs/product/prd.md',
  'docs/architecture/system-architecture.md',
  'docs/security/threat-model.md',
  'docs/quality/verification-and-evaluation-plan.md',
  'docs/project/wbs.md',
  'docs/project/risk-register.md',
  'docs/project/requirements-traceability-matrix.md'
)
rg -n '^[[:space:]>#*+-]*[A-Za-z][A-Za-z ]{15,}' $paths
~~~

한국어 문장 속 technical term, ID, enum, artifact 이름과 deliverable 이름은 번역 대상이 아니다. 완전한 영어 설명 문장, 자연어 표 label과 독자 안내만 번역한다.

- [ ] **Step 2: 소유 문서별 자연어를 번역한다**

PRD requirement와 acceptance 의미, ARC dependency, THR→CTL→VG, WBS predecessor·person-day, risk probability×impact, RTM row field는 바꾸지 않는다. `public-safe`, `fresh evidence`, `fail-closed`, `baseline_blocked`, `policy_blocked`처럼 문서 간 계약어는 그대로 유지하거나 한국어 설명을 덧붙이되 철자를 변경하지 않는다.

- [ ] **Step 3: catalog 수와 RTM closure를 검증한다**

실행:

~~~powershell
$definitions = [ordered]@{
  PRD = @{ Path='docs/product/prd.md'; Pattern='(?m)^\|\s*(PRD-(?:FR|NFR)-\d{3})\s*\|'; Count=37 }
  ARC = @{ Path='docs/architecture/system-architecture.md'; Pattern='(?m)^\|\s*(ARC-\d{3})\s*\|'; Count=14 }
  THR = @{ Path='docs/security/threat-model.md'; Pattern='(?m)^\|\s*(THR-\d{3})\s*\|'; Count=12 }
  CTL = @{ Path='docs/security/threat-model.md'; Pattern='(?m)^\|\s*(CTL-\d{3})\s*\|'; Count=20 }
  VG = @{ Path='docs/quality/verification-and-evaluation-plan.md'; Pattern='(?m)^\|\s*(VG-\d{3})\s*\|'; Count=24 }
  WBS = @{ Path='docs/project/wbs.md'; Pattern='(?m)^\|\s*(WBS-\d{3})\s*\|'; Count=35 }
  RSK = @{ Path='docs/project/risk-register.md'; Pattern='(?m)^\|\s*(RSK-\d{3})\s*\|'; Count=14 }
}
$catalogs = @{}
foreach ($entry in $definitions.GetEnumerator()) {
  $text = Get-Content -LiteralPath $entry.Value.Path -Raw -Encoding UTF8
  $ids = @([regex]::Matches($text, $entry.Value.Pattern) | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
  if ($ids.Count -ne $entry.Value.Count) { throw "$($entry.Key) expected $($entry.Value.Count), got $($ids.Count)" }
  $catalogs[$entry.Key] = $ids
}
$rtm = Get-Content -LiteralPath 'docs/project/requirements-traceability-matrix.md' -Raw -Encoding UTF8
$start = $rtm.IndexOf('## 3. 요구사항 추적표', [System.StringComparison]::Ordinal)
$end = $rtm.IndexOf('## 4. Coverage 요약', [System.StringComparison]::Ordinal)
if ($start -lt 0 -or $end -le $start) { throw 'RTM boundaries missing' }
$matrix = $rtm.Substring($start, $end - $start)
foreach ($catalog in $catalogs.GetEnumerator()) {
  foreach ($id in $catalog.Value) { if (-not $matrix.Contains($id)) { throw "Orphan $($catalog.Key): $id" } }
}
'PRODUCT_DOC_CATALOGS=PASS PRD=37 ARC=14 THR=12 CTL=20 VG=24 WBS=35 RSK=14 orphan=0'
~~~

기대 결과: `PRODUCT_DOC_CATALOGS=PASS PRD=37 ARC=14 THR=12 CTL=20 VG=24 WBS=35 RSK=14 orphan=0`.

- [ ] **Step 4: checkpoint를 확인한다**

실행:

~~~powershell
git diff --check -- 'docs/handoff/forgeops-full-handoff.md' 'docs/product/prd.md' 'docs/architecture/system-architecture.md' 'docs/security/threat-model.md' 'docs/quality/verification-and-evaluation-plan.md' 'docs/project/wbs.md' 'docs/project/risk-register.md' 'docs/project/requirements-traceability-matrix.md'
git status --short
'PROPOSED_COMMIT=docs: complete Korean product documentation translation'
~~~

Git add 또는 commit은 수행하지 않는다.

---

### Task 7: 전체 번역 보존성·구조·범위 검증

**파일:**
- Verify: 번역 대상 일반 Markdown 15개
- Verify unchanged: 실행 계약 5개
- Preserve: 번역 설계서와 이 계획

**인터페이스:**
- 입력: Task 2~6의 번역 결과
- 출력: 한국어 번역 완료 여부와 원문 고정 요소 보존 증빙

- [ ] **Step 1: strict UTF-8, fence, whitespace와 incomplete marker를 검사한다**

실행:

~~~powershell
$targets = @(
  'README.md','docs/README.md','docs/agent-harness/PORTING_GUIDE.md',
  'docs/architecture/system-architecture.md','docs/handoff/forgeops-full-handoff.md',
  'docs/product/prd.md','docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md','docs/project/wbs.md',
  'docs/quality/verification-and-evaluation-plan.md','docs/security/threat-model.md',
  'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md',
  'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md',
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md'
)
$utf8 = [System.Text.UTF8Encoding]::new($false, $true)
$markers = @('T' + 'ODO','T' + 'BD','F' + 'IXME','X' + 'XX')
foreach ($path in $targets) {
  $text = $utf8.GetString([System.IO.File]::ReadAllBytes((Resolve-Path $path)))
  if ([string]::IsNullOrWhiteSpace($text)) { throw "Empty: $path" }
  if (([regex]::Matches($text, '(?m)^(```|~~~)').Count % 2) -ne 0) { throw "Unbalanced fence: $path" }
  if ([regex]::IsMatch($text, '(?m)[ \t]+$')) { throw "Trailing whitespace: $path" }
  foreach ($marker in $markers) { if ($text.Contains($marker)) { throw "Incomplete marker: $path -> $marker" } }
}
'MARKDOWN_STRUCTURE=PASS files=15'
~~~

- [ ] **Step 2: fenced code와 inline code token을 `HEAD` 원문과 비교한다**

실행:

~~~powershell
function Get-ProtectedSegments([string]$text) {
  $segments = [System.Collections.Generic.List[string]]::new()
  $inline = [System.Collections.Generic.List[string]]::new()
  $lines = $text -split "`r?`n"
  $inside = $false
  $marker = $null
  $buffer = [System.Collections.Generic.List[string]]::new()
  foreach ($line in $lines) {
    if (-not $inside -and $line -match '^(```|~~~)') {
      $inside = $true
      $marker = $Matches[1]
      $buffer = [System.Collections.Generic.List[string]]::new()
      $buffer.Add($line)
      continue
    }
    if ($inside) {
      $buffer.Add($line)
      if ($line -match ('^' + [regex]::Escape($marker) + '[ \t]*$')) {
        $segments.Add(($buffer -join "`n"))
        $inside = $false
        $marker = $null
      }
      continue
    }
    foreach ($match in [regex]::Matches($line, '`[^`\r\n]+`')) { $inline.Add($match.Value) }
  }
  if ($inside) { throw 'Unclosed protected fence' }
  [pscustomobject]@{ Fences=@($segments); Inline=@($inline) }
}
$targets = @(
  'README.md','docs/README.md','docs/agent-harness/PORTING_GUIDE.md',
  'docs/architecture/system-architecture.md','docs/handoff/forgeops-full-handoff.md',
  'docs/product/prd.md','docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md','docs/project/wbs.md',
  'docs/quality/verification-and-evaluation-plan.md','docs/security/threat-model.md',
  'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md',
  'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md',
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md'
)
foreach ($path in $targets) {
  $before = git show "HEAD:$path"
  if ($LASTEXITCODE -ne 0) { throw "Cannot read baseline: $path" }
  $after = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  $left = Get-ProtectedSegments(($before -join "`n"))
  $right = Get-ProtectedSegments($after)
  if (($left.Fences -join "`n---SEGMENT---`n") -cne ($right.Fences -join "`n---SEGMENT---`n")) { throw "Fenced content changed: $path" }
  if (($left.Inline -join "`n") -cne ($right.Inline -join "`n")) { throw "Inline code changed: $path" }
}
'PROTECTED_TEXT=PASS files=15'
~~~

기대 결과: `PROTECTED_TEXT=PASS files=15`.

- [ ] **Step 3: 모든 상대 Markdown 링크를 검증한다**

실행:

~~~powershell
$targets = @(
  'README.md','docs/README.md','docs/agent-harness/PORTING_GUIDE.md',
  'docs/architecture/system-architecture.md','docs/handoff/forgeops-full-handoff.md',
  'docs/product/prd.md','docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md','docs/project/wbs.md',
  'docs/quality/verification-and-evaluation-plan.md','docs/security/threat-model.md',
  'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md',
  'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md',
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md'
)
$root = [System.IO.Path]::GetFullPath((Get-Location).Path)
$prefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
$pattern = [regex]'\[[^\]]+\]\(([^)#]+\.md)(?:#[^)]+)?\)'
$count = 0
foreach ($path in $targets) {
  $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
  foreach ($match in $pattern.Matches($text)) {
    $relative = $match.Groups[1].Value
    if ($relative -match '^[A-Za-z]+://') { continue }
    $candidate = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $path) $relative))
    if ($candidate -ne $root -and -not $candidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Link escapes root: $path -> $relative" }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Broken link: $path -> $relative" }
    $count++
  }
}
"MARKDOWN_LINKS=PASS count=$count"
~~~

- [ ] **Step 4: 제외 계약 hash와 변경 범위를 검증한다**

실행:

~~~powershell
$expectedHashes = [ordered]@{
  'AGENTS.md' = '4eb7469ba8f31e1d08e442eb8e947e13ab100cfb'
  '.github/copilot-instructions.md' = '8a905165f665eeefbb1e8922d24dc220dac38f77'
  '.github/agents/main_instruction.prompt.md' = '5c5b332215192069d6e9ccc4c5cade2d16a4b902'
  '.github/agents/part_agent.prompt.md' = '4c67abdc314a9d411a4a05a1f7ec0c6ad3944275'
  '.github/agents/work_agent.prompt.md' = 'ab884ceedc59ab6c4e7a6c0c123f1fec85ce3b19'
}
foreach ($entry in $expectedHashes.GetEnumerator()) {
  $actual = (git hash-object -- $entry.Key).Trim()
  if ($actual -cne $entry.Value) { throw "Excluded contract changed: $($entry.Key)" }
}
$allowed = @(
  'README.md','docs/README.md','docs/agent-harness/PORTING_GUIDE.md',
  'docs/architecture/system-architecture.md','docs/handoff/forgeops-full-handoff.md',
  'docs/product/prd.md','docs/project/requirements-traceability-matrix.md',
  'docs/project/risk-register.md','docs/project/wbs.md',
  'docs/quality/verification-and-evaluation-plan.md','docs/security/threat-model.md',
  'docs/superpowers/plans/2026-07-12-portable-agent-harness-v2.md',
  'docs/superpowers/plans/2026-07-14-forgeops-product-documentation.md',
  'docs/superpowers/specs/2026-07-12-portable-agent-harness-design.md',
  'docs/superpowers/specs/2026-07-14-forgeops-product-documentation-design.md',
  'docs/superpowers/specs/2026-07-19-markdown-korean-translation-design.md',
  'docs/superpowers/plans/2026-07-19-markdown-korean-translation.md'
)
$status = @(git status --porcelain=v1 --untracked-files=all)
foreach ($line in $status) {
  if ($line.Length -lt 4) { continue }
  $path = $line.Substring(3).Replace('\','/')
  if ($path -notin $allowed) { throw "Out-of-scope change: $path" }
}
'EXCLUDED_CONTRACTS=PASS files=5'
'TRANSLATION_SCOPE_FINAL=PASS'
~~~

- [ ] **Step 5: 번역 완전성을 수동 의미 검토한다**

다음을 15개 파일에서 line-by-line으로 확인하고 PASS/FAIL을 기록한다.

1. 독자에게 주는 완전한 영어 제목·문단·목록·표 설명이 한국어다.
2. 남은 영어는 고유명, technical term, ID, enum, field, 경로, URL, command 또는 fenced example이다.
3. 번역이 authority, approval, state, evidence, risk, phase와 validator 의미를 약화하지 않는다.
4. `Run`·`Expected` 같은 실행 안내 label은 한국어지만 명령과 expected literal은 원문이다.
5. 한국어 문장이 기계 번역투 없이 주어·목적어와 기술 관계를 보존한다.

기대 결과: `TRANSLATION_SEMANTIC_REVIEW=PASS items=5/5`.

- [ ] **Step 6: 최종 checkpoint를 출력한다**

실행:

~~~powershell
git diff --check
git status --short --branch --untracked-files=all
'PROPOSED_COMMIT_SET=15 translated general Markdown documents plus translation design and plan'
'PROPOSED_COMMIT=docs: translate ForgeOps general documentation into Korean'
~~~

Git add, commit, push, PR 또는 외부 게시는 수행하지 않는다.

---

## 완료 증빙

다음 fresh 결과가 모두 있어야 번역 완료를 보고한다.

- `TRANSLATION_SCOPE=PASS targets=15 excluded=5`
- `HARNESS_DESIGN_TRANSLATION=PASS`
- `HARNESS_PLAN_TRANSLATION=PASS`
- `PRODUCT_PROCESS_TRANSLATION=PASS`
- `ENTRY_GUIDE_LINKS=PASS`
- `PRODUCT_DOC_CATALOGS=PASS PRD=37 ARC=14 THR=12 CTL=20 VG=24 WBS=35 RSK=14 orphan=0`
- `MARKDOWN_STRUCTURE=PASS files=15`
- `PROTECTED_TEXT=PASS files=15`
- `MARKDOWN_LINKS=PASS`
- `EXCLUDED_CONTRACTS=PASS files=5`
- `TRANSLATION_SCOPE_FINAL=PASS`
- `TRANSLATION_SEMANTIC_REVIEW=PASS items=5/5`

검증하지 못한 항목은 원인과 함께 `NOT_RUN`으로 남기며 서술형 확신으로
대체하지 않는다.
