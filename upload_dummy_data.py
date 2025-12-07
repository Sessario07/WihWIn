#!/usr/bin/env python3
"""
Upload Dummy Data for HELMET005 to EC2 PostgreSQL
This script creates a complete dataset for testing the Analysis View APIs
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import random
import uuid

# EC2 PostgreSQL Configuration
DB_CONFIG = {
    'host': '35.77.98.154',
    'port': 5432,
    'database': 'wihwin',
    'user': 'wihwin',
    'password': 'wihwin2024'
}

# Test User Configuration
DEVICE_ID = "HELMET005"
TEST_USER_EMAIL = "helmet005@test.com"
TEST_USER_PASSWORD = "Test123!"

def get_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def create_test_user(conn):
    """Create test user for HELMET005"""
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE email = %s", (TEST_USER_EMAIL,))
    user = cursor.fetchone()
    
    if user:
        user_id = user['id']
        print(f"✓ User already exists: {user_id}")
    else:
        # Create user with bcrypt hash for "Test123!"
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            'helmet005_user',
            TEST_USER_EMAIL,
            '$2a$10$XQZ9Y.X5x5x5x5x5x5x5x5OeK5K5K5K5K5K5K5K5K5K5K5K5K',  # Dummy hash
            'customer',
            datetime.now()
        ))
        user_id = cursor.fetchone()['id']
        conn.commit()
        print(f"✓ Created new user: {user_id}")
    
    cursor.close()
    return str(user_id)

def create_device(conn, user_id):
    """Create or get HELMET005 device"""
    cursor = conn.cursor()
    
    # Check if device exists
    cursor.execute("SELECT id FROM devices WHERE device_id = %s", (DEVICE_ID,))
    device = cursor.fetchone()
    
    if device:
        device_uuid = device['id']
        # Update user_id if needed
        cursor.execute("""
            UPDATE devices SET user_id = %s, onboarded = true 
            WHERE device_id = %s
        """, (user_id, DEVICE_ID))
        conn.commit()
        print(f"✓ Device already exists: {device_uuid}")
    else:
        cursor.execute("""
            INSERT INTO devices (device_id, user_id, onboarded, battery_pct, last_seen, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            DEVICE_ID,
            user_id,
            True,
            85,
            datetime.now(),
            datetime.now() - timedelta(days=60)
        ))
        device_uuid = cursor.fetchone()['id']
        conn.commit()
        print(f"✓ Created new device: {device_uuid}")
    
    cursor.close()
    return str(device_uuid)

def create_baseline(conn, device_uuid):
    """Create baseline metrics for HELMET005"""
    cursor = conn.cursor()
    
    # Delete existing baseline
    cursor.execute("DELETE FROM baseline_metrics WHERE device_id = %s", (device_uuid,))
    
    # Insert new baseline
    cursor.execute("""
        INSERT INTO baseline_metrics 
        (device_id, mean_hr, sdnn, rmssd, pnn50, lf_hf_ratio, sd1_sd2_ratio, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        device_uuid,
        72.0,  # mean_hr
        52.3,  # sdnn
        45.8,  # rmssd
        23.5,  # pnn50
        1.8,   # lf_hf_ratio
        0.5,   # sd1_sd2_ratio
        datetime.now() - timedelta(days=30)
    ))
    
    baseline_id = cursor.fetchone()['id']
    conn.commit()
    cursor.close()
    
    print(f"✓ Created baseline: {baseline_id}")
    return str(baseline_id)

def create_rides_with_data(conn, device_uuid, user_id, num_rides=30):
    """Create realistic rides with telemetry, events, and summaries"""
    cursor = conn.cursor()
    
    # Delete existing data for this device
    cursor.execute("DELETE FROM raw_ppg_telemetry WHERE device_id = %s", (device_uuid,))
    cursor.execute("DELETE FROM drowsiness_events WHERE device_id = %s", (device_uuid,))
    cursor.execute("""
        DELETE FROM ride_summaries WHERE ride_id IN 
        (SELECT id FROM rides WHERE device_id = %s)
    """, (device_uuid,))
    cursor.execute("DELETE FROM rides WHERE device_id = %s", (device_uuid,))
    conn.commit()
    
    baseline_rmssd = 45.8
    ride_ids = []
    
    print(f"\nCreating {num_rides} rides with complete data...")
    
    for i in range(num_rides):
        # Rides spread over last 30 days
        days_ago = num_rides - i - 1
        start_time = datetime.now() - timedelta(days=days_ago, hours=random.randint(8, 18))
        duration_seconds = random.randint(1800, 5400)  # 30-90 minutes
        end_time = start_time + timedelta(seconds=duration_seconds)
        
        # Vary HRV metrics to show trends
        avg_rmssd = baseline_rmssd + random.uniform(-8, 5)
        min_rmssd = avg_rmssd - random.uniform(5, 15)
        deviation_pct = ((avg_rmssd - baseline_rmssd) / baseline_rmssd) * 100
        
        # Recovery status based on deviation
        if deviation_pct < -15:
            recovery_status = 'slow'
        elif deviation_pct > 10:
            recovery_status = 'fast'
        else:
            recovery_status = 'normal'
        
        # Create ride
        cursor.execute("""
            INSERT INTO rides 
            (device_id, user_id, start_time, end_time, duration_seconds, 
             avg_hr, max_hr, min_hr, avg_rmssd, min_rmssd, baseline_rmssd, 
             baseline_deviation_pct, recovery_status, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            device_uuid, user_id, start_time, end_time, duration_seconds,
            random.uniform(65, 85),  # avg_hr
            random.uniform(90, 110),  # max_hr
            random.uniform(55, 65),   # min_hr
            avg_rmssd, min_rmssd, baseline_rmssd, deviation_pct,
            recovery_status, 'completed', start_time
        ))
        
        ride_id = cursor.fetchone()['id']
        ride_ids.append(str(ride_id))
        
        # Create telemetry data points (every 5 seconds)
        num_telemetry_points = duration_seconds // 5
        lat_base = -6.2000 + random.uniform(-0.01, 0.01)
        lon_base = 106.8167 + random.uniform(-0.01, 0.01)
        
        for j in range(num_telemetry_points):
            timestamp = start_time + timedelta(seconds=j * 5)
            
            # Simulate HRV declining over time (fatigue)
            time_progress = j / num_telemetry_points
            rmssd = avg_rmssd - (time_progress * random.uniform(2, 8))
            
            cursor.execute("""
                INSERT INTO raw_ppg_telemetry
                (device_id, ride_id, timestamp, hr, ibi_ms, sdnn, rmssd, pnn50, 
                 lf_hf_ratio, lat, lon, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                device_uuid, ride_id, timestamp,
                random.uniform(65, 85),  # hr
                random.uniform(700, 900),  # ibi_ms
                random.uniform(40, 60),  # sdnn
                rmssd,
                random.uniform(15, 30),  # pnn50
                random.uniform(1.2, 2.5),  # lf_hf_ratio
                lat_base + random.uniform(-0.001, 0.001),
                lon_base + random.uniform(-0.001, 0.001),
                timestamp
            ))
        
        # Create drowsiness events (random, more likely in fatigued rides)
        num_events = random.randint(0, 5) if deviation_pct < -10 else random.randint(0, 2)
        microsleep_count = 0
        total_drowsiness_events = num_events
        max_severity = 0
        severity_sum = 0
        
        for k in range(num_events):
            event_time = start_time + timedelta(seconds=random.randint(0, duration_seconds))
            severity_score = random.randint(3, 10)
            max_severity = max(max_severity, severity_score)
            severity_sum += severity_score
            
            if severity_score >= 8:
                status = 'MICROSLEEP'
                microsleep_count += 1
            elif severity_score >= 5:
                status = 'DROWSY'
            else:
                status = 'AWAKE'
            
            cursor.execute("""
                INSERT INTO drowsiness_events
                (ride_id, device_id, detected_at, severity_score, status,
                 hr_at_event, sdnn, rmssd, pnn50, lf_hf_ratio, lat, lon, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ride_id, device_uuid, event_time, severity_score, status,
                random.uniform(60, 75),
                random.uniform(30, 45),
                random.uniform(25, 35),
                random.uniform(10, 20),
                random.uniform(2.0, 3.5),
                lat_base, lon_base, event_time
            ))
        
        # Create ride summary
        avg_severity = (severity_sum / num_events) if num_events > 0 else 0
        fatigue_score = min(100, int(abs(deviation_pct) * 2 + (num_events * 5)))
        
        cursor.execute("""
            INSERT INTO ride_summaries
            (ride_id, fatigue_score, total_drowsiness_events, total_microsleep_events,
             max_drowsiness_score, avg_drowsiness_score, hrv_decline_pct, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ride_id, fatigue_score, total_drowsiness_events, microsleep_count,
            max_severity, avg_severity, abs(deviation_pct), end_time
        ))
        
        if (i + 1) % 5 == 0:
            print(f"  ✓ Created {i + 1}/{num_rides} rides")
        
        conn.commit()
    
    cursor.close()
    print(f"✓ Created {num_rides} rides with telemetry and events")
    return ride_ids

def query_all_tables(conn, device_uuid, user_id):
    """Query all tables for HELMET005 data"""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("QUERYING ALL TABLES FOR HELMET005")
    print("="*80)
    
    # 1. Users
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    print("\n1. USERS:")
    print(cursor.fetchone())
    
    # 2. Devices
    cursor.execute("SELECT * FROM devices WHERE id = %s", (device_uuid,))
    print("\n2. DEVICES:")
    print(cursor.fetchone())
    
    # 3. Baseline Metrics
    cursor.execute("SELECT * FROM baseline_metrics WHERE device_id = %s", (device_uuid,))
    print("\n3. BASELINE_METRICS:")
    print(cursor.fetchone())
    
    # 4. Rides
    cursor.execute("""
        SELECT id, start_time, end_time, duration_seconds, avg_hr, avg_rmssd, 
               baseline_deviation_pct, recovery_status, status
        FROM rides WHERE device_id = %s ORDER BY start_time DESC LIMIT 5
    """, (device_uuid,))
    print("\n4. RIDES (Last 5):")
    for row in cursor.fetchall():
        print(row)
    
    # 5. Raw PPG Telemetry
    cursor.execute("""
        SELECT COUNT(*) as total, 
               AVG(hr) as avg_hr, AVG(rmssd) as avg_rmssd, AVG(sdnn) as avg_sdnn
        FROM raw_ppg_telemetry WHERE device_id = %s
    """, (device_uuid,))
    print("\n5. RAW_PPG_TELEMETRY (Summary):")
    print(cursor.fetchone())
    
    # 6. Drowsiness Events
    cursor.execute("""
        SELECT COUNT(*) as total_events,
               SUM(CASE WHEN status = 'MICROSLEEP' THEN 1 ELSE 0 END) as microsleeps,
               AVG(severity_score) as avg_severity
        FROM drowsiness_events WHERE device_id = %s
    """, (device_uuid,))
    print("\n6. DROWSINESS_EVENTS (Summary):")
    print(cursor.fetchone())
    
    # 7. Ride Summaries
    cursor.execute("""
        SELECT rs.*, r.start_time
        FROM ride_summaries rs
        JOIN rides r ON r.id = rs.ride_id
        WHERE r.device_id = %s
        ORDER BY r.start_time DESC LIMIT 5
    """, (device_uuid,))
    print("\n7. RIDE_SUMMARIES (Last 5):")
    for row in cursor.fetchall():
        print(row)
    
    cursor.close()

def main():
    """Main execution"""
    print("="*80)
    print("UPLOADING DUMMY DATA FOR HELMET005 TO EC2 POSTGRESQL")
    print("="*80)
    print(f"\nConnecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Database: {DB_CONFIG['database']}")
    
    try:
        conn = get_connection()
        print("✓ Connected to PostgreSQL")
        
        # Step 1: Create user
        print("\n[STEP 1] Creating test user...")
        user_id = create_test_user(conn)
        
        # Step 2: Create device
        print("\n[STEP 2] Creating/updating device...")
        device_uuid = create_device(conn, user_id)
        
        # Step 3: Create baseline
        print("\n[STEP 3] Creating baseline metrics...")
        create_baseline(conn, device_uuid)
        
        # Step 4: Create rides with complete data
        print("\n[STEP 4] Creating rides with telemetry and events...")
        ride_ids = create_rides_with_data(conn, device_uuid, user_id, num_rides=30)
        
        # Step 5: Query all tables
        query_all_tables(conn, device_uuid, user_id)
        
        print("\n" + "="*80)
        print("✓ DUMMY DATA UPLOAD COMPLETE!")
        print("="*80)
        print(f"\nTest Credentials:")
        print(f"  Email: {TEST_USER_EMAIL}")
        print(f"  Password: {TEST_USER_PASSWORD}")
        print(f"  User ID: {user_id}")
        print(f"  Device ID: {DEVICE_ID}")
        print(f"  Device UUID: {device_uuid}")
        print(f"  Total Rides: {len(ride_ids)}")
        
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
