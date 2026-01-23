from config.database import get_db_connection
from typing import Optional, Dict
from uuid import UUID

class DeviceRepository:
    @staticmethod
    def get_device_by_id(device_id: str) -> Optional[Dict]:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, onboarded, user_id FROM devices WHERE device_id = %s",
                (device_id,)
            )
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def create_device(device_id: str) -> UUID:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO devices (device_id, onboarded) VALUES (%s, %s) RETURNING id",
                (device_id, False)
            )
            return cur.fetchone()['id']
    
    @staticmethod
    def mark_onboarded(device_uuid: UUID) -> None:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE devices SET onboarded = TRUE WHERE id = %s",
                (device_uuid,)
            )
    
    @staticmethod
    def update_last_seen(device_uuid: UUID) -> None:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE devices SET last_seen = now() WHERE id = %s",
                (device_uuid,)
            )
