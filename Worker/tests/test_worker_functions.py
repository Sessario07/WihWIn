import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import math


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GENERAL_BASELINE = {
    "mean_hr": 70.0,
    "sdnn": 50.0,
    "rmssd": 40.0,
    "pnn50": 20.0,
    "lf_hf_ratio": 1.5,
    "sd1_sd2_ratio": 0.5
}


def sanitize_metrics(metrics):

    sanitized = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                sanitized[key] = 0.0
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized


def assess_drowsiness(current_metrics, baseline_metrics):
    drowsiness_score = 0
    alerts = []
    

    if current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.50:
        drowsiness_score += 3
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    elif current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.65:
        drowsiness_score += 2
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    elif current_metrics["sdnn"] < baseline_metrics["sdnn"] * 0.75:
        drowsiness_score += 1
        alerts.append(f"SDNN dropped {((baseline_metrics['sdnn'] - current_metrics['sdnn']) / baseline_metrics['sdnn'] * 100):.1f}%")
    

    if current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.45:
        drowsiness_score += 3
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    elif current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.60:
        drowsiness_score += 2
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    elif current_metrics["rmssd"] < baseline_metrics["rmssd"] * 0.70:
        drowsiness_score += 1
        alerts.append(f"RMSSD dropped {((baseline_metrics['rmssd'] - current_metrics['rmssd']) / baseline_metrics['rmssd'] * 100):.1f}%")
    
    if current_metrics["pnn50"] < baseline_metrics["pnn50"] * 0.40:
        drowsiness_score += 2
        alerts.append(f"pNN50 dropped {((baseline_metrics['pnn50'] - current_metrics['pnn50']) / baseline_metrics['pnn50'] * 100):.1f}%")
    elif current_metrics["pnn50"] < baseline_metrics["pnn50"] * 0.55:
        drowsiness_score += 1
        alerts.append(f"pNN50 dropped {((baseline_metrics['pnn50'] - current_metrics['pnn50']) / baseline_metrics['pnn50'] * 100):.1f}%")
    

    if current_metrics["lf_hf_ratio"] > baseline_metrics["lf_hf_ratio"] * 1.70:
        drowsiness_score += 2
        alerts.append(f"LF/HF increased {((current_metrics['lf_hf_ratio'] - baseline_metrics['lf_hf_ratio']) / baseline_metrics['lf_hf_ratio'] * 100):.1f}%")
    elif current_metrics["lf_hf_ratio"] > baseline_metrics["lf_hf_ratio"] * 1.50:
        drowsiness_score += 1
        alerts.append(f"LF/HF increased {((current_metrics['lf_hf_ratio'] - baseline_metrics['lf_hf_ratio']) / baseline_metrics['lf_hf_ratio'] * 100):.1f}%")
    
    ratio_diff = abs(current_metrics["sd1_sd2_ratio"] - baseline_metrics["sd1_sd2_ratio"])
    if ratio_diff > baseline_metrics["sd1_sd2_ratio"] * 0.60:
        drowsiness_score += 1
        alerts.append(f"SD1/SD2 ratio deviated by {(ratio_diff / baseline_metrics['sd1_sd2_ratio'] * 100):.1f}%")
    
    if drowsiness_score >= 11:
        status_label = "MICROSLEEP"
        should_alert = True
    elif drowsiness_score >= 8:
        status_label = "DROWSY"
        should_alert = True
    else:
        status_label = "AWAKE"
        should_alert = False
    
    return should_alert, drowsiness_score, status_label, alerts


def compute_hrv(ppg_data, sampling_rate):

    import neurokit2 as nk
    try:
        signals, info = nk.ppg_process(ppg_data, sampling_rate=sampling_rate)
        hrv_time = nk.hrv_time(info["PPG_Peaks"], sampling_rate=sampling_rate)
        hrv_freq = nk.hrv_frequency(info["PPG_Peaks"], sampling_rate=sampling_rate)
        hrv_nonlinear = nk.hrv_nonlinear(info["PPG_Peaks"], sampling_rate=sampling_rate)
        
        return {
            "sdnn": float(hrv_time["HRV_SDNN"].iloc[0]) if "HRV_SDNN" in hrv_time.columns else 0.0,
            "rmssd": float(hrv_time["HRV_RMSSD"].iloc[0]) if "HRV_RMSSD" in hrv_time.columns else 0.0,
            "pnn50": float(hrv_time["HRV_pNN50"].iloc[0]) if "HRV_pNN50" in hrv_time.columns else 0.0,
            "lf_hf_ratio": float(hrv_freq["HRV_LFHF"].iloc[0]) if "HRV_LFHF" in hrv_freq.columns else 0.0,
            "sd1_sd2_ratio": float(hrv_nonlinear["HRV_SD1"].iloc[0] / hrv_nonlinear["HRV_SD2"].iloc[0]) 
                           if "HRV_SD1" in hrv_nonlinear.columns and "HRV_SD2" in hrv_nonlinear.columns 
                           and hrv_nonlinear["HRV_SD2"].iloc[0] != 0 else 0.0
        }
    except Exception as e:
        print(f"HRV computation error: {e}")
        return None


class TestAssessDrowsiness:

    def test_awake_state_normal_metrics(self):

        current_metrics = {
            "sdnn": 48.0,
            "rmssd": 38.0,
            "pnn50": 19.0,
            "lf_hf_ratio": 1.6,
            "sd1_sd2_ratio": 0.52
        }
        
        should_alert, score, status, alerts = assess_drowsiness(current_metrics, GENERAL_BASELINE)
        
        assert should_alert is False
        assert status == "AWAKE"
        assert score < 8

    def test_drowsy_state_moderate_decline(self):

        current_metrics = {
            "sdnn": 25.0,     
            "rmssd": 18.0, 
            "pnn50": 8.0,     
            "lf_hf_ratio": 2.6, 
            "sd1_sd2_ratio": 0.1 
        }
        
        should_alert, score, status, alerts = assess_drowsiness(current_metrics, GENERAL_BASELINE)
        
        assert should_alert is True
        assert status in ["DROWSY", "MICROSLEEP"]
        assert score >= 8

    def test_microsleep_state_severe_decline(self):

        current_metrics = {
            "sdnn": 20.0,
            "rmssd": 15.0,
            "pnn50": 6.0,
            "lf_hf_ratio": 3.0,
            "sd1_sd2_ratio": 0.1
        }
        
        should_alert, score, status, alerts = assess_drowsiness(current_metrics, GENERAL_BASELINE)
        
        assert should_alert is True
        assert status == "MICROSLEEP"
        assert score >= 11

    def test_drowsiness_score_calculation(self):

        current_metrics = {
            "sdnn": 24.0,      
            "rmssd": 40.0,     
            "pnn50": 20.0,     
            "lf_hf_ratio": 1.5,
            "sd1_sd2_ratio": 0.5
        }
        
        should_alert, score, status, alerts = assess_drowsiness(current_metrics, GENERAL_BASELINE)
        
        assert score >= 3
        assert len(alerts) >= 1
        assert any("SDNN" in alert for alert in alerts)

    def test_alerts_contain_metric_names(self):

        current_metrics = {
            "sdnn": 25.0,
            "rmssd": 18.0,
            "pnn50": 8.0,
            "lf_hf_ratio": 2.6,
            "sd1_sd2_ratio": 0.1
        }
        
        should_alert, score, status, alerts = assess_drowsiness(current_metrics, GENERAL_BASELINE)
        
        assert len(alerts) > 0
        assert any("%" in alert for alert in alerts)


class TestComputeHRV:

    @patch('neurokit2.ppg_process')
    @patch('neurokit2.hrv_time')
    @patch('neurokit2.hrv_frequency')
    @patch('neurokit2.hrv_nonlinear')
    def test_compute_hrv_success(self, mock_nonlinear, mock_freq, mock_time, mock_process):

        import pandas as pd
        import numpy as np
        
        mock_signals = MagicMock()
        mock_info = {'PPG_Peaks': np.array([10, 60, 110, 160, 210])}
        mock_process.return_value = (mock_signals, mock_info)
        
        mock_time.return_value = pd.DataFrame({
            'HRV_SDNN': [50.0],
            'HRV_RMSSD': [40.0],
            'HRV_pNN50': [20.0]
        })
        mock_freq.return_value = pd.DataFrame({'HRV_LFHF': [1.5]})
        mock_nonlinear.return_value = pd.DataFrame({
            'HRV_SD1': [30.0],
            'HRV_SD2': [60.0]
        })
        
        ppg_data = [100 + i for i in range(250)]
        result = compute_hrv(ppg_data, sampling_rate=50)
        
        assert result is not None
        assert result["sdnn"] == 50.0
        assert result["rmssd"] == 40.0
        assert result["pnn50"] == 20.0
        assert result["lf_hf_ratio"] == 1.5
        assert result["sd1_sd2_ratio"] == 0.5

    @patch('neurokit2.ppg_process')
    def test_compute_hrv_handles_processing_error(self, mock_process):

        mock_process.side_effect = Exception("Processing error")
        
        ppg_data = [100 + i for i in range(250)]
        result = compute_hrv(ppg_data, sampling_rate=50)
        
        assert result is None


class TestSanitizeMetrics:

    def test_sanitize_normal_values(self):

        metrics = {"sdnn": 50.0, "rmssd": 40.0, "pnn50": 20.0}
        result = sanitize_metrics(metrics)
        
        assert result["sdnn"] == 50.0
        assert result["rmssd"] == 40.0
        assert result["pnn50"] == 20.0

    def test_sanitize_nan_values(self):

        metrics = {"sdnn": float('nan'), "rmssd": 40.0, "pnn50": float('nan')}
        result = sanitize_metrics(metrics)
        
        assert result["sdnn"] == 0.0
        assert result["rmssd"] == 40.0
        assert result["pnn50"] == 0.0

    def test_sanitize_inf_values(self):

        metrics = {"sdnn": float('inf'), "rmssd": float('-inf'), "pnn50": 20.0}
        result = sanitize_metrics(metrics)
        
        assert result["sdnn"] == 0.0
        assert result["rmssd"] == 0.0
        assert result["pnn50"] == 20.0

    def test_sanitize_non_float_values(self):

        metrics = {"sdnn": 50.0, "status": "AWAKE", "count": 5}
        result = sanitize_metrics(metrics)
        
        assert result["sdnn"] == 50.0
        assert result["status"] == "AWAKE"
        assert result["count"] == 5
