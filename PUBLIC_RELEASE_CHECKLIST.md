# Public release checklist

Technical preparation and policy decisions are complete. The repository
remains private until the owner performs the publication actions at the end of
this file.

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
- [x] License the original Mac bridge and repository-level work under MIT while
  retaining the firmware subtree's upstream WTFPL v2 license.
- [x] Add `SECURITY.md` with GitHub private vulnerability reporting as the
  coordinated disclosure route.

## Owner publication actions still required

- [ ] Change repository visibility from private to public. This must be an
  explicit owner action.
- [ ] Immediately afterward, open **Settings → Security → Advanced Security**
  and enable **Private vulnerability reporting**. GitHub exposes this setting
  only for public repositories; enabling it activates the private form linked
  from `SECURITY.md`.
