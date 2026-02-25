from fastapi import FastAPI, HTTPException
from models.request_models import *
from models.response_models import *
from services.device_service import DeviceService
from services.baseline_service import BaselineService
from services.ride_service import RideService
from services.analytics_service import AnalyticsService
from services.crash_service import CrashService
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartHelmet FastAPI Backend",
    description="N-Tier architecture with Repository + Service patterns",
    version="2.0.0"
)

@app.get("/device/check", response_model=DeviceCheckResponse)
def check_device(device_id: str):
    try:
        return DeviceService.check_device(device_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while checking device")

@app.post("/baseline")
def compute_baseline(request: BaselineRequest):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing baseline for {request.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while computing baseline")

@app.post("/crash")
def crash_alert(alert: CrashAlert):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing crash alert for {alert.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while processing crash alert")

@app.post("/rides/start")
def start_ride(request: RideStart):
    try:
        return RideService.start_ride(request.device_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting ride for {request.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while starting ride")


@app.post("/rides/{ride_id}/end")
def end_ride(ride_id: str):
    try:
        return RideService.end_ride(ride_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending ride {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while ending ride")


@app.get("/rides/{ride_id}/details", response_model=RideDetailsResponse)
def get_ride_details(ride_id: str):
    try:
        return RideService.get_ride_details(ride_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ride details for {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching ride details")


@app.get("/rides/{ride_id}/analysis")
def get_ride_analysis(ride_id: str):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ride analysis for {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching ride analysis")

@app.get("/rides/{ride_id}/hr-timeline")
def get_ride_hr_timeline(ride_id: str):
    try:
        from repositories.ride_repository import RideRepository
        from config.database import get_db_connection
        
        ride = RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, hr
                FROM raw_ppg_telemetry
                WHERE ride_id = %s AND hr IS NOT NULL
                ORDER BY timestamp ASC
            """, (ride_id,))
            
            rows = cursor.fetchall()
        
        return {
            "ride_id": ride_id,
            "data": [
                {
                    "timestamp": row['timestamp'].isoformat(),
                    "hr": float(row['hr'])
                }
                for row in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HR timeline for ride {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching HR timeline")

@app.get("/rides/{ride_id}/hrv-timeline")
def get_ride_hrv_timeline(ride_id: str):
    try:
        from repositories.ride_repository import RideRepository
        from config.database import get_db_connection
        
        ride = RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        baseline_rmssd = ride.get('baseline_rmssd', 45.0)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, rmssd, sdnn, pnn50, lf_hf_ratio
                FROM raw_ppg_telemetry
                WHERE ride_id = %s AND rmssd IS NOT NULL
                ORDER BY timestamp ASC
            """, (ride_id,))
            
            rows = cursor.fetchall()
        
        return {
            "ride_id": ride_id,
            "baseline_rmssd": baseline_rmssd,
            "data": [
                {
                    "timestamp": row['timestamp'].isoformat(),
                    "rmssd": float(row['rmssd']),
                    "sdnn": float(row['sdnn']) if row['sdnn'] else None,
                    "pnn50": float(row['pnn50']) if row['pnn50'] else None,
                    "lf_hf_ratio": float(row['lf_hf_ratio']) if row['lf_hf_ratio'] else None
                }
                for row in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HRV timeline for ride {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching HRV timeline")

@app.get("/rides/{ride_id}/events")
def get_ride_events(ride_id: str):
    try:
        from repositories.ride_repository import RideRepository
        from config.database import get_db_connection
        
        ride = RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT detected_at, lat, lon, status, severity_score, 
                       hr_at_event, sdnn, rmssd, pnn50, lf_hf_ratio
                FROM drowsiness_events
                WHERE ride_id = %s
                ORDER BY detected_at ASC
            """, (ride_id,))
            
            rows = cursor.fetchall()
        
        return {
            "ride_id": ride_id,
            "total_events": len(rows),
            "events": [
                {
                    "timestamp": row['detected_at'].isoformat(),
                    "lat": float(row['lat']) if row['lat'] else None,
                    "lon": float(row['lon']) if row['lon'] else None,
                    "status": row['status'],
                    "severity_score": row['severity_score'],
                    "metrics": {
                        "hr": float(row['hr_at_event']) if row['hr_at_event'] else None,
                        "sdnn": float(row['sdnn']) if row['sdnn'] else None,
                        "rmssd": float(row['rmssd']) if row['rmssd'] else None,
                        "pnn50": float(row['pnn50']) if row['pnn50'] else None,
                        "lf_hf_ratio": float(row['lf_hf_ratio']) if row['lf_hf_ratio'] else None
                    }
                }
                for row in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events for ride {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching ride events")

@app.get("/rides/{ride_id}/route")
def get_ride_route(ride_id: str):
    try:
        from repositories.ride_repository import RideRepository
        from config.database import get_db_connection
        
        ride = RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, lat, lon
                FROM raw_ppg_telemetry
                WHERE ride_id = %s AND lat IS NOT NULL AND lon IS NOT NULL
                ORDER BY timestamp ASC
            """, (ride_id,))
            
            rows = cursor.fetchall()
        
        return {
            "ride_id": ride_id,
            "route": [
                {
                    "timestamp": row['timestamp'].isoformat(),
                    "lat": float(row['lat']),
                    "lon": float(row['lon'])
                }
                for row in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting route for ride {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching ride route")

@app.post("/telemetry/batch")
def batch_telemetry(batch: TelemetryBatch):
    try:
        return RideService.save_telemetry_batch(batch.device_id, batch.ride_id, batch.telemetry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving telemetry batch for {batch.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while saving telemetry")


@app.post("/drowsiness-events")
def log_drowsiness_event(event: DrowsinessEvent):
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging drowsiness event for {event.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while logging drowsiness event")


@app.get("/users/{user_id}/baseline")
def get_user_baseline(user_id: str):
    try:
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
    except Exception as e:
        logger.error(f"Error getting baseline for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching baseline")


@app.delete("/users/{user_id}/baseline")
def delete_user_baseline(user_id: str):
    try:
        from repositories.baseline_repository import BaselineRepository
        
        deleted = BaselineRepository.delete_user_baseline(user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="No baseline found for this user")
        
        return {
            "success": True,
            "message": "Baseline deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting baseline for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while deleting baseline")


@app.get("/users/{user_id}/daily-hrv-trend")
def get_daily_hrv_trend(user_id: str, days: int = 30):
    return AnalyticsService.get_daily_hrv_trend(user_id, days)


@app.get("/users/{user_id}/weekly-fatigue-score")
def get_weekly_fatigue_score(user_id: str):
    return AnalyticsService.get_weekly_fatigue_score(user_id)


@app.get("/users/{user_id}/hrv-heatmap")
def get_hrv_heatmap(user_id: str, days: int = 7):
    return AnalyticsService.get_hrv_heatmap(user_id, days)


@app.get("/users/{user_id}/lf-hf-trend")
def get_lf_hf_trend(user_id: str, days: int = 30):
    return AnalyticsService.get_lf_hf_trend(user_id, days)


@app.get("/users/{user_id}/fatigue-patterns")
def get_fatigue_patterns(user_id: str):
    return AnalyticsService.get_fatigue_patterns(user_id)


@app.get("/users/{user_id}/rides")
def get_user_rides(user_id: str, page: int = 0, size: int = 20):
    try:
        from repositories.ride_repository import RideRepository
        from repositories.baseline_repository import BaselineRepository
        
        try:
            baseline_data = BaselineRepository.get_user_baseline(user_id)
            baseline_rmssd = baseline_data['rmssd'] if baseline_data else 42.0
        except Exception:
            baseline_rmssd = 42.0
        
        rides, total = RideRepository.get_user_rides(user_id, size, page * size)
        
        ride_summaries = []
        ride_number = total - (page * size)
        
        for ride in rides:
            avg_rmssd = float(ride['avg_rmssd']) if ride['avg_rmssd'] else baseline_rmssd
            min_rmssd = float(ride['min_rmssd']) if ride['min_rmssd'] else baseline_rmssd
            deviation_pct = ((avg_rmssd - baseline_rmssd) / baseline_rmssd) * 100 if baseline_rmssd != 0 else 0
            
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rides for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching user rides")


@app.get("/health")
def health_check():
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
