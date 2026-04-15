# 🚀 Cyber-Twin Router

**Digital Twin Router + IoT Simulation + Honeypot + Blockchain Logging + Cloud Real-Time Attack Dashboard**
                  **100% software-only • No hardware • Windows/Ubuntu + WSL2 ready**

A complete cybersecurity demonstration platform built as a Master's End-Semester Project (2026). Simulate a smart router environment with IoT devices, a deceptive honeypot, tamper-proof blockchain logging, and live cyber-attack scenarios — all running locally .

![Cyber-Twin Router Dashboard](https://github.com/0xc1GenZ/Cyber-Twin-Router/raw/main/screenshots/dashboard-live.png)

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

---

## ✨ Key Features

- **Digital Twin Router** — Realistic FRRouting virtual router
- **IoT Device Simulation** — Multiple sensors publishing via MQTT
- **Honeypot SSH** — Realistic Cowrie honeypot (ports 2222/2323)
- **Blockchain Logging** — Tamper-proof CyberLogger smart contract on Ganache
- **Real-Time Dashboard** — Beautiful live web UI with Server-Sent Events (SSE)
- **Continuous Attack Simulator** — 12+ realistic IoT attacks with instant dashboard updates
- **One-Click Start** — Works perfectly on Windows 11 via `start.bat`

## 🎥 Live Demo Video

Watch the full demo (recommended):

[![Watch Demo Video](https://img.youtube.com/vi/PLACEHOLDER/0.jpg)](https://youtu.be/PLACEHOLDER)

*(Replace with your actual YouTube link after uploading a 60–90 second screen recording showing the dashboard with live attacks rolling in)*

## 🚀 Quick Start (Super Simple)

### Option 1: Windows One-Click (Recommended)
1. Double-click **`start.bat`** in the project folder
2. Wait 30–60 seconds
3. Your browser will automatically open the live dashboard at `http://localhost:5000`

### Option 2: Docker Command (Any OS)
```bash
docker compose up -d --build
