from config.database import get_db_connection
from typing import Optional, Dict
from uuid import UUID

class DeviceRepository:
    @staticmethod
    async def get_device_by_id(device_id: str) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                "SELECT id, onboarded, user_id FROM devices WHERE device_id = $1",
                device_id
            )
            return dict(row) if row else None
    
    @staticmethod
    async def create_device(device_id: str) -> UUID:
        async with get_db_connection() as conn:
            return await conn.fetchval(
                "INSERT INTO devices (device_id, onboarded) VALUES ($1, $2) RETURNING id",
                device_id, False
            )
    
    @staticmethod
    async def mark_onboarded(device_uuid: UUID) -> None:
        async with get_db_connection() as conn:
            await conn.execute(
                "UPDATE devices SET onboarded = TRUE WHERE id = $1",
                device_uuid
            )
    
    @staticmethod
    async def update_last_seen(device_uuid: UUID) -> None:
        async with get_db_connection() as conn:
            await conn.execute(
                "UPDATE devices SET last_seen = now() WHERE id = $1",
                device_uuid
            )
