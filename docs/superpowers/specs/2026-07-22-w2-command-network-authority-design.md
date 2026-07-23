# W2-4 COMMAND·NETWORK exact authority 설계

**작성일:** 2026-07-22  
**상태:** 사용자 승인 설계  
**범위:** `WBS-005`의 COMMAND·NETWORK policy와 `VG-006`

## 1. 목적

COMMAND와 NETWORK는 사람이 읽기에 비슷한 문자열이 아니라 canonical closed
identity의 exact match로만 허용한다. 이 설계는 실제 command·socket을 실행하지
않는 preflight fixture로 raw command, normalization, redirect inheritance,
SSRF 목적지 우회를 effect 전에 차단한다.

## 2. COMMAND 규칙

COMMAND는 `NAMED_COMMANDS`와 trusted validation record의 `id`, `command`,
canonical root-relative `cwd`가 case-sensitive exact 일치할 때만 허용한다.
raw shell, project-wide execute, trim, case folding, whitespace rewrite, profile
밖 command와 inferred cwd는 허용하지 않는다. candidate의 command identity는
하나의 named record를 정확히 가리켜야 한다.

## 3. NETWORK 규칙

NETWORK는 lower-case ASCII DNS `host[:port]` literal과 `NAMED_HOSTS` exact
membership을 요구한다. scheme, path, query, fragment, userinfo, whitespace,
uppercase, wildcard, default-port expansion, trim·rewrite를 허용하지 않는다.
redirect는 원래 host authority를 상속하지 않으며 새 destination은 독립된
NETWORK action으로 재검사한다. canonical identity를 통과해도 loopback,
private, link-local, metadata destination은 destination-safety gate에서
거부한다.

## 4. 구성과 데이터 흐름

W2-3의 `forgeops-authority-policy` envelope에 COMMAND 또는 NETWORK action
identity를 넣어 사용한다. `fixtures/forgeops-authority-command-network/suite.json`은
trusted command catalog와 named host catalog를 public-safe literal로 제공한다.
`tools/policy_contract/verify.py command-network`는 identity schema → scope/list
shape → exact trusted membership → capability/candidate/revision → network
destination safety 순서로 판정한다.

`tests/policy_contract/test_command_network.py`는 fixture catalog의 변조,
stable error priority, dispatcher/network adapter가 negative case에서 호출되지
않는지를 검증한다. result artifact에는 command text나 host 이외의 raw request,
output, header, credential을 기록하지 않는다.

## 5. 오류와 fixture

stable category는 `COMMAND_SCHEMA_INVALID`, `COMMAND_SCOPE_INVALID`,
`COMMAND_RAW_FORBIDDEN`, `COMMAND_IDENTITY_MISMATCH`,
`NETWORK_SCHEMA_INVALID`, `NETWORK_SCOPE_INVALID`,
`NETWORK_IDENTITY_INVALID`, `NETWORK_EXACT_MATCH_REQUIRED`,
`NETWORK_DESTINATION_FORBIDDEN`, `AUTHORITY_CAPABILITY_DENIED`를 사용한다.

fixture는 valid named command triple, id/command/cwd 각각의 mismatch, raw
command, `PROJECT` execute, named host normal case, uppercase·scheme·path·query·
userinfo·wildcard·default port·whitespace, redirect inheritance, localhost,
private/link-local/metadata address, missing/UNKNOWN capability를 포함한다.

## 6. 검증과 범위 제외

`command-network-negative`는 E2 safe result JSON을 생성하며 실제 process,
DNS lookup, HTTP 요청, redirect follow를 수행하지 않는다. proxy, egress
runtime, DNS rebinding 방어와 sandbox network isolation의 실제 집행은 WBS-010과
후속 integration의 범위다.
