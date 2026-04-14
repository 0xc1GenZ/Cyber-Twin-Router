#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import time
print("📡 IoT Simulator started (placeholder)")
client = mqtt.Client()
client.connect("mqtt-broker", 1883, 60)
while True:
    client.publish("iot/devices/router/status", "online")
    time.sleep(10)
