import neurokit2 as nk
import numpy as np
import math
from fastapi import HTTPException
from repositories.device_repository import DeviceRepository
from repositories.baseline_repository import BaselineRepository

def safe_float(value, default=0.0):
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default

class BaselineService:
    @staticmethod
    def compute_baseline(device_id: str, samples: list, sample_rate: int = 50) -> dict:
        try:
            hr_values = []
            sdnn_values = []
            rmssd_values = []
            pnn50_values = []
            lf_hf_values = []
            sd1_sd2_values = []
            
            for i, ppg_data in enumerate(samples):
                try:
                    signals, info = nk.ppg_process(ppg_data, sampling_rate=sample_rate)
                    peaks = info["PPG_Peaks"]
                    
                    if len(peaks) < 2:
                        continue
                    
                    peak_intervals = []
                    for j in range(1, len(peaks)):
                        interval = (peaks[j] - peaks[j-1]) / sample_rate
                        peak_intervals.append(60.0 / interval)
                    
                    if peak_intervals:
                        hr = sum(peak_intervals) / len(peak_intervals)
                        hr_values.append(hr)
                    
                    try:
                        hrv_time = nk.hrv_time(peaks, sampling_rate=sample_rate, show=False)
                        if 'HRV_SDNN' in hrv_time.columns:
                            sdnn_values.append(safe_float(hrv_time['HRV_SDNN'].iloc[0], 50.0))
                        if 'HRV_RMSSD' in hrv_time.columns:
                            rmssd_values.append(safe_float(hrv_time['HRV_RMSSD'].iloc[0], 40.0))
                        if 'HRV_pNN50' in hrv_time.columns:
                            pnn50_values.append(safe_float(hrv_time['HRV_pNN50'].iloc[0], 20.0))
                    except Exception:
                        pass
                    
                    try:
                        hrv_freq = nk.hrv_frequency(peaks, sampling_rate=sample_rate, show=False)
                        if 'HRV_LFHF' in hrv_freq.columns:
                            lf_hf_values.append(safe_float(hrv_freq['HRV_LFHF'].iloc[0], 1.5))
                    except Exception:
                        pass
                    
                    try:
                        hrv_nonlinear = nk.hrv_nonlinear(peaks, sampling_rate=sample_rate, show=False)
                        if 'HRV_SD1' in hrv_nonlinear.columns and 'HRV_SD2' in hrv_nonlinear.columns:
                            sd1 = safe_float(hrv_nonlinear['HRV_SD1'].iloc[0], 30.0)
                            sd2 = safe_float(hrv_nonlinear['HRV_SD2'].iloc[0], 60.0)
                            if sd2 != 0:
                                sd1_sd2_values.append(sd1 / sd2)
                    except Exception:
                        pass
                    
                except Exception:
                    continue
            
            if len(hr_values) < 3:
                raise HTTPException(status_code=400, detail="Insufficient valid PPG samples to compute baseline")
            
            mean_hr = safe_float(np.mean(hr_values), 70.0)
            sdnn = safe_float(np.mean(sdnn_values), 50.0) if sdnn_values else 50.0
            rmssd = safe_float(np.mean(rmssd_values), 40.0) if rmssd_values else 40.0
            pnn50 = safe_float(np.mean(pnn50_values), 20.0) if pnn50_values else 20.0
            lf_hf_ratio = safe_float(np.mean(lf_hf_values), 1.5) if lf_hf_values else 1.5
            sd1_sd2_ratio = safe_float(np.mean(sd1_sd2_values), 0.5) if sd1_sd2_values else 0.5
            
            accel_var = 0.0
            
            hr_diffs = np.diff(hr_values) if len(hr_values) > 1 else []
            hr_decay_rate = safe_float(np.mean(np.abs(hr_diffs)), 0.0) if len(hr_diffs) > 0 else 0.0
            
            metrics = {
                'mean_hr': mean_hr,
                'sdnn': sdnn,
                'rmssd': rmssd,
                'pnn50': pnn50,
                'lf_hf_ratio': lf_hf_ratio,
                'sd1_sd2_ratio': sd1_sd2_ratio,
                'accel_var': accel_var,
                'hr_decay_rate': hr_decay_rate
            }
            
            device = DeviceRepository.get_device_by_id(device_id)
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            device_uuid = device['id']
            
            BaselineRepository.save_baseline(device_uuid, metrics)
            DeviceRepository.mark_onboarded(device_uuid)
            
            return metrics
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error computing baseline: {str(e)}")
