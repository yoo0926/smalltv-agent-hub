# Moving the desk hub to another Mac

The Git repository contains everything needed to rebuild the bridge and the
SmallTV Pro firmware. Runtime state, device settings, credentials, downloaded
references, and build products are deliberately local-only.

## Fresh clone

Install Git and Python 3.9 or newer. Python 3.14.7 is the recommended and tested
version recorded in `.python-version`.

```bash
git clone https://github.com/yoo0926/smalltv-agent-hub.git
cd smalltv-agent-hub
./scripts/bootstrap_macos.sh --build
```

The bootstrap creates a project-local virtual environment, installs the exact
PlatformIO version in `requirements-dev.txt`, verifies the generated web UI,
runs the bridge tests, and optionally builds the SmallTV Pro image. It does not
change Claude, Codex, or launchd configuration without an explicit install
flag.

Once the Mac and SmallTV are on the same network, install the notification hooks
and login service. Prefer the device's mDNS name if it is stable on the network;
otherwise use its current IP address.

```bash
./scripts/bootstrap_macos.sh \
  --device-url http://smalltv-xxxx.local \
  --install-hooks \
  --install-service
```

For a completely new setup, `--all` combines the build and both installation
steps:

```bash
./scripts/bootstrap_macos.sh --device-url http://smalltv-xxxx.local --all
```

The hook installer merges with existing Claude hooks and chains an existing
Codex notifier. It also recognizes a previous desk-hub installation and updates
absolute paths when the clone has moved. Existing configuration files are
backed up before an applied change.

## What stays local

| Data | Location | Move it? |
| --- | --- | --- |
| Agent history, session IDs, worktree paths, logs | `.runtime/` | No. It is ephemeral and may contain private project metadata. |
| Codex notifier forwarding state | `.runtime/codex-forward.json` | No. Re-run the hook installer. |
| Python and PlatformIO environments | `firmware/smalltv-agent-hub/.venv`, `.pio-core`, `.pio` | No. The bootstrap reconstructs them. |
| Reference clones and scratch files | `references/`, `tmp/` | No. They are research/build material, not project inputs. |
| Compiled firmware | `dist/` and `*.bin` | No. Rebuild it or download a CI/release artifact. |
| Claude and Codex hooks | `~/.claude/settings.json`, `~/.codex/config.toml` | Do not copy wholesale. Run `scripts/install_hooks.py --apply` so other settings are preserved. |
| Login service | `~/Library/LaunchAgents/com.geekmagic.desk-hub.plist` | No. Reinstall it so paths and the device URL match the new Mac. |
| Wi-Fi, ticker, weather, display, and web-auth settings | SmallTV flash | They remain on the existing device. Configure them again in the web UI only for a new or erased device. |
| Stock-firmware backup | local backup directory only | Never commit or publish it. Treat any embedded Wi-Fi or auth data as credentials. |

Using the same SmallTV does not require copying its configuration: those values
live on the device. The repository never needs a Wi-Fi password, GitHub token,
Slack credential, or Conductor project content.

## Verify the new Mac

Start new Conductor sessions after installing the hooks, then check:

```bash
curl http://127.0.0.1:4747/api/v1/status
launchctl print gui/$(id -u)/com.geekmagic.desk-hub
tail -n 50 .runtime/desk-hub.stderr.log
```

Send a Claude prompt through a local Conductor workspace and confirm that its
short workspace label and lifecycle state appear on the display. If the service
runs but the display does not update, open the device URL from the same Mac and
reinstall the launch agent with the correct URL.

Before publishing or transferring a working tree, run:

```bash
python3 scripts/check_repository_hygiene.py
git status --short --ignored
```

The first command rejects tracked runtime/build directories, firmware binaries,
absolute macOS home paths, and several common token formats. The second command
is a final human-readable check of local-only files, including device addresses
that are valid in firmware documentation but may still be personal in context.
