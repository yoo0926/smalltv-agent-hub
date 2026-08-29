// WeatherData.h — compact runtime snapshot for the weather screen.
#pragma once
#include <Arduino.h>
#include "config.h"

struct WeatherDay {
  char    label[6];
  int16_t high;
  int16_t low;
  uint8_t code;
  uint8_t rainPct;
};

struct WeatherData {
  char    city[WEATHER_LABEL_LEN];
  int16_t temperature;
  int16_t feelsLike;
  int16_t wind;
  uint8_t humidity;
  uint8_t code;
  bool    isDay;
  bool    valid;
  bool    error;
  uint32_t lastOkMs;
  WeatherDay days[WEATHER_FORECAST_DAYS];
  uint8_t dayCount;

  void clear() {
    city[0] = 0;
    temperature = feelsLike = wind = 0;
    humidity = code = 0;
    isDay = true;
    valid = error = false;
    lastOkMs = 0;
    dayCount = 0;
    for (uint8_t i = 0; i < WEATHER_FORECAST_DAYS; i++) {
      days[i].label[0] = 0;
      days[i].high = days[i].low = 0;
      days[i].code = days[i].rainPct = 0;
    }
  }
};
