#include "TouchButton.h"
#include "config.h"

#if HAS_TOUCH_BUTTON

namespace {
constexpr uint32_t kSampleMs        = 20;
constexpr uint32_t kDebounceMs      = 60;
constexpr uint8_t  kCalibrationReads = 24;

uint32_t g_raw = 0;
uint32_t g_baseline = 0;
uint32_t g_triggerDelta = 0;
uint32_t g_releaseDelta = 0;
uint32_t g_lastSampleMs = 0;
uint32_t g_candidateMs = 0;
uint32_t g_pressedMs = 0;
bool     g_candidate = false;
bool     g_pressed = false;
bool     g_longSent = false;
const char* g_lastEvent = "none";

uint32_t deltaFromBaseline(uint32_t value) {
  return value > g_baseline ? value - g_baseline : g_baseline - value;
}

uint32_t percentWithFloor(uint32_t value, uint8_t percent, uint32_t floorValue) {
  uint32_t scaled = (uint32_t)(((uint64_t)value * percent) / 100U);
  return scaled > floorValue ? scaled : floorValue;
}

void updateThresholds() {
  // A real touch normally moves the reading much farther than 8%. The lower
  // release threshold adds hysteresis so a finger near the edge cannot chatter.
  g_triggerDelta = percentWithFloor(g_baseline, 8, 6);
  g_releaseDelta = percentWithFloor(g_baseline, 4, 3);
}
}  // namespace

void touchButtonBegin() {
  // The first call initializes the ESP32 touch peripheral. Leave it a moment,
  // then average several untouched samples to absorb device-to-device variance.
  (void)touchRead(TOUCH_BUTTON_PIN);
  delay(30);

  uint64_t total = 0;
  uint8_t count = 0;
  for (uint8_t i = 0; i < kCalibrationReads; i++) {
    uint32_t value = touchRead(TOUCH_BUTTON_PIN);
    if (value) {
      total += value;
      count++;
    }
    delay(8);
  }
  g_baseline = count ? (uint32_t)(total / count) : 1;
  g_raw = g_baseline;
  updateThresholds();
  g_lastSampleMs = millis();

  Serial.printf("[touch] pin=%d baseline=%lu trigger=%lu\n", TOUCH_BUTTON_PIN,
                (unsigned long)g_baseline, (unsigned long)g_triggerDelta);
}

TouchButtonEvent touchButtonPoll() {
  const uint32_t now = millis();
  if (now - g_lastSampleMs < kSampleMs) return TOUCH_EVENT_NONE;
  g_lastSampleMs = now;
  g_raw = touchRead(TOUCH_BUTTON_PIN);
  if (!g_raw || !g_baseline) return TOUCH_EVENT_NONE;

  const uint32_t delta = deltaFromBaseline(g_raw);
  const bool sensed = g_pressed ? delta >= g_releaseDelta : delta >= g_triggerDelta;

  if (sensed != g_candidate) {
    g_candidate = sensed;
    g_candidateMs = now;
  }

  if (g_candidate != g_pressed && now - g_candidateMs >= kDebounceMs) {
    g_pressed = g_candidate;
    if (g_pressed) {
      g_pressedMs = now;
      g_longSent = false;
    } else if (!g_longSent) {
      g_lastEvent = "short";
      return TOUCH_EVENT_SHORT;
    }
  }

  if (g_pressed && !g_longSent && now - g_pressedMs >= TOUCH_LONG_PRESS_MS) {
    g_longSent = true;
    g_lastEvent = "long";
    return TOUCH_EVENT_LONG;
  }

  // Follow slow temperature/humidity drift only while confidently untouched.
  // Updating by 1/64 per sample is deliberately too slow to swallow a tap.
  if (!g_pressed && !g_candidate && delta < g_releaseDelta) {
    g_baseline = (uint32_t)(((uint64_t)g_baseline * 63U + g_raw) / 64U);
    updateThresholds();
  }
  return TOUCH_EVENT_NONE;
}

bool touchButtonAvailable() { return g_baseline > 1; }
bool touchButtonPressed() { return g_pressed; }
uint32_t touchButtonRaw() { return g_raw; }
uint32_t touchButtonBaseline() { return g_baseline; }
uint32_t touchButtonTriggerDelta() { return g_triggerDelta; }
const char* touchButtonLastEvent() { return g_lastEvent; }

#else

void touchButtonBegin() {}
TouchButtonEvent touchButtonPoll() { return TOUCH_EVENT_NONE; }
bool touchButtonAvailable() { return false; }
bool touchButtonPressed() { return false; }
uint32_t touchButtonRaw() { return 0; }
uint32_t touchButtonBaseline() { return 0; }
uint32_t touchButtonTriggerDelta() { return 0; }
const char* touchButtonLastEvent() { return "none"; }

#endif
