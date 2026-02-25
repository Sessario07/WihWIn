import asyncpg
from datetime import datetime
from typing import Optional, Dict
from contextlib import asynccontextmanager


class RideAggregatorRepository:
    _pool: asyncpg.Pool = None

    @classmethod
    async def init_pool(cls, db_url: str, min_conn: int = 1, max_conn: int = 5):
        cls._pool = await asyncpg.create_pool(
            db_url, min_size=min_conn, max_size=max_conn
        )
        print(f"[REPOSITORY] Database connection pool made: ({min_conn}-{max_conn} connections)")

    @classmethod
    async def close_pool(cls):
        if cls._pool:
            await cls._pool.close()
            print("[REPOSITORY] Database connection pool closed")

    @classmethod
    @asynccontextmanager
    async def get_connection(cls):
        async with cls._pool.acquire() as conn:
            yield conn

    @classmethod
    async def get_ride_by_id(cls, ride_id: str) -> Optional[Dict]:
        async with cls.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT id, device_id, user_id, start_time, end_time, status
                FROM rides WHERE id = $1
            """, ride_id)
            return dict(row) if row else None

    @classmethod
    async def get_ride_stats(cls, ride_id: str) -> Optional[Dict]:
        async with cls.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    AVG(hr) as avg_hr,
                    MAX(hr) as max_hr,
                    MIN(hr) as min_hr,
                    COUNT(*) as total_records
                FROM raw_ppg_telemetry
                WHERE ride_id = $1 AND hr IS NOT NULL
            """, ride_id)
            return dict(row) if row else None

    @classmethod
    async def get_drowsiness_event_stats(cls, ride_id: str) -> Dict:
        async with cls.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    COALESCE(COUNT(*) FILTER (WHERE status IN ('DROWSY', 'MICROSLEEP')), 0) as total_drowsiness_events,
                    COALESCE(COUNT(*) FILTER (WHERE status = 'MICROSLEEP'), 0) as total_microsleep_events,
                    MAX(severity_score) as max_drowsiness_score,
                    AVG(severity_score) as avg_drowsiness_score
                FROM drowsiness_events
                WHERE ride_id = $1
            """, ride_id)

            return {
                'total_drowsiness_events': row['total_drowsiness_events'] or 0,
                'total_microsleep_events': row['total_microsleep_events'] or 0,
                'max_drowsiness_score': row['max_drowsiness_score'],
                'avg_drowsiness_score': row['avg_drowsiness_score']
            }

    @classmethod
    async def complete_ride_with_summary(
        cls,
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
    ) -> Optional[bool]:
        async with cls.get_connection() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT status FROM rides WHERE id = $1 FOR UPDATE", ride_id
                )

                if not row:
                    return False
                if row['status'] == 'completed':
                    return True
                if row['status'] != 'ending':
                    return None

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
