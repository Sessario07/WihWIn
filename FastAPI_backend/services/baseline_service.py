import neurokit2 as nk
import numpy as np
import math
from fastapi import HTTPException
from repositories.device_repository import DeviceRepository
from repositories.baseline_repository import BaselineRepository

def safe_float(value, default=0.0):
    """Convert value to float, returning default if NaN or infinite"""
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
            print(f"\n🧮 Computing baseline for device {device_id}")
            print(f"   Received {len(samples)} PPG samples at {sample_rate} Hz")
            
            # Process each PPG sample to extract HRV metrics
            all_peaks = []
            hr_values = []
            
            for i, ppg_data in enumerate(samples):
                try:
                    # Process PPG to find peaks
                    signals, info = nk.ppg_process(ppg_data, sampling_rate=sample_rate)
                    peaks = info["PPG_Peaks"]
                    
                    # Calculate HR from this sample
                    if len(peaks) > 1:
                        peak_intervals = []
                        for j in range(1, len(peaks)):
                            interval = (peaks[j] - peaks[j-1]) / sample_rate  # in seconds
                            peak_intervals.append(60.0 / interval)  # convert to BPM
                        hr = sum(peak_intervals) / len(peak_intervals)
                        hr_values.append(hr)
                    
                    # Accumulate all peaks for overall HRV computation
                    all_peaks.extend(peaks)
                    
                except Exception as e:
                    print(f"   ⚠ Warning: Failed to process sample {i+1}: {e}")
                    continue
            
            if len(all_peaks) < 2:
                raise HTTPException(status_code=400, detail="Insufficient PPG data to compute baseline")
            
            print(f"   ✓ Found {len(all_peaks)} total peaks from {len(samples)} samples")
            
            # Compute HRV metrics from all peaks
            hrv_metrics = nk.hrv_time(all_peaks, sampling_rate=sample_rate, show=False)
            
            mean_hr = safe_float(np.mean(hr_values), 70.0) if hr_values else 70.0
            sdnn = safe_float(hrv_metrics['HRV_SDNN'].iloc[0], 50.0) if 'HRV_SDNN' in hrv_metrics.columns else 50.0
            rmssd = safe_float(hrv_metrics['HRV_RMSSD'].iloc[0], 40.0) if 'HRV_RMSSD' in hrv_metrics.columns else 40.0
            pnn50 = safe_float(hrv_metrics['HRV_pNN50'].iloc[0], 20.0) if 'HRV_pNN50' in hrv_metrics.columns else 20.0
            
            # Frequency domain
            try:
                hrv_freq = nk.hrv_frequency(all_peaks, sampling_rate=sample_rate, show=False)
                lf_hf_ratio = safe_float(hrv_freq['HRV_LFHF'].iloc[0], 1.5) if 'HRV_LFHF' in hrv_freq.columns else 1.5
            except Exception as e:
                print(f"   ⚠ Frequency domain computation failed: {e}")
                lf_hf_ratio = 1.5
            
            # Nonlinear domain
            try:
                hrv_nonlinear = nk.hrv_nonlinear(all_peaks, sampling_rate=sample_rate, show=False)
                sd1 = safe_float(hrv_nonlinear['HRV_SD1'].iloc[0], 30.0) if 'HRV_SD1' in hrv_nonlinear.columns else 30.0
                sd2 = safe_float(hrv_nonlinear['HRV_SD2'].iloc[0], 60.0) if 'HRV_SD2' in hrv_nonlinear.columns else 60.0
                sd1_sd2_ratio = sd1 / sd2 if sd2 != 0 else 0.5
            except Exception as e:
                print(f"   ⚠ Nonlinear domain computation failed: {e}")
                sd1_sd2_ratio = 0.5
            
            # Placeholder for accel variance (simulator doesn't send accel in baseline)
            accel_var = 0.0
            
            # HR variability
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
            
            print(f"   ✓ Computed metrics:")
            print(f"     Mean HR: {mean_hr:.2f} bpm")
            print(f"     SDNN: {sdnn:.2f} ms")
            print(f"     RMSSD: {rmssd:.2f} ms")
            print(f"     pNN50: {pnn50:.2f} %")
            print(f"     LF/HF: {lf_hf_ratio:.2f}")
            print(f"     SD1/SD2: {sd1_sd2_ratio:.2f}")
            
            # Save to database
            device = DeviceRepository.get_device_by_id(device_id)
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            
            device_uuid = device['id']
            
            BaselineRepository.save_baseline(device_uuid, metrics)
            DeviceRepository.mark_onboarded(device_uuid)
            
            print(f"✓ Baseline saved to database")
            print(f"✓ Device marked as onboarded\n")
            
            return metrics
            
        except Exception as e:
            print(f"❌ Error computing baseline: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error computing baseline: {str(e)}")
