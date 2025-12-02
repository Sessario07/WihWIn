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
