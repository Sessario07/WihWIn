# WihWin - Smart Helmet Drowsiness Detection System

WihWin is a real-time drowsiness detection system for motorcycle riders. It uses PPG (photoplethysmography) sensors embedded in a smart helmet to monitor heart rate variability (HRV) metrics and detect signs of drowsiness or microsleep events.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Running the System](#running-the-system)
7. [API Endpoints](#api-endpoints)
8. [Database Schema](#database-schema)
9. [Configuration](#configuration)
10. [Testing the Flow](#testing-the-flow)
11. [Drowsiness Detection Algorithm](#drowsiness-detection-algorithm)
12. [Troubleshooting](#troubleshooting)

## System Overview

The system performs the following functions:

- Real-time PPG signal processing and HRV computation
- Drowsiness detection based on HRV metric deviations from baseline
- Ride session management with automatic timeout handling
- Asynchronous ride aggregation and summary generation
- Analytics and heatmap generation for fatigue pattern analysis
- Crash detection and hospital notification (doctor proximity matching)

## Architecture

```
+-------------------+       +-------------------+       +-------------------+
|  Smart Helmet     | MQTT  |     Worker        |  HTTP |   FastAPI         |
|  (Simulator)      +------>+   (Python)        +------>+   Backend         |
|  - PPG Sensor     |       |   - HRV Analysis  |       |   - REST API      |
|  - Accelerometer  |       |   - Drowsiness    |       |   - Telemetry     |
|  - GPS            |       |     Detection     |       |   - Rides         |
+-------------------+       +--------+----------+       +--------+----------+
                                     |                           |
                                     v                           v
                            +-------------------+       +-------------------+
                            |    RabbitMQ       |       |   PostgreSQL      |
                            |  (Message Queue)  |       |   (Database)      |
                            +--------+----------+       +-------------------+
                                     |
                                     v
                            +-------------------+
                            |  Ride Aggregator  |
                            |  - Compute Stats  |
                            |  - Create Summary |
                            +-------------------+

Additional Services:
- Spring Backend: Auth, Users, Profiles, Hospital management
- Nginx: Reverse proxy routing /api/spring/* and /api/fast/*
- MQTT Broker (Mosquitto): Real-time helmet communication
```

## Components

### Worker (Python)
Subscribes to MQTT topics, processes PPG telemetry, computes HRV metrics using NeuroKit2, and detects drowsiness by comparing current metrics against baseline values.

- Real-time HRV computation (SDNN, RMSSD, pNN50, LF/HF ratio)
- Drowsiness scoring algorithm (0-11 scale)
- Automatic ride creation and timeout handling (60 seconds inactivity)
- Telemetry batching (flushes every 120 seconds)
- Live analysis publishing via MQTT

### FastAPI Backend (Python)
REST API for ride management, telemetry storage, analytics, and device management.

### Ride Aggregator (Python)
Consumes ride.end messages from RabbitMQ, computes ride statistics, and creates ride summaries with retry logic (max 3 attempts).

### Spring Backend (Java)
Handles user authentication, profile management, and hospital/doctor management for crash notifications.

### Helmet Simulator (C)
Simulates a smart helmet sending PPG telemetry data via MQTT for testing.

### Infrastructure
- PostgreSQL: Persistent data storage
- RabbitMQ: Async message processing for ride completion
- Mosquitto: MQTT broker for real-time communication
- Nginx: Reverse proxy

## Prerequisites

- Docker and Docker Compose
- For simulator: C compiler (clang/gcc) and libmosquitto

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd WihWIn
```

2. Build the helmet simulator (optional, for testing):
```bash
cd Simulator
# Install libmosquitto first (macOS: brew install mosquitto)
clang helmet_simulator.c -o helmet_simulator -lmosquitto
cd ..
```

## Running the System

### Start All Services

```bash
docker-compose up -d
```

This starts all services:
- PostgreSQL, RabbitMQ, MQTT Broker
- FastAPI Backend, Spring Backend, Worker, Ride Aggregator
- Nginx (port 80)

### Check Service Status

```bash
docker-compose ps
```

### View Logs

```bash
docker-compose logs -f              # All services
docker logs helmet_worker --tail 50  # Worker only
docker logs ride_aggregator --tail 50
```

### Stop Services

```bash
docker-compose down      # Stop all
docker-compose down -v   # Stop and reset database
```

## API Endpoints

All endpoints accessed through Nginx on port 80.

### FastAPI Backend (/api/fast/*)

Rides:
- POST /api/fast/rides/start - Start ride (body: {"device_id": "HELMET003"})
- POST /api/fast/rides/{ride_id}/end - End ride

Telemetry:
- POST /api/fast/telemetry/batch - Store batch telemetry
- POST /api/fast/drowsiness-events - Log drowsiness event

Analytics:
- GET /api/fast/users/{user_id}/hrv-heatmap?days=7 - HRV heatmap
- GET /api/fast/users/{user_id}/daily-hrv-trend?days=30 - Daily HRV trend
- GET /api/fast/users/{user_id}/weekly-fatigue - Weekly fatigue scores
- GET /api/fast/users/{user_id}/lf-hf-trend?days=30 - LF/HF ratio trend
- GET /api/fast/users/{user_id}/fatigue-patterns - Fatigue patterns

Devices:
- GET /api/fast/devices/{device_id} - Get device info
- POST /api/fast/devices/{device_id}/onboard - Onboard device

Baseline:
- POST /api/fast/baseline/compute - Compute baseline
- GET /api/fast/baseline/{device_id} - Get baseline

### Spring Backend (/api/spring/*)

- POST /api/spring/auth/register - Register user
- POST /api/spring/auth/login - Login
- GET /api/spring/users/{id} - Get user profile
- PUT /api/spring/users/{id}/profile - Update profile
- POST /api/spring/crash/alert - Report crash

### Health Check
- GET /health - Returns OK

## Database Schema

Key tables:
- users - User accounts (customers and doctors)
- devices - Smart helmet devices
- baseline_metrics - User HRV baselines
- rides - Ride sessions
- raw_ppg_telemetry - Raw PPG data
- drowsiness_events - Detected events
- ride_summaries - Aggregated statistics
- daily_hrv_summary - Daily aggregations
- hourly_fatigue_heatmap - Hourly fatigue data
- crash_alerts - Crash events

## Configuration

### Environment Variables

Worker:
- MQTT_BROKER (default: localhost)
- MQTT_PORT (default: 1883)
- MQTT_USER (default: helmet)
- MQTT_PASSWORD (default: wihwin123)
- FASTAPI_URL (default: http://localhost:8000)

FastAPI/Aggregator:
- DB_URL - PostgreSQL connection string
- RABBITMQ_URL - RabbitMQ connection string

### MQTT Topics

- helmet/{device_id}/telemetry - PPG telemetry from helmet
- helmet/{device_id}/baseline - Baseline metrics
- helmet/{device_id}/command - Commands to helmet
- helmet/{device_id}/live-analysis - Real-time analysis
- helmet/{device_id}/accel - Accelerometer data

## Testing the Flow

### 1. Create Test User and Device

```bash
docker exec -i postgres_db psql -U postgres -d Wihwin << 'EOF'
INSERT INTO users (id, username, email, password_hash, role)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 'testuser', 'test@example.com', 'hash123', 'customer')
ON CONFLICT (id) DO NOTHING;

INSERT INTO devices (id, user_id, device_id, onboarded)
VALUES ('660e8400-e29b-41d4-a716-446655440000', '550e8400-e29b-41d4-a716-446655440000', 'HELMET003', true)
ON CONFLICT (device_id) DO UPDATE SET user_id = '550e8400-e29b-41d4-a716-446655440000';
EOF
```

### 2. Run Helmet Simulator

```bash
cd Simulator
./helmet_simulator
```

### 3. Monitor Worker

```bash
docker logs -f helmet_worker
```

### 4. Stop Simulator and Wait

Stop simulator (Ctrl+C), wait 60 seconds for ride timeout.

### 5. Verify Results

```bash
# Check ride
docker exec postgres_db psql -U postgres -d Wihwin -c \
  "SELECT id, status, duration_seconds FROM rides;"

# Check summary
docker exec postgres_db psql -U postgres -d Wihwin -c \
  "SELECT fatigue_score, total_drowsiness_events FROM ride_summaries;"

# Test heatmap
curl -s "http://localhost/api/fast/users/550e8400-e29b-41d4-a716-446655440000/hrv-heatmap?days=7"
```

## Drowsiness Detection Algorithm

11-point scoring based on HRV deviations from baseline:

| Metric | Condition | Points |
|--------|-----------|--------|
| SDNN | < 50% baseline | +3 |
| SDNN | < 65% baseline | +2 |
| SDNN | < 75% baseline | +1 |
| RMSSD | < 45% baseline | +3 |
| RMSSD | < 60% baseline | +2 |
| RMSSD | < 70% baseline | +1 |
| pNN50 | < 40% baseline | +2 |
| pNN50 | < 55% baseline | +1 |
| LF/HF | > 170% baseline | +2 |
| LF/HF | > 150% baseline | +1 |
| SD1/SD2 | > 60% deviation | +1 |

Status:
- Score >= 11: MICROSLEEP (critical)
- Score >= 8: DROWSY (warning)
- Score < 8: AWAKE (normal)

## Troubleshooting

### Worker not receiving telemetry
- Check MQTT broker: docker logs mqtt_broker
- Verify MQTT credentials in mosquitto password file

### Ride not completing
- Check RabbitMQ: curl -u guest:guest http://localhost:15672/api/queues/%2F/ride.end
- Check aggregator: docker logs ride_aggregator

### HRV computation warnings
- Warnings from NeuroKit2 are normal with low-variance PPG data
- Worker handles these gracefully

### Empty analytics
- Ensure rides are completed (status = 'completed')
- Verify user_id is valid UUID format