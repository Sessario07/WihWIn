import os
import paho.mqtt.client as mqtt
import json
import neurokit2 as nk
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time
import math
import numpy as np

if not hasattr(np, 'trapz'):
    np.trapz = np.trapezoid

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "helmet")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "wihwin123")

TOPIC_TELEMETRY = "helmet/+/telemetry"
TOPIC_BASELINE = "helmet/+/baseline"

baseline_cache = {}
telemetry_buffer = defaultdict(list)
last_flush_time = {}
active_rides = {}
last_telemetry_time = {}

FLUSH_INTERVAL_SECONDS = 120
RIDE_TIMEOUT_SECONDS = 60

GENERAL_BASELINE = {
    "mean_hr": 70.0,
    "sdnn": 50.0,
    "rmssd": 40.0,
    "pnn50": 20.0,
    "lf_hf_ratio": 1.5,
    "sd1_sd2_ratio": 0.5
}

def sanitize_metrics(metrics):
    sanitized = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                sanitized[key] = 0.0
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized

def compute_hrv(ppg_data, sampling_rate):
    try:
        signals, info = nk.ppg_process(ppg_data, sampling_rate=sampling_rate)
        hrv_time = nk.hrv_time(info["PPG_Peaks"], sampling_rate=sampling_rate)
        hrv_freq = nk.hrv_frequency(info["PPG_Peaks"], sampling_rate=sampling_rate)
        hrv_nonlinear = nk.hrv_nonlinear(info["PPG_Peaks"], sampling_rate=sampling_rate)
        
        return {
            "sdnn": float(hrv_time["HRV_SDNN"].iloc[0]) if "HRV_SDNN" in hrv_time.columns else 0.0,
            "rmssd": float(hrv_time["HRV_RMSSD"].iloc[0]) if "HRV_RMSSD" in hrv_time.columns else 0.0,
            "pnn50": float(hrv_time["HRV_pNN50"].iloc[0]) if "HRV_pNN50" in hrv_time.columns else 0.0,
            "lf_hf_ratio": float(hrv_freq["HRV_LFHF"].iloc[0]) if "HRV_LFHF" in hrv_freq.columns else 0.0,
            "sd1_sd2_ratio": float(hrv_nonlinear["HRV_SD1"].iloc[0] / hrv_nonlinear["HRV_SD2"].iloc[0]) 
                           if "HRV_SD1" in hrv_nonlinear.columns and "HRV_SD2" in hrv_nonlinear.columns 
                           and hrv_nonlinear["HRV_SD2"].iloc[0] != 0 else 0.0
        }
    except Exception as e:
        print(f"HRV computation error: {e}")
        return None

def assess_drowsiness(current_metrics, baseline_metrics):
    drowsiness_score = 0
    alerts = []
    
    if current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.50:
        drowsiness_score += 3
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    elif current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.65:
        drowsiness_score += 2
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    elif current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.75:
        drowsiness_score += 1
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    
    if current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.45:
        drowsiness_score += 3
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    elif current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.60:
        drowsiness_score += 2
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    elif current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.70:
        drowsiness_score += 1
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    
    if current_metrics["pnn50"] < baseline_metrics["pnn50"] * 0.40:
        drowsiness_score += 2
        alerts.append(f"pNN50 dropped {((baseline_metrics['pnn50'] - current_metrics['pnn50']) / baseline_metrics['pnn50'] * 100):.1f}%")
    elif current_metrics["pnn50"] < baseline_metrics["pnn50"] * 0.55:
        drowsiness_score += 1
        alerts.append(f"pNN50 dropped {((baseline_metrics['pnn50'] - current_metrics['pnn50']) / baseline_metrics['pnn50'] * 100):.1f}%")
    
    if current_metrics["lf_hf_ratio"] > baseline_metrics["lf_hf_ratio"] * 1.70:
        drowsiness_score += 2
        alerts.append(f"LF/HF increased {((current_metrics['lf_hf_ratio'] - baseline_metrics['lf_hf_ratio']) / baseline_metrics['lf_hf_ratio'] * 100):.1f}%")
    elif current_metrics["lf_hf_ratio"] > baseline_metrics["lf_hf_ratio"] * 1.50:
        drowsiness_score += 1
        alerts.append(f"LF/HF increased {((current_metrics['lf_hf_ratio'] - baseline_metrics['lf_hf_ratio']) / baseline_metrics['lf_hf_ratio'] * 100):.1f}%")
    
    ratio_diff = abs(current_metrics["sd1_sd2_ratio"] - baseline_metrics["sd1_sd2_ratio"])
    if ratio_diff > baseline_metrics["sd1_sd2_ratio"] * 0.60:
        drowsiness_score += 1
        alerts.append(f"SD1/SD2 ratio deviated by {(ratio_diff / baseline_metrics['sd1_sd2_ratio'] * 100):.1f}%")
    
    if drowsiness_score >= 11:
        status_label = "MICROSLEEP"
        should_alert = True
    elif drowsiness_score >= 8:
        status_label = "DROWSY"
        should_alert = True
    else:
        status_label = "AWAKE"
        should_alert = False
    
    return should_alert, drowsiness_score, status_label, alerts

def get_or_create_active_ride(device_id):
    if device_id in active_rides:
        return active_rides[device_id]
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/rides/start",
            json={"device_id": device_id},
            timeout=5
        )
        
        if response.status_code == 200:
            ride_id = response.json().get("ride_id")
            active_rides[device_id] = ride_id
            return ride_id
    except Exception as e:
        print(f"Error starting ride: {e}")
    
    return None

def log_drowsiness_event(device_id, ride_id, drowsiness_score, status_label, hrv_metrics, lat, lon):
    try:
        requests.post(
            f"{FASTAPI_URL}/drowsiness-events",
            json={
                "device_id": device_id,
                "ride_id": ride_id,
                "severity_score": drowsiness_score,
                "status": status_label,
                "hr_at_event": hrv_metrics.get("hr"),
                "sdnn": hrv_metrics.get("sdnn"),
                "rmssd": hrv_metrics.get("rmssd"),
                "pnn50": hrv_metrics.get("pnn50"),
                "lf_hf_ratio": hrv_metrics.get("lf_hf_ratio"),
                "lat": lat,
                "lon": lon
            },
            timeout=5
        )
    except Exception as e:
        print(f"Error logging drowsiness event: {e}")

def flush_telemetry_buffer(device_id):
    if device_id not in telemetry_buffer or len(telemetry_buffer[device_id]) == 0:
        return
    
    try:
        ride_id = active_rides.get(device_id)
        
        batch_data = {
            "device_id": device_id,
            "ride_id": ride_id,
            "telemetry": telemetry_buffer[device_id]
        }
        
        response = requests.post(
            f"{FASTAPI_URL}/telemetry/batch",
            json=batch_data,
            timeout=10
        )
        
        if response.status_code == 200:
            count = len(telemetry_buffer[device_id])
            print(f"Flushed {count} telemetry records for {device_id}")
            telemetry_buffer[device_id].clear()
            last_flush_time[device_id] = time.time()
        else:
            print(f"Failed to flush telemetry: {response.status_code}")
            
    except Exception as e:
        print(f"Error flushing telemetry: {e}")

def end_ride_if_timeout(device_id):
    if device_id not in active_rides:
        return
    
    if device_id not in last_telemetry_time:
        return
    
    current_time = time.time()
    time_since_last = current_time - last_telemetry_time[device_id]
    
    if time_since_last >= RIDE_TIMEOUT_SECONDS:
        ride_id = active_rides[device_id]
        
        print(f"Device {device_id} inactive for {int(time_since_last)}s, auto-ending ride {ride_id}")
        
        try:
            flush_telemetry_buffer(device_id)
            
            response = requests.post(
                f"{FASTAPI_URL}/rides/{ride_id}/end",
                timeout=5
            )
            
            if response.status_code == 200:
                del active_rides[device_id]
                del last_telemetry_time[device_id]
                if device_id in telemetry_buffer:
                    telemetry_buffer[device_id].clear()
                if device_id in last_flush_time:
                    del last_flush_time[device_id]
            else:
                print(f"Failed to end ride: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error ending ride: {e}")

def check_all_rides_timeout():
    devices_to_check = list(active_rides.keys())
    for device_id in devices_to_check:
        end_ride_if_timeout(device_id)

def on_message_baseline(client, userdata, msg):
    try:
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[1]
        
        payload = json.loads(msg.payload.decode())
        
        baseline_cache[device_id] = {
            "mean_hr": payload.get("mean_hr"),
            "sdnn": payload.get("sdnn"),
            "rmssd": payload.get("rmssd"),
            "pnn50": payload.get("pnn50"),
            "lf_hf_ratio": payload.get("lf_hf_ratio"),
            "sd1_sd2_ratio": payload.get("sd1_sd2_ratio")
        }
        
        print(f"Cached baseline for device {device_id}")
        
    except Exception as e:
        print(f"Error processing baseline: {e}")
        import traceback
        traceback.print_exc()

def on_message_telemetry(client, userdata, msg):
    try:
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[1]
        
        payload = json.loads(msg.payload.decode())
        
        ppg_data = payload.get("ppg")
        sample_rate = payload.get("sample_rate", 50)
        lat = payload.get("lat")
        lon = payload.get("lon")
        
        if not ppg_data:
            return
        
        ride_id = get_or_create_active_ride(device_id)
        
        baseline = baseline_cache.get(device_id, GENERAL_BASELINE)
        
        hrv_metrics = compute_hrv(ppg_data, sample_rate)
        
        if hrv_metrics is None:
            return
        
        hrv_metrics = sanitize_metrics(hrv_metrics)
        
        try:
            signals, info = nk.ppg_process(ppg_data, sampling_rate=sample_rate)
            peaks = info["PPG_Peaks"]
            if len(peaks) > 1:
                peak_intervals = []
                for i in range(1, len(peaks)):
                    interval = (peaks[i] - peaks[i-1]) / sample_rate
                    peak_intervals.append(60.0 / interval)
                hr = sum(peak_intervals) / len(peak_intervals)
                ibi_ms = (60000.0 / hr)
            else:
                hr = baseline.get("mean_hr", 70.0)
                ibi_ms = 60000.0 / hr
        except Exception as e:
            hr = baseline.get("mean_hr", 70.0)
            ibi_ms = 60000.0 / hr
        
        hrv_metrics["hr"] = hr
        
        should_alert, drowsiness_score, status_label, alerts = assess_drowsiness(hrv_metrics, baseline)
        
        telemetry_buffer[device_id].append({
            "timestamp": datetime.now().isoformat(),
            "hr": hr,
            "ibi_ms": ibi_ms,
            "sdnn": hrv_metrics["sdnn"],
            "rmssd": hrv_metrics["rmssd"],
            "pnn50": hrv_metrics["pnn50"],
            "lf_hf_ratio": hrv_metrics["lf_hf_ratio"],
            "accel_x": None,
            "accel_y": None,
            "accel_z": None,
            "lat": lat,
            "lon": lon
        })
        
        current_time = time.time()
        if device_id not in last_flush_time:
            last_flush_time[device_id] = current_time
        
        if current_time - last_flush_time[device_id] >= FLUSH_INTERVAL_SECONDS:
            flush_telemetry_buffer(device_id)
        
        last_telemetry_time[device_id] = current_time
        
        print(f"[{device_id}] HR={hr:.1f} bpm | Score: {drowsiness_score}/11 | Status: {status_label}")
        
        if status_label != "AWAKE" and ride_id:
            log_drowsiness_event(device_id, ride_id, drowsiness_score, status_label, hrv_metrics, lat, lon)
        
        live_analysis_topic = f"helmet/{device_id}/live-analysis"
        live_analysis_payload = {
            "device_id": device_id,
            "timestamp": datetime.now().isoformat(),
            "status": status_label,
            "metrics": {
                "hr": hr,
                "sdnn": hrv_metrics["sdnn"],
                "rmssd": hrv_metrics["rmssd"],
                "pnn50": hrv_metrics["pnn50"],
                "lf_hf_ratio": hrv_metrics["lf_hf_ratio"],
                "drowsiness_score": drowsiness_score
            },
            "location": {
                "lat": lat,
                "lon": lon
            }
        }
        client.publish(live_analysis_topic, json.dumps(live_analysis_payload), qos=1)
        
        cmd_topic = f"helmet/{device_id}/command"
        command_payload = {"vibrate": should_alert}
        client.publish(cmd_topic, json.dumps(command_payload), qos=1)
        
    except Exception as e:
        print(f"Error processing telemetry: {e}")
        import traceback
        traceback.print_exc()

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker with result code {reason_code}")
    
    client.subscribe(TOPIC_TELEMETRY)
    client.subscribe(TOPIC_BASELINE)
    
    client.message_callback_add("helmet/+/telemetry", on_message_telemetry)
    client.message_callback_add("helmet/+/baseline", on_message_baseline)
    
    print(f"Subscribed to: {TOPIC_TELEMETRY}, {TOPIC_BASELINE}")
   
   
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASSWORD) 
client.on_connect = on_connect

print("Connecting to MQTT broker...")

MAX_RETRIES = 30
RETRY_DELAY = 5

for attempt in range(MAX_RETRIES):
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        break
    except Exception as e:
        print(f"MQTT connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES - 1:
            print(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
        else:
            print("Max retries reached. Exiting...")
            raise SystemExit(1)

while True:
    check_all_rides_timeout()
    client.loop(timeout=1.0)