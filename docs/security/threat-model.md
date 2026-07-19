# ForgeOps 위협 모델

**문서 상태:** 초안
**최종 검토일:** 2026-07-14
**대상 독자:** 1인 개발자, 포트폴리오 검토자
**기준 출처:** [ForgeOps 제품 요구사항 문서](../product/prd.md), [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md), [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md), [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md)
**현재 상태:** Portable Harness Foundation의 exact authority와 evidence 계약만 `IMPLEMENTED`이고, 이 문서의 제품 보안 통제는 `SPECIFIED`, 집행 runtime은 `PLANNED`다. 모든 제품 negative gate의 현재 결과는 fresh runtime evidence가 생길 때까지 `NOT_RUN`이다.

## 1. 목적과 방법

이 문서는 ForgeOps의 보호 자산, 공격자, 신뢰 경계, 위협, 통제, negative
verification gate와 잔여 위험을 정의하는 보안 기준 문서다. PRD의 보안
요구사항과 시스템 아키텍처의 경계를 위협 시나리오로 구체화하되,
Protocol 2.0의 canonical packet, exact authority, 승인, 상태 소유권 또는
fresh evidence 의미를 재정의하거나 약화하지 않는다.

분석은 다음 순서로 수행한다.

1. source snapshot부터 외부 효과 identity까지 보호 자산을 식별한다.
2. data plane과 control plane, Main·Part·Work, Gateway·sandbox·Publisher,
   trace·artifact 및 tenant 경계를 구분한다.
3. 공격자의 사전 조건, 공격 경로, 영향과 최초 차단 대상 Phase를
   `THR-001`~`THR-012`로 기록한다.
4. 각 위협을 phase-blocking 통제 `CTL-001`~`CTL-020`과 expected
   fail-closed negative VG에 연결한다.
5. 통제가 남기는 위험과 Phase Exit 차단 조건을 기록한다.

위험도는 통제 severity와 Phase gate로 표현한다. `CRITICAL`, `HIGH`,
`MEDIUM`, `LOW`만 유효하며, 이 문서의 모든 통제는 `phase_blocking=true`다.
위험도는 authority를 부여하지 않는다. capability, authority, approval,
current revision, preflight 또는 evidence가 누락되거나 `UNKNOWN`이면 읽기
범위를 넘어서는 mutation, command, network, destructive action과 external
effect를 fail-closed한다.

## 2. 보호 자산

| 보호 자산 | 보안 목표 | 손상 시 영향 |
| --- | --- | --- |
| Source snapshot과 content manifest | 동일 run의 retrieval, baseline, workspace가 고정된 source identity와 hash를 사용하고 원본은 변경되지 않아야 한다. | baseline 오염, 재현 불가, 원본 손상, 거짓 diff |
| 사용자 소유 변경 | dirty state와 범위 밖 변경을 보존하고 승인된 exact resource 외에는 덮어쓰지 않아야 한다. | 작업 유실, unrelated change, 잘못된 publish |
| Secret, credential, private payload | 최소 scope·짧은 수명으로 필요한 경계에만 주입하고 packet, event, prompt, artifact, trace, telemetry와 응답에 raw 값이 남지 않아야 한다. | 계정 탈취, tenant 침해, 외부 유출 |
| Approval capability | 한 candidate·action identity·target·effect 입력에 서명·만료·nonce로 결합되고 한 번만 사용되어야 한다. | 권한 확대, 승인 replay, 무권한 외부 효과 |
| Trusted validation profile | 운영자 또는 신뢰된 profile loader가 등록한 command `id`, `command`, canonical `cwd`와 baseline을 변조 없이 보존해야 한다. | 임의 명령 실행, test 우회, 거짓 성공 |
| Canonical evidence | closed type, exact reference, 요구 tier와 revision/time freshness를 보존해야 한다. | forged success, stale 결과 수용, audit 단절 |
| Artifact와 quarantine | 무결성, provenance, 암호화, tenant 격리, retention과 삭제가 보장되어야 한다. | cross-tenant 노출, 변조, 삭제 실패 |
| Durable event와 run manifest | task·run·correlation·revision·sequence·actor·reference 관계와 tamper evidence를 보존해야 한다. | 실행 재구성 불가, 책임 부인, event 혼합 |
| Tenant data와 경계 | identity, RBAC/ABAC, key, storage, query와 export가 tenant별로 분리되어야 한다. | 다른 tenant의 source, artifact, credential 접근 |
| External effect identity와 remote state | target, method/path, diff, payload, idempotency와 관찰된 remote state가 exact하게 결합되어야 한다. | 중복 PR·message·deploy, 잘못된 target 변경, 결과 미상 재실행 |

Git commit SHA, `snapshot_id`, task revision, Harness event `seq`, product
`stream_seq`, approval nonce와 idempotency key는 서로 다른 identity다. 이름이
비슷하다는 이유로 대체하거나 정규화하지 않으며, hash는 무결성 근거일 뿐
secret 보호나 authority의 근거가 아니다.

## 3. 공격자와 신뢰 가정

### 공격자 모델

| 공격자 또는 실패 주체 | 가능한 능력 | 신뢰하지 않는 주장 |
| --- | --- | --- |
| 악성 repository·Issue·fixture 작성자 | 코드, 문서, symlink, package script, test와 log에 지시·payload를 삽입한다. | policy 변경, secret 요청, command·network·publish 권한 주장 |
| 손상되거나 악성인 MCP·integration·remote endpoint | tool description/output, redirect, DNS, webhook와 응답 크기·순서를 조작한다. | allowlist 등록, credential scope, 성공 결과, 재시도 안전성 주장 |
| 오류가 있거나 공격에 영향받은 model·agent·tool | schema 밖 field, raw command, 과도한 scope, forged evidence와 완료 서술을 만든다. | capability, authority, approval, accepted state와 검증 성공 주장 |
| 악의적이거나 오인한 tenant 사용자 | 다른 tenant ID, artifact reference, approval target 또는 replay 입력을 제출한다. | tenant membership, 대상 ownership, 과거 승인 재사용 주장 |
| 손상된 worker·storage·clock·운영 경로 | image, artifact, event, manifest, freshness 시각 또는 cleanup 결과를 위조·누락한다. | provenance, teardown, ordering, timestamp와 rollback 성공 주장 |
| 자원 고갈을 유도하는 workload | fork, giant log, disk fill, 느린 network, 반복 failure와 repair를 유도한다. | 진행 발생, budget 예외, 무제한 retry 필요 주장 |

### 신뢰 가정과 fail-closed 기준

- direct user request와 적용되는 instruction hierarchy만 control authority의
  출처다. repository, Issue, documentation, test, log, MCP description/output,
  external response와 model output은 모두 비신뢰 data다.
- Main만 canonical accepted state, revision과 Harness event sequence를
  확정한다. Part와 Work, 제품 runtime과 저장된 event는 proposal 또는
  observation만 제공한다.
- human approval은 capability나 authority를 만들지 않는다. 검증된 approval
  capability와 현재 TaskPacket authority의 교집합만 실행할 수 있다.
- runtime이 실제로 관찰해 `AVAILABLE`로 확정하지 않은 capability는
  `UNKNOWN`이며 허용으로 승격하지 않는다. `UNKNOWN`은 write, command,
  network, credential, destructive action, publication, cost와 external
  effect를 거부한다.
- trusted validation profile, approval key, image signing root, tenant identity,
  egress policy와 validator clock도 검증 가능한 trust anchor이지 무조건
  신뢰되는 문자열이 아니다. compromise 가능성은 잔여 위험으로 남긴다.
- 현재 저장소에는 제품 API, durable queue, sandbox provisioner, Tool Gateway,
  Publisher, artifact store와 tenant runtime이 없다. 아래 통제는 목표 계약이며
  구현 또는 Phase Exit 통과를 주장하지 않는다.

## 4. 신뢰 경계

| 경계 | 비신뢰 입력 | 허용되는 신뢰 근거 | 필수 집행 |
| --- | --- | --- | --- |
| Product Contract → Main | Contract 안의 권한·policy·command·source 주장 | 원문 요청, 적용 instruction/profile, runtime capability observation | 의미를 lossless하게 보존하되 Contract로 authority를 추가하지 않는다. 관찰 불가는 `UNKNOWN`이다. |
| Main → Part | repository, Issue, log, fixture와 retrieval 결과 | canonical TaskPacket의 exact read authority와 current revision | Part는 approved candidate 전에도 `EXPLORE`에서 비보호 대상의 exact-scope read-only discovery와 proposal만 수행할 수 있다. protected resource·credential·private data는 exact target 인간 승인 전 첫 byte도 읽지 않으며 accepted state나 event sequence를 변경하지 않는다. |
| Main → Work | 과거 승인, Part의 문자열 주장, stale candidate | approved candidate, closed action identity, current revision, runtime capability와 exact authority | Work는 preflight를 다시 수행하고 승인된 exact action만 실행한다. 성공 서술은 Main 수용 전 제안이다. |
| Tool Gateway → resource/command | tool name, manifest, raw command, path 변형 | canonical RESOURCE/COMMAND identity와 trusted profile | path·command를 정규화해 일치를 만들지 않고, 결합 효과를 별도 candidate와 dependency로 분리한다. |
| Gateway → sandbox/network | URL, redirect, DNS answer, package script와 tool output | exact NETWORK identity, task egress policy, sandbox profile | 직접 socket/DNS를 차단하고 proxy 목적지 검사, containment, quota, redaction을 적용한다. |
| Orchestration → Publisher | agent publish 요청, replay token, 결과 미상 효과 | 현재 authority와 교집합인 새 approval capability, effect hash, atomic nonce, current remote state | Publisher만 외부 write를 수행하며 effect 직전에 binding과 nonce를 검증한다. 이 경계는 `SPECIFIED`이며 runtime은 `PLANNED`다. |
| Trace/artifact store → model/user/export | raw log, secret, private repository data, 저장된 instruction | schema-valid exact reference, tenant-scoped redacted view | 저장 전·export 전 quota와 redaction, encryption, retention, audit와 재주입 시 data/control 분리를 적용한다. |
| Tenant/API/event boundary | caller가 제공한 tenant, task, revision, idempotency와 event identity | 인증된 tenant membership, closed schema, expected revision과 durable ordering | cross-tenant reference, duplicate effect, stale update와 sequence 혼합을 거부한다. |

Action admission은 다음 비약 없는 교집합을 사용한다.

- RESOURCE의 `PROJECT` authority는 빈 companion list, canonical
  project-root-relative `resource_ref`와 확인된 root containment를 요구한다.
  `NAMED_RESOURCES`는 non-empty 목록의 case-sensitive exact membership만
  허용한다. `NONE`과 `UNKNOWN`은 빈 목록과 deny를 요구한다.
- COMMAND는 `NAMED_COMMANDS`만 허용하며 trusted validation record의
  `id`, `command`, project-root-relative `cwd`가 모두 case-sensitive exact
  일치해야 한다. project-wide command authority와 raw command 주입은 없다.
- NETWORK는 `NAMED_HOSTS`의 canonical lower-case ASCII `host[:port]` exact
  identity만 허용한다. scheme, path, userinfo, whitespace, wildcard, case
  folding, trimming, default-port 확장과 redirect 권한 상속은 거부한다.
- `T0`는 Work action의 자동 승인이 아니다. Part만 approved candidate 전
  `EXPLORE`에서 비보호 대상의 허용된 exact read scope를 discovery할 수 있다.
  protected resource, credential 또는 private data read는 tier와 무관하게
  exact target 인간 승인 전 첫 byte를 model context·log·evidence로 보내지
  않는다.
- Work의 mutation, command와 network는 `EXECUTE`, 대응 capability
  `AVAILABLE`, approved candidate, current base revision, exact authority와
  preflight를 모두 요구한다. 외부 효과에는 별도의
  `external_side_effects=AVAILABLE/ALLOWED`, 파괴적 효과에는 별도의
  `destructive_actions=ALLOWED`가 필요하다.
- 인간 승인, risk tier, evidence tier, tool 이름 또는 저장된 event는 위
  전제 중 어느 것도 대신하거나 넓히지 못한다.

## 5. 위협 카탈로그

| ID | Threat | Asset | Actor | Precondition | Attack path | Impact | Target Phase | Related PRD-NFR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| THR-001 | repository, Issue, log, MCP output의 prompt injection이 control instruction으로 승격 | Contract, policy, approval, budget, tool schema, secret | 악성 source 작성자, 손상된 MCP, prompt에 영향받은 model | data/control plane 분리나 schema·policy validation이 약함 | 비신뢰 본문이 scope 확대, secret 전송, test 우회 또는 publish 지시로 해석된다. | 무권한 action, secret 노출, 검증 우회 | Phase 0 계약, Phase 1~4 집행 | PRD-NFR-002, PRD-NFR-004, PRD-NFR-012 |
| THR-002 | path traversal, protected resource 접근, 사용자 변경 덮어쓰기 | Source snapshot, 사용자 변경, protected resource, host path | 악성 repository, 오류가 있는 agent/tool | 비canonical path, root containment·ownership preflight 누락, symlink/race | absolute·parent path, wildcard·prefix match 또는 링크를 통해 범위 밖을 읽거나 쓰고 dirty state를 덮어쓴다. | 원본·사용자 변경 유실, credential 접근, unrelated change | Phase 0~4 | PRD-NFR-002, PRD-NFR-003 |
| THR-003 | raw command 주입, command profile 변조, authority normalization | Validation profile, command authority, sandbox | 악성 repository·package script, 손상된 agent/profile loader | raw shell 허용, command record 일부 일치, case folding·trim·cwd 추론 | 공격 입력을 command에 결합하거나 profile을 바꾸고 유사 ID·command·cwd를 authorized로 정규화한다. | 임의 코드 실행, host/secret 접근, 검증 조작 | Phase 0~4 | PRD-NFR-002, PRD-NFR-009 |
| THR-004 | SSRF, DNS rebinding, redirect, metadata/private network 접근 | Network authority, internal service, metadata credential, tenant network | 악성 repository, remote endpoint, 손상된 MCP | exact identity만 검사하고 목적지 안전 검사·proxy가 없거나 직접 DNS/socket 허용 | 허용 host를 private IP로 재결합하거나 redirect·parser ambiguity로 loopback, private, link-local, metadata에 연결한다. | credential 탈취, 내부망 pivot, data exfiltration | Phase 0 PoC, Phase 1~4 집행 | PRD-NFR-002, PRD-NFR-003, PRD-NFR-012 |
| THR-005 | sandbox escape, host namespace/device/socket/mount 노출 | Host, 원본 repository, worker, 다른 run·tenant | 악성 workload, 취약 image/runtime | privileged·root 실행, writable rootfs, host namespace/device/socket/mount 노출 | kernel/runtime 취약점이나 노출된 Docker socket·mount·device로 sandbox 밖 권한을 얻는다. | host 장악, cross-run/tenant 침해, 원본 변경 | Phase 0 PoC, Phase 1~4 집행 | PRD-NFR-003, PRD-NFR-012 |
| THR-006 | 무권한 외부 효과, destructive action, approval replay 또는 scope 확대 | Approval capability, external effect identity, remote repository/service | 악성 agent, 오인한 approver, token 탈취자 | approval이 authority를 만들거나 broad scope·재사용 token·별도 hard gate 누락 | 과거 또는 다른 target의 승인을 재사용하고 diff·payload·revision 변경 후 push, PR, message, deploy, delete를 실행한다. | 원격 손상, 비가역 변경, 공급망·운영 사고 | Phase 0 계약, Phase 3~4 집행 | PRD-NFR-002, PRD-NFR-005, PRD-NFR-012 |
| THR-007 | secret, credential, private payload, raw log 유출 | Secret, credential, private source·payload, telemetry | 악성 source/MCP, 오류가 있는 tool/exporter, tenant 사용자 | 과도한 credential 주입, 저장·export 전 redaction 부재, raw log 무제한 | stdout/stderr, packet, event, prompt, artifact, trace, telemetry 또는 응답에 raw 값이나 복원 가능한 표현을 남긴다. | 계정 탈취, privacy·tenant 침해, 장기 노출 | Phase 0~4 | PRD-NFR-004, PRD-NFR-012 |
| THR-008 | artifact 변조, tenant 간 접근, retention/deletion 실패 | Artifact, quarantine, manifest, tenant data와 key | 악의적 tenant, 손상된 storage/admin, 오류가 있는 lifecycle job | tenant-scoped authorization·encryption·checksum·retention·audit 미비 | 다른 tenant reference를 조회하거나 artifact/manifest를 바꾸고 backup·quarantine에 데이터를 무기한 남긴다. | source·secret 유출, 증빙 조작, 규정 위반 | Phase 1~4 | PRD-NFR-004, PRD-NFR-006, PRD-NFR-012 |
| THR-009 | replay, retry, webhook 중복으로 비멱등 효과 재실행 | External effect identity, remote state, task/run lineage | 중복 sender, worker failure, 공격적 caller | idempotency·dedup·reconciliation 누락, approval/nonce/credential 복사 | 같은 webhook·request·timeout을 새 실행으로 처리하거나 replay에서 원래 effect를 다시 수행한다. | 중복 PR·message·deploy·charge, 상태 불일치 | Phase 3~4 | PRD-NFR-005, PRD-NFR-006, PRD-NFR-012 |
| THR-010 | forged, stale, future, wrong-revision evidence와 event identity 혼합 | Evidence catalog, accepted state, event/manifest ordering | 손상된 producer·clock·store, 오류가 있는 agent | open evidence schema, untrusted timestamp, reference·revision·sequence validation 누락 | duplicate/dangling reference, stale·future evidence, `recorded_at` 대체 또는 stream/event/revision identity 혼합으로 성공을 꾸민다. | 거짓 `SUCCEEDED`, 감사·재현 단절, stale mutation 수용 | Phase 0~4 | PRD-NFR-001, PRD-NFR-006 |
| THR-011 | test 조작, baseline 오염, verification bypass, rubric override | Trusted profile, baseline, test, criterion result, evaluation | 악성 source, 목표 편향 agent, 손상된 evaluator | baseline/profile가 workspace에 노출되거나 deterministic gate 우선순위 미강제 | test 삭제·skip·xfail·assert 완화, config 변경, agent가 만든 test만 실행하거나 rubric/human score로 실패를 뒤집는다. | 회귀 은폐, 거짓 성공, 품질 지표 오염 | Phase 1~4 | PRD-NFR-001, PRD-NFR-010 |
| THR-012 | resource exhaustion, budget 우회, no-progress loop, cleanup 잔존 | Worker 자원, budget, sandbox lifecycle, 비용·가용성 | 악성 workload, 반복 agent, 느린 integration | quota·failure signature·stop condition·verified teardown 미비 | fork bomb, giant log, disk/network 고갈, 동일 repair 반복 또는 종료 후 process·mount·lease·secret을 남긴다. | 서비스 거부, 비용 폭증, 다음 run 침해, 자원 누수 | Phase 0 PoC, Phase 1~4 집행 | PRD-NFR-003, PRD-NFR-005, PRD-NFR-008 |

## 6. 보안 통제 카탈로그

아래 항목은 제품 보안 요구 계약이다. 일부 의미가 Harness prompt 계약에
존재하더라도 end-to-end 제품 runtime 집행과 negative fixture가 관찰되지
않았으므로 이 문서에서 통제를 `IMPLEMENTED` 또는 `PASSED`로 승격하지
않는다. `phase_blocking=true`는 관련 Phase에서 통제가 `FAILED`, `NOT_RUN`,
`PARTIAL` 또는 추적 `GAP`이면 Exit를 차단한다는 뜻이다.

| ID | Requirement | Severity | phase_blocking | Target Phase | Related THR | Related PRD-NFR | Negative VG | Residual risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CTL-001 | **비신뢰 data와 control plane 분리 및 injection 승격 차단.** repository, Issue, log, fixture, MCP description/output, external response와 model output을 비신뢰 data plane으로 표시하고 policy, approval, budget, state machine, tool schema를 바꾸는 control instruction으로 승격하지 않는다. schema와 policy 검증 뒤 injection fixture에서 authority·secret·effect 변화가 0이어야 한다. | CRITICAL | true | Phase 0 계약, Phase 1~4 집행 | THR-001 | PRD-NFR-002, PRD-NFR-004, PRD-NFR-012 | VG-004, VG-011, VG-020 | 허용된 data가 의미상 모델을 오도할 수 있으므로 output도 독립 policy와 검증을 거쳐야 한다. |
| CTL-002 | **RESOURCE canonical root-relative exact authority와 protected-resource before-read/mutation preflight.** RESOURCE는 canonical project-root-relative literal만 사용한다. `PROJECT`는 빈 companion list와 확인된 root containment, `NAMED_RESOURCES`는 non-empty case-sensitive exact membership만 허용하며 absolute/parent path, duplicate, wildcard, glob, regex, prefix·suffix 추론을 거부한다. protected resource·credential·private data는 exact target 인간 승인 전 첫 byte read를 거부하고 model context·log·evidence 유입을 0으로 유지한다. 사용자 변경, protected resource와 ownership은 mutation 전에도 다시 preflight한다. | CRITICAL | true | Phase 0~4 | THR-002 | PRD-NFR-002, PRD-NFR-003 | VG-005 | symlink와 filesystem race는 lexical 검사만으로 닫히지 않으므로 read와 mutation 시점 containment가 필요하다. |
| CTL-003 | **COMMAND id, command, cwd 3중 exact match와 NAMED_COMMANDS.** COMMAND는 `NAMED_COMMANDS`와 trusted validation record의 `id`, `command`, canonical root-relative `cwd`가 모두 case-sensitive exact 일치할 때만 허용한다. raw command, project-wide execute, case folding, trim, rewrite와 profile 외 command는 preflight에서 거부한다. | CRITICAL | true | Phase 0~4 | THR-003 | PRD-NFR-002, PRD-NFR-009 | VG-006 | trusted profile loader나 profile 저장소 자체가 손상되면 exact match만으로 안전하지 않다. |
| CTL-004 | **NETWORK canonical host:port exact match와 normalization 금지.** NETWORK는 canonical lower-case ASCII DNS `host[:port]`와 `NAMED_HOSTS` exact membership을 요구한다. scheme, path, query, fragment, userinfo, whitespace, uppercase, wildcard, default-port 확장, trim·rewrite와 redirect 권한 상속으로 일치를 만들지 않는다. | CRITICAL | true | Phase 0~4 | THR-004 | PRD-NFR-002, PRD-NFR-003, PRD-NFR-012 | VG-006, VG-008 | canonical identity는 목적지 안전을 보장하지 않으므로 CTL-012와 함께 집행해야 한다. |
| CTL-005 | **capability AVAILABLE, approved candidate, current revision, preflight 교집합.** action dispatch는 operation mode, 대응 capability `AVAILABLE`, approved candidate, current base revision, closed action identity, exact authority와 protected-resource/ownership/idempotency preflight의 교집합만 허용한다. 어느 안전 전제든 누락·불일치·`UNKNOWN`이면 실행 전에 거부한다. Part의 허용된 EXPLORE discovery와 Work의 approved action 경계는 혼합하지 않는다. | CRITICAL | true | Phase 0~4 | THR-002, THR-003, THR-006 | PRD-NFR-002, PRD-NFR-005 | VG-005, VG-006, VG-007 | preflight와 실제 effect 사이 상태 변화는 effect 직전 재검증 또는 원자적 집행이 필요하다. |
| CTL-006 | **destructive_actions와 external_side_effects 별도 hard gate.** 파괴적 효과에는 `destructive_actions=ALLOWED`, 외부 효과에는 별도의 runtime `external_side_effects=AVAILABLE`와 authority `external_side_effects=ALLOWED`를 요구한다. `DENIED` 또는 `UNKNOWN`은 인간 승인과 무관하게 hard deny하며 destructive와 external-effect gate를 서로 대체하지 않는다. | CRITICAL | true | Phase 0~4 | THR-006 | PRD-NFR-002, PRD-NFR-005, PRD-NFR-012 | VG-007 | 효과 분류가 잘못되면 별도 gate가 적용되지 않을 수 있으므로 effect taxonomy도 closed·versioned해야 한다. |
| CTL-007 | **approval signature, issuer/audience/tenant, all-input hash binding, atomic nonce.** approval capability는 한 candidate, 한 closed action identity, 한 target과 모든 효과 입력을 canonical `effect_hash` 또는 적용 가능한 모든 hash로 결합한다. signature, issuer, audience, approver subject, tenant, key, policy version, not-before/expiry를 검증하고 effect 직전에 nonce를 원자적으로 한 번만 소비한다. base revision, commit, Contract, plan, policy, candidate, identity, target, diff 또는 payload가 바뀌면 무효화하며 현재 authority와의 교집합만 실행한다. token·signature 원문은 packet/event에 넣지 않는다. | CRITICAL | true | Phase 0 계약, Phase 3~4 집행 | THR-006 | PRD-NFR-002, PRD-NFR-005, PRD-NFR-012 | VG-007 | approval key/service compromise와 잘못된 human 판단은 별도 운영·키 관리·review 위험으로 남는다. |
| CTL-008 | **replay mode hard deny, 새 identity, unknown outcome reconcile.** replay mode는 `AUDIT_REPLAY`, `REEXECUTE`, `COUNTERFACTUAL`의 closed enum을 사용한다. 모든 replay는 source lineage를 보존하고 새 run, correlation, revision/event sequence와 evidence namespace를 사용하며 approval, nonce, credential, authority, publisher token을 복사하지 않는다. `AUDIT_REPLAY`와 `COUNTERFACTUAL`은 external effect를 hard deny하고, `REEXECUTE`만 현재 상태 관찰과 effect별 새 candidate·approval·nonce·fresh evidence 후 제한적으로 허용한다. 결과 미상 effect는 reconcile 전 반복하지 않는다. | CRITICAL | true | Phase 0 계약, Phase 3~4 집행 | THR-009 | PRD-NFR-005, PRD-NFR-006, PRD-NFR-012 | VG-003, VG-019, VG-020 | 외부 시스템의 불완전한 조회나 eventual consistency 때문에 reconciliation이 장시간 미결로 남을 수 있다. |
| CTL-009 | **signed digest-pinned image와 provenance 검증.** 실행 image는 immutable digest로 pin하고 signature, issuer와 provenance를 검증하며 검증 실패 또는 미지원 provenance는 provision 전에 거부한다. manifest에는 실제 image digest와 검증 결과 reference를 남긴다. | CRITICAL | true | Phase 0 PoC, Phase 1~4 집행 | THR-005 | PRD-NFR-003, PRD-NFR-012 | VG-008 | signing root와 build pipeline compromise 또는 서명된 취약 image 위험은 별도 공급망 검증이 필요하다. |
| CTL-010 | **rootless, read-only rootfs, namespace/mount/device/socket hardening.** sandbox는 rootless/non-root와 user namespace, read-only rootfs, quota가 있는 workspace/tmp만 쓰기, capability drop ALL, no-new-privileges, seccomp와 AppArmor/SELinux를 강제하고 privileged, host PID/IPC/network namespace, device, Docker socket와 live host mount를 차단한다. | CRITICAL | true | Phase 0 PoC, Phase 1~4 집행 | THR-005 | PRD-NFR-003, PRD-NFR-012 | VG-008 | container는 host kernel을 공유하므로 악성 source에는 gVisor, Kata, microVM 또는 전용 worker 판단이 남는다. |
| CTL-011 | **CPU/memory/PID/disk/log/time quota와 verified teardown.** CPU, memory, PID, disk, file descriptor, log, network와 runtime quota를 강제하고 terminal/cancel 뒤 process tree, mount, lease, transient secret과 workspace가 0인지 runtime observation으로 검증한다. teardown 실패는 성공으로 숨기지 않고 release gate를 차단한다. | CRITICAL | true | Phase 0 PoC, Phase 1~4 집행 | THR-005, THR-012 | PRD-NFR-003, PRD-NFR-005, PRD-NFR-008 | VG-008, VG-014, VG-016 | shared kernel·storage·network의 side channel과 provider cleanup failure는 완전히 제거되지 않는다. |
| CTL-012 | **egress proxy, forbidden address ranges, rebinding/TOCTOU, redirect deny.** sandbox의 직접 socket과 DNS를 차단하고 task별 egress proxy만 허용한다. proxy는 연결 직전 모든 A/AAAA와 실제 connect 주소를 묶어 loopback, private, link-local, CGNAT, ULA, multicast, reserved와 cloud metadata를 차단하고 exact host/port, Host, SNI, certificate를 대조한다. redirect는 기본 거부하며 새 목적지에 권한을 상속하지 않는다. | CRITICAL | true | Phase 0 PoC, Phase 1~4 집행 | THR-004 | PRD-NFR-002, PRD-NFR-003, PRD-NFR-012 | VG-006, VG-008 | egress proxy, resolver, CA 또는 목적지 자체가 손상된 경우와 허용 서비스의 application-level 공격은 남는다. |
| CTL-013 | **pre-storage/export secret redaction, raw secret hash 금지.** secret, credential, private payload와 oversized raw log는 packet, event, prompt, artifact, trace, telemetry exporter와 사용자 응답에 넣지 않는다. stdout/stderr에는 저장·export 전에 quota와 실행 시 secret exact-match 및 pattern/entropy redaction을 적용하고 복원 가능한 preview와 raw secret의 일반 hash를 금지한다. redaction 불가 원문은 기본 폐기한다. | CRITICAL | true | Phase 0~4 | THR-007 | PRD-NFR-004, PRD-NFR-012 | VG-009 | 새 인코딩, 파편화된 secret과 탐지 false negative가 가능하므로 credential 최소화·회전이 계속 필요하다. |
| CTL-014 | **encrypted quarantine, tenant isolation, retention, tamper-evident artifact.** 정책상 보존이 필요한 민감 원문은 tenant별 key로 암호화한 quarantine에 두고 별도 RBAC/ABAC, 접근 승인·audit와 짧은 retention을 적용한다. 모든 artifact는 tenant 격리, 전송·저장 암호화, checksum, tamper-evident manifest, 접근 감사, backup을 포함한 deletion policy를 가지며 저장 후에도 비신뢰 data로 취급한다. | CRITICAL | true | Phase 0 전략, Phase 1~4 집행 | THR-007, THR-008 | PRD-NFR-004, PRD-NFR-006, PRD-NFR-012 | VG-009, VG-021 | key/admin compromise, backup 복제본과 외부 storage의 deletion 지연은 운영 잔여 위험이다. |
| CTL-015 | **closed evidence type와 revision/time freshness validation.** evidence는 unique non-empty ID, exact unique references와 closed type `file`, `diff`, `command`, `test`, `render`, `runtime`, `approval`만 허용한다. `file`/`diff`는 원본 JSON integer `observed_revision==base_revision`만 요구하고 `observed_at`을 금지한다. 나머지는 runtime-supplied strict UTC `observed_at`만 요구하고 `observed_revision`을 금지하며 trusted `validationAt` 대비 0~300초만 fresh다. missing, wrong-mode, stale, future, dangling, duplicate와 낮은 tier evidence는 fail-closed하고 timestamp를 만들지 않는다. | CRITICAL | true | Phase 0~4 | THR-010 | PRD-NFR-001, PRD-NFR-006 | VG-003, VG-023 | trusted validator clock·context나 evidence producer가 손상되면 형식 검증만으로 진실성을 보장하지 못한다. |
| CTL-016 | **trusted baseline, test anti-tamper, deterministic result precedence.** baseline, verification profile와 hidden evaluator를 agent workspace 밖의 trusted source로 유지하고 exact command profile을 사용한다. test 삭제, skip, xfail, assertion 완화, coverage exclude와 config 변경을 탐지하며 agent가 만든 test만의 통과를 성공으로 보지 않는다. deterministic execution/rule 실패와 baseline 회귀는 rubric 또는 human score로 뒤집지 않는다. | HIGH | true | Phase 1~4 | THR-011 | PRD-NFR-001, PRD-NFR-010 | VG-013, VG-017 | trusted baseline 자체의 결함, flaky test와 hidden evaluator coverage 공백은 inconclusive 위험으로 남는다. |
| CTL-017 | **bounded budget, failure signature, no-progress stop.** 시간, token, tool, command, repair, 비용과 resource budget을 강제하고 failure signature, 이전 diff와 evidence를 비교한다. 새 signature, evidence 또는 가설 변화가 없는 반복과 동일 failure, 한도 초과, 위험·권한 상승에서 추가 실행을 중단하며 숫자를 자동으로 늘리지 않는다. | HIGH | true | Phase 2~4 | THR-012 | PRD-NFR-005, PRD-NFR-008 | VG-014, VG-016 | 새로운 형태의 no-progress와 외부 provider 비용·지연은 signature가 즉시 포착하지 못할 수 있다. |
| CTL-018 | **MCP allowlist, scoped credential, schema/size/timeout/redaction.** MCP는 동적 탐색·자동 설치를 금지하고 검토된 allowlist의 고정 version만 허용한다. server·tool·tenant audience에 묶인 short-lived 최소 권한 credential을 Gateway가 주입하며 upstream token 전달을 금지한다. 입력·출력에 closed schema, size, timeout, rate, cancellation, redaction와 audit를 적용하고 description/output은 계속 비신뢰 data로 취급한다. | HIGH | true | Phase 3~4 | THR-001 | PRD-NFR-002, PRD-NFR-004, PRD-NFR-012 | VG-011, VG-020 | allowlisted server compromise와 schema-valid 악성 semantic output은 CTL-001과 후속 검증이 필요하다. |
| CTL-019 | **idempotency key, webhook dedup, non-idempotent retry block.** logical request와 effect에 stable idempotency key, webhook event dedup, expected revision과 effect result ledger를 적용하고 동일 key의 다른 body를 거부한다. timeout·unknown outcome의 비멱등 effect는 자동 retry하지 않고 remote state reconciliation이 끝날 때까지 같은 effect를 차단한다. | CRITICAL | true | Phase 3~4 | THR-009 | PRD-NFR-005, PRD-NFR-006, PRD-NFR-012 | VG-019, VG-020 | downstream이 idempotency·조회 기능을 제공하지 않으면 effect를 안전하게 재개하지 못하고 human reconciliation이 필요하다. |
| CTL-020 | **complete audit trace와 zero-event security invariant release block.** event, manifest와 audit는 task, run, correlation, base/state revision, actor, source, canonical Main `seq`, product `stream_seq`, evidence/artifact reference와 tamper-evident chain을 완전하게 보존한다. Main만 accepted state·revision·canonical sequence를 확정하며 저장 record는 authority가 아니다. gateway 우회 외부 write, 무권한 실행, raw secret 기록, approval nonce/token 재사용, cross-tenant artifact 접근 중 하나라도 관찰되거나 필수 audit trace가 비면 release를 차단하고 security incident로 처리한다. | CRITICAL | true | Phase 0~4 | THR-008, THR-010, THR-011 | PRD-NFR-001, PRD-NFR-006, PRD-NFR-012 | VG-003, VG-009, VG-013, VG-017, VG-021, VG-023 | instrumentation·store·signing key compromise와 분산 ordering 오류가 있으면 trace completeness와 진실성이 함께 손상될 수 있다. |

Severity downgrade는 변경된 threat premise, 동등하거나 강한 substitute control,
fresh verification evidence, RTM과 risk register 갱신을 **같은 변경**에
포함할 때만 검토한다. 승인이나 일정 압박만으로 severity 또는
`phase_blocking`을 낮출 수 없다.

## 7. 위협·통제·검증 매핑

다음은 기준 최소 매핑이며, 이 문서 초안은 이를 정확히 적용한다.

| THR | CTL | Negative VG |
| --- | --- | --- |
| THR-001 | CTL-001, CTL-018 | VG-004, VG-011, VG-020 |
| THR-002 | CTL-002, CTL-005 | VG-005 |
| THR-003 | CTL-003, CTL-005 | VG-006 |
| THR-004 | CTL-004, CTL-012 | VG-006, VG-008 |
| THR-005 | CTL-009, CTL-010, CTL-011 | VG-008 |
| THR-006 | CTL-005, CTL-006, CTL-007 | VG-007 |
| THR-007 | CTL-013, CTL-014 | VG-009 |
| THR-008 | CTL-014, CTL-020 | VG-009, VG-021 |
| THR-009 | CTL-008, CTL-019 | VG-003, VG-019, VG-020 |
| THR-010 | CTL-015, CTL-020 | VG-003, VG-023 |
| THR-011 | CTL-016, CTL-020 | VG-013, VG-017 |
| THR-012 | CTL-011, CTL-017 | VG-014, VG-016 |

Negative VG는 공격 fixture가 **실제 effect 전에** 예상한 stable fail-closed
결과로 거부되고 요구 floor의 fresh evidence를 남기는지를 검증한다. VG ID는
검증 계약 reference이지 현재 `PASSED` 증빙이 아니다. 후속 검증·평가 계획과
RTM에서 정의·연결되기 전에는 `NOT_RUN`과 추적 공백을 유지한다.

여러 Phase에 걸친 통제는 최초 Target Phase에서 계약 negative fixture를 먼저
통과하고 후속 Phase에서 runtime 집행 fixture를 누적 통과해야 한다. 따라서
CTL-001의 VG-004와 CTL-008의 VG-003은 각각 Phase 0 계약 gate이고,
VG-011·VG-019·VG-020은 후속 runtime gate다. 후속 VG 계획은 Phase 0의
계약-level 실패 경로를 대신하지 않는다.

어떤 `THR`, `CTL` 또는 negative `VG`든 orphan이면 문서 baselining을
차단한다. 모든 위협은 최소 하나의 통제와 negative VG, 모든 통제는
PRD-NFR·WBS·VG, 모든 VG는 expected fail-closed 결과와 evidence floor를
가져야 한다. 이 교차 추적이 없거나 `PARTIAL`/`GAP`이면 해당 Phase Exit를
통과할 수 없다.

## 8. Phase별 보안 gate

| Phase | 적용되는 phase-blocking 통제 | 필수 보안 Exit gate | 대표 negative VG | 현재 결과 |
| --- | --- | --- | --- | --- |
| Phase 0 | CTL-001~CTL-015, CTL-020의 계약·PoC 범위 | example schema와 Harness conformance를 통과하고 injection field의 control-plane 승격, replay mode·identity·effect 계약 위반, invalid transition/authority와 approval deny/expiry/nonce reuse가 fail-closed해야 한다. sandbox containment와 secret fixture는 100% 통과해야 한다. | VG-003, VG-004, VG-005, VG-006, VG-007, VG-008, VG-009 | NOT_RUN — 제품 validator, approval service, sandbox/redaction PoC의 fresh evidence가 없다. |
| Phase 1 | CTL-001~CTL-016, CTL-020의 local runtime 범위 | 모든 필수 criterion이 E2 이상이어야 하며 unauthorized execution 0, cleanup failure 0, external write 0이어야 한다. immutable source와 ephemeral workspace, trusted verification과 trace가 관찰되어야 한다. | VG-011, VG-013, VG-014 | NOT_RUN — local vertical slice와 격리 runtime이 없다. |
| Phase 2 | Phase 1 통제와 CTL-017 | 최소 5회 반복과 사전 고정 평가 계약을 사용하고 unauthorized action 0, raw secret 0, critical injection escape 0을 유지해야 한다. task-success paired 95% CI 하한은 0보다 크고 regression-rate paired 95% CI 상한은 0보다 작아야 하며 deterministic failure를 정성 점수가 뒤집지 않아야 한다. | VG-016, VG-017 | NOT_RUN — recovery와 evaluation runtime 및 반복 evidence가 없다. |
| Phase 3 | CTL-001~CTL-020의 controlled integration 범위 | idempotency, expired approval, duplicate webhook와 unauthorized external write 시험을 통과하고 effect별 새 approval·nonce, tenant-scoped RBAC/audit와 Publisher 단일 write 경계를 검증해야 한다. | VG-019, VG-020 | NOT_RUN — durable queue, remote worker, MCP/GitHub integration과 Publisher가 없다. |
| Phase 4 | CTL-001~CTL-020의 multi-tenant 운영 범위 | rolling 30-day SLO를 충족하고 gateway 우회 write, 무권한 실행, raw secret 기록, nonce/token 재사용, cross-tenant artifact 접근이 모두 0이어야 한다. stronger isolation과 retention/deletion도 운영 관찰로 검증해야 한다. | VG-021, VG-023 | NOT_RUN — multi-tenant runtime과 rolling 운영 window가 없다. |

모든 Phase에서 다음 조건을 추가로 적용한다.

- 대상 Phase의 `phase_blocking=true` 통제는 RTM 추적 `COVERED`, 관련 negative
  VG `PASSED`, 요구 floor의 fresh evidence를 모두 가져야 한다.
- `FAILED`, `NOT_RUN`, inconclusive, stale evidence, 추적 `PARTIAL` 또는
  `GAP`을 통과로 간주하지 않는다. Harness Foundation의 `IMPLEMENTED` 상태는
  제품 Phase gate를 대신하지 않는다.
- gateway 우회 외부 write, 무권한 action 실제 실행, 확인된 raw secret
  기록, approval nonce/token 재사용 또는 cross-tenant artifact 접근은 한
  건만 있어도 즉시 release blocker와 security incident다.
- unresolved `HIGH` 또는 `CRITICAL` risk와 approval·authority·freshness
  충돌은 명시적 human gate 없이는 다음 Phase로 넘기지 않는다.

## 9. 잔여 위험과 변경 규칙

| 잔여 위험 | 남는 이유 | 현재 처리와 release 영향 |
| --- | --- | --- |
| 현행 Harness의 직접 workspace 변경 | Work는 허용된 exact resource를 현재 project workspace에서 직접 변경하며 immutable snapshot·sandbox가 없다. | 사용자 변경 보존과 exact authority를 적용하되 containment, durable recovery, rollback을 주장하지 않는다. 제품 Phase gate는 `NOT_RUN`이다. |
| Sandbox shared-kernel 위험 | rootless container hardening도 host kernel 취약점과 side channel을 제거하지 못한다. | 악성·외부 source에는 gVisor, Kata, microVM 또는 전용 worker를 위험 등급과 PoC evidence로 선택한다. 결정 전 Phase Exit를 허용하지 않는다. |
| Approval trust anchor와 human error | signature 검증은 key/service compromise나 잘못된 승인 판단을 막지 못한다. | key rotation·분리, approver authentication, dual review 대상과 incident response를 후속 운영 설계에 연결한다. binding·nonce 실패는 수용하지 않는다. |
| Egress infrastructure compromise | proxy, resolver, CA 또는 허용 endpoint가 손상될 수 있다. | 직접 network를 계속 deny하고 목적지·TLS·quota observation을 남긴다. 내부망 예외는 named zone, exact action과 별도 approval 없이는 허용하지 않는다. |
| Secret 탐지 공백 | 인코딩·분할·새 형식은 redaction을 우회할 수 있고 false positive도 있다. | credential 미주입·최소 scope·짧은 수명·회전을 우선하며 redaction 불가 원문은 폐기한다. raw secret 1건은 release blocker다. |
| Tenant artifact와 deletion 지연 | backup, quarantine, object store와 운영자 경로는 완전한 즉시 삭제가 어렵다. | tenant key·authorization·audit·retention과 deletion evidence를 요구한다. cross-tenant 접근 1건은 수용하지 않는다. |
| Trusted profile·baseline 오류 | trusted source도 잘못되거나 flaky·불완전할 수 있다. | baseline unhealthy와 inconclusive를 성공으로 승격하지 않고 독립 evaluator와 fixed fixture를 사용한다. 결정론적 실패는 그대로 남긴다. |
| 결과 미상 external effect | timeout과 eventual consistency 때문에 effect 발생 여부를 즉시 확정할 수 없다. | 동일 effect를 차단하고 `RECONCILIATION_REQUIRED`로 remote state를 관찰한다. 자동 retry나 approval nonce 복원은 금지한다. |
| Evidence·audit trust anchor 손상 | producer, validator clock, event store 또는 signing key가 손상되면 형식상 valid한 거짓 기록이 가능하다. | independent verification, key 분리, tamper-evident chain과 completeness monitor를 요구한다. missing/future/stale evidence는 fail-closed한다. |
| 자원·비용 side channel | quota 안에서도 shared service 고갈이나 외부 provider 비용·지연이 발생할 수 있다. | tenant/task quota, global circuit breaker와 cleanup SLI를 후속 운영 설계에서 검증한다. budget 자동 확대는 금지한다. |

잔여 위험은 이 문서의 존재만으로 수용되지 않는다. 실제 수용은 위험
등록부의 owner, trigger, 기한, 명시적 decision과 해당 Phase의 fresh
evidence가 필요하다. 다음 변경 규칙을 적용한다.

1. `THR`과 `CTL` ID는 한 번 추적에 사용하면 의미를 바꾸거나 재사용하지
   않는다. 제거가 필요하면 폐기 상태와 기존 link를 보존한다.
2. severity downgrade에는 변경된 위협 전제, substitute control, fresh
   verification evidence, RTM과 risk register 갱신을 같은 변경에 포함한다.
3. exact authority, destructive/external-effect hard gate, approval all-input
   binding·atomic nonce, replay hard deny, sandbox·egress, secret·artifact,
   evidence freshness 불변식을 완화하는 변경은 단순 문구 수정이 아니라
   보안 설계 변경이며 Protocol과 상위 요구사항 검토를 다시 거친다.
4. 통제는 실제 negative fixture가 요구 evidence floor에서 fresh `PASSED`일
   때만 검증 완료로 표시한다. 계획된 command, 미래 artifact path,
   자체 생성 timestamp, stale observation과 정성 점수는 증빙이 아니다.
5. orphan THR·CTL·negative VG, unresolved `CRITICAL` 통제, zero-event 보안
   불변식 위반 또는 상위 출처 충돌은 baselining과 release를 차단한다.

## 10. 관련 문서

- [ForgeOps 제품 요구사항 문서](../product/prd.md) — 보안·신뢰성 NFR과 Phase Exit gate
- [ForgeOps 시스템 아키텍처](../architecture/system-architecture.md) — 구성요소, trust boundary, approval·replay·sandbox 계약
- [ForgeOps 제품 기초 문서 체계 설계](../superpowers/specs/2026-07-14-forgeops-product-documentation-design.md) — 승인된 보안 문서 책임과 완료 기준
- [ForgeOps 제품 문서화 실행 계획](../superpowers/plans/2026-07-14-forgeops-product-documentation.md) — THR·CTL·negative VG 작성 계약
- [ForgeOps 전체 제품 핸드오프](../handoff/forgeops-full-handoff.md) — 제품 비전과 보안 입력 기준선
- [저장소 기본 지시와 ForgeOps project profile](../../AGENTS.md) — protected resource와 repository 운영 경계
- [Main Orchestrator Protocol 2.0](../../.github/agents/main_instruction.prompt.md) — canonical state, authority, evidence와 human gate 불변식
- [Part Analyst 역할 계약](../../.github/agents/part_agent.prompt.md) — read-only discovery와 비신뢰 입력 경계
- [Work Executor 역할 계약](../../.github/agents/work_agent.prompt.md) — exact action preflight, 실행, fresh evidence와 residual risk 경계
