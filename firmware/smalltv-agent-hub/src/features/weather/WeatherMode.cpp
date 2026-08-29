#include "WeatherMode.h"

#if WITH_WEATHER
#include <Arduino_GFX_Library.h>
#include "Gfx.h"
#include "WeatherClient.h"

WeatherMode g_weatherMode;

namespace {
const char* conditionName(uint8_t code) {
  if (code == 0) return "Clear";
  if (code <= 2) return "Partly cloudy";
  if (code == 3) return "Cloudy";
  if (code == 45 || code == 48) return "Fog";
  if (code >= 51 && code <= 57) return "Drizzle";
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "Rain";
  if ((code >= 71 && code <= 77) || (code >= 85 && code <= 86)) return "Snow";
  if (code >= 95) return "Storm";
  return "Weather";
}

void drawCloud(Arduino_GFX* gfx, int x, int y, int s, uint16_t color) {
  gfx->fillCircle(x, y + 5 * s, 7 * s, color);
  gfx->fillCircle(x + 9 * s, y, 9 * s, color);
  gfx->fillCircle(x + 19 * s, y + 5 * s, 7 * s, color);
  gfx->fillRect(x - 1 * s, y + 5 * s, 22 * s, 8 * s, color);
}

void drawWeatherIcon(Arduino_GFX* gfx, uint8_t code, bool isDay, int x, int y, int s) {
  const bool rain = (code >= 51 && code <= 67) || (code >= 80 && code <= 82) || code >= 95;
  const bool snow = (code >= 71 && code <= 77) || (code >= 85 && code <= 86);
  const bool cloudy = code >= 1;

  if (!cloudy || code <= 2) {
    uint16_t sun = isDay ? C_YELLOW : C_GRAY;
    gfx->fillCircle(x + 10 * s, y + 9 * s, 7 * s, sun);
    for (int a = 0; a < 8; a++) {
      float rad = a * 0.785398f;
      int x1 = x + 10 * s + (int)(cosf(rad) * 11 * s);
      int y1 = y + 9 * s + (int)(sinf(rad) * 11 * s);
      int x2 = x + 10 * s + (int)(cosf(rad) * 15 * s);
      int y2 = y + 9 * s + (int)(sinf(rad) * 15 * s);
      gfx->drawLine(x1, y1, x2, y2, sun);
    }
  }

  if (cloudy) drawCloud(gfx, x + (code <= 2 ? 9 * s : 0), y + 8 * s, s, C_WHITE);
  if (rain) {
    for (int i = 0; i < 3; i++)
      gfx->drawLine(x + (5 + i * 8) * s, y + 25 * s, x + (2 + i * 8) * s, y + 31 * s, C_BLUE);
  } else if (snow) {
    for (int i = 0; i < 3; i++) {
      int sx = x + (5 + i * 8) * s, sy = y + 28 * s;
      gfx->drawLine(sx - 2 * s, sy, sx + 2 * s, sy, C_WHITE);
      gfx->drawLine(sx, sy - 2 * s, sx, sy + 2 * s, C_WHITE);
    }
  }
  if (code >= 95) {
    gfx->fillTriangle(x + 14 * s, y + 23 * s, x + 8 * s, y + 34 * s,
                      x + 14 * s, y + 31 * s, C_YELLOW);
  }
}
}  // namespace

void WeatherMode::begin(const Settings& s) {
  weatherInit(s);
  needRender_ = true;
}

void WeatherMode::invalidate(const Settings& s) {
  weatherInit(s);
  needRender_ = true;
}

void WeatherMode::service(const Settings& s) {
  weatherService(s);
  uint32_t rev = weatherRevision();
  if (needRender_ || rev != renderedRevision_) {
    renderedRevision_ = rev;
    needRender_ = false;
    render(s);
  }
}

void WeatherMode::render(const Settings& s) {
  Arduino_GFX* gfx = gfxDev();
  if (!gfx) return;
  const WeatherData& d = weatherData();
  gfx->fillScreen(C_BLACK);

  gfxDrawCentered(d.city[0] ? d.city : "Weather", 7,
                  gfxFitSize(d.city[0] ? d.city : "Weather", 232, 3), C_WHITE);

  if (!d.valid) {
    gfxDrawCentered(weatherStage(), 92, 2, d.error ? C_RED : C_GRAY);
    char retry[24];
    uint32_t sec = weatherRetryInSec();
    if (sec) snprintf(retry, sizeof(retry), "retry in %lus", (unsigned long)sec);
    else strlcpy(retry, "fetching forecast", sizeof(retry));
    gfxDrawCentered(retry, 124, 2, C_DGRAY);
    gfxDrawCentered("Open-Meteo", 224, 1, C_DGRAY);
    return;
  }

  drawWeatherIcon(gfx, d.code, d.isDay, 28, 48, 2);

  char temp[16];
  snprintf(temp, sizeof(temp), "%d %c", d.temperature, s.weather.fahrenheit ? 'F' : 'C');
  gfx->setTextSize(4);
  gfx->setTextColor(C_WHITE);
  gfx->setCursor(105, 49);
  gfx->print(temp);
  gfxDrawCentered(conditionName(d.code), 91, 2, C_GRAY);

  char detail[38];
  snprintf(detail, sizeof(detail), "Feels %d  Hum %u%%  Wind %d",
           d.feelsLike, d.humidity, d.wind);
  gfxDrawCentered(detail, 114, 1, C_DGRAY);
  gfx->drawFastHLine(8, 132, TFT_WIDTH - 16, C_DGRAY);

  // Tomorrow onward: current conditions already represent today, so use up to
  // the next three daily entries as the compact forecast strip.
  uint8_t cards = d.dayCount > 1 ? min((uint8_t)3, (uint8_t)(d.dayCount - 1)) : 0;
  for (uint8_t i = 0; i < cards; i++) {
    const WeatherDay& day = d.days[i + 1];
    int x = 4 + i * 79;
    gfx->drawRect(x, 140, 74, 78, C_DGRAY);
    gfx->setTextSize(1);
    gfx->setTextColor(C_GRAY);
    gfx->setCursor(x + (74 - gfxTextW(day.label, 1)) / 2, 145);
    gfx->print(day.label);
    drawWeatherIcon(gfx, day.code, true, x + 23, 158, 1);
    char range[16];
    snprintf(range, sizeof(range), "%d/%d", day.high, day.low);
    gfx->setTextSize(1);
    gfx->setTextColor(C_WHITE);
    gfx->setCursor(x + (74 - gfxTextW(range, 1)) / 2, 195);
    gfx->print(range);
    char rain[10];
    snprintf(rain, sizeof(rain), "%u%% rain", day.rainPct);
    gfx->setTextColor(C_BLUE);
    gfx->setCursor(x + (74 - gfxTextW(rain, 1)) / 2, 207);
    gfx->print(rain);
  }
  if (!cards) gfxDrawCentered("Forecast unavailable", 174, 1, C_DGRAY);

  if (d.error) gfx->fillCircle(6, 6, 3, C_RED);
  gfx->setTextSize(1);
  gfx->setTextColor(C_DGRAY);
  gfx->setCursor(TFT_WIDTH - gfxTextW("Open-Meteo", 1) - 4, 229);
  gfx->print("Open-Meteo");
}

#endif
