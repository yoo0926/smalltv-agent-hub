# 다른 Mac으로 Desk Hub 이전하기

[English](MIGRATION.md) | 한국어

> 이 문서는 [`MIGRATION.md`](MIGRATION.md)의 한국어 번역본입니다. 내용이
> 서로 다를 경우 영문 원문을 기준으로 합니다.

Git 저장소에는 브리지와 SmallTV Pro 펌웨어를 다시 빌드하는 데 필요한
모든 파일이 들어 있습니다. 실행 상태, 기기 설정, 인증 정보, 내려받은
참고 자료와 빌드 결과는 의도적으로 로컬에만 보관합니다.

## 새로 복제하기

Git과 Python 3.9 이상을 설치하세요. 권장 및 테스트 버전은
`.python-version`에 기록된 Python 3.14.7입니다.

```bash
git clone https://github.com/yoo0926/smalltv-agent-hub.git
cd smalltv-agent-hub
./scripts/bootstrap_macos.sh --build
```

부트스트랩은 프로젝트 전용 가상환경을 만들고,
`requirements-dev.txt`에 고정된 PlatformIO 버전을 설치하고, 생성된 웹
UI를 검증하고, 브리지 테스트를 실행하고, SmallTV Pro 이미지를
빌드합니다. Claude, Codex 또는 launchd 설정은 변경하지 않습니다.

Mac과 SmallTV가 같은 네트워크에 연결되면 알림 훅과 로그인 서비스를
설치합니다. 네트워크에서 안정적으로 동작한다면 기기의 mDNS 이름을
권장하며, 그렇지 않으면 현재 IP 주소를 사용하세요.

```bash
./scripts/setup_macos.sh
```

대화형 setup은 기본값을 대괄호 안에 표시합니다. 첫 실행에서 기기 주소와
설치 선택을 Git에서 제외되는 `.env`에 기록하므로, 다음부터는 Enter를 눌러
그대로 사용할 수 있습니다. 저장소의 `.env.example`에는 공개 가능한
기본값만 있고 Mac별 기기 주소는 포함하지 않습니다.

훅 설치 프로그램은 기존 Claude 훅을 보존해 병합하고 기존 Codex 알림
명령을 연쇄 실행합니다. 이전 desk-hub 설치도 인식하여 저장소 위치가
바뀌면 절대 경로를 갱신합니다. 실제 변경 전에 기존 설정 파일을
백업합니다.

## 로컬에 남는 데이터

| 데이터 | 위치 | 옮겨야 하나요? |
| --- | --- | --- |
| 에이전트 기록, 세션 ID, worktree 경로, 로그 | `.runtime/` | 아니요. 일시적인 데이터이며 비공개 프로젝트 메타데이터가 포함될 수 있습니다. |
| Codex 알림 전달 상태 | `.runtime/codex-forward.json` | 아니요. 대화형 setup을 다시 실행하세요. |
| 대화형 setup 기본값 | `.env` | 일반적으로 아니요. 새 Mac에 맞는 기기 주소와 설치 항목을 setup에서 다시 선택하세요. |
| Python과 PlatformIO 환경 | `firmware/smalltv-agent-hub/.venv`, `.pio-core`, `.pio` | 아니요. 부트스트랩이 다시 생성합니다. |
| 참고 저장소와 임시 파일 | `references/`, `tmp/` | 아니요. 프로젝트 입력이 아닌 조사·빌드 자료입니다. |
| 컴파일된 펌웨어 | `dist/`와 `*.bin` | 아니요. 다시 빌드하거나 CI/릴리스 산출물을 받으세요. |
| Claude와 Codex 훅 | `~/.claude/settings.json`, `~/.codex/config.toml` | 전체 파일을 복사하지 마세요. 대화형 setup이 다른 설정을 보존하면서 훅을 병합합니다. |
| 로그인 서비스 | `~/Library/LaunchAgents/com.geekmagic.desk-hub.plist` | 아니요. 대화형 setup이 새 저장소 경로와 기기 주소로 다시 생성합니다. |
| Wi-Fi, 티커, 날씨, 화면, 웹 인증 설정 | SmallTV 플래시 | 같은 기기에는 그대로 남습니다. 새 기기나 초기화한 기기에서만 웹 UI로 다시 설정하세요. |
| stock 펌웨어 백업 | 별도의 로컬 백업 폴더 | 절대 커밋하거나 공개하지 마세요. 포함된 Wi-Fi 또는 인증 데이터는 인증 정보로 취급하세요. |

같은 SmallTV를 계속 사용한다면 기기 설정을 복사할 필요가 없습니다. 해당
값은 기기에 저장됩니다. 저장소에는 Wi-Fi 비밀번호, GitHub 토큰, Slack
인증 정보나 Conductor 프로젝트 내용이 필요하지 않습니다.

## 새 Mac 검증

훅을 설치한 다음 Conductor 세션을 새로 시작하고 다음을 확인합니다.

```bash
curl http://127.0.0.1:4747/api/v1/status
launchctl print gui/$(id -u)/com.geekmagic.desk-hub
tail -n 50 .runtime/desk-hub.stderr.log
```

로컬 Conductor 워크스페이스에서 Claude 프롬프트를 전송하고, 짧은
워크스페이스 이름과 작업 상태가 화면에 나타나는지 확인하세요. 서비스는
실행 중인데 화면이 갱신되지 않는다면 같은 Mac에서 기기 URL을 열어보고,
올바른 URL로 LaunchAgent를 다시 설치하세요.

작업 트리를 공개하거나 다른 곳으로 옮기기 전에는 다음을 실행합니다.

```bash
python3 scripts/check_repository_hygiene.py
git status --short --ignored
```

첫 번째 명령은 버전 관리 중인 실행·빌드 폴더, 펌웨어 바이너리, macOS 홈
절대 경로와 몇 가지 일반적인 토큰 형식을 차단합니다. 두 번째 명령은
펌웨어 문서에서는 유효하지만 개인 정보가 될 수 있는 기기 주소를 포함해
로컬 전용 파일을 사람이 마지막으로 확인하기 위한 명령입니다.
