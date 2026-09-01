# GeekMagic Conductor Desk Hub

[English](README.md) | 한국어

> 이 문서는 [`README.md`](README.md)의 한국어 번역본입니다. 내용이 서로
> 다를 경우 영문 원문을 기준으로 합니다.

[![CI](https://github.com/yoo0926/smalltv-agent-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/yoo0926/smalltv-agent-hub/actions/workflows/ci.yml)

Claude Code와 Codex를 실행하는 Conductor 세션을 위한 로컬 전용 상태
브리지입니다. 서비스 인증 정보는 Mac에만 보관하고, 개인정보를 최소화한
작업 상태만 Wi-Fi를 통해 커스텀 SmallTV Pro 펌웨어로 전송합니다.

## 현재 지원 기능

- Claude Code 상태: `working`, `needs_input`, `done`, `failed`, `idle`
- Codex 상태: `working`, `needs_input`, `done`, `idle`. `~/.codex/hooks.json`에
  설치한 훅으로 받고, 공식 `agent-turn-complete` 알림도 턴 완료 경로로 함께 유지합니다
- `CONDUCTOR_IS_LOCAL=1`을 이용한 로컬 Conductor 세션 전용 필터링
- 개인정보를 최소화한 오프라인 큐와 브리지 시작 시 자동 재전송
- 외부 의존성 없는 Python 서비스, 로컬 상태 저장
- `POST /api/agents` 비동기 전송과 `POST /api/notify`를 통한 전체 화면
  `done` / `needs_input` 알림
- 기기 화면 자체의 기능 — 앱 메뉴, Settings 카드, 날씨, 티커, 반응형 Agent Hub
  레이아웃 — 은 [`firmware/smalltv-agent-hub/AGENT_HUB.md`](firmware/smalltv-agent-hub/AGENT_HUB.md)에
  설명되어 있습니다

`TaskCompleted`는 하위 작업이나 팀원의 작업 완료를 의미할 수 있으므로
Claude 주 세션의 종료가 아니라 진행 상태로 처리합니다. Claude의 `Stop`
훅을 한 차례 작업 완료를 판단하는 기준 이벤트로 사용하며, 세션을 완전히
닫는 이벤트는 `SessionEnd`뿐입니다.

`Stop`은 세션이 아니라 한 차례 작업의 끝을 뜻합니다. 그래서 권한 승인처럼
새 프롬프트 없이 작업이 재개되면 다음 턴이 끝날 때까지 직전 상태가 그대로
남습니다. 빈도를 제한한 `PostToolUse` 훅으로 이 구간을 메울 수 있고 구현도
되어 있지만 기본 설치하지 않습니다. 훅 프로세스가 도구 호출마다 시작되어
매번 약 80ms가 들기 때문입니다. 켜는 방법은
[`scripts/install_hooks.py`](scripts/install_hooks.py)의 `CLAUDE_EVENTS` 위
주석을 참고하세요.

화면에서 워크스페이스는 하나의 상태로 말합니다. 그 안의 세션 중
`needs_input`이 `failed`보다, `failed`가 `working`보다, `working`이 `done`보다
우선합니다. 따라서 같은 워크스페이스에서 다른 세션이 아직 돌고 있으면
`done` 알림을 띄우지 않고, 끝난 작업은 10분 뒤 화면에서 사라집니다.

각 행의 이름은 `CONDUCTOR_WORKSPACE_NAME`이 아니라 Git 브랜치에서 가져옵니다.
Conductor는 세션을 시작할 때 이 환경변수를 프로세스에 고정하므로, 세션을 연
뒤에 워크스페이스 이름을 바꾸면 새 세션이 열릴 때까지 생성 당시의 코드네임을
계속 알립니다. 브랜치는 이벤트마다 다시 읽고, Conductor의 워크스페이스 이름
자체도 브랜치에서 파생됩니다. 브랜치의 타입 접두사는 제거하므로
`fix/public-error-user-agent`는 `public-error-user-agent`로 표시됩니다.
`main`이나 `master`처럼 특정 작업을 가리키지 않는 브랜치는 워크스페이스
이름에, 그마저 없으면 에이전트 종류에 자리를 넘깁니다. 펌웨어 버퍼 때문에
레이아웃에 담기지 않는 이름은 뒤가 아니라 가운데를 생략합니다. 브랜치는
앞쪽이 무엇인지 알려주고 뒤쪽이 형제 브랜치와 구분해 주기 때문입니다.
`verify-local-agent-hub-status`와 `-v1` 변형은 각각 `verify-..status`,
`verify-..tus-v1`이 됩니다. 글자 예산은 행 개수가 고르는 레이아웃을 따르며
펌웨어와 같은 값을 씁니다. 한 행이면 19자, 카드 두 장이면 15자, 세네 행이면
16자, 알림 화면은 20자입니다.

프롬프트와 응답 내용은 상태 파일이나 오프라인 큐에 저장하지 않습니다.
화면 API에는 `Working`, `Permission required`, `Turn complete` 같은 짧은
상태 메시지만 전송합니다.

## 새 Mac 설정

개발 권장 버전은 Python 3.14.7이며, 브리지는 Python 3.9 이상에서도
테스트됩니다. 새로 복제한 저장소에서 아래 한 번의 명령으로 로컬 도구를
설치하고, 모든 테스트를 실행하고, SmallTV Pro 펌웨어를 빌드할 수 있습니다.

```bash
./scripts/bootstrap_macos.sh --build
```

빌드 단계는 Claude, Codex 또는 launchd 설정을 변경하지 않습니다. 두 번째
단계에서 이 Mac을 대화형으로 설정합니다.

```bash
./scripts/setup_macos.sh
```

setup은 Claude 훅, Codex 알림, 사용자 로그인 서비스의 설치 여부를 묻고,
서비스를 설치할 때 SmallTV 주소를 입력받습니다. 대괄호 안의 값을 그대로
사용하려면 Enter를 누르면 됩니다. 첫 실행의 답은 Git에서 제외되는 `.env`에
저장되고 다음 실행부터 기본값으로 표시됩니다. 공개 가능한 초기 기본값은
[`.env.example`](.env.example)에 있으며, 개인 기기 주소는 대상 Mac에서
입력하기 전까지 의도적으로 비워 둡니다.

로컬 기본값은 다음 네 가지입니다.

- `DESK_HUB_DEVICE_URL`: SmallTV 기본 주소
- `DESK_HUB_INSTALL_CLAUDE`: Claude Code 훅 설치 또는 갱신 여부
- `DESK_HUB_INSTALL_CODEX`: Codex 알림 설치 또는 갱신 여부
- `DESK_HUB_INSTALL_SERVICE`: macOS 로그인 서비스 설치 및 시작 여부

세 설치 항목의 값에는 `true` 또는 `false`를 사용합니다.

자동화된 설치에서는 `.env`를 편집한 뒤
`./scripts/setup_macos.sh --non-interactive`를 실행할 수 있습니다. 저장이나
실제 설치 없이 확인하려면 `--dry-run`을 사용하세요.

기존 설치를 다른 Mac으로 옮길 때는 [Mac 이전 가이드](MIGRATION.ko.md)를
참고하세요. Git에 저장하지 않는 기기 내부 데이터와 Mac 로컬 데이터의
전체 목록도 포함되어 있습니다.

## 브리지 실행

```bash
./bin/desk-hub
```

다른 터미널에서 데모 이벤트를 전송하고 상태를 확인할 수 있습니다.

```bash
./bin/desk-hub-demo
curl http://127.0.0.1:4747/api/v1/status
```

브리지의 로컬 상태 확인 엔드포인트는 다음과 같습니다.

```text
GET /api/v1/status
```

SmallTV가 Mac에서 데이터를 가져오는 구조가 아니라, 브리지가 기기로
데이터를 전송하는 구조입니다. 따라서 로컬 HTTP 서버는 안전하게
`127.0.0.1`에만 바인딩됩니다. 기기 주소를 지정하려면 다음과 같이
실행합니다.

```bash
./bin/desk-hub --device-url http://DEVICE_IP
```

화면에는 에이전트 종류, 짧은 워크스페이스 이름, 작업 상태만 전송합니다.
이 이름은 브랜치 이름이므로 브랜치 이름은 책상에서 보인다고 가정하세요.
브랜치의 타입 접두사는 제거되고, 나머지는 출력 가능한 ASCII로 바뀐 뒤
레이아웃 예산에 맞게 줄어듭니다. 프롬프트, 응답, 파일 경로와 서비스 인증 정보는 Mac에 남습니다.

펌웨어의 선택적 웹 비밀번호를 켜면 `/api/agents`와 `/api/notify`도
보호됩니다. **꺼두세요.** 브리지는 인증 정보를 보내지 않으므로, 켜면 기기가
모든 전송을 거부합니다.

현재 SmallTV Pro 빌드에는 Agent Hub, Ticker, Clawdmeter, Weather,
Home Assistant, Carousel이 포함됩니다. 데스크용 날씨 화면의 공간을
확보하기 위해 upstream의 Plane Radar 화면은 의도적으로 제외했습니다.

## 고급: 로컬 에이전트 훅만 수동으로 설치

일반적인 설치에는 위의 대화형 setup을 사용하세요. 아래 저수준 명령은 훅
설정만 미리 확인하거나 복구할 때 사용합니다.

먼저 파일을 변경하지 않는 미리보기를 실행합니다.

```bash
python3 scripts/install_hooks.py
```

그다음 로컬 Claude Code와 Codex 세션용 전역 훅을 설치합니다.

```bash
python3 scripts/install_hooks.py --apply
```

설치 프로그램은 다음 작업을 수행합니다.

- 다른 훅을 제거하지 않고 `~/.claude/settings.json`에 desk-hub 항목 병합
- 저장소 위치가 바뀌었을 때 이전 절대 경로의 desk-hub 훅 갱신
- `~/.claude/settings.json`, `~/.codex/config.toml`, `~/.codex/hooks.json`을
  쓰기 전에 백업
- 다른 도구의 항목은 그대로 두고 `~/.codex/hooks.json`에 desk-hub 훅만 병합
- 프로젝트 단위 Codex 설정에서는 `notify`를 지정할 수 없으므로 사용자
  단위 Codex `notify` 명령 갱신
- 기존 Codex 알림 명령을 기록하고 원래 JSON을 그대로 전달

설치 후에는 Conductor에서 Claude/Codex 세션을 새로 시작하세요. 기존
세션은 훅 설치 전에 설정을 이미 읽었을 수 있습니다.

기본적으로 훅은 Conductor 외부 세션을 무시합니다. Conductor는 로컬
에이전트에 `CONDUCTOR_IS_LOCAL=1`, `CONDUCTOR_WORKSPACE_NAME`,
`CONDUCTOR_WORKSPACE_PATH`를 제공하므로 일반 터미널 세션을 화면에 섞지
않고 같은 전역 훅을 사용할 수 있습니다. 모든 로컬 Claude/Codex 세션을
의도적으로 모니터링할 때만 `DESK_HUB_CONDUCTOR_ONLY=0`을 설정하세요.

## 고급: macOS 로그인 서비스만 수동으로 관리

대화형 setup에서 해당 항목을 선택하면 이 서비스가 설치됩니다. 아래 명령은
로그인 서비스만 확인하거나 재설치 또는 제거할 때 사용합니다.

사용자 단위 LaunchAgent 설치 내용을 파일 변경 없이 확인합니다.

```bash
python3 scripts/install_launch_agent.py
```

설치하고 바로 시작하려면 다음을 실행합니다.

```bash
python3 scripts/install_launch_agent.py --device-url http://DEVICE_IP --apply
```

로그인 시 자동 실행되고, 비정상 종료 후 다시 시작되며, 로그는
`.runtime/` 아래에 기록됩니다. 제거하려면 다음을 실행합니다.

```bash
python3 scripts/install_launch_agent.py --uninstall --apply
```

## 로컬 Conductor 검증

1. `./bin/desk-hub`를 실행합니다.
2. Conductor 워크스페이스에서 새 Claude Code 세션을 엽니다.
3. 프롬프트를 전송하고 완료를 기다린 뒤 권한 요청을 한 번 발생시킵니다.
4. `http://127.0.0.1:4747/api/v1/status`를 확인합니다.
5. Conductor에서 새 Codex 세션을 열고 한 차례 작업을 완료합니다.
6. 반환된 `cwd`, 워크스페이스 이름과 브랜치가 올바른 Conductor
   worktree를 가리키는지 확인합니다. 화면에 도달하는 값은 브랜치이므로
   기기에 표시된 이름과 대조하세요.

Conductor가 관리하는 Claude/Codex 실행 파일이 `~/.claude` 또는
`~/.codex`와 다른 격리된 홈을 사용한다면, 해당 실행 환경이 시스템 실행
파일을 사용하게 하거나 실제 설정 홈에도 같은 훅을 설치하세요. 이벤트
엔드포인트와 펌웨어 프로토콜은 바뀌지 않습니다.

## 저장소 구성

- `src/`, `bin/`, `scripts/`: macOS 브리지, 이벤트 훅, 설치 프로그램
- `tests/`: 개인정보 보호, 수명주기, 훅 설치, LaunchAgent 테스트
- `firmware/smalltv-agent-hub/`: SmallTV Pro 펌웨어 포크와 에이전트 화면
- `.github/workflows/ci.yml`: Python 테스트, 저장소 검사와 재현 가능한
  SmallTV Pro 빌드 산출물을 만드는 루트 CI

로컬 실행 상태, 기기 설정, stock 펌웨어 백업, 내려받은 참고 저장소,
빌드 도구와 컴파일된 펌웨어 이미지는 의도적으로 버전 관리에서 제외합니다.

변경 사항을 제출하기 전에 [`CONTRIBUTING.md`](CONTRIBUTING.md)를
확인하세요. 개인정보 보호 규칙은 이슈 로그, 스크린샷과 테스트 fixture에도
동일하게 적용됩니다.

릴리스 변경 사항은 [`CHANGELOG.md`](CHANGELOG.md), 소스 기반 릴리스
절차는 [`RELEASING.md`](RELEASING.md)에 기록되어 있습니다.

## 라이선스와 upstream 표기

Mac 브리지와 저장소 단위 작업은 [MIT License](LICENSE)로 제공합니다.
펌웨어는 [giovi321/smalltv-mod](https://github.com/giovi321/smalltv-mod)에서
파생되었으며
[`firmware/smalltv-agent-hub/LICENSE`](firmware/smalltv-agent-hub/LICENSE)의
WTFPL v2 라이선스를 유지합니다. 가져온 revision과 표기는
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)를 참고하세요.

보안 문제는 [`SECURITY.md`](SECURITY.md)의 절차에 따라 신고해야 합니다.
