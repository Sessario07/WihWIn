from config.database import get_db_connection
from typing import Optional, List, Dict, Tuple
from uuid import UUID
from datetime import datetime

class RideRepository:
    @staticmethod
    def get_ride_by_id(ride_id: str) -> Optional[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    r.id,
                    r.device_id,
                    r.user_id,
                    r.start_time,
                    r.end_time,
                    r.duration_seconds,
                    r.avg_hr,
                    r.max_hr,
                    r.min_hr,
                    r.status,
                    d.device_id as device_code,
                    rs.fatigue_score,
                    rs.total_drowsiness_events,
                    rs.total_microsleep_events,
                    rs.max_drowsiness_score,
                    rs.avg_drowsiness_score
                FROM rides r
                JOIN devices d ON d.id = r.device_id
                LEFT JOIN ride_summaries rs ON rs.ride_id = r.id
                WHERE r.id = %s
            """, (ride_id,))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def get_ride_events(ride_id: str) -> List[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    id,
                    detected_at, 
                    severity_score, 
                    status, 
                    hr_at_event,
                    sdnn, 
                    rmssd, 
                    pnn50, 
                    lf_hf_ratio, 
                    lat, 
                    lon
                FROM drowsiness_events
                WHERE ride_id = %s
                ORDER BY detected_at ASC
            """, (ride_id,))
            
            return [dict(row) for row in cur.fetchall()]
    
    @staticmethod
    def get_active_ride(device_uuid: UUID) -> Optional[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM rides 
                WHERE device_id = %s AND status = 'active'
                ORDER BY start_time DESC
                LIMIT 1
            """, (device_uuid,))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def create_ride(device_uuid: UUID, user_id: Optional[UUID]) -> UUID:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO rides (device_id, user_id, start_time, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id
            """, (device_uuid, user_id, datetime.now()))
            
            return cur.fetchone()['id']
    
    @staticmethod
    def end_ride(ride_id: str, end_time: datetime, duration_seconds: int, 
                 avg_hr: float, max_hr: float, min_hr: float) -> None:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE rides
                SET end_time = %s, duration_seconds = %s, avg_hr = %s, 
                    max_hr = %s, min_hr = %s, status = 'completed'
                WHERE id = %s
            """, (end_time, duration_seconds, avg_hr, max_hr, min_hr, ride_id))
    
    @staticmethod
    def mark_ride_ending(ride_id: str) -> bool:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE rides 
                SET status = 'ending'
                WHERE id = %s AND status = 'active'
                RETURNING id
            """, (ride_id,))
            result = cur.fetchone()
            return result is not None
    
    @staticmethod
    def complete_ride_with_summary(
        ride_id: str,
        end_time: datetime,
        duration_seconds: int,
        avg_hr: Optional[float],
        max_hr: Optional[float],
        min_hr: Optional[float],
        fatigue_score: int,
        total_drowsiness: int,
        total_microsleep: int,
        max_score: Optional[int],
        avg_score: Optional[float]
    ) -> bool:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT status FROM rides WHERE id = %s", (ride_id,))
            result = cur.fetchone()
            
            if not result:
                return False
            
            if result['status'] == 'completed':
                return True
            
            if result['status'] != 'ending':
                return False
            
            cur.execute("""
                UPDATE rides
                SET end_time = %s, duration_seconds = %s, avg_hr = %s,
                    max_hr = %s, min_hr = %s, status = 'completed'
                WHERE id = %s AND status = 'ending'
            """, (end_time, duration_seconds, avg_hr, max_hr, min_hr, ride_id))
            
            cur.execute("""
                INSERT INTO ride_summaries 
                (ride_id, fatigue_score, total_drowsiness_events, total_microsleep_events,
                 max_drowsiness_score, avg_drowsiness_score)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ride_id) DO UPDATE SET
                    fatigue_score = EXCLUDED.fatigue_score,
                    total_drowsiness_events = EXCLUDED.total_drowsiness_events,
                    total_microsleep_events = EXCLUDED.total_microsleep_events,
                    max_drowsiness_score = EXCLUDED.max_drowsiness_score,
                    avg_drowsiness_score = EXCLUDED.avg_drowsiness_score,
                    computed_at = now()
            """, (ride_id, fatigue_score, total_drowsiness, total_microsleep, max_score, avg_score))
            
            return True

    @staticmethod
    def get_ride_stats(ride_id: str) -> Optional[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    AVG(hr) as avg_hr,
                    MAX(hr) as max_hr,
                    MIN(hr) as min_hr,
                    COUNT(*) as total_records
                FROM raw_ppg_telemetry
                WHERE ride_id = %s
            """, (ride_id,))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def get_user_rides(user_id: str, limit: int, offset: int) -> Tuple[List[Dict], int]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute(
                "SELECT COUNT(*) as count FROM rides WHERE user_id = %s AND status = 'completed'",
                (user_id,)
            )
            total = cur.fetchone()['count']
            
            cur.execute("""
                SELECT 
                    r.id,
                    r.start_time,
                    r.duration_seconds,
                    r.avg_rmssd,
                    r.min_rmssd,
                    rs.fatigue_score,
                    rs.total_drowsiness_events,
                    rs.total_microsleep_events,
                    r.recovery_status
                FROM rides r
                LEFT JOIN ride_summaries rs ON rs.ride_id = r.id
                WHERE r.user_id = %s AND r.status = 'completed'
                ORDER BY r.start_time DESC
                LIMIT %s OFFSET %s
            """, (user_id, limit, offset))
            
            rides = [dict(row) for row in cur.fetchall()]
            
            return rides, total
    
    @staticmethod
    def create_ride_summary(ride_id: str, fatigue_score: int, 
                           total_drowsiness: int, total_microsleep: int,
                           max_score: int, avg_score: float) -> None:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ride_summaries 
                (ride_id, fatigue_score, total_drowsiness_events, total_microsleep_events, 
                 max_drowsiness_score, avg_drowsiness_score)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (ride_id, fatigue_score, total_drowsiness, total_microsleep, max_score, avg_score))
