# W5 로컬 Snapshot·Baseline·Context Pack 설계

## 1. 목적

W5는 Phase 1 local vertical slice의 source 경계를 구현한다. 범위는 WBS-013 immutable snapshot provider, WBS-014 baseline runner와 baseline artifact, WBS-015 code retrieval과 Context Pack이다. 후속 W6의 Main·Part·Work 흐름은 W5가 제공하는 고정 source identity와 재현 가능한 context를 소비한다.

완료 조건은 파일 존재가 아니다. 동일 repository 상태에서 snapshot identity가 결정론적으로 재현되고, dirty·untracked 상태가 manifest에 보존되며, 원본 write 없이 별도 workspace가 생성돼야 한다. Baseline과 retrieval은 같은 snapshot을 사용해야 하며 VG-010과 VG-011의 등록 결과가 fresh E2 `PASSED`일 때만 WBS-013~WBS-015를 완료 처리한다.

## 2. 범위와 비범위

### 포함

- Git repository의 HEAD, tracked, staged, modified, deleted, untracked 상태를 결합한 content-addressed snapshot
- source manifest와 snapshot identity 검증
- snapshot에서 파생한 독립 ephemeral workspace
- trusted profile의 exact argv와 cwd를 사용하는 baseline 실행
- baseline result artifact와 failure classification
- 결정론적 code retrieval과 source-attributed Context Pack
- repository instruction을 비신뢰 data로 유지하는 injection negative 검증
- VG-010·VG-011 verifier, fixture, result와 W5 문서 상태 갱신

### 제외

- 외부 database, queue, object store와 daemon service
- remote repository clone, fetch, package download와 network access
- LLM embedding, vector database와 semantic ranking service
- patch 적용, Work 실행, recovery와 cancellation lifecycle
- 외부 publish, PR, deployment와 remote write
- Phase 1 Exit 또는 W6 이후 WBS 완료 주장

## 3. 설계 원칙

- Python 표준 라이브러리와 저장소의 기존 `jsonschema` 의존성만 사용한다.
- snapshot identity, Git commit, task revision, run identity를 서로 대체하지 않는다.
- 파일 경로는 canonical project-root-relative POSIX literal로 기록한다.
- symlink, parent traversal, absolute path, `.git`, protected/credential-like path와 비정상 file type은 materialize 전에 거부한다.
- snapshot은 content manifest hash로 불변성을 검증한다. OS permission만으로 immutability를 주장하지 않는다.
- Git status와 file enumeration은 NUL-delimited plumbing command를 `shell=False`로 실행한다.
- baseline command는 trusted fixture/profile의 exact argv와 cwd만 허용한다. raw shell string, glob expansion과 command normalization은 없다.
- Context Pack content는 data plane이다. source text가 authority, policy, budget, approval, tool schema 또는 accepted state를 변경하지 못한다.
- 모든 결과는 closed, bounded, public-safe JSON이며 atomic replace로 기록한다.

## 4. 작업 분해

| 순서 | 작업 | WBS / VG | 선행 조건 | 독립 완료 기준 |
| --- | --- | --- | --- | --- |
| 1 | Snapshot·Baseline·Context 계약과 fixture | WBS-013~015 / VG-010~011 | Phase 0 READY | schema와 ordered positive/negative catalog가 self-validation 통과 |
| 2 | Immutable Snapshot Provider | WBS-013 / VG-010 | 작업 1 | source 보존, manifest 재현, snapshot/workspace 격리와 negative path 거부 |
| 3 | Trusted Baseline Runner | WBS-014 / VG-010·013 | 작업 2 | exact profile 실행, bounded artifact, baseline unhealthy와 runner failure 분리 |
| 4 | Code Retrieval과 Context Pack | WBS-015 / VG-010·011 | 작업 2 | 반복 retrieval 동일, provenance 완전, injection control 승격 0 |
| 5 | 통합 verifier, fresh evidence와 W5 마감 | WBS-013~015 / VG-010·011 | 작업 1~4 | 등록 명령 4개 E2 PASSED, 문서와 profile 일치, 전체 회귀 통과 |

작업 3과 작업 4는 snapshot contract만 공유하고 기능적으로 독립이다. 구현은 동일 파일 충돌과 검토 순서를 명확히 하기 위해 순차 수행한다.

## 5. 작업 1 — 계약과 fixture

### 산출물

- `contracts/forgeops-snapshot-contract/1.0/schema.json`
- `contracts/forgeops-context-pack/1.0/schema.json`
- `fixtures/forgeops-snapshot-baseline/suite.json`
- `fixtures/forgeops-context-security/suite.json`
- `tests/snapshot_context/test_contracts.py`

### Snapshot contract

Snapshot manifest는 정확히 다음 의미를 보존한다.

- `snapshot_version`: `1.0`
- `snapshot_id`: canonical manifest body의 SHA-256 reference
- `source`: repository root의 공개-safe logical label, HEAD SHA 또는 `UNBORN`, Git tree state hash
- `entries`: path 오름차순의 file record
- file record: `path`, `size`, `sha256`, `mode`, `source_states`
- `source_states`: `tracked`, `staged`, `modified`, `untracked` 중 해당 path에 동시에 적용되는 값을 위 순서로 보존하는 non-empty array
- `dirty`: staged, modified, deleted 또는 untracked 상태가 하나라도 있으면 true
- `deleted_paths`: HEAD/index에는 있으나 working tree snapshot에서 제외된 canonical path 목록
- `manifest_sha256`: `snapshot_id`와 `manifest_sha256`를 제외한 canonical body hash

`snapshot_id`는 `sha256:<manifest_sha256>`이며 Git SHA, task revision이나 rollback evidence로 사용하지 않는다.

### Baseline artifact

Baseline artifact는 `snapshot_id`, trusted `profile_id`, ordered command result, start/end time과 exit category를 포함한다. 각 command record는 `command_id`, exact `argv`, canonical `cwd`, `status`, `exit_code`, `stdout_bytes_seen`, `stderr_bytes_seen`, `output_truncated`와 공개 field만으로 만든 `result_fingerprint`만 기록한다. stdout/stderr 원문과 그 raw-content hash는 artifact에 저장하지 않는다.

### Context Pack contract

Context Pack은 `context_pack_version`, `snapshot_id`, normalized query token 목록, ordered item과 summary를 가진다. 각 item은 `path`, `sha256`, `size`, `media_type`, `selection_reason`, `score`, `excerpt`, `trust="UNTRUSTED_SOURCE"`를 포함한다. `control_claims_accepted`는 항상 false다.

### Stable 오류

- `SNAPSHOT_SOURCE_INVALID`
- `SNAPSHOT_PATH_INVALID`
- `SNAPSHOT_FILE_TYPE_FORBIDDEN`
- `SNAPSHOT_CONTENT_CHANGED`
- `SNAPSHOT_MANIFEST_INVALID`
- `BASELINE_PROFILE_INVALID`
- `BASELINE_COMMAND_REJECTED`
- `BASELINE_TIMEOUT`
- `BASELINE_UNHEALTHY`
- `CONTEXT_QUERY_INVALID`
- `CONTEXT_PROVENANCE_INVALID`
- `CONTEXT_INJECTION_ESCAPE`

Fixture는 positive/negative case의 ID, kind, mutation과 expected result를 ordered exact catalog로 고정한다. unknown field, duplicate ID, case 변경과 catalog 순서 변경은 runner error로 닫는다.

## 6. 작업 2 — Immutable Snapshot Provider

### 책임

현재 working tree의 최종 visible bytes를 읽어 content manifest를 만들고, 그 bytes만 별도 snapshot directory와 ephemeral workspace에 materialize한다. 원본 repository와 `.git` 내부에는 write하지 않는다.

### 입력과 출력

```text
create_snapshot(source_root, destination_root, repository_label)
  -> SnapshotBundle(manifest, snapshot_root, workspace_root)
```

`destination_root`는 source root 밖의 호출자 소유 임시 directory여야 한다. `snapshot_root`는 manifest bytes와 일치하는 source image이고, `workspace_root`는 후속 baseline과 retrieval이 사용하는 별도 copy다.

### Git 관찰

- `git rev-parse --verify HEAD`
- `git ls-files -z --cached --others --exclude-standard`
- `git status --porcelain=v2 -z --untracked-files=all`

모든 호출은 argv array, `shell=False`, bounded timeout으로 실행한다. Git이 없거나 repository가 아니거나 status parsing이 불완전하면 `SNAPSHOT_SOURCE_INVALID`로 거부한다.

### 파일 경계

- regular file만 포함한다.
- symlink와 reparse point는 follow하지 않고 거부한다.
- `.git`, `.env`, `.env.*`, credential/secret 이름과 repository 밖 resolved path를 거부한다.
- ignored file은 포함하지 않는다.
- deleted path는 entries에 넣지 않고 `deleted_paths`에 기록한다.
- file read 전후 size와 mtime을 비교하고 content hash가 materialize 후 달라지면 전체 임시 bundle을 폐기한다.

### 불변성과 cleanup

provider는 임시 sibling directory에 완전한 bundle을 만든 뒤 destination으로 atomic rename한다. 실패하면 destination manifest를 남기지 않는다. Snapshot immutability는 materialize 후 전체 entry hash 재검증으로 증명하고, workspace 변경은 snapshot_root hash에 영향을 주지 않아야 한다.

## 7. 작업 3 — Trusted Baseline Runner

### 책임

동일 `snapshot_id`의 workspace에서 trusted profile command를 순서대로 실행해 변경 전 상태를 기록한다.

### Trusted profile

Profile은 closed JSON object다.

- `profile_id`
- `profile_version`
- `commands[]`: `command_id`, `argv[]`, `cwd`, `timeout_seconds`, `max_output_bytes`

`argv`는 non-empty string array이고 `cwd`는 snapshot workspace 내부 canonical relative path다. shell operator, empty argument policy 위반, duplicate command ID, absolute/traversal cwd, wildcard command identity와 unknown field를 거부한다. 실행은 `subprocess.run(..., shell=False)`만 사용한다.

### 결과 분류

- 모든 command exit 0: `PASSED`
- trusted command가 실행됐지만 exit non-zero: `BASELINE_UNHEALTHY`
- timeout: `BASELINE_TIMEOUT`
- executable/cwd/profile/runtime 오류: `BASELINE_RUNNER_ERROR`

Non-zero baseline은 agent regression이 아니라 기존 실패로 보존한다. 후속 patch 검증은 이 artifact와 동일 `snapshot_id`를 요구한다.

### 출력 제한

stdout/stderr는 별도 reader thread가 chunk 단위로 drain하고 byte count와 cap 초과 여부만 남긴다. cap을 넘은 원문은 계속 drain하되 보존하지 않으며 process 종료 뒤 즉시 폐기한다. `result_fingerprint`는 command identity, status, exit code와 truncation flag만 canonical hash한다. artifact에는 원문, raw-content hash, absolute path, environment와 secret-like value를 기록하지 않는다.

## 8. 작업 4 — Code Retrieval과 Context Pack

### 책임

Snapshot manifest에 등록된 text file에서 요청 query와 일치하는 bounded context를 결정론적으로 선택한다.

### Retrieval 규칙

- query는 1~32개의 case-folded ASCII/Unicode alphanumeric token으로 분해한다.
- manifest entry 가운데 UTF-8 decode가 가능하고 file size가 256 KiB 이하인 file만 고려한다.
- path token exact match, path substring, content token 빈도를 고정 weight로 계산한다.
- score 내림차순, path 오름차순으로 정렬하며 `top_k`는 1~20이다.
- 동일 snapshot, query와 top_k는 byte-identical Context Pack을 생성한다.
- excerpt는 token 주변의 최대 1,024 UTF-8 character이며 file 전체를 대체하지 않는다.

### Selection provenance

`selection_reason`은 `PATH_EXACT`, `PATH_SUBSTRING`, `CONTENT_MATCH`의 ordered list와 match count를 포함한다. 모든 item hash는 snapshot manifest entry와 다시 일치해야 한다.

### Injection 경계

Repository text의 `ignore previous`, authority/policy/budget/approval 주장과 tool invocation 문장은 content로 반환될 수 있지만 control로 해석하지 않는다. Context Pack schema에는 authority, policy, budget, approval, tool schema와 accepted state field가 없다. Injection negative fixture는 이러한 문장이 존재해도 `control_claims_accepted=false`, 외부 effect 0, protected read 0임을 검증한다. Context Pack은 runtime-local이며 public verification result에는 excerpt 원문을 복사하지 않는다.

Binary, undecodable, oversized, protected, missing 또는 hash-mismatch file은 결과에서 제외하거나 provenance 오류로 전체 실패하며 조용히 다른 bytes로 대체하지 않는다.

## 9. 작업 5 — 통합 검증과 등록

### 등록 명령

- profile `forgeops-snapshot-baseline`
  - `snapshot-identity`
  - `baseline-retrieval-repeat`
- profile `forgeops-context-security`
  - `context-provenance`
  - `injection-negative`

### 산출물

- `tools/snapshot_context/model.py`
- `tools/snapshot_context/snapshot.py`
- `tools/snapshot_context/baseline.py`
- `tools/snapshot_context/retrieval.py`
- `tools/snapshot_context/verify.py`
- `tests/snapshot_context/`
- `artifacts/verification/vg-010-snapshot-identity-result.json`
- `artifacts/verification/vg-010-baseline-retrieval-result.json`
- `artifacts/verification/vg-011-context-provenance-result.json`
- `artifacts/verification/vg-011-injection-negative-result.json`
- 갱신된 `AGENTS.md`, `README.md`, WBS, RTM과 verification plan

Verifier는 등록된 schema/suite/result/command identity의 exact literal만 수용한다. 네 command는 각자 독립 public-safe E2 result를 atomic write한다. result는 input SHA-256, ordered case outcome, effect counters와 summary를 포함한다.

### W5 완료 판정

- WBS-013: `snapshot-identity`와 `baseline-retrieval-repeat`이 snapshot immutability, dirty preservation, source write 0을 fresh E2로 입증할 때 `WBS_DONE`
- WBS-014: baseline fixture가 exact profile, same snapshot과 baseline failure classification을 fresh E2로 입증할 때 `WBS_DONE`
- WBS-015: `context-provenance`와 `injection-negative`가 provenance 완전성과 critical escape 0을 fresh E2로 입증할 때 `WBS_DONE`

어느 command라도 `FAILED` 또는 `NOT_RUN`이면 해당 WBS는 완료 처리하지 않는다. W6 이후 작업과 Phase 1 Exit는 계속 `WBS_NOT_STARTED`와 `NOT_RUN`을 유지한다.

## 10. 데이터 흐름

```text
Git working tree
  -> safe NUL-delimited inventory
  -> canonical content manifest
  -> snapshot_id
  -> immutable snapshot_root
  -> independent workspace_root
       -> trusted baseline profile -> baseline artifact
       -> deterministic retrieval -> Context Pack
  -> VG-010 / VG-011 verifier results
  -> W5 documentation status
```

Baseline과 Context Pack은 manifest를 복사해 신뢰하지 않고 `snapshot_id`와 각 entry hash를 재검증한다. Artifact와 Context Pack의 `snapshot_id`가 다르면 결합을 거부한다.

## 11. 오류 처리와 안전성

- CLI parse, input read, Git, schema와 subprocess 오류는 stack trace 없이 stable public category로 변환한다.
- result path는 command별 등록 literal만 허용하며 arbitrary output path를 거부한다.
- source 또는 manifest 오류 뒤 partial snapshot, workspace, manifest와 success result를 남기지 않는다.
- baseline timeout 뒤 새 command를 시작하지 않는다.
- retrieval provenance가 하나라도 불완전하면 Context Pack을 `PASSED`로 기록하지 않는다.
- protected/secret-like path는 byte read 전에 거부한다.
- no network, no external write, no credential injection을 invariant로 유지한다.

## 12. 테스트 전략

### Unit

- canonical path, protected path, symlink/reparse, deleted file와 hash 변경
- clean, staged, modified, deleted, untracked Git 상태
- manifest ordering, repeated identity와 workspace/snapshot separation
- trusted profile exactness, raw shell rejection, timeout과 output truncation
- retrieval ordering, query validation, UTF-8/size 경계와 repeatability
- injection text가 control field나 effect를 만들지 않는지 검증

### Contract/CLI

- schema self-validation과 closed fixture catalog
- 네 등록 command의 exact input/output identity
- runner failure가 기존 PASSED artifact를 성공으로 보존하지 않는지 검증
- public result에 absolute path, raw stdout/stderr, environment와 forbidden key가 없는지 검사

### 통합

- temp Git repository에 staged, modified, deleted, untracked file을 만들고 snapshot 생성
- snapshot에서 baseline과 retrieval을 실행한 뒤 원본 tree hash와 status가 바뀌지 않았는지 확인
- workspace file 변경 뒤 snapshot root와 baseline artifact가 변하지 않는지 확인
- 같은 입력을 두 번 실행해 snapshot manifest와 Context Pack의 의미 결과가 동일한지 확인

### 회귀

- `tests/snapshot_context` 전체
- 기존 프로젝트 전체 `python -m unittest discover -s tests -p "test_*.py"`
- `git diff --check`

## 13. 승인 범위와 handoff

이 설계는 로컬 repository file, temporary directory와 local subprocess만 변경·실행한다. Network, external publication, destructive reset, 원본 repository 삭제와 credential 접근은 포함하지 않는다.

W5 완료 후 W6는 `snapshot_id`, baseline artifact와 Context Pack을 immutable input으로 받아 Main normalization과 Part/Work routing을 구현한다. W6는 W5 내부를 우회해 working tree를 직접 source of truth로 사용할 수 없다.
