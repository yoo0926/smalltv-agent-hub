# SmallTV Agent Hub

This fork targets the GeekMagic SmallTV Pro (`smalltv_esp32_8mb`) and adds a
persistent local-agent dashboard for Conductor sessions.

## Device API

Push the four newest tasks to the persistent dashboard:

```http
POST /api/agents
Content-Type: application/json

{"agents":[{"label":"da-nang","agent":"claude","state":"working"}]}
```

Supported states are `working`, `needs_input`, `done`, `failed`, and `idle`.
Only printable short labels are retained; prompts and responses are not part of
the protocol.

The dashboard adapts to the number of visible sessions. One session gets a
full-screen hero layout with a large project name and state, two sessions use
two large cards, and three or four sessions use compact rows while keeping the
project and state at text size 2. Long labels are shortened instead of being
shrunk to the least-readable font size.

Use the transient full-screen overlay for attention events:

```http
POST /api/notify
Content-Type: application/json

{"state":"done","ttl":20,"label":"da-nang"}
```

`state` is `done` or `waiting`. Both endpoints follow the web UI's digest-auth
setting. The bundled Mac bridge currently expects that setting to remain off.

## SmallTV Pro touch controls

The top capacitive button is intentionally limited to a few predictable actions:

- Tap while a full-screen notification is visible to dismiss it.
- Hold for about one second to open the app menu.
- In the menu, tap to move to the next app and hold to select it.
- Leave the menu untouched for 15 seconds to cancel without changing apps.

The selected app is saved and survives a reboot. Touch readings are calibrated
at boot and reported under `touch` in `GET /api/status` for diagnostics.

The web dashboard's **Status** tab provides the same app choices as direct
buttons. Selecting one calls `POST /api/mode`, closes any notification or touch
menu, displays that app immediately, and saves it as the reboot default.

## SmallTV Pro apps

The `smalltv_esp32_8mb` build contains Agent Hub, Ticker, Clawdmeter, Weather,
Home Assistant, and Carousel. Radar is disabled in this target. Weather resolves
the configured city with Open-Meteo geocoding and fetches current conditions plus
a compact four-day forecast without an API key.

Yahoo tickers accept exchange-qualified symbols such as `000660.KS`. The Pro
buffers Yahoo's chart response before parsing it, because direct decoding from
the live TLS stream could fail despite an HTTP 200 response. The Ticker tab
exposes the last fetch stage and HTTP code when a symbol fails.
Korean won quotes use a drawn won glyph and grouped whole-won values (for
example, `₩1,653,000`) because the device's built-in bitmap font has no Unicode
won character.

Saving the web form shows a short success or failure toast, and temporarily
disables the save button to prevent duplicate submissions.

## Build and install

From the repository root on macOS, the recommended clean setup and build is:

```bash
./scripts/bootstrap_macos.sh --build
```

The project currently pins PlatformIO 6.1.19, pioarduino's ESP32 platform
55.03.311 (Arduino ESP32 3.3.11 / ESP-IDF 5.5.5), and exact application library
versions in `platformio.ini`. To rebuild with an existing local environment:

```bash
cd firmware/smalltv-agent-hub
PLATFORMIO_CORE_DIR=.pio-core PLATFORMIO_SETTING_ENABLE_TELEMETRY=no \
  .venv/bin/pio run -e smalltv_esp32_8mb
```

Upload `.pio/build/smalltv_esp32_8mb/firmware.bin` through the stock `/update`
page. It is the OTA app image. Do not upload `firmware.factory.bin` through the
web page; that merged image is only for a 3.3 V UART recovery flash at address
`0x0`.

On first boot the firmware imports the stock Wi-Fi SSID/password from
`/.sys/config.json` into its own `/config.json`, leaving the rest of the stock
LittleFS data untouched. Automatic GitHub self-update is disabled so an
upstream release cannot silently replace the Agent Hub changes.
