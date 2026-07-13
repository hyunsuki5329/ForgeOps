# ForgeOps 제품 기초 문서 체계 설계

**일자:** 2026-07-14
**상태:** 사용자 설계 승인 완료, 기초 문서 작성 전
**대상 저장소:** D:/VS/ForgeOps/ForgeOps
**기준 문서:** docs/handoff/forgeops-full-handoff.md
**대상 독자:** 1인 개발자, 포트폴리오 검토자

## 1. 배경

ForgeOps에는 Portable Agent Harness Protocol 2.0 구현과 전체 제품 비전을
설명하는 핸드오프가 있다. 그러나 제품 요구사항, 실행 일정, 아키텍처,
보안, 품질, 추적성, 위험을 역할별로 관리하는 기초 문서 세트는 아직
없다.

이번 작업은 핸드오프를 반복 요약하는 것이 아니라, 핸드오프의 제품
비전과 현재 구현 기준선을 실행 가능한 문서 체계로 정규화한다. 문서는
1인 개발자가 10주 동안 Phase 0과 Phase 1을 관리할 수 있어야 하며,
제3자가 요구사항에서 검증 증빙까지 따라갈 수 있는 포트폴리오 자료가
되어야 한다.

## 2. 목표

1. 전체 제품 범위인 Phase 0~4의 요구사항을 한국어 PRD로 정리한다.
2. Phase 0~1을 상세화한 상대 일정 10주 WBS를 만든다.
3. WBS에서 Phase 2~4는 제품 비전을 보존하되 상위 마일스톤으로 관리한다.
4. 제품, 아키텍처, 보안, 품질, 프로젝트 관리의 책임을 문서별로 분리한다.
5. 요구사항, 설계, 작업, 검증, 증빙의 추적 관계를 한 곳에서 관리한다.
6. 현재 구현과 계약 및 미래 계획을 명시적으로 구분한다.
7. 1인 개발자가 유지할 수 있도록 중복 서술과 문서 수를 제한한다.

## 3. 비목표

- 제품 runtime, sandbox, API, 데이터베이스 또는 UI를 구현하지 않는다.
- 현행 Protocol 2.0, 역할 프롬프트 또는 핸드오프의 계약을 변경하지 않는다.
- Phase 2~4의 세부 스프린트나 확정 일정을 만들지 않는다.
- 검증되지 않은 기술 스택 또는 구현 상태를 확정 사실로 기록하지 않는다.
- 외부 게시, 배포, PR 생성 또는 원격 저장소 푸시를 수행하지 않는다.
- 별도의 결정 기록 문서나 운영 매뉴얼을 추가하지 않는다.

## 4. 채택한 접근법

균형형 8문서 세트를 채택한다. 최소형 문서 세트보다 보안과 검증 근거를
명확하게 보존하면서도, 완전한 조직형 문서 체계보다 1인 유지관리 비용이
낮다.

문서별 단일 책임을 유지한다. PRD는 무엇과 왜를, 아키텍처와 보안 및
품질 문서는 어떻게와 통제를, WBS와 RTM 및 위험 등록부는 실행과 증빙을
담당한다. 같은 설명을 여러 문서에 복제하지 않고 안정적인 식별자로
연결한다.

## 5. 출처와 우선순위

저장소 전체에서 충돌이 발생하면 다음 순서를 적용한다.

1. 직접 사용자 요청과 적용 범위에 해당하는 지시 파일
2. 현행 Protocol 2.0 파일, 저장소 내용, 새로 실행한 검증 결과
3. docs/handoff/forgeops-full-handoff.md
4. 이번 작업에서 생성하는 파생 문서

핸드오프는 제품 비전과 현재 기준선을 제공하지만, IMPLEMENTED 표시는
실제 저장소 파일이나 fresh evidence로 확인할 수 있을 때만 사용한다.
파생 문서는 상위 출처의 권한, 승인, fail-closed, fresh evidence 불변식을
약화할 수 없다.

위 순서는 최초 문서 세트를 작성할 때 적용한다. 8개 문서가 사용자 검토를
거쳐 기준선 상태가 된 뒤에는 아래 영역별 기준 소유 문서가 해당 영역의
규범이며, 핸드오프는 비전과 인수인계 요약으로 사용한다. Protocol 2.0
불변식과 fresh repository evidence는 계속 상위다. 기준 소유 문서의
변경으로 핸드오프 요약이 달라지면 같은 변경에서 핸드오프를 동기화하거나,
즉시 동기화할 수 없는 이유와 목표 주차를 RSK 항목으로 기록한다.

문서 영역별 기준 소유자는 다음과 같다.

| 영역 | 기준 문서 |
| --- | --- |
| 제품 목표, 범위, 요구사항, 성공 기준 | docs/product/prd.md |
| 구성요소, 상태, 계약, 데이터 흐름 | docs/architecture/system-architecture.md |
| 위협, 보안 통제, 잔여 위험 | docs/security/threat-model.md |
| 검증 방법, 평가, 품질 게이트 | docs/quality/verification-and-evaluation-plan.md |
| 일정, 의존성, 산출물, 완료 정의 | docs/project/wbs.md |
| 문서 간 추적 관계와 누락 | docs/project/requirements-traceability-matrix.md |
| 프로젝트 위험과 대응 | docs/project/risk-register.md |
| 문서 지도와 읽기 순서 | docs/README.md |

## 6. 산출물 구조

기존 핸드오프는 유지하고 다음 8개 파일을 추가한다.

~~~text
docs/
├─ README.md
├─ handoff/
│  └─ forgeops-full-handoff.md
├─ product/
│  └─ prd.md
├─ architecture/
│  └─ system-architecture.md
├─ security/
│  └─ threat-model.md
├─ quality/
│  └─ verification-and-evaluation-plan.md
└─ project/
   ├─ wbs.md
   ├─ requirements-traceability-matrix.md
   └─ risk-register.md
~~~

각 신규 문서에는 목적, 범위, 기준 출처, 현재 상태, 최종 검토일,
관련 문서 링크를 둔다. 문서 상태는 초안, 검토됨, 기준선 중 하나로
표시한다. 최초 생성 시 상태는 초안이다.

## 7. 식별자와 상태

### 7.1 식별자

| 형식 | 의미 | 소유 문서 |
| --- | --- | --- |
| PRD-FR-### | 기능 요구사항 | PRD |
| PRD-NFR-### | 비기능 요구사항 | PRD |
| ARC-### | 아키텍처 구성요소 또는 결정 | 시스템 아키텍처 |
| THR-### | 위협 시나리오 | 위협 모델 |
| CTL-### | 보안 통제 | 위협 모델 |
| VG-### | 검증 또는 품질 게이트 | 검증 및 평가 계획 |
| WBS-### | 실행 작업 패키지 또는 상위 마일스톤 | WBS |
| RSK-### | 프로젝트 위험 | 위험 등록부 |

식별자의 숫자는 3자리로 채우고 문서 안에서 유일해야 한다. 한 번 추적에
사용한 식별자는 의미를 바꾸거나 다른 항목에 재사용하지 않는다. 항목이
제거되면 식별자를 폐기 상태로 남겨 링크의 의미가 변하지 않게 한다.

### 7.2 요구사항 성숙도

| 상태 | 의미 |
| --- | --- |
| IMPLEMENTED | 저장소와 검증 증빙으로 확인 가능한 현재 구현 |
| SPECIFIED | 계약과 기대 동작은 정의됐지만 제품 runtime은 없음 |
| PLANNED | 향후 제품 비전 또는 로드맵 |

### 7.3 실행 상태

WBS는 요구사항 성숙도와 별도로 WBS_NOT_STARTED, WBS_IN_PROGRESS,
WBS_BLOCKED, WBS_DONE을 사용한다. 이 값은 프로젝트 관리 전용이며
제품 workflow state나 Protocol 2.0 canonical accepted state로 직렬화,
변환 또는 해석하지 않는다. 요구사항 우선순위는 필수, 권장, 후순위로
제한한다. 위험 상태는 OPEN, MITIGATING, MONITORING, CLOSED를 사용한다.

## 8. 추적성 설계

추적 방향은 다음과 같다.

~~~text
PRD 요구사항
  → 아키텍처 요소 또는 보안 통제
  → WBS 작업 패키지
  → 검증 게이트와 trusted verification profile
  → 실제 실행에서 생성된 fresh evidence와 관찰 metadata
~~~

requirements-traceability-matrix.md가 문서 간 관계를 관리하는 유일한
교차 추적 표다. 다른 문서에는 소유한 내용을 설명하고 관련 식별자만
참조한다.

RTM의 각 행은 다음 열을 갖는다.

- 요구사항 ID
- 단계와 우선순위
- 성숙도
- 관련 아키텍처 ID
- 관련 위협 ID
- 관련 통제 ID
- 관련 위험 ID
- 관련 WBS ID
- 검증 게이트 ID
- 요구 evidence floor
- 검증 결과
- 실제 evidence tier
- fresh evidence 참조
- 관찰 revision 또는 시각
- 추적 상태
- 누락 또는 후속 조치

모든 필수 요구사항은 최소 하나의 검증 게이트를 가져야 한다. Phase 0과
Phase 1의 필수 요구사항은 WBS 작업과 계획된 VG까지 연결한다.
IMPLEMENTED는 코드나 문서 artifact가 현재 존재한다는 성숙도이며, 최소
fresh E1 file 또는 diff evidence가 있어야 한다. 기능 검증 결과는 이
성숙도와 별도로 PASSED, FAILED, NOT_RUN을 사용할 수 있다. FAILED나
NOT_RUN인 IMPLEMENTED 항목을 검증 완료로 표현하거나 Phase Exit에
사용할 수 없다. SPECIFIED와 PLANNED 항목은 NOT_RUN 및 fresh evidence
없음이 정상 상태다. Phase 2~4의 요구사항은 해당 상위 WBS 마일스톤과
검증 게이트까지 연결하고 세부 작업은 후속 계획에서 확장한다.

검증 방법은 VG 항목이 소유하며 verification_profile_id와 신뢰된
project profile의 exact command_id를 참조한다. raw shell command는
RTM에 기록하거나 실행 권한의 근거로 사용하지 않는다. RTM의 검증 결과는
PASSED, FAILED, NOT_RUN 중 하나로 기록한다. fresh evidence 참조는 실제
관찰이 생성된 뒤에만 저장소 상대 경로나 실행 결과 식별자를 기록한다.
Protocol 2.0 evidence type은 file, diff, command, test, render, runtime,
approval의 closed enum이다. contract와 metadata 관찰은 현재 Protocol에서
file evidence와 source 경로로 표현하며, 별도 type을 암묵적으로 만들지
않는다. file과 diff는 observed_revision만 가지며 그 값이 base_revision과
같아야 하고 observed_at은 금지한다. command, test, render, runtime,
approval의 observed_at은 실행 환경이 공급한 strict UTC 값이어야 하며
packet 입력에서 자체 생성할 수 없다. 이 시간 기반 evidence는
observed_revision을 금지하며 validator가 보유한 trusted validationAt을
기준으로 0~300초 범위인지 검증해야 한다. NOT_RUN이면 evidence 참조와
tier 및 관찰 metadata는 없음으로 표시하고 실행하지 못한 이유를 후속
조치 열에 기록한다. 계획된 명령이나 미래 artifact 경로를 현재 증빙처럼
기록하지 않는다.

추적 상태는 COVERED, PARTIAL, GAP의 closed enum을 사용한다. 관련 위협이나
위험이 없으면 해당 열에 없음을 명시하되, 누락된 분석을 없음으로
표시해서는 안 된다.

## 9. 문서별 내용 설계

### 9.1 docs/README.md

- 문서 체계의 목적과 대상 독자
- 권장 읽기 순서
- 문서별 책임, 상태, 최종 검토일, 링크
- 출처 우선순위와 변경 규칙
- 성숙도와 실행 상태의 차이

README는 상세 요구사항이나 일정을 복제하지 않는 탐색용 문서다.

### 9.2 docs/product/prd.md

- 제품 개요와 문제 정의
- 목표 사용자와 핵심 사용 시나리오
- 제품 목표와 비목표
- Harness Foundation 현재 기준선
- Phase 0~4 기능 요구사항
- 보안, 신뢰성, 이식성, 성능, 관찰 가능성 비기능 요구사항
- 성공 지표와 단계별 Exit gate
- 제약사항, 가정, 범위 제외
- 수용 기준과 관련 문서

각 요구사항에는 식별자, 단계, 우선순위, 성숙도, 명확한 요구 문장,
근거, 관찰 가능한 수용 기준, 검증 게이트 참조를 둔다. PRD는 구현
작업이나 상세 일정을 정의하지 않는다. Phase 0~4 모두 기능 및 비기능
요구사항과 release-level 수용 결과를 정의한다.

### 9.3 docs/architecture/system-architecture.md

- 시스템 컨텍스트와 제품 경계
- 사용자, Main, Part, Work, runtime, gateway, artifact store의 책임
- Harness와 제품 계층의 경계
- 제품 workflow state와 canonical accepted state의 분리 및 명시적 매핑
- MainDecision만 state, revision, event sequence를 확정하는 상태 계약
- Part와 Work의 proposed transition은 제안일 뿐이라는 규칙
- 핵심 실행 흐름과 제품 CANCELLED 경계
- Task Contract와 TaskPacket bridge
- API, event wrapper, manifest, evidence 계약
- snapshot, sandbox, verification, cancellation의 데이터 흐름
- 외부 통합과 replay의 경계
- 단계별 배치 구조와 미결정 기술 선택

각 ARC 항목은 관련 PRD ID와 성숙도를 표시한다. 기술 선택이 확정되지
않은 경우 선택지를 사실처럼 기록하지 않고 관련 위험과 결정 목표 주차를
연결한다.

제품 CANCELLED는 현행 Protocol 2.0 canonical state로 강제 변환하지
않는다. versioned protocol 변경으로 canonical 상태가 확장되기 전에는
제품 취소 상태의 통합을 차단하고 제품 계층 결과로만 보존한다.

### 9.4 docs/security/threat-model.md

- 보호 자산과 보안 목표
- 신뢰 경계와 공격자 모델
- 저장소 입력, 명령 실행, network, secret, artifact, 외부 효과 위협
- 위협별 사전 조건, 공격 경로, 영향
- exact authority, approval, sandbox, egress, redaction 통제
- 검증 방법과 잔여 위험
- Phase별 보안 gate

각 위협은 하나 이상의 통제와 검증 게이트에 연결한다. 인간 승인은 권한을
새로 만들지 않으며 UNKNOWN은 fail-closed한다는 Protocol 2.0 불변식을
명시한다.

위협 모델은 다음 보안 불변식을 이름만 언급하지 않고 개별 CTL 항목과
검증 가능한 수용 조건으로 정의한다.

각 CTL에는 severity를 CRITICAL, HIGH, MEDIUM, LOW의 closed enum으로
기록하고 phase_blocking boolean을 둔다. 무권한 mutation 또는 외부 효과,
sandbox escape, secret 노출, tenant 경계 위반, 승인 재사용, evidence
무결성 훼손을 막는 통제는 CRITICAL이며 phase_blocking은 반드시 true다.
심각도를 낮출 때는 변경된 위협 전제와 대체 통제, 검증 근거, RTM과 위험
등록부 갱신을 같은 변경에 포함해야 한다.

#### Exact authority와 결합 효과

- RESOURCE의 read_scope와 write_scope는 NONE, PROJECT, NAMED_RESOURCES,
  UNKNOWN의 closed enum이다. PROJECT는 companion resource list가 비어
  있고 canonical resource_ref가 project root 안에 있으며 root containment가
  확인될 때만 허용한다. NAMED_RESOURCES는 non-empty 목록의 case-sensitive
  exact membership만 허용한다. NONE과 UNKNOWN은 빈 companion list를
  요구하며 UNKNOWN은 fail-closed한다.
- resource_ref는 project-root-relative canonical literal이어야 한다.
  absolute path, parent traversal, empty 또는 duplicate 값, wildcard,
  glob, regex, prefix나 suffix 추론을 거부한다. protected resource와
  사용자 소유 변경을 preflight에서 별도로 확인한다.
- RESOURCE read는 filesystem_read capability AVAILABLE, exact read
  authority, current base revision과 preflight를 요구한다. Part의 승인
  후보 생성 전 EXPLORE read에는 candidate 승인을 요구하지 않지만,
  Work가 수행하는 READ_RESOURCE action은 approved candidate도 요구한다.
  protected resource나 secret 가능성이 있는 resource는 적용되는 추가
  승인 규칙을 통과해야 하며 어느 전제 값이든 UNKNOWN이면 fail-closed한다.
- mutation은 operation_mode EXECUTE, filesystem write capability AVAILABLE,
  approved candidate, exact write authority, current base revision과
  preflight를 모두 충족할 때만 허용한다.
- COMMAND는 execute_scope가 NAMED_COMMANDS이고 승인된 exact command_id가
  존재하며, 신뢰된 validation command record의 id, command,
  project-root-relative cwd가 모두 case-sensitive exact 일치할 때만
  허용한다. project-wide execute authority는 존재하지 않는다.
  operation_mode EXECUTE, command_execute capability AVAILABLE, approved
  candidate, current base revision, exact command authority와 preflight를
  모두 요구한다.
- NETWORK는 NAMED_HOSTS scope와 canonical lower-case host 또는 host:port의
  exact 일치를 요구한다. scheme, path, userinfo, whitespace, wildcard,
  case folding, trimming, prefix 또는 suffix 일치, redirect 권한 상속,
  default-port 확장을 포함한 암묵적 normalization으로 권한을 만들 수 없다.
  operation_mode EXECUTE, network capability AVAILABLE, approved candidate,
  current base revision, exact network authority와 preflight를 모두 요구한다.
- 외부 효과가 있으면 external_side_effects capability AVAILABLE과
  external_side_effects authority ALLOWED도 요구한다. 어느 capability,
  authority 또는 전제 값이든 UNKNOWN이면 fail-closed한다.
- DELETE_RESOURCE나 파괴적 COMMAND 또는 NETWORK를 포함해 action의 효과가
  파괴적이면 destructive_actions authority ALLOWED도 요구한다. DENIED나
  UNKNOWN이면 인간 승인 여부와 무관하게 fail-closed하며, 이 거부 경로를
  phase-blocking CRITICAL negative VG로 검증한다.
- tier, 도구 이름, MCP manifest나 description, 저장소 내용, 모델 출력,
  인간 승인은 capability나 authority를 만들거나 확장할 수 없다.
- COMMAND와 NETWORK처럼 결합된 효과는 별도 candidate와 exact action
  identity로 분리하고 명시적인 dependency를 둔다.

#### 승인 binding과 replay

- 승인 capability 하나는 candidate 하나, action identity 하나와 target
  하나에 결합하며, 해당 효과에 적용되는 모든 입력과 예상 결과를
  binding한다. diff_hash와 request_payload_hash처럼 적용 가능한 hash를
  모두 포함하거나 target, method와 path, diff, payload를 함께 포함한
  versioned canonical effect_hash를 사용한다.
- base revision, commit, Contract, plan, policy, diff, target, payload 중
  하나라도 바뀌면 기존 승인을 무효화한다.
- issuer, audience, approver subject, tenant, expiry, key와 signature를
  검증하고 외부 효과 직전에 nonce를 원자적으로 한 번만 소비한다.
- 승인 capability와 현재 TaskPacket authority의 교집합만 실행할 수 있다.
- timeout 또는 결과 미상인 비멱등 효과는 자동 재시도하지 않고 원격
  상태를 reconcile하기 전까지 반복 실행을 차단한다.
- replay는 AUDIT_REPLAY, REEXECUTE, COUNTERFACTUAL의 closed product mode를
  사용한다. 기본 AUDIT_REPLAY는 Harness EXPLORE에 매핑하고 새 run,
  correlation, event sequence를 만들며 network DENIED, external effects
  DENIED로 시작한다. 기존 approval, nonce, credential, authority,
  publisher token을 복사하지 않는다.
- 모든 replay는 source_task_id, source_run_id, source_manifest_id를
  보존하되 새 run의 revision, event sequence와 evidence를 원본과 섞지
  않는다. AUDIT_REPLAY와 같은 Contract의 REEXECUTE는 원래 task identity를
  유지한다.
- COUNTERFACTUAL이 Product Task Contract를 바꾸면 새 task ID를 만들고
  source_task_id와 source_run_id로 원본을 보존한다.
- AUDIT_REPLAY와 COUNTERFACTUAL은 승인 여부와 무관하게 외부 효과를
  hard deny한다. REEXECUTE만 기본 deny 상태에서 현재 상태 관찰, exact
  action별 새 candidate, 새 approval과 nonce 및 fresh evidence를 거쳐
  외부 효과를 허용할 수 있다. PR, issue, message, push, deploy,
  package install을 자동 replay하지 않는다.

#### Sandbox와 egress

- 실행 image는 immutable digest로 고정하고 signature와 provenance를
  검증한다. process는 rootless 또는 non-root와 user namespace에서
  실행하며 root filesystem은 read-only로 유지한다.
- quota가 있는 task workspace와 임시 영역만 쓰기를 허용한다.
  privileged mode, host PID와 IPC 및 network namespace, host device,
  Docker socket, live host mount를 차단한다.
- capability drop ALL, no-new-privileges, seccomp와 AppArmor 또는 SELinux를
  강제하고 CPU, memory, PID, disk, file descriptor, log, runtime quota를
  둔다. 종료와 취소 후 process tree, mount, lease, transient secret,
  workspace teardown을 검증한다.
- sandbox의 직접 socket과 DNS를 차단하고 task별 egress proxy만 허용한다.
  proxy는 loopback, private, link-local, CGNAT, ULA, multicast, reserved,
  cloud metadata 주소를 차단한다.
- DNS 결과와 실제 연결 주소를 결합해 rebinding과 TOCTOU를 막고 Host,
  SNI, 인증서, exact host와 port의 일치를 확인한다. redirect는 기본
  차단하며 새 목적지에 기존 권한을 상속하지 않는다.
- 외부 또는 악성 가능성이 있는 저장소에는 Docker만으로 충분하다고
  주장하지 않고 위험 등급에 따라 gVisor, Kata, microVM 또는 전용
  worker를 요구한다.

#### Secret과 artifact

- secret, credential, private payload, 대형 raw log를 packet, event,
  prompt, telemetry export, 사용자 응답에 넣지 않는다.
- stdout과 stderr는 저장 또는 exporter 전 quota와 redaction을 적용한다.
  raw secret의 일반 hash를 대체값으로 저장하지 않는다.
- redaction할 수 없는 원문은 기본 폐기한다. 정책상 보존이 필요하면
  tenant별로 암호화된 quarantine, 별도 접근 승인, RBAC 또는 ABAC,
  audit와 짧은 retention을 적용한다.
- artifact는 tenant 격리, 전송 및 저장 암호화, retention과 backup을
  포함한 삭제 정책, 접근 감사, checksum과 tamper-evident manifest를
  가져야 한다.
- repository content와 log는 저장 뒤에도 비신뢰 데이터이며 모델에
  재주입할 때 동일한 injection과 secret 정책을 다시 적용한다.

### 9.5 docs/quality/verification-and-evaluation-plan.md

- 검증 목적과 범위
- 정적 문서 검사, contract fixture, component, integration, end-to-end 계층
- baseline과 변경 후 검증
- 증빙 등급과 fresh evidence 요구
- 단계별 품질 게이트와 통과 조건
- 회귀, 복구, 안전, 비용, 지연 평가 지표
- 실패, inconclusive, baseline unhealthy 처리
- 평가 반복성과 포트폴리오 증빙 보존

각 VG 항목에는 대상 요구사항, verification_profile_id, trusted
command_id 또는 비실행 관찰 방법, 요구 evidence floor, 통과 조건,
실패 시 상태를 둔다. 실제 증빙에는 evidence_ref, tier와 관찰 revision
또는 실행 시각을 별도로 둔다. 결정론적 검증 실패나 안전 위반은 정성
평가 점수로 뒤집을 수 없다.

모든 THR은 하나 이상의 CTL과 negative VG를 가져야 한다. 모든 CTL은
PRD-NFR, WBS, VG와 연결하며, 모든 VG는 expected fail-closed 결과와
evidence floor를 갖는다. orphan THR, CTL, VG가 있으면 문서 기준선
확정을 차단한다. 문서 작성 시 SPECIFIED와 PLANNED 통제의 NOT_RUN은
정상이나, 구현 단계에서 CRITICAL CTL의 추적 상태 PARTIAL 또는 GAP,
검증 결과 NOT_RUN은 해당 Phase Exit를 차단하고 요구 floor의 fresh
evidence PASSED를 요구한다. 무권한 action,
gateway 우회 외부 write, raw secret 기록, nonce 재사용, tenant 간
artifact 접근은 관찰 0건이어야 한다.

secret redaction fixture는 packet, event, artifact, trace, telemetry
exporter 각각의 누출 여부를 검사한다. sandbox와 egress negative fixture는
금지된 namespace, mount, socket, DNS, 주소 범위, redirect, quota 초과,
종료 후 잔존 resource와 관찰된 외부 효과를 검사한다.

포트폴리오 증빙 패키지는 public-safe demo fixture, 재현 절차, redacted
trace와 diff, 지표와 manifest hash를 포함한다. credential, private
repository 내용, tenant 식별자, raw log, 라이선스가 불명확한 코드는
포함하지 않는다. secret과 redaction 검사를 통과해야 하며 외부 게시는
항상 별도 승인을 요구한다.

### 9.6 docs/project/wbs.md

- 계획 목적과 10주 범위
- 일정 가정과 1인 개발 제약
- Phase 0~1 상세 작업 패키지
- Phase 2~4 상위 마일스톤
- 주차별 의존성과 critical path
- 예상 person-day, 주간 가용 용량, buffer, 재계획 trigger
- 주간 운영 및 변경 통제
- 완료 정의와 포트폴리오 checkpoint

각 WBS 항목에는 단계, 주차, 실행 상태, 선행 작업, 관련 PRD ID, 산출물,
예상 person-day, 완료 정의, 검증 게이트, 예상 증빙 유형을 둔다. 실제
fresh evidence 참조는 RTM만 소유한다. WBS는 제품 요구사항을 재정의하지
않는다.

기본 용량은 주당 5 person-day이며 계획 작업은 최대 4 person-day로
제한하고 1 person-day를 검토, 실패, 문서화 buffer로 보존한다. 한 주의
계획이 4 person-day를 넘거나, Phase gate가 목표 주차에 미달하거나,
보안 불변식 실패 또는 2주 연속 carry-over가 발생하면 이후 작업을
자동으로 당기지 않고 WBS를 재계획한다.

### 9.7 docs/project/requirements-traceability-matrix.md

- 추적 규칙과 상태 정의
- 모든 PRD 요구사항의 교차 추적 표
- 필수 요구사항 coverage 요약
- orphan 요구사항과 orphan 작업 목록
- Phase별 추적 공백과 해소 목표

RTM은 설명의 소유자가 아니라 연결의 소유자다. 요구사항과 통제의 본문은
각 기준 문서로 링크한다.

### 9.8 docs/project/risk-register.md

- 점수와 상태 산정 규칙
- 일정, 기술, 보안, 제품, 평가, 포트폴리오 위험
- 확률과 영향
- 조기 경보 또는 trigger
- 예방, 완화, contingency
- 관련 요구사항과 작업
- 결정 또는 대응 목표 주차

확률과 영향은 각각 1~5로 기록하고 점수는 두 값의 곱으로 계산한다.
1인 개발자라는 조건 때문에 병렬 작업 가정을 두지 않으며, 중대한 보안
불변식 위반은 단순 일정 위험으로 수용하지 않는다.

## 10. 상대 일정 10주 배치

| 주차 | 단계 | 주요 결과와 Exit 조건 |
| --- | --- | --- |
| W1 | Phase 0 | 현행 Harness 기준선, Product Task Contract와 TaskPacket bridge 매핑 |
| W2 | Phase 0 | 상태 전이 validator, 승인·권한 정책 matrix와 fail-closed fixture |
| W3 | Phase 0 | versioned OpenAPI, durable event wrapper, run manifest schema |
| W4 | Phase 0 | sample fixture, sandbox PoC, secret redaction, Phase 0 Exit gate |
| W5 | Phase 1 | repository snapshot, baseline, code retrieval |
| W6 | Phase 1 | Main 정규화·라우팅 → Part 분석 → Work 실행·검증 → Main 수용 |
| W7 | Phase 1 | patch와 diff, test, lint, typecheck 검증 파이프라인 |
| W8 | Phase 1 | budget, cancellation, 기본 trace viewer |
| W9 | Phase 1 | 필수 기준 E2 이상 증빙, 격리, 무권한 실행 0건, cleanup 실패 0건 |
| W10 | Phase 1 Exit | local vertical slice 최종 통합, 회귀 검증, public-safe 포트폴리오 증빙 패키지 |

Phase 0은 Harness conformance, 잘못된 전이와 권한, 승인 거부와 만료 및
nonce 재사용, sandbox containment smoke test, secret redaction fixture가
핸드오프의 Exit gate를 충족할 때 종료한다. Phase 1 vertical slice는
로컬 실행으로 제한하며 외부 write를 허용하지 않는다.

Phase 2는 bounded repair와 benchmark 및 hidden evaluation, Phase 3은
GitHub draft PR과 RBAC 및 audit와 webhook deduplication, Phase 4는
멀티테넌트 운영과 강화된 격리 및 플러그인 생태계를 상위 마일스톤으로만
기록한다.

## 11. 오류와 불확실성 처리

- 저장소와 문서가 충돌하면 fresh observation을 기록하고 파생 문서를
  수정한다.
- 근거가 없는 구현 주장은 PLANNED로 낮추거나 문서에서 제거한다.
- 미결정 사항은 임시 미완료 표식으로 두지 않고 RSK 항목, 책임 주체,
  결정 목표 주차, 선택 기준을 기록한다.
- 링크 대상이나 식별자가 없으면 추적 완료로 표시하지 않는다.
- 검증 명령을 실행할 수 없으면 성공으로 간주하지 않고 이유와 필요한
  capability 또는 권한을 기록한다.
- Protocol 2.0과 제품 계약 사이의 차이는 자동으로 합치지 않고 경계와
  bridge 책임을 명시한다.

## 12. 문서 검증 전략

### 12.1 자동 검사

1. 8개 산출물의 존재와 UTF-8 읽기를 확인한다.
2. Markdown 상대 링크가 저장소 안의 실제 파일을 가리키는지 확인한다.
3. 식별자 형식, 중복, 잘못된 참조를 검사한다.
4. 필수 PRD 요구사항의 RTM coverage와 orphan WBS, THR, CTL, VG를
   검사한다.
5. 각 WBS 항목에 선행 조건, 산출물, 완료 정의, 검증, 증빙이 있는지
   확인한다.
6. 일반적인 임시 미완료 표식과 비어 있는 필수 절을 검사한다.
7. Markdown fence 균형과 git diff --check를 확인한다.

### 12.2 의미 검토

1. PRD가 Phase 0~4 전체 제품 범위를 보존하는지 검토한다.
2. WBS가 Phase 0~1을 상세화하고 Phase 2~4를 과도하게 확정하지 않는지
   검토한다.
3. 구현 상태 주장이 저장소 증빙과 일치하는지 검토한다.
4. 요구사항, 설계, 통제, 작업, 검증의 관계가 서로 모순되지 않는지
   검토한다.
5. Protocol 2.0의 승인, 권한, fail-closed, fresh evidence 불변식이
   유지되는지 검토한다.
6. 제품 상태, WBS 상태, canonical accepted state가 서로 혼합되지
   않는지 검토한다.
7. 제3자가 목표에서 포트폴리오 증빙까지 추적할 수 있는지 검토한다.

## 13. 완료 기준

다음 조건이 모두 충족되어야 기초 문서 작업을 완료로 판정한다.

1. 역할별 경로에 8개 신규 한국어 문서가 존재한다.
2. PRD는 Phase 0~4의 목표, 요구사항, 비기능 조건, Exit gate를 포함한다.
3. WBS는 상대 일정 10주와 Phase 0~1의 실행 가능한 상세를 포함한다.
4. WBS에서만 Phase 2~4를 상위 마일스톤으로 유지하며 PRD는 전체 단계의
   기능 및 비기능 요구사항과 release-level 수용 결과를 보존한다.
5. 모든 필수 요구사항이 검증 게이트를 가지며 RTM에 나타난다.
6. Phase 0~1의 필수 요구사항은 WBS 작업과 계획된 VG까지 연결된다.
   IMPLEMENTED 상태는 최소 fresh E1 존재 증빙을 요구하고, Phase Exit는
   해당 필수 검증이 요구 floor의 fresh PASSED일 때만 허용한다.
7. 구현, 계약, 계획 상태가 구분되고 근거 없는 현재 구현 주장이 없다.
8. 링크, 식별자, 추적성, Markdown, UTF-8, diff 검사가 통과한다.
9. 사용자 변경을 보존하고 이번 작업 범위 밖의 파일을 수정하지 않는다.
10. 제품 workflow state와 canonical accepted state가 분리되고,
    MainDecision만 state, revision, event sequence를 확정한다.
11. 제품 CANCELLED는 versioned protocol 변경 전까지 canonical 상태로
    강제 변환되거나 통합되지 않는다.
12. 모든 THR이 CTL과 negative VG에 연결되고 모든 CTL이 PRD-NFR, WBS,
    VG에 연결되며 orphan 보안 항목이 없다.
13. exact authority, 승인 binding과 replay, sandbox와 egress,
    secret과 artifact 불변식이 개별 CTL과 검증 가능한 VG로 정의된다.
14. 모든 CTL이 closed severity와 phase_blocking 값을 가지며 CRITICAL
    통제의 미검증 또는 실패 상태가 해당 Phase Exit를 차단한다.

## 14. 실행 경계

이 설계 명세가 사용자 검토를 통과하면 writing-plans 단계에서 8개 문서의
작성 순서, 검증 명령, 검토 checkpoint를 구체화한다. 이번 사용자의 Git
승인은 이 설계 명세 파일의 커밋에 한정한다. 이후 8개 기초 문서의 커밋,
푸시 또는 외부 게시 권한으로 확대 해석하지 않는다.
