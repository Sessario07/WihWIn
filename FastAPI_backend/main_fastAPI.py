from fastapi import FastAPI, HTTPException
from models.request_models import *
from models.response_models import *
from services.device_service import DeviceService
from services.baseline_service import BaselineService
from services.ride_service import RideService
from services.analytics_service import AnalyticsService
from services.crash_service import CrashService

app = FastAPI(
    title="SmartHelmet FastAPI Backend",
    description="N-Tier architecture with Repository + Service patterns",
    version="2.0.0"
)



@app.get("/device/check", response_model=DeviceCheckResponse)
def check_device(device_id: str):
    return DeviceService.check_device(device_id)


@app.post("/baseline")
def compute_baseline(request: BaselineRequest):
    metrics = BaselineService.compute_baseline(
        request.device_id, 
        request.samples,
        request.sample_rate or 50
    )
    return {
        "success": True,
        "message": "Baseline computed and stored successfully",
        "metrics": metrics
    }



@app.post("/crash")
def crash_alert(alert: CrashAlert):
    return CrashService.handle_crash(
        alert.device_id, 
        alert.lat, 
        alert.lon,
        alert.severity,
        alert.accel_magnitude,
        alert.accel_x,
        alert.accel_y,
        alert.accel_z
    )



@app.post("/rides/start")
def start_ride(request: RideStart): 
    return RideService.start_ride(request.device_id)


@app.post("/rides/{ride_id}/end")
def end_ride(ride_id: str):
    return RideService.end_ride(ride_id)


@app.get("/rides/{ride_id}/details", response_model=RideDetailsResponse)
def get_ride_details(ride_id: str):
    return RideService.get_ride_details(ride_id)


@app.get("/rides/{ride_id}/analysis")
def get_ride_analysis(ride_id: str):
    from repositories.ride_repository import RideRepository
    
    ride = RideRepository.get_ride_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    return {
        "ride_id": str(ride['id']),
        "device_id": ride['device_code'],
        "start_time": ride['start_time'].isoformat() if ride['start_time'] else None,
        "end_time": ride['end_time'].isoformat() if ride['end_time'] else None,
        "duration_seconds": ride['duration_seconds'],
        "status": ride['status'],
        "heart_rate": {
            "avg": ride['avg_hr'],
            "max": ride['max_hr'],
            "min": ride['min_hr']
        },
        "summary": {
            "fatigue_score": ride['fatigue_score'] or 0,
            "total_drowsiness_events": ride['total_drowsiness_events'] or 0,
            "total_microsleep_events": ride['total_microsleep_events'] or 0,
            "max_drowsiness_score": ride['max_drowsiness_score'] or 0,
            "avg_drowsiness_score": ride['avg_drowsiness_score'] or 0
        }
    }

@app.get("/rides/{ride_id}/hr-timeline")
def get_ride_hr_timeline(ride_id: str):
    """Get heart rate timeline for charts"""
    from repositories.ride_repository import RideRepository
    from config.database import get_db_connection
    
    # Verify ride exists
    ride = RideRepository.get_ride_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get HR data from raw_ppg_telemetry
    cursor.execute("""
        SELECT timestamp, hr
        FROM raw_ppg_telemetry
        WHERE ride_id = %s AND hr IS NOT NULL
        ORDER BY timestamp ASC
    """, (ride_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "ride_id": ride_id,
        "data": [
            {
                "timestamp": row[0].isoformat(),
                "hr": float(row[1])
            }
            for row in rows
        ]
    }

@app.get("/rides/{ride_id}/hrv-timeline")
def get_ride_hrv_timeline(ride_id: str):
    """Get HRV (RMSSD) timeline for charts"""
    from repositories.ride_repository import RideRepository
    from repositories.baseline_repository import BaselineRepository
    from config.database import get_db_connection
    
    # Verify ride exists
    ride = RideRepository.get_ride_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    # Get baseline
    baseline_rmssd = ride.get('baseline_rmssd', 45.0)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get RMSSD data from raw_ppg_telemetry
    cursor.execute("""
        SELECT timestamp, rmssd, sdnn, pnn50, lf_hf_ratio
        FROM raw_ppg_telemetry
        WHERE ride_id = %s AND rmssd IS NOT NULL
        ORDER BY timestamp ASC
    """, (ride_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "ride_id": ride_id,
        "baseline_rmssd": baseline_rmssd,
        "data": [
            {
                "timestamp": row[0].isoformat(),
                "rmssd": float(row[1]),
                "sdnn": float(row[2]) if row[2] else None,
                "pnn50": float(row[3]) if row[3] else None,
                "lf_hf_ratio": float(row[4]) if row[4] else None
            }
            for row in rows
        ]
    }

@app.get("/rides/{ride_id}/events")
def get_ride_events(ride_id: str):
    """Get drowsiness events for map visualization"""
    from repositories.ride_repository import RideRepository
    from config.database import get_db_connection
    
    # Verify ride exists
    ride = RideRepository.get_ride_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get drowsiness events
    cursor.execute("""
        SELECT detected_at, lat, lon, status, severity_score, 
               hr_at_event, sdnn, rmssd, pnn50, lf_hf_ratio
        FROM drowsiness_events
        WHERE ride_id = %s
        ORDER BY detected_at ASC
    """, (ride_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "ride_id": ride_id,
        "total_events": len(rows),
        "events": [
            {
                "timestamp": row[0].isoformat(),
                "lat": float(row[1]) if row[1] else None,
                "lon": float(row[2]) if row[2] else None,
                "status": row[3],
                "severity_score": row[4],
                "metrics": {
                    "hr": float(row[5]) if row[5] else None,
                    "sdnn": float(row[6]) if row[6] else None,
                    "rmssd": float(row[7]) if row[7] else None,
                    "pnn50": float(row[8]) if row[8] else None,
                    "lf_hf_ratio": float(row[9]) if row[9] else None
                }
            }
            for row in rows
        ]
    }

@app.get("/rides/{ride_id}/route")
def get_ride_route(ride_id: str):
    """Get GPS route for map visualization"""
    from repositories.ride_repository import RideRepository
    from config.database import get_db_connection
    
    # Verify ride exists
    ride = RideRepository.get_ride_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get GPS coordinates from telemetry
    cursor.execute("""
        SELECT timestamp, lat, lon
        FROM raw_ppg_telemetry
        WHERE ride_id = %s AND lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY timestamp ASC
    """, (ride_id,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "ride_id": ride_id,
        "route": [
            {
                "timestamp": row[0].isoformat(),
                "lat": float(row[1]),
                "lon": float(row[2])
            }
            for row in rows
        ]
    }

@app.post("/telemetry/batch")
def batch_telemetry(batch: TelemetryBatch):
    return RideService.save_telemetry_batch(batch.device_id, batch.ride_id, batch.telemetry)


@app.post("/drowsiness-events")
def log_drowsiness_event(event: DrowsinessEvent):
    return RideService.log_drowsiness_event({
        'device_id': event.device_id,
        'ride_id': event.ride_id,
        'severity_score': event.severity_score,
        'status': event.status,
        'hr_at_event': event.hr_at_event,
        'sdnn': event.sdnn,
        'rmssd': event.rmssd,
        'pnn50': event.pnn50,
        'lf_hf_ratio': event.lf_hf_ratio,
        'lat': event.lat,
        'lon': event.lon
    })



#analytics yea

@app.get("/users/{user_id}/baseline")
def get_user_baseline(user_id: str):
    """Get user's current baseline HRV metrics"""
    from repositories.baseline_repository import BaselineRepository
    
    baseline = BaselineRepository.get_user_baseline_full(user_id)
    if not baseline:
        return {
            "has_baseline": False,
            "baseline": None
        }
    
    return {
        "has_baseline": True,
        "baseline": {
            "mean_hr": baseline.get('mean_hr'),
            "sdnn": baseline.get('sdnn'),
            "rmssd": baseline.get('rmssd'),
            "pnn50": baseline.get('pnn50'),
            "lf_hf_ratio": baseline.get('lf_hf_ratio'),
            "computed_at": baseline.get('computed_at').isoformat() if baseline.get('computed_at') else None
        }
    }


@app.delete("/users/{user_id}/baseline")
def delete_user_baseline(user_id: str):
    """Delete user's baseline metrics"""
    from repositories.baseline_repository import BaselineRepository
    
    deleted = BaselineRepository.delete_user_baseline(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No baseline found for this user")
    
    return {
        "success": True,
        "message": "Baseline deleted successfully"
    }


@app.get("/users/{user_id}/daily-hrv-trend")
def get_daily_hrv_trend(user_id: str, days: int = 30):
    """Feature 1: Daily RMSSD line chart with baseline and 7-day moving average"""
    return AnalyticsService.get_daily_hrv_trend(user_id, days)


@app.get("/users/{user_id}/weekly-fatigue-score")
def get_weekly_fatigue_score(user_id: str):
    """Feature 2: Weekly fatigue score bar chart (7 days)"""
    return AnalyticsService.get_weekly_fatigue_score(user_id)


@app.get("/users/{user_id}/hrv-heatmap")
def get_hrv_heatmap(user_id: str, days: int = 7):
    """Feature 3: HRV deviation heatmap by hour and day"""
    return AnalyticsService.get_hrv_heatmap(user_id, days)


@app.get("/users/{user_id}/lf-hf-trend")
def get_lf_hf_trend(user_id: str, days: int = 30):
    """Feature 4: LF/HF ratio trend per ride"""
    return AnalyticsService.get_lf_hf_trend(user_id, days)


@app.get("/users/{user_id}/fatigue-patterns")
def get_fatigue_patterns(user_id: str):
    """Analyze fatigue patterns by time of day and day of week"""
    return AnalyticsService.get_fatigue_patterns(user_id)


@app.get("/users/{user_id}/rides")
def get_user_rides(user_id: str, page: int = 0, size: int = 20):
    """Feature 5: Ride list with summary cards"""
    from repositories.ride_repository import RideRepository
    from repositories.baseline_repository import BaselineRepository
    
    # Get user's baseline
    baseline_data = BaselineRepository.get_user_baseline(user_id)
    baseline_rmssd = baseline_data['rmssd'] if baseline_data else 42.0
    
    rides, total = RideRepository.get_user_rides(user_id, size, page * size)
    
    ride_summaries = []
    ride_number = total - (page * size)
    
    for ride in rides:
        avg_rmssd = float(ride['avg_rmssd']) if ride['avg_rmssd'] else baseline_rmssd
        min_rmssd = float(ride['min_rmssd']) if ride['min_rmssd'] else baseline_rmssd
        deviation_pct = ((avg_rmssd - baseline_rmssd) / baseline_rmssd) * 100
        
        alert_count = ride['total_drowsiness_events'] or 0
        microsleep_count = ride['total_microsleep_events'] or 0
        
        if microsleep_count > 0:
            status_icon = "Bad"
        elif alert_count > 2:
            status_icon = "Warning"
        else:
            status_icon = "Good"
        
        ride_summaries.append({
            "ride_id": str(ride['id']),
            "ride_number": ride_number,
            "date": ride['start_time'].date().isoformat(),
            "start_time": ride['start_time'].time().isoformat(),
            "duration_minutes": ride['duration_seconds'] // 60 if ride['duration_seconds'] else 0,
            "avg_rmssd": round(avg_rmssd, 1),
            "lowest_rmssd": round(min_rmssd, 1),
            "baseline_rmssd": round(baseline_rmssd, 1),
            "deviation_pct": round(deviation_pct, 1),
            "alert_count": alert_count,
            "microsleep_count": microsleep_count,
            "fatigue_score": ride['fatigue_score'] or 0,
            "recovery_status": ride['recovery_status'] or "normal",
            "status_icon": status_icon
        })
        
        ride_number -= 1
    
    return {
        "user_id": user_id,
        "total_rides": total,
        "page": page,
        "size": size,
        "rides": ride_summaries
    }





@app.get("/health")
def health_check():
    """Health check endpoint"""
    from config.database import test_connection
    
    db_healthy = test_connection()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "version": "2.0.0",
        "architecture": "N-Tier (Repository + Service)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
