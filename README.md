# GeekMagic Conductor Desk Hub

[English](README.md) | [한국어](README.ko.md)

[![CI](https://github.com/yoo0926/smalltv-agent-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/yoo0926/smalltv-agent-hub/actions/workflows/ci.yml)

Local-only status bridge for Conductor sessions running Claude Code and Codex. The bridge keeps service credentials on the Mac and pushes a privacy-minimized task snapshot to the custom SmallTV Pro firmware over Wi-Fi.

## Current capabilities

- Claude Code: `working`, `needs_input`, `done`, `failed`, and `idle`
- Codex: `done` for the officially supported external `agent-turn-complete` notification
- Conductor workspace labeling from the git branch, falling back to the Conductor workspace name, so a workspace renamed after its session started is still labeled correctly
- One row per workspace, not per session, so a Claude restart or a Codex run beside it never splits a repository across two rows
- Existing Codex `notify` command chaining instead of replacing it
- Local-Conductor-only filtering through `CONDUCTOR_IS_LOCAL=1`
- Privacy-minimized offline queue with automatic replay on bridge startup
- Dependency-free Python service running on Homebrew Python 3.14, with Python 3.9+ compatibility and persisted local state
- Asynchronous push to `POST /api/agents`, plus full-screen `done` / `needs_input` alerts through `POST /api/notify`
- SmallTV Pro touch controls: tap to dismiss an alert; hold to open the app menu, tap to move, and hold to select
- Web dashboard app shortcuts that switch the display immediately and persist the selection
- SmallTV Pro weather screen for a configured city, powered by Open-Meteo current conditions and a four-day forecast
- Yahoo Finance ticker support for exchange-qualified symbols such as `000660.KS`, with fetch diagnostics in the web dashboard
- Native-looking won-sign and grouped whole-won prices for Korean tickers
- Adaptive Agent Hub layout: a large hero view for one task, two large cards, or readable compact rows for three to four tasks
- Visible success/error toast feedback after saving settings in the web dashboard

`TaskCompleted` is treated as progress rather than ending the main Claude session, because it can refer to a subtask or teammate. The Claude `Stop` hook is the authoritative turn-complete event, and only `SessionEnd` closes a session for good.

`Stop` ends a turn rather than the session, so a session that resumes without a new prompt — after a permission grant, for example — keeps showing its last state until the next turn ends. The bridge can close that gap with a throttled `PostToolUse` hook, which is implemented but not installed: the hook process starts on every tool call and costs roughly 80 ms each time. See the note above `CLAUDE_EVENTS` in [`scripts/install_hooks.py`](scripts/install_hooks.py) to turn it on.

A workspace speaks with one voice on the display: among its sessions, `needs_input` outranks `failed`, which outranks `working`, which outranks `done`. A `done` alert is therefore suppressed while another session in the same workspace is still running, and finished work leaves the display after ten minutes.

A row is named after its git branch rather than `CONDUCTOR_WORKSPACE_NAME`, because Conductor freezes that variable into the session process at launch: a workspace renamed afterwards keeps announcing the codename it was created with until a new session replaces it. The branch is re-read on every event, and Conductor derives the workspace name from it anyway. A branch's conventional type prefix is dropped, so `fix/public-error-user-agent` shows as `public-error-user-agent`. A branch that names no particular work — `main` or `master` — yields to the workspace name, which yields in turn to the agent type. Labels are cut to twenty characters by the firmware's buffer, so branches that differ only in a suffix can look alike on the display.

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

Only the agent type, short workspace label, and lifecycle state are sent to the display. That label is the branch name, so treat branch names as visible on the desk; a branch's type prefix is dropped and the rest is cut to twenty printable ASCII characters. Prompts, responses, file paths, and service credentials stay on the Mac.

The firmware's optional web password also protects `/api/agents` and `/api/notify`. Leave it disabled for this first local setup; digest-auth support can be added to the Mac push client before enabling it.

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
- backs up existing Claude and Codex configuration files;
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

1. Start `./bin/desk-hub`.
2. Open a new Claude Code session from a Conductor workspace.
3. Send a prompt, wait for completion, then trigger one permission request.
4. Inspect `http://127.0.0.1:4747/api/v1/status`.
5. Open a new Codex session in Conductor and finish one turn.
6. Confirm that the returned `cwd`, workspace name, and branch identify the correct Conductor worktree.
   The branch is what reaches the display, so check it against the label shown there.

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
The current GitHub configuration review is recorded in
[`REPOSITORY_SETTINGS.md`](REPOSITORY_SETTINGS.md).

## Licensing and upstream attribution

The original Mac bridge and repository-level work are available under the
[MIT License](LICENSE). The firmware is derived from
[giovi321/smalltv-mod](https://github.com/giovi321/smalltv-mod) and retains its
WTFPL v2 license in
[`firmware/smalltv-agent-hub/LICENSE`](firmware/smalltv-agent-hub/LICENSE). See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the imported revision and
attribution.

Security reports must follow [`SECURITY.md`](SECURITY.md). Publication and
repository-owner settings are documented in
[`PUBLIC_RELEASE_CHECKLIST.md`](PUBLIC_RELEASE_CHECKLIST.md).
