// SmallTV Agent Hub — custom firmware for GeekMagic SmallTV hardware
//
// Features are self-contained DisplayModes (see Mode.h), picked in the web UI
// and dispatched from the registry below. The SmallTV Pro distribution starts
// with Agent Hub, then Ticker, Usage, Weather, and Home Assistant; optional
// targets may compile a different subset.
// Shared plumbing (WiFi, web UI, OTA, display core, settings) lives at src root.
//
// License: WTFPL
#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include "Platform.h"
#include "config.h"
#include "Settings.h"
#include "Net.h"
#include "Gfx.h"
#include "WebPortal.h"
#include "OtaUpdate.h"
#include "Mode.h"
#include "Clock.h"
#include "WgClient.h"
#include "TouchButton.h"
#if WITH_NOTIFY
#include "NotifyMode.h"
#endif
#if WITH_AGENTS
#include "features/agents/AgentMode.h"
#endif

#if WITH_TICKER
#include "TickerMode.h"
#endif
#if WITH_USAGE
#include "UsageMode.h"
#endif
#if WITH_WEATHER
#include "features/weather/WeatherMode.h"
#endif
#if WITH_RADAR
#include "RadarMode.h"
#endif
#if WITH_HA
#include "HaMode.h"
#include "MqttClient.h"
#endif

// ---- mode registry --------------------------------------------------------
// The compiled-in features, in display order. main.cpp holds no per-feature
// state of its own — each mode owns its fetch/render/dirty tracking.
static DisplayMode* kModes[] = {
#if WITH_AGENTS
  &g_agentMode,
#endif
#if WITH_TICKER
  &g_tickerMode,
#endif
#if WITH_USAGE
  &g_usageMode,
#endif
#if WITH_WEATHER
  &g_weatherMode,
#endif
#if WITH_RADAR
  &g_radarMode,
#endif
#if WITH_HA
  &g_haMode,
#endif
};
static const size_t kModeCount = sizeof(kModes) / sizeof(kModes[0]);

// ---- carousel -------------------------------------------------------------
// MODE_CAROUSEL rotates through the ticked features. Switches call wake() on
// the incoming mode: repaint from cached data, no refetch.
static size_t   g_carIdx = 0;
static uint32_t g_carSwitch = 0;

static bool carouselHas(const Settings& s, const DisplayMode* m) {
  switch (m->modeConst()) {
    case MODE_AGENTS: return s.carouselAgents;
    case MODE_STOCKS: return s.carouselTicker;
    case MODE_USAGE:  return s.carouselUsage;
    case MODE_WEATHER:return s.carouselWeather;
    case MODE_RADAR:  return s.carouselRadar;
#if WITH_HA
    case MODE_HA:     return s.carouselHa;
#endif
    default:          return true;
  }
}

// Advance g_carIdx to the next ticked mode (stays put if none other is ticked).
static void carouselNext(const Settings& s) {
  for (size_t hop = 1; hop <= kModeCount; hop++) {
    size_t cand = (g_carIdx + hop) % kModeCount;
    if (!carouselHas(s, kModes[cand])) continue;
    if (cand != g_carIdx) {
      g_carIdx = cand;
      kModes[cand]->wake(s);
    }
    return;
  }
}

static DisplayMode* activeMode(const Settings& s) {
  if (s.mode == MODE_CAROUSEL && kModeCount > 0) {
    if (g_carSwitch == 0) g_carSwitch = millis();
    if (!carouselHas(s, kModes[g_carIdx])) carouselNext(s);   // settings changed
    if (millis() - g_carSwitch >= (uint32_t)s.carouselSec * 1000UL) {
      g_carSwitch = millis();
      carouselNext(s);
    }
    return kModes[g_carIdx];
  }
  for (size_t i = 0; i < kModeCount; i++)
    if (kModes[i]->modeConst() == s.mode) return kModes[i];
  return kModeCount ? kModes[0] : nullptr;   // fall back to the first compiled mode
}

static Settings g_settings;



#if HAS_TOUCH_BUTTON
// ---- one-button app menu --------------------------------------------------
// The Pro has a single capacitive input, so the interaction deliberately stays
// tiny: hold to enter, tap to move, hold to choose. A timeout exits unchanged.
static bool     g_touchMenuOpen = false;
static size_t   g_touchMenuIndex = 0;
static uint32_t g_touchMenuActivity = 0;
// A tap is not acted on until the double-tap window closes, so the gesture
// resolves to exactly one move. Nothing is drawn while it is pending either,
// which leaves the touch sampler free to catch the second tap.
static bool     g_touchMenuPending = false;
static uint32_t g_touchMenuPendingAt = 0;

static const char* touchModeLabel(uint8_t mode) {
  switch (mode) {
    case MODE_AGENTS:   return "Agent Hub";
    case MODE_STOCKS:   return "Ticker";
    case MODE_USAGE:    return "Clawdmeter";
    case MODE_WEATHER:  return "Weather";
    case MODE_RADAR:    return "Radar";
    case MODE_HA:       return "Home Assistant";
    case MODE_CAROUSEL: return "Carousel";
    default:            return "App";
  }
}

// Two rows follow the compiled-in apps: Carousel, then Settings. Settings is not
// an app — picking it opens a card and leaves settings.mode alone (see below).
static size_t touchMenuCount() { return kModeCount + 2; }

static bool touchMenuIsSettings(size_t index) { return index == kModeCount + 1; }

static uint8_t touchMenuMode(size_t index) {
  return index < kModeCount ? kModes[index]->modeConst() : MODE_CAROUSEL;
}

static const char* touchMenuLabel(size_t index) {
  return touchMenuIsSettings(index) ? "Settings" : touchModeLabel(touchMenuMode(index));
}

// The rows share the band between the hint and the footer instead of a fixed
// pitch, so a build with more features compiled in cannot run its last row into
// the cancel notice. The cap keeps the common case looking unchanged.
static const int kTouchMenuTop = 46;
static int touchMenuStep() { return min(27, (216 - kTouchMenuTop) / (int)touchMenuCount()); }

static void drawTouchMenuRow(Arduino_GFX* gfx, size_t i) {
  const int y = kTouchMenuTop + (int)i * touchMenuStep();
  const bool on = (i == g_touchMenuIndex);
  gfx->fillRect(10, y - 5, TFT_WIDTH - 20, 22, on ? C_BLUE : C_BLACK);
  gfxDrawCentered(touchMenuLabel(i), y, 2, on ? C_WHITE : C_GRAY);
}

static void drawTouchMenu() {
  Arduino_GFX* gfx = gfxDev();
  if (!gfx) return;

  gfx->fillScreen(C_BLACK);
  gfxDrawCentered("CHOOSE APP", 8, 2, C_WHITE);
  gfxDrawCentered("tap next - 2 taps back - hold ok", 29, 1, C_GRAY);
  for (size_t i = 0; i < touchMenuCount(); i++) drawTouchMenuRow(gfx, i);
  gfxDrawCentered("15 sec to cancel", 224, 1, C_DGRAY);
}

// Moving the highlight repaints the two rows that changed, not the panel. The
// full-screen version blanked and rewrote 240x240 over SPI on every tap, and
// touchButtonPoll() cannot sample while that runs — long enough that the second
// tap of a quick double could begin and end unseen, which is exactly how the
// gesture went missing.
static void redrawTouchMenuMove(size_t from) {
  Arduino_GFX* gfx = gfxDev();
  if (!gfx || from == g_touchMenuIndex) return;
  drawTouchMenuRow(gfx, from);
  drawTouchMenuRow(gfx, g_touchMenuIndex);
}

static void openTouchMenu() {
  g_touchMenuIndex = kModeCount;  // Carousel is the final row.
  for (size_t i = 0; i < kModeCount; i++) {
    if (kModes[i]->modeConst() == g_settings.mode) {
      g_touchMenuIndex = i;
      break;
    }
  }
  g_touchMenuOpen = true;
  g_touchMenuActivity = millis();
  g_touchMenuPending = false;   // the hold that opened the menu is not half a tap
  drawTouchMenu();
}

// ---- settings card --------------------------------------------------------
// Deliberately not a DisplayMode: the boot banner already shows the address and
// then leaves, and this is the way back to it — so it must not become the boot
// default, must not join the carousel, and must not need a settings slice. It
// borrows the menu's interaction instead: tap to leave, hold for the menu.
static bool     g_settingsCardOpen = false;
static uint32_t g_settingsCardOpenedAt = 0;
static uint32_t g_settingsCardPolled = 0;
static String   g_settingsCardIp;
static String   g_settingsCardSsid;

static void drawSettingsCard() {
  g_settingsCardIp = netIP();
  g_settingsCardSsid = netSSID();
  gfxSettingsInfo(g_settingsCardSsid.c_str(), netRSSI(), g_settingsCardIp.c_str(),
                  g_settings.hostname.c_str(), FW_VERSION " - " FW_VARIANT);
}

static void openSettingsCard() {
  g_settingsCardOpen = true;
  g_settingsCardOpenedAt = millis();
  g_settingsCardPolled = g_settingsCardOpenedAt;
  drawSettingsCard();
}

static void closeSettingsCard() {
  g_settingsCardOpen = false;
  DisplayMode* m = activeMode(g_settings);
  if (m) m->wake(g_settings);
}

static void serviceSettingsCard(TouchButtonEvent event) {
#if WITH_NOTIFY
  // An alert outranks a card someone opened to read an address off; drop the card
  // without repainting, because the overlay is about to cover the screen anyway.
  if (g_notifyMode.active()) {
    g_settingsCardOpen = false;
    return;
  }
#endif
  if (event == TOUCH_EVENT_SHORT) {
    closeSettingsCard();
    return;
  }
  if (event == TOUCH_EVENT_LONG) {
    g_settingsCardOpen = false;   // straight back to the menu, no repaint in between
    openTouchMenu();
    return;
  }
  if (millis() - g_settingsCardOpenedAt >= SETTINGS_SCREEN_TIMEOUT_MS) {
    closeSettingsCard();
    return;
  }
  // A lease can be renewed onto a different address while the card is up, which
  // is exactly when a stale one does the most damage. Poll slowly and repaint
  // only on a real change, so the panel isn't rewritten every tick.
  if (millis() - g_settingsCardPolled < 1000) return;
  g_settingsCardPolled = millis();
  if (netIP() != g_settingsCardIp || netSSID() != g_settingsCardSsid) drawSettingsCard();
}

static void closeTouchMenu(bool choose) {
  const bool settings = choose && touchMenuIsSettings(g_touchMenuIndex);
  if (choose && !settings) {
    g_settings.mode = touchMenuMode(g_touchMenuIndex);
    saveSettings(g_settings);
    if (g_settings.mode == MODE_CAROUSEL) g_carIdx = 0;
    g_carSwitch = 0;
  }

  g_touchMenuOpen = false;
  if (settings) {
    openSettingsCard();
    return;
  }
  DisplayMode* m = activeMode(g_settings);
  if (m) m->wake(g_settings);
}

static void moveTouchMenu(int delta) {
  const size_t count = touchMenuCount();
  const size_t from = g_touchMenuIndex;
  g_touchMenuIndex = (g_touchMenuIndex + count + delta) % count;
  redrawTouchMenuMove(from);
}

static void serviceTouchMenu(TouchButtonEvent event) {
  const uint32_t now = millis();

  if (event == TOUCH_EVENT_SHORT) {
    g_touchMenuActivity = now;
    // A tap arriving right after the previous one is the second half of a
    // double: it cancels the step the first was about to take and goes back one
    // instead. Judged on how long the finger was off, which is what a double tap
    // actually controls — the interval between taps also carries however long
    // the button was held, and that varied enough to lose the gesture.
    if (g_touchMenuPending && touchButtonLastIdleMs() <= TOUCH_DOUBLE_TAP_MS) {
      g_touchMenuPending = false;
      moveTouchMenu(-1);
      return;
    }
    // Otherwise let any step still waiting land, and start waiting on this one.
    // Steps wait rather than act at once so a double tap resolves to a single
    // clean move instead of visibly hopping forward and back.
    if (g_touchMenuPending) moveTouchMenu(1);
    g_touchMenuPending = true;
    g_touchMenuPendingAt = now;
    return;
  }

  if (event == TOUCH_EVENT_LONG) {
    // Holding before the wait is over still means "the row that tap was taking
    // me to", so let it land rather than choosing the row under the old highlight.
    if (g_touchMenuPending) {
      g_touchMenuPending = false;
      moveTouchMenu(1);
    }
    closeTouchMenu(true);
    return;
  }

  if (g_touchMenuPending && now - g_touchMenuPendingAt >= TOUCH_TAP_COMMIT_MS) {
    g_touchMenuPending = false;
    moveTouchMenu(1);
    return;
  }
  if (now - g_touchMenuActivity >= TOUCH_MENU_TIMEOUT_MS) closeTouchMenu(false);
}
#endif

static String   g_resetReason;        // why the chip last reset (diagnostics)
static bool     g_safeMode = false;   // last reset was an exception -> don't re-enter the crash
static char     g_epcStr[16] = "";
static char     g_addrStr[16] = "";
static int g_lastBr = -1;        // last effective brightness written (-1 = none yet)
#if HAS_LDR
static uint32_t g_lastAutoBr = 0;
static uint8_t  g_ldrCache   = DEFAULT_BRIGHTNESS;   // last LDR reading (2 s cadence)
#endif

// Single brightness resolver: night mode overrides auto-brightness overrides the
// manual level. Only writes the PWM when the effective target changes.
static uint8_t appEffectiveBrightness() {
  if (clockNightActive()) return g_settings.clock.nightLevel;
#if HAS_LDR
  if (g_settings.autoBrightness) {
    if (millis() - g_lastAutoBr > 2000) {
      g_lastAutoBr = millis();
      int raw = analogRead(LDR_PIN);
      g_ldrCache = (uint8_t)constrain(raw * 100 / ADC_MAX, 5, 100);
    }
    return g_ldrCache;
  }
#endif
  return g_settings.brightness;
}

void appApplyBrightness() {
  uint8_t t = appEffectiveBrightness();
  if ((int)t != g_lastBr) {
    g_lastBr = t;
    gfxSetBrightness(t, g_settings.backlightInverted);
  }
}

// Exposed to the web portal (/api/status) so the last reset reason is visible.
const char* appResetReason() { return g_resetReason.c_str(); }


// Called by the web portal after settings are applied: re-init every mode and
// force a fresh repaint so a mode/URL/symbol change takes effect immediately.
void appInvalidate() {
  for (size_t i = 0; i < kModeCount; i++) kModes[i]->invalidate(g_settings);
}

// Immediate app switch for the web UI. Unlike saving the full settings form,
// this also closes any local menu/notification so the requested app is visible
// on the very next display tick. The selected app remains the boot default.
bool appActivateMode(uint8_t mode) {
  bool supported = mode == MODE_CAROUSEL;
  for (size_t i = 0; i < kModeCount; i++) {
    if (kModes[i]->modeConst() == mode) {
      supported = true;
      break;
    }
  }
  if (!supported) return false;

#if WITH_NOTIFY
  g_notifyMode.dismiss();
#endif
#if HAS_TOUCH_BUTTON
  g_touchMenuOpen = false;
  g_settingsCardOpen = false;
#endif
  g_settings.mode = mode;
  saveSettings(g_settings);
  if (mode == MODE_CAROUSEL) g_carIdx = 0;
  g_carSwitch = 0;

  DisplayMode* m = activeMode(g_settings);
  if (m) m->wake(g_settings);
  return true;
}

static void bootProgress(const char* msg) {
  gfxBoot("SmallTV", msg);
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println(FW_NAME " " FW_VERSION);

  // Capture why we (re)booted. On a reboot loop this is the key clue, and the
  // device's UART isn't exposed — so we also show it on screen below. On the
  // ESP8266 we also keep the crash PC (epc1) for addr2line decoding; the
  // ESP32-C2 (RISC-V) doesn't expose it, so epc/addr come back empty there.
  PlatformReset pr = platformResetInfo();
  Serial.print("[boot] reset reason: ");
  Serial.println(pr.reason);

  if (pr.wasCrash) {
    g_safeMode = true;                   // crashed last boot -> stay out of the crash path
    strlcpy(g_epcStr,  pr.epc,  sizeof(g_epcStr));
    strlcpy(g_addrStr, pr.addr, sizeof(g_addrStr));
    char rich[80];
    snprintf(rich, sizeof(rich), "%s epc %s addr %s", pr.reason.c_str(),
             g_epcStr[0] ? g_epcStr : "-", g_addrStr[0] ? g_addrStr : "-");
    g_resetReason = rich;
  } else {
    g_resetReason = pr.reason;
  }

  Serial.println("[boot] settings");
  settingsBegin();
  loadSettings(g_settings);

  Serial.println("[boot] display");
  gfxBegin(g_settings);
  gfxBoot(g_safeMode ? "Crashed" : "SmallTV", FW_VERSION);

  Serial.println("[boot] net");
  netBegin(g_settings, bootProgress);
  // Arm SNTP now that WiFi (STA) is up — but only if night mode is enabled, so a
  // ticker-only device doesn't pay the SNTP heap cost (which can starve the cash.ch
  // TLS handshake on the ESP8266). clockReapply arms it iff needed. Skipped after a
  // crash so a fault in here can't boot-loop before the web server starts (the
  // device then comes up in safe mode, OTA-recoverable, instead of needing UART).
  // ...unless a WireGuard tunnel is configured, which needs the clock and only
  // exists on an ESP32 where the heap argument for the skip does not apply.
  if (!g_safeMode || wgNeedsClock(g_settings)) clockReapply(g_settings);

  // Optional WireGuard tunnel (ESP32 targets). Arms the state machine only;
  // the bring-up itself runs from loop(), so nothing here can delay the web
  // server. A crash last boot feeds the three-strikes hold that keeps a bad
  // tunnel config from locking the device out of its own web UI.
  wgBegin(g_settings, g_safeMode);

  // A GitHub update queued from the web UI runs now, before the features claim
  // the heap (the download needs a 16 KB TLS buffer that only fits at boot).
  // On success it reboots into the new image; a no-op stub on the ESP32 targets.
#if SELF_UPDATE_ENABLED
  if (otaBootRequested()) {
    Serial.println("[boot] github update");
    gfxBoot("SmallTV", "updating...");
    otaBootUpdate(g_settings);
    gfxBoot("SmallTV", "update failed");   // still here -> failed; details in the web UI
    delay(1200);
  }
#endif

  Serial.println("[boot] web");
  webPortalBegin(g_settings);

#if WITH_HA
  mqttBegin(g_settings);   // arms the client; the connect itself runs from loop()
#endif

  Serial.println("[boot] modes");
  for (size_t i = 0; i < kModeCount; i++) kModes[i]->begin(g_settings);
#if HAS_TOUCH_BUTTON
  Serial.println("[boot] touch");
  touchButtonBegin();
#endif
  Serial.println("[boot] done");

  if (netMode() == NET_AP) {
    gfxApInfo(g_settings.apSsid.c_str(), g_settings.apPass.c_str(), netIP().c_str());
  } else if (g_safeMode) {
    // Last boot crashed: show the crash address (persistent) and keep the web
    // server up for OTA recovery — don't enter the render path that crashed.
    gfxCrash(g_epcStr, g_addrStr, netIP().c_str());
  } else {
    // Show which network we joined and how to reach the web UI, long enough to read.
    gfxStaInfo(netSSID().c_str(), netIP().c_str(), g_settings.hostname.c_str());
    delay(3500);
  }
}

void loop() {
  netLoop();
  webPortalLoop();

  if (webPortalRebootDue()) {
    delay(120);
    ESP.restart();
  }

  // Before the safe-mode return on purpose: if the crash had nothing to do with
  // the tunnel, remote access survives it, and if it did, the three-strikes hold
  // stops the retries by itself.
  wgService(g_settings);

  if (g_safeMode) {
    delay(5);
    return;  // crashed last boot: web UI stays up for OTA recovery, no rendering
  }

#if WITH_HA
  // After the safe-mode return on purpose: a fault in here (e.g. a malformed
  // retained screen that re-arrives on every connect) must not boot-loop the
  // device past its own recovery page. Self-gates on WiFi STA + broker config.
  mqttLoop();
#endif

  if (netMode() == NET_AP) {
    delay(5);
    return;  // setup mode: AP info stays on screen
  }

  // --- STA mode: the active feature fetches + renders itself ---

  // Night-mode state machine (NTP-trust gate), then apply the effective brightness
  // (night override / auto-brightness / manual level).
  clockService(g_settings);
  appApplyBrightness();

#if WITH_NOTIFY
  static bool wasNotifying = false;
#endif

#if HAS_TOUCH_BUTTON
  const TouchButtonEvent touchEvent = touchButtonPoll();
  if (g_touchMenuOpen) {
    serviceTouchMenu(touchEvent);
    delay(5);
    return;
  }

  if (g_settingsCardOpen) {
    serviceSettingsCard(touchEvent);
    delay(5);
    return;
  }

  if (touchEvent == TOUCH_EVENT_LONG) {
#if WITH_NOTIFY
    if (g_notifyMode.active()) {
      wasNotifying = true;
      g_notifyMode.dismiss();
    }
#endif
    openTouchMenu();
    delay(5);
    return;
  }

#if WITH_NOTIFY
  // A tap has one useful, low-risk action on the normal screen: acknowledge an
  // attention overlay. Otherwise it does nothing, so brushing the case cannot
  // unexpectedly switch apps.
  if (touchEvent == TOUCH_EVENT_SHORT && g_notifyMode.active()) {
    wasNotifying = true;
    g_notifyMode.dismiss();
  }
#endif
#endif

  // On expiry the carousel dwell is credited back the time it was hidden, so it
  // resumes on the same feature with the same remaining slice.
#if WITH_NOTIFY
  if (g_notifyMode.active()) {
    wasNotifying = true;
    g_notifyMode.service(g_settings);
    delay(5);
    return;
  }
  bool restore = wasNotifying;
  if (wasNotifying) {
    wasNotifying = false;
    if (g_carSwitch) g_carSwitch += g_notifyMode.heldMs();
  }
#else
  const bool restore = false;
#endif

  DisplayMode* m = activeMode(g_settings);
  if (m) {
    if (restore) m->wake(g_settings);
    m->service(g_settings);
  }

  delay(5);
}
