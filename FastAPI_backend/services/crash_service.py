from fastapi import HTTPException
from repositories.device_repository import DeviceRepository
from repositories.user_repository import UserRepository

class CrashService:
    @staticmethod
    def handle_crash(device_id: str, lat: float, lon: float, 
                     severity: str = "unknown", accel_magnitude: float = None,
                     accel_x: float = None, accel_y: float = None, accel_z: float = None) -> dict:
       
        device = DeviceRepository.get_device_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        device_uuid = device['id']
        user_id = device.get('user_id')
        
        hospital = UserRepository.find_nearest_hospital(lat, lon)
        
        notified_doctor_id = None
        distance_km = None
        hospital_name = None
        
        if hospital:
            notified_doctor_id = hospital['id']
            distance_km = hospital['distance_km']
            hospital_name = hospital['hospital_name']
      
        user_info = None
        if user_id:
            user_data = UserRepository.get_user_info(user_id)
            if user_data:
                user_info = {
                    "username": user_data['username'],
                    "email": user_data['email'],
                    "blood_type": user_data['blood_type'],
                    "allergies": user_data['allergies'],
                    "emergency_contact_name": user_data['emergency_contact_name'],
                    "emergency_contact_phone": user_data['emergency_contact_phone']
                }
        
        crash_id = UserRepository.create_crash_alert(
            device_uuid, lat, lon, notified_doctor_id, distance_km
        )
        
        return {
            "success": True,
            "crash_id": crash_id,
            "severity": severity,
            "accel_magnitude": accel_magnitude,
            "hospital_notified": hospital is not None,
            "hospital_name": hospital_name,
            "distance_km": distance_km,
            "user_info_included": user_info is not None,
            "user_info": user_info
        }
