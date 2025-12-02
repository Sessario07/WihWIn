from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, time

class BaselineMetrics(BaseModel):
    mean_hr: float
    sdnn: float
    rmssd: float
    pnn50: float
    lf_hf_ratio: float
    sd1_sd2_ratio: float
    accel_var: float
    hr_decay_rate: float

class DeviceCheckResponse(BaseModel):
    exists: bool
    onboarded: bool
    baseline_metrics: Optional[BaselineMetrics]
    device_uuid: str
    message: str

class RideEvent(BaseModel):
    timestamp: Optional[time]
    status: str
    severity_score: int
    rmssd: Optional[float]

class HeartRateMetrics(BaseModel):
    avg: Optional[float]
    max: Optional[float]
    min: Optional[float]

class HRVMetrics(BaseModel):
    avg_rmssd: Optional[float]
    lowest_rmssd: Optional[float]
    baseline_rmssd: Optional[float]
    deviation_pct: Optional[float]

class RideDetailsResponse(BaseModel):
    ride_id: str
    date: Optional[date]
    start_time: Optional[time]
    end_time: Optional[time]
    duration_minutes: int
    heart_rate: HeartRateMetrics
    hrv: HRVMetrics
    events: List[RideEvent]
    fatigue_score: int
    recovery_status: str

class RideSummary(BaseModel):
    ride_id: str
    ride_number: int
    date: str
    start_time: str
    duration_minutes: int
    avg_rmssd: float
    lowest_rmssd: float
    baseline_rmssd: float
    deviation_pct: float
    alert_count: int
    microsleep_count: int
    fatigue_score: int
    recovery_status: str
    status_icon: str
