# Changelog

All notable user-visible changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) for firmware releases.

## Unreleased

- Fixed two workspaces whose branches share a long prefix rendering as the
  same name. Labels now lose their middle rather than their tail, and the
  bridge spends the same per-layout budget the firmware does, so the display no
  longer shortens a second time from the front.
- Fixed a workspace renamed after its session started showing its old
  creation-time codename on the display. Conductor freezes
  `CONDUCTOR_WORKSPACE_NAME` into the session process at launch, so rows are
  now named after the git branch, which is re-read on every event. The
  branch's type prefix is dropped, and `main`/`master` yields to the
  workspace name. Branch names are therefore visible on the display.
- Fixed a firmware upload that reached the device intact still failing, and
  failing silently. The upload now gets a 30-second stall budget instead of the
  web server's generic 5 seconds, so a weak link no longer aborts a transfer
  that is still alive. An image that finished installing reboots into itself
  even when the browser is already gone, rather than leaving the device running
  the old firmware with the new one already written. A rejected image is dropped
  at the first chunk instead of being read to the end, and every failure now
  records a reason in `updateMsg`, which the update page asks for when the
  connection dies before the reply — the page used to say only "Upload error".
  A `POST /update` carrying no firmware at all no longer reports success and
  reboots.
- Fixed the touch button becoming unusable after the device had been running a
  while, reading as permanently held so taps did nothing. The filter that tracks
  the untouched reading could only ever move it *down*: integer truncation meant
  moving up by one needed a jump of 64, which the filter's own guard forbids. It
  drifted away from the real resting value until releases stopped registering.
  The filter now carries the fraction, so it tracks both directions at the rate
  it was meant to, and a press still held after ten seconds — which no finger
  is — re-learns the resting value instead of staying stuck until a reboot.
- Fixed a queued `needs_input` or `done` alert being thrown away when the push
  that carried it failed. Alerts were cleared before the request was even sent,
  so a device that was momentarily busy cost you the full-screen overlay
  entirely. They now go back on the queue and are retried for two minutes, after
  which they are dropped as before — replaying an old overlay says nothing about
  now.
- Raised the push timeout from 1.5 to 6 seconds. The device has been measured
  answering in about 4, because its single thread legitimately spends seconds
  drawing a frame, so the bridge was abandoning pushes to a healthy device and
  reporting it as broken.
- Fixed a session whose terminal was closed mid-turn holding one of the four
  display rows forever. It never reports an end, so it stays `working`; it now
  stops speaking for its workspace after six hours. It is still kept in the
  state file, where it is harmless.
- Fixed the state file growing without bound when sessions are abandoned rather
  than ended. Running sessions are exempt from both pruners, so the session cap
  had nothing it was allowed to evict; it now falls back to dropping the oldest
  running ones once nothing else is left.
- Capped the offline queue at 5 MB, keeping the newest events. Only a bridge
  start drains it, so with the bridge stopped it grew for as long as agents kept
  running.
- Fixed any device on the network being able to crash the SmallTV with a single
  unauthenticated request. A `POST /update` that is not a multipart upload takes
  the web server's raw-body path, which hands the upload handler a null record;
  reading it panicked the chip. The handler now checks the content type before
  touching that record.
- Stopped the web dashboard polling the device every five seconds during a
  firmware upload. The device answers one client at a time, so the poll spent
  the whole upload queued behind it.
- Added moving backwards through the SmallTV Pro app menu with two quick taps.
  The menu only went forward, so reaching the row above meant going all the way
  round. A tap waits briefly to see whether a second follows, so the gesture
  makes one clean move rather than visibly stepping forward and back.
- Fixed the touch button losing taps whenever the device was busy. Sampling ran
  on the main loop, which serving a single HTTP request blocks for about a tenth
  of a second — as long as a tap lasts — so taps were missed entirely and the
  double-tap gesture mostly failed. Sampling now runs on its own task, which the
  scheduler keeps going regardless of what the rest of the firmware is doing.
- Added a Settings card to the end of the SmallTV Pro app menu. Setting up a new
  device previously meant catching the address on the boot banner before it
  disappeared; the card brings it back on demand, showing the IP to type into a
  browser, the `.local` name, the joined network, and the firmware version.
- Fixed the display showing one row per session, which repeated a workspace
  whenever Claude restarted under a new session id or Codex ran beside it. Rows
  are now one per workspace, and the session that most needs attention speaks
  for it.
- Fixed a finished session claiming a workspace was done while another session
  in it was still running, both on the dashboard and as a full-screen alert.
- Stopped the state file from growing without bound by dropping finished
  sessions that a newer one in the same workspace replaced. Sessions that are
  still working or waiting are never dropped.
- Shortened how long finished work stays on the display from thirty minutes to
  ten, so it no longer holds one of the four rows for so long.
- Fixed interactive setup corrupting `~/.codex/config.toml` when the existing
  `notify` command spanned several lines. Setup could leave two top-level
  `notify` keys, which made Codex fail to start; it now refuses to write rather
  than duplicate a key it cannot parse.
- Split fresh-Mac onboarding into a repository-local build and an interactive
  setup command with Git-ignored, reusable `.env` defaults.
- Added reproducible macOS bootstrap, pinned firmware dependencies, root CI,
  repository hygiene checks, and public contribution templates.
- Scoped project documentation and release artifacts to the tested GeekMagic
  SmallTV Pro distribution target.
- Kept firmware updates manual-only so a remote release cannot silently replace
  the installed custom image.
- Updated pinned GitHub Actions and made generated-web-UI verification work for
  both clean clones and consistent in-progress source changes.
- Added the root MIT license and a security policy using GitHub private
  vulnerability reporting for coordinated disclosure.
- Added separate Korean translations for the main guide and Mac migration guide,
  with language links that keep the English documents as the source of truth.

## 0.2.1 - 2026-08-30

- Added the adaptive Agent Hub display for one to four Conductor sessions.
- Added transient done/needs-input notifications.
- Enabled SmallTV Pro touch dismissal and app selection.
- Added web-dashboard app switching and save-result toasts.
- Added Open-Meteo weather and improved Yahoo Finance handling for Korean
  symbols such as `000660.KS`.
- Added won-sign rendering and readable compact Agent Hub layouts.
