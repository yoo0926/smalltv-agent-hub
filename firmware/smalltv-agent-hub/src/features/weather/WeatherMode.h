// WeatherMode.h — current conditions and compact multi-day forecast.
#pragma once
#include "Mode.h"
#include "config.h"

#if WITH_WEATHER
class WeatherMode : public DisplayMode {
 public:
  const char* id() const override { return "weather"; }
  uint8_t modeConst() const override { return MODE_WEATHER; }

  void begin(const Settings& s) override;
  void service(const Settings& s) override;
  void invalidate(const Settings& s) override;
  void wake(const Settings& s) override { needRender_ = true; }

 private:
  void render(const Settings& s);

  uint32_t renderedRevision_ = 0xFFFFFFFF;
  bool needRender_ = true;
};

extern WeatherMode g_weatherMode;
#endif
