# Task 1: Add the ForgeOps introduction

**Files:**
- Modify: `README.md:3` immediately after `# ForgeOps`
- Reference: `docs/superpowers/specs/2026-07-24-readme-introduction-design.md`
- Reference: `docs/project/wbs.md`

**Binding constraints:**

- Modify only `README.md` for the product-facing introduction.
- Keep Korean copy concise and accessible to developers and evaluators.
- Do not claim Phase 0 Exit, WBS-008 completion, deployment, or external integration.
- Do not stage, commit, push, publish, or modify Git internals.

**Required content:**

Insert directly below `# ForgeOps` and before `## Portable Agent Harness`:

```markdown
## ForgeOps란?

ForgeOps는 AI 에이전트가 소프트웨어 작업을 수행할 때 필요한 계약, 권한, 상태 전이, 증빙을 명확하게 정의하고 검증하는 안전 중심 프레임워크입니다. 제품 요청 데이터와 실행 제어 정보를 분리해, 에이전트의 판단과 실행 결과를 재현 가능하고 감사 가능한 형태로 관리합니다.

- **역할 분리:** Main은 최종 상태와 결정을 소유하고, Part는 읽기 전용 분석을, Work는 승인된 범위의 실행과 검증을 담당합니다.
- **명시적 권한과 승인:** 파일, 명령, 네트워크, 외부 효과를 정확한 대상과 승인 조건으로 제한합니다.
- **추적 가능한 실행 기록:** durable event와 run manifest로 task/run identity, 순서, revision, provenance를 보존합니다.
- **실행 가능한 검증:** 스키마와 fixture 기반 검증 게이트로 정상·거부 동작을 자동 확인합니다.

### 현재 구현 범위

W1~W3의 핵심 계약 작업과 VG-004 인터페이스 검증이 구현되어 있습니다. 다만 [WBS](docs/project/wbs.md)의 WBS-008은 별도 Phase 4 VG-023 증빙 게이트가 남아 `WBS_IN_PROGRESS` 상태이며, 이를 Phase 0 완료로 해석하지 않습니다.
```

**Verification:**

1. `rg -n "^# ForgeOps$|^## ForgeOps란\?$|^### 현재 구현 범위$|^## Portable Agent Harness$|WBS-008|VG-023" README.md`
2. `git diff --check -- README.md`
3. `git diff -- README.md`

Expected: the new sections sit between the title and Portable Agent Harness; WBS-008 is `WBS_IN_PROGRESS` pending VG-023; no whitespace errors; only the specified README content changes.
