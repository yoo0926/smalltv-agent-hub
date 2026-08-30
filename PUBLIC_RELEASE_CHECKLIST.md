# Public release checklist

Technical preparation is complete. The repository remains private until the
owner completes the three decisions at the end of this file.

## Completed technical work

- [x] Pin Python/PlatformIO guidance, the ESP32 platform, and firmware libraries.
- [x] Provide a safe fresh-Mac bootstrap and path-aware Claude/Codex hook installer.
- [x] Document Git-tracked, Mac-local, and device-resident data in `MIGRATION.md`.
- [x] Scan tracked files for credentials, personal paths, logs, stock firmware,
  build output, and local runtime data; enforce common cases in root CI.
- [x] Replace machine-specific values with placeholders in project documentation.
- [x] Run Python 3.9/3.14 tests and `smalltv_esp32_8mb` from a clean checkout.
  [CI run #1](https://github.com/yoo0926/smalltv-agent-hub/actions/runs/33314191659)
  passed and produced checksummed OTA/factory artifacts.
- [x] Add least-privilege root CI with pinned actions, timeouts, generated-web-UI
  verification, and source-built firmware artifacts.
- [x] Keep firmware updates manual-only. The device does not query an upstream
  or private GitHub release feed, and the web UI names the exact OTA artifact.
- [x] Replace inherited project branding and links while preserving explicit
  upstream attribution in `THIRD_PARTY_NOTICES.md` and the firmware README.
- [x] Remove the inherited documentation site and nested workflows whose board,
  feature, release, and updater claims did not match this Pro distribution.
- [x] Add `CHANGELOG.md`, `RELEASING.md`, CODEOWNERS, contribution guidance,
  privacy-aware issue/PR forms, and weekly dependency checks.
- [x] Review current GitHub repository and Actions settings; record the result
  and future multi-contributor branch-rule recommendation in
  `REPOSITORY_SETTINGS.md`.
- [x] Ensure release instructions publish only clean source-built Agent Hub
  artifacts and never stock firmware or device settings.

## Owner decisions still required

- [ ] Choose a license for the original Mac bridge and add it as root `LICENSE`.
  MIT is the current recommendation. The firmware subtree retains upstream
  WTFPL v2 under `firmware/smalltv-agent-hub/LICENSE`.
- [ ] Choose a private security-reporting route: enable GitHub private
  vulnerability reporting after publication, or provide a dedicated security
  contact. Replace the placeholder in `SECURITY.md.template` and rename it to
  `SECURITY.md`.
- [ ] Change repository visibility from private to public only after the two
  files above are complete. This must be an explicit owner action.
