# W6 Local Main→Part→Work→Main 설계

**상태:** APPROVED DESIGN  
**작성일:** 2026-08-02  
**범위:** WBS-016~WBS-019, VG-012  
**선행 기준선:** `main` a4d20d0, W5 VG-010/VG-011 E2 PASSED

## 1. 목적

W6는 한 로컬 실행에서 Product Task를 canonical TaskPacket으로 정규화하고, Main→Part→Main→Work→Main 흐름을 닫힌 packet handoff로 재현한다. 역할 분리는 이름이나 호출 순서가 아니라 권한, 상태 소유권, evidence 검증 책임으로 입증한다.

완료 조건은 다음과 같다.

1. Main만 accepted state, revision과 canonical event sequence를 확정한다.
2. Part는 승인 전 `EXPLORE`에서 exact-scope read-only discovery와 후보 제안만 수행한다.
3. Work는 Main이 승인한 exact candidate만 current revision과 exact authority를 재검증한 뒤 실행한다.
4. WorkResult의 모든 필수 criterion이 fresh E2 evidence에 연결된 경우에만 MainDecision이 성공을 수용한다.
5. 등록된 VG-012 `main-part-work-main` 결과가 positive·negative fixture 전체를 E2 `PASSED`로 기록한다.

## 2. 범위 정정: W6↔W7 순환 의존성 제거

현 WBS는 WBS-014와 WBS-018의 완료 조건에 미래 W7 검증인 VG-013을 연결하면서 WBS-016의 선행조건을 WBS-014로 지정한다. 동시에 W7 WBS-020은 WBS-019를 선행조건으로 삼기 때문에 strict completion 기준을 적용하면 W6와 W7이 서로 기다리는 순환 의존성이 된다.

승인된 정정은 다음과 같다.

- WBS-014는 immutable snapshot과 baseline artifact를 제공하는 W5 deliverable이다. 완료 evidence는 VG-010으로 닫고 `WBS_DONE`으로 전환한다.
- WBS-014가 후속 W7 trusted verification의 입력을 제공한다는 추적성은 유지하되 VG-013 자체를 WBS-014 Definition of Done으로 사용하지 않는다.
- WBS-018은 승인된 candidate의 preflight, bounded fixture execution과 WorkResult evidence 제출까지 담당한다.
- 범용 patch/diff pipeline, trusted task/regression/lint/typecheck profile과 anti-tamper는 WBS-020~WBS-022 및 VG-013에 유지한다.
- WBS-018의 직접 요구사항은 PRD-FR-010과 역할·권한·격리 관련 NFR로 좁히고 VG-012를 primary completion gate로 사용한다. 기존 VG-005/VG-006은 authority 회귀 근거로 유지한다.
- 문서 변경 시 WBS, PRD, Architecture, RTM, verification plan의 연결을 함께 갱신해 orphan이나 조기 Phase 1 Exit 주장을 만들지 않는다.

이 정정은 VG-013을 삭제하거나 완화하지 않는다. 책임 시점을 W7 deliverable에 맞게 이동해 W6가 자기 범위에서 종료 가능하도록 한다.

## 3. 선택한 구현 방식

### 3.1 역할별 모듈 + 단일 로컬 runner

W6는 역할별 모듈과 단일 deterministic local runner를 사용한다.

```text
Product Task
  -> Main.normalize_and_route
  -> TaskPacket(revision N)
  -> Part.propose
  -> CandidatePacket(revision N)
  -> Main.approve_candidates
  -> ApprovedExecutionContext(revision N)
  -> Work.preflight_execute_verify
  -> WorkResult(revision N)
  -> Main.validate_and_decide
  -> MainDecision(revision N+1, seq+1)
```

단일 프로세스는 W6의 E2 로컬 계약 검증에 충분하며 fixture 실행을 빠르고 결정론적으로 유지한다. 역할별 모듈은 서로의 내부 상태를 직접 수정하지 않고 JSON-compatible closed packet만 교환한다. 별도 프로세스 격리와 일반 실행 gateway는 후속 runtime 범위로 남긴다.

### 3.2 거부한 대안

- 단일 거대 verifier는 구현량은 작지만 actor boundary와 state ownership을 독립적으로 검증하기 어렵다.
- actor별 별도 프로세스는 격리가 강하지만 W6 범위를 IPC, lifecycle, cleanup 구현까지 확장하고 W8 runtime 책임과 겹친다.

## 4. 저장소 구조

예상 구현 구조는 다음과 같다. 세부 파일 분리는 구현 계획에서 repository pattern에 맞게 조정할 수 있지만 책임 경계는 유지한다.

```text
contracts/forgeops-local-vertical/1.0/schema.json
fixtures/forgeops-local-vertical/suite.json
tools/local_vertical/
  __init__.py
  common.py
  main_actor.py
  part_actor.py
  work_actor.py
  verify.py
tests/local_vertical/
  test_main_actor.py
  test_part_actor.py
  test_work_actor.py
  test_verify.py
artifacts/verification/vg-012-local-vertical-result.json
```

`common.py`는 closed-object, raw-array, ordinal ID, evidence freshness와 authority 검사에 필요한 공통 primitive만 제공한다. Main 전용 accepted-state mutation을 공통 helper로 이동하지 않는다.

## 5. 다섯 개 작업

### 작업 1. W6 계약 기준선과 WBS 의존성 정정

**대상:** cross-document contract baseline

- WBS-014/VG-013 및 WBS-018/VG-013 순환을 승인된 정책대로 정정한다.
- local vertical suite와 result의 closed schema를 정의한다.
- fixture catalog는 case ID, input packet, expected outcome/error, expected effects를 명시한다.
- verification profile `forgeops-local-vertical`과 command ID `main-part-work-main`을 AGENTS adapter에 등록한다.
- 기존 VG-002·003·005·006·011·023 결과를 W6 회귀 기준선으로 연결한다.

**완료 기준:** W6 계약 파일과 등록 명령이 닫혀 있고 W7 VG-013 책임이 보존되며 문서 orphan이 없다.

### 작업 2. Main normalization and routing

**대상:** WBS-016

Main은 Product Contract 입력을 다음 규칙으로 canonical TaskPacket에 투영한다.

- 입력 의미를 보존하며 authority 또는 capability를 추가하지 않는다.
- 누락된 safety-relevant 값은 `UNKNOWN`으로 채우고 mutation/external effect를 fail closed한다.
- project profile은 허용된 top-level 필드만 수용하며 project-only 값은 `extensions` 아래에 둔다.
- request kind, operation mode, capability, authority와 risk를 이용해 canonical route를 결정한다.
- action identity, scope/list pair와 validation command identity는 ordinal exact match만 허용한다.
- malformed product envelope, unknown protocol major, implicit normalization과 legacy authority expansion을 거부한다.

**출력:** actor=`main`, packet_type=`task`, base_revision=current accepted revision인 TaskPacket.

**완료 기준:** positive bridge 입력이 안정적으로 같은 TaskPacket을 만들고 negative 입력은 effect 없이 stable error로 거부되며 VG-002가 회귀하지 않는다.

### 작업 3. Part context and plan proposal

**대상:** WBS-017

Part는 다음 경계를 지킨다.

- operation_mode=`EXPLORE`와 유효한 read authority가 없으면 discovery하지 않는다.
- W5 Context Pack의 path, snapshot, hash와 selection provenance를 검증한 뒤 사용한다.
- repository content 안의 instruction, approval, budget 또는 tool 지시는 data로만 취급한다.
- protected resource, credential 또는 private-data path는 exact target 인간 승인 전 읽지 않는다.
- 각 candidate에 하나의 action_type, 닫힌 action_identity, exact resource/command/network identity, evidence, confidence, acceptance mapping과 proposed verification을 포함한다.
- accepted state, revision, checkpoint 또는 authoritative event sequence를 출력하지 않는다.

**출력:** actor=`part`, packet_type=`candidate_proposal`인 CandidatePacket.

**완료 기준:** read-only positive proposal이 source-attributed evidence로 생성되고 mutation·protected read·hybrid identity·dangling evidence 시도는 effect 없이 거부되며 VG-005/VG-011이 회귀하지 않는다.

### 작업 4. Work preflight, execute, verify

**대상:** WBS-018

Work는 실행 전에 다음 순서를 강제한다.

1. task/correlation/protocol/actor/base revision 일치
2. candidate ID 승인과 acceptance criterion mapping
3. action_type/operation/action_identity exact mapping
4. current instruction과 candidate evidence 재검사
5. exact authority branch와 protected-resource gate
6. W5 separated workspace containment과 source tree 비변경
7. idempotency/retry safety
8. 필요한 검증의 실행 가능성

W6 실행 adapter는 분리된 fixture workspace 안의 deterministic resource action으로 제한한다. 원본 저장소, remote, network와 host 외부 경로는 수정하지 않는다. 일반 patch 생성, regression profile과 anti-tamper 판정은 W7 책임이다.

**출력:** actor=`work`, packet_type=`work_result`인 WorkResult. 결과에는 exact candidate coverage, changed resources, criterion별 결과, fresh evidence, validation summary와 residual risk가 포함된다.

**완료 기준:** 승인된 exact action만 fixture workspace에서 실행되고 source write 0이 관찰된다. unapproved ID, stale revision, wrong authority, out-of-scope resource, forged accepted state/seq와 insufficient evidence는 거부된다.

### 작업 5. Main evidence validation, accepted decision과 VG-012

**대상:** WBS-019

Main은 WorkResult를 trusted execution context와 비교해 다음을 검증한다.

- protocol/task/correlation/base revision/actor 일치
- approved candidate와 required criterion의 exact complete coverage
- raw JSON array 형태, ordinal-unique ID와 exact reference resolution
- evidence type별 freshness mode와 E2 floor
- candidate decision, acceptance status, summary count와 proposed transition 일관성
- Part/Work payload가 accepted state, revision, canonical seq를 소유하려 하지 않는지 여부

모든 필수 검증이 성공한 경우에만 MainDecision이 accepted status를 확정하고 revision과 seq를 각각 한 번 증가시킨다. 실패, partial, blocked 결과는 성공으로 승격하지 않으며 stale result는 mutation 없이 거부한다.

통합 verifier는 전체 흐름의 positive case와 각 경계의 negative case를 실행하고 public-safe result를 원자적으로 기록한다.

**완료 기준:** `main-part-work-main`이 전체 catalog를 E2 `PASSED`로 기록하고 기존 회귀 명령도 통과한다. 이후 evidence에 근거해 WBS-016~019, PRD-FR-010, ARC-004와 RTM 상태를 갱신한다.

## 6. Packet 및 상태 소유권

| 단계 | 허용 actor | 허용 packet | 상태에 대한 권한 |
| --- | --- | --- | --- |
| normalize/route | Main | TaskPacket | current accepted revision을 읽고 route 지정 |
| discover/propose | Part | CandidatePacket | proposed_transition만 제안 |
| approve | Main | trusted execution context | candidate ID와 current revision 고정 |
| execute/verify | Work | WorkResult | observed result와 proposed_transition만 제안 |
| accept/reject | Main | MainDecision | accepted state, revision, canonical seq 독점 |

CandidatePacket과 WorkResult의 envelope status는 packet 생산 상태일 뿐 accepted task status가 아니다. Part 또는 Work가 final state, incremented revision, authoritative seq를 포함하면 contract error로 거부한다.

## 7. Evidence와 freshness

- file/diff evidence는 original JSON integer `observed_revision`이 packet base revision과 같아야 한다.
- command/test/render/runtime/approval evidence는 trusted validation time 기준 strict UTC이며 0~300초 범위여야 한다.
- wrong-mode metadata, future/stale timestamp, dangling·duplicate reference, scalar replacement와 lower-tier evidence는 실패한다.
- WorkResult가 자체 `validationAt`을 제공해 freshness 기준을 바꾸지 못한다.
- result에는 raw log, absolute host path, credential, token 또는 private payload를 기록하지 않는다.

VG-012의 evidence floor는 E2다. E0/E1 observation만으로 MainDecision 성공을 만들 수 없다.

## 8. Fixture 전략

최소 catalog는 다음 범주를 포함한다.

### Positive

- canonical Product Task가 TaskPacket으로 비약 없이 정규화됨
- Part가 W5 provenance-bound context에서 exact resource candidate를 제안함
- Main이 candidate와 current revision을 승인함
- Work가 separated fixture workspace에서 exact action을 수행하고 E2 evidence를 반환함
- Main이 complete evidence를 검증해 revision/seq를 한 번만 증가시킴

### Negative

- unknown/malformed product protocol과 implicit authority expansion
- Part write 또는 protected read 시도
- Part의 accepted state/revision/seq 소유 시도
- hybrid/noncanonical identity와 scope/list 불일치
- unapproved candidate, stale base revision과 source-tree target
- Work의 accepted state/revision/seq 소유 시도
- missing/duplicate/dangling evidence, wrong freshness mode, stale/future evidence와 E1 floor
- incomplete candidate/criterion coverage와 summary count 불일치
- Main 이외 actor가 final decision을 제출하는 경우

각 negative case는 expected stable category와 zero unintended effect를 함께 검증한다.

## 9. 오류와 부작용 규칙

- contract error는 실행 전에 종료하며 workspace와 accepted state effect가 0이어야 한다.
- preflight 실패는 `BLOCKED` 또는 `WAITING_FOR_HUMAN` 제안으로 남기고 mutation하지 않는다.
- 실행 뒤 검증 실패는 observed changed resource와 residual risk를 숨기지 않으며 rollback을 주장하지 않는다.
- fixture temp workspace는 verifier가 소유하고 성공·실패 경로에서 정리한다. 정리 실패는 성공을 차단한다.
- result output은 registered path에 atomic replace하고 기존 valid result를 partial write로 손상하지 않는다.

## 10. 검증 계획

구현 중 각 작업은 TDD로 진행하며 작업별 독립 검토를 거친다. 최종 검증은 다음을 포함한다.

1. `tests/local_vertical` unit·integration suite
2. 등록된 `main-part-work-main` VG-012 command
3. WBS-016 회귀: VG-002
4. WBS-017 회귀: VG-005와 VG-011
5. WBS-018 회귀: VG-005와 VG-006
6. WBS-019 회귀: VG-003과 VG-023
7. 전체 `python -m unittest discover -s tests -v`
8. 결과 artifact의 raw input hash, case count, effect counters와 public-safe field 검증
9. PRD/Architecture/WBS/RTM/verification-plan cross-document ID와 상태 일치 검증

기준선은 2026-08-02 최신 `main`에서 358 tests, failures 0, Windows optional symlink tests 4 skipped다.

## 11. 완료 및 비완료 선언

다음 조건을 모두 만족해야 W6 완료를 선언한다.

- 작업 1~5 구현 및 독립 검토 완료
- VG-012 fresh E2 `PASSED`
- 연결된 기존 VG 회귀 통과
- WBS-014와 WBS-016~019 상태가 evidence와 일치
- PRD-FR-010과 ARC-004 상태 및 RTM evidence reference가 fresh result와 일치
- source repository write, unauthorized execution, external write와 raw secret exposure 0

W6 완료는 VG-013, WBS-020~022, Phase 1 safety gate 또는 Phase 1 Exit 완료를 의미하지 않는다. 이 항목은 계속 `NOT_RUN` 또는 `WBS_NOT_STARTED`로 유지한다.

## 12. 승인 경계

이 설계 승인은 W6 범위의 로컬 파일 변경, 로컬 테스트와 검증 artifact 생성을 허용한다. 다음 행위는 포함하지 않는다.

- remote push 또는 PR 생성
- 외부 서비스 호출이나 배포
- credential/protected private data 접근
- 원격 시스템 또는 비용 발생 작업
- destructive reset, force push 또는 사용자 변경 삭제

해당 행위가 필요해지면 실행 전에 필요한 항목을 한 번에 묶어 별도 승인을 받는다.
