# Public release checklist

The GitHub repository is intentionally private during development. Complete this checklist before changing its visibility.

- [ ] Choose a license for the original Mac bridge code and add it at the repository root. MIT is the current recommendation; the firmware keeps its existing WTFPL v2 license.
- [ ] Re-run the test suite and the `smalltv_esp32_8mb` firmware build from a clean checkout.
- [ ] Review every tracked file for credentials, device configuration, IP addresses, personal paths, logs, and stock-firmware backups.
- [ ] Replace local setup examples such as the current device IP with placeholders where appropriate.
- [ ] Decide whether the firmware updater should target this repository. While the repository is private, an unauthenticated device cannot download private GitHub releases.
- [ ] Adapt and move the firmware CI workflows to the repository root only when automatic public builds and documentation deployment are wanted. Workflows nested below `firmware/` do not run in this repository.
- [ ] Update fork branding and documentation links while keeping the upstream attribution in `THIRD_PARTY_NOTICES.md`.
- [ ] Build release assets from source; never publish the stock firmware backup.
- [ ] Review GitHub repository settings, Actions permissions, issue templates, and the security contact before making the repository public.
