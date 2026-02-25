from config.database import get_db_connection
from typing import Optional, Dict
from uuid import UUID

class BaselineRepository:   
    @staticmethod
    async def get_latest_baseline(device_uuid: UUID) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT mean_hr, sdnn, rmssd, pnn50, lf_hf_ratio, 
                       sd1_sd2_ratio, accel_var, hr_decay_rate
                FROM baseline_metrics
                WHERE device_id = $1
                ORDER BY computed_at DESC
                LIMIT 1
            """, device_uuid)
            return dict(row) if row else None
    
    @staticmethod
    async def save_baseline(device_uuid: UUID, metrics: Dict) -> None:
        async with get_db_connection() as conn:
            await conn.execute("""
                INSERT INTO baseline_metrics 
                (device_id, mean_hr, sdnn, rmssd, pnn50, lf_hf_ratio, 
                 sd1_sd2_ratio, accel_var, hr_decay_rate)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                device_uuid,
                metrics['mean_hr'], metrics['sdnn'], metrics['rmssd'],
                metrics['pnn50'], metrics['lf_hf_ratio'],
                metrics['sd1_sd2_ratio'], metrics['accel_var'], metrics['hr_decay_rate']
            )
    
    @staticmethod
    async def get_user_baseline(user_id: str) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT bm.rmssd
                FROM baseline_metrics bm
                JOIN devices d ON d.id = bm.device_id
                WHERE d.user_id = $1
                ORDER BY bm.computed_at DESC
                LIMIT 1
            """, user_id)
            return dict(row) if row else None
    
    @staticmethod
    async def get_user_baseline_full(user_id: str) -> Optional[Dict]:
        async with get_db_connection() as conn:
            row = await conn.fetchrow("""
                SELECT bm.mean_hr, bm.sdnn, bm.rmssd, bm.pnn50, 
                       bm.lf_hf_ratio, bm.sd1_sd2_ratio, bm.computed_at
                FROM baseline_metrics bm
                JOIN devices d ON d.id = bm.device_id
                WHERE d.user_id = $1
                ORDER BY bm.computed_at DESC
                LIMIT 1
            """, user_id)
            return dict(row) if row else None
    
    @staticmethod
    async def delete_user_baseline(user_id: str) -> bool:
        async with get_db_connection() as conn:
            result = await conn.execute("""
                DELETE FROM baseline_metrics
                WHERE device_id IN (
                    SELECT id FROM devices WHERE user_id = $1
                )
            """, user_id)
            deleted_count = int(result.split()[-1])
            return deleted_count > 0
