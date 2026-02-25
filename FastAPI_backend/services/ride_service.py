from fastapi import HTTPException
from datetime import datetime
import os
import json
import pika
from repositories.device_repository import DeviceRepository
from repositories.ride_repository import RideRepository
from repositories.telemetry_repository import TelemetryRepository
from models.response_models import RideDetailsResponse, RideEvent, HeartRateMetrics, HRVMetrics
import logging

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def publish_ride_end(ride_id: str, end_time: datetime):
    conn = None
    try:
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
            properties=pika.BasicProperties(delivery_mode=2)
        )
    except Exception as e:
        logger.error(f"Failed to publish ride end for {ride_id}: {e}")
        raise
    finally:
        if conn and not conn.is_closed:
            try:
                conn.close()
            except Exception:
                pass

class RideService:
    @staticmethod
    def start_ride(device_id: str) -> dict:
        try:
            device = DeviceRepository.get_device_by_id(device_id)
        except Exception as e:
            logger.error(f"DB error looking up device {device_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while looking up device")

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        device_uuid = device['id']
        user_id = device.get('user_id')
        
        try:
            existing_ride = RideRepository.get_active_ride(device_uuid)
            if existing_ride:
                return {
                    "ride_id": str(existing_ride['id']),
                    "message": "Ride already active"
                }
            
            ride_id = RideRepository.create_ride(device_uuid, user_id)
        except Exception as e:
            logger.error(f"DB error managing ride for device {device_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while starting ride")
        
        return {
            "ride_id": str(ride_id),
            "message": "Ride started successfully"
        }
    
    @staticmethod
    def end_ride(ride_id: str) -> dict:
        end_time = datetime.now()
        
        try:
            marked = RideRepository.mark_ride_ending(ride_id)
        except Exception as e:
            logger.error(f"DB error marking ride {ride_id} as ending: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while ending ride")

        if not marked:
            try:
                ride = RideRepository.get_ride_by_id(ride_id)
            except Exception as e:
                logger.error(f"DB error looking up ride {ride_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error while looking up ride")

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
        
        try:
            publish_ride_end(ride_id, end_time)
        except Exception as e:
            logger.error(f"Failed to queue ride end for {ride_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to queue ride completion")
        
        return {
            "success": True,
            "ride_id": ride_id,
            "message": "Ride end queued for processing"
        }
    
    @staticmethod
    def get_ride_details(ride_id: str) -> RideDetailsResponse:
        try:
            ride_data = RideRepository.get_ride_by_id(ride_id)
        except Exception as e:
            logger.error(f"DB error fetching ride {ride_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while fetching ride")
        
        if not ride_data:
            raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found")
        
        try:
            events_data = RideRepository.get_ride_events(ride_id)
        except Exception as e:
            logger.error(f"DB error fetching events for ride {ride_id}: {e}")
            events_data = []
        
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
        try:
            device = DeviceRepository.get_device_by_id(device_id)
            #delete once finish testing
            if not device:
                device_uuid = DeviceRepository.create_device(device_id)
            else:
                device_uuid = device['id']
        except Exception as e:
            logger.error(f"DB error looking up/creating device {device_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while processing device")

        try:
            records_inserted = TelemetryRepository.save_telemetry_batch(
                device_uuid, ride_id, telemetry
            )
        except Exception as e:
            logger.error(f"DB error saving telemetry batch for {device_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while saving telemetry")

        try:
            DeviceRepository.update_last_seen(device_uuid)
        except Exception as e:
            logger.warning(f"Failed to update last_seen for device {device_id}: {e}")
        
        return {
            "success": True,
            "records_inserted": records_inserted,
            "device_id": device_id
        }
    
    @staticmethod
    def log_drowsiness_event(event_data: dict) -> dict:
        try:
            device = DeviceRepository.get_device_by_id(event_data['device_id'])
        except Exception as e:
            logger.error(f"DB error looking up device {event_data['device_id']}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while looking up device")

        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        device_uuid = device['id']
        
        try:
            event_id = TelemetryRepository.save_drowsiness_event(
                event_data['ride_id'], 
                device_uuid, 
                event_data
            )
        except Exception as e:
            logger.error(f"DB error saving drowsiness event: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while logging drowsiness event")
        
        return {
            "success": True,
            "event_id": str(event_id)
        }
