# Public release checklist

The GitHub repository is intentionally private during development. Complete this checklist before changing its visibility.

- [ ] Choose a license for the original Mac bridge code and add it at the repository root. MIT is the current recommendation; the firmware keeps its existing WTFPL v2 license.
- [x] Re-run the test suite and the `smalltv_esp32_8mb` firmware build from a clean checkout. [CI run #1](https://github.com/yoo0926/smalltv-agent-hub/actions/runs/33314191659) passed for commit `79a9698` and produced checksummed OTA/factory artifacts.
- [x] Pin Python/PlatformIO guidance, ESP32 platform, and firmware libraries so a fresh checkout does not silently follow future toolchain releases.
- [x] Document fresh-Mac setup and distinguish Git-tracked source from device-resident and Mac-local data in `MIGRATION.md`.
- [x] Review tracked files for credentials, device configuration, personal paths, logs, and stock-firmware backups. Root CI also runs `scripts/check_repository_hygiene.py` to prevent common regressions.
- [x] Replace machine-specific setup values with placeholders in root project documentation.
- [ ] Decide whether the firmware updater should target this repository. While the repository is private, an unauthenticated device cannot download private GitHub releases.
- [x] Add a least-privilege root CI workflow for Python 3.9/3.14 tests, source hygiene, generated-web-UI verification, and the pinned SmallTV Pro firmware build. It uploads checksummed OTA/factory artifacts without publishing a release.
- [ ] Update fork branding and documentation links while keeping the upstream attribution in `THIRD_PARTY_NOTICES.md`.
- [x] Build CI artifacts exclusively from source; never publish the stock firmware backup.
- [x] Add privacy-aware issue forms, a pull request template, contribution guidance, and weekly dependency update checks.
- [ ] Choose a private security-reporting contact or enable GitHub private vulnerability reporting, then add `SECURITY.md`.
- [ ] Review GitHub repository settings and Actions permissions before making the repository public.
