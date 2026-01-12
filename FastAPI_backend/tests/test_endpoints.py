import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_fastAPI import app

client = TestClient(app)


class TestRideStartEndpoint:

    @patch('services.ride_service.DeviceRepository')
    @patch('services.ride_service.RideRepository')
    def test_start_ride_success(self, mock_ride_repo, mock_device_repo):

        device_uuid = str(uuid.uuid4())
        ride_uuid = str(uuid.uuid4())
        
        mock_device_repo.get_device_by_id.return_value = {
            'id': device_uuid,
            'device_id': 'TEST-DEVICE-001',
            'user_id': str(uuid.uuid4())
        }
        mock_ride_repo.get_active_ride.return_value = None
        mock_ride_repo.create_ride.return_value = ride_uuid
        
        response = client.post("/rides/start", json={"device_id": "TEST-DEVICE-001"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["ride_id"] == ride_uuid
        assert "message" in data

    @patch('services.ride_service.DeviceRepository')
    def test_start_ride_device_not_found(self, mock_device_repo):

        mock_device_repo.get_device_by_id.return_value = None
        
        response = client.post("/rides/start", json={"device_id": "INVALID-DEVICE"})
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('services.ride_service.DeviceRepository')
    @patch('services.ride_service.RideRepository')
    def test_start_ride_already_active(self, mock_ride_repo, mock_device_repo):

        device_uuid = str(uuid.uuid4())
        existing_ride_id = str(uuid.uuid4())
        
        mock_device_repo.get_device_by_id.return_value = {
            'id': device_uuid,
            'device_id': 'TEST-DEVICE-001',
            'user_id': None
        }
        mock_ride_repo.get_active_ride.return_value = {'id': existing_ride_id}
        
        response = client.post("/rides/start", json={"device_id": "TEST-DEVICE-001"})
        
        assert response.status_code == 200
        assert response.json()["ride_id"] == existing_ride_id


class TestRideEndEndpoint:

    @patch('services.ride_service.publish_ride_end')
    @patch('services.ride_service.RideRepository')
    def test_end_ride_success(self, mock_ride_repo, mock_publish):

        ride_id = str(uuid.uuid4())
        mock_ride_repo.mark_ride_ending.return_value = True
        mock_publish.return_value = None
        
        response = client.post(f"/rides/{ride_id}/end")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ride_id"] == ride_id

    @patch('services.ride_service.RideRepository')
    def test_end_ride_not_found(self, mock_ride_repo):

        ride_id = str(uuid.uuid4())
        mock_ride_repo.mark_ride_ending.return_value = False
        mock_ride_repo.get_ride_by_id.return_value = None
        
        response = client.post(f"/rides/{ride_id}/end")
        
        assert response.status_code == 404

    @patch('services.ride_service.RideRepository')
    def test_end_ride_already_completed(self, mock_ride_repo):

        ride_id = str(uuid.uuid4())
        mock_ride_repo.mark_ride_ending.return_value = False
        mock_ride_repo.get_ride_by_id.return_value = {
            'id': ride_id,
            'status': 'completed'
        }
        
        response = client.post(f"/rides/{ride_id}/end")
        
        assert response.status_code == 200
        assert "already completed" in response.json()["message"].lower()


class TestCrashEndpoint:

    @patch('services.crash_service.UserRepository')
    @patch('services.crash_service.DeviceRepository')
    def test_crash_alert_with_hospital(self, mock_device_repo, mock_user_repo):

        device_uuid = str(uuid.uuid4())
        user_uuid = str(uuid.uuid4())
        doctor_uuid = str(uuid.uuid4())
        
        mock_device_repo.get_device_by_id.return_value = {
            'id': device_uuid,
            'user_id': user_uuid
        }
        mock_user_repo.find_nearest_hospital.return_value = {
            'id': doctor_uuid,
            'hospital_name': 'Test Hospital',
            'distance_km': 2.5
        }
        mock_user_repo.get_user_info.return_value = {
            'username': 'testuser',
            'email': 'test@example.com',
            'blood_type': 'O+',
            'allergies': None,
            'emergency_contact_name': 'Emergency Contact',
            'emergency_contact_phone': '+1234567890'
        }
        mock_user_repo.create_crash_alert.return_value = str(uuid.uuid4())
        
        response = client.post("/crash", json={
            "device_id": "TEST-DEVICE-001",
            "lat": 40.7128,
            "lon": -74.0060,
            "severity": "high",
            "accel_magnitude": 8.5
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["hospital_notified"] is True
        assert data["hospital_name"] == "Test Hospital"

    @patch('services.crash_service.DeviceRepository')
    def test_crash_alert_device_not_found(self, mock_device_repo):

        mock_device_repo.get_device_by_id.return_value = None
        
        response = client.post("/crash", json={
            "device_id": "INVALID-DEVICE",
            "lat": 40.7128,
            "lon": -74.0060
        })
        
        assert response.status_code == 404

    @patch('services.crash_service.UserRepository')
    @patch('services.crash_service.DeviceRepository')
    def test_crash_alert_no_hospital_nearby(self, mock_device_repo, mock_user_repo):
        device_uuid = str(uuid.uuid4())
        
        mock_device_repo.get_device_by_id.return_value = {
            'id': device_uuid,
            'user_id': None
        }
        mock_user_repo.find_nearest_hospital.return_value = None
        mock_user_repo.create_crash_alert.return_value = str(uuid.uuid4())
        
        response = client.post("/crash", json={
            "device_id": "TEST-DEVICE-001",
            "lat": 40.7128,
            "lon": -74.0060
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["hospital_notified"] is False


class TestBaselineEndpoint:


    @patch('services.baseline_service.BaselineRepository')
    @patch('services.baseline_service.DeviceRepository')
    @patch('services.baseline_service.nk')
    def test_compute_baseline_success(self, mock_nk, mock_device_repo, mock_baseline_repo):

        import numpy as np
        import pandas as pd
        
        device_uuid = str(uuid.uuid4())
        
        mock_signals = MagicMock()
        mock_info = {'PPG_Peaks': np.array([10, 60, 110, 160, 210])}
        mock_nk.ppg_process.return_value = (mock_signals, mock_info)
        
        mock_hrv_time = pd.DataFrame({
            'HRV_SDNN': [50.0],
            'HRV_RMSSD': [40.0],
            'HRV_pNN50': [20.0]
        })
        mock_nk.hrv_time.return_value = mock_hrv_time
        
        mock_hrv_freq = pd.DataFrame({'HRV_LFHF': [1.5]})
        mock_nk.hrv_frequency.return_value = mock_hrv_freq
        
        mock_hrv_nonlinear = pd.DataFrame({
            'HRV_SD1': [30.0],
            'HRV_SD2': [60.0]
        })
        mock_nk.hrv_nonlinear.return_value = mock_hrv_nonlinear
        
        mock_device_repo.get_device_by_id.return_value = {'id': device_uuid}
        mock_baseline_repo.save_baseline.return_value = None
        mock_device_repo.mark_onboarded.return_value = None
        
        samples = [[100 + i for i in range(250)] for _ in range(5)]
        
        response = client.post("/baseline", json={
            "device_id": "TEST-DEVICE-001",
            "samples": samples,
            "sample_rate": 50
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "metrics" in data

    @patch('services.baseline_service.DeviceRepository')
    @patch('services.baseline_service.nk')
    def test_compute_baseline_device_not_found(self, mock_nk, mock_device_repo):
  
        import numpy as np
        import pandas as pd
        

        mock_signals = MagicMock()
        mock_info = {'PPG_Peaks': np.array([10, 60, 110, 160, 210])}
        mock_nk.ppg_process.return_value = (mock_signals, mock_info)
        mock_nk.hrv_time.return_value = pd.DataFrame({
            'HRV_SDNN': [50.0], 'HRV_RMSSD': [40.0], 'HRV_pNN50': [20.0]
        })
        mock_nk.hrv_frequency.return_value = pd.DataFrame({'HRV_LFHF': [1.5]})
        mock_nk.hrv_nonlinear.return_value = pd.DataFrame({
            'HRV_SD1': [30.0], 'HRV_SD2': [60.0]
        })
        
        mock_device_repo.get_device_by_id.return_value = None
        
        samples = [[100 + i for i in range(250)] for _ in range(5)]
        
        response = client.post("/baseline", json={
            "device_id": "INVALID-DEVICE",
            "samples": samples,
            "sample_rate": 50
        })
        
        assert response.status_code == 500
        assert "Device not found" in response.json()["detail"]
