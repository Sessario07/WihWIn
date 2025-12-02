from pydantic import BaseModel
from typing import List, Optional

class BaselineSample(BaseModel):
    hr: float
    ibi_ms: float
    accel_x: float
    accel_y: float
    accel_z: float

class BaselineRequest(BaseModel):
    device_id: str
    samples: List[BaselineSample]

class CrashAlert(BaseModel):
    device_id: str
    lat: float
    lon: float
    severity: Optional[str] = "unknown"  
    accel_magnitude: Optional[float] = None
    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None

class TelemetryBatch(BaseModel):
    device_id: str
    ride_id: Optional[str] = None
    telemetry: List[dict]

class RideStart(BaseModel):
    device_id: str

class RideEnd(BaseModel):
    ride_id: str

class DrowsinessEvent(BaseModel):
    device_id: str
    ride_id: str
    severity_score: int
    status: str
    hr_at_event: float
    sdnn: float
    rmssd: float
    pnn50: float
    lf_hf_ratio: float
    lat: float
    lon: float
