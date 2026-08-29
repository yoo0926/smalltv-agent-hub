# GeekMagic Conductor Desk Hub

Local-only status bridge for Conductor sessions running Claude Code and Codex. The bridge keeps service credentials on the Mac and pushes a privacy-minimized task snapshot to the custom SmallTV Pro firmware over Wi-Fi.

## What works in this first slice

- Claude Code: `working`, `needs_input`, `done`, `failed`, and `idle`
- Codex: `done` for the officially supported external `agent-turn-complete` notification
- Conductor workspace labeling from the hook's `cwd` plus the git branch
- Existing Codex `notify` command chaining instead of replacing it
- Local-Conductor-only filtering through `CONDUCTOR_IS_LOCAL=1`
- Privacy-minimized offline queue with automatic replay on bridge startup
- Dependency-free Python service running on Homebrew Python 3.14, with Python 3.9+ compatibility and persisted local state
- Asynchronous push to `POST /api/agents`, plus full-screen `done` / `needs_input` alerts through `POST /api/notify`
- SmallTV Pro touch controls: tap to dismiss an alert; hold to open the app menu, tap to move, and hold to select
- Web dashboard app shortcuts that switch the display immediately and persist the selection
- SmallTV Pro weather screen for a configured city, powered by Open-Meteo current conditions and a four-day forecast
- Yahoo Finance ticker support for exchange-qualified symbols such as `000660.KS`, with fetch diagnostics in the web dashboard
- Visible success/error toast feedback after saving settings in the web dashboard

`TaskCompleted` is treated as progress rather than ending the main Claude session, because it can refer to a subtask or teammate. The Claude `Stop` hook is the authoritative turn-complete event.

Prompts and assistant responses are not persisted in the state file or offline queue. The display API emits short lifecycle messages such as `Working`, `Permission required`, and `Turn complete`.

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

Only the agent type, short workspace label, and lifecycle state are sent to the display. Prompts, responses, file paths, branches, and service credentials stay on the Mac.

The firmware's optional web password also protects `/api/agents` and `/api/notify`. Leave it disabled for this first local setup; digest-auth support can be added to the Mac push client before enabling it.

The current SmallTV Pro build includes Agent Hub, Ticker, Clawdmeter, Weather,
Home Assistant, and Carousel. The upstream plane-radar screen is intentionally
excluded from this build to leave room for the desk-focused weather screen.

## Install local agent hooks

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
- backs up existing Claude and Codex configuration files;
- changes the user-level Codex `notify` command, because project-level Codex config is not allowed to set `notify`;
- records the previous Codex notify command and forwards the original JSON to it.

Start fresh Claude/Codex sessions in Conductor after installing. Existing sessions may have loaded their configuration before the hooks were installed.

The hook ignores non-Conductor sessions by default. Conductor supplies `CONDUCTOR_IS_LOCAL=1`, `CONDUCTOR_WORKSPACE_NAME`, and `CONDUCTOR_WORKSPACE_PATH` to local agents, so the same global hook can be installed without mixing ordinary terminal sessions into the desk display. Set `DESK_HUB_CONDUCTOR_ONLY=0` only when you intentionally want to monitor every local Claude/Codex session.

## Run automatically on macOS

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

If a Conductor-managed Claude/Codex binary uses an isolated home instead of `~/.claude` or `~/.codex`, point that harness at the system executable or install the same hook configuration in its actual config home. The event endpoint and firmware protocol do not change.

## Repository layout

- `src/`, `bin/`, and `scripts/`: the macOS bridge, event hook, and installers
- `tests/`: privacy, lifecycle, hook-installation, and launch-agent tests
- `firmware/smalltv-agent-hub/`: the SmallTV Pro firmware fork and agent display mode

Local runtime state, device configuration, stock-firmware backups, downloaded reference repositories, build toolchains, and compiled firmware images are intentionally excluded from version control.

## Licensing and upstream attribution

The firmware is derived from [giovi321/smalltv-mod](https://github.com/giovi321/smalltv-mod) and retains its WTFPL v2 license in [`firmware/smalltv-agent-hub/LICENSE`](firmware/smalltv-agent-hub/LICENSE). See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the imported revision and attribution.

This repository is private for now. The Mac bridge does not yet have a public license; choose and add one before changing the repository visibility. The remaining publication steps are tracked in [`PUBLIC_RELEASE_CHECKLIST.md`](PUBLIC_RELEASE_CHECKLIST.md).
