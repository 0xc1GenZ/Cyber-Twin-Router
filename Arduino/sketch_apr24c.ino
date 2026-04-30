/*ReadMe.!
 * ╔══════════════════════════════════════════════════════════╗
 * ║   Cyber-Twin Router — NodeMCU #2 PIR Firmware v3.0      ║
 * ║   Enhanced: interrupt-driven, LED feedback, auto-        ║
 * ║   reconnect, dual-zone, threat scoring, statistics       ║
 * ╚══════════════════════════════════════════════════════════╝
 *
 * Hardware:  NodeMCU v3 (ESP8266) + HC-SR501 PIR
 * Pins:      PIR OUT → D5 (GPIO14)
 *            Built-in LED → D4 (GPIO2) — onboard blue LED
 *            Status LED (optional) → D6 (GPIO12)
 *
 * Libraries: PubSubClient, ArduinoJson
 *            Install via Tools → Manage Libraries
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ════════════════════════════════════════════════════════════
//  ❶  The name of the ssid,psswd & Ipaddr
// ════════════════════════════════════════════════════════════
const char* WIFI_SSID      = "";
const char* WIFI_PASS      = "";
const char* MQTT_SERVER    = "192.168.X.X";   // your laptop IP
// ════════════════════════════════════════════════════════════

// ── Identity ─────────────────────────────────────────────────
const char* DEVICE_ID      = "IoT-Node-02";
const char* MQTT_TOPIC     = "iot/sensor-01/data";
const char* MQTT_STATUS    = "iot/node-02/status";   // heartbeat topic
const int   MQTT_PORT      = 1883;

// ── Pin map ───────────────────────────────────────────────────
#define PIR_PIN       D5    // HC-SR501 OUT signal
#define LED_BUILTIN_N D4    // NodeMCU onboard LED (active LOW)
#define LED_STATUS    D6    // optional external LED (active HIGH)

// ── PIR tuning ────────────────────────────────────────────────
// Cooldown: minimum ms between two published events.
// Lower = more responsive. Higher = fewer duplicate events.
// HC-SR501 hardware delay pot is the PRIMARY filter;
// this is a software guard on top.
#define PIR_COOLDOWN_MS    500   // minimum ms between MQTT publishes
#define PIR_BURST_WINDOW   5000  // window to count burst events
#define PIR_BURST_THRESH   3     // events in window → threat upgrade

// ── Heartbeat ─────────────────────────────────────────────────
#define HEARTBEAT_INTERVAL 30000  // send status every 30 s

// ════════════════════════════════════════════════════════════
//  Runtime state
// ════════════════════════════════════════════════════════════
WiFiClient   espClient;
PubSubClient mqtt(espClient);

// Interrupt flag — set inside ISR, cleared in loop()
volatile bool pirTriggered   = false;
volatile unsigned long pirISRtime = 0;

// Statistics
unsigned long motionCount    = 0;   // total detections this session
unsigned long mqttSent       = 0;   // successfully published
unsigned long mqttFailed     = 0;   // failed publishes
unsigned long sessionStart   = 0;   // millis() at WiFi connect
unsigned long lastMotion     = 0;   // millis() of last published event
unsigned long lastHeartbeat  = 0;

// Burst detection
struct BurstWindow {
  unsigned long times[20];
  int head = 0, count = 0;
} burst;

// LED state machine
unsigned long ledOffAt = 0;         // millis when to turn LED off
bool ledOn = false;

// ════════════════════════════════════════════════════════════
//  ISR — runs in <1 µs on rising edge of PIR OUT
//  Keep it minimal: just set a flag and record time
// ════════════════════════════════════════════════════════════
IRAM_ATTR void pirISR() {
  pirISRtime  = millis();
  pirTriggered = true;
}

// ════════════════════════════════════════════════════════════
//  LED helpers
// ════════════════════════════════════════════════════════════
void ledFlash(int durationMs) {
  digitalWrite(LED_BUILTIN_N, LOW);   // active LOW → ON
  digitalWrite(LED_STATUS, HIGH);
  ledOn    = true;
  ledOffAt = millis() + durationMs;
}

void ledUpdate() {
  if (ledOn && millis() >= ledOffAt) {
    digitalWrite(LED_BUILTIN_N, HIGH); // OFF
    digitalWrite(LED_STATUS, LOW);
    ledOn = false;
  }
}

// ════════════════════════════════════════════════════════════
//  WiFi — blocks until connected, retries indefinitely
// ════════════════════════════════════════════════════════════
void connectWiFi() {
  Serial.print("\n[WiFi] Connecting to ");
  Serial.print(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print('.');
    if (++dots % 20 == 0) Serial.println();
    ledFlash(80);
  }

  sessionStart = millis();
  Serial.println();
  Serial.println("[WiFi] ✓ Connected");
  Serial.print  ("       IP   : "); Serial.println(WiFi.localIP());
  Serial.print  ("       RSSI : "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
}

// ════════════════════════════════════════════════════════════
//  MQTT — non-blocking reconnect with back-off
// ════════════════════════════════════════════════════════════
void connectMQTT() {
  int retries = 0;
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Connecting... ");
    if (mqtt.connect(DEVICE_ID)) {
      Serial.println("✓ connected");
      // Publish online status
      mqtt.publish(MQTT_STATUS, "{\"status\":\"online\",\"device\":\"IoT-Node-02\"}");
    } else {
      int rc = mqtt.state();
      Serial.print("✗ rc="); Serial.print(rc);
      // rc meaning: -4=timeout -3=conn lost -2=failed -1=disconnected
      // 1=bad proto 2=bad clientId 3=unavail 4=bad creds 5=unauth
      if      (rc == -4) Serial.println(" (broker unreachable — check IP & firewall)");
      else if (rc == -2) Serial.println(" (connection refused — broker running?)");
      else               Serial.print  (" — retry in 5s\n");

      unsigned long wait = min(5000UL * (retries + 1), 30000UL);
      delay(wait);
      retries++;
    }
  }
}

// ════════════════════════════════════════════════════════════
//  Burst analysis — returns events in the last PIR_BURST_WINDOW
// ════════════════════════════════════════════════════════════
int countBurstEvents(unsigned long now) {
  int count = 0;
  for (int i = 0; i < burst.count; i++) {
    int idx = (burst.head - 1 - i + 20) % 20;
    if (now - burst.times[idx] < PIR_BURST_WINDOW) count++;
    else break;
  }
  return count;
}

void recordBurstEvent(unsigned long now) {
  burst.times[burst.head] = now;
  burst.head = (burst.head + 1) % 20;
  if (burst.count < 20) burst.count++;
}

// ════════════════════════════════════════════════════════════
//  Threat level scoring
// ════════════════════════════════════════════════════════════
const char* threatLevel(int burstCount, unsigned long msSinceLast) {
  if (burstCount >= PIR_BURST_THRESH)            return "HIGH";
  if (burstCount >= 3 || msSinceLast < 3000)     return "MEDIUM";
  return "LOW";
}

// ════════════════════════════════════════════════════════════
//  Publish motion event to MQTT → blockchain via bridge
// ════════════════════════════════════════════════════════════
void publishMotion(unsigned long now) {
  // Cooldown gate — fastest the firmware will publish
  if (now - lastMotion < PIR_COOLDOWN_MS) return;

  motionCount++;
  recordBurstEvent(now);
  int   bCount  = countBurstEvents(now);
  unsigned long msSinceLast = lastMotion > 0 ? now - lastMotion : 99999;
  const char*   threat      = threatLevel(bCount, msSinceLast);
  unsigned long uptime      = (now - sessionStart) / 1000;

  // Build JSON payload
  StaticJsonDocument<384> doc;
  doc["device"]      = DEVICE_ID;
  doc["attack"]      = "MotionDetected";
  doc["attackerIP"]  = WiFi.localIP().toString();
  doc["iotDevice"]   = "PIR-HC-SR501";
  doc["threat"]      = threat;

  // Rich details string — appears in dashboard
  char details[128];
  snprintf(details, sizeof(details),
    "%s threat | burst:%d/%ds | event#%lu | up:%lus",
    threat, bCount, PIR_BURST_WINDOW / 1000,
    motionCount, uptime);
  doc["details"]     = details;

  doc["motionCount"] = motionCount;
  doc["burstCount"]  = bCount;
  doc["msSinceLast"] = msSinceLast;
  doc["rssi"]        = WiFi.RSSI();
  doc["uptimeSec"]   = uptime;
  doc["timestamp"]   = now / 1000;

  char buf[384];
  serializeJson(doc, buf);

  if (mqtt.publish(MQTT_TOPIC, buf)) {
    mqttSent++;
    lastMotion = now;
    ledFlash(threat[0] == 'H' ? 800 : threat[0] == 'M' ? 400 : 150);

    Serial.printf("\n[PIR] ✓ MOTION #%lu  threat=%-6s  burst=%d  RSSI=%d dBm\n",
      motionCount, threat, bCount, WiFi.RSSI());
    Serial.printf("      sent=%lu  failed=%lu  uptime=%lus\n",
      mqttSent, mqttFailed, uptime);
  } else {
    mqttFailed++;
    Serial.println("[PIR] ✗ MQTT publish FAILED — will retry on next motion");
  }
}

// ════════════════════════════════════════════════════════════
//  Heartbeat — periodic status to MQTT_STATUS topic
// ════════════════════════════════════════════════════════════
void sendHeartbeat(unsigned long now) {
  StaticJsonDocument<200> doc;
  doc["device"]      = DEVICE_ID;
  doc["status"]      = "alive";
  doc["motionCount"] = motionCount;
  doc["mqttSent"]    = mqttSent;
  doc["mqttFailed"]  = mqttFailed;
  doc["rssi"]        = WiFi.RSSI();
  doc["uptimeSec"]   = (now - sessionStart) / 1000;
  doc["freeHeap"]    = ESP.getFreeHeap();

  char buf[200];
  serializeJson(doc, buf);
  mqtt.publish(MQTT_STATUS, buf);

  Serial.printf("[HB]  alive | motion=%lu sent=%lu rssi=%d heap=%u\n",
    motionCount, mqttSent, WiFi.RSSI(), ESP.getFreeHeap());
}

// ════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(200);

  Serial.println(F("\n\n╔══════════════════════════════════════╗"));
  Serial.println(F(  "║  Cyber-Twin PIR Node v3.0            ║"));
  Serial.println(F(  "║  NodeMCU #2 — HC-SR501 PIR sensor    ║"));
  Serial.println(F(  "╚══════════════════════════════════════╝"));
  Serial.printf (    "  Device : %s\n", DEVICE_ID);
  Serial.printf (    "  Broker : %s:%d\n", MQTT_SERVER, MQTT_PORT);
  Serial.printf (    "  Topic  : %s\n\n", MQTT_TOPIC);

  // Pin setup
  pinMode(PIR_PIN,       INPUT);
  pinMode(LED_BUILTIN_N, OUTPUT); digitalWrite(LED_BUILTIN_N, HIGH); // off
  pinMode(LED_STATUS,    OUTPUT); digitalWrite(LED_STATUS,    LOW);

  // Attach INTERRUPT on rising edge — fires instantly when PIR goes HIGH
  // This is faster and more reliable than polling in loop()
  attachInterrupt(digitalPinToInterrupt(PIR_PIN), pirISR, RISING);

  // Connect
  connectWiFi();
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setKeepAlive(60);
  connectMQTT();

  // PIR calibration — HC-SR501 needs 30s to set thermal baseline
  Serial.println("[PIR] Calibrating — 30 seconds...");
  Serial.println("      Do NOT move in front of the sensor during this time");
  for (int i = 30; i > 0; i--) {
    Serial.printf("      %2d s remaining...\r", i);
    // Flash LED during calibration to show activity
    ledFlash(50); delay(1000);
  }
  Serial.println("\n[PIR] Calibration complete — sensor is ARMED");
  Serial.println("      Wave hand or walk past to trigger");

  // Three quick flashes = ready
  for (int i = 0; i < 3; i++) {
    ledFlash(100); delay(200);
  }

  pirTriggered = false;  // clear any spurious triggers during calibration
}

// ════════════════════════════════════════════════════════════
//  LOOP — non-blocking, interrupt-driven
// ════════════════════════════════════════════════════════════
void loop() {
  unsigned long now = millis();

  // ── WiFi watchdog ─────────────────────────────────────────
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Lost connection — reconnecting...");
    connectWiFi();
  }

  // ── MQTT watchdog ─────────────────────────────────────────
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();

  // ── Process PIR interrupt flag ─────────────────────────────
  // pirTriggered is set by pirISR() — check and clear atomically
  if (pirTriggered) {
    noInterrupts();
    unsigned long eventTime = pirISRtime;
    pirTriggered = false;
    interrupts();

    publishMotion(eventTime);
  }

  // ── LED state machine (non-blocking) ──────────────────────
  ledUpdate();

  // ── Heartbeat ─────────────────────────────────────────────
  if (now - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    sendHeartbeat(now);
    lastHeartbeat = now;
  }

  // ── Yield to WiFi stack (essential for ESP8266) ───────────
  yield();
}
