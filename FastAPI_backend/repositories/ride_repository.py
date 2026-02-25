from config.database import get_db_connection
from typing import Optional, List, Dict, Tuple
from uuid import UUID
from datetime import datetime

class RideRepository:
    @staticmethod
    async def get_ride_by_id(ride_id: str) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    r.id, r.device_id, r.user_id, r.start_time, r.end_time,
                    r.duration_seconds, r.avg_hr, r.max_hr, r.min_hr, r.status,
                    d.device_id as device_code,
                    rs.fatigue_score, rs.total_drowsiness_events,
                    rs.total_microsleep_events, rs.max_drowsiness_score,
                    rs.avg_drowsiness_score
                FROM rides r
                JOIN devices d ON d.id = r.device_id
                LEFT JOIN ride_summaries rs ON rs.ride_id = r.id
                WHERE r.id = $1
            """, ride_id)
            return dict(row) if row else None
    
    @staticmethod
    async def get_ride_events(ride_id: str) -> List[Dict]:
        async with get_db_connection() as conn:
            rows = await conn.fetch("""
                SELECT id, detected_at, severity_score, status, hr_at_event,
                       sdnn, rmssd, pnn50, lf_hf_ratio, lat, lon
                FROM drowsiness_events
                WHERE ride_id = $1
                ORDER BY detected_at ASC
            """, ride_id)
            return [dict(row) for row in rows]
    
    @staticmethod
    async def get_active_ride(device_uuid: UUID) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT id FROM rides 
                WHERE device_id = $1 AND status = 'active'
                ORDER BY start_time DESC
                LIMIT 1
            """, device_uuid)
            return dict(row) if row else None
    
    @staticmethod
    async def create_ride(device_uuid: UUID, user_id: Optional[UUID]) -> UUID:
        async with get_db_connection() as conn:
            return await conn.fetchval("""
                INSERT INTO rides (device_id, user_id, start_time, status)
                VALUES ($1, $2, $3, 'active')
                RETURNING id
            """, device_uuid, user_id, datetime.now())
    
    @staticmethod
    async def end_ride(ride_id: str, end_time: datetime, duration_seconds: int, 
                       avg_hr: float, max_hr: float, min_hr: float) -> None:
        async with get_db_connection() as conn:
            await conn.execute("""
                UPDATE rides
                SET end_time = $1, duration_seconds = $2, avg_hr = $3, 
                    max_hr = $4, min_hr = $5, status = 'completed'
                WHERE id = $6
            """, end_time, duration_seconds, avg_hr, max_hr, min_hr, ride_id)
    
    @staticmethod
    async def mark_ride_ending(ride_id: str) -> bool:
        async with get_db_connection() as conn:
            result = await conn.fetchrow("""
                UPDATE rides 
                SET status = 'ending'
                WHERE id = $1 AND status = 'active'
                RETURNING id
            """, ride_id)
            return result is not None
    
    @staticmethod
    async def complete_ride_with_summary(
        ride_id: str, end_time: datetime, duration_seconds: int,
        avg_hr: Optional[float], max_hr: Optional[float], min_hr: Optional[float],
        fatigue_score: int, total_drowsiness: int, total_microsleep: int,
        max_score: Optional[int], avg_score: Optional[float]
    ) -> bool:
        async with get_db_connection() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT status FROM rides WHERE id = $1", ride_id)
                
                if not row:
                    return False
                if row['status'] == 'completed':
                    return True
                if row['status'] != 'ending':
                    return False
                
                await conn.execute("""
                    UPDATE rides
                    SET end_time = $1, duration_seconds = $2, avg_hr = $3,
                        max_hr = $4, min_hr = $5, status = 'completed'
                    WHERE id = $6 AND status = 'ending'
                """, end_time, duration_seconds, avg_hr, max_hr, min_hr, ride_id)
                
                await conn.execute("""
                    INSERT INTO ride_summaries 
                    (ride_id, fatigue_score, total_drowsiness_events, total_microsleep_events,
                     max_drowsiness_score, avg_drowsiness_score)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (ride_id) DO UPDATE SET
                        fatigue_score = EXCLUDED.fatigue_score,
                        total_drowsiness_events = EXCLUDED.total_drowsiness_events,
                        total_microsleep_events = EXCLUDED.total_microsleep_events,
                        max_drowsiness_score = EXCLUDED.max_drowsiness_score,
                        avg_drowsiness_score = EXCLUDED.avg_drowsiness_score,
                        computed_at = now()
                """, ride_id, fatigue_score, total_drowsiness, total_microsleep, max_score, avg_score)
                
                return True

    @staticmethod
    async def get_ride_stats(ride_id: str) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    AVG(hr) as avg_hr, MAX(hr) as max_hr,
                    MIN(hr) as min_hr, COUNT(*) as total_records
                FROM raw_ppg_telemetry
                WHERE ride_id = $1
            """, ride_id)
            return dict(row) if row else None
    
    @staticmethod
    async def get_user_rides(user_id: str, limit: int, offset: int) -> Tuple[List[Dict], int]:
        async with get_db_connection() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM rides WHERE user_id = $1 AND status = 'completed'",
                user_id
            )
            
            rows = await conn.fetch("""
                SELECT 
                    r.id, r.start_time, r.duration_seconds,
                    r.avg_rmssd, r.min_rmssd,
                    rs.fatigue_score, rs.total_drowsiness_events,
                    rs.total_microsleep_events, r.recovery_status
                FROM rides r
                LEFT JOIN ride_summaries rs ON rs.ride_id = r.id
                WHERE r.user_id = $1 AND r.status = 'completed'
                ORDER BY r.start_time DESC
                LIMIT $2 OFFSET $3
            """, user_id, limit, offset)
            
            return [dict(row) for row in rows], total
    
    @staticmethod
    async def create_ride_summary(ride_id: str, fatigue_score: int, 
                                  total_drowsiness: int, total_microsleep: int,
                                  max_score: int, avg_score: float) -> None:
        async with get_db_connection() as conn:
            await conn.execute("""
                INSERT INTO ride_summaries 
                (ride_id, fatigue_score, total_drowsiness_events, total_microsleep_events, 
                 max_drowsiness_score, avg_drowsiness_score)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, ride_id, fatigue_score, total_drowsiness, total_microsleep, max_score, avg_score)
