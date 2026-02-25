from config.database import get_db_connection
from typing import Optional, Dict, Tuple

class UserRepository:    
    @staticmethod
    async def get_user_info(user_id: str) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT u.username, u.email, cp.blood_type, cp.allergies, 
                       cp.emergency_contact_name, cp.emergency_contact_phone
                FROM users u
                LEFT JOIN customer_profiles cp ON cp.user_id = u.id
                WHERE u.id = $1
            """, user_id)
            return dict(row) if row else None
    
    @staticmethod
    async def find_nearest_hospital(lat: float, lon: float) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    u.id,
                    dp.hospital_name,
                    dp.lat,
                    dp.lon,
                    point($1, $2) <@> point(dp.lon, dp.lat) AS distance_km
                FROM doctor_profiles dp
                JOIN users u ON u.id = dp.user_id
                WHERE dp.on_duty = TRUE
                ORDER BY distance_km ASC
                LIMIT 1
            """, lon, lat)
            return dict(row) if row else None
    
    @staticmethod
    async def create_crash_alert(device_uuid: str, lat: float, lon: float,
                                 notified_doctor_id: Optional[str], 
                                 distance_km: Optional[float]) -> str:
        async with get_db_connection() as conn:
            result = await conn.fetchval("""
                INSERT INTO crash_alerts 
                (device_id, lat, lon, hospital_notified, notified_doctor_id, 
                 distance_km, notification_sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, now())
                RETURNING id
            """,
                device_uuid, lat, lon,
                notified_doctor_id is not None,
                notified_doctor_id,
                distance_km
            )
            return str(result)
