from fastapi import HTTPException
from datetime import datetime
from repositories.device_repository import DeviceRepository
from repositories.ride_repository import RideRepository
from repositories.telemetry_repository import TelemetryRepository
from models.response_models import RideDetailsResponse, RideEvent, HeartRateMetrics, HRVMetrics

class RideService:
    @staticmethod
    def start_ride(device_id: str) -> dict:
        device = DeviceRepository.get_device_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        device_uuid = device['id']
        user_id = device.get('user_id')
        
        existing_ride = RideRepository.get_active_ride(device_uuid)
        if existing_ride:
            return {
                "ride_id": str(existing_ride['id']),
                "message": "Ride already active"
            }
        
    
        ride_id = RideRepository.create_ride(device_uuid, user_id)
        
        print(f"✓ Started ride {ride_id} for device {device_id}")
        
        return {
            "ride_id": str(ride_id),
            "message": "Ride started successfully"
        }
    
    @staticmethod
    def end_ride(ride_id: str) -> dict:
        ride = RideRepository.get_ride_by_id(ride_id)
        if not ride or ride['status'] != 'active':
            raise HTTPException(status_code=404, detail="Ride not found or already ended")
        
        end_time = datetime.now()
        start_time = ride['start_time']
        duration_seconds = int((end_time - start_time).total_seconds())

        stats = RideRepository.get_ride_stats(ride_id)
        avg_hr = stats['avg_hr'] if stats else None
        max_hr = stats['max_hr'] if stats else None
        min_hr = stats['min_hr'] if stats else None
        
        
        RideRepository.end_ride(ride_id, end_time, duration_seconds, avg_hr, max_hr, min_hr)
        
        event_stats = TelemetryRepository.get_drowsiness_event_stats(ride_id)
        
        total_drowsiness = event_stats['total_drowsiness_events']
        total_microsleep = event_stats['total_microsleep_events']
        max_score = event_stats['max_drowsiness_score']
        avg_score = event_stats['avg_drowsiness_score']
        
        fatigue_score = min(100, int((total_drowsiness * 10) + (total_microsleep * 20)))
        
        RideRepository.create_ride_summary(
            ride_id, fatigue_score, total_drowsiness, 
            total_microsleep, max_score, avg_score
        )
        
        print(f"✓ Ended ride {ride_id} - Duration: {duration_seconds}s, Fatigue: {fatigue_score}/100")
        
        return {
            "success": True,
            "ride_id": ride_id,
            "duration_seconds": duration_seconds,
            "fatigue_score": fatigue_score,
            "total_drowsiness_events": total_drowsiness,
            "total_microsleep_events": total_microsleep
        }
    
    @staticmethod
    def get_ride_details(ride_id: str) -> RideDetailsResponse:

        ride_data = RideRepository.get_ride_by_id(ride_id)
        
        if not ride_data:
            raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found")
        
        events_data = RideRepository.get_ride_events(ride_id)
        
       
        events = [
            RideEvent(
                timestamp=event['detected_at'].time() if event['detected_at'] else None,
                status=event['status'],
                severity_score=event['severity_score'],
                rmssd=round(event['rmssd'], 1) if event['rmssd'] else None
            )
            for event in events_data
        ]
        
       
        return RideDetailsResponse(
            ride_id=ride_id,
            date=ride_data['start_time'].date() if ride_data['start_time'] else None,
            start_time=ride_data['start_time'].time() if ride_data['start_time'] else None,
            end_time=ride_data['end_time'].time() if ride_data['end_time'] else None,
            duration_minutes=ride_data['duration_seconds'] // 60 if ride_data['duration_seconds'] else 0,
            heart_rate=HeartRateMetrics(
                avg=ride_data['avg_hr'],
                max=ride_data['max_hr'],
                min=ride_data['min_hr']
            ),
            hrv=HRVMetrics(
                avg_rmssd=None,  
                lowest_rmssd=None,
                baseline_rmssd=None,
                deviation_pct=None
            ),
            events=events,
            fatigue_score=ride_data['fatigue_score'] or 0,
            recovery_status="normal"
        )
    
    @staticmethod
    def save_telemetry_batch(device_id: str, ride_id: str, telemetry: list) -> dict:
      
        device = DeviceRepository.get_device_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        device_uuid = device['id']
        
        # Save telemetry
        records_inserted = TelemetryRepository.save_telemetry_batch(
            device_uuid, ride_id, telemetry
        )
        
        # Update last seen
        DeviceRepository.update_last_seen(device_uuid)
        
        print(f"✓ Stored {records_inserted} telemetry entries for device {device_id}")
        
        return {
            "success": True,
            "records_inserted": records_inserted,
            "device_id": device_id
        }
    
    @staticmethod
    def log_drowsiness_event(event_data: dict) -> dict:
       
        device = DeviceRepository.get_device_by_id(event_data['device_id'])
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        device_uuid = device['id']
        
        event_id = TelemetryRepository.save_drowsiness_event(
            event_data['ride_id'], 
            device_uuid, 
            event_data
        )
        
        return {
            "success": True,
            "event_id": str(event_id)
        }
