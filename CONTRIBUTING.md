# Contributing

Thanks for helping improve the Conductor desk hub and SmallTV Pro firmware.
This repository combines a dependency-free local Python bridge with an embedded
firmware fork, so changes should keep both privacy and flash constraints in
mind.

## Development setup

On macOS with Python 3.9 or newer:

```bash
./scripts/bootstrap_macos.sh --build
```

The command creates only project-local build environments. The separate
`./scripts/setup_macos.sh` command performs machine-local hook and service
installation. See `MIGRATION.md` for the data that must remain outside Git.

For a quick bridge-only test:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/check_repository_hygiene.py
```

For a firmware change, also regenerate and verify the embedded web UI before
building:

```bash
python3 firmware/smalltv-agent-hub/tools/gzip_webui.py
git diff -- firmware/smalltv-agent-hub/src/webui.h
./scripts/bootstrap_macos.sh --build
```

Commit `src/webui.h` when `src/webui.html` changes. Do not hand-edit the
generated header.

## Privacy and test data

- Never commit `.runtime/`, stock firmware, compiled binaries, local reference
  clones, Wi-Fi details, web passwords, service tokens, user prompts, or agent
  responses.
- Use placeholders such as `http://DEVICE_IP` or
  `http://smalltv-xxxx.local` in documentation and tests.
- Redact session IDs, absolute worktree paths, project names, branches, SSIDs,
  and device identifiers from bug reports and logs.
- Keep the bridge bound to loopback unless a change has an explicit security
  design and test coverage.

## Pull requests

Keep changes focused and describe which bridge event, firmware screen, or
hardware target is affected. Include tests for event mapping, persistence, hook
merging, or API behavior when applicable. Firmware UI changes should include a
photo or screenshot when it materially helps review.

Root CI tests Python 3.9 and 3.14, checks repository hygiene and the generated
web UI, and builds the `smalltv_esp32_8mb` target with pinned dependencies.

By contributing, you agree that repository-level and Mac bridge contributions
are provided under the root MIT License. Changes within
`firmware/smalltv-agent-hub/` remain under that subtree's WTFPL v2 license and
must preserve the upstream attribution recorded in `THIRD_PARTY_NOTICES.md`.
