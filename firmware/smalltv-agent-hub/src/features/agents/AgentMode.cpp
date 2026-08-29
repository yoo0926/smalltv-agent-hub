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

static void compactLabel(const char* src, char* dst, size_t dstSize,
                         size_t maxChars) {
  if (dstSize == 0) return;
  dst[0] = '\0';
  if (!src || !src[0]) return;
  size_t len = strlen(src);
  if (len <= maxChars) {
    strlcpy(dst, src, dstSize);
    return;
  }
  size_t keep = maxChars > 2 ? maxChars - 2 : maxChars;
  if (keep >= dstSize) keep = dstSize - 1;
  memcpy(dst, src, keep);
  size_t pos = keep;
  if (maxChars > 2 && pos + 2 < dstSize) {
    dst[pos++] = '.';
    dst[pos++] = '.';
  }
  dst[pos] = '\0';
}

static void ageLabel(uint32_t updatedMs, char* out, size_t size, bool verbose) {
  if (!updatedMs) {
    strlcpy(out, verbose ? "local push ready" : "ready", size);
    return;
  }
  uint32_t age = (millis() - updatedMs) / 1000UL;
  if (age < 60)
    snprintf(out, size, verbose ? "updated %lus ago" : "%lus",
             (unsigned long)age);
  else if (age < 3600)
    snprintf(out, size, verbose ? "updated %lum ago" : "%lum",
             (unsigned long)(age / 60));
  else
    snprintf(out, size, verbose ? "updated %luh ago" : "%luh",
             (unsigned long)(age / 3600));
}

static void drawStateIcon(Arduino_GFX* gfx, int cx, int cy, int radius,
                          AgentState state) {
  const uint16_t color = stateColor(state);
  gfx->fillCircle(cx, cy, radius, color);
  const uint16_t ink = (state == AGENT_NEEDS_INPUT) ? C_BLACK : C_WHITE;
  const int d = radius / 2;
  if (state == AGENT_DONE) {
    gfx->drawLine(cx - d, cy, cx - 1, cy + d, ink);
    gfx->drawLine(cx - 1, cy + d, cx + d + 2, cy - d, ink);
  } else if (state == AGENT_FAILED) {
    gfx->drawLine(cx - d, cy - d, cx + d, cy + d, ink);
    gfx->drawLine(cx + d, cy - d, cx - d, cy + d, ink);
  } else if (state == AGENT_NEEDS_INPUT) {
    uint8_t sz = radius >= 18 ? 3 : radius >= 11 ? 2 : 1;
    gfx->setTextSize(sz);
    gfx->setTextColor(ink);
    gfx->setCursor(cx - (GFX_FONT_W * sz) / 2, cy - (GFX_FONT_H * sz) / 2);
    gfx->print("!");
  } else if (state == AGENT_WORKING) {
    gfx->fillTriangle(cx - d / 2, cy - d, cx - d / 2, cy + d,
                      cx + d, cy, ink);
  } else {
    gfx->drawFastHLine(cx - d, cy, d * 2, ink);
  }
}

static void drawHeader(Arduino_GFX* gfx, uint8_t count, uint32_t updatedMs) {
  gfx->setTextSize(2);
  gfx->setTextColor(C_WHITE);
  gfx->setCursor(6, 6);
  gfx->print("AGENT HUB");

  char age[12];
  ageLabel(updatedMs, age, sizeof(age), false);
  char meta[20];
  snprintf(meta, sizeof(meta), "%u task%s  %s", count, count == 1 ? "" : "s", age);
  gfx->setTextSize(1);
  gfx->setTextColor(C_DGRAY);
  gfx->setCursor(TFT_WIDTH - gfxTextW(meta, 1) - 5, 10);
  gfx->print(meta);
  gfx->drawFastHLine(6, 29, TFT_WIDTH - 12, C_DGRAY);
}

static void drawAgeFooter(uint32_t updatedMs) {
  char footer[32];
  ageLabel(updatedMs, footer, sizeof(footer), true);
  gfxDrawCentered(footer, 228, 1, C_DGRAY);
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

  drawHeader(gfx, count_, updatedMs_);

  if (!count_) {
    gfxDrawCentered("WAITING FOR", 82, 3, C_GRAY);
    gfxDrawCentered("CONDUCTOR", 118, 3, C_WHITE);
    gfxDrawCentered("No task events yet", 168, 2, C_DGRAY);
    drawAgeFooter(updatedMs_);
    return;
  }

  // A single Conductor session is the common desk setup. Give it a hero view
  // instead of spending most of the display on empty list rows.
  if (count_ == 1) {
    const AgentRow& row = rows_[0];
    const uint16_t color = stateColor(row.state);
    drawStateIcon(gfx, TFT_WIDTH / 2, 70, 24, row.state);

    char label[AGENT_LABEL_LEN];
    compactLabel(row.label, label, sizeof(label), 19);
    gfxDrawCentered(label, 105, gfxFitSize(label, 232, 3), C_WHITE);
    gfxDrawCentered(stateLabel(row.state), 145,
                    gfxFitSize(stateLabel(row.state), 232, 4), color);
    gfxDrawCentered(row.tool, 190, gfxFitSize(row.tool, 220, 3), C_GRAY);
    drawAgeFooter(updatedMs_);
    return;
  }

  // Two sessions still fit as generous cards with large project and state
  // text. The coloured icon makes the state scannable from across the desk.
  if (count_ == 2) {
    for (uint8_t i = 0; i < 2; i++) {
      const AgentRow& row = rows_[i];
      const uint16_t color = stateColor(row.state);
      const int y = 36 + i * 92;
      gfx->drawRoundRect(5, y, TFT_WIDTH - 10, 86, 8, C_DGRAY);
      drawStateIcon(gfx, 27, y + 42, 17, row.state);

      char label[AGENT_LABEL_LEN];
      compactLabel(row.label, label, sizeof(label), 15);
      uint8_t labelSize = gfxFitSize(label, 178, 3);
      if (labelSize < 2) labelSize = 2;
      gfx->setTextSize(labelSize);
      gfx->setTextColor(C_WHITE);
      gfx->setCursor(50, y + 10);
      gfx->print(label);

      const char* state = stateLabel(row.state);
      gfx->setTextSize(gfxFitSize(state, 178, 3));
      gfx->setTextColor(color);
      gfx->setCursor(50, y + 45);
      gfx->print(state);

      gfx->setTextSize(1);
      gfx->setTextColor(C_GRAY);
      gfx->setCursor(TFT_WIDTH - gfxTextW(row.tool, 1) - 12, y + 70);
      gfx->print(row.tool);
    }
    drawAgeFooter(updatedMs_);
    return;
  }

  // Three or four sessions use dense rows, but keep both the project name and
  // state at text size 2. Long labels are shortened instead of shrinking to the
  // barely-legible size-1 font used by the original layout.
  {
    const int firstY = 34;
    const int rowH = 47;
    for (uint8_t i = 0; i < count_; i++) {
      const AgentRow& row = rows_[i];
      const int y = firstY + i * rowH;
      const uint16_t color = stateColor(row.state);
      gfx->drawRoundRect(3, y, TFT_WIDTH - 6, 43, 6, C_DGRAY);
      gfx->fillRoundRect(3, y, 6, 43, 3, color);
      drawStateIcon(gfx, 21, y + 21, 10, row.state);

      char label[AGENT_LABEL_LEN];
      compactLabel(row.label, label, sizeof(label), 16);
      gfx->setTextSize(2);
      gfx->setTextColor(C_WHITE);
      gfx->setCursor(36, y + 3);
      gfx->print(label);

      gfx->setTextSize(2);
      gfx->setTextColor(color);
      gfx->setCursor(36, y + 23);
      gfx->print(stateLabel(row.state));

      gfx->setTextSize(1);
      gfx->setTextColor(C_GRAY);
      gfx->setCursor(TFT_WIDTH - gfxTextW(row.tool, 1) - 9, y + 27);
      gfx->print(row.tool);
    }
  }
}
