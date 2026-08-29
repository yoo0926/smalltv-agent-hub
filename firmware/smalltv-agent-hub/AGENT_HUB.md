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

Use the transient full-screen overlay for attention events:

```http
POST /api/notify
Content-Type: application/json

{"state":"done","ttl":20,"label":"da-nang"}
```

`state` is `done` or `waiting`. Both endpoints follow the web UI's digest-auth
setting. The bundled Mac bridge currently expects that setting to remain off.

## Build and install

```bash
PLATFORMIO_CORE_DIR=.pio-core .venv/bin/pio run -e smalltv_esp32_8mb
```

Upload `.pio/build/smalltv_esp32_8mb/firmware.bin` through the stock `/update`
page. It is the OTA app image. Do not upload `firmware.factory.bin` through the
web page; that merged image is only for a 3.3 V UART recovery flash at address
`0x0`.

On first boot the firmware imports the stock Wi-Fi SSID/password from
`/.sys/config.json` into its own `/config.json`, leaving the rest of the stock
LittleFS data untouched. Automatic GitHub self-update is disabled so an
upstream release cannot silently replace the Agent Hub changes.
