<h1 align="center">
  <br>
  <a href="https://github.com/0xc1GenZ/Cyber-Twin-Router"><img src="https://github.com/user-attachments/assets/821fcd1d-59a7-4704-b46a-c91119c31440" width=300 height=300 alt="Forensic"></a>
  <br>
  🍯 Cyber-Twin Router 🖧
  <h4 align="center">Honeypot is proof that the best defense is pretending to be the dumbest server on the internet</h4>
  <br>
</h1>

**Digital Twin Router + IoT Simulation + Honeypot + Blockchain Logging + Cloud Real-Time Attack Dashboard**

A complete cybersecurity demonstration platform built as a Master's End-Semester Project (2026). Simulating a smart router environment with IoT devices, A honeypot to act as a decoy system designed to look like a legitimate, valuable target to lure, detect, and analyze malicious attackers, with a tamper-proof blockchain logging and live cyber-attack scenarios all running locally .

![Cyber-Twin Router Dashboard] <img width="1919" height="936" alt="Image" src="https://github.com/user-attachments/assets/f4fddd8f-8c89-4694-a8f4-afcdb45bab5e" />

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

---

## ✨ Key Features

- **Digital Twin Router** — Realistic FRRouting virtual router
- **IoT Device Simulation** — Multiple sensors publishing via MQTT
- **Honeypot SSH** — Realistic Cowrie honeypot (ports 2222/2323)
- **Blockchain Logging** — Tamper-proof CyberLogger smart contract on Ganache
- **Real-Time Dashboard** — Live Web UI with Server-Sent Events (SSE)
- **Continuous Attack Simulator** — 12+ realistic IoT attacks with instant dashboard updates

## 🎥 Live Demo Video

Watch the full demo (recommended):

[![Watch Demo Video](https://img.youtube.com/vi/PLACEHOLDER/0.jpg)](https://youtu.be/PLACEHOLDER)

*(Replace with your actual YouTube link after uploading a 60–90 second screen recording showing the dashboard with live attacks rolling in)*

🛠️ Tech Stack
Backend: Python 3.12 + Flask + Web3.py
IoT: MQTT (Eclipse Mosquitto)
Blockchain: Ganache + Solidity Smart Contract
Honeypot: Cowrie SSH Honeypot
Router: FRRouting (FRR) Docker image
Containerization: Docker Compose + WSL 2
Real-time: Server-Sent Events (SSE)

## 🚀 Quick Start (Super Simple)

### Option 1: Windows 
1. Double-click **`run.bat`** in the project folder
2. Wait 30–60 seconds
3. Your browser will automatically open the live dashboard at `http://localhost:5000`

### Option 2: Docker Command (Any OS)
```bash
docker compose up -d --build
