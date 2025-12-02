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
    def compute_baseline(device_id: str, samples: list) -> dict:
        
        try:
            print(f"\n Computing baseline for device {device_id}")
            print(f"   Received {len(samples)} samples")
            
            hr_values = [s.hr for s in samples]
            ibi_values = [s.ibi_ms for s in samples]
            accel_x = [s.accel_x for s in samples]
            accel_y = [s.accel_y for s in samples]
            accel_z = [s.accel_z for s in samples]
            

            print(f"Converting {len(ibi_values)} IBI values to peak indices")
            rr_intervals = np.array(ibi_values)
            peaks = nk.intervals_to_peaks(rr_intervals)
            print(f"Converted to {len(peaks)} peak indices")
            

            hrv_metrics = nk.hrv_time(peaks, sampling_rate=1000, show=False)
            
            mean_hr = safe_float(np.mean(hr_values), 70.0)
            sdnn = safe_float(hrv_metrics['HRV_SDNN'].iloc[0], 50.0) if 'HRV_SDNN' in hrv_metrics.columns else 50.0
            rmssd = safe_float(hrv_metrics['HRV_RMSSD'].iloc[0], 40.0) if 'HRV_RMSSD' in hrv_metrics.columns else 40.0
            pnn50 = safe_float(hrv_metrics['HRV_pNN50'].iloc[0], 20.0) if 'HRV_pNN50' in hrv_metrics.columns else 20.0
            

            try:
                hrv_freq = nk.hrv_frequency(peaks, sampling_rate=1000, show=False)
                lf_hf_ratio = safe_float(hrv_freq['HRV_LFHF'].iloc[0], 1.5) if 'HRV_LFHF' in hrv_freq.columns else 1.5
            except Exception as e:
                print(f"Frequency domain computation failed: {e}")
                lf_hf_ratio = 1.5
            

            try:
                hrv_nonlinear = nk.hrv_nonlinear(peaks, sampling_rate=1000, show=False)
                sd1 = safe_float(hrv_nonlinear['HRV_SD1'].iloc[0], 30.0) if 'HRV_SD1' in hrv_nonlinear.columns else 30.0
                sd2 = safe_float(hrv_nonlinear['HRV_SD2'].iloc[0], 60.0) if 'HRV_SD2' in hrv_nonlinear.columns else 60.0
                sd1_sd2_ratio = sd1 / sd2 if sd2 != 0 else 0.5
            except Exception as e:
                print(f"Nonlinear domain computation failed: {e}")
                sd1_sd2_ratio = 0.5
            

            accel_var = safe_float(np.var(accel_x) + np.var(accel_y) + np.var(accel_z), 0.0)
            

            hr_diffs = np.diff(hr_values)
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
            
            print(f"metrics:")
            print(f"     Mean HR: {mean_hr:.2f} bpm")
            print(f"     SDNN: {sdnn:.2f} ms")
            print(f"     RMSSD: {rmssd:.2f} ms")
            print(f"     pNN50: {pnn50:.2f} %")
            print(f"     LF/HF: {lf_hf_ratio:.2f}")
            print(f"     SD1/SD2: {sd1_sd2_ratio:.2f}")
            

            device = DeviceRepository.get_device_by_id(device_id)
            if not device:
                raise HTTPException(status_code=404, detail="No device")
            
            device_uuid = device['id']
            

            BaselineRepository.save_baseline(device_uuid, metrics)
            DeviceRepository.mark_onboarded(device_uuid)
            
            print(f"Baseline saved to database")
            print(f"Device is onboarded\n")
            
            return metrics
            
        except Exception as e:
            print(f"Error baseline: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error baseline: {str(e)}")
