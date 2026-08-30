# Releasing

The repository does not publish a release merely because code was pushed or a
tag was created. This avoids distributing an unreviewed firmware image while
the project is private.

## Before the first public release

The MIT license and GitHub private vulnerability-reporting route are already
represented in the repository. Complete the two owner actions in
`PUBLIC_RELEASE_CHECKLIST.md`: make the repository public, then immediately
enable private vulnerability reporting in GitHub's Advanced Security settings.

## Prepare a version

1. Update `FW_VERSION` in `firmware/smalltv-agent-hub/src/config.h`.
2. Move the relevant `CHANGELOG.md` entries under the new version and date.
3. Run `./scripts/bootstrap_macos.sh --build`.
4. Push the commit and wait for every root CI job to pass.
5. Download the `smalltv-agent-hub-esp32-pro-<commit>` CI artifact and verify
   `SHA256SUMS` inside the ZIP.
6. Test the OTA image on a SmallTV Pro through the web updater. Do not upload
   the factory image through the web page.

## Publish

Create a signed or annotated tag such as `v0.2.2` at the tested commit, then
create a GitHub release from that tag. Attach these source-built files without
renaming them:

- `smalltv-agent-hub-esp32-pro-ota.bin`
- `smalltv-agent-hub-esp32-pro-factory.bin`
- `SHA256SUMS`

Copy the matching changelog section into the release notes. Never attach stock
firmware, a device settings export, `.runtime` data, credentials, logs, or a
locally produced binary that did not pass the same clean CI build.

The device intentionally does not fetch GitHub releases by itself. Users choose
and upload an OTA image manually, so publishing a release does not modify any
installed device.
