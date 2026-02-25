from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from models.request_models import *
from models.response_models import *
from services.device_service import DeviceService
from services.baseline_service import BaselineService
from services.ride_service import RideService, init_rabbitmq, close_rabbitmq
from services.analytics_service import AnalyticsService
from services.crash_service import CrashService
from config.database import init_pool, close_pool, get_db_connection, test_connection
from repositories.ride_repository import RideRepository
from repositories.baseline_repository import BaselineRepository
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    try:
        await init_rabbitmq()
    except Exception as e:
        logger.warning(f"RabbitMQ not available at startup: {e}")
    yield
    await close_rabbitmq()
    await close_pool()


app = FastAPI(
    title="SmartHelmet FastAPI Backend",
    description="N-Tier architecture with Repository + Service patterns",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/device/check", response_model=DeviceCheckResponse)
async def check_device(device_id: str):
    try:
        return await DeviceService.check_device(device_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking device {device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while checking device")

@app.post("/baseline")
async def compute_baseline(request: BaselineRequest):
    try:
        metrics = await BaselineService.compute_baseline(
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
async def crash_alert(alert: CrashAlert):
    try:
        return await CrashService.handle_crash(
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
async def start_ride(request: RideStart):
    try:
        return await RideService.start_ride(request.device_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting ride for {request.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while starting ride")


@app.post("/rides/{ride_id}/end")
async def end_ride(ride_id: str):
    try:
        return await RideService.end_ride(ride_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending ride {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while ending ride")


@app.get("/rides/{ride_id}/details", response_model=RideDetailsResponse)
async def get_ride_details(ride_id: str):
    try:
        return await RideService.get_ride_details(ride_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ride details for {ride_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching ride details")


@app.get("/rides/{ride_id}/analysis")
async def get_ride_analysis(ride_id: str):
    try:
        ride = await RideRepository.get_ride_by_id(ride_id)
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
async def get_ride_hr_timeline(ride_id: str):
    try:
        ride = await RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT timestamp, hr
                FROM raw_ppg_telemetry
                WHERE ride_id = $1 AND hr IS NOT NULL
                ORDER BY timestamp ASC
            """, ride_id)
        
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
async def get_ride_hrv_timeline(ride_id: str):
    try:
        ride = await RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        baseline_rmssd = ride.get('baseline_rmssd', 45.0)
        
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT timestamp, rmssd, sdnn, pnn50, lf_hf_ratio
                FROM raw_ppg_telemetry
                WHERE ride_id = $1 AND rmssd IS NOT NULL
                ORDER BY timestamp ASC
            """, ride_id)
        
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
async def get_ride_events(ride_id: str):
    try:
        ride = await RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT detected_at, lat, lon, status, severity_score, 
                       hr_at_event, sdnn, rmssd, pnn50, lf_hf_ratio
                FROM drowsiness_events
                WHERE ride_id = $1
                ORDER BY detected_at ASC
            """, ride_id)
        
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
async def get_ride_route(ride_id: str):
    try:
        ride = await RideRepository.get_ride_by_id(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT timestamp, lat, lon
                FROM raw_ppg_telemetry
                WHERE ride_id = $1 AND lat IS NOT NULL AND lon IS NOT NULL
                ORDER BY timestamp ASC
            """, ride_id)
        
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
async def batch_telemetry(batch: TelemetryBatch):
    try:
        return await RideService.save_telemetry_batch(batch.device_id, batch.ride_id, batch.telemetry)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving telemetry batch for {batch.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while saving telemetry")


@app.post("/drowsiness-events")
async def log_drowsiness_event(event: DrowsinessEvent):
    try:
        return await RideService.log_drowsiness_event({
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
async def get_user_baseline(user_id: str):
    try:
        baseline = await BaselineRepository.get_user_baseline_full(user_id)
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
async def delete_user_baseline(user_id: str):
    try:
        deleted = await BaselineRepository.delete_user_baseline(user_id)
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
async def get_daily_hrv_trend(user_id: str, days: int = 30):
    return await AnalyticsService.get_daily_hrv_trend(user_id, days)


@app.get("/users/{user_id}/weekly-fatigue-score")
async def get_weekly_fatigue_score(user_id: str):
    return await AnalyticsService.get_weekly_fatigue_score(user_id)


@app.get("/users/{user_id}/hrv-heatmap")
async def get_hrv_heatmap(user_id: str, days: int = 7):
    return await AnalyticsService.get_hrv_heatmap(user_id, days)


@app.get("/users/{user_id}/lf-hf-trend")
async def get_lf_hf_trend(user_id: str, days: int = 30):
    return await AnalyticsService.get_lf_hf_trend(user_id, days)


@app.get("/users/{user_id}/fatigue-patterns")
async def get_fatigue_patterns(user_id: str):
    return await AnalyticsService.get_fatigue_patterns(user_id)


@app.get("/users/{user_id}/rides")
async def get_user_rides(user_id: str, page: int = 0, size: int = 20):
    try:
        try:
            baseline_data = await BaselineRepository.get_user_baseline(user_id)
            baseline_rmssd = baseline_data['rmssd'] if baseline_data else 42.0
        except Exception:
            baseline_rmssd = 42.0
        
        rides, total = await RideRepository.get_user_rides(user_id, size, page * size)
        
        ride_summaries = []
        ride_number = total - (page * size)
        
        for ride in rides:
            avg_rmssd = float(ride['avg_rmssd']) if ride['avg_rmssd'] else baseline_rmssd
            min_rmssd = float(ride['min_rmssd']) if ride['min_rmssd'] else baseline_rmssd
            deviation_pct = ((avg_rmssd - baseline_rmssd) / baseline_rmssd) * 100 if baseline_rmssd != 0 else 0
            
            alert_count = ride['total_drowsiness_events'] or 0
            microsleep_count = ride['total_microsleep_events'] or 0
            
            if (microsleep_count > 0):
                status_icon = "Bad"
            elif (alert_count > 2):
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
async def health_check():
    db_healthy = await test_connection()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "version": "2.0.0",
        "architecture": "N-Tier (Repository + Service) - Async"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
