from fastapi import HTTPException
from datetime import datetime
import os
import json
import pika
from repositories.device_repository import DeviceRepository
from repositories.ride_repository import RideRepository
from repositories.telemetry_repository import TelemetryRepository
from models.response_models import RideDetailsResponse, RideEvent, HeartRateMetrics, HRVMetrics

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def publish_ride_end(ride_id: str, end_time: datetime):
    """Publish ride end message to RabbitMQ for async processing"""
    params = pika.URLParameters(RABBITMQ_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue="ride.end", durable=True)
    ch.basic_publish(
        exchange="",
        routing_key="ride.end",
        body=json.dumps({
            "ride_id": str(ride_id),
            "end_time": end_time.isoformat()
        }),
        properties=pika.BasicProperties(delivery_mode=2)  # persistent
    )
    conn.close()
    print(f"[RABBITMQ] [INFO] Published ride.end ride_id={ride_id} end_time={end_time.isoformat()}")

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
        
        print(f"[OK] Started ride {ride_id} for device {device_id}")
        
        return {
            "ride_id": str(ride_id),
            "message": "Ride started successfully"
        }
    
    @staticmethod
    def end_ride(ride_id: str) -> dict:
        """
        End ride asynchronously:
        1. Atomically mark ride as 'ending'
        2. Publish message to RabbitMQ with end_time
        3. Return immediately (aggregation happens in worker)
        """
        # Capture end_time NOW (before any async processing)
        end_time = datetime.now()
        
        # Atomically mark ride as ending (prevents double-publish)
        marked = RideRepository.mark_ride_ending(ride_id)
        if not marked:
            # Check if ride exists and its current status
            ride = RideRepository.get_ride_by_id(ride_id)
            if not ride:
                raise HTTPException(status_code=404, detail="Ride not found")
            if ride['status'] == 'ending':
                return {
                    "success": True,
                    "ride_id": ride_id,
                    "message": "Ride end already in progress"
                }
            if ride['status'] == 'completed':
                return {
                    "success": True,
                    "ride_id": ride_id,
                    "message": "Ride already completed"
                }
            raise HTTPException(status_code=400, detail=f"Cannot end ride with status: {ride['status']}")
        
        # Publish to RabbitMQ for async aggregation (include end_time)
        try:
            publish_ride_end(ride_id, end_time)
        except Exception as e:
            print(f"[RABBITMQ] [ERROR] Failed to publish ride.end: {e}")
            # Note: ride is marked 'ending' but message failed
            # In production, use transactional outbox pattern
            raise HTTPException(status_code=500, detail="Failed to queue ride completion")
        
        return {
            "success": True,
            "ride_id": ride_id,
            "message": "Ride end queued for processing"
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
        
        print(f"[OK] Stored {records_inserted} telemetry entries for device {device_id}")
        
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
