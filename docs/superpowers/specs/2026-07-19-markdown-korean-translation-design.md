# ForgeOps 일반 Markdown 한국어 번역 설계

**작성일:** 2026-07-19
**상태:** 승인된 방향; 번역 실행 전
**대상:** ForgeOps 저장소의 일반 Markdown 문서

## 1. 목적

ForgeOps의 README, 가이드, 설계서, 계획서와 제품·프로젝트 문서를 한국어
사용자가 일관되게 읽을 수 있도록 자연어 서술을 기술 한국어로 번역한다.
번역은 문서 가독성을 높이되 Protocol, agent 동작, 명령, 스키마와 추적
식별자의 의미를 바꾸지 않는다.

## 2. 대상 범위

Git이 추적하는 일반 문서 가운데 다음 범주를 번역 대상으로 삼는다.

- 루트 `README.md`
- `docs/README.md`
- `docs/agent-harness/PORTING_GUIDE.md`
- `docs/handoff/forgeops-full-handoff.md`
- `docs/product/`, `docs/architecture/`, `docs/security/`, `docs/quality/`,
  `docs/project/` 아래 Markdown 문서
- `docs/superpowers/specs/`와 `docs/superpowers/plans/` 아래 설계·계획 문서

이미 한국어인 문장은 유지한다. 영어 비중이 높은 문서를 우선 번역하고,
혼용 문서에서는 독립적인 영어 자연어 문장·제목·표 설명만 번역한다.

## 3. 제외 범위

다음 파일은 실행 지시 또는 Protocol 계약이므로 번역하거나 수정하지 않는다.

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.github/agents/main_instruction.prompt.md`
- `.github/agents/part_agent.prompt.md`
- `.github/agents/work_agent.prompt.md`

`LICENSE`, 소스 코드, 설정, 생성 산출물, Git 내부 상태와 외부 저장소도 범위
밖이다. 번역 작업은 커밋, 푸시, PR 생성 또는 외부 게시 권한을 포함하지
않는다.

## 4. 번역 규칙

다음 자연어 요소를 자연스러운 기술 한국어로 번역한다.

- Markdown 제목과 절 이름
- 설명 문단, 목록 설명과 인용문
- 표의 자연어 열 이름과 셀 설명
- 상태·목적·대상 독자처럼 사람이 읽는 metadata 값

다음 요소는 case와 철자를 포함해 원문 그대로 보존한다.

- fenced code block과 그 안의 모든 내용
- backtick으로 감싼 inline code
- 파일 경로, URL, Git SHA와 명령어
- Protocol 이름, packet·schema field, enum과 stable error code
- `PRD-*`, `ARC-*`, `THR-*`, `CTL-*`, `VG-*`, `WBS-*`, `RSK-*` 식별자
- validator의 기대 출력과 복사·실행용 문자열

Main, Part, Work, TaskPacket처럼 고유 계약 의미가 있는 용어는 번역하지 않고
한국어 조사와 설명만 자연스럽게 연결한다. 일반 영어 용어는 최초 문맥에서
필요하면 `한국어(영문)`로 쓰고 이후 한국어 표현을 사용한다.

## 5. 작업 순서

1. 대상 파일별 영어 자연어 구간과 보존 구간을 분류한다.
2. 영어 비중이 높은 설계서·계획서·가이드를 먼저 번역한다.
3. 이미 한국어인 제품 문서에서는 남은 자연어 영어만 제한적으로 번역한다.
4. 파일별 검증 후 전체 링크·식별자·추적성 검증을 수행한다.
5. 제외 파일과 범위 밖 파일이 변경되지 않았는지 확인한다.

## 6. 검증 기준

번역 완료는 다음 조건을 모두 만족해야 한다.

- 대상 파일이 strict UTF-8로 해석되고 빈 파일이 없다.
- Markdown fence가 짝을 이루고 trailing whitespace가 없다.
- 저장소 상대 Markdown 링크가 실제 파일로 해석된다.
- 코드 블록, inline code, 경로, URL, 명령, ID와 enum이 번역 전과 동일하다.
- PRD 37, ARC 14, THR 12, CTL 20, VG 24, WBS 35, RSK 14 catalog와
  RTM 연결이 유지된다.
- 제외된 실행 계약 5개에 working-tree 변경이 없다.
- 번역 대상 밖의 사용자 소유 변경을 덮어쓰지 않는다.

검증할 수 없는 항목은 성공으로 추정하지 않고 원인과 함께 `NOT_RUN`으로
보고한다.

## 7. 완료 산출물

완료 시 한국어 번역된 일반 Markdown 문서, 파일별 번역 범위 요약과 fresh
검증 결과를 제공한다. Git 커밋·푸시·PR·게시는 별도 명시적 승인 전 수행하지
않는다.
