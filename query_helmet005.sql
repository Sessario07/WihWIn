-- Query all data for HELMET005 from EC2 PostgreSQL
-- Run this with: psql -h 35.77.98.154 -U wihwin -d wihwin -f query_helmet005.sql

\echo '================================================================================'
\echo 'QUERYING ALL DATA FOR HELMET005'
\echo '================================================================================'

-- Get device UUID first
\echo ''
\echo '1. DEVICE INFORMATION'
\echo '-------------------'
SELECT id, device_id, user_id, onboarded, battery_pct, last_seen, created_at
FROM devices 
WHERE device_id = 'HELMET005';

-- Store device_id in a variable (for PostgreSQL 9.6+)
\set device_uuid (SELECT id FROM devices WHERE device_id = 'HELMET005')

\echo ''
\echo '2. USER INFORMATION'
\echo '-------------------'
SELECT u.id, u.username, u.email, u.role, u.created_at
FROM users u
JOIN devices d ON d.user_id = u.id
WHERE d.device_id = 'HELMET005';

\echo ''
\echo '3. BASELINE METRICS'
\echo '-------------------'
SELECT bm.id, bm.mean_hr, bm.sdnn, bm.rmssd, bm.pnn50, 
       bm.lf_hf_ratio, bm.sd1_sd2_ratio, bm.computed_at
FROM baseline_metrics bm
JOIN devices d ON d.id = bm.device_id
WHERE d.device_id = 'HELMET005';

\echo ''
\echo '4. RIDES SUMMARY (Last 10)'
\echo '-------------------'
SELECT r.id, r.start_time, r.end_time, 
       r.duration_seconds / 60 as duration_minutes,
       r.avg_hr, r.avg_rmssd, r.min_rmssd, r.baseline_rmssd,
       ROUND(r.baseline_deviation_pct::numeric, 2) as deviation_pct,
       r.recovery_status, r.status
FROM rides r
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
ORDER BY r.start_time DESC
LIMIT 10;

\echo ''
\echo '5. RIDE COUNT BY STATUS'
\echo '-------------------'
SELECT r.status, COUNT(*) as count
FROM rides r
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
GROUP BY r.status;

\echo ''
\echo '6. RAW PPG TELEMETRY SUMMARY'
\echo '-------------------'
SELECT 
    COUNT(*) as total_records,
    ROUND(AVG(hr)::numeric, 2) as avg_hr,
    ROUND(AVG(sdnn)::numeric, 2) as avg_sdnn,
    ROUND(AVG(rmssd)::numeric, 2) as avg_rmssd,
    ROUND(AVG(pnn50)::numeric, 2) as avg_pnn50,
    ROUND(AVG(lf_hf_ratio)::numeric, 2) as avg_lf_hf_ratio,
    MIN(timestamp) as first_record,
    MAX(timestamp) as last_record
FROM raw_ppg_telemetry t
JOIN devices d ON d.id = t.device_id
WHERE d.device_id = 'HELMET005';

\echo ''
\echo '7. TELEMETRY RECORDS PER RIDE (Top 5 Rides)'
\echo '-------------------'
SELECT 
    r.id as ride_id,
    r.start_time,
    COUNT(t.id) as telemetry_count,
    r.duration_seconds / 60 as duration_minutes
FROM rides r
JOIN raw_ppg_telemetry t ON t.ride_id = r.id
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
GROUP BY r.id, r.start_time, r.duration_seconds
ORDER BY r.start_time DESC
LIMIT 5;

\echo ''
\echo '8. DROWSINESS EVENTS SUMMARY'
\echo '-------------------'
SELECT 
    COUNT(*) as total_events,
    SUM(CASE WHEN status = 'MICROSLEEP' THEN 1 ELSE 0 END) as microsleep_count,
    SUM(CASE WHEN status = 'DROWSY' THEN 1 ELSE 0 END) as drowsy_count,
    SUM(CASE WHEN status = 'AWAKE' THEN 1 ELSE 0 END) as awake_count,
    ROUND(AVG(severity_score)::numeric, 2) as avg_severity,
    MAX(severity_score) as max_severity,
    MIN(detected_at) as first_event,
    MAX(detected_at) as last_event
FROM drowsiness_events de
JOIN devices d ON d.id = de.device_id
WHERE d.device_id = 'HELMET005';

\echo ''
\echo '9. DROWSINESS EVENTS BY RIDE (Rides with most events)'
\echo '-------------------'
SELECT 
    r.id as ride_id,
    r.start_time,
    COUNT(de.id) as event_count,
    ROUND(AVG(de.severity_score)::numeric, 2) as avg_severity,
    MAX(de.severity_score) as max_severity
FROM rides r
LEFT JOIN drowsiness_events de ON de.ride_id = r.id
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
GROUP BY r.id, r.start_time
HAVING COUNT(de.id) > 0
ORDER BY event_count DESC
LIMIT 10;

\echo ''
\echo '10. RIDE SUMMARIES (Last 10 Rides)'
\echo '-------------------'
SELECT 
    rs.ride_id,
    r.start_time,
    rs.fatigue_score,
    rs.total_drowsiness_events,
    rs.total_microsleep_events,
    rs.max_drowsiness_score,
    ROUND(rs.avg_drowsiness_score::numeric, 2) as avg_drowsiness_score,
    ROUND(rs.hrv_decline_pct::numeric, 2) as hrv_decline_pct
FROM ride_summaries rs
JOIN rides r ON r.id = rs.ride_id
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
ORDER BY r.start_time DESC
LIMIT 10;

\echo ''
\echo '11. DAILY HRV TREND (Last 30 Days)'
\echo '-------------------'
SELECT 
    DATE(r.start_time) as ride_date,
    COUNT(r.id) as ride_count,
    ROUND(AVG(t.rmssd)::numeric, 2) as avg_rmssd,
    ROUND(MIN(t.rmssd)::numeric, 2) as min_rmssd,
    ROUND(MAX(t.rmssd)::numeric, 2) as max_rmssd
FROM rides r
JOIN raw_ppg_telemetry t ON t.ride_id = r.id
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
    AND r.start_time >= CURRENT_DATE - INTERVAL '30 days'
    AND r.status = 'completed'
GROUP BY DATE(r.start_time)
ORDER BY ride_date DESC;

\echo ''
\echo '12. WEEKLY FATIGUE SCORE (Last 7 Days)'
\echo '-------------------'
WITH baseline AS (
    SELECT rmssd as baseline_rmssd
    FROM baseline_metrics bm
    JOIN devices d ON d.id = bm.device_id
    WHERE d.device_id = 'HELMET005'
    LIMIT 1
)
SELECT 
    DATE(r.start_time) as ride_date,
    TO_CHAR(r.start_time, 'Day') as day_name,
    COUNT(r.id) as total_rides,
    ROUND(AVG(t.rmssd)::numeric, 2) as avg_rmssd,
    ROUND((SELECT baseline_rmssd FROM baseline)::numeric, 2) as baseline_rmssd,
    ROUND(AVG(ABS(((SELECT baseline_rmssd FROM baseline) - t.rmssd) / (SELECT baseline_rmssd FROM baseline) * 100))::numeric, 2) as avg_deviation_pct,
    SUM(CASE WHEN de.id IS NOT NULL THEN 1 ELSE 0 END) as total_alerts,
    SUM(CASE WHEN de.status = 'MICROSLEEP' THEN 1 ELSE 0 END) as total_microsleeps
FROM rides r
JOIN raw_ppg_telemetry t ON t.ride_id = r.id
LEFT JOIN drowsiness_events de ON de.ride_id = r.id
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
    AND r.start_time >= CURRENT_DATE - INTERVAL '6 days'
    AND r.status = 'completed'
GROUP BY DATE(r.start_time), TO_CHAR(r.start_time, 'Day')
ORDER BY ride_date DESC;

\echo ''
\echo '13. LF/HF RATIO TREND (Last 30 Days)'
\echo '-------------------'
SELECT 
    r.id as ride_id,
    DATE(r.start_time) as ride_date,
    r.start_time::time as start_time,
    r.duration_seconds / 60 as duration_minutes,
    ROUND(AVG(t.lf_hf_ratio)::numeric, 2) as avg_lf_hf,
    ROUND(MAX(t.lf_hf_ratio)::numeric, 2) as peak_lf_hf,
    CASE 
        WHEN MAX(t.lf_hf_ratio) > 2.5 THEN 'SPIKE'
        ELSE 'NORMAL'
    END as stress_indicator
FROM rides r
JOIN raw_ppg_telemetry t ON t.ride_id = r.id
JOIN devices d ON d.id = r.device_id
WHERE d.device_id = 'HELMET005'
    AND r.start_time >= CURRENT_DATE - INTERVAL '30 days'
    AND r.status = 'completed'
    AND t.lf_hf_ratio IS NOT NULL
GROUP BY r.id, DATE(r.start_time), r.start_time, r.duration_seconds
ORDER BY r.start_time DESC
LIMIT 20;

\echo ''
\echo '14. CRASH ALERTS'
\echo '-------------------'
SELECT 
    ca.id,
    ca.detected_at,
    ca.lat,
    ca.lon,
    ca.hospital_notified,
    ca.distance_km
FROM crash_alerts ca
JOIN devices d ON d.id = ca.device_id
WHERE d.device_id = 'HELMET005'
ORDER BY ca.detected_at DESC;

\echo ''
\echo '================================================================================'
\echo 'QUERY COMPLETE'
\echo '================================================================================'
