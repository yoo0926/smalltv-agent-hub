#include "WeatherClient.h"
#include "Platform.h"
#include <ArduinoJson.h>
#include <memory>
#include <math.h>

#if WITH_WEATHER

namespace {
WeatherData g_data;
String   g_cityKey;
float    g_lat = 0;
float    g_lon = 0;
bool     g_resolved = false;
uint32_t g_nextTryMs = 0;
uint32_t g_revision = 0;
int      g_lastHttp = 0;
const char* g_stage = "idle";

String urlEncode(const String& src) {
  static const char* hex = "0123456789ABCDEF";
  String out;
  for (size_t i = 0; i < src.length(); i++) {
    uint8_t c = (uint8_t)src[i];
    if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
      out += (char)c;
    } else {
      out += '%';
      out += hex[(c >> 4) & 0xF];
      out += hex[c & 0xF];
    }
  }
  return out;
}

void setDayLabel(const char* iso, char* out, size_t n) {
  int year = 0, month = 0, day = 0;
  if (!iso || sscanf(iso, "%d-%d-%d", &year, &month, &day) != 3) {
    strlcpy(out, "--", n);
    return;
  }
  snprintf(out, n, "%d/%d", month, day);
}

bool parseGeocode(Stream& stream, const Settings& s) {
  JsonDocument filter;
  JsonObject first = filter["results"][0].to<JsonObject>();
  first["name"] = true;
  first["latitude"] = true;
  first["longitude"] = true;

  JsonDocument doc;
  if (deserializeJson(doc, stream, DeserializationOption::Filter(filter))) return false;
  JsonObjectConst result = doc["results"][0];
  if (result.isNull() || !result["latitude"].is<float>() || !result["longitude"].is<float>()) return false;

  g_lat = result["latitude"].as<float>();
  g_lon = result["longitude"].as<float>();
  g_resolved = true;
  const char* label = s.weather.label.length() ? s.weather.label.c_str() : (result["name"] | s.weather.city.c_str());
  strlcpy(g_data.city, label, sizeof(g_data.city));
  return true;
}

bool parseForecast(Stream& stream) {
  JsonDocument filter;
  JsonObject current = filter["current"].to<JsonObject>();
  current["temperature_2m"] = true;
  current["apparent_temperature"] = true;
  current["is_day"] = true;
  current["weather_code"] = true;
  current["relative_humidity_2m"] = true;
  current["wind_speed_10m"] = true;
  JsonObject daily = filter["daily"].to<JsonObject>();
  daily["time"][0] = true;
  daily["weather_code"][0] = true;
  daily["temperature_2m_max"][0] = true;
  daily["temperature_2m_min"][0] = true;
  daily["precipitation_probability_max"][0] = true;

  JsonDocument doc;
  if (deserializeJson(doc, stream, DeserializationOption::Filter(filter))) return false;
  JsonObjectConst cur = doc["current"];
  if (cur.isNull() || (!cur["temperature_2m"].is<float>() && !cur["temperature_2m"].is<int>())) return false;

  g_data.temperature = (int16_t)lroundf(cur["temperature_2m"].as<float>());
  g_data.feelsLike = (int16_t)lroundf(cur["apparent_temperature"].as<float>());
  g_data.wind = (int16_t)lroundf(cur["wind_speed_10m"].as<float>());
  g_data.humidity = (uint8_t)constrain(cur["relative_humidity_2m"].as<int>(), 0, 100);
  g_data.code = (uint8_t)cur["weather_code"].as<int>();
  g_data.isDay = cur["is_day"].as<int>() != 0;

  JsonObjectConst day = doc["daily"];
  JsonArrayConst times = day["time"];
  JsonArrayConst codes = day["weather_code"];
  JsonArrayConst highs = day["temperature_2m_max"];
  JsonArrayConst lows = day["temperature_2m_min"];
  JsonArrayConst rain = day["precipitation_probability_max"];
  size_t count = times.size();
  if (count > WEATHER_FORECAST_DAYS) count = WEATHER_FORECAST_DAYS;
  g_data.dayCount = (uint8_t)count;
  for (size_t i = 0; i < count; i++) {
    setDayLabel(times[i] | "", g_data.days[i].label, sizeof(g_data.days[i].label));
    g_data.days[i].code = (uint8_t)(codes[i] | 0);
    g_data.days[i].high = (int16_t)lroundf(highs[i].as<float>());
    g_data.days[i].low = (int16_t)lroundf(lows[i].as<float>());
    g_data.days[i].rainPct = (uint8_t)constrain(rain[i].as<int>(), 0, 100);
  }

  g_data.valid = true;
  g_data.error = false;
  g_data.lastOkMs = millis();
  return true;
}

bool fetchJson(const Settings& s, const String& url, bool geocode) {
  std::unique_ptr<NetClient> client(platformMakeSecureClient(4096));
  HTTPClient http;
  uint16_t timeout = s.httpTimeout < WEATHER_HTTP_TIMEOUT_MS ? WEATHER_HTTP_TIMEOUT_MS : s.httpTimeout;
  http.setTimeout(timeout);
  http.setReuse(false);
  http.useHTTP10(true);
  g_lastHttp = 0;
  g_stage = geocode ? "geocoding" : "forecast";
  if (!http.begin(*client, url)) {
    g_stage = "begin failed";
    return false;
  }
  http.addHeader("Accept", "application/json");
  http.setUserAgent(F(FW_NAME));
  int code = http.GET();
  g_lastHttp = code;
  if (code != HTTP_CODE_OK) {
    g_stage = code < 0 ? "network error" : "http error";
    http.end();
    return false;
  }
  bool ok = geocode ? parseGeocode(http.getStream(), s) : parseForecast(http.getStream());
  if (!ok) g_stage = "parse error";
  http.end();
  return ok;
}

String geocodeUrl(const Settings& s) {
  String url = F(OPEN_METEO_GEO_URL "?name=");
  url += urlEncode(s.weather.city);
  url += F("&count=1&language=en&format=json");
  return url;
}

String forecastUrl(const Settings& s) {
  String url = F(OPEN_METEO_URL "?latitude=");
  url += String(g_lat, 4);
  url += F("&longitude=");
  url += String(g_lon, 4);
  url += F("&current=temperature_2m,apparent_temperature,is_day,weather_code,relative_humidity_2m,wind_speed_10m");
  url += F("&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max");
  url += F("&timezone=auto&forecast_days=4");
  if (s.weather.fahrenheit) url += F("&temperature_unit=fahrenheit&wind_speed_unit=mph");
  return url;
}

void failForRetry() {
  g_data.error = true;
  g_nextTryMs = millis() + WEATHER_RETRY_SEC * 1000UL;
  g_revision++;
}
}  // namespace

void weatherInit(const Settings& s) {
  g_data.clear();
  g_cityKey = s.weather.city;
  const char* label = s.weather.label.length() ? s.weather.label.c_str() : s.weather.city.c_str();
  strlcpy(g_data.city, label, sizeof(g_data.city));
  g_lat = g_lon = 0;
  g_resolved = false;
  g_nextTryMs = millis();
  g_lastHttp = 0;
  g_stage = s.weather.city.length() ? "waiting" : "set city";
  g_revision++;
}

void weatherService(const Settings& s) {
  if (s.weather.city != g_cityKey) weatherInit(s);
  if (!s.weather.city.length()) return;
  if ((int32_t)(millis() - g_nextTryMs) < 0) return;

  if (!g_resolved) {
    if (!fetchJson(s, geocodeUrl(s), true)) {
      failForRetry();
      return;
    }
    g_nextTryMs = millis();
    g_revision++;
    return;
  }

  if (!fetchJson(s, forecastUrl(s), false)) {
    failForRetry();
    return;
  }
  g_stage = "ok";
  g_nextTryMs = millis() + (uint32_t)s.weather.pollMin * 60000UL;
  g_revision++;
}

void weatherForceRefresh() {
  g_nextTryMs = millis();
}

const WeatherData& weatherData() { return g_data; }
uint32_t weatherRevision() { return g_revision; }
const char* weatherStage() { return g_stage; }
int weatherLastHttp() { return g_lastHttp; }
uint32_t weatherRetryInSec() {
  int32_t left = (int32_t)(g_nextTryMs - millis());
  return left > 0 ? (uint32_t)left / 1000UL : 0;
}

#endif
