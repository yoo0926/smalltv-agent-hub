## Summary

Describe the user-visible bridge or firmware change.

## Verification

- [ ] Bridge tests pass on a supported Python version.
- [ ] `python3 scripts/check_repository_hygiene.py` passes.
- [ ] `src/webui.h` was regenerated if the firmware web UI changed.
- [ ] `smalltv_esp32_8mb` builds if firmware code or dependencies changed.
- [ ] Logs, screenshots, and fixtures contain no credentials or private agent/project data.

## Device testing

Describe the SmallTV Pro hardware test, or write `not applicable`.
