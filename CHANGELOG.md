# Changelog

All notable user-visible changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) for firmware releases.

## Unreleased

Nothing here has shipped in a release yet, so entries describe where things
landed rather than every step taken to get there.

### Added

- Codex reports while it works, not only when a turn ends. Setup installs
  `~/.codex/hooks.json` alongside the existing `notify` command, so Codex shows
  `working` and `needs_input` the way Claude does. Other tools' entries in that
  file are left alone.
- A Settings card at the end of the SmallTV Pro app menu, showing the address to
  open in a browser, the network it came from, and the running firmware. Setting
  up a new device no longer means catching the boot banner before it disappears.
- Two quick taps move back through the app menu, which previously only went
  forward.

### Changed

- A workspace is one row, not one row per session, and it is named after its git
  branch. Only the newest session of each kind speaks for it, so a restarted
  Claude replaces the one before it while Claude and Codex each keep a voice.
  The same workspace reached through a Conductor symlink and through its real
  path counts once.
- Which workspaces reach the four rows, and their order, follows how much each
  wants attention rather than recency alone, so one waiting for you is never
  crowded out by busier ones.
- Finished work leaves the display after ten minutes rather than thirty.
- Fresh-Mac onboarding is a repository-local build followed by an interactive
  setup command, with reusable `.env` defaults. Firmware updates stay
  manual-only so a remote release cannot silently replace the installed image.

### Fixed

- The touch button became unusable after the device had been running a while,
  reading as permanently held, and lost taps whenever the device was busy.
  Sampling now runs on its own task and the filter that tracks the untouched
  reading can move in both directions.
- A firmware upload that reached the device intact could still fail, silently.
  Uploads now get a 30-second stall budget, a committed image reboots into
  itself even if the browser has gone, and every failure records a reason.
- Any device on the network could crash the SmallTV with a single
  unauthenticated request.
- A queued `needs_input` or `done` alert was thrown away when the push carrying
  it failed, and the push timeout was shorter than the device's measured
  response time.
- The state file and the offline queue could both grow without bound.
- Interactive setup could corrupt `~/.codex/config.toml` when the existing
  `notify` command spanned several lines.

### Documentation

- Korean translations of the main guide and the Mac migration guide, kept
  alongside the English originals.
- MIT license, security policy using GitHub private vulnerability reporting, and
  upstream attribution.

## 0.2.1 - 2026-08-30

- Added the adaptive Agent Hub display for one to four Conductor sessions.
- Added transient done/needs-input notifications.
- Enabled SmallTV Pro touch dismissal and app selection.
- Added web-dashboard app switching and save-result toasts.
- Added Open-Meteo weather and improved Yahoo Finance handling for Korean
  symbols such as `000660.KS`.
- Added won-sign rendering and readable compact Agent Hub layouts.
