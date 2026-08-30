# Changelog

All notable user-visible changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) for firmware releases.

## Unreleased

- Added reproducible macOS bootstrap, pinned firmware dependencies, root CI,
  repository hygiene checks, and public contribution templates.
- Scoped project documentation and release artifacts to the tested GeekMagic
  SmallTV Pro distribution target.
- Kept firmware updates manual-only so a remote release cannot silently replace
  the installed custom image.
- Updated pinned GitHub Actions and made generated-web-UI verification work for
  both clean clones and consistent in-progress source changes.

## 0.2.1 - 2026-08-30

- Added the adaptive Agent Hub display for one to four Conductor sessions.
- Added transient done/needs-input notifications.
- Enabled SmallTV Pro touch dismissal and app selection.
- Added web-dashboard app switching and save-result toasts.
- Added Open-Meteo weather and improved Yahoo Finance handling for Korean
  symbols such as `000660.KS`.
- Added won-sign rendering and readable compact Agent Hub layouts.
