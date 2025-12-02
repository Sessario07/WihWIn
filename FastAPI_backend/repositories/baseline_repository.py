from config.database import get_db_connection
from typing import Optional, Dict
from uuid import UUID

class BaselineRepository:   
    @staticmethod
    def get_latest_baseline(device_uuid: UUID) -> Optional[Dict]:
       
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT mean_hr, sdnn, rmssd, pnn50, lf_hf_ratio, 
                       sd1_sd2_ratio, accel_var, hr_decay_rate
                FROM baseline_metrics
                WHERE device_id = %s
                ORDER BY computed_at DESC
                LIMIT 1
            """, (device_uuid,))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    @staticmethod
    def save_baseline(device_uuid: UUID, metrics: Dict) -> None:
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO baseline_metrics 
                (device_id, mean_hr, sdnn, rmssd, pnn50, lf_hf_ratio, 
                 sd1_sd2_ratio, accel_var, hr_decay_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                device_uuid,
                metrics['mean_hr'],
                metrics['sdnn'],
                metrics['rmssd'],
                metrics['pnn50'],
                metrics['lf_hf_ratio'],
                metrics['sd1_sd2_ratio'],
                metrics['accel_var'],
                metrics['hr_decay_rate']
            ))
    
    @staticmethod
    def get_user_baseline(user_id: str) -> Optional[Dict]:
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT bm.rmssd
                FROM baseline_metrics bm
                JOIN devices d ON d.id = bm.device_id
                WHERE d.user_id = %s
                ORDER BY bm.computed_at DESC
                LIMIT 1
            """, (user_id,))
            
            result = cur.fetchone()
            return dict(result) if result else None
