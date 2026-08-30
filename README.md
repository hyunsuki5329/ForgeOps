# ForgeOps

ForgeOps는 AI 에이전트가 소프트웨어 작업을 수행할 때 필요한 계약, 권한, 상태 전이, 증빙을 명확하게 정의하고 검증하는 안전 중심 프레임워크입니다. 제품 요청 데이터와 실행 제어 정보를 분리해, 에이전트의 판단과 실행 결과를 재현 가능하고 감사 가능한 형태로 관리합니다.

## ForgeOps란?

에이전트 기반 개발 자동화에서는 “무엇을 만들 것인가”와 “어떤 권한으로 어떻게 실행할 것인가”를 분리해야 합니다. ForgeOps는 이 경계를 계약으로 고정하고, 승인된 실행과 검증 결과만 신뢰할 수 있는 기록으로 남기도록 설계합니다.

## 핵심 원칙

- **데이터와 제어의 분리:** 제품 요청은 실행 권한, 승인, 정책, 예산, 상태를 직접 부여하지 않습니다.
- **명시적 권한과 승인:** 파일, 명령, 네트워크, 외부 효과는 정확한 대상과 승인 조건에 따라 허용하거나 거부합니다.
- **추적 가능한 실행 기록:** durable event와 run manifest가 task/run identity, 순서, revision, provenance를 보존합니다.
- **실행 가능한 검증:** 스키마와 fixture 기반 검증 게이트로 정상 동작과 거부 동작을 자동 확인합니다.

## 역할과 책임

| 역할 | 책임 |
| --- | --- |
| Main | 요청을 정규화하고, 최종 상태·revision·canonical event sequence·MainDecision을 소유합니다. |
| Part | 읽기 전용으로 저장소를 분석하고, 실행 후보와 근거를 제안합니다. |
| Work | 승인된 범위 안에서만 변경·명령 실행·검증을 수행하고 결과를 증빙과 함께 제안합니다. |

## 현재 구현 상태

- **W1:** Product Contract와 TaskPacket bridge, 계약 검증 fixture를 구현했습니다.
- **W2:** 상태 전이, replay, resource/command/network authority, approval/effect policy 검증을 구현했습니다.
- **W3:** versioned OpenAPI, data/control boundary, durable event, run manifest, VG-004 인터페이스 계약 검증을 구현했습니다.
- **W4:** Foundation conformance, attested sandbox containment·egress·teardown, secret surface와 artifact isolation 검증을 구현했습니다.
- **W5:** content-addressed immutable snapshot, trusted baseline runner, deterministic Context Pack과 VG-010/VG-011 E2 검증을 구현했습니다. WBS-013~015는 완료됐습니다.
- **W6:** Product Task를 Main이 정규화하고 Part가 read-only 후보를 제안한 뒤, Main-issued immutable context로 Work의 exact fixture action을 제한하고 Main만 accepted revision과 canonical event sequence를 확정하는 local vertical flow를 구현했습니다. VG-012는 30/30 사례가 fresh E2 `PASSED`입니다.
- **W7:** 원본과 분리된 workspace의 bounded patch/canonical diff, code-owned task·regression·lint·typecheck profile, baseline differential과 test/coverage/profile anti-tamper를 구현했습니다. VG-013 세 명령은 합계 27/27 사례가 fresh E2 `PASSED`입니다.
- **W8:** fail-closed budget·no-progress stop, cancellation과 5종 adapter cleanup, closed trace manifest, 정적 viewer와 external-write gateway를 구현했습니다. VG-014/VG-015 네 명령은 합계 48/48 사례가 fresh E2 `PASSED`입니다.
- **Phase 0:** 등록된 18개 필수 결과가 모두 `PASSED`이고 blockers 0으로 `READY`입니다. W1~W9의 해당 범위와 Phase 1 safety gate는 완료됐지만 Phase 1 Exit 및 배포 작업은 아직 완료되지 않았습니다.

## 검증 실행

W3 인터페이스 계약 검증은 다음 등록 명령으로 실행합니다.

```powershell
python tools/interface_contract/verify.py --openapi contracts/forgeops-api/1.0/openapi.yaml --event-schema contracts/forgeops-event/1.0/schema.json --manifest-schema contracts/forgeops-run-manifest/1.0/schema.json --api-version-suite fixtures/forgeops-api/version-envelope-suite.json --api-boundary-suite fixtures/forgeops-api/data-control-suite.json --event-suite fixtures/forgeops-event-contract/suite.json --manifest-suite fixtures/forgeops-run-manifest/suite.json --result artifacts/verification/vg-004-interface-contract-result.json --command-id interface-contract-fixture
```

검증 결과는 공개 가능한 요약만 남기며, 거부 fixture에서 외부 효과가 발생하지 않는지도 함께 확인합니다.

W5는 `forgeops-snapshot-baseline`과 `forgeops-context-security` 프로필의 등록 명령 4개로 검증합니다. 현재 VG-010은 24/24, VG-011은 20/20 사례가 fresh E2 `PASSED`이며 관찰 가능한 source write는 0입니다. OS 수준 protected read, network call, external write는 이 E2 검증 범위에서 0으로 단정하지 않고 결과에 `null`로 기록합니다. 이 결과는 VG-010/VG-011 범위만 증명하며 VG-013이나 Phase 1 Exit를 선언하지 않습니다.

W6는 `forgeops-local-vertical` 프로필의 `main-part-work-main` 명령으로 검증합니다. 결과는 `artifacts/verification/vg-012-local-vertical-result.json`에 30/30 E2 `PASSED`, source tree hash unchanged, unauthorized fixture effect 0으로 기록됩니다.

W7은 `forgeops-patch-verification` 프로필의 `task-checks`, `regression-checks`, `verification-anti-tamper` 명령으로 검증합니다. 세 결과는 `artifacts/verification/vg-013-*-result.json`에 각각 9/9 E2 `PASSED`로 기록되며, 관찰된 unauthorized workspace effect·outside-workspace write attempt·remote write attempt·raw secret occurrence는 모두 0입니다. OS 전체 host write와 network call은 이 로컬 E2 검증에서 관찰하지 않아 `null`입니다.

W8은 `forgeops-lifecycle-budget`과 `forgeops-trace-manifest` 프로필의 네 등록 명령으로 검증합니다. `artifacts/verification/vg-014-*-result.json`과 `vg-015-*-result.json`에 16/16, 10/10, 12/12, 10/10 E2 `PASSED`가 기록되며 정적 trace viewer는 `artifacts/reviews/w8-trace-viewer.html`입니다. OS process tree·mount·network는 기존 VG-008 E3가 소유하고 W8 결과에서는 `null`입니다. W9와 Phase 1 safety gate도 완료됐으며 Phase 1 Exit는 W10 범위로 남아 있습니다.

## 문서 안내

- [프로젝트 운영 규칙](AGENTS.md)
- [제품 요구사항](docs/product/prd.md)
- [시스템 아키텍처](docs/architecture/system-architecture.md)
- [위협 모델](docs/security/threat-model.md)
- [검증 및 평가 계획](docs/quality/verification-and-evaluation-plan.md)
- [작업 분해 구조](docs/project/wbs.md)
- [요구사항 추적성 매트릭스](docs/project/requirements-traceability-matrix.md)

## 다른 프로젝트에 적용하기

ForgeOps의 Portable Agent Harness는 프로젝트 독립적인 Protocol 2.0 규칙을 제공합니다. 새 프로젝트에서는 공통 harness prompt를 복사하는 대신, 해당 프로젝트의 adapter와 project profile을 작성해 적용 범위·보호 자원·검증 명령을 명시합니다.

- [포팅 가이드](docs/agent-harness/PORTING_GUIDE.md)
- [Copilot adapter](.github/copilot-instructions.md)
- [Main orchestrator](.github/agents/main_instruction.prompt.md)
- [Part analyst](.github/agents/part_agent.prompt.md)
- [Work executor](.github/agents/work_agent.prompt.md)

## W9 completion status

W9 is complete. Protected-main [run 33287890009](https://github.com/hyunsuki5329/ForgeOps/actions/runs/33287890009) verified source SHA `ff16f39d74861710c5500d81045c46512ee8d589` through the isolated two-job Linux E3 path. The sole signed artifact was independently verified and imported: the security-negative reducer passed 20/20, the required-evidence reducer passed 19/19 (five E3 plus fourteen E2), and the Phase 1 safety gate is `READY` with blockers 0 and all eight effect counters at 0. WBS-026~WBS-028 are `WBS_DONE`; W10, VG-024, Phase 1 Exit, deployment, and release are still incomplete.
