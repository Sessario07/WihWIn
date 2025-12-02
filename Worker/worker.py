import os
import paho.mqtt.client as mqtt
import json
import numpy as np
import neurokit2 as nk
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time
import math

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "helmet")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "wihwin123")

TOPIC_TELEMETRY = "helmet/+/telemetry"
TOPIC_BASELINE = "helmet/+/baseline"
TOPIC_ACCEL = "helmet/+/accel"


baseline_cache = {}


telemetry_buffer = defaultdict(list)
last_flush_time = {}


active_rides = {}


FLUSH_INTERVAL_SECONDS = 600  


CRASH_G_THRESHOLD = 4.0  
CRASH_VECTOR_THRESHOLD = 6.0  


GENERAL_BASELINE = {
    "mean_hr": 70.0,
    "sdnn": 50.0,
    "rmssd": 40.0,
    "pnn50": 20.0,
    "lf_hf_ratio": 1.5,
    "sd1_sd2_ratio": 0.5
}


def process_ppg_signal(ppg_data, sample_rate=50):
    try:
        
        ppg_array = np.array(ppg_data, dtype=float)
        signals, info = nk.ppg_process(ppg_array, sampling_rate=sample_rate)
        hr_values = signals["PPG_Rate"].dropna()
        mean_hr = float(hr_values.mean()) if len(hr_values) > 0 else 70.0
        
        
        peaks = info.get("PPG_Peaks", [])
        
        if len(peaks) < 3:
            print(f"Not enough peaks detected ({len(peaks)}), using defaults")
            return {
                "hr": mean_hr,
                "sdnn": 50.0,
                "rmssd": 40.0,
                "pnn50": 20.0,
                "lf_hf_ratio": 1.5,
                "sd1_sd2_ratio": 0.5
            }
        
        
        hrv_time = nk.hrv_time(peaks, sampling_rate=sample_rate)
        
        try:
            hrv_freq = nk.hrv_frequency(peaks, sampling_rate=sample_rate)
            lf_hf = float(hrv_freq["HRV_LFHF"].iloc[0]) if "HRV_LFHF" in hrv_freq.columns else 1.5
        except:
            lf_hf = 1.5
        
        try:
            hrv_nonlinear = nk.hrv_nonlinear(peaks, sampling_rate=sample_rate)
            sd1 = float(hrv_nonlinear["HRV_SD1"].iloc[0]) if "HRV_SD1" in hrv_nonlinear.columns else 1.0
            sd2 = float(hrv_nonlinear["HRV_SD2"].iloc[0]) if "HRV_SD2" in hrv_nonlinear.columns else 1.0
            sd1_sd2 = sd1 / sd2 if sd2 != 0 else 0.5
        except:
            sd1_sd2 = 0.5
        
        return {
            "hr": mean_hr,
            "sdnn": float(hrv_time["HRV_SDNN"].iloc[0]) if "HRV_SDNN" in hrv_time.columns else 50.0,
            "rmssd": float(hrv_time["HRV_RMSSD"].iloc[0]) if "HRV_RMSSD" in hrv_time.columns else 40.0,
            "pnn50": float(hrv_time["HRV_pNN50"].iloc[0]) if "HRV_pNN50" in hrv_time.columns else 20.0,
            "lf_hf_ratio": lf_hf,
            "sd1_sd2_ratio": sd1_sd2
        }
        
    except Exception as e:
        print(f"Error processing PPG signal: {e}")
        import traceback
        traceback.print_exc()
        return None


def detect_crash(accel_x, accel_y, accel_z):
    accel_magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
    max_axis = max(abs(accel_x), abs(accel_y), abs(accel_z - 9.8))  
    
    
    is_crash = False
    severity = "none"
    details = {}
    
    if max_axis > CRASH_G_THRESHOLD or accel_magnitude > CRASH_VECTOR_THRESHOLD + 9.8:
        is_crash = True
        
        
        if max_axis > 8.0 or accel_magnitude > 15.0:
            severity = "severe"
        elif max_axis > 6.0 or accel_magnitude > 12.0:
            severity = "moderate"
        else:
            severity = "mild"
        
        details = {
            "accel_x": accel_x,
            "accel_y": accel_y,
            "accel_z": accel_z,
            "magnitude": accel_magnitude,
            "max_axis_deviation": max_axis
        }
    
    return is_crash, severity, details


def notify_hospital_crash(device_id, lat, lon, severity, accel_details):
    try:
        response = requests.post(
            f"{FASTAPI_URL}/crash",
            json={
                "device_id": device_id,
                "lat": lat,
                "lon": lon,
                "severity": severity,
                "accel_magnitude": accel_details.get("magnitude"),
                "accel_x": accel_details.get("accel_x"),
                "accel_y": accel_details.get("accel_y"),
                "accel_z": accel_details.get("accel_z")
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[CRASH] Hospital notified: {result.get('hospital_name')}")
            print(f"[CRASH]  Distance: {result.get('distance_km', 'N/A')} km")
            return result
        else:
            print(f"[CRASH] Failed to notify hospital: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[CRASH] Error notifying hospital: {e}")
        return None


def assess_drowsiness(current_metrics, baseline_metrics):
    drowsiness_score = 0
    alerts = []
    
    
    if current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.80:
        drowsiness_score += 3
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    
    
    if current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.75:
        drowsiness_score += 3
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    
    
    if current_metrics["pnn50"] < baseline_metrics["pnn50"] * 0.70:
        drowsiness_score += 2
        alerts.append(f"pNN50 dropped {((baseline_metrics['pnn50'] - current_metrics['pnn50']) / baseline_metrics['pnn50'] * 100):.1f}%")
    
    
    if current_metrics["lf_hf_ratio"] > baseline_metrics["lf_hf_ratio"] * 1.3:
        drowsiness_score += 2
        alerts.append(f"LF/HF increased {((current_metrics['lf_hf_ratio'] - baseline_metrics['lf_hf_ratio']) / baseline_metrics['lf_hf_ratio'] * 100):.1f}%")
    
    
    ratio_diff = abs(current_metrics["sd1_sd2_ratio"] - baseline_metrics["sd1_sd2_ratio"])
    if ratio_diff > baseline_metrics["sd1_sd2_ratio"] * 0.3:
        drowsiness_score += 1
        alerts.append(f"SD1/SD2 ratio deviated by {(ratio_diff / baseline_metrics['sd1_sd2_ratio'] * 100):.1f}%")
    
    
    if drowsiness_score >= 8:
        status_label = "MICROSLEEP"
        should_alert = True
    elif drowsiness_score >= 5:
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
            print(f"[RIDE] Started new ride {ride_id} for device {device_id}")
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
        print(f"Error logging drowsiness: {e}")


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
            print(f"[BATCH] Flushed {count} telemetry records for {device_id} to database")
            telemetry_buffer[device_id].clear()
            last_flush_time[device_id] = time.time()
        else:
            print(f"[BATCH] Failed to flush telemetry: {response.status_code}")
            
    except Exception as e:
        print(f"[BATCH] Error flushing telemetry: {e}")


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
        
        print(f"\n[BASELINE] Cached baseline for device {device_id}")
        print(f"  SDNN: {baseline_cache[device_id]['sdnn']:.2f}, RMSSD: {baseline_cache[device_id]['rmssd']:.2f}")
        
    except Exception as e:
        print(f"[BASELINE] Error processing baseline: {e}")
        import traceback
        traceback.print_exc()


def on_message_accel(client, userdata, msg):
    try:
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[1]
        
        payload = json.loads(msg.payload.decode())
        
        accel_x = payload.get("accel_x", 0)
        accel_y = payload.get("accel_y", 0)
        accel_z = payload.get("accel_z", 9.8)
        lat = payload.get("lat")
        lon = payload.get("lon")
        
        
        is_crash, crash_severity, crash_details = detect_crash(accel_x, accel_y, accel_z)
        
        if is_crash:
            print(f"\n[{device_id}] CRASH DETECTED! Severity: {crash_severity.upper()}")
            print(f"  Accel: X={accel_x:.2f}G, Y={accel_y:.2f}G, Z={accel_z:.2f}G")
            print(f"  Magnitude: {crash_details['magnitude']:.2f}G")
            
            
            hospital_result = notify_hospital_crash(device_id, lat, lon, crash_severity, crash_details)
            
            
            cmd_topic = f"helmet/{device_id}/command"
            crash_command = {
                "crash_detected": True,
                "severity": crash_severity,
                "hospital_notified": hospital_result is not None,
                "hospital_name": hospital_result.get("hospital_name") if hospital_result else None
            }
            client.publish(cmd_topic, json.dumps(crash_command), qos=1)
            
            
            crash_topic = f"helmet/{device_id}/crash"
            client.publish(crash_topic, json.dumps({
                "device_id": device_id,
                "timestamp": datetime.now().isoformat(),
                "severity": crash_severity,
                "location": {"lat": lat, "lon": lon},
                "accel": crash_details,
                "hospital": hospital_result
            }), qos=1)
        
    except Exception as e:
        print(f"[ACCEL] Error processing accelerometer data: {e}")


def on_message_telemetry(client, userdata, msg):

    try:
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[1]
        
        payload = json.loads(msg.payload.decode())
        
        
        ppg_data = payload.get("ppg", [])
        sample_rate = payload.get("sample_rate", 50)
        lat = payload.get("lat")
        lon = payload.get("lon")
        
        print(f"\n[{device_id}] Received PPG telemetry: {len(ppg_data)} samples @ {sample_rate}Hz")
        
        
        if len(ppg_data) < 50:
            print(f"[{device_id}] Not enough PPG samples ({len(ppg_data)})")
            return
        
        
        hrv_metrics = process_ppg_signal(ppg_data, sample_rate)
        
        if hrv_metrics is None:
            print(f"[{device_id}] PPG processing failed, skipping...")
            return
        
        hr = hrv_metrics["hr"]
        ibi_ms = 60000.0 / hr if hr > 0 else 0
        
        print(f"[{device_id}] Extracted: HR={hr:.1f} bpm, SDNN={hrv_metrics['sdnn']:.2f}, RMSSD={hrv_metrics['rmssd']:.2f}")
        
        
        ride_id = get_or_create_active_ride(device_id)
        
        
        baseline = baseline_cache.get(device_id, GENERAL_BASELINE)
        using_general = device_id not in baseline_cache
        
        if using_general:
            print(f"[{device_id}] Using general baseline (device not onboarded)")
        
        
        should_alert, drowsiness_score, status_label, alerts = assess_drowsiness(hrv_metrics, baseline)
        
        
        telemetry_buffer[device_id].append({
            "timestamp": datetime.now().isoformat(),
            "hr": hr,
            "ibi_ms": ibi_ms,
            "sdnn": hrv_metrics["sdnn"],
            "rmssd": hrv_metrics["rmssd"],
            "pnn50": hrv_metrics["pnn50"],
            "lf_hf_ratio": hrv_metrics["lf_hf_ratio"],
            "lat": lat,
            "lon": lon
        })
        
        
        current_time = time.time()
        if device_id not in last_flush_time:
            last_flush_time[device_id] = current_time
        
        if current_time - last_flush_time[device_id] >= FLUSH_INTERVAL_SECONDS:
            flush_telemetry_buffer(device_id)
        
        print(f"[{device_id}] Drowsiness Score: {drowsiness_score}/11 | Status: {status_label}")
        print(f"  Current  - SDNN: {hrv_metrics['sdnn']:.2f}, RMSSD: {hrv_metrics['rmssd']:.2f}, pNN50: {hrv_metrics['pnn50']:.2f}")
        print(f"  Baseline - SDNN: {baseline['sdnn']:.2f}, RMSSD: {baseline['rmssd']:.2f}, pNN50: {baseline['pnn50']:.2f}")
        
        if should_alert:
            print(f"{status_label} DETECTED:")
            for alert in alerts:
                print(f"     - {alert}")
        else:
            print(f"Normal state")
        
        
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
        print(f"[MQTT] 📱 Published live analysis to {live_analysis_topic}")
        
        
        cmd_topic = f"helmet/{device_id}/command"
        command_payload = {"vibrate": should_alert, "crash_detected": False}
        client.publish(cmd_topic, json.dumps(command_payload), qos=1)
        
    except Exception as e:
        print(f"[TELEMETRY] Error processing telemetry: {e}")
        import traceback
        traceback.print_exc()


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker with result code {reason_code}")
    
    client.subscribe(TOPIC_TELEMETRY)
    client.subscribe(TOPIC_BASELINE)
    client.subscribe(TOPIC_ACCEL)
    
    client.message_callback_add("helmet/+/telemetry", on_message_telemetry)
    client.message_callback_add("helmet/+/baseline", on_message_baseline)
    client.message_callback_add("helmet/+/accel", on_message_accel)
    
    print(f"\n✓ Worker subscribed to:")
    print(f"  - {TOPIC_TELEMETRY} (PPG data, every 5s)")
    print(f"  - {TOPIC_BASELINE} (baseline metrics)")
    print(f"  - {TOPIC_ACCEL} (accelerometer, every 100ms)")
    print(f"\n Telemetry Processing:")
    print(f"  - Input: PPG array (integers) @ configurable sample rate")
    print(f"  - Output: HR, SDNN, RMSSD, pNN50, LF/HF ratio")
    print(f"  - Flush interval: {FLUSH_INTERVAL_SECONDS}s ({FLUSH_INTERVAL_SECONDS/60:.0f} minutes)")
    print(f"\n Crash Detection (from accel topic):")
    print(f"  - G-force threshold: {CRASH_G_THRESHOLD}G (single axis)")
    print(f"  - Vector magnitude threshold: {CRASH_VECTOR_THRESHOLD}G")
    print(f"  - On crash: Notify nearest hospital via FastAPI")
    print(f"\n Mobile App Topics:")
    print(f"  - helmet/<deviceID>/live-analysis (HRV + drowsiness)")
    print(f"  - helmet/<deviceID>/crash (crash events)")
    print(f"\n Drowsiness Detection (from telemetry topic):")
    print(f"  - AWAKE: Score < 5")
    print(f"  - DROWSY: Score 5-7")
    print(f"  - MICROSLEEP: Score >= 8")
    print(f"\n General Baseline (fallback):")
    print(f"  - SDNN: {GENERAL_BASELINE['sdnn']}, RMSSD: {GENERAL_BASELINE['rmssd']}, pNN50: {GENERAL_BASELINE['pnn50']}\n")



client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.on_connect = on_connect

print("Connecting to MQTT broker...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.loop_forever()