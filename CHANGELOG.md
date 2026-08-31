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
