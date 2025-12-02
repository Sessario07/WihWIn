from config.database import get_db_connection
from typing import Optional, Dict, Tuple

class UserRepository:    
    @staticmethod
    def get_user_info(user_id: str) -> Optional[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.username, u.email, cp.blood_type, cp.allergies, 
                       cp.emergency_contact_name, cp.emergency_contact_phone
                FROM users u
                LEFT JOIN customer_profiles cp ON cp.user_id = u.id
                WHERE u.id = %s
            """, (user_id,))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def find_nearest_hospital(lat: float, lon: float) -> Optional[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    u.id,
                    dp.hospital_name,
                    dp.lat,
                    dp.lon,
                    point(%s, %s) <@> point(dp.lon, dp.lat) AS distance_km
                FROM doctor_profiles dp
                JOIN users u ON u.id = dp.user_id
                WHERE dp.on_duty = TRUE
                ORDER BY distance_km ASC
                LIMIT 1
            """, (lon, lat))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def create_crash_alert(device_uuid: str, lat: float, lon: float,
                          notified_doctor_id: Optional[str], 
                          distance_km: Optional[float]) -> str:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO crash_alerts 
                (device_id, lat, lon, hospital_notified, notified_doctor_id, 
                 distance_km, notification_sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                RETURNING id
            """, (
                device_uuid, lat, lon, 
                notified_doctor_id is not None,
                notified_doctor_id, 
                distance_km
            ))
            
            return str(cur.fetchone()['id'])
