import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from datetime import datetime
from typing import Optional, Dict
from contextlib import contextmanager

class RideAggregatorRepository:
    _pool = None
    
    @classmethod
    def init_pool(cls, db_url: str, min_conn: int = 1, max_conn: int = 5):
        cls._pool = pool.ThreadedConnectionPool(
            min_conn, max_conn, db_url, cursor_factory=RealDictCursor
        )
        print(f"[REPOSITORY] Database connection pool made: ({min_conn}-{max_conn} connections)")
    
    @classmethod
    def close_pool(cls):
        if cls._pool:
            cls._pool.closeall()
            print("[REPOSITORY] Database connection pool closed")
    
    @classmethod
    @contextmanager
    def get_connection(cls):
        conn = cls._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cls._pool.putconn(conn)
    
    @classmethod
    def get_ride_by_id(cls, ride_id: str) -> Optional[Dict]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, device_id, user_id, start_time, end_time, status
                FROM rides WHERE id = %s
            """, (ride_id,))
            result = cur.fetchone()
            cur.close()
            return dict(result) if result else None

    @classmethod
    def get_ride_stats(cls, ride_id: str) -> Optional[Dict]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    AVG(hr) as avg_hr,
                    MAX(hr) as max_hr,
                    MIN(hr) as min_hr,
                    COUNT(*) as total_records
                FROM raw_ppg_telemetry
                WHERE ride_id = %s AND hr IS NOT NULL
            """, (ride_id,))
            result = cur.fetchone()
            cur.close()
            return dict(result) if result else None

    @classmethod
    def get_drowsiness_event_stats(cls, ride_id: str) -> Dict:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COALESCE(COUNT(*) FILTER (WHERE status IN ('DROWSY', 'MICROSLEEP')), 0) as total_drowsiness_events,
                    COALESCE(COUNT(*) FILTER (WHERE status = 'MICROSLEEP'), 0) as total_microsleep_events,
                    MAX(severity_score) as max_drowsiness_score,
                    AVG(severity_score) as avg_drowsiness_score
                FROM drowsiness_events
                WHERE ride_id = %s
            """, (ride_id,))
            result = cur.fetchone()
            cur.close()
            
            return {
                'total_drowsiness_events': result['total_drowsiness_events'] or 0,
                'total_microsleep_events': result['total_microsleep_events'] or 0,
                'max_drowsiness_score': result['max_drowsiness_score'],
                'avg_drowsiness_score': result['avg_drowsiness_score']
            }

    @classmethod
    def complete_ride_with_summary(
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
        with cls.get_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT status FROM rides WHERE id = %s FOR UPDATE", (ride_id,))
            result = cur.fetchone()
            
            if not result:
                cur.close()
                return False
            
            if result['status'] == 'completed':
                cur.close()
                return True
            
            if result['status'] != 'ending':
                cur.close()
                return None
            
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
            
            cur.close()
            return True
