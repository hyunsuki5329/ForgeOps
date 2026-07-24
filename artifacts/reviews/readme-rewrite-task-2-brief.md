# Task 2: Rewrite the top-level README as a project guide

**Files:**
- Modify: `README.md`
- Reference: `docs/superpowers/specs/2026-07-24-readme-introduction-design.md`
- Reference: `docs/project/wbs.md`

**Binding constraints:**

- Replace the top-level README as authorized by the user; do not preserve obsolete standalone text only because it already exists.
- Keep Korean copy concise and accessible to developers and evaluators.
- Do not claim Phase 0 Exit, WBS-008 completion, deployment, or external integration.
- Use only repository-relative links to existing files.
- Do not stage, commit, push, publish, or modify Git internals.

**Required README content:**

Replace `README.md` with exactly the following Markdown content:

````markdown
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
- **남은 게이트:** [WBS](docs/project/wbs.md)의 WBS-008은 VG-004 증빙이 있어도 별도 Phase 4 VG-023 evidence/provenance 게이트가 남아 있으므로 `WBS_IN_PROGRESS`입니다. 이는 Phase 0 Exit 완료를 의미하지 않습니다.

## 검증 실행

W3 인터페이스 계약 검증은 다음 등록 명령으로 실행합니다.

```powershell
python tools/interface_contract/verify.py --openapi contracts/forgeops-api/1.0/openapi.yaml --event-schema contracts/forgeops-event/1.0/schema.json --manifest-schema contracts/forgeops-run-manifest/1.0/schema.json --api-version-suite fixtures/forgeops-api/version-envelope-suite.json --api-boundary-suite fixtures/forgeops-api/data-control-suite.json --event-suite fixtures/forgeops-event-contract/suite.json --manifest-suite fixtures/forgeops-run-manifest/suite.json --result artifacts/verification/vg-004-interface-contract-result.json --command-id interface-contract-fixture
```

검증 결과는 공개 가능한 요약만 남기며, 거부 fixture에서 외부 효과가 발생하지 않는지도 함께 확인합니다.

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
````

**Verification:**

1. `rg -n "^# ForgeOps$|^## (ForgeOps란\?|핵심 원칙|역할과 책임|현재 구현 상태|검증 실행|문서 안내|다른 프로젝트에 적용하기)$|WBS-008|VG-023|interface-contract-fixture" README.md`
2. Verify each Markdown link targets an existing repository file.
3. `git diff --check -- README.md`
4. `git diff -- README.md`

Expected: all headings occur once; all links exist; WBS-008 is `WBS_IN_PROGRESS` pending VG-023; no whitespace errors; README is a coherent replacement.
