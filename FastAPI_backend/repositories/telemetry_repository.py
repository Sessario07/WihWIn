from config.database import get_db_connection
from typing import List, Dict, Optional
from uuid import UUID
import uuid as uuid_module

#delete once finish testing
def is_valid_uuid(val: str) -> bool:
    if not val:
        return False
    try:
        uuid_module.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False

class TelemetryRepository:
    @staticmethod
    def save_telemetry_batch(device_uuid: UUID, ride_id: Optional[str], telemetry: List[dict]) -> int:
        valid_ride_id = ride_id if ride_id and is_valid_uuid(ride_id) else None
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            insert_query = """
                INSERT INTO raw_ppg_telemetry 
                (device_id, ride_id, timestamp, hr, ibi_ms, sdnn, rmssd, pnn50, lf_hf_ratio, 
                 accel_x, accel_y, accel_z, lat, lon)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            for entry in telemetry:
                cur.execute(insert_query, (
                    device_uuid,
                    valid_ride_id,
                    entry.get('timestamp'),
                    entry.get('hr'),
                    entry.get('ibi_ms'),
                    entry.get('sdnn'),
                    entry.get('rmssd'),
                    entry.get('pnn50'),
                    entry.get('lf_hf_ratio'),
                    entry.get('accel_x'),
                    entry.get('accel_y'),
                    entry.get('accel_z'),
                    entry.get('lat'),
                    entry.get('lon')
                ))
            
            return len(telemetry)
    
    @staticmethod
    def save_drowsiness_event(ride_id: str, device_uuid: UUID, event_data: Dict) -> UUID:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO drowsiness_events 
                (ride_id, device_id, detected_at, severity_score, status, hr_at_event, 
                 sdnn, rmssd, pnn50, lf_hf_ratio, lat, lon)
                VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                ride_id, device_uuid, 
                event_data['severity_score'], event_data['status'],
                event_data['hr_at_event'], event_data['sdnn'], 
                event_data['rmssd'], event_data['pnn50'], 
                event_data['lf_hf_ratio'], event_data['lat'], event_data['lon']
            ))
            
            return cur.fetchone()['id']
    
    @staticmethod
    def get_drowsiness_event_stats(ride_id: str) -> Dict:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status != 'AWAKE') as total_drowsiness_events,
                    COUNT(*) FILTER (WHERE status = 'MICROSLEEP') as total_microsleep_events,
                    MAX(severity_score) as max_drowsiness_score,
                    AVG(severity_score) as avg_drowsiness_score
                FROM drowsiness_events
                WHERE ride_id = %s
            """, (ride_id,))
            
            result = cur.fetchone()
            return dict(result) if result else {
                'total_drowsiness_events': 0,
                'total_microsleep_events': 0,
                'max_drowsiness_score': 0,
                'avg_drowsiness_score': 0.0
            }
