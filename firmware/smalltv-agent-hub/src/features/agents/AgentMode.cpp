#include "AgentMode.h"

#include <ArduinoJson.h>
#include <Arduino_GFX_Library.h>
#include <string.h>

#include "Gfx.h"

AgentMode g_agentMode;

static AgentState parseState(const char* value) {
  if (!strcmp(value, "working"))     return AGENT_WORKING;
  if (!strcmp(value, "needs_input")) return AGENT_NEEDS_INPUT;
  if (!strcmp(value, "done"))        return AGENT_DONE;
  if (!strcmp(value, "failed"))      return AGENT_FAILED;
  return AGENT_IDLE;
}

static const char* stateLabel(AgentState state) {
  switch (state) {
    case AGENT_WORKING:     return "WORKING";
    case AGENT_NEEDS_INPUT: return "NEEDS YOU";
    case AGENT_DONE:        return "DONE";
    case AGENT_FAILED:      return "FAILED";
    default:                return "IDLE";
  }
}

static uint16_t stateColor(AgentState state) {
  switch (state) {
    case AGENT_WORKING:     return C_BLUE;
    case AGENT_NEEDS_INPUT: return C_YELLOW;
    case AGENT_DONE:        return C_GREEN;
    case AGENT_FAILED:      return C_RED;
    default:                return C_GRAY;
  }
}

static void copyPrintable(char* dst, size_t size, const char* src) {
  size_t n = 0;
  for (; src && *src && n + 1 < size; src++) {
    unsigned char c = (unsigned char)*src;
    if (c >= 0x20 && c <= 0x7e) dst[n++] = (char)c;
  }
  dst[n] = '\0';
}

bool AgentMode::apply(const String& body) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) return false;
  JsonArrayConst agents = doc["agents"].as<JsonArrayConst>();
  if (agents.isNull()) return false;

  AgentRow next[AGENT_MAX_ROWS] = {};
  uint8_t nextCount = 0;
  for (JsonObjectConst item : agents) {
    if (nextCount >= AGENT_MAX_ROWS) break;
    const char* label = item["label"] | item["workspace"] | "agent";
    const char* tool  = item["agent"] | "agent";
    const char* state = item["state"] | "idle";
    copyPrintable(next[nextCount].label, sizeof(next[nextCount].label), label);
    copyPrintable(next[nextCount].tool, sizeof(next[nextCount].tool), tool);
    if (!next[nextCount].label[0]) strlcpy(next[nextCount].label, "agent", sizeof(next[nextCount].label));
    if (!next[nextCount].tool[0]) strlcpy(next[nextCount].tool, "agent", sizeof(next[nextCount].tool));
    next[nextCount].state = parseState(state);
    nextCount++;
  }

  memcpy(rows_, next, sizeof(rows_));
  count_ = nextCount;
  updatedMs_ = millis();
  lastAgeRenderMs_ = 0;
  dirty_ = true;
  return true;
}

uint8_t AgentMode::countState(AgentState state) const {
  uint8_t n = 0;
  for (uint8_t i = 0; i < count_; i++) if (rows_[i].state == state) n++;
  return n;
}

uint32_t AgentMode::updatedAgoSec() const {
  return updatedMs_ ? (millis() - updatedMs_) / 1000UL : 0;
}

void AgentMode::begin(const Settings&) { dirty_ = true; }
void AgentMode::invalidate(const Settings&) { dirty_ = true; }
void AgentMode::wake(const Settings&) { dirty_ = true; }

void AgentMode::service(const Settings&) {
  // Repaint the age footer once per minute; pushes repaint immediately.
  if (updatedMs_ && millis() - lastAgeRenderMs_ >= 60000UL) dirty_ = true;
  if (!dirty_) return;
  render();
  dirty_ = false;
  lastAgeRenderMs_ = millis();
}

void AgentMode::render() {
  Arduino_GFX* gfx = gfxDev();
  if (!gfx) return;
  gfx->fillScreen(C_BLACK);

  gfxDrawCentered("AGENT HUB", 8, 3, C_WHITE);
  gfx->drawFastHLine(8, 38, TFT_WIDTH - 16, C_DGRAY);

  if (!count_) {
    gfxDrawCentered("WAITING FOR", 88, 2, C_GRAY);
    gfxDrawCentered("CONDUCTOR", 116, 3, C_WHITE);
    gfxDrawCentered("No task events yet", 164, 1, C_DGRAY);
  } else {
    const int firstY = 48;
    const int rowH = 42;
    for (uint8_t i = 0; i < count_; i++) {
      const AgentRow& row = rows_[i];
      const int y = firstY + i * rowH;
      const uint16_t color = stateColor(row.state);

      gfx->fillCircle(17, y + 12, 8, color);
      if (row.state == AGENT_DONE) {
        gfx->drawLine(12, y + 12, 16, y + 16, C_BLACK);
        gfx->drawLine(16, y + 16, 22, y + 8, C_BLACK);
      } else if (row.state == AGENT_FAILED) {
        gfx->drawLine(13, y + 8, 21, y + 16, C_BLACK);
        gfx->drawLine(21, y + 8, 13, y + 16, C_BLACK);
      } else if (row.state == AGENT_NEEDS_INPUT) {
        gfx->setTextSize(1);
        gfx->setTextColor(C_BLACK);
        gfx->setCursor(15, y + 8);
        gfx->print("!");
      }

      gfx->setTextSize(gfxFitSize(row.label, 198, 2));
      gfx->setTextColor(C_WHITE);
      gfx->setCursor(34, y + 2);
      gfx->print(row.label);

      char detail[28];
      snprintf(detail, sizeof(detail), "%s  %s", row.tool, stateLabel(row.state));
      gfx->setTextSize(1);
      gfx->setTextColor(color);
      gfx->setCursor(35, y + 23);
      gfx->print(detail);
    }
  }

  char footer[32];
  if (!updatedMs_) {
    strlcpy(footer, "local push ready", sizeof(footer));
  } else {
    uint32_t age = updatedAgoSec();
    if (age < 60) snprintf(footer, sizeof(footer), "updated %lus ago", (unsigned long)age);
    else          snprintf(footer, sizeof(footer), "updated %lum ago", (unsigned long)(age / 60));
  }
  gfxDrawCentered(footer, 228, 1, C_DGRAY);
}
