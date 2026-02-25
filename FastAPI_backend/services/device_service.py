from repositories.device_repository import DeviceRepository
from repositories.baseline_repository import BaselineRepository
from models.response_models import DeviceCheckResponse, BaselineMetrics
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class DeviceService:
    @staticmethod
    async def check_device(device_id: str) -> DeviceCheckResponse:
        try:
            device = await DeviceRepository.get_device_by_id(device_id)
        except Exception as e:
            logger.error(f"DB error looking up device {device_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error while looking up device")
        
        if not device:
            try:
                device_uuid = await DeviceRepository.create_device(device_id)
            except Exception as e:
                logger.error(f"DB error creating device {device_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error while creating device")
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
            try:
                baseline_data = await BaselineRepository.get_latest_baseline(device_uuid)
                if baseline_data:
                    baseline_metrics = BaselineMetrics(**baseline_data)
            except Exception as e:
                logger.error(f"DB error fetching baseline for device {device_id}: {e}")
        
        return DeviceCheckResponse(
            exists=True,
            onboarded=onboarded,
            baseline_metrics=baseline_metrics,
            device_uuid=str(device_uuid),
            message="Device onboarded" if onboarded else "Device needs onboarding"
        )
