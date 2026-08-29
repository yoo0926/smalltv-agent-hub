// TouchButton.h — calibrated one-button input for the SmallTV Pro's ESP32 T9.
#pragma once
#include <Arduino.h>

enum TouchButtonEvent : uint8_t {
  TOUCH_EVENT_NONE = 0,
  TOUCH_EVENT_SHORT,
  TOUCH_EVENT_LONG,
};

void             touchButtonBegin();
TouchButtonEvent touchButtonPoll();

// Diagnostics exposed through /api/status. These are also useful for tuning a
// particular unit without needing the SmallTV Pro's unexposed UART.
bool        touchButtonAvailable();
bool        touchButtonPressed();
uint32_t    touchButtonRaw();
uint32_t    touchButtonBaseline();
uint32_t    touchButtonTriggerDelta();
const char* touchButtonLastEvent();
