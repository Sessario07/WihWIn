from config.database import get_db_connection
from datetime import datetime, timedelta
from fastapi import HTTPException
from repositories.baseline_repository import BaselineRepository

class AnalyticsService: 
    @staticmethod
    def get_daily_hrv_trend(user_id: str, days: int = 30) -> dict:
        days = int(days)
        baseline_data = BaselineRepository.get_user_baseline(user_id)
        baseline_rmssd = baseline_data['rmssd'] if baseline_data else 42.0
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(r.start_time) as ride_date,
                    AVG(t.rmssd) as avg_rmssd,
                    MIN(t.rmssd) as min_rmssd,
                    MAX(t.rmssd) as max_rmssd
                FROM rides r
                JOIN raw_ppg_telemetry t ON t.ride_id = r.id::text
                WHERE r.user_id = %s 
                    AND r.start_time >= CURRENT_DATE - make_interval(days := %s)
                    AND r.status = 'completed'
                GROUP BY ride_date
                ORDER BY ride_date ASC
            """, (user_id, days))
            
            rows = cur.fetchall()
        
        data = []
        rmssd_values = [float(row['avg_rmssd']) if row['avg_rmssd'] else baseline_rmssd for row in rows]
        
        for i, row in enumerate(rows):
            start_idx = max(0, i - 6)
            window = rmssd_values[start_idx:i+1]
            moving_avg = sum(window) / len(window) if window else baseline_rmssd
            
            data.append({
                "date": row['ride_date'].isoformat(),
                "avg_rmssd": float(row['avg_rmssd']) if row['avg_rmssd'] else baseline_rmssd,
                "min_rmssd": float(row['min_rmssd']) if row['min_rmssd'] else baseline_rmssd,
                "max_rmssd": float(row['max_rmssd']) if row['max_rmssd'] else baseline_rmssd,
                "moving_avg_7day": round(moving_avg, 2)
            })
        
        return {
            "user_id": user_id,
            "baseline_rmssd": baseline_rmssd,
            "period_days": days,
            "data": data
        }
    
    @staticmethod
    def get_weekly_fatigue_score(user_id: str) -> dict:
        baseline_data = BaselineRepository.get_user_baseline(user_id)
        baseline_rmssd = baseline_data['rmssd'] if baseline_data else 42.0
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(r.start_time) as ride_date,
                    AVG(t.rmssd) as avg_rmssd
                FROM rides r
                JOIN raw_ppg_telemetry t ON t.ride_id = r.id::text
                WHERE r.user_id = %s 
                    AND r.start_time >= CURRENT_DATE - make_interval(days := 6)
                    AND r.status = 'completed'
                GROUP BY ride_date
                ORDER BY ride_date ASC
            """, (user_id,))
            
            rows = cur.fetchall()
        
        scores = []
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for row in rows:
            avg_rmssd = float(row['avg_rmssd']) if row['avg_rmssd'] else baseline_rmssd
            deviation_pct = abs(((baseline_rmssd - avg_rmssd) / baseline_rmssd) * 100)
            
            if deviation_pct < 20:
                color = "green"
                level = "low"
            elif deviation_pct < 40:
                color = "yellow"
                level = "medium"
            else:
                color = "red"
                level = "high"
            
            day_of_week = row['ride_date'].weekday()
            
            scores.append({
                "day": day_names[day_of_week],
                "date": row['ride_date'].isoformat(),
                "score": int(deviation_pct),
                "color": color,
                "level": level
            })
        
        week_start = (datetime.now() - timedelta(days=6)).date()
        week_end = datetime.now().date()
        
        return {
            "user_id": user_id,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "scores": scores
        }
    
    @staticmethod
    def get_hrv_heatmap(user_id: str, days: int = 7) -> dict:
        days = int(days)
        baseline_data = BaselineRepository.get_user_baseline(user_id)
        baseline_rmssd = baseline_data['rmssd'] if baseline_data else 42.0
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    DATE(t.timestamp) as date,
                    EXTRACT(HOUR FROM t.timestamp) as hour,
                    AVG(t.rmssd) as avg_rmssd,
                    COUNT(de.id) as event_count
                FROM raw_ppg_telemetry t
                JOIN rides r ON r.id = t.ride_id
                LEFT JOIN drowsiness_events de ON de.ride_id = r.id 
                    AND DATE_TRUNC('hour', de.detected_at) = DATE_TRUNC('hour', t.timestamp)
                WHERE r.user_id = %s 
                    AND t.timestamp >= CURRENT_DATE - make_interval(days := %s)
                GROUP BY date, hour
                ORDER BY date ASC, hour ASC
            """, (user_id, days))
            
            rows = cur.fetchall()
   
        heatmap_dict = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for row in rows:
            date = row['date']
            hour = int(row['hour'])
            avg_rmssd = float(row['avg_rmssd']) if row['avg_rmssd'] else baseline_rmssd
            event_count = row['event_count'] or 0
            
            deviation_pct = abs(((baseline_rmssd - avg_rmssd) / baseline_rmssd) * 100)

            if deviation_pct < 20:
                color = "green"
                severity = "normal"
            elif deviation_pct < 40:
                color = "yellow"
                severity = "medium"
            else:
                color = "red"
                severity = "high"
            
            if date not in heatmap_dict:
                heatmap_dict[date] = {
                    "date": date.isoformat(),
                    "day_name": day_names[date.weekday()],
                    "hours": []
                }
            
            heatmap_dict[date]["hours"].append({
                "hour": hour,
                "avg_deviation_pct": round(deviation_pct, 1),
                "event_count": event_count,
                "color": color,
                "severity": severity
            })
        
        heatmap = list(heatmap_dict.values())
        
        return {
            "user_id": user_id,
            "days": days,
            "heatmap": heatmap
        }
    
    @staticmethod
    def get_lf_hf_trend(user_id: str, days: int = 30) -> dict:
        days = int(days)
        threshold = 2.5
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    r.id,
                    r.start_time,
                    AVG(t.lf_hf_ratio) as avg_lf_hf,
                    MAX(t.lf_hf_ratio) as peak_lf_hf,
                    r.duration_seconds
                FROM rides r
                JOIN raw_ppg_telemetry t ON t.ride_id = r.id::text
                WHERE r.user_id = %s 
                    AND r.start_time >= CURRENT_DATE - make_interval(days := %s)
                    AND r.status = 'completed'
                    AND t.lf_hf_ratio IS NOT NULL
                GROUP BY r.id, r.start_time, r.duration_seconds
                ORDER BY r.start_time ASC
            """, (user_id, days))
            
            rows = cur.fetchall()
        
        data = []
        for row in rows:
            avg_lf_hf = float(row['avg_lf_hf']) if row['avg_lf_hf'] else 1.5
            peak_lf_hf = float(row['peak_lf_hf']) if row['peak_lf_hf'] else 1.5
            is_spike = peak_lf_hf > threshold
            
            data.append({
                "ride_id": str(row['id']),
                "date": row['start_time'].date().isoformat(),
                "start_time": row['start_time'].time().isoformat(),
                "avg_lf_hf_ratio": round(avg_lf_hf, 2),
                "peak_lf_hf_ratio": round(peak_lf_hf, 2),
                "is_spike": is_spike,
                "duration_minutes": row['duration_seconds'] // 60 if row['duration_seconds'] else 0
            })
        
        return {
            "user_id": user_id,
            "threshold": threshold,
            "period_days": days,
            "data": data
        }
    
    @staticmethod
    def get_fatigue_patterns(user_id: str) -> dict:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    EXTRACT(HOUR FROM de.detected_at) as hour_of_day,
                    COUNT(*) as event_count,
                    AVG(de.severity_score) as avg_severity
                FROM drowsiness_events de
                JOIN rides r ON r.id = de.ride_id
                WHERE r.user_id = %s
                GROUP BY hour_of_day
                ORDER BY hour_of_day
            """, (user_id,))
            
            hourly_rows = cur.fetchall()
            
            cur.execute("""
                SELECT 
                    EXTRACT(DOW FROM de.detected_at) as day_of_week,
                    COUNT(*) as event_count,
                    AVG(de.severity_score) as avg_severity
                FROM drowsiness_events de
                JOIN rides r ON r.id = de.ride_id
                WHERE r.user_id = %s
                GROUP BY day_of_week
                ORDER BY day_of_week
            """, (user_id,))
            
            daily_rows = cur.fetchall()
        
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        
        return {
            "user_id": user_id,
            "patterns": {
                "by_hour": [
                    {
                        "hour": int(row['hour_of_day']),
                        "event_count": row['event_count'],
                        "avg_severity": float(row['avg_severity']) if row['avg_severity'] else 0
                    } for row in hourly_rows
                ],
                "by_day": [
                    {
                        "day_of_week": int(row['day_of_week']),
                        "day_name": day_names[int(row['day_of_week'])],
                        "event_count": row['event_count'],
                        "avg_severity": float(row['avg_severity']) if row['avg_severity'] else 0
                    } for row in daily_rows
                ]
            }
        }
