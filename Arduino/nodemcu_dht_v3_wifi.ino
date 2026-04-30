
 *
 * Hardware:  NodeMCU v3 (ESP8266) + DHT11 sensor
 * Wiring:    DHT11 VCC  → NodeMCU 3V3
 *            DHT11 DATA → NodeMCU D4 (GPIO2)
 *            DHT11 GND  → NodeMCU GND
 *            Status LED → NodeMCU D6 (GPIO12) [optional]
 *
 * Libraries (Tools → Manage Libraries):
 *   DHT sensor library  — by Adafruit
 *   Adafruit Unified Sensor — by Adafruit
 *   PubSubClient        — by Nick O'Leary
 *   ArduinoJson         — by Benoit Blanchon v6.x
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ════════════════════════════════════════════════════════════
//  ❶  WiFi + Broker — same as Node #2
// ════════════════════════════════════════════════════════════
const char* WIFI_SSID   = "WhyFi";
const char* WIFI_PASS   = "YOUR WIFI PSSWD HERE";
const char* MQTT_SERVER = "192.168.0.101";
const int   MQTT_PORT   = 1883;

// ════════════════════════════════════════════════════════════
//  ❷  Identity
// ════════════════════════════════════════════════════════════
const char* DEVICE_ID   = "IoT-Node-01";
const char* MQTT_TOPIC  = "iot/sensor-01/data";   // shared with Node #2
const char* MQTT_STATUS = "iot/node-01/status";   // own heartbeat topic

// ════════════════════════════════════════════════════════════
//  ❸  Pin map
//     D4 = DHT11 DATA (also onboard blue LED — shared, safe)
//     D6 = optional external status LED (active HIGH)
// ════════════════════════════════════════════════════════════
#define DHT_PIN      D4
#define DHT_TYPE     DHT11
#define LED_STATUS   D6    // external LED — shows severity

// ════════════════════════════════════════════════════════════
//  ❹  Alert thresholds — tune for your environment
//     Bengaluru room temp is typically 26-32°C, 50-75% humid
// ════════════════════════════════════════════════════════════
#define TEMP_WARN_HIGH   33.0f   // °C → WARNING
#define TEMP_CRIT_HIGH   38.0f   // °C → CRITICAL
#define TEMP_WARN_LOW    18.0f   // °C → WARNING (too cold)
#define HUMID_WARN_HIGH  80.0f   // %  → WARNING
#define HUMID_CRIT_HIGH  92.0f   // %  → CRITICAL
#define HUMID_WARN_LOW   25.0f   // %  → WARNING (too dry)
#define TEMP_SPIKE_DEG    2.5f   // °C jump in one sample → ANOMALY
#define HUMID_SPIKE_PCT   8.0f   // %  jump in one sample → ANOMALY

// ════════════════════════════════════════════════════════════
//  ❺  Timing
// ════════════════════════════════════════════════════════════
#define NORMAL_INTERVAL    5000UL   // ms between normal publishes
#define ANOMALY_INTERVAL   1200UL   // ms when anomaly/warning active
#define HEARTBEAT_INTERVAL 30000UL  // ms between heartbeat publishes
#define AVG_WINDOW         5        // rolling average sample count

// ════════════════════════════════════════════════════════════
//  Objects
// ════════════════════════════════════════════════════════════
DHT          dht(DHT_PIN, DHT_TYPE);
WiFiClient   espClient;
PubSubClient mqtt(espClient);

// ─── Rolling average ──────────────────────────────────────
struct RollingAvg {
  float buf[AVG_WINDOW];
  int   head  = 0;
  int   count = 0;

  void push(float v) {
    buf[head] = v;
    head      = (head + 1) % AVG_WINDOW;
    if (count < AVG_WINDOW) count++;
  }
  float avg() const {
    if (!count) return 0;
    float s = 0;
    for (int i = 0; i < count; i++) s += buf[i];
    return s / count;
  }
  float stddev() const {
    if (count < 2) return 0;
    float m = avg(), s = 0;
    for (int i = 0; i < count; i++) s += (buf[i]-m)*(buf[i]-m);
    return sqrt(s / count);
  }
  // Compare newest vs oldest sample for trend direction
  const char* trend() const {
    if (count < AVG_WINDOW) return "WARMING";   // still filling buffer
    int newest = (head - 1 + AVG_WINDOW) % AVG_WINDOW;
    int oldest = head % AVG_WINDOW;
    float delta = buf[newest] - buf[oldest];
    if      (delta >  0.6f) return "RISING";
    else if (delta < -0.6f) return "FALLING";
    else                    return "STABLE";
  }
};

RollingAvg tempAvg;
RollingAvg humidAvg;

// ─── Runtime state ────────────────────────────────────────
unsigned long readCount      = 0;
unsigned long publishCount   = 0;
unsigned long alertCount     = 0;
unsigned long failCount      = 0;
unsigned long sessionStart   = 0;
unsigned long lastRead       = 0;
unsigned long lastHeartbeat  = 0;
float         lastPubTemp    = 0;
float         lastPubHumid   = 0;
bool          inAnomaly      = false;

// LED state machine (non-blocking, same as Node #2)
unsigned long ledOffAt = 0;
bool          ledOn    = false;

// ════════════════════════════════════════════════════════════
//  LED helpers — same pattern as Node #2
// ════════════════════════════════════════════════════════════
void ledFlash(int ms) {
  digitalWrite(LED_STATUS, HIGH);
  ledOn    = true;
  ledOffAt = millis() + ms;
}
void ledUpdate() {
  if (ledOn && millis() >= ledOffAt) {
    digitalWrite(LED_STATUS, LOW);
    ledOn = false;
  }
}
void ledThreeFlash() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_STATUS, HIGH); delay(120);
    digitalWrite(LED_STATUS, LOW);  delay(160);
  }
}

// ════════════════════════════════════════════════════════════
//  WiFi — blocks until connected, retries indefinitely
//  Identical structure to Node #2
// ════════════════════════════════════════════════════════════
void connectWiFi() {
  Serial.print(F("\n[WiFi] Connecting to "));
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
    ledFlash(60);
    if (++dots % 20 == 0) Serial.println();
  }

  sessionStart = millis();
  Serial.println(F("\n[WiFi] ✓ Connected"));
  Serial.print  (F("       IP   : ")); Serial.println(WiFi.localIP());
  Serial.print  (F("       RSSI : ")); Serial.print(WiFi.RSSI());
  Serial.println(F(" dBm"));
}

// ════════════════════════════════════════════════════════════
//  MQTT — non-blocking reconnect with backoff
//  Identical structure to Node #2
// ════════════════════════════════════════════════════════════
void connectMQTT() {
  int retries = 0;
  while (!mqtt.connected()) {
    Serial.print(F("[MQTT] Connecting... "));
    if (mqtt.connect(DEVICE_ID)) {
      Serial.println(F("✓ connected"));
      mqtt.publish(MQTT_STATUS,
        "{\"status\":\"online\",\"device\":\"IoT-Node-01\",\"sensor\":\"DHT11\"}");
    } else {
      int rc = mqtt.state();
      Serial.print(F("✗ rc=")); Serial.print(rc);
      if      (rc == -4) Serial.println(F(" (broker unreachable — check IP)"));
      else if (rc == -2) Serial.println(F(" (refused — is mqtt-broker running?)"));
      else               Serial.println(F(" — retry"));
      unsigned long wait = min(5000UL * (retries + 1), 30000UL);
      delay(wait);
      retries++;
    }
  }
}

// ════════════════════════════════════════════════════════════
//  Severity classifier
//  ESP8266 toolchain does not support brace-init struct returns.
//  Instead use four plain globals set by classify() each call.
// ════════════════════════════════════════════════════════════
const char* g_attack   = "SensorReading";
const char* g_severity = "NORMAL";
int         g_ledMs    = 100;

void classify(float t, float h, bool tSpike, bool hSpike) {
  if (tSpike || hSpike) {
    g_attack   = "SensorAnomaly";
    g_severity = "ANOMALY";
    g_ledMs    = 600;
  } else if (t >= TEMP_CRIT_HIGH || h >= HUMID_CRIT_HIGH) {
    g_attack   = "CriticalEnvironment";
    g_severity = "CRITICAL";
    g_ledMs    = 900;
  } else if (t >= TEMP_WARN_HIGH || t <= TEMP_WARN_LOW ||
             h >= HUMID_WARN_HIGH || h <= HUMID_WARN_LOW) {
    g_attack   = "EnvironmentWarning";
    g_severity = "WARNING";
    g_ledMs    = 400;
  } else {
    g_attack   = "SensorReading";
    g_severity = "NORMAL";
    g_ledMs    = 100;
  }
}

// ════════════════════════════════════════════════════════════
//  Heat index — Steadman approximation
//  Only meaningful at temp > 26°C and humidity > 40%
// ════════════════════════════════════════════════════════════
float heatIndex(float t, float h) {
  if (t < 27.0f || h < 40.0f) return t;
  return -8.78469475556f
    + 1.61139411f    * t
    + 2.33854883889f * h
    - 0.14611605f    * t * h
    - 0.012308094f   * t * t
    - 0.0164248277778f * h * h
    + 0.002211732f   * t * t * h
    + 0.00072546f    * t * h * h
    - 0.000003582f   * t * t * h * h;
}

// ════════════════════════════════════════════════════════════
//  Read DHT11, update averages, publish to MQTT
// ════════════════════════════════════════════════════════════
void readAndPublish() {
  float rawT = dht.readTemperature();
  float rawH = dht.readHumidity();

  // Reject bad reads silently
  if (isnan(rawT) || isnan(rawH)) {
    Serial.println(F("[DHT] Read failed — skipping"));
    return;
  }
  // Reject physically impossible values
  if (rawT < -10.0f || rawT > 70.0f || rawH < 0.0f || rawH > 100.0f) {
    Serial.printf("[DHT] Out of range (%.1f°C %.0f%%) — rejected\n", rawT, rawH);
    return;
  }

  readCount++;

  // Spike detection BEFORE updating the average
  bool tSpike = (tempAvg.count  > 0) && (fabs(rawT - tempAvg.avg())  > TEMP_SPIKE_DEG);
  bool hSpike = (humidAvg.count > 0) && (fabs(rawH - humidAvg.avg()) > HUMID_SPIKE_PCT);

  tempAvg.push(rawT);
  humidAvg.push(rawH);

  float avgT  = tempAvg.avg();
  float avgH  = humidAvg.avg();
  float hi    = heatIndex(avgT, avgH);
  float tStd  = tempAvg.stddev();

  const char* tTrend = tempAvg.trend();
  const char* hTrend = humidAvg.trend();

  classify(avgT, avgH, tSpike, hSpike);
  inAnomaly = (strcmp(g_severity, "NORMAL") != 0);
  if (inAnomaly) alertCount++;

  // Build payload (512 bytes — same style as Node #2)
  StaticJsonDocument<512> doc;
  doc["device"]      = DEVICE_ID;
  doc["attack"]      = g_attack;
  doc["attackerIP"]  = WiFi.localIP().toString();
  doc["iotDevice"]   = "DHT11-Sensor";
  doc["severity"]    = g_severity;

  char details[160];
  snprintf(details, sizeof(details),
    "%s | T:%.1fC(%s) H:%.0f%%(%s) HI:%.1fC | std:%.2f | read#%lu",
    g_severity, avgT, tTrend, avgH, hTrend, hi, tStd, readCount);
  doc["details"]     = details;

  // Raw + averaged values — dashboard shows both
  doc["tempRaw"]     = rawT;
  doc["tempAvg"]     = avgT;
  doc["tempTrend"]   = tTrend;
  doc["humidRaw"]    = rawH;
  doc["humidAvg"]    = avgH;
  doc["humidTrend"]  = hTrend;
  doc["heatIndex"]   = hi;
  doc["tempStdDev"]  = tStd;
  doc["tempSpike"]   = tSpike;
  doc["humidSpike"]  = hSpike;
  doc["readCount"]   = readCount;
  doc["alertCount"]  = alertCount;
  doc["publishCount"]= publishCount;
  doc["rssi"]        = WiFi.RSSI();
  doc["uptimeSec"]   = (millis() - sessionStart) / 1000;

  char buf[512];
  serializeJson(doc, buf);

  if (mqtt.publish(MQTT_TOPIC, buf)) {
    publishCount++;
    lastPubTemp  = avgT;
    lastPubHumid = avgH;
    ledFlash(g_ledMs);

    Serial.printf("\n[DHT] #%lu  %.1fC %s  %.0f%% %s  HI:%.1f  %s\n",
      readCount, avgT, tTrend, avgH, hTrend, hi, g_severity);
    if (tSpike) Serial.printf("      ⚠ TEMP  SPIKE raw=%.1f avg=%.1f\n", rawT, lastPubTemp);
    if (hSpike) Serial.printf("      ⚠ HUMID SPIKE raw=%.0f avg=%.0f\n", rawH, lastPubHumid);
    Serial.printf("      sent=%lu  alerts=%lu  rssi=%d  std=%.2f\n",
      publishCount, alertCount, WiFi.RSSI(), tStd);
  } else {
    failCount++;
    Serial.printf("[DHT] ✗ Publish failed (fail#%lu)\n", failCount);
  }
}

// ════════════════════════════════════════════════════════════
//  Heartbeat — same pattern as Node #2
// ════════════════════════════════════════════════════════════
void sendHeartbeat(unsigned long now) {
  if (!mqtt.connected()) return;

  StaticJsonDocument<220> doc;
  doc["device"]        = DEVICE_ID;
  doc["status"]        = "alive";
  doc["readCount"]     = readCount;
  doc["publishCount"]  = publishCount;
  doc["alertCount"]    = alertCount;
  doc["failCount"]     = failCount;
  doc["tempNow"]       = tempAvg.avg();
  doc["humidNow"]      = humidAvg.avg();
  doc["rssi"]          = WiFi.RSSI();
  doc["uptimeSec"]     = (now - sessionStart) / 1000;
  doc["freeHeap"]      = ESP.getFreeHeap();

  char buf[220];
  serializeJson(doc, buf);
  mqtt.publish(MQTT_STATUS, buf);

  Serial.printf("[HB]  alive | reads=%lu alerts=%lu rssi=%d heap=%u\n",
    readCount, alertCount, WiFi.RSSI(), ESP.getFreeHeap());
}

// ════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);   // FIXED: was 57600, now matches Node #2
  delay(200);

  Serial.println(F("\n\n╔══════════════════════════════════════╗"));
  Serial.println(F(  "║  Cyber-Twin DHT11 Node v3.0          ║"));
  Serial.println(F(  "║  NodeMCU #1 — Temperature + Humidity ║"));
  Serial.println(F(  "╚══════════════════════════════════════╝"));
  Serial.printf (    "  Device    : %s\n", DEVICE_ID);
  Serial.printf (    "  Broker    : %s:%d\n", MQTT_SERVER, MQTT_PORT);
  Serial.printf (    "  Topic     : %s\n", MQTT_TOPIC);
  Serial.printf (    "  Avg window: %d samples\n", AVG_WINDOW);
  Serial.printf (    "  T warn/crit: >%.0f / >%.0f C\n", TEMP_WARN_HIGH, TEMP_CRIT_HIGH);
  Serial.printf (    "  H warn/crit: >%.0f / >%.0f%%\n\n", HUMID_WARN_HIGH, HUMID_CRIT_HIGH);

  // Pin init
  pinMode(LED_STATUS, OUTPUT);
  digitalWrite(LED_STATUS, LOW);

  // DHT init
  dht.begin();

  // Connect
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setKeepAlive(60);
  connectWiFi();
  connectMQTT();

  // Warm-up: fill rolling average silently before publishing
  // Prevents false spikes on the very first published value
  Serial.println(F("[DHT] Warming up — 5 baseline samples..."));
  int attempts = 0;
  int collected = 0;
  while (collected < AVG_WINDOW && attempts < 25) {
    delay(1200);   // DHT11 needs >=1s between reads
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t) && !isnan(h) && t > -10 && t < 70 && h >= 0 && h <= 100) {
      tempAvg.push(t);
      humidAvg.push(h);
      collected++;
      Serial.printf("      sample %d/%d — %.1fC  %.0f%%\n",
        collected, AVG_WINDOW, t, h);
    } else {
      Serial.printf("      sample %d/%d — read failed, retry\n",
        collected+1, AVG_WINDOW);
    }
    attempts++;
  }

  Serial.printf("[DHT] Baseline: %.1fC  %.0f%%\n",
    tempAvg.avg(), humidAvg.avg());

  // Three flashes = armed, same as Node #2
  ledThreeFlash();
  Serial.println(F("[DHT] ✓ Armed — publishing every 5s\n"));
}

// ════════════════════════════════════════════════════════════
//  LOOP — non-blocking, matches Node #2 structure exactly
// ════════════════════════════════════════════════════════════
void loop() {
  unsigned long now = millis();

  // WiFi watchdog
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("[WiFi] Lost — reconnecting..."));
    connectWiFi();
  }

  // MQTT watchdog
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  // Adaptive publish interval — 1.2s on anomaly, 5s normal
  // DHT11 hard minimum is 1s — enforced here
  unsigned long interval = inAnomaly ? ANOMALY_INTERVAL : NORMAL_INTERVAL;

  if (now - lastRead >= interval) {
    lastRead = now;
    readAndPublish();
  }

  // LED state machine (non-blocking)
  ledUpdate();

  // Heartbeat
  if (now - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    sendHeartbeat(now);
    lastHeartbeat = now;
  }

  // Yield to ESP8266 WiFi stack — essential
  yield();
}
