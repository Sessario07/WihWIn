import os
import paho.mqtt.client as mqtt
import json
import neurokit2 as nk
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import time

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "helmet")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "wihwin123")

# Subscribe to all device topics
TOPIC_TELEMETRY = "helmet/+/telemetry"
TOPIC_BASELINE = "helmet/+/baseline"

# Baseline cache: device_id -> baseline_metrics
baseline_cache = {}

# Telemetry buffer: device_id -> list of telemetry entries
telemetry_buffer = defaultdict(list)
last_flush_time = {}

# Active ride tracking: device_id -> ride_id
active_rides = {}

# Flush telemetry to database every 10 minutes
FLUSH_INTERVAL_SECONDS = 600  # 10 minutes

# General baseline for devices without personalized baseline
GENERAL_BASELINE = {
    "mean_hr": 70.0,
    "sdnn": 50.0,
    "rmssd": 40.0,
    "pnn50": 20.0,
    "lf_hf_ratio": 1.5,
    "sd1_sd2_ratio": 0.5
}

def compute_hrv(ppg_data, sampling_rate):
    """Compute HRV metrics using NeuroKit2"""
    try:
        signals, info = nk.ppg_process(ppg_data, sampling_rate=sampling_rate)
        
        # Time-domain metrics
        hrv_time = nk.hrv_time(info["PPG_Peaks"], sampling_rate=sampling_rate)
        
        # Frequency-domain metrics
        hrv_freq = nk.hrv_frequency(info["PPG_Peaks"], sampling_rate=sampling_rate)
        
        # Nonlinear metrics
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
    """
    Multi-metric drowsiness assessment
    Returns: (should_alert, drowsiness_score, status_label, alerts)
    """
    drowsiness_score = 0
    alerts = []
    
    # 1. SDNN Check (weight: 3)
    if current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.80:
        drowsiness_score += 3
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    
    # 2. RMSSD Check (weight: 3)
    if current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.75:
        drowsiness_score += 3
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    
    # 3. pNN50 Check (weight: 2)
    if current_metrics["pnn50"] < baseline_metrics["pnn50"] * 0.70:
        drowsiness_score += 2
        alerts.append(f"pNN50 dropped {((baseline_metrics['pnn50'] - current_metrics['pnn50']) / baseline_metrics['pnn50'] * 100):.1f}%")
    
    # 4. LF/HF Ratio Check (weight: 2)
    if current_metrics["lf_hf_ratio"] > baseline_metrics["lf_hf_ratio"] * 1.3:
        drowsiness_score += 2
        alerts.append(f"LF/HF increased {((current_metrics['lf_hf_ratio'] - baseline_metrics['lf_hf_ratio']) / baseline_metrics['lf_hf_ratio'] * 100):.1f}%")
    
    # 5. SD1/SD2 Ratio Check (weight: 1)
    ratio_diff = abs(current_metrics["sd1_sd2_ratio"] - baseline_metrics["sd1_sd2_ratio"])
    if ratio_diff > baseline_metrics["sd1_sd2_ratio"] * 0.3:
        drowsiness_score += 1
        alerts.append(f"SD1/SD2 ratio deviated by {(ratio_diff / baseline_metrics['sd1_sd2_ratio'] * 100):.1f}%")
    
    # Determine status label
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
    """Get active ride ID or create a new one"""
    if device_id in active_rides:
        return active_rides[device_id]
    
    try:
        # Call FastAPI to start a new ride
        response = requests.post(
            f"{FASTAPI_URL}/rides/start",
            json={"device_id": device_id},
            timeout=5
        )
        
        if response.status_code == 200:
            ride_id = response.json().get("ride_id")
            active_rides[device_id] = ride_id
            print(f"[RIDE] ✓ Started new ride {ride_id} for device {device_id}")
            return ride_id
    except Exception as e:
        print(f"[RIDE] ❌ Error starting ride: {e}")
    
    return None

def log_drowsiness_event(device_id, ride_id, drowsiness_score, status_label, hrv_metrics, lat, lon):
    """Log drowsiness event to database"""
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
        print(f"[EVENT] ❌ Error logging drowsiness event: {e}")

def flush_telemetry_buffer(device_id):
    """Send buffered telemetry to FastAPI for database storage"""
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
            print(f"[BATCH] ✓ Flushed {count} telemetry records for {device_id} to database")
            telemetry_buffer[device_id].clear()
            last_flush_time[device_id] = time.time()
        else:
            print(f"[BATCH] ❌ Failed to flush telemetry: {response.status_code}")
            
    except Exception as e:
        print(f"[BATCH] ❌ Error flushing telemetry: {e}")

def on_message_baseline(client, userdata, msg):
    """Handle baseline messages from devices"""
    try:
        # Extract device_id from topic: helmet/<deviceID>/baseline
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[1]
        
        payload = json.loads(msg.payload.decode())
        
        # Cache the baseline
        baseline_cache[device_id] = {
            "mean_hr": payload.get("mean_hr"),
            "sdnn": payload.get("sdnn"),
            "rmssd": payload.get("rmssd"),
            "pnn50": payload.get("pnn50"),
            "lf_hf_ratio": payload.get("lf_hf_ratio"),
            "sd1_sd2_ratio": payload.get("sd1_sd2_ratio")
        }
        
        print(f"\n[BASELINE] ✓ Cached baseline for device {device_id}")
        print(f"  SDNN: {baseline_cache[device_id]['sdnn']:.2f}, RMSSD: {baseline_cache[device_id]['rmssd']:.2f}")
        
    except Exception as e:
        print(f"[BASELINE] ❌ Error processing baseline: {e}")
        import traceback
        traceback.print_exc()

def on_message_telemetry(client, userdata, msg):
    """Handle telemetry messages from devices"""
    try:
        # Extract device_id from topic: helmet/<deviceID>/telemetry
        topic_parts = msg.topic.split('/')
        device_id = topic_parts[1]
        
        payload = json.loads(msg.payload.decode())
        
        # Extract PPG data from simulator payload
        ppg_data = payload.get("ppg")  # Raw PPG array from simulator
        sample_rate = payload.get("sample_rate", 50)
        lat = payload.get("lat")
        lon = payload.get("lon")
        
        # If no PPG data, skip processing
        if not ppg_data:
            print(f"[{device_id}] ⚠️  No PPG data in payload, skipping...")
            return
        
        # Get or create active ride
        ride_id = get_or_create_active_ride(device_id)
        
        # Get baseline (from cache or use general)
        baseline = baseline_cache.get(device_id, GENERAL_BASELINE)
        using_general = device_id not in baseline_cache
        
        if using_general:
            print(f"[{device_id}] ⚠️  Using general baseline (device not onboarded)")
        
        # Process PPG data to extract HRV metrics and HR
        hrv_metrics = compute_hrv(ppg_data, sample_rate)
        
        if hrv_metrics is None:
            print(f"[{device_id}] ❌ HRV computation failed, skipping...")
            return
        
        # Extract heart rate from PPG peaks
        try:
            signals, info = nk.ppg_process(ppg_data, sampling_rate=sample_rate)
            peaks = info["PPG_Peaks"]
            if len(peaks) > 1:
                # Calculate HR from peak intervals
                peak_intervals = []
                for i in range(1, len(peaks)):
                    interval = (peaks[i] - peaks[i-1]) / sample_rate  # in seconds
                    peak_intervals.append(60.0 / interval)  # convert to BPM
                hr = sum(peak_intervals) / len(peak_intervals)
                ibi_ms = (60000.0 / hr)  # Inter-beat interval in ms
            else:
                hr = baseline.get("mean_hr", 70.0)
                ibi_ms = 60000.0 / hr
        except Exception as e:
            print(f"[{device_id}] ⚠️  HR extraction failed, using baseline: {e}")
            hr = baseline.get("mean_hr", 70.0)
            ibi_ms = 60000.0 / hr
        
        # Add HR to metrics
        hrv_metrics["hr"] = hr
        
        # Assess drowsiness
        should_alert, drowsiness_score, status_label, alerts = assess_drowsiness(hrv_metrics, baseline)
        
        # Buffer telemetry with computed HRV metrics for batch upload
        telemetry_buffer[device_id].append({
            "timestamp": datetime.now().isoformat(),
            "hr": hr,
            "ibi_ms": ibi_ms,
            "sdnn": hrv_metrics["sdnn"],
            "rmssd": hrv_metrics["rmssd"],
            "pnn50": hrv_metrics["pnn50"],
            "lf_hf_ratio": hrv_metrics["lf_hf_ratio"],
            "accel_x": None,  # Accel sent separately
            "accel_y": None,
            "accel_z": None,
            "lat": lat,
            "lon": lon
        })
        
        # Check if we need to flush the buffer
        current_time = time.time()
        if device_id not in last_flush_time:
            last_flush_time[device_id] = current_time
        
        if current_time - last_flush_time[device_id] >= FLUSH_INTERVAL_SECONDS:
            flush_telemetry_buffer(device_id)
        
        print(f"\n[{device_id}] Received telemetry: HR={hr:.1f} bpm, IBI={ibi_ms:.1f}ms (buffered: {len(telemetry_buffer[device_id])})")
        print(f"[{device_id}] Drowsiness Score: {drowsiness_score}/11 | Status: {status_label}")
        print(f"  Current - SDNN: {hrv_metrics['sdnn']:.2f}, RMSSD: {hrv_metrics['rmssd']:.2f}, pNN50: {hrv_metrics['pnn50']:.2f}")
        print(f"  Baseline - SDNN: {baseline['sdnn']:.2f}, RMSSD: {baseline['rmssd']:.2f}, pNN50: {baseline['pnn50']:.2f}")
        
        if should_alert:
            print(f"  🚨 {status_label} DETECTED:")
            for alert in alerts:
                print(f"     - {alert}")
        else:
            print(f"  ✅ Normal state")
        
        # Log drowsiness event if not AWAKE
        if status_label != "AWAKE" and ride_id:
            log_drowsiness_event(device_id, ride_id, drowsiness_score, status_label, hrv_metrics, lat, lon)
        
        # 🆕 Publish live analysis to mobile app topic
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
        
        # Send command back to helmet
        cmd_topic = f"helmet/{device_id}/command"
        command_payload = {"vibrate": should_alert}
        client.publish(cmd_topic, json.dumps(command_payload), qos=1)
        
    except Exception as e:
        print(f"[TELEMETRY] ❌ Error processing telemetry: {e}")
        import traceback
        traceback.print_exc()

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker with result code {reason_code}")
    
    client.subscribe(TOPIC_TELEMETRY)
    client.subscribe(TOPIC_BASELINE)
    
    # Set up message callbacks using message filters
    client.message_callback_add("helmet/+/telemetry", on_message_telemetry)
    client.message_callback_add("helmet/+/baseline", on_message_baseline)
    
    print(f"\n✓ Worker subscribed to:")
    print(f"  - {TOPIC_TELEMETRY}")
    print(f"  - {TOPIC_BASELINE}")
    print(f"\n📊 Telemetry buffering:")
    print(f"  - Flush interval: {FLUSH_INTERVAL_SECONDS}s ({FLUSH_INTERVAL_SECONDS/60:.0f} minutes)")
    print(f"\n📱 Mobile App Live Stream:")
    print(f"  - Publishing to: helmet/<deviceID>/live-analysis")
    print(f"  - Includes: status (AWAKE/DROWSY/MICROSLEEP) + HRV metrics + location")
    print(f"\n🧠 Drowsiness Detection:")
    print(f"  - SDNN: Overall HRV (weight: 3)")
    print(f"  - RMSSD: Parasympathetic activity (weight: 3)")
    print(f"  - pNN50: Beat-to-beat variation (weight: 2)")
    print(f"  - LF/HF Ratio: Autonomic balance (weight: 2)")
    print(f"  - SD1/SD2 Ratio: Poincaré analysis (weight: 1)")
    print(f"  - Status Labels:")
    print(f"    * AWAKE: Score < 5")
    print(f"    * DROWSY: Score 5-7")
    print(f"    * MICROSLEEP: Score >= 8")
    print(f"\n💾 General Baseline (fallback):")
    print(f"  - SDNN: {GENERAL_BASELINE['sdnn']}, RMSSD: {GENERAL_BASELINE['rmssd']}, pNN50: {GENERAL_BASELINE['pnn50']}\n")

# Set up MQTT client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)  # Add authentication
client.on_connect = on_connect

print("Connecting to MQTT broker...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.loop_forever()