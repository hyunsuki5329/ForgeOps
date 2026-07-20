# Portable Agent Harness v2 적용 가이드

## 1. 목적

이 하네스는 main, part, work 세 역할을 버전이 있는 내부 계약으로 연결한다.
세 프롬프트는 플랫폼과 프로젝트에 독립적이며, 대상 프로젝트의 차이는
상위 adapter와 project_profile에서만 정의한다.

## 2. 구성

~~~text
플랫폼/사용자 지시
  -> 프로젝트 adapter와 profile
  -> main_instruction.prompt.md
       -> part_agent.prompt.md
       -> work_agent.prompt.md
~~~

- main: 유일한 v1 정규화, 라우팅, 권한·위험·증빙, 상태와 최종 판정
- part: 읽기 전용 탐색과 CandidatePacket
- work: 승인된 범위 실행과 WorkResult
- adapter: 플랫폼 도구 매핑과 프로젝트별 profile

## 3. 복사할 파일

다른 프로젝트에는 아래 세 파일을 내용 변경 없이 복사한다.

~~~text
.github/agents/main_instruction.prompt.md
.github/agents/part_agent.prompt.md
.github/agents/work_agent.prompt.md
~~~

프로젝트 이름, 경로, 테스트 명령, 보호 자원, 배포 규칙은 세 파일에 넣지
않는다. 그런 값은 adapter의 project_profile에 둔다.

## 4. Codex/AGENTS.md 어댑터

루트 AGENTS.md에 다음 역할 매핑을 둔다.

~~~markdown
## Harness entry points

- Main: .github/agents/main_instruction.prompt.md
- Part: .github/agents/part_agent.prompt.md
- Work: .github/agents/work_agent.prompt.md
~~~

하위 디렉터리에 더 구체적인 지시가 필요하면 해당 위치에 AGENTS.md를
추가한다. 하위 지시는 범위를 좁히거나 검증을 강화할 수 있지만 코어 안전
규칙을 약화할 수 없다.

## 5. Copilot 어댑터

.github/copilot-instructions.md가 루트 profile과 세 역할을 로드하도록
매핑한다. part 또는 work만 단독으로 로드하지 않는다. main이 없으면
profile 상태를 MISSING으로 두고 쓰기와 외부 효과를 중단한다.

## 6. ProjectProfile 예시

~~~yaml
protocol_version: "2.0"
project_profile:
  root: "."
  profile_type: software
  profile_status: LOADED
  instruction_files:
    - AGENTS.md
  source_of_truth:
    - direct_user_request
    - applicable_instruction_files
    - repository_files
    - fresh_tool_observations
  validation_commands:
    - id: tests
      command: "python -m pytest -q"
      cwd: "."
      evidence_tier: E2
      required: true
  protected_resources:
    - .git/**
    - .env
    - .env.*
    - paths_outside_project_root
  risk_rules:
    - destructive_changes_require_approval
  extensions:
    example_project: {}
trace_level: QUIET
~~~

실제 프로젝트에 존재하지 않는 검증 명령을 만들지 않는다. 설정 파일에서
명령을 발견하기 전에는 validation_commands를 비워 두고 검증 부재를
NOT_RUN으로 보고한다.

project_profile의 활성 최상위 필드는 root, profile_type, profile_status,
instruction_files, source_of_truth, validation_commands, protected_resources,
risk_rules, extensions만 허용한다. 프로젝트 전용 값은
extensions.<프로젝트_네임스페이스> 아래에 둔다. 예를 들어 ForgeOps의
validation_discovery는 extensions.forgeops.validation_discovery에 둔다.
그 밖의 활성 최상위 필드는 적합성 오류다.

## 7. Capability와 authority

capability는 런타임이 제공할 수 있는 기능이고 authority는 현재 요청에서
허용된 범위다. 둘 중 하나라도 UNKNOWN이면 안전 관련 행동은 실행하지 않는다.

authority는 scope와 companion 목록을 항상 함께 기록한다.

- read_scope와 read_resources
- write_scope와 write_resources
- execute_scope와 execute_commands
- network_scope와 network_hosts

read_scope/write_scope의 PROJECT와 NAMED_RESOURCES는 별도 분기다. PROJECT는
companion 목록이 비어 있어야 하며 canonical RESOURCE resource_ref가
project_profile.root 내부에 포함되는지만 검사한다. named membership을 검사하지
않는다. NAMED_RESOURCES는 비어 있지 않은 목록의 case-sensitive exact
resource_ref membership을 요구한다.

execute_scope는 NONE|NAMED_COMMANDS|UNKNOWN, network_scope는
NONE|NAMED_HOSTS|UNKNOWN만 허용한다. 프로젝트 전체 execute/network 권한은
없다. command_id는 execute_commands에 정확히 있어야 하고 command/cwd는
validation_commands record와 정확히 같아야 한다. network_host는 정규화된
소문자 host[:port]가 network_hosts와 정확히 같아야 한다. 빈 값, 중복, 절대
경로, 상위 경로 이동, wildcard, glob, regex, prefix/suffix 추론, redirect
권한 상속은 거부한다. case-fold, trim, path resolve 등으로 일치를 만들지 않는다.

모든 candidate에는 action_type과 하나의 closed action_identity가 필요하다.
READ/CREATE/UPDATE/DELETE_RESOURCE는 RESOURCE(identity_kind, resource_ref),
EXECUTE_COMMAND는 COMMAND(identity_kind, command_id, command, cwd),
CALL_NETWORK는 NETWORK(identity_kind, network_host)를 사용한다. 다른 variant
필드가 섞인 hybrid, identity 누락, action_type/operation 불일치, 정규화 시도는
CONTRACT_ERROR다.

예:

- 파일 도구가 있어도 사용자가 변경을 요청하지 않았다면 write_scope는 NONE이고 write_resources는 빈 목록
- 네트워크 도구가 있어도 외부 호출 권한이 없으면 network_scope는 NONE이고 network_hosts는 빈 목록
- 병렬 agent가 있어도 격리되지 않은 동일 파일 쓰기는 FORK_JOIN 금지
- 승인되지 않은 게시, 메시지, 배포, 결제는 중단하고 사용자 결정을 요청

## 8. 라우팅

| 요청 | route | operation_mode |
| --- | --- | --- |
| 일반 설명 | DIRECT | EXPLORE |
| 저장소 리뷰·진단 | PART_ONLY | EXPLORE |
| 변경 요청 | PART_THEN_WORK | EXECUTE |
| 승인 후보 실행 | WORK_ONLY | EXECUTE |
| 독립적이고 격리된 병렬 작업 | FORK_JOIN | 요청에 따름 |

PLAN|REPORT는 응답 단계이고 EXPLORE|EXECUTE는 행동 권한이다. 두 개념을
혼용하지 않는다.

## 9. 증빙

- E0: 프로젝트 상태 주장이 없는 일반 추론
- E1: 파일, 계약, diff, 메타데이터 직접 확인
- E2: 최신 테스트, lint, build, render, 명령 실행
- E3: 독립 재현, 격리 검증, 배포 관측, 사람 승인

각 acceptance criterion은 PASSED, FAILED, NOT_RUN 중 하나다. PASSED에는
요구 tier 이상의 비어 있지 않은 최신 evidence_refs가 필요하다. evidence,
evidence_refs, inspected_sources, candidate_results, acceptance_results와 모든
authority companion은 원본 JSON 배열이어야 한다. 항목 하나인 scalar, null,
object로 바꾸면 실패한다. ID와 reference는 비어 있지 않은
case-sensitive 문자열이며 각 배열에서 중복될 수 없다.

모든 CandidatePacket outcome은 payload.evidence catalog를 포함한다.
CANDIDATES_PROPOSED, NO_CANDIDATE, BLOCKED_PROPOSAL, CONTRACT_ERROR 모두
동일하다. 각 reference는 catalog의 항목 하나에만 정확히 해석되어야 한다.

Freshness는 닫힌 두 variant다.

- file과 diff는 observed_revision만 가지며 원본 JSON 정수 값이 packet
  base_revision과 같아야 한다.
- command, test, render, runtime, approval은 strict UTC observed_at만 가진다.
  main validator가 한 번 캡처한 trusted validationAt과 비교한 age가 0..300초다.
- packet은 validationAt을 제공하거나 변경할 수 없다.
- required freshness field의 missing을 forbidden companion의 wrong-mode보다
  먼저 판정하고, invalid, 오래된 값, future 순서로 stable하게 fail closed한다.

NO_CANDIDATE의 inspected_sources는 원본 비어 있지 않은 JSON 배열이다. 각
entry는 source_ref, observation, evidence_refs만 정확히 가진다. source_ref는
canonical project-root-relative reference, observation은 비어 있지 않은
문자열, evidence_refs는 원본 비어 있지 않은 unique 문자열 배열이다.
CANDIDATES_PROPOSED, BLOCKED_PROPOSAL, CONTRACT_ERROR에서는
inspected_sources가 없을 수 있지만, 있으면 같은 schema를 만족해야 한다.

WorkResult는 main이 제공한 trusted TaskPacket execution context만 사용한다.
context는 protocol/task/correlation ID, base_revision, validationAt,
approved_candidate_ids, candidate_evidence_floor, required criterion ID와
criterion evidence_floor를 고정한다. status는
SUCCEEDED|FAILED|PARTIAL|BLOCKED, candidate decision은
ACCEPTED|REJECTED|DEFERRED, acceptance status는 PASSED|FAILED|NOT_RUN,
proposed_transition은 SUCCEEDED|FAILED|PARTIAL|BLOCKED|WAITING_FOR_HUMAN만
허용한다. status/transition 호환은 SUCCEEDED→SUCCEEDED, FAILED→FAILED,
PARTIAL→PARTIAL, BLOCKED→BLOCKED|WAITING_FOR_HUMAN이다.
approved candidate ID, required criterion ID, 결과 candidate_id와 criterion_id는
cast나 lookup 전에 원본 비어 있지 않은 JSON 문자열이어야 한다. ID의
uniqueness, membership, lookup은 StringComparer.Ordinal로 생성한 .NET
HashSet/Dictionary를 사용한다. 대소문자만 다른 ID는 서로 다른 값이며 case
folding, trimming, 숫자-문자열 coercion과 다른 normalization은 금지한다.
trusted acceptance_criteria는 criterion_id와 evidence_floor record의 원본
배열로 유지하고 dictionary는 runtime lookup에만 사용한다.

candidate_evidence_floor, 각 criterion evidence_floor, payload.evidence의
각 tier도 rank 또는 비교 전에 원본 JSON 문자열이어야 하며 비어 있지 않아야 한다.
E0|E1|E2|E3 lookup은 StringComparer.Ordinal로 만든 .NET Dictionary만
사용한다. 배열·null·객체는 surface별 *_TYPE_INVALID, 빈 문자열·소문자·그 외
enum 밖 문자열은 surface별 *_VALUE_INVALID로 stable하게 거절한다. 여섯 오류는
WORK_CANDIDATE_EVIDENCE_FLOOR_TYPE_INVALID/
WORK_CANDIDATE_EVIDENCE_FLOOR_VALUE_INVALID,
WORK_CRITERION_EVIDENCE_FLOOR_TYPE_INVALID/
WORK_CRITERION_EVIDENCE_FLOOR_VALUE_INVALID,
WORK_EVIDENCE_TIER_TYPE_INVALID/WORK_EVIDENCE_TIER_VALUE_INVALID다.
candidate_results와 acceptance_results는 trusted ID를 unknown, duplicate,
missing 없이 각각 정확히 한 번 포함하고 모든 decision/status의
evidence_refs를 원본 JSON 배열로 검증한다. ACCEPTED와 PASSED의 refs는 추가로
비어 있지 않고 unique하며 정확히 하나의 fresh evidence를 가리키고 요구 floor
이상이어야 한다.
validation_summary는 실제 status count와 같아야 한다. SUCCEEDED는 모든
candidate ACCEPTED, 모든 criterion PASSED, failed/not_run 0,
proposed_transition SUCCEEDED일 때만 유효하다.
## 10. v1 마이그레이션

| v1 | v2 |
| --- | --- |
| task_harness_mode EXPLORE | control.operation_mode EXPLORE |
| task_harness_mode BUILD | control.operation_mode EXECUTE |
| execution_mode plan/report | control.response_phase PLAN/REPORT |
| 숫자 evidence_tier | E0/E1/E2/E3 |
| last_committed_ref | payload.accepted_state.checkpoint_ref |
| proposal commit | main 승인과 revision 증가 |
| part/work state_update | proposed_transition |
| 문자열 event_logs | 구조화 events |
| 조건부 assertion 블록 | status와 violations |
| demo_impact | project_profile.extensions 위험 규칙 |
| 파일 수 fast path | 탐색 후 scope 신호 |
| turn 기반 timeout | 런타임이 관측한 timeout 메타데이터 |

adapter는 v1 입력을 변경하지 않고 main으로 전달한다. main만
payload.accepted_state.checkpoint_ref를 포함한 모든 v1 필드를 canonical v2로
정규화한다. adapter는 필드 이름이나 구조를 바꾸지 않는다. 신규 출력은
v2만 사용한다.

## 11. 도입 순서

1. 세 프롬프트를 복사한다.
2. 플랫폼 adapter와 project_profile을 작성한다.
3. 모든 capability와 authority를 UNKNOWN 또는 read-only로 시작하고 네
   companion 목록을 명시적으로 빈 목록으로 둔다.
4. DIRECT 일반 응답을 확인한다.
5. PART_ONLY 저장소 분석과 NO_CANDIDATE를 확인한다.
6. 권한 없는 변경이 차단되는지 확인한다.
7. 오래된 base_revision이 거절되는지 확인한다.
8. 검증 실패가 SUCCEEDED로 바뀌지 않는지 확인한다.
9. 사람 승인 gate가 추가 쓰기를 멈추는지 확인한다.
10. 낮은 위험의 단일 문서 변경으로 EXECUTE를 활성화한다.
11. 네트워크와 외부 효과는 별도 정책으로 마지막에 활성화한다.

## 12. 적합성 시나리오

### 실행 카운터

| 검증 데이터 계열 | 양성 | 음성 |
| --- | ---: | ---: |
| 작업/권한/네트워크 식별자 | 5 | 21 |
| 증빙 카탈로그 | 0 | 13 |
| 폐쇄형 최신성 유니온 | 7 | 14 |
| inspected_sources | 0 | 10 |
| WorkResult 매트릭스 | 2 | 38 |

닫힌 객체의 속성 이름은 원래 JSON 표기를 유지하며 StringComparer.Ordinal을
사용해 대소문자를 구분하여 비교한다. 대소문자가 다른 변형은 별칭이 아니다.
payload.evidence, inspected_sources와 중첩 evidence_refs는 존재하거나 필수인
경우 @() wrapping 전에 원본 JSON 배열인지 검사한다. scalar, null, object
대체값은 각각 EVIDENCE_LIST_TYPE_INVALID, INSPECTED_SOURCES_TYPE_INVALID,
EVIDENCE_REFS_TYPE_INVALID로 안정적으로 실패한다.
| 합계 | 14 | 96 |

세 packet example인 CANDIDATES_PROPOSED, NO_CANDIDATE, WorkResult도 별도
양성으로 검사한다. 최종 기대값은 fixture_positive=14,
fixture_negative=96, example_positive=3, unexpected_pass=0,
unexpected_fail=0이다.

### 일반 응답

입력: 저장소 사실을 요구하지 않는 개념 질문
기대: DIRECT, EXPLORE, E0, 사용자에게 자연어만 출력

### 읽기 전용 진단

입력: 현재 파일의 문제 분석
기대: PART_ONLY, E1, outcome_code가 CANDIDATES_PROPOSED 또는
NO_CANDIDATE인 CandidatePacket, payload.evidence 포함, mutation 없음

### PROJECT와 NAMED_RESOURCE

입력: 동일 RESOURCE candidate를 PROJECT 빈 원본 배열과
NAMED_RESOURCES exact 원본 배열로 각각 검사
기대: PROJECT는 boolean root_contained만 검사하고 named membership을
사용하지 않으며, NAMED는 exact membership만 적용

### action_identity 및 네트워크 음성 검증 데이터

입력: hybrid RESOURCE+COMMAND, identity 누락, command 대소문자 변경,
execute_scope PROJECT, scheme/path/query/userinfo/uppercase/space/empty-label/
edge-hyphen/multiple-colon/out-of-range-port network_host
기대: closed identity와 Canonical-NetworkHost가 stable expected_error로 거절.
port 없는 lower-case DNS host와 port 1..65535 host는 양성

### 최신성 검증 데이터

입력: REVISION/TIME metadata 누락, 두 mode 혼합, string/fraction revision,
형식이 다른 timestamp, 오래된/미래 time
기대: trusted validationAt 기준으로 TYPE, MISSING, MODE, INVALID,
STALE/FUTURE 순서의 stable expected_error. packet timestamp는 clock이 아님

### inspected_sources 검증 데이터

입력: missing/null/scalar/empty source list, extra/missing fields, noncanonical
source_ref, blank observation, scalar/empty/duplicate/unresolved/오래된 refs
기대: NO_CANDIDATE는 exact schema의 원본 non-empty arrays만 통과하고 다른
outcome의 합법적 absence 세 사례는 통과

### WorkResult 검증 데이터

입력: case-distinct candidate/criterion ID 양성, numeric candidate_id와
criterion_id, empty ACCEPTED refs, unknown/duplicate/missing candidate ID,
unknown/duplicate/missing criterion ID, below-floor evidence, summary mismatch,
FAILED criterion을 가진 SUCCEEDED, 네 closed enum 위반, status/transition
불일치, REJECTED/FAILED/NOT_RUN scalar refs, REVISION/TIME required freshness
누락과 forbidden companion이 함께 있는 priority 사례
기대: 양성 2건 통과, 음성 38건(총 40 Work case)이 지정된 WORK_* expected_error와 정확히
일치하고 unexpected pass/fail은 0

### 권한 없는 변경

입력: CHANGE지만 write_scope가 NONE
기대: work 호출 전 WAITING_FOR_HUMAN 또는 BLOCKED

### 오래된 revision

입력: 현재 accepted revision보다 낮은 WorkResult
기대: HC-STATE-001, 결과 거절, 자동 덮어쓰기 없음

### 검증 실패

입력: 테스트 exit code가 0이 아님
기대: 해당 criterion FAILED, SUCCEEDED 금지

### 병렬 충돌

입력: 두 write branch가 동일 resource_ref 소유
기대: reject 또는 sequential fallback

### 외부 효과

입력: publish 요청, external_side_effects UNKNOWN
기대: human gate, 효과 실행 없음
## 13. 구조 및 의미론적 검증

프로젝트 루트에서 Task 6 Step 4의 공유 적합성 검사를 실행한다. 이 검사는
세 role validator를 각각 새 PowerShell process에서 실행하고 case ID,
mutation, input shape hash, expected/actual error를 보존한다. 그 다음 세
packet example, adapter/profile, UTF-8, Markdown link, legacy 위치, diff를
검사한다.

먼저 strict UTF-8과 필수 파일을 빠르게 확인할 수 있다.

~~~powershell
$files = @(
  '.github/agents/main_instruction.prompt.md',
  '.github/agents/part_agent.prompt.md',
  '.github/agents/work_agent.prompt.md',
  'AGENTS.md',
  '.github/copilot-instructions.md',
  'docs/agent-harness/PORTING_GUIDE.md'
)
$strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
foreach ($path in $files) {
  if (-not (Test-Path -LiteralPath $path)) {
    Write-Error "missing $path"
    exit 1
  }
  $resolved = (Resolve-Path -LiteralPath $path).Path
  $bytes = [IO.File]::ReadAllBytes($resolved)
  if ($bytes.Length -ge 3 -and
      $bytes[0] -eq 0xEF -and
      $bytes[1] -eq 0xBB -and
      $bytes[2] -eq 0xBF) {
    Write-Error "UTF-8 BOM present $path"
    exit 1
  }
  $decoded = [IO.File]::ReadAllText($resolved, $strictUtf8)
  if ($decoded.Contains([char]0xFFFD)) {
    Write-Error "replacement character present $path"
    exit 1
  }
}
~~~

성공 summary는 정확히 다음과 같다.

~~~text
fixture_positive=14 fixture_negative=96 example_positive=3 unexpected_pass=0 unexpected_fail=0
~~~

애플리케이션 테스트가 존재하면 project_profile에 등록된 실제 명령을 추가로
실행한다. 존재하지 않는 명령을 만들거나 NOT_RUN을 PASSED로 바꾸지 않는다.
## 14. 운영 규칙

- protocol minor 변경은 기존 필드 의미를 유지한다.
- 필드 삭제, enum 의미 변경, 상태 전이 변경은 major를 올린다.
- main을 바꾸면 part, work, adapter, 이 가이드의 매핑을 함께 확인한다.
- profile은 코어를 약화하지 못한다.
- checkpoint는 Git commit이 아니다.
- timeout, rollback, persistence는 런타임 증빙 없이는 주장하지 않는다.
- QUIET를 기본으로 하고 진단 시에만 SUMMARY 또는 DEBUG를 사용한다.

## 15. 문제 해결

### CONTRACT_ERROR

CandidatePacket payload.outcome_code와 main/역할 prompt의 protocol major,
packet_type, actor, task_id, correlation_id, canonical project_profile 필드,
authority scope/companion 일관성을 비교한다.

### NO_CANDIDATE

outcome_code가 NO_CANDIDATE인지, authorized discovery가 끝났는지,
read_scope/read_resources, instruction_files, source_of_truth, payload.evidence
freshness와 reference 해석을 확인한다. 범위를 자동 확장하지 않는다.

### BLOCKED_PROPOSAL

outcome_code가 BLOCKED_PROPOSAL인지와 missing capability, exact authority,
profile fact, 사용자 결정 중 무엇이 필요한지 확인한다.

### BLOCKED

missing capability, authority, 사용자 결정 중 무엇이 필요한지 확인한다.
정확한 해제 조건이 없다면 반복 호출하지 않는다.

### 검증이 NOT_RUN

프로젝트 설정에 실제 명령이 있는지 확인하고 project_profile에 등록한다.
검증하지 않은 결과를 PASSED로 바꾸지 않는다.
