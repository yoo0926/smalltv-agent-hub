# GeekMagic Conductor Desk Hub

[English](README.md) | [한국어](README.ko.md)

[![CI](https://github.com/yoo0926/smalltv-agent-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/yoo0926/smalltv-agent-hub/actions/workflows/ci.yml)

Local-only status bridge for Conductor sessions running Claude Code and Codex. The bridge keeps service credentials on the Mac and pushes a privacy-minimized task snapshot to the custom SmallTV Pro firmware over Wi-Fi.

## Current capabilities

- Claude Code: `working`, `needs_input`, `done`, `failed`, and `idle`
- Codex: `working`, `needs_input`, `done`, and `idle`, from hooks in `~/.codex/hooks.json`, with the official `agent-turn-complete` notification kept as a second turn-complete path
- Local-Conductor-only filtering through `CONDUCTOR_IS_LOCAL=1`
- Privacy-minimized offline queue with automatic replay on bridge startup
- Dependency-free Python service with persisted local state
- Asynchronous push to `POST /api/agents`, plus full-screen `done` / `needs_input` alerts through `POST /api/notify`
- What the device itself shows — the app menu, the Settings card, weather, tickers, and the adaptive Agent Hub layout — is described in [`firmware/smalltv-agent-hub/AGENT_HUB.md`](firmware/smalltv-agent-hub/AGENT_HUB.md)

`TaskCompleted` is treated as progress rather than ending the main Claude session, because it can refer to a subtask or teammate. The Claude `Stop` hook is the authoritative turn-complete event, and only `SessionEnd` closes a session for good.

`Stop` ends a turn rather than the session, so a session that resumes without a new prompt — after a permission grant, for example — keeps showing its last state until the next turn ends. A throttled `PostToolUse` hook would close that gap; it is implemented but deliberately not installed, for the reason recorded above `CLAUDE_EVENTS` in [`scripts/install_hooks.py`](scripts/install_hooks.py).

A workspace speaks with one voice on the display. Only the newest session of each kind counts, so a restarted Claude replaces the one it succeeded while Claude and Codex each keep a voice; among those, `needs_input` outranks `failed`, which outranks `working`, which outranks `done`. The same ranking decides which workspaces reach the four rows and the order they appear in, so one waiting for you is never crowded out by busier ones. A `done` alert is suppressed while another session in the workspace is still running, and finished work leaves the display after ten minutes.

A row is named after its git branch, not `CONDUCTOR_WORKSPACE_NAME`: Conductor freezes that variable at session launch, so a workspace renamed afterwards would keep announcing its old codename. The branch's type prefix is dropped, so `fix/public-error-user-agent` shows as `public-error-user-agent`, and a branch naming no particular work — `main` or `master` — yields to the workspace name. A label too long for its row loses its middle rather than its tail, so `verify-local-agent-hub-status` and its `-v1` variant stay distinguishable. Budgets match the firmware's own so it never shortens twice: 19 characters for a lone row, 15 for a pair, 16 for three or four, 20 on the alert screen.

Prompts and assistant responses are not persisted in the state file or offline queue. The display API emits short lifecycle messages such as `Working`, `Permission required`, and `Turn complete`.

## Fresh Mac setup

Python 3.14.7 is the recommended development version; the bridge remains tested
on Python 3.9+. From a new clone, create the local toolchain, run all tests, and
build the SmallTV Pro firmware with:

```bash
./scripts/bootstrap_macos.sh --build
```

The build does not change Claude, Codex, or launchd configuration. Configure
this Mac in the second, interactive step:

```bash
./scripts/setup_macos.sh
```

Setup asks whether to install the Claude hooks, Codex notifications, and the
per-user login service, then asks for the SmallTV URL when the service is
enabled. Press Enter to accept each value in brackets. The first run saves the
answers to the Git-ignored `.env`; later runs use them as defaults. Safe initial
defaults live in [`.env.example`](.env.example), while a device URL is
deliberately left blank until supplied on the target Mac.

The local defaults are:

- `DESK_HUB_DEVICE_URL`: SmallTV base URL;
- `DESK_HUB_INSTALL_CLAUDE`: install or refresh Claude Code hooks;
- `DESK_HUB_INSTALL_CODEX`: install or refresh Codex notifications;
- `DESK_HUB_INSTALL_SERVICE`: install and start the macOS login service.

The three installation switches accept `true` or `false`.

For scripted provisioning, edit `.env` and run
`./scripts/setup_macos.sh --non-interactive`. Use `--dry-run` to preview without
saving settings or applying either installer.

See [`MIGRATION.md`](MIGRATION.md) for moving an existing setup, including the
complete list of device-resident and Mac-local data that is intentionally not
stored in Git.

## Run the bridge

```bash
./bin/desk-hub
```

In another terminal, inject demo events:

```bash
./bin/desk-hub-demo
curl http://127.0.0.1:4747/api/v1/status
```

The bridge's local inspection endpoint is:

```text
GET /api/v1/status
```

The SmallTV pulls no data from the Mac. The bridge pushes outward, so the HTTP server remains safely bound to `127.0.0.1`. Point it at the device with:

```bash
./bin/desk-hub --device-url http://DEVICE_IP
```

Only the agent type, short workspace label, and lifecycle state are sent to the display. That label is the branch name, so treat branch names as visible on the desk; a branch's type prefix is dropped and the rest is reduced to printable ASCII within the layout's budget. Prompts, responses, file paths, and service credentials stay on the Mac.

The firmware's optional web password also protects `/api/agents` and `/api/notify`. Leave it off: the bridge sends no credentials, so turning it on makes the device reject every push.

The current SmallTV Pro build includes Agent Hub, Ticker, Clawdmeter, Weather,
Home Assistant, and Carousel. The upstream plane-radar screen is intentionally
excluded from this build to leave room for the desk-focused weather screen.

## Advanced: install local agent hooks manually

The interactive setup above is the normal installation path. Use these
lower-level commands only to preview or repair the hook configuration by
itself.

First inspect the changes without writing anything:

```bash
python3 scripts/install_hooks.py
```

Then install global hooks for local Claude Code and Codex sessions:

```bash
python3 scripts/install_hooks.py --apply
```

The installer:

- merges desk-hub entries into `~/.claude/settings.json` without removing other hooks;
- updates old absolute desk-hub hook paths when the clone has moved;
- backs up `~/.claude/settings.json`, `~/.codex/config.toml`, and `~/.codex/hooks.json` before writing;
- merges the desk-hub hook into `~/.codex/hooks.json`, leaving other tools' entries there untouched;
- changes the user-level Codex `notify` command, because project-level Codex config is not allowed to set `notify`;
- records the previous Codex notify command and forwards the original JSON to it.

Start fresh Claude/Codex sessions in Conductor after installing. Existing sessions may have loaded their configuration before the hooks were installed.

The hook ignores non-Conductor sessions by default. Conductor supplies `CONDUCTOR_IS_LOCAL=1`, `CONDUCTOR_WORKSPACE_NAME`, and `CONDUCTOR_WORKSPACE_PATH` to local agents, so the same global hook can be installed without mixing ordinary terminal sessions into the desk display. Set `DESK_HUB_CONDUCTOR_ONLY=0` only when you intentionally want to monitor every local Claude/Codex session.

## Advanced: manage the macOS login service manually

The interactive setup installs this service when that option is accepted. Use
the commands below to inspect, reinstall, or remove only the login service.

Preview the per-user launch agent installation:

```bash
python3 scripts/install_launch_agent.py
```

Install and start it:

```bash
python3 scripts/install_launch_agent.py --device-url http://DEVICE_IP --apply
```

It runs on login, restarts after a crash, and writes logs under `.runtime/`. Remove it with:

```bash
python3 scripts/install_launch_agent.py --uninstall --apply
```

## Local Conductor verification

Send a prompt from a local Conductor workspace, then compare
`http://127.0.0.1:4747/api/v1/status` against the label on the device: the row is
named after the git branch, so that is what should match.

If a Conductor-managed Claude/Codex binary uses an isolated home instead of `~/.claude` or `~/.codex`, point that harness at the system executable or install the same hook configuration in its actual config home. The event endpoint and firmware protocol do not change.

## Repository layout

- `src/`, `bin/`, and `scripts/`: the macOS bridge, event hook, and installers
- `tests/`: privacy, lifecycle, hook-installation, and launch-agent tests
- `firmware/smalltv-agent-hub/`: the SmallTV Pro firmware fork and agent display mode
- `.github/workflows/ci.yml`: root CI for Python tests, repository hygiene, and reproducible SmallTV Pro build artifacts

Local runtime state, device configuration, stock-firmware backups, downloaded reference repositories, build toolchains, and compiled firmware images are intentionally excluded from version control.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a change. Its privacy
rules apply equally to issue logs, screenshots, and test fixtures.

Release changes are tracked in [`CHANGELOG.md`](CHANGELOG.md), and the
source-only release process is documented in [`RELEASING.md`](RELEASING.md).

## Licensing and upstream attribution

The original Mac bridge and repository-level work are available under the
[MIT License](LICENSE). The firmware is derived from
[giovi321/smalltv-mod](https://github.com/giovi321/smalltv-mod) and retains its
WTFPL v2 license in
[`firmware/smalltv-agent-hub/LICENSE`](firmware/smalltv-agent-hub/LICENSE). See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the imported revision and
attribution.

Security reports must follow [`SECURITY.md`](SECURITY.md).
