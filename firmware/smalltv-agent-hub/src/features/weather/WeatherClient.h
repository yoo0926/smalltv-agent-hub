// WeatherClient.h — Open-Meteo city lookup and compact forecast fetcher.
#pragma once
#include <Arduino.h>
#include "Settings.h"
#include "WeatherData.h"

void weatherInit(const Settings& s);
void weatherService(const Settings& s);
void weatherForceRefresh();

const WeatherData& weatherData();
uint32_t weatherRevision();
const char* weatherStage();
int weatherLastHttp();
uint32_t weatherRetryInSec();
