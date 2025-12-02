from repositories.device_repository import DeviceRepository
from repositories.baseline_repository import BaselineRepository
from models.response_models import DeviceCheckResponse, BaselineMetrics

class DeviceService:
    @staticmethod
    def check_device(device_id: str) -> DeviceCheckResponse:
        
        device = DeviceRepository.get_device_by_id(device_id)
        
        if not device:
            
            device_uuid = DeviceRepository.create_device(device_id)
            return DeviceCheckResponse(
                exists=False,
                onboarded=False,
                baseline_metrics=None,
                device_uuid=str(device_uuid),
                message="Device created - needs onboarding"
            )
        
        device_uuid = device['id']
        onboarded = device['onboarded']
        
      
        baseline_metrics = None
        if onboarded:
            baseline_data = BaselineRepository.get_latest_baseline(device_uuid)
            if baseline_data:
                baseline_metrics = BaselineMetrics(**baseline_data)
        
        return DeviceCheckResponse(
            exists=True,
            onboarded=onboarded,
            baseline_metrics=baseline_metrics,
            device_uuid=str(device_uuid),
            message="Device onboarded" if onboarded else "Device needs onboarding"
        )
