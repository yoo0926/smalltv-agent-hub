# SmallTV Agent Hub firmware

Custom firmware for the GeekMagic SmallTV Pro that turns the 240×240 display
into a local Conductor session dashboard. This directory is derived from
[`giovi321/smalltv-mod`](https://github.com/giovi321/smalltv-mod), with the
imported revision and license recorded in the repository root's
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

## Supported distribution target

The project builds, tests, and publishes artifacts for the GeekMagic SmallTV
Pro environment `smalltv_esp32_8mb`: classic ESP32, 8 MB flash, ST7789 240×240
display, and the capacitive touch button on top. Other upstream-derived
PlatformIO environments remain in the source tree for reference, but they are
not release targets of this project and are not covered by its CI hardware
claim.

The Pro image contains:

- Agent Hub for Claude Code and Codex sessions launched by local Conductor;
- Ticker with Yahoo Finance symbols such as `000660.KS`;
- Clawdmeter usage display;
- Weather using Open-Meteo;
- Home Assistant screens over MQTT;
- Carousel across enabled apps;
- transient full-screen notifications and SmallTV Pro touch controls.

Plane Radar is intentionally compiled out of the Pro distribution target.

## Build

From the repository root on macOS:

```bash
./scripts/bootstrap_macos.sh --build
```

Or, with an existing project-local environment:

```bash
cd firmware/smalltv-agent-hub
PLATFORMIO_CORE_DIR=.pio-core PLATFORMIO_SETTING_ENABLE_TELEMETRY=no \
  .venv/bin/pio run -e smalltv_esp32_8mb
```

The root [CI workflow](../../.github/workflows/ci.yml) runs the same pinned
build from a clean checkout. Its downloadable ZIP contains:

- `smalltv-agent-hub-esp32-pro-ota.bin` for the device web updater;
- `smalltv-agent-hub-esp32-pro-factory.bin` for recovery through a 3.3 V UART
  adapter at flash address `0x0`;
- `SHA256SUMS` for both images.

Do not upload the factory image through the web page.

## Install and update

For the first custom install, open the stock firmware's `/update` page and
upload the OTA image. The SmallTV Pro USB-C connector supplies power only; UART
recovery requires opening the case and using the internal header. Back up stock
firmware and device settings privately if recovery matters to you—neither is
redistributed by this repository.

This fork deliberately supports **manual OTA only**. Automatic GitHub release
downloads are disabled at compile time, so an upstream release or a private
repository authentication failure cannot replace a working Agent Hub image.
Install only a CI or release OTA image that you selected explicitly.

## Device integration

Use the [root README](../../README.md)'s two-step macOS build and interactive
setup for the normal Conductor integration. The endpoints below document the
device-side contract for custom clients and troubleshooting.

The firmware accepts privacy-minimized session state from the Mac bridge:

```http
POST /api/agents
Content-Type: application/json

{"agents":[{"label":"example","agent":"claude","state":"working"}]}
```

Attention overlays use:

```http
POST /api/notify
Content-Type: application/json

{"state":"done","ttl":20,"label":"example"}
```

See [`AGENT_HUB.md`](AGENT_HUB.md) for the state contract, layout, touch
controls, and settings behavior. The root [`MIGRATION.md`](../../MIGRATION.md)
describes the Mac service and local-only data.

## Upstream hardware reference

The upstream project's
[hardware](https://giovi321.github.io/smalltv-mod/getting-started/hardware/),
[flashing](https://giovi321.github.io/smalltv-mod/getting-started/flashing/), and
[recovery](https://giovi321.github.io/smalltv-mod/reference/recovery/) pages are
useful background for the shared firmware base and other board variants. Their
release names, enabled features, and automatic-update instructions do not apply
to this Agent Hub distribution.

GeekMagic, Conductor, Anthropic, and OpenAI product names identify compatible
hardware and integrations only. This project is not affiliated with or endorsed
by those companies.
