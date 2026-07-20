# W1 Harness 기준선 인벤토리 설계

**작성일:** 2026-07-19

**상태:** 승인된 대화 설계의 서면 기록

**대상 범위:** `docs/project/wbs.md`의 W1 및 그중 첫 번째 작업인 `WBS-001`

## 1. 목적

W1의 `WBS-001`~`WBS-003`을 구현 순서와 검증 책임이 분명한 다섯 개
작업으로 나누고, 첫 번째 작업인 Harness 기준선 인벤토리의 산출물과
검증 방법을 확정한다.

현재 저장소에는 Portable Agent Harness Protocol 2.0과 Main·Part·Work
역할 프롬프트, 저장소 adapter/profile 및 적용 가이드가 존재한다. 반면
ForgeOps 제품 runtime, versioned Product Task Contract schema와 실행 가능한
Contract→TaskPacket bridge는 아직 구현 또는 검증 완료 상태가 아니다.
첫 번째 작업은 이 경계를 제3자가 파일 근거로 추적할 수 있게 만든다.

## 2. W1의 다섯 작업

| 순서 | 작업 | 원본 WBS | 완료 결과 |
| ---: | --- | --- | --- |
| 1 | Harness 기준선 인벤토리와 증빙 링크 정리 | WBS-001 | Protocol, 역할, adapter와 적용 가이드의 현재 경계 및 VG-001 검토 입력을 한 문서에서 추적할 수 있다. |
| 2 | Product Task Contract schema 정의 | WBS-002 | 원문, criterion, constraint와 source identity를 보존하는 versioned closed schema가 존재한다. |
| 3 | Contract→TaskPacket 매핑 및 non-grant 경계 정의 | WBS-002 | 제품 입력과 canonical control의 필드별 경계 및 권한 비부여 규칙이 명시된다. |
| 4 | positive/negative fixture와 VG-002 검증 | WBS-002 | 정상 보존 사례와 control 승격 거부 사례가 결정론적으로 검증된다. |
| 5 | 브리지 검토 및 공개 가능한 W1 체크포인트 작성 | WBS-003 | schema, 경계, 검토 결과와 해소되지 않은 조건을 제3자가 재검토할 수 있다. |

이 분해는 WBS의 선행 관계인 `WBS-001 → WBS-002 → WBS-003`을 유지한다.
W1의 계획 부하는 기존과 동일한 4.0 person-day이며 1.0 person-day buffer는
새 기능 범위로 전환하지 않는다.

## 3. 첫 번째 작업의 산출물

### 3.1 기준선 인벤토리

`docs/agent-harness/BASELINE_INVENTORY.md`를 새로 만든다. 이 문서는 다음을
단일 책임으로 가진다.

- Protocol 2.0의 현재 기준 파일과 책임을 링크한다.
- Main, Part, Work의 역할·변경 권한·결과 소유권 경계를 요약한다.
- root `AGENTS.md`, `.github/copilot-instructions.md`와 적용 가이드가 맡는
  adapter/profile 책임을 구분한다.
- 현재 구현된 Harness Foundation과 아직 계획 또는 명세 상태인 ForgeOps
  제품 runtime을 구분한다.
- `VG-001`에서 검토해야 할 파일 입력과 확인 관점을 식별한다.
- 문서 링크와 파일 존재는 현재 관찰 근거이지만 제품 runtime 실행,
  Phase Exit, VG 통과 또는 외부 게시 권한을 뜻하지 않음을 명시한다.

인벤토리는 비밀·자격증명·환경 파일의 내용이나 `.git` 내부 정보를 읽거나
기록하지 않는다. 근거는 프로젝트 루트 기준 상대 경로와 공개 가능한
책임 요약으로 제한한다.

### 3.2 문서 지도 연결

`docs/README.md`의 권장 읽기 순서와 문서 책임 영역에서 기준선 인벤토리를
찾을 수 있게 링크한다. 이 추가 문서는 기존 기초 문서 8개의 owner catalog를
대체하거나 새 catalog ID를 만들지 않는다.

### 3.3 WBS 상태

산출물과 검증 결과가 모두 확인된 뒤 `docs/project/wbs.md`의 `WBS-001`
상태만 `WBS_NOT_STARTED`에서 `WBS_DONE`으로 바꾼다. `WBS-002`, `WBS-003`,
`VG-001`은 실행 또는 통과한 것으로 변경하지 않는다.

## 4. 정보 구조

기준선 인벤토리는 다음 순서로 구성한다.

1. 문서 목적, 범위와 관찰 시점
2. 구현·명세·계획 상태의 의미
3. Harness Foundation 파일별 인벤토리
4. Main·Part·Work 및 adapter의 책임 경계
5. 제품 runtime과의 비구현 경계
6. VG-001 검토 입력과 기대 관찰
7. 알려진 제한과 후속 W1 연결

각 파일 행은 상대 경로, 현재 책임, 상태, 확인할 근거와 금지되는 확대
해석을 가진다. 역할 경계는 하위 문서가 상위 Protocol을 약화하지 못한다는
저장소 우선순위를 그대로 유지한다.

## 5. 데이터 및 추적 흐름

인벤토리는 다음 단방향 근거 흐름을 표현한다.

`Protocol 2.0 및 역할 프롬프트 → repository adapter/profile → 적용 가이드 → VG-001 검토 입력`

제품 요구사항과 아키텍처 문서는 이 흐름을 참조하지만 canonical Harness
control을 만들지 않는다. 후속 `WBS-002`는 인벤토리의 현재 경계를 입력으로
삼아 Product Task Contract schema와 bridge를 정의한다. `WBS-003`은 그
결과를 검토하지만 외부 게시나 publication authority를 만들지 않는다.

## 6. 불일치 처리

- 링크 대상이 없으면 검증을 실패시키고 `WBS-001`을 완료 처리하지 않는다.
- Protocol과 파생 문서 설명이 충돌하면 Protocol과 fresh repository
  observation을 보존하고 충돌을 제한 사항으로 기록한다.
- 구현 근거가 없는 제품 capability는 `SPECIFIED` 또는 `PLANNED`로 유지하고
  `IMPLEMENTED`로 올리지 않는다.
- VG 검증을 실제로 실행하지 않았으면 `PASSED`로 기록하지 않는다.
- 사용자 작업 트리의 기존 변경은 그대로 보존하며 이 설계와 직접 관련된
  새 파일 및 명시된 문서 행만 수정한다.

## 7. 검증

첫 번째 작업의 검증은 저장소 내부에서 읽기 전용 명령으로 수행한다.

1. 인벤토리에 Main, Part, Work, root adapter, Copilot adapter, Porting Guide와
   `VG-001` 입력이 모두 포함됐는지 확인한다.
2. 인벤토리가 참조하는 프로젝트 내부 상대 경로가 모두 존재하는지 확인한다.
3. Harness Foundation과 제품 runtime 경계를 나타내는 `IMPLEMENTED`,
   `SPECIFIED`, `PLANNED` 표현이 일관적인지 확인한다.
4. `docs/README.md`에서 인벤토리 링크가 해석되는지 확인한다.
5. UTF-8, Markdown 기본 구조, trailing whitespace와 파일 끝 newline을
   확인한다.
6. fresh diff를 확인해 기존 사용자 변경이 섞이거나 덮어써지지 않았는지
   검토한다.

검증 실패는 숨기지 않고 해당 항목을 수정한 뒤 같은 검사를 다시 실행한다.
검사를 실행하지 못하면 `WBS-001`은 완료 처리하지 않는다.

## 8. 범위 제외

첫 번째 작업에서는 다음을 수행하지 않는다.

- Product Task Contract 또는 TaskPacket bridge schema 구현
- positive/negative fixture 및 VG-001·VG-002 통과 선언
- runtime, API, database, queue, sandbox 또는 publisher 구현
- 외부 네트워크 호출, 게시, push, PR 또는 메시지 전송
- credential, private data, protected resource 접근
- Git commit 또는 기존 사용자 변경 정리

## 9. 완료 기준

첫 번째 작업은 다음 조건이 모두 충족될 때 완료된다.

- 기준선 인벤토리가 Protocol 2.0, Main·Part·Work, adapter와 적용 가이드를
  정확한 저장소 링크로 연결한다.
- 현재 Harness Foundation과 계획된 ForgeOps 제품 runtime이 혼동되지 않는다.
- VG-001 검토 입력과 아직 검증되지 않은 상태가 명시된다.
- 문서 지도에서 인벤토리를 찾을 수 있다.
- fresh 검증 명령과 diff 검토가 성공한다.
- `WBS-001`만 `WBS_DONE`으로 갱신되고 후속 WBS와 VG 상태는 바뀌지 않는다.
