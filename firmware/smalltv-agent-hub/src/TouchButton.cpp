#include "TouchButton.h"
#include "config.h"

#if HAS_TOUCH_BUTTON

namespace {
constexpr uint32_t kSampleMs        = 20;
// Asymmetric on purpose. A press needs the longer guard so brushing the case
// cannot act; a release needs the shorter one because the finger-off gap inside
// a deliberate double tap can be very brief, and swallowing it merges the two
// taps into a single press that the menu then reads as one step forward.
constexpr uint32_t kPressDebounceMs   = 60;
// 45, not 30: the finger-off gap inside a measured double tap is around 100 ms
// (gap 200 ms minus a ~96 ms press), so this keeps a 2x margin while staying far
// enough above the noise floor that one press cannot break into two taps.
constexpr uint32_t kReleaseDebounceMs = 45;
constexpr uint8_t  kCalibrationReads = 24;

// The sampler runs as its own FreeRTOS task rather than from loop(). A tap is
// only 70-170 ms of contact, and loop() was measured stalling for 233 ms inside
// server.handleClient() — a single HTTP request on a weak link blocks it for
// ~100 ms, which is long enough to miss a whole tap. The scheduler keeps this
// task running through all of that, so detection no longer depends on what the
// rest of the firmware happens to be doing. Events cross to loop() through a
// queue so none are dropped while it is busy.
QueueHandle_t g_events = nullptr;
TaskHandle_t  g_task = nullptr;

uint32_t g_raw = 0;
uint32_t g_baseline = 0;
// The baseline in 1/64 counts. The obvious integer form,
// `baseline = (baseline * 63 + raw) / 64`, is a one-way ratchet: reaching
// baseline+1 needs raw >= baseline + 64, which the tracking gate below forbids,
// so it can only ever move DOWN — a full count per sample, 64x faster than the
// intended time constant. Carrying the fraction makes both directions move at
// the rate the filter is supposed to have.
uint64_t g_baselineQ6 = 0;
uint32_t g_triggerDelta = 0;
uint32_t g_releaseDelta = 0;
uint32_t g_candidateMs = 0;
uint32_t g_pressedMs = 0;
bool     g_candidate = false;
bool     g_pressed = false;
bool     g_longSent = false;
const char* g_lastEvent = "none";
// How long the finger was off between the previous tap and this one. This, not
// the interval between taps, is what a double tap actually controls: measured on
// hardware it is 80 ms every time, while the interval also carries however long
// the button happened to be held (100-300 ms), which is what made the gesture
// fail whenever it was pressed a little longer.
uint32_t g_releasedMs = 0;
uint32_t g_lastIdleMs = 0;


// Longest interval ever seen between two calls to touchButtonPoll(). The sampler
// needs to run every 20 ms to see a tap; if something in loop() blocks for
// longer than a finger is down, the tap is simply never observed. This says
// whether that is happening, instead of leaving it a theory.
uint32_t g_maxPollGap = 0;

uint32_t deltaFromBaseline(uint32_t value) {
  return value > g_baseline ? value - g_baseline : g_baseline - value;
}

uint32_t percentWithFloor(uint32_t value, uint8_t percent, uint32_t floorValue) {
  uint32_t scaled = (uint32_t)(((uint64_t)value * percent) / 100U);
  return scaled > floorValue ? scaled : floorValue;
}

void setBaseline(uint32_t value) {
  g_baseline = value ? value : 1;
  g_baselineQ6 = (uint64_t)g_baseline << 6;
}

void updateThresholds() {
  // A real touch normally moves the reading much farther than 8%. The lower
  // release threshold adds hysteresis so a finger near the edge cannot chatter.
  g_triggerDelta = percentWithFloor(g_baseline, 8, 6);
  g_releaseDelta = percentWithFloor(g_baseline, 4, 3);
}
}  // namespace

TouchButtonEvent sampleOnce();   // defined below; the task is the only caller

namespace {
void touchTask(void*) {
  TickType_t wake = xTaskGetTickCount();
  for (;;) {
    const TouchButtonEvent event = sampleOnce();
    if (event != TOUCH_EVENT_NONE && g_events) xQueueSend(g_events, &event, 0);
    vTaskDelayUntil(&wake, pdMS_TO_TICKS(kSampleMs));
  }
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
  setBaseline(count ? (uint32_t)(total / count) : 1);
  g_raw = g_baseline;
  updateThresholds();

  Serial.printf("[touch] pin=%d baseline=%lu trigger=%lu\n", TOUCH_BUTTON_PIN,
                (unsigned long)g_baseline, (unsigned long)g_triggerDelta);

  g_events = xQueueCreate(8, sizeof(TouchButtonEvent));
  if (!g_events) return;   // no queue: touchButtonPoll() just reports nothing
  // Priority above the Arduino loop task so a sample is never postponed behind
  // it, and on the same core so it does not contend with the WiFi stack.
  xTaskCreatePinnedToCore(touchTask, "touch", 3072, nullptr, 2, &g_task, 1);
}

// One sampling pass. Runs on the touch task, never on loop().
TouchButtonEvent sampleOnce() {
  const uint32_t now = millis();
  {
    static uint32_t lastCall = 0;
    if (lastCall && now - lastCall > g_maxPollGap) g_maxPollGap = now - lastCall;
    lastCall = now;
  }
  g_raw = touchRead(TOUCH_BUTTON_PIN);
  if (!g_raw || !g_baseline) return TOUCH_EVENT_NONE;

  const uint32_t delta = deltaFromBaseline(g_raw);
  const bool sensed = g_pressed ? delta >= g_releaseDelta : delta >= g_triggerDelta;

  if (sensed != g_candidate) {
    g_candidate = sensed;
    g_candidateMs = now;
  }

  const uint32_t debounce = g_candidate ? kPressDebounceMs : kReleaseDebounceMs;
  if (g_candidate != g_pressed && now - g_candidateMs >= debounce) {
    g_pressed = g_candidate;
    if (g_pressed) {
      g_lastIdleMs = g_releasedMs ? now - g_releasedMs : 0;
      g_pressedMs = now;
      g_longSent = false;
    } else {
      // Stamped on every release, including one that already reported itself as
      // a long press: the next tap measures its idle time from here, and a
      // stale stamp would make that tap look like half of a double.
      const bool wasTap = !g_longSent;
      g_releasedMs = now;
      if (wasTap) {
        g_lastEvent = "short";
        return TOUCH_EVENT_SHORT;
      }
    }
  }

  if (g_pressed && !g_longSent && now - g_pressedMs >= TOUCH_LONG_PRESS_MS) {
    g_longSent = true;
    g_lastEvent = "long";
    return TOUCH_EVENT_LONG;
  }

  // Self-heal a latched button. Release needs the reading back inside the
  // release band, so a baseline that has drifted outside it can never let go on
  // its own: the button then reads as permanently held and every tap is lost.
  // A press this long is not a finger, so take the reading in front of us as
  // the new rest state.
  if (g_pressed && now - g_pressedMs >= TOUCH_STUCK_RESET_MS) {
    setBaseline(g_raw);
    updateThresholds();
    g_pressed = false;
    g_candidate = false;
    g_longSent = false;
    g_candidateMs = now;
    g_lastEvent = "stuck-reset";
    return TOUCH_EVENT_NONE;
  }

  // Follow slow temperature/humidity drift only while confidently untouched.
  // Updating by 1/64 per sample is deliberately too slow to swallow a tap.
  if (!g_pressed && !g_candidate && delta < g_releaseDelta) {
    const int64_t target = (int64_t)g_raw << 6;
    g_baselineQ6 = (uint64_t)((int64_t)g_baselineQ6 + (target - (int64_t)g_baselineQ6) / 64);
    g_baseline = (uint32_t)(g_baselineQ6 >> 6);
    if (!g_baseline) g_baseline = 1;
    updateThresholds();
  }
  return TOUCH_EVENT_NONE;
}

// loop() side: hand over whatever the sampler has seen since the last call.
TouchButtonEvent touchButtonPoll() {
  TouchButtonEvent event = TOUCH_EVENT_NONE;
  if (g_events) xQueueReceive(g_events, &event, 0);
  return event;
}

bool touchButtonAvailable() { return g_baseline > 1; }
bool touchButtonPressed() { return g_pressed; }
uint32_t touchButtonRaw() { return g_raw; }
uint32_t touchButtonBaseline() { return g_baseline; }
uint32_t touchButtonTriggerDelta() { return g_triggerDelta; }
const char* touchButtonLastEvent() { return g_lastEvent; }
uint32_t touchButtonLastIdleMs() { return g_lastIdleMs; }
uint32_t touchButtonMaxPollGapMs() { return g_maxPollGap; }

#else

void touchButtonBegin() {}
TouchButtonEvent touchButtonPoll() { return TOUCH_EVENT_NONE; }
bool touchButtonAvailable() { return false; }
bool touchButtonPressed() { return false; }
uint32_t touchButtonRaw() { return 0; }
uint32_t touchButtonBaseline() { return 0; }
uint32_t touchButtonTriggerDelta() { return 0; }
const char* touchButtonLastEvent() { return "none"; }
uint32_t touchButtonLastIdleMs() { return 0; }
uint32_t touchButtonMaxPollGapMs() { return 0; }

#endif
