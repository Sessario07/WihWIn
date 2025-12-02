CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  
CREATE EXTENSION IF NOT EXISTS "cube";      
CREATE EXTENSION IF NOT EXISTS "earthdistance";  


CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('customer', 'doctor')),
    push_token TEXT, 
    created_at TIMESTAMP DEFAULT now(),
    last_login TIMESTAMP
);


CREATE TABLE customer_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    blood_type VARCHAR(5),
    allergies TEXT,
    pre_existing_conditions TEXT,
    current_medications TEXT,
    recent_medical_history TEXT,
    advance_directives TEXT,
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    updated_at TIMESTAMP DEFAULT now()
);


CREATE TABLE doctor_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    hospital_name VARCHAR(200) NOT NULL,
    lat FLOAT NOT NULL,  
    lon FLOAT NOT NULL,
    specialization VARCHAR(100),
    license_number VARCHAR(50),
    on_duty BOOLEAN DEFAULT TRUE,  
    created_at TIMESTAMP DEFAULT now()
);


CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE SET NULL,  
    device_id VARCHAR(64) UNIQUE NOT NULL,   
    onboarded BOOLEAN DEFAULT FALSE,         
    last_seen TIMESTAMP DEFAULT now(),
    battery_pct INT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE baseline_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    mean_hr FLOAT,
    sdnn FLOAT,
    rmssd FLOAT,
    pnn50 FLOAT,
    lf_hf_ratio FLOAT,
    sd1_sd2_ratio FLOAT,
    accel_var FLOAT,
    hr_decay_rate FLOAT,
    computed_at TIMESTAMP DEFAULT now()
);

CREATE TABLE rides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds INT,
    distance_km FLOAT,
    avg_hr FLOAT,
    max_hr FLOAT,
    min_hr FLOAT,
    avg_rmssd FLOAT,
    min_rmssd FLOAT,
    baseline_rmssd FLOAT,
    baseline_deviation_pct FLOAT,  
    recovery_status VARCHAR(20) CHECK (recovery_status IN ('slow', 'normal', 'fast')),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE drowsiness_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id UUID REFERENCES rides(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    detected_at TIMESTAMP NOT NULL,
    severity_score INT CHECK (severity_score >= 0 AND severity_score <= 11),  -- Drowsiness score (0-11)
    status VARCHAR(20) NOT NULL CHECK (status IN ('AWAKE', 'DROWSY', 'MICROSLEEP')),
    hr_at_event FLOAT,
    sdnn FLOAT,
    rmssd FLOAT,
    pnn50 FLOAT,
    lf_hf_ratio FLOAT,
    lat FLOAT,
    lon FLOAT,
    created_at TIMESTAMP DEFAULT now()
);


CREATE TABLE ride_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id UUID UNIQUE REFERENCES rides(id) ON DELETE CASCADE,
    fatigue_score INT CHECK (fatigue_score >= 0 AND fatigue_score <= 100),  -- Overall fatigue (0-100)
    total_drowsiness_events INT DEFAULT 0,
    total_microsleep_events INT DEFAULT 0,
    max_drowsiness_score INT,
    avg_drowsiness_score FLOAT,
    hrv_decline_pct FLOAT,  
    total_distance_km FLOAT,
    avg_speed_kmh FLOAT,
    computed_at TIMESTAMP DEFAULT now()
);

CREATE TABLE daily_hrv_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    avg_rmssd FLOAT,
    min_rmssd FLOAT,
    max_rmssd FLOAT,
    avg_sdnn FLOAT,
    avg_lf_hf_ratio FLOAT,
    baseline_rmssd FLOAT,
    deviation_pct FLOAT,
    total_ride_duration_seconds INT,
    total_rides INT,
    moving_avg_7day FLOAT, 
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(user_id, date)
);


CREATE TABLE hourly_fatigue_heatmap (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    hour_of_day INT CHECK (hour_of_day >= 0 AND hour_of_day <= 23),
    avg_deviation_pct FLOAT,
    event_count INT DEFAULT 0,
    severity_level VARCHAR(20) CHECK (severity_level IN ('normal', 'medium', 'high')),
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE(user_id, date, hour_of_day)
);


CREATE TABLE raw_ppg_telemetry (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    ride_id UUID REFERENCES rides(id) ON DELETE SET NULL,  
    timestamp TIMESTAMP NOT NULL,
    hr FLOAT,
    ibi_ms FLOAT,
    sdnn FLOAT,  
    rmssd FLOAT,
    pnn50 FLOAT,
    lf_hf_ratio FLOAT,
    accel_x FLOAT,
    accel_y FLOAT,
    accel_z FLOAT,
    lat FLOAT,
    lon FLOAT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE hrv_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    mean_hr FLOAT,
    sdnn FLOAT,
    rmssd FLOAT,
    pnn50 FLOAT,
    lf_hf_ratio FLOAT,
    sd1_sd2_ratio FLOAT,
    accel_var FLOAT,
    hr_decay_rate FLOAT,
    microsleep_risk FLOAT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE telemetry_log (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    ts TIMESTAMP,
    hr FLOAT,
    accel_x FLOAT,
    accel_y FLOAT,
    accel_z FLOAT,
    lat FLOAT,
    lon FLOAT,
    pressure FLOAT,
    battery_pct INT
);


CREATE TABLE crash_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    ride_id UUID REFERENCES rides(id) ON DELETE SET NULL,
    lat FLOAT NOT NULL,
    lon FLOAT NOT NULL,
    detected_at TIMESTAMP DEFAULT now(),
    hospital_notified BOOLEAN DEFAULT FALSE,
    notified_doctor_id UUID REFERENCES users(id),
    distance_km FLOAT,  
    notification_sent_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_devices_user_id ON devices(user_id);
CREATE INDEX idx_devices_device_id ON devices(device_id);
CREATE INDEX idx_doctor_location ON doctor_profiles(lat, lon);
CREATE INDEX idx_baseline_metrics_device_id ON baseline_metrics(device_id);


CREATE INDEX idx_rides_device_id ON rides(device_id);
CREATE INDEX idx_rides_user_id ON rides(user_id);
CREATE INDEX idx_rides_start_time ON rides(start_time);
CREATE INDEX idx_rides_status ON rides(status);


CREATE INDEX idx_drowsiness_events_ride_id ON drowsiness_events(ride_id);
CREATE INDEX idx_drowsiness_events_device_id ON drowsiness_events(device_id);
CREATE INDEX idx_drowsiness_events_detected_at ON drowsiness_events(detected_at);
CREATE INDEX idx_drowsiness_events_status ON drowsiness_events(status);


CREATE INDEX idx_ride_summaries_ride_id ON ride_summaries(ride_id);


CREATE INDEX idx_daily_hrv_user_date ON daily_hrv_summary(user_id, date);


CREATE INDEX idx_hourly_fatigue_user_date ON hourly_fatigue_heatmap(user_id, date, hour_of_day);


CREATE INDEX idx_raw_ppg_device_id ON raw_ppg_telemetry(device_id);
CREATE INDEX idx_raw_ppg_ride_id ON raw_ppg_telemetry(ride_id);
CREATE INDEX idx_raw_ppg_timestamp ON raw_ppg_telemetry(timestamp);


CREATE INDEX idx_hrv_sessions_device_id ON hrv_sessions(device_id);
CREATE INDEX idx_hrv_sessions_created_at ON hrv_sessions(created_at);
CREATE INDEX idx_crash_device_id ON crash_alerts(device_id);
CREATE INDEX idx_crash_ride_id ON crash_alerts(ride_id);
CREATE INDEX idx_crash_detected_at ON crash_alerts(detected_at);