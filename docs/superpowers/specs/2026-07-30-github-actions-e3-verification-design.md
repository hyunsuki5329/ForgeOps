# GitHub Actions 2-job E3 검증 설계

## 목적

ForgeOps VG-008의 현재 `SANDBOX_RUNTIME_UNAVAILABLE` 차단을 GitHub-hosted Linux runner에서 해소한다. 장기 비밀키나 별도 검증 서버 없이 GitHub OIDC와 Cosign keyless 서명을 사용하며, 검증 조건이 하나라도 불명확하면 기존처럼 `NOT_RUN` 또는 `FAILED`로 닫는다.

이 설계는 W4의 VG-008만 다룬다. 애플리케이션 배포, 일반 CI 교체, 이미지 공개, 자동 커밋, PR 생성은 범위에 포함하지 않는다.

## 선택한 접근

하나의 수동 실행 workflow 안에 서로 다른 GitHub-hosted `ubuntu-latest` job 두 개를 둔다.

1. `build-sign`: 이미지를 빌드하고 GHCR에 digest로 push한 뒤 GitHub OIDC로 Cosign keyless 서명한다.
2. `verify-e3`: 새로운 runner에서 서명을 독립 확인하고 rootless Docker로 고정 probe를 실행한 뒤 서명된 E3 증빙을 만든다.

기본 Docker를 사용하는 단일 job은 더 짧지만 rootless·독립 검증 경계를 충족하지 못하므로 채택하지 않는다. 별도 verifier 서비스는 더 강한 분리를 제공하지만 운영 부담 때문에 현재 범위에서는 제외한다.

## 신뢰 경계

- workflow는 `workflow_dispatch`로만 실행하며 저장소 기본 브랜치에 병합된 workflow 파일만 E3 발급자로 인정한다. 따라서 구현 파일을 로컬에 작성하는 것만으로는 외부 E3가 활성화되지 않으며, 기본 브랜치 반영은 사용자가 별도로 결정한다.
- 두 job은 `github.ref == refs/heads/<default_branch>`와 `github.ref_protected == true`를 선행 확인한다. 불일치하면 이미지 빌드나 runtime provisioning 전에 중단한다.
- GitHub OIDC issuer는 `https://token.actions.githubusercontent.com`로 고정한다.
- Cosign 인증서 identity는 `https://github.com/<owner>/<repo>/.github/workflows/vg-008-e3.yml@refs/heads/<default_branch>`의 정확한 값으로 고정한다. owner, repository, default branch는 workflow event의 저장소 metadata에서 얻고 빈 값이나 형식 불일치를 거부한다.
- 이미지 이름은 workflow에서 계산한 단일 GHCR 경로만 허용하고, 실행은 tag가 아니라 `name@sha256:<digest>`만 허용한다.
- 외부 Action은 릴리스 tag가 아니라 검토된 commit SHA로 고정한다.
- 대상 source와 verifier/workflow identity를 분리해 기록한다. PR 또는 임의 branch가 workflow나 verifier를 바꾸어 스스로 E3를 발급할 수 없다.

## 권한

workflow 최상위 기본 권한은 비활성화하고 job별 최소 권한만 부여한다.

- `build-sign`: `contents: read`, `packages: write`, `id-token: write`
- `verify-e3`: `contents: read`, `packages: read`, `id-token: write`, `actions: write`는 사용하지 않음
- 장기 Cosign private key, PAT, cloud credential은 만들지 않는다.
- `GITHUB_TOKEN`은 GHCR push/pull에만 사용한다.
- GHCR package의 visibility는 변경하지 않으며 공개 전환을 시도하지 않는다. 현재 저장소 token으로 private package를 사용할 수 없으면 권한을 넓히지 않고 실패한다.

## Job 1: build-sign

1. 보호된 기본 브랜치와 workflow identity를 확인한다.
2. repository source를 exact commit SHA로 checkout한다.
3. 고정된 Dockerfile로 최소 E3 probe image를 빌드한다.
4. GHCR에 push하고 registry가 반환한 digest를 기록한다.
5. Cosign keyless로 정확한 digest reference를 서명한다.
6. `image_ref`, `image_digest`, source SHA, workflow ref/SHA만 다음 job output으로 전달한다. tag는 실행 입력으로 전달하지 않는다.

서명 또는 digest 획득 실패 시 `verify-e3`는 실행되지 않으며 VG-008 pass 증빙도 생성되지 않는다.

## Job 2: verify-e3

새 GitHub-hosted runner에서 다음 순서로 수행한다.

1. workflow/ref/repository identity와 Job 1의 digest 출력 형식을 다시 검증한다.
2. Cosign으로 digest signature를 확인한다. exact certificate identity와 GitHub OIDC issuer가 일치해야 한다.
3. rootless Docker 구성 요소를 설치하고 사용자 daemon을 시작한다.
4. `docker info`의 rootless security option, daemon socket 위치, cgroup/quota 지원을 관찰한다.
5. digest image를 pull하고 local inspect digest가 Job 1 digest와 같은지 확인한다.
6. repository의 일반 evaluator 프로세스와 분리된 helper process가 고정 probe catalog를 실행한다. helper 경로와 SHA-256은 workflow가 고정하고 caller 입력으로 바꿀 수 없다.
7. 별도 attestation verifier process가 helper 출력의 closed schema, input hash, effect count와 residue를 검증하고 `e3-attestation.json`을 만든다.
8. attestation을 keyless `sign-blob` bundle로 서명한 뒤, ForgeOps importer가 그 bundle을 다시 검증하여 runtime profile을 생성한다.
9. 같은 runner에서 기존 VG-008 세 command와 Phase 0 aggregator를 즉시 실행해 freshness window 안의 result/report를 생성하고 GitHub Actions artifact로 업로드한다.

rootless 설치, cgroup/quota, 서명, issuer, identity, digest 또는 cleanup 관찰이 하나라도 불확실하면 pass 증빙을 만들지 않는다. runtime capability 부재는 `available=false`와 stable `NOT_RUN` code로, 실제 probe 위반은 stable `FAILED` code로 닫는다. GitHub-hosted runner에서 rootless Docker가 항상 제공된다고 가정하지 않는다.

## 고정 runtime probe

helper는 caller가 임의 command/flag를 전달할 수 없는 고정 probe만 지원한다.

- provenance: signed digest positive와 tag/signature/issuer negative preflight
- containment: non-root UID, read-only rootfs, capability drop ALL, no-new-privileges, 금지 mount/device/socket 없음
- egress: `--internal` network의 exact local proxy만 허용하고 direct DNS/socket, redirect, loopback/private/metadata 목적지 시도를 거부
- quota: PID, memory, CPU, writable tmpfs 한계를 관찰하고 escape를 실패로 기록
- teardown: container, network, mount, lease, transient file/workspace를 제거한 뒤 두 번째 관찰에서 모두 0인지 확인

위험한 negative flag를 실제로 실행해 host를 노출하지 않는다. helper allowlist가 provisioning 전에 거부하고 effect count 0을 기록한다.

## E3 증빙 계약

`e3-attestation.json`은 다음 공개 필드만 가진다.

- schema/version과 command identity
- repository ID, workflow ref/SHA, run ID/attempt
- source commit SHA
- exact image digest
- Cosign issuer와 certificate identity
- rootless/cgroup capability 관찰
- probe별 status와 effect/residue counters
- schema, suite, runtime profile, helper의 SHA-256
- strict UTC `observed_at`

raw Docker output, environment, token, certificate 원문, host absolute path, container log, source payload는 포함하지 않는다. Job 2는 이 JSON을 Cosign `sign-blob` keyless bundle로 서명한다. importer는 bundle, issuer, workflow identity, subject hash를 다시 확인한 뒤에만 `evidence_kind=runtime`으로 변환한다.

## ForgeOps 연동

- `.github/workflows/vg-008-e3.yml`: 두 job orchestration
- 고정 probe Dockerfile과 probe entrypoint
- 독립 helper executable/script와 closed attestation schema
- attestation importer: 서명 bundle과 identity를 확인해 `artifacts/runtime/sandbox-runtime-profile.json`을 생성
- 기존 `tools/sandbox_security/verify.py`: verified external attestation reference가 있을 때만 세 VG-008 command를 실행
- 기존 `tools/phase_exit/verify.py`: 18개 결과를 재집계

workflow는 repository 파일을 자동 커밋하지 않는다. 결과는 `forgeops-e3-evidence-<run_id>-<run_attempt>` Actions artifact로 업로드하며 signed attestation, Cosign bundle, runtime profile, VG-008 세 result, Phase 0 result/report와 공개 manifest만 포함한다.

GitHub runner에서 생성한 Phase 0 결과가 해당 실행의 authoritative fresh evidence다. 로컬 반영 도구는 artifact의 manifest·bundle·identity·hash를 검증해 파일을 명시적으로 가져오되, 다운로드 시점이 기존 300초 freshness window를 벗어났다면 새 실행 결과로 재생하거나 `READY`를 다시 선언하지 않는다. 이 경우 immutable GitHub run/artifact reference만 보존하고 fresh 재검증은 workflow를 다시 실행한다.

## 오류 처리

- build/sign 실패: Job 2 미실행, E3 없음
- signature/identity/digest 불일치: provisioning 전 실패
- rootless 또는 quota capability 없음: closed `NOT_RUN`
- probe 위반: closed `FAILED`
- teardown 불확실: `SANDBOX_TEARDOWN_INCOMPLETE`, Phase 0 차단
- artifact/schema/signature import 실패: 기존 `available=false` profile을 보존하고 pass 결과를 쓰지 않음
- artifact 다운로드가 freshness window를 넘김: 과거 signed evidence로만 보존하고 fresh `READY`로 승격하지 않음

모든 실패는 exception text나 raw command output 대신 stable public code로 기록한다.

## 테스트와 완료 조건

로컬 테스트는 workflow/action pin, 최소 권한, exact identity, digest-only 실행, closed schema, importer negative case를 검증한다. GitHub 실행에서는 다음을 모두 만족해야 한다.

- Job 1 image signature와 Job 2 verification identity가 일치
- rootless Docker와 필요한 quota capability가 관찰됨
- VG-008 세 command가 E3 `PASSED`
- negative provisioning effects와 terminal residue가 모두 0
- Phase 0 aggregation이 18/18 `PASSED`, blockers 0, `READY`
- 외부 보관 artifact에 금지 정보가 없음
- workflow의 실패 경로에서 pass artifact나 `READY` manifest가 생성되지 않음

## 승인 묶음

구현 파일 작성과 로컬 unit test에는 추가 승인이 필요하지 않다. 실제 외부 실행 전에 다음을 한 번에 승인받는다.

- GitHub Actions workflow 실행
- GitHub OIDC token 발급
- GHCR image push/pull 및 Cosign signature/attestation 저장
- Sigstore Fulcio/Rekor와 GitHub/GHCR 네트워크 접근
- Actions artifact 업로드와 이후 다운로드

승인에는 자동 커밋, push, PR, release, deployment, 일반 외부 메시지, 장기 credential 생성은 포함하지 않는다.

## 참고

- GitHub OIDC reference: https://docs.github.com/en/actions/reference/security/oidc
- GitHub Docker image publishing: https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images
- Docker rootless mode: https://docs.docker.com/engine/security/rootless/
- Docker rootless resource limits: https://docs.docker.com/engine/security/rootless/tips/#limiting-resources
- Sigstore Cosign installer: https://github.com/sigstore/cosign-installer
- Cosign keyless verification: https://docs.sigstore.dev/cosign/verifying/verify/
