# ForgeOps README Introduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a concise Korean introduction to the repository README that explains ForgeOps and its current verified scope.

**Architecture:** The change is limited to the top-level README. A new section appears directly after the title and before the existing Portable Agent Harness section, preserving all current links and protocol material. Its status language is derived from the approved design and WBS.

**Tech Stack:** Markdown and repository-relative links.

## Global Constraints

- Modify only `README.md` for the product-facing introduction.
- Keep Korean copy concise and accessible to developers and evaluators.
- Do not claim Phase 0 Exit, WBS-008 completion, deployment, or external integration.
- Do not stage, commit, push, publish, or modify Git internals.

---

### Task 1: Add the ForgeOps introduction

**Files:**
- Modify: `README.md:3` immediately after `# ForgeOps`
- Reference: `docs/superpowers/specs/2026-07-24-readme-introduction-design.md`
- Reference: `docs/project/wbs.md`

**Interfaces:**
- Consumes: the README title and existing `## Portable Agent Harness` heading.
- Produces: a `## ForgeOps란?` section with a definition, four principles, and a WBS status note.

- [ ] **Step 1: Confirm the insertion boundary**

Run: `rg -n "^# ForgeOps$|^## Portable Agent Harness$" README.md`

Expected: the title is followed by the existing Portable Agent Harness heading, with no introduction section between them.

- [ ] **Step 2: Insert the approved Markdown copy**

Insert directly below the title:

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

- [ ] **Step 3: Validate Markdown placement and status wording**

Run: `rg -n "^# ForgeOps$|^## ForgeOps란\?$|^### 현재 구현 범위$|^## Portable Agent Harness$|WBS-008|VG-023" README.md`

Expected: the new sections occur between the title and Portable Agent Harness, and WBS-008 is described as `WBS_IN_PROGRESS` pending VG-023.

- [ ] **Step 4: Inspect the final diff without Git mutation**

Run: `git diff --check -- README.md; git diff -- README.md`

Expected: no whitespace errors; only the planned README introduction is added.

### Task 2: Rewrite the top-level README as a project guide

**Files:**
- Modify: `README.md`
- Reference: `docs/superpowers/specs/2026-07-24-readme-introduction-design.md`
- Reference: `docs/project/wbs.md`

**Interfaces:**
- Consumes: verified W1-W3 delivery state and repository documentation paths.
- Produces: a standalone Korean project guide with an accurate status boundary.

- [ ] **Step 1: Replace the whole README with the approved guide structure**

Use these headings in order: `ForgeOps`, `ForgeOps란?`, `핵심 원칙`, `역할과 책임`, `현재 구현 상태`, `검증 실행`, `문서 안내`, `다른 프로젝트에 적용하기`.

The guide must define ForgeOps as a safety-first framework for AI-agent workflows; cover data/control separation, explicit authority and approval, durable records, and executable verification; state Main/Part/Work ownership; accurately describe W1-W3 and WBS-008/VG-023; include the registered VG-004 command; and link only to existing project-relative documents.

- [ ] **Step 2: Verify the guide**

Run: `rg -n "^# ForgeOps$|^## (ForgeOps란\?|핵심 원칙|역할과 책임|현재 구현 상태|검증 실행|문서 안내|다른 프로젝트에 적용하기)$|WBS-008|VG-023|interface-contract-fixture" README.md`

Expected: every required heading appears once; WBS-008 remains `WBS_IN_PROGRESS` pending VG-023; the registered command identity appears.

- [ ] **Step 3: Check links and diff**

Run: `git diff --check -- README.md; git diff -- README.md`

Expected: no whitespace errors; the README is a coherent replacement without protocol, contract, fixture, code, or Git changes.
